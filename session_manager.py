import os
import platform
import json
import datetime
from colorama import Fore, Style

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
    # Prevent numeric names to avoid conflict with indices
    base_name = name
    if base_name.endswith(".json"):
        base_name = base_name[:-5]
    if base_name.isdigit():
        print(f"\n{Fore.RED}[Session Manager Error] Session name must not be a number.{Style.RESET_ALL}")
        return None

    # Ensure it ends with .json
    if not name.endswith(".json"):
        name += ".json"
        
    # Inject/update last accessed timestamp
    data["_last_accessed"] = datetime.datetime.now().isoformat()
        
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
            
            # Update last accessed and write back immediately to update mtime and metadata
            save_session(name, data)
            
            set_last_session(name)
            return data
        except Exception as e:
            print(f"\n[Session Manager Error] Failed to load session: {e}")
            return None
    return None

def list_sessions(limit=5):
    """Returns list of session filenames sorted by most recently accessed."""
    app_dir = get_app_dir()
    sessions = []
    for f in os.listdir(app_dir):
        if f.endswith(".json") and f != "state.json":
            path = os.path.join(app_dir, f)
            access_time = os.path.getmtime(path) # Fallback
            
            # Try to get exact time from JSON
            try:
                with open(path, "r") as jf:
                    # We only read the first few lines to be fast
                    line = jf.readline()
                    while line:
                        if '"_last_accessed":' in line:
                            # Extract ISO string
                            iso_str = line.split('"')[3]
                            access_time = datetime.datetime.fromisoformat(iso_str).timestamp()
                            break
                        line = jf.readline()
            except Exception:
                pass
                
            sessions.append((f, access_time))
    
    # Sort by time descending
    sessions.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in sessions[:limit]]

def resolve_session_name(target):
    """Resolves a target (name or 1-based index) to a full filename."""
    if not target:
        return None
        
    # Check if it's an index
    if target.isdigit():
        idx = int(target) - 1
        sessions = list_sessions(limit=100) # Get a reasonably large list
        if 0 <= idx < len(sessions):
            return sessions[idx]
        else:
            # It was a number, but out of bounds. 
            # We explicitly do NOT fallback to treating it as a filename.
            return None
            
    # Otherwise treat as name
    if not target.endswith(".json"):
        target += ".json"
    return target

def delete_session(target):
    name = resolve_session_name(target)
    if not name:
        return False
        
    file_path = os.path.join(get_app_dir(), name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            # If we deleted the last session, clear state
            if get_last_session() == name:
                os.remove(get_state_path())
            return True
        except Exception as e:
            print(f"\n[Session Manager Error] Failed to delete session: {e}")
    return False

def delete_all_sessions():
    app_dir = get_app_dir()
    deleted_count = 0
    for f in os.listdir(app_dir):
        if f.endswith(".json") and f != "state.json":
            try:
                os.remove(os.path.join(app_dir, f))
                deleted_count += 1
            except Exception:
                pass
    
    # Also clear state.json
    state_path = get_state_path()
    if os.path.exists(state_path):
        try:
            os.remove(state_path)
        except Exception:
            pass
            
    return deleted_count
