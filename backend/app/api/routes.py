from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.llm.engine import llm_engine
from app.memory.context import get_history, add_turn, reset_session
from app.core.config import build_prompt
import time
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# --- REST endpoint (for testing) ---
@router.post("/chat")
async def chat(payload: dict):
    session_id = payload.get("session_id", "default")
    user_message = payload.get("message", "")

    if not user_message:
        return {"error": "message field is required"}

    history = get_history(session_id)
    prompt = build_prompt(history, user_message)

    start = time.perf_counter()
    response = llm_engine.generate(prompt)
    latency_ms = (time.perf_counter() - start) * 1000

    add_turn(session_id, user_message, response)
    logger.info(f"Session={session_id} | Latency={latency_ms:.2f}ms")

    return {
        "session_id": session_id,
        "response": response,
        "latency_ms": round(latency_ms, 2)
    }

# --- WebSocket endpoint (required by assignment) ---
@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    try:
        while True:
            data = await websocket.receive_json()
            session_id = data.get("session_id", "default")
            user_message = data.get("message", "")

            if not user_message:
                await websocket.send_json({"error": "message is required"})
                continue

            history = get_history(session_id)
            prompt = build_prompt(history, user_message)

            start = time.perf_counter()
            response = llm_engine.generate(prompt)
            latency_ms = (time.perf_counter() - start) * 1000

            add_turn(session_id, user_message, response)
            logger.info(f"WS Session={session_id} | Latency={latency_ms:.2f}ms")

            await websocket.send_json({
                "session_id": session_id,
                "response": response,
                "latency_ms": round(latency_ms, 2)
            })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: session={session_id}")

# --- Session reset ---
@router.post("/reset")
async def reset(payload: dict):
    session_id = payload.get("session_id", "default")
    reset_session(session_id)
    return {"message": f"Session {session_id} cleared"}