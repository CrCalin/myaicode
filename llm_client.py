from openai import OpenAI
import tiktoken
import config
from tools import TOOLS

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            base_url=config.API_BASE_URL,
            api_key=config.API_KEY,
            timeout=60.0  # Fail loudly after 60s instead of hanging forever
        )
        self._encoder = tiktoken.get_encoding("cl100k_base")
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in a string using the cl100k_base encoder."""
        if not text:
            return 0
        return len(self._encoder.encode(text))

    def route_request(self, messages: list, tools_description: str) -> list:
        """
        Calls the LLM to decide which tools to use. Uses streaming to avoid
        hanging on servers that return empty non-streaming responses.
        Returns a list of tool names.
        """
        router_system = f"""You are a tool routing assistant. The user wants to accomplish a task.
Available tools:
{tools_description}

CRITICAL: If the user wants to edit or create a file, you MUST route to `replace_file_content`. NEVER rely on `run_terminal_command` for file editing (e.g. sed, echo, cat).

Reply with ONLY a comma-separated list of the tool names that might be required to fulfill this request. Be liberal with using tools - if in doubt, include it. Do not include spaces or quotes. For example: replace_file_content,search_web
"""
        # Flatten into a single user message. Local models often have buggy `system` role templates!
        chat_history = [m for m in messages if m["role"] != "system"]
        
        flat_prompt = router_system + "\n\nChat History:\n"
        for m in chat_history[-3:]:
            content = str(m.get("content") or "")
            flat_prompt += f"{m['role'].upper()}: {content}\n"
            
        flat_prompt += "\nWhich tools do you need?"
            
        router_messages = [{"role": "user", "content": flat_prompt}]
        
        try:
            # Use streaming + max_tokens to prevent hanging on servers that return
            # empty non-streaming responses (e.g. when model tries to call a tool)
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=router_messages,
                temperature=0.1,
                max_tokens=800,
                stream=True,
                extra_body=config.UTILITY_EXTRA_BODY
            )
            content = ""
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    content += delta.content
            
            if not content:
                return []
            
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
        Uses the LLM to aggressively compress a large block of text.
        """
        system_prompt = (
            "You are an aggressive, LOSSY text compression engine. Your mission is to maximize token reduction by any means necessary. "
            "Target 80-95% compression. You are explicitly authorized to DROP information that is not critical to the current task. "
            "Be ruthless: delete filler, pleasantries, repetition, and verbose explanations. "
            "Preserve ONLY vital technical anchors: core file paths, key function names, critical error messages, and final decisions. "
            "If a long code block is present, summarize its logic in 1-2 lines unless it was the specific subject of the last 2 messages. "
            "Use ultra-terse notation, abbreviations, and bullet points. Omit all non-essential parts of speech. "
            "Do NOT explain your reasoning. Output ONLY the compressed result."
        )
        
        # Flatten recent context to help the summarizer understand what is important
        flat_context = ""
        for m in recent_context:
            if m["role"] != "system":
                flat_context += f"{m['role'].upper()}: {m['content']}\n"
                
        user_prompt = f"Recent Conversation Context:\n{flat_context}\n\nCONTENT TO COMPRESS:\n{content_to_summarize}\n\nRemember: Output ONLY the ultra-compressed result. Drop all low-value details."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            original_tokens = max(1, len(self._encoder.encode(content_to_summarize)))

            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                temperature=0.0,
                stream=True,
                extra_body=config.UTILITY_EXTRA_BODY
            )
            result = ""
            token_count = 0
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    result += delta.content
                    token_count += 1
                    print(f"\r[Compacting: {token_count}/{original_tokens} tokens]", end="", flush=True)
            reduction = max(0, 100 - int(token_count / original_tokens * 100))
            print(f"\r[Compacting: {token_count}/{original_tokens} tokens — {reduction}% reduction]")
            return result
        except Exception as e:
            print(f"\n[Summarizer API Error]: {e}")
            return "[Compression Failed]"
