import sys
from agent import Agent
from colorama import Fore, Style

def main():
    print(f"{Fore.MAGENTA}=== MyAICode Local Agent Harness ==={Style.RESET_ALL}")
    print("Type your request. Type 'exit' or 'quit' to stop.")
    
    agent = Agent()
    
    # Check if user passed a prompt as an argument
    if len(sys.argv) > 1:
        initial_prompt = " ".join(sys.argv[1:])
        print(f"{Fore.BLUE}User: {initial_prompt}{Style.RESET_ALL}")
        agent.run_interaction_loop(initial_prompt)
    
    while True:
        try:
            user_input = input(f"\n{Fore.BLUE}User: {Style.RESET_ALL}")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
                
            agent.run_interaction_loop(user_input)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
