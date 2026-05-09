import sys
from agent import Agent
import colorama
from colorama import Fore, Style

colorama.init()

def consume_agent_events(agent: Agent, generator):
    """Helper to consume events from the agent generator and handle UI concerns."""
    for event in generator:
        if event["type"] == "content":
            # Stream text live
            print(f"{Fore.GREEN}{event['text']}{Style.RESET_ALL}", end="", flush=True)
        
        elif event["type"] == "system":
            print(f"{Fore.LIGHTBLACK_EX}{event['content']}{Style.RESET_ALL}")
            
        elif event["type"] == "error":
            print(f"{Fore.RED}{event['content']}{Style.RESET_ALL}")
            
        elif event["type"] == "usage":
            print(f"{Fore.MAGENTA}\n[Exact Usage: {event['prompt_tokens']} prompt, {event['completion_tokens']} completion]{Style.RESET_ALL}")
            
        elif event["type"] == "approval_needed":
            print(f"\n{Fore.RED}[!] Agent wants to run potentially destructive command:{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}> {event['command']}{Style.RESET_ALL}")
            choice = input("Allow? (y/N): ")
            
            approved = choice.lower() == 'y'
            if not approved:
                print(f"{Fore.RED}Command rejected.{Style.RESET_ALL}")
                # Tell the agent it was rejected by sending a fake tool result
                agent.context.add_message(
                    role="tool",
                    content="Command execution rejected by user.",
                    tool_call_id=event['tool_call']['id'],
                    name=event['tool_call']['function']['name'],
                    ephemeral=False
                )
                # Resume normal execution (no pending tool call)
                new_gen = agent.run()
                consume_agent_events(agent, new_gen)
            else:
                # Resume with approval
                new_gen = agent.run(resume_tool_call=event['tool_call'], approved=True)
                consume_agent_events(agent, new_gen)

def main():
    print(f"{Fore.MAGENTA}=== MyAICode Local Agent Harness (V2 Stream) ==={Style.RESET_ALL}")
    print("Type your request. Type 'exit' or 'quit' to stop.")
    
    agent = Agent()
    
    if len(sys.argv) > 1:
        initial_prompt = " ".join(sys.argv[1:])
        print(f"{Fore.BLUE}User: {initial_prompt}{Style.RESET_ALL}")
        gen = agent.run(user_input=initial_prompt)
        consume_agent_events(agent, gen)
    
    while True:
        try:
            user_input = input(f"\n{Fore.BLUE}User: {Style.RESET_ALL}")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
                
            gen = agent.run(user_input=user_input)
            consume_agent_events(agent, gen)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
