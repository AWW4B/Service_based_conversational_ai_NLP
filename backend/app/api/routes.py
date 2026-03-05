# =============================================================================
# app/api/routes.py
# Purpose : Production FastAPI routes with:
#           - Async REST endpoint (/chat)
#           - Streaming WebSocket (/ws/chat)
#           - Latency benchmarking endpoint
#           - Concurrent user handling (via async + thread pool in engine.py)
#           - Robust error handling throughout
#           - Session lifecycle management
# =============================================================================

import uuid
import time
import asyncio
import logging
from fastapi             import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic            import BaseModel, Field
from app.llm.engine      import llm_engine
from app.memory.context  import (
    reset_session,
    get_chat_history,
    get_session_state,
    get_session_status,
    list_active_sessions,
    get_or_create_session,
    get_welcome_message,
)
from app.memory.database import list_sessions, load_session, delete_session as db_delete_session
from app.core.config import MAX_TURNS

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class ChatRequest(BaseModel):
    session_id : str | None = Field(None,  description="Omit to auto-generate")
    message    : str        = Field(...,   description="User message text")

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
    status     : str
    turns_used : int
    turns_max  : int

class ResetRequest(BaseModel):
    session_id: str

    class Config:
        json_schema_extra = {"example": {"session_id": "abc-123"}}


# =============================================================================
# REST ENDPOINT — POST /chat
# Standard request/response. Used for Postman testing and non-streaming clients.
# Async — does NOT block event loop during inference (engine uses ThreadPool).
#
# Concurrent users: FastAPI handles each request in its own async task.
# While one user waits for inference, others can hit /health, /reset, etc.
# Inference itself is serialised (1 model instance) but I/O is concurrent.
#
# Test:
#   curl -X POST http://localhost:8000/chat \
#     -H "Content-Type: application/json" \
#     -d '{"message": "I need earbuds under 3000 PKR"}'
# =============================================================================

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message and receive a complete response.
    Session ID is auto-generated if not provided — reuse it to maintain memory.
    """
    session_id = request.session_id or str(uuid.uuid4())

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    logger.info(f"[routes] POST /chat | session={session_id}")

    # engine.generate() is async — awaiting it frees the event loop
    result = await llm_engine.generate(
        session_id   = session_id,
        user_message = request.message.strip(),
    )

    # -------------------------------------------------------------------------
    # [PARTNER TODO — Multi-Session Persistence]
    # To save conversations to disk/DB across server restarts, add here:
    #   await db.save_message(session_id, "user", request.message)
    #   await db.save_message(session_id, "assistant", result["response"])
    # The in-memory history in context.py is already updated by engine.py.
    # -------------------------------------------------------------------------

    return ChatResponse(**result)


# =============================================================================
# WEBSOCKET ENDPOINT — /ws/chat  (Assignment requirement)
# Streams tokens in real time as the model generates them.
# Enables the ChatGPT-style typewriter effect on the frontend.
#
# Message format IN:  {"session_id": "...", "message": "..."}
# Message format OUT (per token): {"token": "...", "done": false}
# Final chunk OUT:    {"token": "", "done": true, "full_response": "...",
#                      "latency_ms": 0.0, "status": "...",
#                      "turns_used": N, "turns_max": N}
#
# Test with wscat:
#   wscat -c ws://localhost:8000/ws/chat
#   > {"session_id": "test1", "message": "I need a laptop under 80000 PKR"}
#
# PARTNER NOTE:
# - Append each "token" to the chat bubble as it arrives
# - On done=true, finalise the bubble and update UI state
# - On status="ended", disable the input box
# - On "cancelled": true, show "[cancelled]" indicator
# =============================================================================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Streaming WebSocket chat endpoint."""
    await websocket.accept()
    session_id = None

    try:
        while True:
            # --- Receive ---
            try:
                data = await websocket.receive_json()
            except Exception:
                await websocket.send_json({
                    "error": "Invalid JSON. Expected: {session_id, message}"
                })
                continue

            session_id   = data.get("session_id") or str(uuid.uuid4())
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_json({"error": "message field is required."})
                continue

            logger.info(f"[routes] WS /ws/chat | session={session_id}")

            # --- Stream tokens ---
            # Each token is sent immediately as it's generated.
            # If client disconnects, WebSocketDisconnect is raised by send_json,
            # which propagates up to the outer except block for clean handling.
            try:
                async for chunk in llm_engine.stream(session_id, user_message):
                    await websocket.send_json(chunk)
                    if chunk.get("done"):
                        break

            except WebSocketDisconnect:
                # Client closed tab or pressed stop during streaming
                logger.info(f"[routes] WS disconnected mid-stream | session={session_id}")
                return

            # -----------------------------------------------------------------
            # [PARTNER TODO — Multi-Session Persistence for WebSocket]
            # Same hook as REST endpoint above. Add DB write after stream ends.
            # -----------------------------------------------------------------

    except WebSocketDisconnect:
        logger.info(f"[routes] WS disconnected | session={session_id}")

    except Exception as e:
        logger.error(f"❌ [routes] WS error | session={session_id} | {e}")
        try:
            await websocket.send_json({"error": str(e), "done": True})
        except Exception:
            pass


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================

@router.get("/session/welcome/{session_id}", tags=["Session"])
async def welcome(session_id: str):
    """
    Call when a new chat opens. Returns welcome message + session metadata.
    Partner displays this as the first chat bubble before any user input.
    """
    return get_welcome_message(session_id)


@router.post("/reset", tags=["Session"])
async def reset(request: ResetRequest):
    """Clears history and state for a session. Wired to the New Chat button."""
    reset_session(request.session_id)
    return {"message": f"Session '{request.session_id}' reset.", "status": "active"}


# =============================================================================
# SESSION HISTORY ENDPOINTS — view / load / delete previous chats
# =============================================================================

@router.get("/sessions", tags=["Session"])
async def get_all_sessions():
    """
    Returns all saved chat sessions, ordered by most recent.
    Used by the session sidebar in the frontend.
    """
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}", tags=["Session"])
async def get_session(session_id: str):
    """
    Loads a specific session with full message history.
    Used when a user clicks a previous chat to resume/view it.
    The context is fully restored so the model knows the conversation state.
    """
    # This triggers get_or_create_session which loads from DB if needed
    session = get_or_create_session(session_id)
    return {
        "session_id"    : session_id,
        "history"       : session["history"],
        "state"         : session["state"],
        "turns"         : session["turns"],
        "status"        : session["status"],
        "turns_max"     : MAX_TURNS,
    }


@router.delete("/sessions/{session_id}", tags=["Session"])
async def delete_session_endpoint(session_id: str):
    """
    Deletes a session from both memory and database.
    Used when user removes a chat from history.
    """
    from app.memory.context import active_chats
    if session_id in active_chats:
        del active_chats[session_id]
    success = db_delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": f"Session '{session_id}' deleted."}


# =============================================================================
# BENCHMARKING ENDPOINT
# Required by assignment: "Inference latency benchmarks"
# Runs N sequential inferences and returns timing statistics.
#
# Test:
#   curl -X POST "http://localhost:8000/benchmark?runs=5"
# =============================================================================

@router.post("/benchmark", tags=["Benchmarking"])
async def benchmark(runs: int = 3):
    """
    Runs N inference calls and returns latency statistics.
    Use this to measure model performance before submission.
    Results should go in README.md performance benchmarks section.
    """
    if runs < 1 or runs > 20:
        raise HTTPException(status_code=400, detail="runs must be between 1 and 20.")

    bench_session = f"benchmark-{uuid.uuid4()}"
    latencies     = []
    errors        = 0
    test_message  = "I need a budget smartphone under 20000 PKR."

    logger.info(f"[benchmark] Starting {runs} runs...")

    for i in range(runs):
        try:
            result = await llm_engine.generate(bench_session, test_message)
            latencies.append(result["latency_ms"])
            logger.info(f"[benchmark] Run {i+1}/{runs}: {result['latency_ms']:.0f}ms")
        except Exception as e:
            errors += 1
            logger.error(f"[benchmark] Run {i+1} failed: {e}")

    # Clean up benchmark session
    reset_session(bench_session)

    if not latencies:
        raise HTTPException(status_code=500, detail="All benchmark runs failed.")

    latencies.sort()
    avg = sum(latencies) / len(latencies)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else latencies[-1]

    return {
        "runs_completed" : len(latencies),
        "runs_failed"    : errors,
        "avg_ms"         : round(avg, 2),
        "min_ms"         : round(latencies[0], 2),
        "max_ms"         : round(latencies[-1], 2),
        "p50_ms"         : round(p50, 2),
        "p95_ms"         : round(p95, 2),
        "note"           : "Save these results for README.md performance benchmarks."
    }


# =============================================================================
# DEBUG / INSPECTION ENDPOINTS
# Used during development and testing — remove or protect before public deploy.
# =============================================================================

@router.get("/health", tags=["System"])
async def health():
    """Basic health check — first thing to test after server start."""
    return {
        "status"          : "ok",
        "model"           : "qwen2.5-3b-instruct-q4_k_m",
        "active_sessions" : len(list_active_sessions()),
    }


@router.post("/debug/warmup", tags=["Debug"])
async def warmup():
    """
    Warms up the model with a trivial inference.
    First call is always slow (KV cache init). Run this once after server start
    before running benchmarks or showing the system to anyone.
    """
    warm_id = f"warmup-{uuid.uuid4()}"
    result  = await llm_engine.generate(warm_id, "Hello")
    reset_session(warm_id)
    return {
        "message"    : "Warmup complete. Model is ready.",
        "latency_ms" : result["latency_ms"],
    }


@router.get("/debug/history/{session_id}", tags=["Debug"])
async def debug_history(session_id: str):
    """Returns full message history. Verify sliding window is working."""
    history = get_chat_history(session_id)
    return {
        "session_id"    : session_id,
        "message_count" : len(history),
        "history"       : history,
    }


@router.get("/debug/state/{session_id}", tags=["Debug"])
async def debug_state(session_id: str):
    """Returns extracted STATE. Verify budget/item/preferences extraction works."""
    return {
        "session_id" : session_id,
        "state"      : get_session_state(session_id),
        "status"     : get_session_status(session_id),
    }


@router.get("/debug/sessions", tags=["Debug"])
async def debug_sessions():
    """Lists all active sessions. Verify session isolation for concurrent users."""
    sessions = list_active_sessions()
    return {
        "count"      : len(sessions),
        "session_ids": sessions,
    }