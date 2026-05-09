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
        # Flatten into a single user message. Local models often have buggy `system` role templates!
        chat_history = [m for m in messages if m["role"] != "system"]
        
        flat_prompt = router_system + "\n\nChat History:\n"
        for m in chat_history[-3:]:
            flat_prompt += f"{m['role'].upper()}: {m['content']}\n"
            
        flat_prompt += "\nWhich tools do you need?"
            
        router_messages = [{"role": "user", "content": flat_prompt}]
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=router_messages,
                temperature=0.1
            )
            content = response.choices[0].message.content
            if not content: return []
            
            # Clean up the output by extracting all words, making it immune to conversational hallucinations
            import re
            return re.findall(r'[a-zA-Z_]+', content)
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

    def summarize_content(self, content_to_summarize: str, recent_context: list) -> str:
        """
        Uses the LLM to losslessly compress a large block of text.
        """
        system_prompt = "You are a highly efficient text compression algorithm. Your job is to summarize the following content, stripping out conversational fluff, but keeping ALL vital technical information (exact file paths, exact code snippets, logic decisions, error messages). Do not respond conversationally. Output ONLY the compressed summary."
        
        # Flatten recent context to help the summarizer understand what is important
        flat_context = ""
        for m in recent_context:
            if m["role"] != "system":
                flat_context += f"{m['role'].upper()}: {m['content']}\n"
                
        user_prompt = f"Recent Conversation Context:\n{flat_context}\n\nCONTENT TO COMPRESS:\n{content_to_summarize}\n\nRemember: Output ONLY the compressed summary. Keep technical details intact."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"\n[Summarizer API Error]: {e}")
            return "[Compression Failed]"
