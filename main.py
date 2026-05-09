import sys
import atexit
import session_manager
try:
    import readline
except ImportError:
    pass

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
            
        elif event["type"] == "system_stream":
            print(f"{Fore.LIGHTBLACK_EX}{event['text']}{Style.RESET_ALL}", end="", flush=True)
            
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
    
    args = sys.argv[1:]
    is_new = False
    
    if args:
        if args[0].lower() == "new":
            is_new = True
            if len(args) > 1:
                print(f"{Fore.RED}Usage: python main.py [new]{Style.RESET_ALL}")
                sys.exit(1)
        else:
            print(f"{Fore.RED}Usage: python main.py [new]{Style.RESET_ALL}")
            sys.exit(1)
        
    session_name = None
    state_dict = None
    
    if is_new:
        session_name = session_manager.get_new_session_name()
        print(f"{Fore.CYAN}Starting new session: {session_name}.json{Style.RESET_ALL}")
    else:
        last_session = session_manager.get_last_session()
        if last_session:
            state_dict = session_manager.load_session(last_session)
            if state_dict:
                session_name = last_session
                print(f"{Fore.CYAN}Loaded previous session: {session_name}{Style.RESET_ALL}")
            else:
                session_name = session_manager.get_new_session_name()
                print(f"{Fore.CYAN}Starting new session: {session_name}.json{Style.RESET_ALL}")
        else:
            session_name = session_manager.get_new_session_name()
            print(f"{Fore.CYAN}Starting new session: {session_name}.json{Style.RESET_ALL}")
            
    agent = Agent(state_dict=state_dict, session_name=session_name)
    
    def save_on_exit():
        if agent.session_name:
            session_manager.save_session(agent.session_name, agent.context.export_state())
            
    atexit.register(save_on_exit)

    print("Type your request. Type '/help' to see available commands.")
    
    
    while True:
        try:
            user_input = input(f"\n{Fore.BLUE}User: {Style.RESET_ALL}")
            cmd = user_input.strip().lower()
            
            if cmd in ['/exit', '/quit']:
                break
                
            if cmd == '/help':
                print(f"{Fore.YELLOW}Available Commands:{Style.RESET_ALL}")
                print(f"  {Fore.CYAN}/help{Style.RESET_ALL}    - Show this help message")
                print(f"  {Fore.CYAN}/compact{Style.RESET_ALL} - Force compact the context by truncating old tool outputs")
                print(f"  {Fore.CYAN}/new{Style.RESET_ALL}        - Start a fresh session (autosaves current)")
                print(f"  {Fore.CYAN}/save [name]{Style.RESET_ALL} - Save session to file")
                print(f"  {Fore.CYAN}/load <name>{Style.RESET_ALL} - Load a session from file (autosaves current)")
                print(f"  {Fore.CYAN}/exit{Style.RESET_ALL}    - Exit the application")
                continue
                
            if cmd == '/new':
                session_manager.save_session(agent.session_name, agent.context.export_state())
                agent.session_name = session_manager.get_new_session_name()
                agent.context.import_state({})
                agent._update_system_prompt()
                print(f"{Fore.CYAN}Started new session: {agent.session_name}.json{Style.RESET_ALL}")
                continue
                
            if cmd.startswith('/save'):
                parts = cmd.split(maxsplit=1)
                if len(parts) > 1:
                    agent.session_name = parts[1].strip()
                path = session_manager.save_session(agent.session_name, agent.context.export_state())
                print(f"{Fore.GREEN}Session saved to: {path}{Style.RESET_ALL}")
                continue
                
            if cmd.startswith('/load'):
                parts = cmd.split(maxsplit=1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    session_manager.save_session(agent.session_name, agent.context.export_state())
                    data = session_manager.load_session(target)
                    if data:
                        agent.session_name = target
                        if not agent.session_name.endswith(".json"):
                            agent.session_name += ".json"
                        agent.context.import_state(data)
                        agent._update_system_prompt()
                        print(f"{Fore.GREEN}Session loaded: {agent.session_name}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Failed to load session: {target}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: /load <session_name>{Style.RESET_ALL}")
                continue
                
            if cmd == '/compact':
                agent.context.prune_if_needed(llm_client=agent.llm, force=True)
                print(f"{Fore.GREEN}Context compacted! Current size: {agent.context.get_total_tokens()} tokens.{Style.RESET_ALL}")
                continue
                
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
