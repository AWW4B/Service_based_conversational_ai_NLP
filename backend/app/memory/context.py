from collections import defaultdict
from typing import List, Dict

# Stores conversation history per session_id
_sessions: Dict[str, List[dict]] = defaultdict(list)

MAX_HISTORY_TURNS = 10  # keep last 10 exchanges to stay within context

def get_history(session_id: str) -> List[dict]:
    return _sessions[session_id]

def add_turn(session_id: str, user_message: str, assistant_response: str):
    _sessions[session_id].append({
        "user": user_message,
        "assistant": assistant_response
    })
    # Trim to last MAX_HISTORY_TURNS to avoid context overflow
    if len(_sessions[session_id]) > MAX_HISTORY_TURNS:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY_TURNS:]

def reset_session(session_id: str):
    _sessions[session_id] = []

def list_sessions() -> List[str]:
    return list(_sessions.keys())