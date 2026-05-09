import tiktoken
import config

class ContextManager:
    def __init__(self):
        self.messages = []
        # tiktoken gives a good enough estimate for Llama models for context management purposes
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.system_prompt = "You are a helpful AI coding assistant."
        # Local models inject the tools schema into the prompt, which adds hundreds of tokens.
        # We start with an estimate and calibrate it dynamically based on the exact usage.
        self.token_overhead = 200
        self.plan = None

    def set_system_prompt(self, prompt):
        self.system_prompt = prompt

    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def _get_message_tokens(self, message: dict) -> int:
        tokens = 0
        if "content" in message and message["content"]:
            tokens += self.count_tokens(str(message["content"]))
        if "tool_calls" in message and message["tool_calls"]:
            for call in message["tool_calls"]:
                tokens += self.count_tokens(str(call))
        return tokens + 20 # Overhead per message

    def get_total_tokens(self) -> int:
        total = self.count_tokens(self.system_prompt)
        for msg in self.messages:
            total += self._get_message_tokens(msg)
        return total + self.token_overhead

    def calibrate_overhead(self, exact_prompt_tokens: int):
        # Calculate what our manual estimate was without overhead
        estimated_without_overhead = self.get_total_tokens() - self.token_overhead
        # The new overhead is the difference between exact and our manual estimate
        # (This accounts for tools schema, jinja templates, and tokenizer differences)
        self.token_overhead = exact_prompt_tokens - estimated_without_overhead

    def add_message(self, role: str, content: str = None, tool_calls=None, tool_call_id=None, name=None, ephemeral=False, llm_client=None):
        msg = {"role": role}
        if content is not None:
            msg["content"] = content
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        if name is not None:
            msg["name"] = name
            
        msg["_ephemeral"] = ephemeral # Custom flag to track if this can be safely pruned early
        
        self.messages.append(msg)
        self.prune_if_needed(llm_client=llm_client)

    def prune_if_needed(self, llm_client=None, force=False):
        # We need to prune if we are exceeding the safe threshold OR if forced
        while (force or self.get_total_tokens() > config.SAFE_CONTEXT_THRESHOLD) and len(self.messages) > 2:
            # Pruning strategy:
            # 1. Try to find the oldest ephemeral message (like a huge command output) and summarize/truncate it
            # 2. If no ephemeral messages, try to compact large regular messages (user/assistant)
            # 3. If everything is compacted, start dropping the oldest interactions
            
            pruned = False
            
            # Step 1: Look for old ephemeral messages to truncate
            # We skip the most recent few messages so the agent doesn't immediately forget what it just read (unless forced)
            end_idx = len(self.messages) if force else len(self.messages) - 3
            for i in range(max(0, end_idx)):
                msg = self.messages[i]
                if msg.get("_ephemeral") and msg["role"] == "tool" and isinstance(msg.get("content"), str):
                    if len(msg["content"]) > 500:
                        content_to_sum = msg["content"]
                        if len(content_to_sum) > 15000:
                            content_to_sum = content_to_sum[:7500] + "\n...[Middle truncated prior to summarization]...\n" + content_to_sum[-7500:]
                            
                        if llm_client:
                            print("\n[Compacting large tool output via AI...]")
                            summary = llm_client.summarize_content(content_to_sum, self.messages[-3:])
                            msg["content"] = f"[AI Summary of Tool Output]:\n{summary}"
                        else:
                            msg["content"] = "[Content truncated by Context Manager to save space. Run tool again if needed.]\n" + msg["content"][:200]
                            
                        msg["_ephemeral"] = False # Mark as already truncated
                        pruned = True
                        break
                        
                        
            if not pruned:
                # Step 2: Look for non-ephemeral large messages to compact
                for i in range(max(0, end_idx)):
                    msg = self.messages[i]
                    if isinstance(msg.get("content"), str) and len(msg["content"]) > 1000 and not msg.get("_compacted"):
                        content_to_sum = msg["content"]
                        if len(content_to_sum) > 15000:
                            content_to_sum = content_to_sum[:7500] + "\n...[Middle truncated prior to summarization]...\n" + content_to_sum[-7500:]
                            
                        if llm_client:
                            print("\n[Compacting large conversation block via AI...]")
                            summary = llm_client.summarize_content(content_to_sum, self.messages[-3:])
                            msg["content"] = f"[AI Compacted Message]:\n{summary}"
                        else:
                            msg["content"] = msg["content"][:300] + "\n...[Content compacted to save space]...\n" + msg["content"][-200:]
                            
                        msg["_compacted"] = True
                        pruned = True
                        break

            if pruned:
                continue
                
            if force:
                break # If forced, we only want to compact, not wipe the chat history!
            
            # Step 3: Drop oldest messages
            if not pruned:
                # Find the first non-system message and drop it (usually user/assistant pairs)
                # Be careful not to drop tool calls without dropping the corresponding tool response
                # A simple approach for a basic harness: drop the oldest message.
                self.messages.pop(0)

    def get_messages_for_api(self):
        # Strip out our custom metadata before sending to API
        api_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.messages:
            api_msg = {k: v for k, v in msg.items() if not k.startswith("_")}
            api_messages.append(api_msg)
        return api_messages
