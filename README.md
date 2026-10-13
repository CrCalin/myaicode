# Why?
I built this project because existing ones don't handle small context windows gracefully, and i can't run more than 65k context window on a competent model on my pc. Thought it would be fun to throw AI at the problem.

**2026 UPDATE:** In the mean time, the local AI landscape has shifted a lot. I have access to much nicer models with bigger context windows, and [pi](https://github.com/earendil-works/pi) exists, and solves any and all problems this project attempted to solve. I will leave it up for reference, but **archived**. 

The following is the AI's description of the project:

> [!WARNING]
> **DISCLAIMER:** This project is entirely **vibe-coded**. 

# MyAICode - Local AI Coding Assistant

MyAICode is a versatile AI coding assistant designed to interface with local or remote OpenAI-compatible LLMs. It features a dual-interface system (Terminal & Web), advanced context management, real-time token tracking, and autonomous tool execution.

## Key Features

- **Modern Web UI**: A sleek, React-based web interface inspired by ChatGPT, featuring streaming responses, tool call visualizations, and persistent session management.
- **Terminal UI (TUI)**: A robust, colorized terminal interface for those who prefer the command line.
- **Autonomous Tool Execution**: The agent can autonomously run terminal commands, view and edit files, and search the web or local codebase.
- **Smart Context Management**: Uses `tiktoken` to accurately track context size and intelligently prunes or AI-summarizes history to stay within context limits.
- **Real-Time Metrics**: Live tracking of token generation, elapsed time, and throughput (TPS) during response generation.
- **Safety First**: Potentially destructive commands or significant file edits require explicit user approval.

## Architecture Overview

The codebase is split into a Python backend and a React frontend:

- **`main.py`**: The entry point router. Directs to either the Terminal UI or the Web API.
- **`tui.py`**: Contains all logic for the interactive terminal experience.
- **`web.py`**: A Flask-based API server that streams agent events to the frontend via Server-Sent Events (SSE).
- **`agent.py`**: The core reasoning engine orchestrating turns between the LLM and tools.
- **`frontend/`**: A modern React application (Vite + CSS) providing the premium web experience.
- **`llm_client.py`**: Handles API communication, tool routing, and token counting.
- **`context_manager.py`**: Manages the conversation history and context pruning logic.
- **`session_manager.py`**: Handles persistent storage of chat sessions.
- **`tools.py`**: Core tool definitions and execution logic.

## Getting Started

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
# Requires: flask, flask-cors, openai, tiktoken, colorama, beautifulsoup4
```

2. Configure `config.py` with your LLM provider details (API Key, Base URL, Model Name).

### Frontend Setup (for Web UI)

1. Ensure you have Node.js installed.
2. Install dependencies:
```bash
cd frontend
npm install
```

## Usage

### Option 1: Terminal Interface (TUI)

Run the standard terminal-based chat:
```bash
python main.py tui
# Or simply 'python main.py' as it defaults to TUI
```

### Option 2: Web Interface

1. Start the backend API:
```bash
python main.py web
```

2. Start the frontend development server:
```bash
cd frontend
npm run dev
```
3. Open `http://localhost:5173` in your browser.

---

### CLI Session Management

Manage your history directly from the command line:
```bash
# List all recent sessions
python main.py tui sessions

# Load a specific session
python main.py tui session 2

# Delete sessions
python main.py tui sessions delete <idx>
```
