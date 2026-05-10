> [!WARNING]
> **DISCLAIMER:** This project is entirely **vibe-coded**. 

# MyAICode - Local AI Coding Assistant

MyAICode is a terminal-based AI coding assistant designed to interface with local or remote OpenAI-compatible LLMs. It features advanced context management, real-time token tracking, robust session handling, and autonomous tool execution for file editing, code navigation, and terminal command execution.

## Key Features

- **Autonomous Tool Execution**: The agent can autonomously run terminal commands, view and edit files, and search the web or local codebase to fulfill complex user requests.
- **Smart Context Management**: Uses `tiktoken` to accurately track context size. When the context approaches its limit, the agent intelligently prunes or AI-summarizes older messages to prevent context exhaustion while maintaining essential history.
- **Real-Time Streaming & Metrics**: Streams responses to the terminal in real-time, accompanied by live token generation counts, elapsed time, and Tokens-Per-Second (TPS) throughput metrics.
- **Advanced Session Management**: Chat sessions are auto-saved and can be retrieved using recency-based indices or specific names. Easily resume where you left off.
- **Safety First**: Destructive commands or significant file modifications pause execution to request explicit user approval.

## Architecture Overview

The codebase is modularized to separate API communication, agent reasoning, UI, and session state:

- **`main.py`**: The entry point. Handles the command-line interface, user input loops, and parses agent events (content, metrics, tool usage) for colorized terminal output.
- **`agent.py`**: The core reasoning loop. Orchestrates turns between the user, the LLM, and the tool execution engine. It aggregates context and handles the live streaming event generator.
- **`llm_client.py`**: Manages communication with OpenAI-compatible endpoints. It handles tool routing logic, content summarization requests, and accurate client-side token counting (`cl100k_base`).
- **`context_manager.py`**: The memory engine. Tracks token overhead and aggressively prunes or compacts the chat history (starting with the oldest/largest messages) when the `SAFE_CONTEXT_THRESHOLD` is approached.
- **`session_manager.py`**: Handles local file persistence of conversation states, implementing a robust recency-indexed retrieval system.
- **`tools.py`**: Defines the schemas and execution logic for the agent's capabilities (e.g., `replace_file_content`, `run_command`, `search_web`).
- **`config.py`**: Central configuration for API endpoints, keys, model names, and context buffer limits.

## Getting Started

### Prerequisites

Ensure you have Python installed along with the required dependencies:
```bash
pip install -r requirements.txt
```
*(Dependencies generally include `openai`, `tiktoken`, `colorama`, and `beautifulsoup4`)*

### Configuration

Edit `config.py` or set the necessary environment variables to point to your LLM provider (local e.g., LM Studio, Ollama, or remote e.g., OpenAI, OpenRouter):
- `OPENAI_API_BASE`
- `OPENAI_API_KEY`
- `MODEL_NAME`

## Usage

Start a new session or auto-resume your most recent one:
```bash
python main.py
```

Start a explicitly fresh session:
```bash
python main.py new
```

### In-App Commands

While in the chat interface, you can use the following commands:
- `/new` - Start a fresh session (autosaves the current one).
- `/sessions [n]` - List the `n` most recent sessions.
- `/load <name|idx>` - Load a previous session by its name or index number.
- `/save [name]` - Save the current session with a specific name (numeric names are disallowed).
- `/compact` - Force the context manager to immediately prune/summarize the context to save space.
- `/help` - Display the help menu.
- `/exit` - Safely autosave and exit the application.

### CLI Management

You can also manage sessions directly from the command line:
```bash
# List all recent sessions
python main.py sessions

# Load the 2nd most recent session
python main.py session 2

# Delete a specific session
python main.py sessions delete <name|idx>

# Delete all sessions
python main.py sessions deleteall
```
