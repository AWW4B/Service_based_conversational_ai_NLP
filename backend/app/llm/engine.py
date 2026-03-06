# =============================================================================
# llm/engine.py
# Purpose: Single-pass, high-speed streaming LLM engine.
# =============================================================================

import os
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional
from llama_cpp import Llama

from app.core.config import (
    build_chatml_prompt, MAX_TURNS, MAX_TOKENS, N_CTX, N_THREADS,
    N_BATCH, TEMPERATURE, TOP_P, REPEAT_PENALTY,
)
from app.memory.context import (
    build_inference_payload, add_message_to_chat, extract_and_strip_state,
    increment_turn, is_session_maxed, get_session_status, set_session_status,
    is_conversation_resolved, get_or_create_session,
)

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1)

class LLMEngine:
    def __init__(self):
        self.model: Optional[Llama] = None
        self._load_model()

    def _load_model(self) -> None:
        model_path = os.getenv(
            "MODEL_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "qwen2.5-3b-instruct-q4_k_m.gguf")
        )
        model_path = os.path.abspath(model_path)
        logger.info(f"[engine] Loading model: {model_path}")
        try:
            self.model = Llama(
                model_path=model_path, n_ctx=N_CTX, n_threads=N_THREADS,
                n_batch=N_BATCH, n_gpu_layers=0, verbose=False,
            )
            logger.info("✅ [engine] Model loaded.")
        except Exception as e:
            logger.error(f"❌ [engine] Load failed: {e}")
            self.model = None

    def _check_lifecycle_guards(self, session_id: str, user_message: str) -> Optional[dict]:
        session = get_or_create_session(session_id)
        if self.model is None:
            return self._make_response(session_id, session, "I'm temporarily unavailable. Please try again later.")
        if get_session_status(session_id) == "ended":
            return self._make_response(session_id, session, "This session has ended. Please start a new chat.", status="ended")
        if is_session_maxed(session_id):
            set_session_status(session_id, "ended")
            farewell = "We've reached the end of our session. Thank you for shopping with Daraz Assistant!"
            add_message_to_chat(session_id, "user", user_message)
            add_message_to_chat(session_id, "assistant", farewell)
            return self._make_response(session_id, session, farewell, status="ended")
        return None

    async def stream(self, session_id: str, user_message: str) -> AsyncGenerator[dict, None]:
        guard = self._check_lifecycle_guards(session_id, user_message)
        if guard:
            yield {**guard, "done": True}
            return

        session = get_or_create_session(session_id)
        start = time.perf_counter()

        messages = build_inference_payload(session_id, user_message)
        prompt = build_chatml_prompt(messages)
        full_text = ""

        try:
            loop = asyncio.get_event_loop()
            token_generator = await loop.run_in_executor(
                _executor,
                lambda: self.model(
                    prompt, max_tokens=MAX_TOKENS,
                    stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                    echo=False, temperature=TEMPERATURE, top_p=TOP_P,
                    repeat_penalty=REPEAT_PENALTY, stream=True,
                )
            )

            for token_data in token_generator:
                token = token_data["choices"][0]["text"]
                full_text += token
                yield {"token": token, "done": False}
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            if full_text.strip():
                clean = extract_and_strip_state(session_id, full_text)
                self._persist_turn(session_id, user_message, clean + " [cancelled]")
            yield {"token": "", "done": True, "cancelled": True, "session_id": session_id, "status": get_session_status(session_id)}
            return
        except Exception as e:
            logger.error(f"❌ [engine] [{session_id}] Stream error: {e}")
            yield {"token": "", "done": True, "error": str(e), "session_id": session_id, "status": "error"}
            return

        latency_ms = (time.perf_counter() - start) * 1000
        clean_response = extract_and_strip_state(session_id, full_text)

        self._persist_turn(session_id, user_message, clean_response)
        self._update_lifecycle(session_id)

        session = get_or_create_session(session_id)
        yield {
            "token": "", "done": True, "full_response": clean_response,
            "latency_ms": round(latency_ms, 2), "session_id": session_id,
            "status": session["status"], "turns_used": session["turns"], "turns_max": MAX_TURNS,
        }
    async def generate(self, session_id: str, user_message: str) -> dict:
        """
        Non-streaming wrapper for the stream method. 
        Collects all tokens and returns a standard ChatResponse dict.
        """
        full_response = ""
        latency_ms = 0
        status = "active"
        turns_used = 0

        async for chunk in self.stream(session_id, user_message):
            if not chunk.get("done"):
                full_response += chunk.get("token", "")
            else:
                latency_ms = chunk.get("latency_ms", 0)
                status = chunk.get("status", "active")
                turns_used = chunk.get("turns_used", 0)

        return {
            "response": full_response,
            "latency_ms": latency_ms,
            "session_id": session_id,
            "status": status,
            "turns_used": turns_used,
            "turns_max": MAX_TURNS
        }
        
    def _persist_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        add_message_to_chat(session_id, "user", user_msg)
        add_message_to_chat(session_id, "assistant", assistant_msg)
        increment_turn(session_id)

    def _update_lifecycle(self, session_id: str) -> None:
        if get_session_status(session_id) == "ended":
            return
        if is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")

    def _make_response(self, session_id: str, session: dict, response: str, latency_ms: float = 0.0, status: str = None) -> dict:
        return {
            "response": response, "latency_ms": round(latency_ms, 2), "session_id": session_id,
            "status": status or session.get("status", "active"), "turns_used": session.get("turns", 0),
            "turns_max": MAX_TURNS,
        }

llm_engine = LLMEngine()