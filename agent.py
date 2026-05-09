import json
import colorama
from colorama import Fore, Style
from context_manager import ContextManager
from llm_client import LLMClient
from tools import execute_tool

colorama.init()

class Agent:
    def __init__(self):
        self.context = ContextManager()
        self.llm = LLMClient()
        self.system_prompt = """You are MyAICode, an expert AI programming assistant.
You have access to tools to view files, edit files, and run terminal commands.
Always verify the context and read files before editing them.
Do NOT try to output entire files. Use `replace_file_content` to surgically edit files.
If a user asks you to do something, use the tools available to accomplish it, then report back."""
        self.context.set_system_prompt(self.system_prompt)

    def run_interaction_loop(self, user_input: str):
        self.context.add_message("user", content=user_input)
        
        while True:
            print(f"{Fore.CYAN}Thinking (Context: {self.context.get_total_tokens()} tokens)...{Style.RESET_ALL}")
            
            # 1. Get messages
            messages = self.context.get_messages_for_api()
            
            # 2. Call LLM
            response_message = self.llm.chat(messages)
            
            if not response_message:
                print(f"{Fore.RED}Failed to get response from LLM.{Style.RESET_ALL}")
                break
                
            # 3. Add assistant message to context
            tool_calls = response_message.tool_calls
            content = response_message.content
            
            # Some local models return raw dicts, others return objects. Handle both.
            tc_list = []
            if tool_calls:
                for tc in tool_calls:
                    tc_dict = {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    tc_list.append(tc_dict)
            
            self.context.add_message("assistant", content=content, tool_calls=tc_list if tc_list else None)

            # 4. Print text response if any
            if content:
                print(f"{Fore.GREEN}Assistant: {content}{Style.RESET_ALL}")

            # 5. Execute tools if any
            if not tool_calls:
                break # Agent is done with its thought process
                
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}
                    
                print(f"{Fore.YELLOW}Executing tool: {function_name}({function_args}){Style.RESET_ALL}")
                
                # Execute
                result_str, is_ephemeral = execute_tool(function_name, function_args)
                
                # Print a small snippet of the result
                snippet = result_str[:200] + ("..." if len(result_str) > 200 else "")
                print(f"{Fore.LIGHTBLACK_EX}Result: {snippet}{Style.RESET_ALL}")
                
                # Add result to context
                self.context.add_message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tool_call.id,
                    name=function_name,
                    ephemeral=is_ephemeral
                )
