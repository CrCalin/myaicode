from openai import OpenAI
import config
from tools import TOOLS

class LLMClient:
    def __init__(self):
        # We use a dummy API key because most local servers (llama.cpp) don't need one, 
        # but the OpenAI client requires the argument.
        self.client = OpenAI(
            base_url=config.API_BASE_URL,
            api_key=config.API_KEY
        )

    def chat(self, messages: list):
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.0,
            )
            return response.choices[0].message
        except Exception as e:
            print(f"\n[LLM API Error]: {e}")
            return None
