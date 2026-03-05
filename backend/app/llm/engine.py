# =============================================================================
# llm/engine.py
# Purpose : Production-grade LLM engine with two-stage pipeline:
#           Stage 1 — Fast intent classifier (same model, max_tokens=5)
#           Stage 2 — Full response generation (only if on-topic)
#
#           Also includes:
#           - Async-safe inference via ThreadPoolExecutor
#           - Token streaming support
#           - Cancellation handling
#           - Robust error handling
# =============================================================================

import os
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional
from llama_cpp import Llama

from app.core.config import (
    build_chatml_prompt,
    MAX_TURNS, MAX_TOKENS, N_CTX, N_THREADS,
    N_BATCH, TEMPERATURE, TOP_P, REPEAT_PENALTY,
)
from app.memory.context import (
    active_chats,
    build_inference_payload,
    add_message_to_chat,
    extract_and_strip_state,
    increment_turn,
    is_session_maxed,
    get_session_status,
    set_session_status,
    is_conversation_resolved,
    get_or_create_session,
)

logger = logging.getLogger(__name__)

# =============================================================================
# THREAD POOL
# llama-cpp-python is synchronous C++. Running it directly in async FastAPI
# blocks the entire event loop. ThreadPoolExecutor keeps the event loop free
# so concurrent requests (health checks, resets, other sessions) are served
# while inference runs in the background thread.
#
# max_workers=1 because the model is NOT thread-safe.
# Concurrent inference requests queue here and execute one at a time.
# =============================================================================
_executor = ThreadPoolExecutor(max_workers=1)

# =============================================================================
# OFF-TOPIC REFUSAL MESSAGE
# Single source of truth — change here to update everywhere.
# =============================================================================
_REFUSAL = (
    "I can only help with product recommendations on Daraz.pk. "
    "Is there something you'd like to buy today?"
)


# =============================================================================
# LLM ENGINE
# =============================================================================

class LLMEngine:
    """
    Two-stage inference pipeline:

    Stage 1 — Intent Classifier:
        Tiny call to the same model (max_tokens=5, temperature=0).
        Classifies message as 'shopping' or 'off_topic'.
        Fast (~0.3-0.8s). No context window used.

    Stage 2 — Full Response:
        Only reached if Stage 1 returns 'shopping'.
        Uses full sliding window + STATE-injected system prompt.
        Generates complete assistant response.

    This separation means:
    - The main shopping prompt stays clean (no refusal rules needed)
    - The model uses its natural language understanding for classification
    - No brittle keyword lists
    - "how about a phone?" correctly classified as shopping
    - "I am bleeding" correctly classified as off_topic
    """

    def __init__(self):
        self.model: Optional[Llama] = None
        self._load_model()

    # -------------------------------------------------------------------------
    def _load_model(self) -> None:
        """
        Loads GGUF model once at startup.
        Server starts even on failure — responses degrade gracefully.
        """
        model_path = os.getenv(
            "MODEL_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "qwen2.5-3b-instruct-q4_k_m.gguf")
        )
        model_path = os.path.abspath(model_path)
        logger.info(f"[engine] Loading model: {model_path}")

        try:
            self.model = Llama(
                model_path   = model_path,
                n_ctx        = N_CTX,
                n_threads    = N_THREADS,
                n_batch      = N_BATCH,
                n_gpu_layers = 0,
                verbose      = False,
            )
            logger.info("✅ [engine] Model loaded.")

        except FileNotFoundError:
            logger.error(f"❌ [engine] Model not found: {model_path}")
            self.model = None
        except Exception as e:
            logger.error(f"❌ [engine] Load failed: {e}")
            self.model = None

    # -------------------------------------------------------------------------
    # STAGE 1 — INTENT CLASSIFIER
    # -------------------------------------------------------------------------

    async def _classify_intent(self, message: str, session_id: str) -> str:
        """
        Classifies intent WITH recent conversation context.
        This fixes vague follow-ups like "any alternate options?" being
        misclassified — the classifier now sees what was discussed before.
        """
        # Get last 2 exchanges for context (enough without being slow)
        session = get_or_create_session(session_id)
        recent  = session["history"][-4:]  # last 4 messages = 2 turns

        # Build a brief context summary for the classifier
        context_str = ""
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_str += f"{role}: {msg['content'][:80]}\n"

        classification_prompt = (
             "<|im_start|>system\n"
            "You are an intent classifier for a shopping assistant. Reply with ONLY one word: 'shopping' or 'off_topic'.\n"
            "Rule: If the user's message makes sense in the context of a shopping conversation, reply 'shopping'.\n"
            "Rule: Reply 'off_topic' ONLY if the message has absolutely nothing to do with shopping, buying, or products.\n"
            "Rule: Switching products, changing requirements, asking follow-up questions, or refining preferences are all 'shopping'.\n"
            "Rule: When in doubt, reply 'shopping'.\n"
            "<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Recent conversation:\n{context_str}\n"
            f"Classify this message: {message}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: self.model(
                    classification_prompt,
                    max_tokens  = 5,
                    temperature = 0.0,
                    echo        = False,
                    stop        = ["<|im_end|>", "\n", " "],
                )
            )
            label  = result["choices"][0]["text"].strip().lower()
            intent = "shopping" if "shopping" in label else "off_topic"
            logger.info(f"[engine] Intent: '{message[:40]}' → {intent}")
            return intent

        except Exception as e:
            logger.error(f"[engine] Intent classification failed: {e}")
            return "shopping"

    # -------------------------------------------------------------------------
    # LIFECYCLE GUARDS
    # -------------------------------------------------------------------------

    def _check_lifecycle_guards(
        self, session_id: str, user_message: str
    ) -> Optional[dict]:
        """
        Checks session lifecycle state before any inference.
        Returns a response dict if a guard triggers, None if clear to proceed.
        """
        session = get_or_create_session(session_id)

        # Guard 0: Model unavailable
        if self.model is None:
            return self._make_response(
                session_id, session,
                "I'm temporarily unavailable. Please try again later.",
            )

        # Guard 1: Session already ended
        if get_session_status(session_id) == "ended":
            return self._make_response(
                session_id, session,
                "This session has ended. Please start a new chat.",
                status="ended",
            )

        # Guard 2: Turn limit reached
        if is_session_maxed(session_id):
            set_session_status(session_id, "ended")
            farewell = (
                "We've reached the end of our session. "
                "Thank you for shopping with Daraz Assistant! Have a great day. 🛍️"
            )
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", farewell)
            return self._make_response(
                session_id, session, farewell, status="ended"
            )

        return None  # all guards passed

    # -------------------------------------------------------------------------
    # STANDARD GENERATE (REST endpoint)
    # -------------------------------------------------------------------------

    async def generate(self, session_id: str, user_message: str) -> dict:
        """
        Two-stage async inference for POST /chat.

        Stage 1: classify intent (~0.5s)
        Stage 2: generate response (only if shopping)

        Args:
            session_id   (str): Active session ID.
            user_message (str): User's input.

        Returns:
            dict: {response, latency_ms, session_id, status, turns_used, turns_max}
        """
        # Lifecycle guards
        guard = self._check_lifecycle_guards(session_id, user_message)
        if guard:
            return guard

        session = get_or_create_session(session_id)
        start   = time.perf_counter()

        # --- Stage 1: Intent classification ---
        intent = await self._classify_intent(user_message, session_id)

        if intent == "off_topic":
            latency_ms = (time.perf_counter() - start) * 1000
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", _REFUSAL)
            increment_turn(session_id)
            logger.info(f"[engine] [{session_id}] off_topic refusal | {latency_ms:.0f}ms")
            return self._make_response(session_id, session, _REFUSAL, latency_ms)

        # --- Stage 2: Full response generation ---
        messages = build_inference_payload(session_id, user_message)
        prompt   = build_chatml_prompt(messages)

        try:
            loop       = asyncio.get_event_loop()
            raw_output = await loop.run_in_executor(
                _executor,
                lambda: self.model(
                    prompt,
                    max_tokens     = MAX_TOKENS,
                    stop           = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                    echo           = False,
                    temperature    = TEMPERATURE,
                    top_p          = TOP_P,
                    repeat_penalty = REPEAT_PENALTY,
                    stream         = False,
                )
            )
            raw_text = raw_output["choices"][0]["text"].strip()

        except asyncio.CancelledError:
            logger.warning(f"[engine] [{session_id}] Cancelled by client.")
            return self._make_response(session_id, session, "Response cancelled.")

        except Exception as e:
            logger.error(f"❌ [engine] [{session_id}] Inference error: {e}")
            return self._make_response(
                session_id, session, "Something went wrong. Please try again."
            )

        latency_ms     = (time.perf_counter() - start) * 1000
        clean_response = extract_and_strip_state(session_id, raw_text)

        self._persist_turn(session_id, user_message, clean_response)
        self._update_lifecycle(session_id)

        logger.info(
            f"[engine] [{session_id}] {latency_ms:.0f}ms | "
            f"turn {session['turns']}/{MAX_TURNS}"
        )

        session = get_or_create_session(session_id)
        return self._make_response(session_id, session, clean_response, latency_ms)

    # -------------------------------------------------------------------------
    # STREAMING GENERATE (WebSocket endpoint)
    # -------------------------------------------------------------------------

    async def stream(
        self, session_id: str, user_message: str
    ) -> AsyncGenerator[dict, None]:
        """
        Two-stage async token streaming for WebSocket /ws/chat.

        Stage 1: classify intent (instant, no streaming needed)
        Stage 2: stream tokens one by one (only if shopping)

        PARTNER NOTE (frontend WebSocket handler):
        - Each chunk while streaming: {"token": str, "done": false}
        - Final chunk:  {"token": "", "done": true, "full_response": str,
                         "latency_ms": float, "status": str,
                         "turns_used": int, "turns_max": int}
        - On cancelled:  {"token": "", "done": true, "cancelled": true}
        - On status="ended": disable the input box in UI
        """
        # Lifecycle guards
        guard = self._check_lifecycle_guards(session_id, user_message)
        if guard:
            yield {**guard, "done": True}
            return

        session = get_or_create_session(session_id)
        start   = time.perf_counter()

        # --- Stage 1: Intent classification ---
        intent = await self._classify_intent(user_message, session_id)

        if intent == "off_topic":
            latency_ms = (time.perf_counter() - start) * 1000
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", _REFUSAL)
            increment_turn(session_id)
            session = get_or_create_session(session_id)
            yield {
                "token"        : _REFUSAL,
                "done"         : True,
                "full_response": _REFUSAL,
                "latency_ms"   : round(latency_ms, 2),
                "session_id"   : session_id,
                "status"       : session["status"],
                "turns_used"   : session["turns"],
                "turns_max"    : MAX_TURNS,
            }
            return

        # --- Stage 2: Stream full response ---
        messages  = build_inference_payload(session_id, user_message)
        prompt    = build_chatml_prompt(messages)
        full_text = ""

        try:
            loop = asyncio.get_event_loop()

            token_generator = await loop.run_in_executor(
                _executor,
                lambda: self.model(
                    prompt,
                    max_tokens     = MAX_TOKENS,
                    stop           = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                    echo           = False,
                    temperature    = TEMPERATURE,
                    top_p          = TOP_P,
                    repeat_penalty = REPEAT_PENALTY,
                    stream         = True,
                )
            )

            for token_data in token_generator:
                token      = token_data["choices"][0]["text"]
                full_text += token
                yield {"token": token, "done": False}
                await asyncio.sleep(0)  # yield control to event loop

        except asyncio.CancelledError:
            # Client disconnected or pressed stop mid-stream
            logger.warning(
                f"[engine] [{session_id}] Stream cancelled "
                f"at {len(full_text)} chars."
            )
            if full_text.strip():
                clean = extract_and_strip_state(session_id, full_text)
                self._persist_turn(session_id, user_message, clean + " [cancelled]")
            yield {
                "token"     : "",
                "done"      : True,
                "cancelled" : True,
                "session_id": session_id,
                "status"    : get_session_status(session_id),
            }
            return

        except Exception as e:
            logger.error(f"❌ [engine] [{session_id}] Stream error: {e}")
            yield {
                "token"     : "",
                "done"      : True,
                "error"     : str(e),
                "session_id": session_id,
                "status"    : "error",
            }
            return

        # Stream complete — process and persist
        latency_ms     = (time.perf_counter() - start) * 1000
        clean_response = extract_and_strip_state(session_id, full_text)

        self._persist_turn(session_id, user_message, clean_response)
        self._update_lifecycle(session_id)

        logger.info(
            f"[engine] [{session_id}] stream {latency_ms:.0f}ms | "
            f"turn {session['turns']}/{MAX_TURNS}"
        )

        session = get_or_create_session(session_id)
        yield {
            "token"        : "",
            "done"         : True,
            "full_response": clean_response,
            "latency_ms"   : round(latency_ms, 2),
            "session_id"   : session_id,
            "status"       : session["status"],
            "turns_used"   : session["turns"],
            "turns_max"    : MAX_TURNS,
        }

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _persist_turn(
        self, session_id: str, user_msg: str, assistant_msg: str
    ) -> None:
        """Saves both sides of an exchange and increments turn counter."""
        add_message_to_chat(session_id, "user",      user_msg)
        add_message_to_chat(session_id, "assistant", assistant_msg)
        increment_turn(session_id)

    def _update_lifecycle(self, session_id: str) -> None:
        """
        Updates session status using semantic resolution from STATE tag.
        Model sets Resolved: yes when request is fully satisfied.
        'no' answers to mid-conversation questions won't trigger closing
        because the model sets Resolved: no in those cases.
        """
        if get_session_status(session_id) == "ended":
            return
        if is_conversation_resolved(session_id):
            set_session_status(session_id, "closing")
            logger.debug(f"[engine] [{session_id}] Status → closing")

    def _make_response(
        self,
        session_id : str,
        session    : dict,
        response   : str,
        latency_ms : float = 0.0,
        status     : str   = None,
    ) -> dict:
        """Builds a standardised response dict."""
        return {
            "response"   : response,
            "latency_ms" : round(latency_ms, 2),
            "session_id" : session_id,
            "status"     : status or session.get("status", "active"),
            "turns_used" : session.get("turns", 0),
            "turns_max"  : MAX_TURNS,
        }


# =============================================================================
# SINGLETON
# =============================================================================
llm_engine = LLMEngine()