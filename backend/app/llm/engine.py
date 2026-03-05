# =============================================================================
# llm/engine.py
# Purpose : Loads the Qwen2.5 GGUF model via llama-cpp-python and exposes
#           a single generate() function.
# Optimised for: 4-core Intel i5 8th Gen, CPU-only inference, no RAG.
# =============================================================================

import os
import time
import logging
from llama_cpp import Llama

from app.core.config import build_chatml_prompt, MAX_TURNS
from app.memory.context import (
    active_chats,
    build_inference_payload,
    add_message_to_chat,
    extract_and_strip_state,
    increment_turn,
    is_session_maxed,
    get_session_status,
    set_session_status,
    is_closing_message,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LLM ENGINE CLASS
# =============================================================================

class LLMEngine:
    """
    Singleton-style wrapper around a llama-cpp-python Llama instance.

    Responsibilities:
    - Load the GGUF model once at startup.
    - Accept a session_id + user message.
    - Build the prompt via context.py + config.py.
    - Run inference.
    - Strip hidden <STATE> tags from the output via context.py.
    - Persist the clean turn into session history.
    - Return the clean response to the caller (routes.py).
    """

    def __init__(self):
        self.model: Llama | None = None
        self._load_model()

    # -------------------------------------------------------------------------
    def _load_model(self) -> None:
        """
        Loads the GGUF model from the path set in the MODEL_PATH env variable.
        Falls back to a default relative path for local development.
        If loading fails the server still starts — responses degrade
        gracefully rather than crashing the entire process.
        """
        model_path = os.getenv(
            "MODEL_PATH",
            "./models/qwen2.5-3b-instruct-q4_k_m.gguf"
        )

        logger.info(f"[engine] Loading model from: {model_path}")

        try:
            self.model = Llama(
                model_path   = model_path,
                n_ctx        = 4096,     # safe for i5 8th gen RAM budget
                n_threads    = 4,        # match physical core count exactly
                n_batch      = 512,      # tokens per forward pass
                n_gpu_layers = 0,        # CPU-only inference
                verbose      = False,    # suppress llama.cpp C++ logs
            )
            logger.info("✅ [engine] Model loaded successfully.")

        except FileNotFoundError:
            logger.error(
                f"❌ [engine] Model file not found at '{model_path}'. "
                "Download it and set MODEL_PATH correctly."
            )
            self.model = None

        except Exception as exc:
            logger.error(f"❌ [engine] Unexpected error loading model: {exc}")
            self.model = None

    # -------------------------------------------------------------------------
    def generate(self, session_id: str, user_message: str) -> dict:
        """
        Main entry point called by routes.py for every user message.

        Pipeline:
        1. Guard checks (model loaded, session status, turn limit, closing)
        2. Build sliding-window + state-injected message list (context.py)
        3. Format as ChatML string (config.py)
        4. Run llama-cpp-python inference
        5. Strip <STATE> tag, update session state (context.py)
        6. Persist clean turn to session history
        7. Increment turn counter, update session status
        8. Return structured result dict to routes.py
        """

        # --- Guard 0: Model failed to load ---
        if self.model is None:
            return {
                "response"   : "I'm sorry, the assistant is temporarily unavailable. Please try again later.",
                "latency_ms" : 0.0,
                "session_id" : session_id,
                "status"     : "error",
                "turns_used" : 0,
                "turns_max"  : MAX_TURNS,
            }

        # --- Guard 1: Session already ended ---
        if get_session_status(session_id) == "ended":
            return {
                "response"   : "This chat session has ended. Please start a new chat.",
                "latency_ms" : 0.0,
                "session_id" : session_id,
                "status"     : "ended",
                "turns_used" : active_chats[session_id]["turns"],
                "turns_max"  : MAX_TURNS,
            }

        # --- Guard 2: Turn limit hit ---
        if is_session_maxed(session_id):
            set_session_status(session_id, "ended")
            farewell = (
                "We've reached the end of our session. "
                "Thank you for shopping with Daraz Assistant! Have a great day. 🛍️"
            )
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", farewell)
            return {
                "response"   : farewell,
                "latency_ms" : 0.0,
                "session_id" : session_id,
                "status"     : "ended",
                "turns_used" : active_chats[session_id]["turns"],
                "turns_max"  : MAX_TURNS,
            }

        # --- Guard 3: User is closing the conversation ---
        # Only triggers if the model previously asked "anything else?"
        # which set the status to "closing" in a prior turn.
        if is_closing_message(user_message) and get_session_status(session_id) == "closing":
            set_session_status(session_id, "ended")
            farewell = "Thank you for shopping with Daraz Assistant! Have a great day. 🛍️"
            add_message_to_chat(session_id, "user",      user_message)
            add_message_to_chat(session_id, "assistant", farewell)
            return {
                "response"   : farewell,
                "latency_ms" : 0.0,
                "session_id" : session_id,
                "status"     : "ended",
                "turns_used" : active_chats[session_id]["turns"],
                "turns_max"  : MAX_TURNS,
            }

        # --- Step 1: Build the inference payload ---
        # context.py applies the sliding window, injects extracted state
        # into the system prompt, and appends the new user message.
        messages = build_inference_payload(session_id, user_message)

        # --- Step 2: Format to ChatML string ---
        prompt = build_chatml_prompt(messages)
        logger.debug(f"[engine] [{session_id}] Prompt length: {len(prompt)} chars")

        # --- Step 3: Inference ---
        start = time.perf_counter()

        try:
            raw_output = self.model(
                prompt,
                max_tokens     = 512,
                stop           = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
                echo           = False,
                temperature    = 0.7,
                top_p          = 0.9,
                repeat_penalty = 1.1,
            )
            raw_text = raw_output["choices"][0]["text"].strip()

        except Exception as exc:
            logger.error(f"❌ [engine] Inference error for session {session_id}: {exc}")
            return {
                "response"   : "Something went wrong during inference. Please try again.",
                "latency_ms" : 0.0,
                "session_id" : session_id,
                "status"     : get_session_status(session_id),
                "turns_used" : active_chats[session_id]["turns"],
                "turns_max"  : MAX_TURNS,
            }

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(f"[engine] [{session_id}] Inference complete in {latency_ms:.1f}ms")

        # --- Step 4: Strip <STATE> tag and update session state ---
        clean_response = extract_and_strip_state(session_id, raw_text)

        # --- Step 5: Persist this clean turn to history ---
        add_message_to_chat(session_id, "user",      user_message)
        add_message_to_chat(session_id, "assistant", clean_response)

        # --- Step 6: Detect closing question from model ---
        # If the model ended with "anything else?", set status to closing
        # so the next user "no/bye" triggers the farewell guard above.
        if "anything else" in clean_response.lower():
            set_session_status(session_id, "closing")

        # --- Step 7: Increment turn counter ---
        increment_turn(session_id)
        session = active_chats[session_id]

        return {
            "response"   : clean_response,
            "latency_ms" : round(latency_ms, 2),
            "session_id" : session_id,
            "status"     : session["status"],   # frontend uses this to lock UI
            "turns_used" : session["turns"],
            "turns_max"  : MAX_TURNS,
        }


# =============================================================================
# MODULE-LEVEL SINGLETON
# Instantiated once when the module is first imported by FastAPI.
# routes.py imports this object directly:
#   from app.llm.engine import llm_engine
# =============================================================================
llm_engine = LLMEngine()