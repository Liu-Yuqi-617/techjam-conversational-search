"""Deterministic, serializable conversation state for the offline agent."""

from __future__ import annotations

from dataclasses import dataclass, field

SLOT_NAMES = ("category", "material", "color", "size", "style", "brand", "budget", "feature", "use_case", "goal")

@dataclass
class Slot:
    """One normalized preference and its lifecycle within a conversation."""

    value: object | None = None
    operator: str = "eq"
    level: str = "soft"
    status: str = "empty"
    source_turn: int | None = None
    confidence: float = 0.0
    explicit: bool = False

@dataclass
class SessionState:
    """All mutable state for one session; no state is shared across shoppers."""

    intent: str = "unknown"
    slots: dict[str, Slot] = field(default_factory=lambda: {name: Slot() for name in SLOT_NAMES})
    query_history: list[str] = field(default_factory=list)
    recommended_asins: set[str] = field(default_factory=set)
    asked_attributes: set[str] = field(default_factory=set)
    route: str = "unknown"
    route_reason: str = ""
    candidate_attribute_coverage: dict[str, float] = field(default_factory=dict)
    debug_events: list[dict[str, object]] = field(default_factory=list)
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    profile_terms: list[str] = field(default_factory=list)

    def active_values(self) -> list[str]:
        """Return only current preference values used to build the FTS query."""
        result: list[str] = []
        for slot in self.slots.values():
            if slot.status == "active" and slot.value not in (None, ""):
                result.extend(slot.value if isinstance(slot.value, list) else [str(slot.value)])
        return result

    def deactivate_for_override(self, turn: int) -> None:
        """Archive prior intent so a replacement query cannot inherit it."""
        for name, slot in self.slots.items():
            if slot.status == "active":
                slot.status = "replaced"
                # Keep the history on the old record while making the current
                # state unambiguously queryable through active_values().
                self.slots[name] = Slot(status="replaced", source_turn=slot.source_turn,
                                        confidence=slot.confidence, explicit=slot.explicit)

    def deactivate_prior_to(self, turn: int) -> None:
        """Archive active values from earlier turns before applying a replacement."""
        for name, slot in self.slots.items():
            if slot.status == "active" and slot.source_turn is not None and slot.source_turn < turn:
                self.slots[name] = Slot(status="replaced", source_turn=slot.source_turn,
                                        confidence=slot.confidence, explicit=slot.explicit)
