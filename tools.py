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
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Download a webpage and convert it to clean markdown. Useful for reading documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to read"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Search the local codebase for a regex pattern (similar to ripgrep). Returns file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Regex pattern to search for"},
                    "directory": {"type": "string", "description": "Directory to search in (e.g. '.')"}
                },
                "required": ["query", "directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory_tree",
            "description": "List the structure of a directory as an ASCII tree. Useful for exploring a project. Automatically ignores bulky hidden folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The directory path (e.g. '.')"},
                    "max_depth": {"type": "integer", "description": "Maximum depth to traverse (default 2)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_plan",
            "description": "Create, update, or clear your internal task checklist/plan. This plan is injected into your system prompt on every turn to help you remember your goals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action to perform: 'set', 'clear'", "enum": ["set", "clear"]},
                    "content": {"type": "string", "description": "The markdown content of the plan (required if action is 'set')"}
                },
                "required": ["action"]
            }
        }
    }
]

def get_tool_descriptions() -> str:
    descriptions = []
    for t in TOOLS:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        descriptions.append(f"- {name}: {desc}")
    return "\n".join(descriptions)

def get_tools_by_names(names: list) -> list:
    return [t for t in TOOLS if t["function"]["name"] in names]

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
    elif name == "read_url":
        return _read_url(**kwargs), True
    elif name == "search_codebase":
        return _search_codebase(**kwargs), True
    elif name == "list_directory_tree":
        return _list_directory_tree(**kwargs), True
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

def _check_syntax(path: str):
    ext = os.path.splitext(path)[1]
    if ext in config.LINT_COMMANDS:
        lint_cmd = config.LINT_COMMANDS[ext].format(path=path)
        try:
            res = subprocess.run(lint_cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                error_output = (res.stderr or res.stdout).strip()
                return f"BUT a syntax error was detected by the auto-linter:\n{error_output}\nPlease fix it."
        except Exception:
            pass
    return None

def _replace_file_content(path: str, target_string: str, new_string: str) -> str:
    try:
        is_new_file = False
        if not os.path.exists(path):
             # Let's auto-create if it doesn't exist and target_string is empty
            if target_string == "":
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_string)
                is_new_file = True
            else:
                return f"Error: File '{path}' does not exist."
        else:    
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if target_string not in content:
                return "Error: target_string not found exactly in the file. No changes made. Check whitespace and try again."
                
            new_content = content.replace(target_string, new_string, 1)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
        # Auto-Linting Check
        lint_err = _check_syntax(path)
        
        action = "created new file" if is_new_file else "replaced content in"
        if lint_err:
            return f"Successfully {action} {path}, {lint_err}"
            
        return f"Successfully {action} {path}."
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

def _read_url(url: str) -> str:
    import urllib.request
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 MyAICode/1.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.extract()
            
        markdown_text = md(str(soup), heading_style="ATX").strip()
        
        # Truncate if too long (e.g. 10000 chars)
        if len(markdown_text) > 10000:
            markdown_text = markdown_text[:10000] + "\n\n... [Content Truncated due to length]"
            
        return markdown_text
    except Exception as e:
        return f"Error reading URL: {e}"

def _search_codebase(query: str, directory: str) -> str:
    import re
    try:
        if not os.path.isdir(directory):
            return f"Error: {directory} is not a valid directory."
            
        pattern = re.compile(query)
        results = []
        
        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs like .git or node_modules
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            
            for file in files:
                if file.startswith('.'): continue
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if pattern.search(line):
                                results.append(f"{path}:{i+1}: {line.strip()}")
                                if len(results) >= 50:
                                    results.append("... [More results truncated. Refine your query.]")
                                    return "\n".join(results)
                except UnicodeDecodeError:
                    pass # Skip binary files
                    
        if not results:
            return "No matches found."
            
        return "\n".join(results)
    except Exception as e:
        return f"Error searching codebase: {e}"

def _list_directory_tree(path: str, max_depth: int = 2) -> str:
    try:
        if not os.path.exists(path):
            return f"Error: Path '{path}' does not exist."
            
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', '.idea', '.vscode'}
        
        tree = []
        base_depth = path.rstrip(os.sep).count(os.sep)
        
        for root, dirs, files in os.walk(path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            # Calculate current depth
            current_depth = root.rstrip(os.sep).count(os.sep) - base_depth
            if current_depth > max_depth:
                del dirs[:] # Stop recursing further
                continue
                
            indent = "  " * current_depth
            basename = os.path.basename(root)
            if current_depth == 0:
                tree.append(f"📁 {path}/")
            else:
                tree.append(f"{indent}📁 {basename}/")
                
            # Only show files if we haven't hit max depth
            if current_depth < max_depth:
                for f in files:
                    if f.startswith('.'): continue
                    tree.append(f"{indent}  📄 {f}")
                    
        return "\n".join(tree)
    except Exception as e:
        return f"Error listing directory: {e}"
