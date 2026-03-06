# =============================================================================
# memory/context.py
# Purpose : Session management, sliding window, STATE extraction,
#           semantic conversation-end detection.
# =============================================================================

import re
import logging
from typing import Optional
from app.core.config import (
    build_system_prompt,
    SLIDING_WINDOW_SIZE,
    MAX_TURNS,
    WELCOME_MESSAGE,
)
from app.memory.database import save_session, load_session, load_all_sessions_to_memory, init_db

logger = logging.getLogger(__name__)

# =============================================================================
# REGEX PATTERNS
# =============================================================================

_STATE_PATTERN = re.compile(r"<STATE>(.*?)</STATE>", re.DOTALL | re.IGNORECASE)
_STATE_KV_PATTERN = re.compile(
    r"(Budget|Item|Preferences|Resolved)\s*:\s*([^,<\n]+)", re.IGNORECASE
)

# =============================================================================
# IN-MEMORY SESSION STORE
#
# Structure:
# active_chats = {
#   "session_id": {
#       "history"  : [{"role": str, "content": str}, ...],
#       "state"    : {
#           "budget"     : str | None,
#           "item"       : str | None,
#           "preferences": str | None,
#           "resolved"   : str,        # "yes" | "no"
#       },
#       "turns"    : int,
#       "status"   : str,              # "active" | "closing" | "ended"
#   }
# }
#
# MULTI-SESSION NOTE:
# Each session_id is fully isolated. Concurrent users get separate entries.
# This dict is process-local — suitable for single-instance deployment.
# For multi-instance scaling, replace with Redis:
#   import redis; r = redis.Redis(); r.hset(session_id, mapping=session_data)
# =============================================================================
active_chats: dict[str, dict] = {}


def init_sessions_from_db() -> None:
    """Load all persisted sessions into memory at server startup."""
    init_db()
    loaded = load_all_sessions_to_memory()
    active_chats.update(loaded)
    logger.info(f"[context] Loaded {len(loaded)} sessions from database")


# =============================================================================
# PUBLIC SESSION API
# =============================================================================

def get_or_create_session(session_id: str) -> dict:
    """
    Returns existing session or creates a fresh one.
    Checks SQLite first if not in memory.

    Args:
        session_id (str): Unique session identifier (UUID recommended).

    Returns:
        dict: Session dict with history, state, turns, status.
    """
    if session_id not in active_chats:
        # Try loading from database first
        db_session = load_session(session_id)
        if db_session:
            active_chats[session_id] = db_session
            logger.info(f"[context] Loaded session from DB: {session_id}")
            return active_chats[session_id]

        active_chats[session_id] = {
            "history": [],
            "state": {
                "budget"     : None,
                "item"       : None,
                "preferences": None,
                "resolved"   : "no",
            },
            "turns" : 0,
            "status": "active",
        }
        logger.info(f"[context] New session: {session_id}")
    return active_chats[session_id]


def add_message_to_chat(session_id: str, role: str, text: str) -> None:
    """
    Appends a message to session history and persists to SQLite.
    Always call with clean text — STATE tag must be stripped before calling.

    Args:
        session_id (str): Target session.
        role       (str): "user" or "assistant".
        text       (str): Clean message content.
    """
    session = get_or_create_session(session_id)
    session["history"].append({"role": role, "content": text})
    _persist(session_id)


def get_chat_history(session_id: str) -> list:
    """Returns full raw message history for a session."""
    return get_or_create_session(session_id)["history"]


def get_session_state(session_id: str) -> dict:
    """Returns extracted state dict {budget, item, preferences, resolved}."""
    return get_or_create_session(session_id)["state"]


def get_session_status(session_id: str) -> str:
    """Returns 'active', 'closing', or 'ended'."""
    return get_or_create_session(session_id)["status"]


def set_session_status(session_id: str, status: str) -> None:
    """Updates session lifecycle status."""
    get_or_create_session(session_id)["status"] = status
    _persist(session_id)


def increment_turn(session_id: str) -> None:
    """Increments completed turn counter after each exchange."""
    get_or_create_session(session_id)["turns"] += 1
    _persist(session_id)


def is_session_maxed(session_id: str) -> bool:
    """Returns True if session has hit MAX_TURNS limit."""
    return get_or_create_session(session_id)["turns"] >= MAX_TURNS


def reset_session(session_id: str) -> None:
    """
    Wipes history and state for a session.
    Called by /reset endpoint (New Chat button).
    Old session is preserved in DB; new session gets a fresh ID.
    """
    # Persist final state of old session before removing from memory
    if session_id in active_chats:
        _persist(session_id)
        del active_chats[session_id]

    logger.info(f"[context] Session reset: {session_id}")


def list_active_sessions() -> list:
    """Returns all active session IDs. Used by debug endpoint."""
    return list(active_chats.keys())


def get_welcome_message(session_id: str) -> dict:
    """
    Returns welcome message payload for new sessions.
    Called by GET /session/welcome/{session_id} when chat opens.
    """
    get_or_create_session(session_id)
    return {
        "session_id" : session_id,
        "response"   : WELCOME_MESSAGE,
        "latency_ms" : 0.0,
        "status"     : "active",
        "turns_used" : 0,
        "turns_max"  : MAX_TURNS,
    }


# =============================================================================
# CONTEXT WINDOW BUILDER
# Signal filtering: only last SLIDING_WINDOW_SIZE messages are kept.
# Critical facts (budget, item) are preserved via STATE injection into
# the system prompt — they never fall out of context.
# =============================================================================

def build_inference_payload(session_id: str, new_user_message: str) -> list:
    """
    Assembles optimised prompt payload for llama-cpp-python.

    Args:
        session_id       (str): Active session ID.
        new_user_message (str): Latest user input.

    Returns:
        list: Ready-to-format message list for build_chatml_prompt().
    """
    session = get_or_create_session(session_id)

    system_msg = {
        "role"   : "system",
        "content": build_system_prompt(session["state"]),
    }

    # Sliding window — drop old noise, keep recent signal
    trimmed = session["history"][-SLIDING_WINDOW_SIZE:]

    payload = [system_msg] + trimmed + [{"role": "user", "content": new_user_message}]

    logger.debug(
        f"[context] [{session_id}] Payload: "
        f"1 system + {len(trimmed)} history + 1 user = {len(payload)} messages"
    )
    return payload


# =============================================================================
# STATE EXTRACTION
# =============================================================================

def extract_and_strip_state(session_id: str, raw_response: str) -> str:
    session = get_or_create_session(session_id)

    # TEMPORARY DEBUG — remove after fixing
    logger.info(f"[context] RAW RESPONSE: {repr(raw_response)}")

    match = _STATE_PATTERN.search(raw_response)
    if match:
        _update_state_from_block(session["state"], match.group(1))
        logger.debug(f"[context] [{session_id}] State: {session['state']}")
    else:
        logger.warning(f"[context] [{session_id}] NO STATE TAG FOUND in response")

    clean = _STATE_PATTERN.sub("", raw_response).strip()
    clean = re.sub(r"Resolved\s*:\s*(yes|no)", "", clean, flags=re.IGNORECASE).strip()
    return clean

    
def is_conversation_resolved(session_id: str) -> bool:
    """
    Semantic end-of-conversation detection via STATE tag.
    Model sets Resolved: yes only when request is fully satisfied AND
    it has asked the closing question. "no" answers to mid-conversation
    questions will NOT trigger this — the model controls it via context.

    Returns:
        bool: True only if model flagged Resolved: yes.
    """
    state = get_or_create_session(session_id)["state"]
    return state.get("resolved", "no").lower().strip() == "yes"


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _update_state_from_block(state: dict, state_block: str) -> None:
    """
    Parses key:value pairs from STATE block and updates session state.
    Skips placeholder values (Unknown, None, N/A).
    """
    for match in _STATE_KV_PATTERN.finditer(state_block):
        key   = match.group(1).strip().lower()
        value = match.group(2).strip()

        if value.lower() in ("unknown", "none", "n/a", ""):
            continue

        state[key] = value


def _persist(session_id: str) -> None:
    """Saves session to SQLite. Called after any mutation."""
    if session_id in active_chats:
        try:
            save_session(session_id, active_chats[session_id])
        except Exception as e:
            logger.error(f"[context] Persistence error for {session_id}: {e}")