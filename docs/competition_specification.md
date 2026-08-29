# Competition Specification

## Objective

Build a multi-turn shopping agent that finds a hidden target product as early and as highly ranked as possible.

The hidden target is based on a real purchase record from Amazon Reviews 2023. Customer messages are simulated from a hidden intent card derived from product metadata; the source dataset does not contain real shopping conversations.

## Scope

In scope: keyword, dense, or hybrid retrieval; Buying/Browsing routing; query rewriting; semantic reranking; conversation-state management; clarification strategy; anonymized-profile use; legally accessible LLM APIs or local models.

Out of scope: catalog modification, identifiers outside the frozen catalog, private-label reconstruction, real transactions, mandatory UI work, full-model training, multimodal systems, and infrastructure-heavy vector databases.

## Official Data

The frozen `Clothing_Shoes_and_Jewelry` catalog contains 50,000 products. Participant-visible fields are `parent_asin`, `title`, `features`, `description`, `price`, `categories`, `details`, `average_rating`, `rating_number`, and `store`. Only `parent_asin` is scored.

The public set has 200 labeled development sessions. The organizer keeps 800 sessions private. Private intent cards, ground truth, and simulator state are never sent to the participant Agent.

Direct user identifiers, purchase timestamps, free-text reviews, and raw purchase histories have been removed. The Agent sees only a safe aggregate `user_profile` with purchase-frequency and rating summaries plus controlled preference tags.

Both splits use the same fixed scenario mix:

- 40% Buying: a hard constraint is disclosed early.
- 40% Browsing: the customer begins vague.
- 15% Intent Override: an earlier preference is replaced on turn 3 or 4.
- 5% Boundary: the customer may have no preference for a requested attribute.

## Session Protocol

1. The evaluator creates a random `session_id` and calls `reset(session_id, user_profile)`.
2. The simulated customer sends a scenario-dependent first message.
3. The Agent returns natural `message`, structured `ask_attribute`, and ranked `recommendations`.
4. The evaluator scores the first 10 unique catalog-valid `parent_asin` values.
5. A target hit records rank and turn; otherwise the deterministic customer policy replies.
6. An Intent Override session cannot convert before the new intent is sent.
7. The session ends after a valid hit or turn 10.

The simulator policy decides what information to reveal. If natural-language paraphrasing is added by the organizer, it cannot decide correctness. Hits are always exact code matches.

## Required Agent Interface

```python
class Agent:
    def reset(self, session_id: str, user_profile: dict) -> None:
        pass

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "Do you have a material preference?",
            "ask_attribute": "material",
            "recommendations": [{"parent_asin": "B000..."}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30}
        }
```

Rules:

- `message` is customer-facing natural language.
- `ask_attribute` is one allowed attribute or `null`; the simulator uses this field instead of guessing from prose.
- Recommendations are ordered best to worst. Invalid and duplicate IDs are removed; only the first 10 valid unique IDs are scored.
- An optional numeric recommendation `score` is accepted but ignored.
- `usage` reports non-negative prompt and completion token counts. It is optional when no model is used.
- Exceptions, invalid output, and timeouts may count as a miss.

## Metrics

```text
HitRate@10 = successful sessions / N
MRR = sum(1 / target_rank, with misses equal to 0) / N
MTTC = sum(first_hit_turn, with misses assigned 11) / N
Efficiency = clip((11 - MTTC) / 10, 0, 1)
TechnicalScore = 0.50 × HitRate@10 + 0.30 × MRR + 0.20 × Efficiency
```

`TechnicalScore` is an objective input to the `Technical Execution` assessment. It is not a separate judging criterion and does not represent the entire `Technical Execution` score.

The same metrics are reported separately for Buying, Browsing, Intent Override, and Boundary sessions. Reported token use and latency are feasibility measures and do not change the core score.

## Innovation Directions

- Buying versus Browsing routing and multi-route retrieval
- hybrid retrieval and semantic reranking
- structured constraint state, intent override handling, and dynamic context construction
- adaptive clarification and question-value estimation
- safe personalization using the aggregate profile
- failure detection, strategy switching, low latency, and low token cost
- transparent recommendation explanations

## Recommended Product and Agent Design

This section defines the recommended implementation design for teams that want
to build a competitive agent. It is a design guide, not a change to the
official evaluator contract or scoring rules above.

### Design objective

The Agent should maintain a structured representation of the customer's
current intent, recommend products on every turn, and update ranking whenever
the customer adds, removes, or replaces a preference. The primary design
principles are:

- hard constraints must remain higher priority than preferences;
- user goals such as value, quality, comfort, durability, appearance,
  functionality, convenience, safety, and fit should work across product
  categories;
- ranking weights should adapt to what the customer emphasizes in the current
  conversation;
- a new explicit intent must replace conflicting old intent immediately;
- clarification and recommendation should happen in parallel when possible;
- the system should retain an offline, deterministic fallback.

### End-to-end workflow

```text
User message
  -> intent and attribute extraction
  -> constraint-state update
  -> scenario and strategy routing
  -> lexical and semantic candidate retrieval
  -> candidate fusion and structured reranking
  -> clarification-attribute selection
  -> valid Top-10 response
```

The workflow must run on every turn. The Agent should not wait until the end
of the conversation to produce recommendations because MTTC rewards early
hits.

### Conversation state

Each session should keep structured state rather than only concatenating the
raw conversation. A constraint record should include:

- `attribute`: category, material, color, size, brand, budget, feature,
  use_case, style, or another supported attribute;
- `value` and optional operator such as `under`, `at_least`, or `equals`;
- `constraint_level`: `hard`, `goal`, or `soft_preference`;
- `status`: `active`, `replaced`, `negated`, or `unconstrained`;
- source turn and confidence;
- whether the value was explicitly stated by the customer.

Example:

```json
{
  "category": {"value": "wireless headphones", "constraint_level": "hard", "status": "active"},
  "budget": {"value": 100, "operator": "under", "constraint_level": "hard", "status": "active"},
  "goal": {"value": "value", "constraint_level": "goal", "status": "active"},
  "feature": {"value": "long battery life", "constraint_level": "soft_preference", "status": "active"}
}
```

Hard constraints describe requirements that should normally be satisfied.
Goals describe what the customer is optimizing for. Soft preferences are
useful ranking signals but should not override either hard constraints or
explicit current goals.

### Constraint update and intent override

The Agent should process each new message in this order:

1. Extract explicit requirements, goals, negations, and uncertainty.
2. Identify whether the message adds to, relaxes, or replaces existing intent.
3. Mark conflicting old records as `replaced` or `negated`.
4. Add the new records as `active` with the current turn and confidence.
5. Rebuild the retrieval query and rerank from the catalog again.

Override signals include phrases such as “actually”, “instead”, “ignore my
earlier preference”, “change of plan”, “now I need”, and their equivalent
paraphrases. An override must not be handled by blindly appending all turns to
one query, because that would allow stale preferences to continue affecting
the result.

If the customer says they have no preference for an attribute, that attribute
must become `unconstrained`; it must not be converted into a positive or
negative product filter.

### Cross-category user-goal taxonomy

User goals should be represented independently from product category. The same
goal can be mapped to different catalog evidence depending on the category.

| Goal | Typical expressions | Evidence used for ranking |
|---|---|---|
| Value | good value, worth it, cost-effective | price, rating, review volume, feature match |
| Price sensitivity | cheap, affordable, limited budget | price and budget compliance |
| Quality | high quality, well-made, premium | rating, brand, material, product evidence |
| Durability | long-lasting, sturdy, durable | material, protective features, review evidence |
| Comfort | comfortable, easy to use, suitable for long use | comfort, ergonomics, weight, fit or usability |
| Appearance | stylish, attractive, minimalist, professional | color, design, style, brand, descriptive similarity |
| Functionality | powerful, waterproof, long battery, easy storage | explicit features, specifications, use-case evidence |
| Fit and compatibility | fits me, compatible, suitable for | size, dimensions, compatibility, intended users |
| Convenience | portable, easy to clean, simple to install | weight, maintenance, setup, handling evidence |
| Safety | stable, protective, safe | safety features, certifications, stability evidence |
| Personalization | matches my taste or previous preferences | aggregate profile and current preferences |

The goal vocabulary must be extensible. Product-specific evidence should be
configured as mappings to these generic goals rather than creating a separate
scoring system for every category.

### Dynamic ranking model

The recommended ranking model is:

```text
FinalScore(c, u, t) =
    w_hard      * HardConstraintScore(c, u)
  + w_category  * CategoryScore(c, u)
  + w_lexical   * LexicalScore(c, u)
  + w_semantic  * SemanticScore(c, u)
  + w_goal      * UserGoalScore(c, u, t)
  + w_profile   * ProfileScore(c, u)
  + w_quality   * QualityScore(c)
```

All component scores should be normalized to comparable ranges. The weights
should be non-negative and sum to one. `w_hard` must remain dominant whenever
the customer has explicit hard requirements. User goals should dynamically
change the middle of the ranking rather than override a hard constraint.

The goal score can be decomposed as:

```text
UserGoalScore =
    a_value         * ValueScore
  + a_quality       * QualityGoalScore
  + a_durability    * DurabilityScore
  + a_comfort       * ComfortScore
  + a_appearance    * AppearanceScore
  + a_functionality * FunctionalityScore
  + a_compatibility * CompatibilityScore
  + a_convenience   * ConvenienceScore
  + a_safety        * SafetyScore
```

Only goals detected in the current intent should receive material weight.
When the customer says “I want better value”, the Agent should increase
`ValueScore`, which combines affordability, rating, review volume, and match to
the requested functionality. It should not simply choose the cheapest item.

When a budget is explicit, budget compliance is a hard constraint. When only
“good value” is expressed, price remains a ranking signal and must be balanced
against quality and feature match.

Initial weights may be hand-designed, but they should be tuned on the public
set. The Agent should log the active goal and selected weight profile during
local development so changes can be analyzed by scenario.

### Retrieval and reranking

The recommended two-stage retrieval pipeline is:

1. Build a lexical index over `title`, `categories`, `features`, `details`,
   `description`, and `store`.
2. Generate a keyword/BM25 candidate set, for example Top 100.
3. Generate a semantic candidate set, for example Top 100, using a local or
   legally accessible model when available.
4. Merge and deduplicate the candidates.
5. Apply structured constraint and dynamic-goal reranking.
6. Return the first 10 valid unique `parent_asin` values.

Keyword retrieval is especially important for exact brands, colors, materials,
categories, prices, specifications, and product terms. Semantic retrieval is
useful for paraphrases and relationships such as “good for rainy conditions”
and “water-resistant outdoor use”.

Candidate lists can be fused with reciprocal-rank fusion or another normalized
combination of lexical rank and semantic similarity. Explicit constraint
matching should receive a larger influence than generic popularity or profile
signals.

### Scenario-specific behavior

- **Buying:** use disclosed hard constraints immediately, recommend on the
  first turn, and ask one high-value missing attribute.
- **Browsing:** begin with broad category and use-case retrieval, then narrow
  the candidate set as the customer provides information.
- **Intent Override:** archive conflicting old preferences, activate the new
  intent, and rebuild retrieval from the current state.
- **Boundary:** treat “no preference” as unconstrained and use other active
  requirements plus general relevance for ranking.

### Clarification policy

The Agent should choose at most one attribute per response through
`ask_attribute`. The question should target an attribute that is both missing
and likely to distinguish candidates. A useful heuristic is:

```text
QuestionValue(attribute) =
  expected candidate reduction
  * target-discrimination value
  * scenario relevance
  - answer cost
```

The natural-language question and `ask_attribute` must agree. Asking through
prose alone is insufficient because the simulator uses the structured field to
decide what information to reveal.

The Agent should stop asking about an attribute when the customer has already
provided it, explicitly has no preference for it, or repeated questioning is
unlikely to produce new information.

### Reliability and fallback

The recommended implementation uses a layered design:

```text
optional LLM extraction
  -> rule and pattern extraction fallback
  -> offline lexical retrieval
  -> optional semantic retrieval
  -> structured reranking
```

The system must still return a valid response if an optional model, network
service, or semantic index is unavailable. API credentials must remain in
environment variables and must never be committed. Teams must document model
choice, approximate cost, latency, token usage, and fallback behavior.

### Design acceptance criteria

An implementation based on this design should demonstrate that:

- every response contains valid, ordered, deduplicated catalog IDs;
- recommendations are produced from the current state on every turn;
- explicit hard constraints outrank soft goals and profile signals;
- value, quality, durability, comfort, appearance, functionality,
  compatibility, convenience, and safety can be applied across categories;
- a new preference replaces a conflicting old preference;
- a boundary response does not create an incorrect filter;
- the agent can run without an online model if a fallback is claimed;
- public-set evaluation reports overall and per-scenario HitRate@10, MRR, MTTC,
  efficiency, and reported token usage.

## Model and API Policy

Teams choose and manage their own model credentials. API keys must be passed through environment variables and never committed. Teams disclose model choice, approximate cost, token usage, latency, and any fallback behavior. The organizer does not need to issue a common API key.

## Final Deliverables

- Source code with setup and reproduction instructions
- A working Agent using the required interface
- A short report covering architecture, models, cost, limitations, and team contributions
- One demonstrated multi-turn session
