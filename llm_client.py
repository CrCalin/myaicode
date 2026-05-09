from openai import OpenAI
import config
from tools import TOOLS

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            base_url=config.API_BASE_URL,
            api_key=config.API_KEY
        )

    def route_request(self, messages: list, tools_description: str) -> list:
        """
        Calls the LLM quickly to decide which tools to use.
        Returns a list of tool names.
        """
        router_system = f"""You are a tool routing assistant. The user wants to accomplish a task.
Available tools:
{tools_description}

Reply with ONLY a comma-separated list of the tool names that might be required to fulfill this request. Do not include spaces or quotes. For example: replace_file_content,search_web
"""
        router_messages = [{"role": "system", "content": router_system}]
        # Append the last few user/assistant messages to give context
        router_messages.extend(messages[-3:])
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=router_messages,
                temperature=0.0,
                max_tokens=50
            )
            content = response.choices[0].message.content
            if not content: return []
            
            # Clean up the output
            return [t.strip() for t in content.split(",") if t.strip()]
        except Exception as e:
            print(f"\n[Router API Error]: {e}")
            return []

    def chat_stream(self, messages: list, tools: list = None):
        """
        Yields chunks from the LLM. 
        Each chunk is either a text delta or a tool call delta.
        Also attempts to yield usage statistics if provided by the server.
        """
        try:
            # We request stream=True and try to ask for usage stats
            kwargs = {
                "model": config.MODEL_NAME,
                "messages": messages,
                "temperature": 0.0,
                "stream": True,
                "stream_options": {"include_usage": True}
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            
            for chunk in response:
                yield chunk
                
        except Exception as e:
            print(f"\n[LLM API Error]: {e}")
            yield None
