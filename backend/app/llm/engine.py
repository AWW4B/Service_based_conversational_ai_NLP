from llama_cpp import Llama
import logging
import os

logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        model_path = os.getenv("MODEL_PATH", "./models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
        try:
            self.model = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_threads=4,
                n_batch=512,
                verbose=False
            )
            logger.info("✅ Qwen model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            self.model = None

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        if self.model is None:
            return "Model unavailable. Please try again later."
        try:
            output = self.model(
                prompt,
                max_tokens=max_tokens,
                stop=["<|im_end|>", "<|endoftext|>"],
                echo=False
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"❌ Inference failed: {e}")
            return "An error occurred during inference."

# Single instance, imported everywhere
llm_engine = LLMEngine()