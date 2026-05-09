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
    last_metrics_len = 0
    
    def clear_metrics():
        nonlocal last_metrics_len
        if last_metrics_len > 0:
            print("\b" * last_metrics_len, end="", flush=True)
            print(" " * last_metrics_len, end="", flush=True)
            print("\b" * last_metrics_len, end="", flush=True)
            last_metrics_len = 0

    for event in generator:
        if event["type"] == "content":
            clear_metrics()
            # Stream text live
            print(f"{Fore.GREEN}{event['text']}{Style.RESET_ALL}", end="", flush=True)
        
        elif event["type"] == "metrics":
            clear_metrics()
            tokens = event.get('tokens', 0)
            elapsed = event.get('elapsed', 0)
            metrics_str = f" {Fore.LIGHTBLACK_EX}({tokens}t, {elapsed:.1f}s){Style.RESET_ALL}"
            plain_metrics = f" ({tokens}t, {elapsed:.1f}s)"
            last_metrics_len = len(plain_metrics)
            print(metrics_str, end="", flush=True)

        elif event["type"] == "system":
            clear_metrics()
            print(f"{Fore.LIGHTBLACK_EX}{event['content']}{Style.RESET_ALL}")
            
        elif event["type"] == "system_stream":
            clear_metrics()
            print(f"{Fore.LIGHTBLACK_EX}{event['text']}{Style.RESET_ALL}", end="", flush=True)
            
        elif event["type"] == "error":
            clear_metrics()
            print(f"{Fore.RED}{event['content']}{Style.RESET_ALL}")
            
        elif event["type"] == "usage":
            clear_metrics()
            prompt = event.get('prompt_tokens')
            completion = event.get('completion_tokens', 0)
            elapsed = event.get('time_elapsed', 0)
            tps = completion / elapsed if elapsed > 0 else 0
            
            prompt_str = f"{prompt} prompt, " if prompt is not None else ""
            print(f"{Fore.MAGENTA}\n[Usage: {prompt_str}{completion} completion | {elapsed:.1f}s | {tps:.1f} tps]{Style.RESET_ALL}")
            
        elif event["type"] == "tools_active":
            clear_metrics()
            default_part = f"{Fore.LIGHTBLACK_EX}{', '.join(event['default'])}{Style.RESET_ALL}"
            routed_part  = f"{Fore.CYAN}{', '.join(event['routed'])}{Style.RESET_ALL}" if event["routed"] else ""
            tools_str = default_part + (f"{Fore.LIGHTBLACK_EX}, {Style.RESET_ALL}" + routed_part if routed_part else "")
            print(f"{Fore.LIGHTBLACK_EX}Active tools: {Style.RESET_ALL}{tools_str}")
            
        elif event["type"] == "approval_needed":
            clear_metrics()
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

def print_sessions(limit=5):
    sessions = session_manager.list_sessions(limit=limit)
    if not sessions:
        print(f"{Fore.YELLOW}No sessions found.{Style.RESET_ALL}")
        return
    
    print(f"{Fore.CYAN}Latest {len(sessions)} sessions:{Style.RESET_ALL}")
    for i, s in enumerate(sessions):
        print(f"  {Fore.YELLOW}[{i+1}]{Style.RESET_ALL} {s}")

def main():
    print(f"{Fore.MAGENTA}=== MyAICode Local Agent Harness (V2 Stream) ==={Style.RESET_ALL}")
    
    args = sys.argv[1:]
    session_name = None
    state_dict = None
    
    # Handle CLI arguments
    if args:
        cmd = args[0].lower()
        if cmd == "new":
            session_name = session_manager.get_new_session_name()
            print(f"{Fore.CYAN}Starting new session: {session_name}.json{Style.RESET_ALL}")
        elif cmd == "session":
            if len(args) > 1:
                target = args[1]
                resolved = session_manager.resolve_session_name(target)
                if resolved:
                    state_dict = session_manager.load_session(resolved)
                    if state_dict:
                        session_name = resolved
                        print(f"{Fore.CYAN}Loaded session: {session_name}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Error: Failed to load session '{resolved}'{Style.RESET_ALL}")
                        sys.exit(1)
                else:
                    print(f"{Fore.RED}Error: Session '{target}' not found.{Style.RESET_ALL}")
                    sys.exit(1)
            else:
                print(f"{Fore.RED}Usage: python main.py session <name|index>{Style.RESET_ALL}")
                sys.exit(1)
        elif cmd == "sessions":
            if len(args) > 1:
                sub = args[1].lower()
                if sub == "delete":
                    if len(args) > 2:
                        target = args[2]
                        if session_manager.delete_session(target):
                            print(f"{Fore.GREEN}Session '{target}' deleted.{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Error: Could not delete session '{target}'.{Style.RESET_ALL}")
                        sys.exit(0)
                    else:
                        print(f"{Fore.RED}Usage: python main.py sessions delete <name|index>{Style.RESET_ALL}")
                        sys.exit(1)
                elif sub == "deleteall":
                    count = session_manager.delete_all_sessions()
                    print(f"{Fore.GREEN}Deleted {count} sessions.{Style.RESET_ALL}")
                    sys.exit(0)
                elif sub.isdigit():
                    print_sessions(limit=int(sub))
                    sys.exit(0)
                else:
                    print(f"{Fore.RED}Unknown sessions command: {sub}{Style.RESET_ALL}")
                    sys.exit(1)
            else:
                print_sessions()
                sys.exit(0)
        else:
            print(f"{Fore.RED}Unknown command: {cmd}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Available commands:{Style.RESET_ALL}")
            print("  new                   - Start new session")
            print("  session <name|index>  - Start with specific session")
            print("  sessions [limit]      - List recent sessions")
            print("  sessions delete <idx> - Delete a session")
            print("  sessions deleteall    - Delete all sessions")
            sys.exit(1)
            
    # Default behavior: load last or start new
    if not session_name:
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
                print(f"  {Fore.CYAN}/sessions [n]{Style.RESET_ALL}- List latest n sessions")
                print(f"  {Fore.CYAN}/save [name]{Style.RESET_ALL} - Save session to file")
                print(f"  {Fore.CYAN}/load <name|idx>{Style.RESET_ALL} - Load a session from file (autosaves current)")
                print(f"  {Fore.CYAN}/exit{Style.RESET_ALL}    - Exit the application")
                continue
                
            if cmd.startswith('/sessions'):
                parts = cmd.split()
                limit = 5
                if len(parts) > 1 and parts[1].isdigit():
                    limit = int(parts[1])
                print_sessions(limit=limit)
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
                new_name = agent.session_name
                if len(parts) > 1:
                    new_name = parts[1].strip()
                
                path = session_manager.save_session(new_name, agent.context.export_state())
                if path:
                    agent.session_name = new_name
                    print(f"{Fore.GREEN}Session saved to: {path}{Style.RESET_ALL}")
                continue
                
            if cmd.startswith('/load'):
                parts = cmd.split(maxsplit=1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    resolved = session_manager.resolve_session_name(target)
                    if resolved:
                        session_manager.save_session(agent.session_name, agent.context.export_state())
                        data = session_manager.load_session(resolved)
                        if data:
                            agent.session_name = resolved
                            agent.context.import_state(data)
                            agent._update_system_prompt()
                            print(f"{Fore.GREEN}Session loaded: {agent.session_name}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Failed to load session: {resolved}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Session '{target}' not found.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: /load <name|idx>{Style.RESET_ALL}")
                continue
                
            if cmd == '/compact':
                agent.context.prune_if_needed(llm_client=agent.llm, force=True)
                print(f"{Fore.GREEN}Context compacted! Current size: {agent.context.get_total_tokens()} tokens.{Style.RESET_ALL}")
                continue
                
            if not user_input.strip():
                continue
                
            gen = agent.run(user_input=user_input)
            consume_agent_events(agent, gen)
            
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
