from llm_client import LLMClient

def test_summarization():
    llm = LLMClient()
    
    recent_context = [
        {"role": "user", "content": "Can you show me the output of `ls -la`?"},
        {"role": "assistant", "content": "Sure, I'll run that command now."}
    ]
    
    # A fake, extremely bloated tool output
    bloated_content = """
    Okay, so I went ahead and searched the entire codebase for references to `LLMClient`. 
    This is a very important class that handles all of the communication with the local inference server! 
    I found several matches across multiple files. Here is the raw output from the ripgrep command I just ran for you:
    
    agent.py:12:        self.llm = LLMClient()
    agent.py:49:        routed_names = self.llm.route_request(messages, get_tool_descriptions())
    agent.py:118:            for chunk in self.llm.chat_stream(messages, tools=self.active_tool_schemas):
    main.py:14:    agent = Agent()
    llm_client.py:6:class LLMClient:
    llm_client.py:11:        self.client = OpenAI(
    
    As you can see, the `agent.py` file is heavily dependent on this class. It initializes it in the constructor on line 12, uses it for routing on line 49, and streams chat responses on line 118.
    The `main.py` file doesn't actually import it directly, it just imports `Agent`.
    
    Also, I noticed that you're using OpenAI API format for the local model. That's a great choice because it makes it super easy to swap in different models later! 
    If you ever want to use a different model, you just need to change the `MODEL_NAME` config variable in `config.py`.
    
    Anyway, I hope this ripgrep output was helpful. Do you want me to look at how `route_request` is implemented next? Or maybe we can look at the `ContextManager`? Let me know what you think! I am ready to help you with whatever you need.
    """
    
    print("Testing AI Summarization...")
    print("--------------------------------------------------")
    print("Original Length:", len(bloated_content))
    print("Sending to LLM...")
    
    summary = llm.summarize_content(bloated_content, recent_context)
    
    print("--------------------------------------------------")
    print("Summarized Output:")
    print(summary)
    print("--------------------------------------------------")
    print("Summary Length:", len(summary))

if __name__ == "__main__":
    test_summarization()
