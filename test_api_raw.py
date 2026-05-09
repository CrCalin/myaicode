import os
os.environ["OPENAI_API_BASE"] = "http://localhost:8080/v1"
os.environ["OPENAI_API_KEY"] = "sk-no-key-needed"

from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="sk-no-key-needed", timeout=30.0)

prompt = """You are a tool routing assistant. The user wants to accomplish a task.
Available tools:
- view_file_lines: Read specific lines from a file.
- replace_file_content: Replace a string in a file.
- run_terminal_command: Run a shell command.
- search_web: Search the web.
- read_url: Download a webpage.
- search_codebase: Search for a pattern in code.
- list_directory_tree: List files in a directory.
- manage_plan: Manage a task plan.

Reply with ONLY a comma-separated list of the tool names that might be required. For example: replace_file_content,search_web

Chat History:
USER: test

Which tools do you need?"""

print(f"Prompt length: {len(prompt)} chars")
print("Sending via STREAM to see what model outputs...")
resp = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    stream=True,
    max_tokens=100  # Force a hard cap
)

print("Stream open, reading chunks:")
char_count = 0
for chunk in resp:
    delta = chunk.choices[0].delta if chunk.choices else None
    if delta and delta.content:
        print(repr(delta.content), end="", flush=True)
        char_count += len(delta.content)
    finish = chunk.choices[0].finish_reason if chunk.choices else None
    if finish:
        print(f"\n[Finish reason: {finish}]")

print(f"\nTotal chars: {char_count}")
