import json
from context_manager import ContextManager
from llm_client import LLMClient
from tools import execute_tool, RequiresApproval

class Agent:
    def __init__(self):
        self.context = ContextManager()
        self.llm = LLMClient()
        self.system_prompt = """You are MyAICode, an expert AI programming assistant.
You have access to tools to view/edit files, run terminal commands, search the codebase, and search the web.

CRITICAL INSTRUCTIONS:
1. ONLY USE local system tools (view/edit/terminal/search) WHEN ABSOLUTELY NECESSARY to fulfill the user's specific request.
2. USE THE `search_web` TOOL LIBERALLY for general questions, facts, or API documentation. If `search_web` returns a useful link, use `read_url` to read the full documentation page!
3. If you need to find where a function or class is defined, use `search_codebase` instead of guessing file paths.
4. When editing files, use `replace_file_content`. NOTE: The harness will automatically run a syntax checker after you edit a file. If the tool returns a syntax error, YOU MUST generate another tool call to fix your mistake!
5. If you have enough information to fulfill the request, output your final answer and DO NOT use tools.
"""
        self.context.set_system_prompt(self.system_prompt)

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
            self.context.add_message("user", content=user_input)

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
                resume_tool_call = None
                continue # Loop back to let the LLM think about the tool result

            # Normal LLM turn
            messages = self.context.get_messages_for_api()
            yield {"type": "system", "content": f"\nThinking (Context estimated: {self.context.get_total_tokens()} tokens)..."}
            
            content = ""
            tool_calls = {}
            
            for chunk in self.llm.chat_stream(messages):
                if chunk is None:
                    yield {"type": "error", "content": "Failed to get response from LLM."}
                    return
                    
                # Handle exact usage if supported by the server
                if hasattr(chunk, 'usage') and chunk.usage:
                    self.context.calibrate_overhead(chunk.usage.prompt_tokens)
                    yield {
                        "type": "usage", 
                        "prompt_tokens": chunk.usage.prompt_tokens, 
                        "completion_tokens": chunk.usage.completion_tokens
                    }

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
