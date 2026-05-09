import os

# API Configuration
API_BASE_URL = os.environ.get("OPENAI_API_BASE", "http://172.20.16.1:8080/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-no-key-needed")

# Default model (can be overridden, often local servers ignore this but some need it)
MODEL_NAME = "local-model"

# Context Management Configuration
MAX_CONTEXT_TOKENS = 32768
# We leave a buffer for the response and for tokenizer inaccuracies
CONTEXT_BUFFER_TOKENS = 2000
SAFE_CONTEXT_THRESHOLD = MAX_CONTEXT_TOKENS - CONTEXT_BUFFER_TOKENS

# Output limits for tools (to avoid flooding context)
MAX_COMMAND_OUTPUT_LINES = 200
MAX_FILE_VIEW_LINES = 300
