import json
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from agent import Agent
import session_manager

app = Flask(__name__)
CORS(app) # Allow React dev server to communicate with the API

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    sessions = session_manager.list_sessions(limit=50)
    return jsonify({"sessions": sessions})

@app.route("/api/session/<name>", methods=["GET"])
def get_session(name):
    resolved = session_manager.resolve_session_name(name)
    if not resolved:
        return jsonify({"error": "Session not found"}), 404
    data = session_manager.load_session(resolved)
    if not data:
        return jsonify({"error": "Failed to load session"}), 500
    return jsonify({"session_name": resolved, "state": data})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message")
    session_name = data.get("session_name")
    resume_tool_call = data.get("resume_tool_call")
    approved = data.get("approved", False)
    
    # Initialize Agent
    state_dict = None
    if session_name:
        resolved = session_manager.resolve_session_name(session_name)
        if resolved:
            state_dict = session_manager.load_session(resolved)
            session_name = resolved
    
    agent = Agent(state_dict=state_dict, session_name=session_name)
    if not agent.session_name:
        agent.session_name = session_manager.get_new_session_name()

    def generate():
        try:
            # Inform the UI of the active session name right away
            yield f"data: {json.dumps({'type': 'session_info', 'session_name': agent.session_name})}\n\n"

            if resume_tool_call:
                if not approved:
                    # Inject a fake rejection tool message and resume normally
                    agent.context.add_message(
                        role="tool",
                        content="Command execution rejected by user.",
                        tool_call_id=resume_tool_call['id'],
                        name=resume_tool_call['function']['name'],
                        ephemeral=False
                    )
                    gen = agent.run()
                else:
                    gen = agent.run(resume_tool_call=resume_tool_call, approved=True)
            elif user_input:
                gen = agent.run(user_input=user_input)
            else:
                # Empty message and no resume? Just return state.
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            for event in gen:
                yield f"data: {json.dumps(event)}\n\n"
                
            # After generation is complete, save the session state
            session_manager.save_session(agent.session_name, agent.context.export_state())
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")

def run_web(args):
    port = 5000
    if args and args[0].isdigit():
        port = int(args[0])
    print(f"Starting MyAICode Web API on port {port}...")
    # threaded=True is default in Flask, but explicitly noting it for SSE
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
