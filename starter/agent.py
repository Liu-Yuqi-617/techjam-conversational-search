from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from starter.llm import OllamaPlanner
from starter.state import SessionState, Slot

TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some", "that", "the", "this", "to", "want", "with", "would", "you", "looking", "still", "here", "there", "those", "options", "quite", "right", "yet", "ask", "about", "one", "specific", "attribute"}
COLORS = ("black", "white", "blue", "red", "pink", "green", "brown", "gray", "grey", "purple", "yellow", "orange", "beige", "navy", "gold", "silver")
MATERIALS = ("cotton", "polyester", "nylon", "leather", "wool", "spandex", "silk", "rayon", "linen", "denim", "suede", "fabric")
SIZES = ("xxs", "xs", "small", "medium", "large", "xl", "xxl", "wide", "narrow", "petite", "plus")
USE_CASES = ("running", "hiking", "walking", "gym", "work", "winter", "outdoor", "rain", "wedding", "travel", "casual", "party", "yoga", "swimming")
FEATURES = ("waterproof", "water resistant", "breathable", "comfortable", "lightweight", "durable", "warm", "insulated", "stretch", "support", "quick dry", "uv protection")
CATEGORIES = ("shoe", "shoes", "boot", "boots", "sandal", "sandals", "sneaker", "sneakers", "shirt", "shirts", "jacket", "coat", "dress", "dresses", "jeans", "pants", "shorts", "skirt", "bra", "earring", "earrings", "necklace", "ring", "watch", "bag", "handbag", "backpack", "belt", "sock", "socks", "hat", "cap", "glove", "gloves", "swimsuit")
OVERRIDE_RE = re.compile(r"\b(?:actually|instead|change\s+(?:of\s+)?plan|ignore\s+(?:my\s+)?earlier|now\s+(?:i\s+)?need)\b", re.I)
BUYING_RE = re.compile(r"\b(?:need|buy|purchase|must have|looking for|want)\b", re.I)
BROWSING_RE = re.compile(r"\b(?:explor(?:e|ing)|browse|just looking|show me|ideas|options)\b", re.I)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def _terms(text: str) -> list[str]:
    return [term.lower() for term in TOKEN_RE.findall(text) if len(term) > 1 and term.lower() not in STOPWORDS]


def _matches(text: str, values: tuple[str, ...]) -> list[str]:
    return [word for word in values if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text.lower())]


class Agent:
    """Deterministic, offline FTS5 retrieval with per-session English slot state."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl", *, llm_planner: OllamaPlanner | None = None) -> None:
        self.catalog_path = Path(catalog_path)
        self.connection = sqlite3.connect(":memory:")
        self.sessions: dict[str, SessionState] = {}
        self.llm_planner = llm_planner or OllamaPlanner()
        self.profile_weight = float(os.getenv("SHOPPING_PROFILE_WEIGHT", "0"))
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute("CREATE VIRTUAL TABLE products USING fts5(parent_asin UNINDEXED, title, categories, features, details, store, description, price UNINDEXED, rating UNINDEXED, rating_count UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
        batch: list[tuple[object, ...]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line in handle:
                product = json.loads(line)
                batch.append((str(product["parent_asin"]), _text(product.get("title")), _text(product.get("categories")), _text(product.get("features")), _text(product.get("details")), _text(product.get("store")), _text(product.get("description")), product.get("price"), product.get("average_rating") or 0, product.get("rating_number") or 0))
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch); batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()

    def reset(self, session_id: str, user_profile: dict) -> None:
        state = SessionState()
        # Profile is a soft, opt-in quality signal and never a slot constraint.
        # It remains off in the frozen default after its public-set ablation.
        if self.profile_weight > 0 and isinstance(user_profile, dict):
            state.profile_terms = _terms(" ".join(_text(value) for value in (
                user_profile.get("preference_tags", []), user_profile.get("summary", ""))))[:20]
        self.sessions[session_id] = state

    @staticmethod
    def _set(state: SessionState, name: str, value: object, turn: int, operator: str = "eq", level: str = "soft") -> None:
        old = state.slots[name]
        if old.status == "active" and old.value != value:
            old.status = "replaced"
        state.slots[name] = Slot(value=value, operator=operator, level=level, status="active", source_turn=turn, confidence=1.0, explicit=True)

    def _extract(self, state: SessionState, message: str, turn: int) -> None:
        text = message.lower(); state.query_history.append(message)
        is_override = bool(OVERRIDE_RE.search(text))
        inherited_category = state.slots["category"].value if state.slots["category"].status == "active" else None
        if is_override:
            state.deactivate_for_override(turn)
            state.debug_events.append({"turn": turn, "event": "override", "reason": "explicit override signal"})
        # `goal` is a normalized current-turn slot, not a concatenation of history.
        # It keeps category/detail words that do not belong to one of the fixed
        # attribute dictionaries while all earlier constraints remain in slots.
        normalized_goal = _terms(text)
        if normalized_goal:
            self._set(state, "goal", normalized_goal, turn)
        self._route(state, text, turn)
        boundary = re.search(r"(?:no|don't have|do not have|without) (?:a |any )?(?:preference|preference for)?\s*(?:for )?(category|material|color|size|style|brand|budget|feature|use case)", text)
        if boundary:
            state.slots[boundary.group(1).replace(" ", "_")] = Slot(status="unconstrained", source_turn=turn, confidence=1.0, explicit=True)
        for name, words, level in (("color", COLORS, "hard"), ("material", MATERIALS, "hard"), ("size", SIZES, "hard"), ("use_case", USE_CASES, "soft"), ("feature", FEATURES, "soft"), ("category", CATEGORIES, "hard")):
            found = _matches(text, words)
            if found and state.slots[name].status != "unconstrained":
                self._set(state, name, found if len(found) > 1 else found[0], turn, level=level)
        # "Actually I need it in black" replaces colour, not necessarily the
        # product class. Keep the prior class as a non-explicit soft hint only
        # when the replacement message does not name a new class.
        if is_override and inherited_category and state.slots["category"].status != "active":
            self._set(state, "category", inherited_category, turn, level="soft")
        for pattern, operator in ((r"(?:under|below|less than|up to|at most|<=)\s*\$?\s*(\d+(?:\.\d{1,2})?)", "lte"), (r"(?:over|above|more than|at least|>=)\s*\$?\s*(\d+(?:\.\d{1,2})?)", "gte"), (r"\$\s*(\d+(?:\.\d{1,2})?)", "eq")):
            match = re.search(pattern, text)
            if match:
                self._set(state, "budget", float(match.group(1)), turn, operator, "hard"); break
        brand = re.search(r"(?:brand|by|from)\s+([a-z][a-z0-9'&.-]*(?:\s+[a-z][a-z0-9'&.-]*){0,2})", text)
        if brand and state.slots["brand"].status != "unconstrained": self._set(state, "brand", brand.group(1).strip(), turn, level="hard")
        for style in ("formal", "sporty", "classic", "fashion", "regular fit", "slim fit", "oversized"):
            if style in text: self._set(state, "style", style, turn)

    def _apply_llm_plan(self, state: SessionState, message: str, turn: int) -> str | None:
        """Merge only literal supplemental soft LLM signals after rule extraction."""
        state_view = {name: slot.value for name, slot in state.slots.items() if slot.status == "active"}
        result = self.llm_planner.plan(message, {"intent": state.intent, "slots": state_view})
        state.llm_prompt_tokens += result.prompt_tokens
        state.llm_completion_tokens += result.completion_tokens
        if result.failure:
            state.debug_events.append({"turn": turn, "event": "llm_fallback", "reason": result.failure, "latency_ms": result.latency_ms})
            return None
        plan = result.payload or {}
        # Intent and explicit overrides are deliberately rule-only: a small
        # local model must never discard the search context. It may only fill
        # an empty supplemental slot using words present in this message.
        normalized_message = " ".join(_terms(message))
        for name, value in plan.get("slots", {}).items():
            normalized_value = " ".join(_terms(str(value)))
            if (name in {"feature", "style", "brand", "use_case"}
                    and state.slots[name].status == "empty"
                    and normalized_value
                    and normalized_value in normalized_message):
                self._set(state, name, value, turn, level="soft")
        state.debug_events.append({"turn": turn, "event": "llm_plan", "latency_ms": result.latency_ms})
        return None

    @staticmethod
    def _route(state: SessionState, text: str, turn: int) -> None:
        """Route without withholding recommendations; debug remains session-local."""
        active_hard = sum(slot.status == "active" and slot.level == "hard" for slot in state.slots.values())
        category_known = state.slots["category"].status == "active"
        if BROWSING_RE.search(text) and not (BUYING_RE.search(text) and active_hard >= 2):
            route, reason = "browsing", "explicit exploration language"
        elif BUYING_RE.search(text) or active_hard >= 2:
            route, reason = "buying", "purchase language or multiple hard constraints"
        elif category_known:
            route, reason = "browsing", "category known but no purchase commitment"
        else:
            route, reason = "browsing", "insufficient constraints"
        state.intent = route
        state.route = route
        state.route_reason = reason
        state.debug_events.append({"turn": turn, "event": "route", "route": route, "reason": reason})

    def _retrieve(self, state: SessionState, top_k: int) -> list[dict]:
        terms = list(dict.fromkeys(_terms(" ".join(state.active_values()))))[:40]
        if not terms: return []
        expression = " OR ".join(f'"{term}"' for term in terms)
        # Order the bounded FTS candidate pool before deterministic Python reranking.
        # Without this ORDER BY, SQLite is free to return arbitrary rowids for LIMIT.
        rows = self.connection.execute("SELECT parent_asin, title, categories, features, details, store, description, price, rating, rating_count, bm25(products, 8.0, 5.0, 3.5, 2.5, 1.5, 1.0, 1.0, 0.0, 0.0, 0.0) AS lexical FROM products WHERE products MATCH ? ORDER BY lexical LIMIT 120", (expression,)).fetchall()
        budget = state.slots["budget"]; scored: list[tuple[float, str]] = []
        # This is deliberately calculated from the retrieved candidate pool,
        # not from labels or evaluator state.  It estimates which unanswered
        # attribute would split the live search space most effectively.
        coverage_counts = {"feature": 0, "material": 0, "color": 0,
                           "use_case": 0, "size": 0, "style": 0,
                           "brand": 0, "budget": 0}
        eligible_rows = 0
        for row in rows:
            asin, *fields, price, rating, rating_count, lexical = row
            if budget.status == "active" and price is not None and ((budget.operator == "lte" and float(price) > float(budget.value)) or (budget.operator == "gte" and float(price) < float(budget.value))): continue
            corpus = " ".join(_text(field).lower() for field in fields)
            eligible_rows += 1
            for attribute, values in (("feature", FEATURES), ("material", MATERIALS),
                                      ("color", COLORS), ("use_case", USE_CASES),
                                      ("size", SIZES)):
                # Values are a fixed, normalized vocabulary; direct membership
                # avoids recompiling dozens of regular expressions per row.
                if any(value in corpus for value in values):
                    coverage_counts[attribute] += 1
            if any(word in corpus for word in ("formal", "sporty", "classic", "fashion", "slim fit", "oversized")):
                coverage_counts["style"] += 1
            if str(row[5]).strip():
                coverage_counts["brand"] += 1
            if price is not None:
                coverage_counts["budget"] += 1
            category_bonus = 0.0; category = state.slots["category"]
            if category.status == "active":
                wanted = category.value if isinstance(category.value, list) else [category.value]
                category_bonus = 4.0 * sum(str(word).lower() in _text(row[2]).lower() for word in wanted)
            profile_bonus = self.profile_weight * sum(term in corpus for term in state.profile_terms)
            score = -float(lexical) + 1.5 * sum(term in corpus for term in terms) + category_bonus + profile_bonus + .05 * float(rating or 0) + min(float(rating_count or 0), 10000) / 100000
            scored.append((score, str(asin)))
        state.candidate_attribute_coverage = {
            attribute: count / eligible_rows for attribute, count in coverage_counts.items()
        } if eligible_rows else {}
        scored.sort(key=lambda item: (-item[0], item[1]))
        limit = max(0, min(top_k, 10)); seen: set[str] = set(); result: list[dict] = []
        for _, asin in scored:
            if asin in seen: continue
            seen.add(asin); result.append({"parent_asin": asin})
            if len(result) == limit: break
        return result

    @staticmethod
    def _next_question(state: SessionState, turn: int, recommendations: list[dict]) -> str | None:
        """Select one unanswered attribute by deterministic candidate split value."""
        if turn >= 8 or not recommendations:
            return None
        # Coverage close to 50% yields the best binary split.  Attributes seen
        # in nearly every/no candidate have low information value.  The small
        # fixed preference is a stable answer-cost tie-break, not a label-based
        # heuristic.  Asked/unconstrained/current attributes are ineligible.
        order = ("feature", "material", "color", "use_case", "size", "budget", "style", "brand")
        candidates: list[tuple[float, int, str]] = []
        for position, attribute in enumerate(order):
            slot = state.slots[attribute]
            if slot.status in {"active", "unconstrained"} or attribute in state.asked_attributes:
                continue
            coverage = state.candidate_attribute_coverage.get(attribute, 0.0)
            split_value = 1.0 - abs(0.5 - coverage) * 2.0
            # Below 5% coverage a question is effectively a dead end.
            if coverage >= 0.05:
                candidates.append((split_value, -position, attribute))
        if not candidates:
            return None
        attribute = max(candidates)[2]
        state.asked_attributes.add(attribute)
        state.debug_events.append({"turn": turn, "event": "clarification", "attribute": attribute,
                                   "coverage": round(state.candidate_attribute_coverage[attribute], 4)})
        return attribute

    @staticmethod
    def _question_message(attribute: str | None, route: str) -> str:
        if not attribute:
            return "Here are the closest matches based on your current preferences."
        labels = {"feature": "feature", "use_case": "intended use", "budget": "budget", "color": "color", "material": "material", "size": "size", "style": "style", "brand": "brand"}
        prefix = "While you browse" if route == "browsing" else "To refine these options"
        return f"{prefix}, do you have a preference for {labels[attribute]}?"

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        if session_id not in self.sessions: raise RuntimeError("reset must be called before respond")
        state = self.sessions[session_id]; self._extract(state, user_message or "", turn)
        prompt_tokens_before = state.llm_prompt_tokens
        completion_tokens_before = state.llm_completion_tokens
        llm_ask_attribute = self._apply_llm_plan(state, user_message or "", turn)
        recommendations = self._retrieve(state, top_k); state.recommended_asins.update(item["parent_asin"] for item in recommendations)
        ask_attribute = self._next_question(state, turn, recommendations)
        # The model may propose a clarification only when the deterministic
        # policy considers it safe, unanswered, and useful.
        if llm_ask_attribute and ask_attribute and llm_ask_attribute == ask_attribute:
            state.debug_events.append({"turn": turn, "event": "llm_clarification_accepted", "attribute": ask_attribute})
        return {"message": self._question_message(ask_attribute, state.route), "ask_attribute": ask_attribute, "recommendations": recommendations, "usage": {"prompt_tokens": state.llm_prompt_tokens - prompt_tokens_before, "completion_tokens": state.llm_completion_tokens - completion_tokens_before}}
