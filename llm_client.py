from openai import OpenAI
import config
from tools import TOOLS

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            base_url=config.API_BASE_URL,
            api_key=config.API_KEY
        )

    def chat_stream(self, messages: list):
        """
        Yields chunks from the LLM. 
        Each chunk is either a text delta or a tool call delta.
        Also attempts to yield usage statistics if provided by the server.
        """
        try:
            # We request stream=True and try to ask for usage stats
            # Some local servers might not support stream_options, but it's safe to pass to OpenAI client usually.
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.0,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            for chunk in response:
                yield chunk
                
        except Exception as e:
            print(f"\n[LLM API Error]: {e}")
            yield None
