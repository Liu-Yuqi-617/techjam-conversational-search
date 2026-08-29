from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent

CATALOG = [
    {"parent_asin": "A", "title": "Blue cotton running shoes", "categories": ["Shoes"], "features": ["waterproof", "lightweight"], "details": {}, "description": ["sporty shoe"], "store": "Acme", "price": 40, "average_rating": 4.8, "rating_number": 100},
    {"parent_asin": "B", "title": "Black leather winter boots", "categories": ["Boots"], "features": ["warm", "durable"], "details": {}, "description": ["classic style"], "store": "Bravo", "price": 90, "average_rating": 4.5, "rating_number": 10},
]

class IterationOneAndTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(); cls.catalog = Path(cls.directory.name) / "catalog.jsonl"
        cls.catalog.write_text("".join(json.dumps(row) + "\n" for row in CATALOG), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None: cls.directory.cleanup()
    def agent(self) -> Agent: return Agent(self.catalog)

    def test_retrieval_is_deterministic_and_valid(self) -> None:
        agent = self.agent(); agent.reset("one", {})
        first = agent.respond("one", "I need blue cotton running shoes under $50", 1, 10)["recommendations"]
        agent.reset("two", {}); second = agent.respond("two", "I need blue cotton running shoes under $50", 1, 10)["recommendations"]
        self.assertEqual(first, second); self.assertEqual(first, [{"parent_asin": "A"}])

    def test_slots_have_three_english_regressions_each(self) -> None:
        cases = {
            "category": ["running shoes", "winter boots", "a casual dress"], "material": ["cotton shirt", "leather boots", "silk scarf"], "color": ["blue shoes", "black bag", "red dress"], "size": ["small shirt", "wide shoes", "petite coat"], "style": ["classic watch", "sporty shoes", "formal dress"], "brand": ["brand Acme shoes", "by Bravo boots", "from Cedar bags"], "budget": ["under $50 shoes", "above $20 boots", "$30 shirt"], "feature": ["waterproof boots", "lightweight shoes", "durable bag"], "use_case": ["running shoes", "hiking boots", "travel bag"], "goal": ["good value shoes", "affordable boots", "premium bag"],
        }
        for attribute, messages in cases.items():
            for message in messages:
                agent = self.agent(); agent.reset("s", {}); agent.respond("s", message, 1, 10)
                self.assertEqual(agent.sessions["s"].slots[attribute].status, "active", (attribute, message))

    def test_accumulates_budget_boundary_and_reset(self) -> None:
        agent = self.agent(); agent.reset("s", {})
        agent.respond("s", "I need blue leather boots under $100", 1, 10); agent.respond("s", "They should be waterproof", 2, 10)
        state = agent.sessions["s"]
        self.assertEqual(state.slots["color"].value, "blue"); self.assertEqual(state.slots["material"].value, "leather")
        self.assertEqual(state.slots["budget"].operator, "lte"); self.assertEqual(state.slots["feature"].value, "waterproof")
        agent.respond("s", "I don't have a preference for color", 3, 10); self.assertEqual(state.slots["color"].status, "unconstrained")
        agent.reset("s", {}); self.assertEqual(agent.sessions["s"].slots["color"].status, "empty")

if __name__ == "__main__": unittest.main()
