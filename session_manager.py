import os
import platform
import json
import datetime

def get_app_dir():
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
        
    app_dir = os.path.join(base, "myaicode")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

def get_state_path():
    return os.path.join(get_app_dir(), "state.json")

def get_new_session_name():
    now = datetime.datetime.now()
    return now.strftime("session_%Y_%m_%d_%H%M%S")

def get_last_session():
    state_path = get_state_path()
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
                return state.get("last_session")
        except Exception:
            pass
    return None

def set_last_session(name):
    state_path = get_state_path()
    try:
        with open(state_path, "w") as f:
            json.dump({"last_session": name}, f)
    except Exception as e:
        print(f"\n[Session Manager Error] Failed to update state.json: {e}")

def save_session(name, data):
    # Ensure it ends with .json
    if not name.endswith(".json"):
        name += ".json"
        
    file_path = os.path.join(get_app_dir(), name)
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        set_last_session(name)
        return file_path
    except Exception as e:
        print(f"\n[Session Manager Error] Failed to save session: {e}")
        return None

def load_session(name):
    if not name.endswith(".json"):
        name += ".json"
        
    file_path = os.path.join(get_app_dir(), name)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            set_last_session(name)
            return data
        except Exception as e:
            print(f"\n[Session Manager Error] Failed to load session: {e}")
            return None
    return None
