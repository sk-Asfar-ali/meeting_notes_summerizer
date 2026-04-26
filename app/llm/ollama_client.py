"""Wrapper around Ollama chat calls used by the agents."""

import ollama
import logging
import os
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OllamaClient:
    """Small adapter that centralizes model options and error handling."""

    def __init__(self, model_name: Optional[str] = None):
        # Keep the default aligned with README.md. A 7B model can turn a small
        # upload into a multi-minute wait on typical laptops.
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
        self.num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "900"))
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, json_format: bool = False, temperature: float = 0.3) -> str:
        """Generate a response from the local Ollama model."""
        try:
            options = {
                "temperature": temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            }
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            kwargs = {
                "model": self.model_name,
                "messages": messages,
                "options": options,
                "keep_alive": self.keep_alive,
            }
            if json_format:
                kwargs["format"] = "json"
                
            response = ollama.chat(**kwargs)
            
            return response['message']['content']
        except Exception as e:
            logger.error(f"Error generating response from Ollama: {e}")
            return "{}" if json_format else f"Error: {e}"

    def check_model_availability(self) -> bool:
        """Check if the model is pulled and available locally."""
        try:
            response = ollama.list()
            # Support both new object response (response.models) and older dict response.
            models = getattr(response, 'models', response.get('models', [])) if hasattr(response, 'get') else response.models
            
            for m in models:
                name = getattr(m, 'model', getattr(m, 'name', m.get('name', '') if isinstance(m, dict) else ''))
                if name == self.model_name or name.startswith(f"{self.model_name}:"):
                    return True
            return False
        except Exception as e:
            logger.error(f"Could not connect to Ollama: {e}")
            return False
