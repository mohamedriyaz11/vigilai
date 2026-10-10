"""Pluggable LLM provider interface for VigilAI (none | local | cloud).

HARD PRIVACY CONSTRAINT:
Video frames are NEVER sent over the network or passed to any LLM.
Only strictly sanitized, structured symbolic JSON event summaries are processed.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for speech explanation verbalization."""

    @abstractmethod
    def generate_explanation(self, event_summary: dict[str, Any]) -> str | None:
        """Generate a natural sentence explaining the event. Returns None on failure."""
        pass


class NoneLLMProvider(LLMProvider):
    """Default provider: entirely offline, uses deterministic rule-based templates."""

    def generate_explanation(self, event_summary: dict[str, Any]) -> str | None:
        # None provider returns None so caller immediately uses canonical fallback template
        return None


class LocalLLMProvider(LLMProvider):
    """Local quantized model provider (e.g. llama-cpp-python running GGUF on CPU/NPU)."""

    def __init__(self, model_path: str = "") -> None:
        self.model_path = model_path
        self._llm = None
        if model_path and os.path.exists(model_path):
            try:
                from llama_cpp import Llama

                logger.info("Loading local LLM from %s...", model_path)
                self._llm = Llama(model_path=model_path, n_ctx=512, verbose=False)
            except Exception as exc:
                logger.warning("Could not initialize local llama_cpp (%s). Falling back.", exc)

    def generate_explanation(self, event_summary: dict[str, Any]) -> str | None:
        if self._llm is None:
            return None

        prompt = (
            "You are VigilAI, an ambient desk companion. In one short, polite sentence, "
            "inform the user of this event:\n"
            f"{json.dumps(event_summary)}\n"
            "Sentence:"
        )
        try:
            output = self._llm(prompt, max_tokens=40, stop=["\n"], temperature=0.2)
            text = output["choices"][0]["text"].strip()
            return text if text else None
        except Exception as exc:
            logger.warning("Local LLM inference error: %s", exc)
            return None


class CloudLLMProvider(LLMProvider):
    """Text-only cloud API (e.g. OpenAI / Groq / Anthropic). Disabled by default."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        model: str = "gpt-4o-mini",
        enabled: bool = False,
    ) -> None:
        self.enabled = enabled
        self.api_key = api_key or os.getenv("VIGILAI_CLOUD_LLM_API_KEY", "")
        self.endpoint = endpoint
        self.model = model

    def generate_explanation(self, event_summary: dict[str, Any]) -> str | None:
        if not self.enabled or not self.api_key:
            return None

        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are VigilAI, an ambient assistant. Output only a single brief, helpful spoken alert sentence. Never hallucinate or add preamble.",
                },
                {
                    "role": "user",
                    "content": f"Event: {json.dumps(event_summary)}",
                },
            ],
            "max_tokens": 45,
            "temperature": 0.2,
        }
        try:
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            logger.warning("Cloud LLM returned HTTP %d: %s", resp.status_code, resp.text)
            return None
        except Exception as exc:
            logger.warning("Cloud LLM request failed or timed out: %s", exc)
            return None
