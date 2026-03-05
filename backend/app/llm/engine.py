# =============================================================================
# llm/engine.py
# Purpose : Loads the Qwen2.5-1.5B-Instruct-Q4_K_M GGUF model via
#           llama-cpp-python and exposes a single generate() function.
#           Integrates with context.py for state extraction and prompt
#           assembly, and with config.py for ChatML formatting.
# Optimised for: 4-core Intel i5 8th Gen, CPU-only inference, no RAG.
# =============================================================================

import os
import time
import logging
from llama_cpp import Llama

from app.core.config    import build_chatml_prompt
from app.memory.context import (
    build_inference_payload,
    add_message_to_chat,
    extract_and_strip_state,
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
        If loading fails the server still starts — responses will degrade
        gracefully rather than crashing the entire process.
        """
        model_path = os.getenv(
            "MODEL_PATH",
            # Default path matches docker-compose volume + local dev layout
            "./models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
            
        )

        logger.info(f"[engine] Loading model from: {model_path}")

        try:
            self.model = Llama(
                model_path = model_path,

                # --- Context window ---
                # 4096 is safe for 8 GB RAM + 1.12 GB model.
                # Do NOT raise this above 4096 on a 4-core i5.
                n_ctx      = 4096,

                # --- CPU threading ---
                # Match physical core count exactly. Hyperthreading does NOT
                # help llama.cpp — using logical cores (8) actually slows it.
                n_threads  = 4,

                # --- Batch size ---
                # 512 tokens processed per forward pass. Good balance between
                # throughput and memory pressure on a laptop CPU.
                n_batch    = 512,

                # --- GPU layers ---
                # 0 = full CPU inference (required — no GPU assumed).
                n_gpu_layers = 0,

                # Suppress llama.cpp's verbose C++ logs in production.
                verbose    = False,
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
        Main entry point called by your partner's routes.py.

        Full pipeline per call:
        1. Build sliding-window + state-injected message list (context.py).
        2. Format it as a ChatML string (config.py).
        3. Run llama-cpp-python inference.
        4. Strip <STATE> tag, update session state (context.py).
        5. Persist the clean turn to session history (context.py).
        6. Return structured result dict.

        Args:
            session_id   (str): UUID identifying the active chat session.
            user_message (str): Raw text the user just sent.

        Returns:
            dict: {
                "response"   : str,    # clean assistant reply shown to user
                "latency_ms" : float,  # end-to-end inference time in ms
                "session_id" : str,
            }
        """
        # --- Guard: model failed to load ---
        if self.model is None:
            return {
                "response"   : "I'm sorry, the assistant is temporarily unavailable. Please try again later.",
                "latency_ms" : 0.0,
                "session_id" : session_id,
            }

        # --- Step 1: Build the inference payload ---
        # context.py applies the sliding window, injects extracted state into
        # the system prompt, and appends the new user message.
        messages = build_inference_payload(session_id, user_message)

        # --- Step 2: Format to ChatML string ---
        prompt = build_chatml_prompt(messages)

        logger.debug(f"[engine] [{session_id}] Prompt length: {len(prompt)} chars")

        # --- Step 3: Inference ---
        start = time.perf_counter()

        try:
            raw_output = self.model(
                prompt,

                # Max tokens the model may generate in a single turn.
                # 512 keeps responses concise and fast on CPU.
                max_tokens  = 512,

                # Stop tokens for Qwen2.5 ChatML format.
                # These prevent the model from role-playing both sides.
                stop        = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],

                # Do not repeat the prompt in the output.
                echo        = False,

                # Sampling parameters — conservative for a factual assistant.
                temperature = 0.7,   # slight creativity without hallucination
                top_p       = 0.9,   # nucleus sampling
                repeat_penalty = 1.1 # mild penalty to reduce repetition
            )
            raw_text = raw_output["choices"][0]["text"].strip()

        except Exception as exc:
            logger.error(f"❌ [engine] Inference error for session {session_id}: {exc}")
            return {
                "response"   : "Something went wrong during inference. Please try again.",
                "latency_ms" : 0.0,
                "session_id" : session_id,
            }

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(f"[engine] [{session_id}] Inference complete in {latency_ms:.1f}ms")

        # --- Step 4: Strip <STATE> tag and update session state ---
        # extract_and_strip_state() mutates the session's state dict in-place
        # and returns the clean text the user should see.
        clean_response = extract_and_strip_state(session_id, raw_text)

        # --- Step 5: Persist this clean turn to history ---
        # We store user message first, then assistant — always in order.
        add_message_to_chat(session_id, "user",      user_message)
        add_message_to_chat(session_id, "assistant", clean_response)

        return {
            "response"   : clean_response,
            "latency_ms" : round(latency_ms, 2),
            "session_id" : session_id,
        }


# =============================================================================
# MODULE-LEVEL SINGLETON
# Instantiated once when the module is first imported by FastAPI.
# routes.py imports this object directly:
#   from app.llm.engine import llm_engine
# =============================================================================
llm_engine = LLMEngine()