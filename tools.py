import os
import subprocess
import config

# Define tool schemas for the OpenAI API
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "view_file_lines",
            "description": "Read specific lines from a file. Always use this instead of cat. Limits output to a reasonable number of lines to save context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to the file"},
                    "start_line": {"type": "integer", "description": "1-indexed start line"},
                    "end_line": {"type": "integer", "description": "1-indexed end line"}
                },
                "required": ["path", "start_line", "end_line"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_file_content",
            "description": "Replace a specific string block in a file with a new string. Use this to edit files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit"},
                    "target_string": {"type": "string", "description": "Exact text block to replace. Must match exactly, including whitespace."},
                    "new_string": {"type": "string", "description": "The new text to insert in place of the target_string."}
                },
                "required": ["path", "target_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Run a bash/powershell command in the terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information using SearXNG. Returns concise snippets of the top results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    }
]

class RequiresApproval(Exception):
    def __init__(self, command: str):
        self.command = command
        super().__init__(f"Command requires manual approval: {command}")

def execute_tool(name: str, kwargs: dict) -> tuple[str, bool]:
    """
    Executes a tool and returns (output_string, is_ephemeral).
    Raises RequiresApproval if the tool requires manual intervention.
    """
    if name == "view_file_lines":
        return _view_file_lines(**kwargs), True
    elif name == "replace_file_content":
        return _replace_file_content(**kwargs), False
    elif name == "run_terminal_command":
        return _run_terminal_command(**kwargs), True
    elif name == "search_web":
        return _search_web(**kwargs), True
    else:
        return f"Error: Unknown tool {name}", False

def _view_file_lines(path: str, start_line: int, end_line: int) -> str:
    try:
        if not os.path.exists(path):
            return f"Error: File '{path}' does not exist."
        if end_line - start_line > config.MAX_FILE_VIEW_LINES:
            end_line = start_line + config.MAX_FILE_VIEW_LINES
            trunc_msg = f"\n[Warning: Requested too many lines. Truncated to {config.MAX_FILE_VIEW_LINES} lines.]"
        else:
            trunc_msg = ""
            
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        output_lines = []
        for i in range(start_idx, end_idx):
            output_lines.append(f"{i+1}| {lines[i]}")
            
        return "".join(output_lines) + trunc_msg
    except Exception as e:
        return f"Error reading file: {e}"

def _replace_file_content(path: str, target_string: str, new_string: str) -> str:
    try:
        if not os.path.exists(path):
             # Let's auto-create if it doesn't exist and target_string is empty
            if target_string == "":
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_string)
                return f"Successfully created new file {path}."
            return f"Error: File '{path}' does not exist."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if target_string not in content:
            return "Error: target_string not found exactly in the file. No changes made. Check whitespace and try again."
            
        new_content = content.replace(target_string, new_string, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return f"Successfully replaced content in {path}."
    except Exception as e:
        return f"Error editing file: {e}"

def _run_terminal_command(command: str, approved: bool = False) -> str:
    # Safety Check
    safe_prefixes = ["git", "ls", "cat", "echo", "pwd", "cd", "dir"]
    is_safe = any(command.strip().startswith(prefix) for prefix in safe_prefixes)
    
    if not is_safe and not approved:
        # Instead of asking here, we raise an exception to pause the agent and bubble up to the UI
        raise RequiresApproval(command)
            
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
            
        if not output.strip():
            output = "Command executed successfully (no output)."
            
        # Truncate output if it's too long
        lines = output.split('\n')
        if len(lines) > config.MAX_COMMAND_OUTPUT_LINES:
            output = '\n'.join(lines[:config.MAX_COMMAND_OUTPUT_LINES]) + f"\n... [{len(lines)-config.MAX_COMMAND_OUTPUT_LINES} lines truncated]"
            
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error running command: {e}"

def _search_web(query: str) -> str:
    import urllib.request
    import urllib.parse
    import json
    
    try:
        url = f"{config.SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 MyAICode/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        results = data.get('results', [])
        if not results:
            return "No results found."
            
        output = [f"Search Results for '{query}':\n"]
        for i, res in enumerate(results[:7]):
            title = res.get('title', 'No Title')
            link = res.get('url', 'No URL')
            snippet = res.get('content', '') or res.get('snippet', '')
            output.append(f"{i+1}. {title}\n   URL: {link}\n   Snippet: {snippet[:200]}...\n")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error performing web search: {e}"
