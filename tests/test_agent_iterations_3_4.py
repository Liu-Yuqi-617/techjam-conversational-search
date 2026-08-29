from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent


CATALOG = [
    {"parent_asin": "BLUE", "title": "Blue cotton running shoes", "categories": ["Shoes"], "features": ["lightweight"], "details": {}, "description": [], "store": "Acme", "price": 40, "average_rating": 4.8, "rating_number": 100},
    {"parent_asin": "BLACK", "title": "Black leather winter boots", "categories": ["Boots"], "features": ["waterproof"], "details": {}, "description": [], "store": "Bravo", "price": 90, "average_rating": 4.5, "rating_number": 10},
]


class IterationThreeAndFourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.directory.name) / "catalog.jsonl"
        cls.catalog.write_text("".join(json.dumps(row) + "\n" for row in CATALOG), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def agent(self) -> Agent:
        return Agent(self.catalog)

    def test_buying_recommends_immediately_and_records_route_reason(self) -> None:
        agent = self.agent(); agent.reset("buy", {})
        response = agent.respond("buy", "I need blue cotton running shoes", 1, 10)
        self.assertEqual(agent.sessions["buy"].route, "buying")
        self.assertTrue(agent.sessions["buy"].route_reason)
        self.assertEqual(response["recommendations"], [{"parent_asin": "BLUE"}])

    def test_browsing_recommends_and_asks_one_attribute(self) -> None:
        agent = self.agent(); agent.reset("browse", {})
        response = agent.respond("browse", "I'm still exploring shoes", 1, 10)
        self.assertEqual(agent.sessions["browse"].route, "browsing")
        self.assertTrue(response["recommendations"])
        self.assertIn(response["ask_attribute"], {"feature", "material", "color", "use_case", "size", "budget", "style", "brand"})

    def test_explicit_override_removes_old_constraints_from_active_query(self) -> None:
        agent = self.agent(); agent.reset("override", {})
        agent.respond("override", "I need blue cotton shoes", 1, 10)
        agent.respond("override", "Actually, ignore my earlier preference. Now I need black leather boots.", 3, 10)
        state = agent.sessions["override"]
        self.assertEqual(state.slots["color"].value, "black")
        self.assertEqual(state.slots["material"].value, "leather")
        self.assertEqual(state.slots["category"].value, "boots")
        self.assertNotIn("blue", state.active_values())
        self.assertNotIn("cotton", state.active_values())

    def test_override_keeps_product_class_when_only_an_attribute_changes(self) -> None:
        agent = self.agent(); agent.reset("partial-override", {})
        agent.respond("partial-override", "I need blue shoes", 1, 10)
        agent.respond("partial-override", "Actually, I need black instead.", 2, 10)
        state = agent.sessions["partial-override"]
        self.assertEqual(state.slots["category"].value, "shoes")
        self.assertEqual(state.slots["category"].level, "soft")
        self.assertEqual(state.slots["color"].value, "black")


    def test_boundary_does_not_repeat_questioned_attribute(self) -> None:
        agent = self.agent(); agent.reset("boundary", {})
        first = agent.respond("boundary", "I'm browsing shoes", 1, 10)
        attribute = first["ask_attribute"]
        self.assertIsNotNone(attribute)
        second = agent.respond("boundary", f"I don't have a preference for {attribute}", 2, 10)
        self.assertNotEqual(second["ask_attribute"], attribute)
        self.assertEqual(agent.sessions["boundary"].slots[attribute].status, "unconstrained")

    def test_clarification_uses_candidate_split_and_stops_at_turn_eight(self) -> None:
        agent = self.agent(); agent.reset("split", {})
        early = agent.respond("split", "I'm browsing shoes", 1, 10)
        state = agent.sessions["split"]
        self.assertIsNotNone(early["ask_attribute"])
        self.assertIn(early["ask_attribute"], state.candidate_attribute_coverage)
        self.assertGreaterEqual(state.candidate_attribute_coverage[early["ask_attribute"]], 0.05)
        late = agent.respond("split", "Please show more options", 8, 10)
        self.assertIsNone(late["ask_attribute"])
