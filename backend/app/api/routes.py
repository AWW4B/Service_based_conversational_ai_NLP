# =============================================================================
# app/api/routes.py
# Purpose : REST and WebSocket endpoints for the Daraz Shopping Assistant.
#           Designed so you can test the ENTIRE backend via:
#             - Swagger UI at http://localhost:8000/docs  (REST)
#             - wscat / Postman WebSocket (WS)
#           without touching the frontend at all.
#
# Partner note: routes.py is the ONLY file that touches the LLM and memory.
#               Import llm_engine and memory helpers — nothing else.
# =============================================================================

import uuid
import logging
from fastapi             import APIRouter, WebSocket, WebSocketDisconnect
from pydantic            import BaseModel
from app.llm.engine      import llm_engine
from app.memory.context  import (
    reset_session,
    get_chat_history,
    get_session_state,
    list_active_sessions,
    get_or_create_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()

from app.memory.context import get_welcome_message

# =============================================================================
# REQUEST / RESPONSE SCHEMAS
# Pydantic models give you automatic validation + Swagger UI docs for free.
# =============================================================================

class ChatRequest(BaseModel):
    session_id : str | None = None   # Optional: auto-generated if not provided
    message    : str                 # The user's message text

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc-123",
                "message"   : "I need a phone under 30000 PKR"
            }
        }

class ChatResponse(BaseModel):
    session_id : str
    response   : str
    latency_ms : float

class ResetRequest(BaseModel):
    session_id: str

    class Config:
        json_schema_extra = {"example": {"session_id": "abc-123"}}


# =============================================================================
# REST ENDPOINT — /chat  (POST)
# Primary endpoint for testing. Hit this from Swagger UI or curl/Postman.
# No WebSocket client needed — plain HTTP request/response.
#
# Test with curl:
#   curl -X POST http://localhost:8000/chat \
#     -H "Content-Type: application/json" \
#     -d '{"message": "I need earbuds under 3000 PKR"}'
# =============================================================================

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to the Daraz assistant and get a response.

    - If session_id is omitted, a new one is auto-generated and returned.
    - Reuse the same session_id across requests to maintain conversation memory.
    - Check latency_ms in the response to benchmark your model speed.
    """
    # Auto-generate a session ID if the client didn't send one
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(f"[routes] POST /chat | session={session_id} | msg='{request.message[:50]}'")

    # --- Hand off to LLM engine ---
    # engine.py handles: prompt building → inference → state extraction → history saving
    result = llm_engine.generate(
        session_id   = session_id,
        user_message = request.message,
    )

    # -------------------------------------------------------------------------
    # [PARTNER TODO — Multi-Chat Persistence Hook]
    # To save conversations across sessions to disk or DB, add a call here.
    # Example:
    #   await save_chat_to_db(session_id, request.message, result["response"])
    # Or append to a JSON file:
    #   await append_to_chat_log(session_id, request.message, result["response"])
    # The in-memory history in context.py is already updated by engine.py.
    # This hook is ONLY for persistent cross-restart storage.
    # -------------------------------------------------------------------------

    return ChatResponse(
        session_id = result["session_id"],
        response   = result["response"],
        latency_ms = result["latency_ms"],
    )


# =============================================================================
# WEBSOCKET ENDPOINT — /ws/chat  (Required by assignment)
# Real-time bidirectional channel used by the frontend.
# Test this with wscat (install: npm install -g wscat):
#   wscat -c ws://localhost:8000/ws/chat
#   Then send: {"session_id": "abc-123", "message": "Hello"}
# Or use Postman → New → WebSocket Request → ws://localhost:8000/ws/chat
# =============================================================================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming chat.
    Accepts JSON: {"session_id": "...", "message": "..."}
    Returns JSON: {"session_id": "...", "response": "...", "latency_ms": 0.0}
    """
    await websocket.accept()
    session_id = None

    try:
        while True:
            # --- Receive message from client ---
            try:
                data = await websocket.receive_json()
            except Exception:
                await websocket.send_json({"error": "Invalid JSON. Send {session_id, message}."})
                continue

            session_id   = data.get("session_id") or str(uuid.uuid4())
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_json({"error": "message field is required."})
                continue

            logger.info(f"[routes] WS /ws/chat | session={session_id} | msg='{user_message[:50]}'")

            # --- Inference ---
            result = llm_engine.generate(
                session_id   = session_id,
                user_message = user_message,
            )

            # -----------------------------------------------------------------
            # [PARTNER TODO — Multi-Chat Persistence Hook for WebSocket]
            # Same as the REST hook above. Add DB/file write call here.
            # -----------------------------------------------------------------

            await websocket.send_json({
                "session_id" : result["session_id"],
                "response"   : result["response"],
                "latency_ms" : result["latency_ms"],
            })

    except WebSocketDisconnect:
        logger.info(f"[routes] WebSocket disconnected | session={session_id}")


# =============================================================================
# RESET ENDPOINT — /reset  (POST)
# Clears history and state for a session. Wired to the "New Chat" button.
#
# Test:
#   curl -X POST http://localhost:8000/reset \
#     -H "Content-Type: application/json" \
#     -d '{"session_id": "abc-123"}'
# =============================================================================

@router.post("/reset", tags=["Session"])
async def reset(request: ResetRequest):
    """Clears the conversation history and extracted state for a session."""
    reset_session(request.session_id)

    # -------------------------------------------------------------------------
    # [PARTNER TODO — Multi-Chat Persistence Hook]
    # If saving chats to disk/DB, archive the session here before wiping it.
    # Example: await archive_session(request.session_id)
    # -------------------------------------------------------------------------

    return {"message": f"Session '{request.session_id}' has been reset."}


# =============================================================================
# DEBUG / INSPECTION ENDPOINTS
# These are purely for YOU to test and verify backend state during development.
# Remove or protect these before any public deployment.
# =============================================================================

@router.get("/debug/history/{session_id}", tags=["Debug"])
async def debug_history(session_id: str):
    """
    Returns the full raw message history for a session.
    Use this to verify the sliding window is working correctly.
    """
    history = get_chat_history(session_id)
    return {
        "session_id"    : session_id,
        "message_count" : len(history),
        "history"       : history,
    }


@router.get("/debug/state/{session_id}", tags=["Debug"])
async def debug_state(session_id: str):
    """
    Returns the extracted state (budget, item, preferences) for a session.
    Use this to verify the <STATE> tag extraction is working correctly.
    """
    state = get_session_state(session_id)
    return {
        "session_id" : session_id,
        "state"      : state,
    }


@router.get("/debug/sessions", tags=["Debug"])
async def debug_sessions():
    """
    Lists all currently active session IDs in memory.
    Use this to verify session creation and isolation.
    """
    sessions = list_active_sessions()
    return {
        "active_session_count" : len(sessions),
        "session_ids"          : sessions,
    }


@router.post("/debug/warmup", tags=["Debug"])
async def warmup():
    """
    Sends a trivial message to the model to warm up inference.
    First inference is always slower due to KV cache initialisation.
    Call this once after server start before running latency benchmarks.
    """
    warm_session = "warmup-session"
    result = llm_engine.generate(
        session_id   = warm_session,
        user_message = "Hello",
    )
    # Reset immediately so warmup doesn't pollute history
    reset_session(warm_session)

    return {
        "message"    : "Warmup complete. Model is ready.",
        "latency_ms" : result["latency_ms"],
    }

    
@router.get("/session/welcome/{session_id}", tags=["Session"])
async def welcome(session_id: str):
    """
    Call this when a new chat is opened.
    Returns the welcome message + session metadata.
    Partner displays this as the first chat bubble.
    """
    return get_welcome_message(session_id)
