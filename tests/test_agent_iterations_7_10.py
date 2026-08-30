from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent
from starter.llm import OllamaPlanner, PlannerResult


CATALOG = [
    {"parent_asin": "BLUE", "title": "Blue cotton running shoes", "categories": ["Shoes"], "features": ["lightweight"], "details": {}, "description": [], "store": "Acme", "price": 40, "average_rating": 4.8, "rating_number": 100},
    {"parent_asin": "BLACK", "title": "Black leather winter boots", "categories": ["Boots"], "features": ["waterproof"], "details": {}, "description": [], "store": "Bravo", "price": 90, "average_rating": 4.5, "rating_number": 10},
]


class FakePlanner:
    def __init__(self, result: PlannerResult) -> None:
        self.result = result

    def plan(self, message: str, state: dict) -> PlannerResult:
        return self.result


class IterationSevenToTenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.directory.name) / "catalog.jsonl"
        cls.catalog.write_text("".join(json.dumps(row) + "\n" for row in CATALOG), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_llm_failure_keeps_a_valid_offline_response(self) -> None:
        agent = Agent(self.catalog, llm_planner=FakePlanner(PlannerResult(None, failure="TimeoutError")))
        agent.reset("offline", {})
        response = agent.respond("offline", "I need blue shoes", 1, 10)
        self.assertEqual(response["recommendations"], [{"parent_asin": "BLUE"}])
        self.assertEqual(response["usage"], {"prompt_tokens": 0, "completion_tokens": 0})
        self.assertIn("llm_fallback", [event["event"] for event in agent.sessions["offline"].debug_events])

    def test_llm_cannot_replace_rules_or_invent_a_soft_slot(self) -> None:
        planner = FakePlanner(PlannerResult({"intent": "browsing", "slots": {"color": "red", "feature": "lightweight"}}, 7, 3))
        agent = Agent(self.catalog, llm_planner=planner)
        agent.reset("merge", {})
        response = agent.respond("merge", "I need blue shoes", 1, 10)
        state = agent.sessions["merge"]
        self.assertEqual(state.slots["color"].value, "blue")
        self.assertIsNone(state.slots["feature"].value)
        self.assertEqual(response["usage"], {"prompt_tokens": 7, "completion_tokens": 3})

    def test_usage_is_reported_once_per_turn(self) -> None:
        planner = FakePlanner(PlannerResult({"slots": {}}, 5, 2))
        agent = Agent(self.catalog, llm_planner=planner)
        agent.reset("usage", {})
        first = agent.respond("usage", "I need shoes", 1, 10)
        second = agent.respond("usage", "show more", 2, 10)
        self.assertEqual(first["usage"], {"prompt_tokens": 5, "completion_tokens": 2})
        self.assertEqual(second["usage"], {"prompt_tokens": 5, "completion_tokens": 2})

    def test_llm_schema_rejects_product_ids_and_unknown_fields(self) -> None:
        self.assertIsNone(OllamaPlanner._validate({"recommendations": ["BLUE"]}))
        self.assertIsNone(OllamaPlanner._validate({"slots": {"parent_asin": "BLUE"}}))
        self.assertIsNone(OllamaPlanner._validate({"ask_attribute": "price"}))

    def test_llm_schema_keeps_allowlisted_slots_when_model_adds_noise(self) -> None:
        self.assertEqual(OllamaPlanner._validate({
            "slots": {"color": "blue", "parent_asin": "do-not-use"},
        }), {"slots": {"color": "blue"}})

    def test_empty_message_and_sessions_remain_isolated(self) -> None:
        agent = Agent(self.catalog, llm_planner=FakePlanner(PlannerResult(None, failure="disabled")))
        agent.reset("one", {}); agent.reset("two", {})
        empty = agent.respond("one", "", 1, 10)
        blue = agent.respond("two", "blue shoes", 1, 10)
        self.assertEqual(empty["recommendations"], [])
        self.assertEqual(blue["recommendations"], [{"parent_asin": "BLUE"}])
        self.assertEqual(agent.sessions["one"].slots["color"].status, "empty")
