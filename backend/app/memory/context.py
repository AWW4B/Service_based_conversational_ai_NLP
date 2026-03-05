# =============================================================================
# memory/context.py
# Purpose : In-memory session management, sliding window context trimming,
#           and silent <STATE> tag extraction from LLM responses.
# Domain  : Daraz.pk shopping assistant — CPU-optimised, no database.
# =============================================================================

import re
import logging
from typing import Optional
from app.core.config import build_system_prompt

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Maximum number of conversation TURNS (user + assistant = 1 turn) to keep
# in the sliding window. Keeping this at 6 messages (3 turns) prevents context
# overflow on a 4096-token context window on a 4-core i5.
SLIDING_WINDOW_MESSAGES = 6

# Regex to extract the hidden <STATE>...</STATE> block the LLM appends.
# re.DOTALL lets . match newlines in case the model wraps the tag.
_STATE_PATTERN = re.compile(r"<STATE>(.*?)</STATE>", re.DOTALL | re.IGNORECASE)

# Regex to parse individual key:value pairs inside the STATE block.
_STATE_KV_PATTERN = re.compile(r"(Budget|Item|Preferences)\s*:\s*([^,<\n]+)", re.IGNORECASE)


# =============================================================================
# IN-MEMORY SESSION STORE
# Structure:
#   active_chats = {
#       "session_id": {
#           "history" : [{"role": "user"|"assistant", "content": str}, ...],
#           "state"   : {"budget": str|None, "item": str|None, "preferences": str|None}
#       }
#   }
# This lives purely in process memory — no disk, no database.
# =============================================================================
active_chats: dict[str, dict] = {}


# =============================================================================
# PUBLIC API  (functions your partner's routes.py will call)
# =============================================================================

def get_or_create_session(session_id: str) -> dict:
    """
    Returns the session dict for session_id, creating it if it does not exist.
    Your partner should call this once at the start of every WebSocket connection.

    Args:
        session_id (str): Unique identifier for the chat session (e.g. UUID).

    Returns:
        dict: The session dict with keys 'history' and 'state'.
    """
    if session_id not in active_chats:
        active_chats[session_id] = {
            "history": [],   # list of {role, content} dicts
            "state"  : {     # extracted user constraints
                "budget"     : None,
                "item"       : None,
                "preferences": None,
            }
        }
        logger.info(f"[context] New session created: {session_id}")

    return active_chats[session_id]


def add_message_to_chat(session_id: str, role: str, text: str) -> None:
    """
    Appends a single message to the session's raw history.
    Call this AFTER stripping the <STATE> tag from assistant messages.

    Args:
        session_id (str): The session to update.
        role       (str): "user" or "assistant".
        text       (str): The message content (clean, no <STATE> tag).
    """
    session = get_or_create_session(session_id)
    session["history"].append({"role": role, "content": text})
    logger.debug(f"[context] [{session_id}] +{role}: {text[:60]}...")


def get_chat_history(session_id: str) -> list:
    """
    Returns the raw message history for a session.
    Useful for your partner to send conversation history to the frontend.

    Args:
        session_id (str): The session to query.

    Returns:
        list: List of {"role": str, "content": str} dicts.
    """
    session = get_or_create_session(session_id)
    return session["history"]


def get_session_state(session_id: str) -> dict:
    """
    Returns the currently extracted state dict for a session.

    Args:
        session_id (str): The session to query.

    Returns:
        dict: {"budget": ..., "item": ..., "preferences": ...}
    """
    session = get_or_create_session(session_id)
    return session["state"]


def reset_session(session_id: str) -> None:
    """
    Wipes history and state for a session (used by the 'New Chat' button).
    Your partner will call this from the /reset endpoint.

    Args:
        session_id (str): The session to clear.
    """
    active_chats[session_id] = {
        "history": [],
        "state"  : {"budget": None, "item": None, "preferences": None}
    }
    logger.info(f"[context] Session reset: {session_id}")


def list_active_sessions() -> list:
    """Returns all currently active session IDs. Useful for debugging."""
    return list(active_chats.keys())


# =============================================================================
# INTERNAL LOGIC  (used by engine.py, not directly by routes.py)
# =============================================================================

def extract_and_strip_state(session_id: str, raw_response: str) -> str:
    """
    Intercepts the raw LLM output before it reaches the user.

    1. Finds the hidden <STATE>...</STATE> block the LLM appended.
    2. Parses Budget / Item / Preferences from it.
    3. Updates the session state dict with any newly extracted values.
    4. Strips the <STATE> tag from the text so the user never sees it.

    Args:
        session_id   (str): The active session.
        raw_response (str): The raw text returned by llama-cpp-python.

    Returns:
        str: Clean response text with <STATE> block removed.
    """
    session = get_or_create_session(session_id)
    match   = _STATE_PATTERN.search(raw_response)

    if match:
        state_block = match.group(1)  # text inside <STATE>...</STATE>
        _update_state_from_block(session["state"], state_block)
        logger.debug(f"[context] [{session_id}] State updated: {session['state']}")

    # Remove the entire <STATE>...</STATE> tag (including surrounding whitespace)
    clean_response = _STATE_PATTERN.sub("", raw_response).strip()
    return clean_response


def build_inference_payload(session_id: str, new_user_message: str) -> list:
    """
    Assembles the sliding-window message list to send to the LLM.

    Steps:
    1. Injects the state-aware system prompt at index 0.
    2. Takes the last SLIDING_WINDOW_MESSAGES messages from history.
    3. Appends the new user message at the end.

    This is the ONLY function engine.py needs to call before inference.

    Args:
        session_id       (str): The active session.
        new_user_message (str): The latest message typed by the user.

    Returns:
        list: Ready-to-use message list for build_chatml_prompt() in config.py.
    """
    session = get_or_create_session(session_id)

    # --- 1. Build state-injected system prompt ---
    system_prompt = build_system_prompt(session["state"])
    system_message = {"role": "system", "content": system_prompt}

    # --- 2. Apply sliding window to history ---
    # We trim BEFORE adding the new user message so the window is always
    # the last N *stored* messages + the incoming one.
    trimmed_history = session["history"][-SLIDING_WINDOW_MESSAGES:]

    # --- 3. Append current user message ---
    current_user_msg = {"role": "user", "content": new_user_message}

    # --- 4. Assemble final payload ---
    payload = [system_message] + trimmed_history + [current_user_msg]

    logger.debug(
        f"[context] [{session_id}] Inference payload: "
        f"1 system + {len(trimmed_history)} history + 1 user = {len(payload)} messages"
    )
    return payload


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _update_state_from_block(state: dict, state_block: str) -> None:
    """
    Parses key:value pairs from inside a <STATE> block and updates
    the session state dict in-place. Only overwrites a field if the
    newly extracted value is meaningful (not 'Unknown' or 'None').

    Args:
        state       (dict): The session's existing state dict (mutated).
        state_block (str) : Raw text content inside <STATE>...</STATE>.
    """
    for kv_match in _STATE_KV_PATTERN.finditer(state_block):
        key   = kv_match.group(1).strip().lower()        # budget / item / preferences
        value = kv_match.group(2).strip()

        # Skip placeholder values the LLM writes when it doesn't know yet
        if value.lower() in ("unknown", "none", "n/a", ""):
            continue

        state[key] = value