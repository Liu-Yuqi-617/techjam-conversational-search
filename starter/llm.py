"""Small, optional Ollama planner with a safe offline failure mode.

The planner deliberately has no catalog access.  It can only improve dialogue
state from the current customer message; retrieval remains deterministic.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib import request


ALLOWED_ATTRIBUTES = frozenset({
    "category", "material", "color", "size", "style", "brand", "budget",
    "feature", "use_case", "other",
})
ALLOWED_SLOTS = ALLOWED_ATTRIBUTES - {"other"}

SYSTEM_PROMPT = """You are a shopping-dialogue planner. Return exactly one JSON object,
with no markdown and no explanation. Allowed keys are intent, override, slots,
and ask_attribute. intent is buying or browsing. override is boolean. slots is
an object whose keys are only category, material, color, size, style, brand,
budget, feature, use_case; each value is a short English string or number.
ask_attribute is one allowed attribute or null. Never return product IDs,
recommendations, or any text outside the JSON object."""


@dataclass(frozen=True)
class PlannerResult:
    payload: dict[str, Any] | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    failure: str | None = None


class OllamaPlanner:
    """Ollama's local HTTP API, disabled unless explicitly opted in by env var."""

    def __init__(self, *, enabled: bool | None = None, host: str | None = None,
                 model: str | None = None, timeout_seconds: float | None = None) -> None:
        self.enabled = (os.getenv("SHOPPING_LLM_ENABLED") == "1") if enabled is None else enabled
        self.host = (host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("SHOPPING_LLM_MODEL", "")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else float(os.getenv("SHOPPING_LLM_TIMEOUT_SECONDS", "1.5"))

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.model)

    def plan(self, message: str, state: dict[str, Any]) -> PlannerResult:
        if not self.available:
            return PlannerResult(None, failure="disabled")
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "system": SYSTEM_PROMPT,
            "prompt": json.dumps({"customer_message": message[:2000], "state": state}, ensure_ascii=True),
        }
        started = time.perf_counter()
        try:
            encoded = json.dumps(body).encode("utf-8")
            req = request.Request(self.host + "/api/generate", data=encoded,
                                  headers={"Content-Type": "application/json"}, method="POST")
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw.get("response", "")
            payload = json.loads(content) if isinstance(content, str) else None
            validated = self._validate(payload)
            elapsed = round((time.perf_counter() - started) * 1000)
            if validated is None:
                return PlannerResult(None, latency_ms=elapsed, failure="invalid_json_schema")
            return PlannerResult(validated, int(raw.get("prompt_eval_count") or 0),
                                 int(raw.get("eval_count") or 0), elapsed)
        except Exception as exc:  # Network/model errors must never interrupt an agent turn.
            elapsed = round((time.perf_counter() - started) * 1000)
            return PlannerResult(None, latency_ms=elapsed, failure=type(exc).__name__)

    @staticmethod
    def _validate(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict) or set(value) - {"intent", "override", "slots", "ask_attribute"}:
            return None
        result: dict[str, Any] = {}
        intent = value.get("intent")
        if intent is not None:
            if intent not in {"buying", "browsing"}:
                return None
            result["intent"] = intent
        override = value.get("override")
        if override is not None:
            if not isinstance(override, bool):
                return None
            result["override"] = override
        slots = value.get("slots")
        if slots is not None:
            if not isinstance(slots, dict) or set(slots) - ALLOWED_SLOTS:
                return None
            clean_slots = {key: item for key, item in slots.items()
                           if isinstance(item, (str, int, float)) and str(item).strip()}
            if len(clean_slots) != len(slots):
                return None
            result["slots"] = clean_slots
        asked = value.get("ask_attribute")
        if asked is not None:
            if asked not in ALLOWED_ATTRIBUTES:
                return None
            result["ask_attribute"] = asked
        return result
