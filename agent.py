import json
import datetime
import platform
import os
import time
import config
from context_manager import ContextManager
from llm_client import LLMClient
from tools import execute_tool, RequiresApproval, get_tool_descriptions, get_tools_by_names

class Agent:
    def __init__(self, state_dict=None, session_name=None):
        self.context = ContextManager()
        if state_dict:
            self.context.import_state(state_dict)
            
        self.session_name = session_name
        self.llm = LLMClient()
        self.chat_start_time = datetime.datetime.now()
        self.base_system_prompt = """You are MyAICode, an expert AI programming assistant.
You have access to tools to view/edit files, run terminal commands, search the codebase, and search the web.

CRITICAL INSTRUCTIONS:
1. ONLY USE local system tools (view/edit/terminal/search) WHEN ABSOLUTELY NECESSARY to fulfill the user's specific request.
2. USE THE `search_web` TOOL LIBERALLY for general questions, facts, or API documentation. If `search_web` returns a useful link, use `read_url` to read the full documentation page!
3. If you need to find where a function or class is defined, use `search_codebase` instead of guessing file paths.
4. When editing or creating files, you MUST EXCLUSIVELY use the `replace_file_content` tool. NEVER use bash commands (like sed, echo, awk, etc.) to modify files. NOTE: The harness will automatically run a syntax checker after you edit a file. If the tool returns a syntax error, YOU MUST generate another tool call to fix your mistake!
5. If you have enough information to fulfill the request, output your final answer and DO NOT use tools.
6. NEVER view, edit, or run commands on files outside the Current Working Directory (and its subdirectories) unless explicitly instructed to do so by the user.
7. If the user asks you to build, refactor, or implement a feature that is even slightly complex, ALWAYS use the `manage_plan` tool to structure your approach BEFORE you start modifying files.
"""
        self._update_system_prompt()
        self.always_active_tools = ["replace_file_content", "run_terminal_command", "view_file_lines", "list_directory_tree", "manage_plan"]
        self.active_tool_schemas = get_tools_by_names(self.always_active_tools)

    def _update_system_prompt(self):
        now = datetime.datetime.now()
        dynamic_context = f"""
ENVIRONMENT CONTEXT:
- Chat Session Started: {self.chat_start_time.strftime('%Y-%m-%d %H:%M:%S')}
- Current Date/Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
- Operating System: {platform.system()} {platform.release()}
- Current Working Directory: {os.getcwd()}
"""
        if self.context.plan:
            dynamic_context += f"\nCURRENT TASK PLAN:\n{self.context.plan}\n"
            
        self.context.set_system_prompt(self.base_system_prompt + "\n" + dynamic_context)

    def _determine_active_tools(self, user_input: str):
        defaults = set(self.always_active_tools)
        
        # Call router
        messages = self.context.get_messages_for_api()
        routed_names = self.llm.route_request(messages, get_tool_descriptions())
        
        active_names = defaults | set(routed_names)
        self.active_tool_schemas = get_tools_by_names(list(active_names))
        
        # Filter out LLM hallucinations — only keep names that exist in the schema registry
        valid_names = {t["function"]["name"] for t in self.active_tool_schemas}
        return {
            "default": [n for n in self.always_active_tools if n in valid_names],
            "routed":  [n for n in valid_names if n not in defaults]
        }

    def run(self, user_input: str = None, resume_tool_call=None, approved=False):
        """
        Generator that yields events.
        Events:
        - {"type": "content", "text": str}
        - {"type": "system", "content": str}
        - {"type": "error", "content": str}
        - {"type": "approval_needed", "command": str, "tool_call": dict}
        - {"type": "usage", "prompt_tokens": int, "completion_tokens": int}
        """
        if user_input:
            self._update_system_prompt()
            self.context.add_message("user", content=user_input)

            # Explicitly prune BEFORE routing so we know exactly when a slow AI compaction happens
            if self.context.get_total_tokens() > config.SAFE_CONTEXT_THRESHOLD:
                yield {"type": "system", "content": "\n[Context near limit — compacting before routing...]"}
                self.context.prune_if_needed(llm_client=self.llm)

            yield {"type": "system", "content": "\nRouting tools..."}
            tool_groups = self._determine_active_tools(user_input)
            yield {"type": "tools_active", "default": tool_groups["default"], "routed": tool_groups["routed"]}

        while True:
            if resume_tool_call:
                # We are resuming from an approval pause
                tc = resume_tool_call
                function_name = tc['function']['name']
                try:
                    function_args = json.loads(tc['function']['arguments'])
                except json.JSONDecodeError:
                    function_args = {}
                    
                if function_name == "run_terminal_command" and approved:
                    function_args['approved'] = True
                    
                yield {"type": "system", "content": f"\nExecuting tool: {function_name}({function_args})"}
                try:
                    result_str, is_ephemeral = execute_tool(function_name, function_args)
                except RequiresApproval as e:
                    # Should not happen since we passed approved=True
                    yield {"type": "error", "content": "Failed to bypass approval check."}
                    return

                snippet = result_str[:200] + ("..." if len(result_str) > 200 else "")
                yield {"type": "system", "content": f"Result: {snippet}"}
                
                self.context.add_message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tc["id"],
                    name=function_name,
                    ephemeral=is_ephemeral
                )
                # Cheap silent prune after tool results (no AI summarization here)
                self.context.prune_if_needed(llm_client=None)
                resume_tool_call = None
                continue # Loop back to let the LLM think about the tool result

            # Normal LLM turn
            messages = self.context.get_messages_for_api()
            yield {"type": "system", "content": f"\nThinking (Context estimated: {self.context.get_total_tokens()} tokens)..."}
            
            content = ""
            tool_calls = {}
            start_time = time.time()
            usage_emitted = False
            
            for chunk in self.llm.chat_stream(messages, tools=self.active_tool_schemas):
                if chunk is None:
                    yield {"type": "error", "content": "Failed to get response from LLM."}
                    return
                    
                # Handle exact usage if supported by the server
                if hasattr(chunk, 'usage') and chunk.usage:
                    self.context.calibrate_overhead(chunk.usage.prompt_tokens)
                    yield {
                        "type": "usage", 
                        "prompt_tokens": chunk.usage.prompt_tokens, 
                        "completion_tokens": chunk.usage.completion_tokens,
                        "time_elapsed": time.time() - start_time
                    }
                    usage_emitted = True

                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    content += delta.content
                    yield {"type": "content", "text": delta.content}
                    
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": ""}}
                        if tc.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                
                # Emit live metrics for every chunk (content or tool call)
                current_tokens = self.llm.count_tokens(content)
                for tc in tool_calls.values():
                    current_tokens += self.llm.count_tokens(tc["function"]["name"])
                    current_tokens += self.llm.count_tokens(tc["function"]["arguments"])
                
                yield {
                    "type": "metrics",
                    "tokens": current_tokens,
                    "elapsed": time.time() - start_time
                }

            # Turn is over, assemble history
            elapsed = time.time() - start_time
            
            # If usage wasn't emitted (common on some local servers), estimate it
            if not usage_emitted:
                completion_tokens = self.llm.count_tokens(content)
                # Also count tool call tokens if any
                for tc in tool_calls.values():
                    completion_tokens += self.llm.count_tokens(tc["function"]["name"])
                    completion_tokens += self.llm.count_tokens(tc["function"]["arguments"])
                
                yield {
                    "type": "usage",
                    "prompt_tokens": None, # We don't know the exact prompt tokens without server help
                    "completion_tokens": completion_tokens,
                    "time_elapsed": elapsed
                }

            # Turn is over, assemble history
            tc_list = [tc for idx, tc in sorted(tool_calls.items())]
            self.context.add_message("assistant", content=content, tool_calls=tc_list if tc_list else None)
            
            if not tc_list:
                break # Agent is done
                
            # Execute pending tools
            for tc in tc_list:
                function_name = tc["function"]["name"]
                try:
                    function_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    function_args = {}
                    
                yield {"type": "system", "content": f"\nExecuting tool: {function_name}({function_args})"}
                try:
                    if function_name == "manage_plan":
                        action = function_args.get("action", "set")
                        if action == "clear":
                            self.context.plan = None
                            result_str = "Plan cleared successfully."
                        else:
                            self.context.plan = function_args.get("content", "")
                            result_str = "Plan updated successfully. It will be injected into your prompt."
                        is_ephemeral = True
                        self._update_system_prompt() # Instantly refresh prompt
                    else:
                        result_str, is_ephemeral = execute_tool(function_name, function_args)
                except RequiresApproval as e:
                    yield {"type": "approval_needed", "command": e.command, "tool_call": tc}
                    return # Stop generator until UI resumes it
                    
                snippet = result_str[:200] + ("..." if len(result_str) > 200 else "")
                yield {"type": "system", "content": f"Result: {snippet}"}
                
                self.context.add_message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tc["id"],
                    name=function_name,
                    ephemeral=is_ephemeral
                )
                # Cheap silent prune after tool results (no AI summarization here)
                self.context.prune_if_needed(llm_client=None)
