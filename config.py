import os

# API Configuration
API_BASE_URL = os.environ.get("OPENAI_API_BASE", "http://172.20.16.1:8080/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-no-key-needed")
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://172.20.16.1:8888")

# Default model (can be overridden, often local servers ignore this but some need it)
MODEL_NAME = "local-model"

# Context Management Configuration
MAX_CONTEXT_TOKENS = 32768
# We leave a huge buffer for the response since the model can output up to 8k tokens at once
CONTEXT_BUFFER_TOKENS = 8000
SAFE_CONTEXT_THRESHOLD = MAX_CONTEXT_TOKENS - CONTEXT_BUFFER_TOKENS

# Output limits for tools (to avoid flooding context)
MAX_COMMAND_OUTPUT_LINES = 200
MAX_FILE_VIEW_LINES = 300

# Auto-Linting Configuration
# If the agent edits a file with these extensions, the harness will silently run this command to check for syntax errors.
# We check for the existence of cargo/npm later, but these are fallbacks for single files.
LINT_COMMANDS = {
    ".py": "python -m py_compile {path}",
    ".js": "node --check {path}",
    ".c": "gcc -fsyntax-only {path}",
    ".cpp": "g++ -fsyntax-only {path}",
    ".rs": "rustc --emit=metadata {path}"
}
