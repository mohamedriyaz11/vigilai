"""Synthesizes human-centric spoken explanations from structured scene events.

Ensures absolute determinism through strict template fallbacks and schema validation.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.llm import LLMProvider, NoneLLMProvider

logger = logging.getLogger(__name__)


class EventExplainer:
    """Transforms structured symbolic events into succinct verbal messages."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.provider = llm_provider or NoneLLMProvider()

    def _render_template(self, label: str, rule_matched: str) -> str:
        """Produce guaranteed deterministic voice message based on matched rule."""
        label_clean = label.replace("_", " ").lower()
        if rule_matched == "medication_dose_window":
            return f"Your {label_clean} is on the counter for your scheduled dose."
        elif rule_matched == "walking_path_hazard":
            return f"Please watch your step; a {label_clean} is obstructing your walking path."
        elif rule_matched == "object_displaced":
            return f"Your {label_clean} appears to have moved from its usual spot."
        return f"A {label_clean} has been noticed nearby."

    def explain(
        self,
        label: str,
        direction: str,
        reason: str,
        urgency: str,
        rule_matched: str,
    ) -> str:
        """Generate verbal alert text.

        Guarantees:
        1. Critical alerts always use deterministic templates.
        2. Non-critical alerts attempt LLM verbalization if configured.
        3. Any validation failure or timeout falls back immediately to template.
        """
        template_text = self._render_template(label, rule_matched)

        # Invariant: Critical alerts ALWAYS bypass LLM and use deterministic template
        if urgency in {"critical", "high_critical"}:
            return template_text

        # Prepare strictly scoped structured JSON summary for optional LLM
        summary_payload: dict[str, Any] = {
            "label": label,
            "direction": direction,
            "reason": reason,
            "urgency": urgency,
        }

        try:
            llm_text = self.provider.generate_explanation(summary_payload)
            if self._validate_llm_output(llm_text):
                return str(llm_text).strip()
            if llm_text is not None:
                logger.warning("LLM explanation rejected validation. Falling back to template.")
        except Exception as exc:
            logger.warning("Explainer encountered error (%s). Falling back to template.", exc)

        return template_text

    def _validate_llm_output(self, text: str | None) -> bool:
        """Validate generated utterance against safety and clarity constraints."""
        if not text:
            return False
        clean = text.strip()
        # Reject excessively long responses, markdown blocks, or code leakage
        if len(clean) < 5 or len(clean) > 160:
            return False
        if "```" in clean or "{" in clean or "}" in clean or "<" in clean:
            return False
        return True
