# Iteration 5–6 Validation Record

Date: 2026-08-29 (SGT)  
Runtime used for this validation: Python 3.14.5, Python standard library, and SQLite FTS5. The submission remains compatible with the project requirement of Python 3.12+; rebuild the project virtual environment with Python 3.12 before final submission.

## Iteration 5: active clarification

- Kept the offline deterministic retrieval and recommendation-on-every-turn policy.
- Calculated attribute coverage from the live, structured-filtered FTS candidate pool. An unanswered attribute is eligible only if it occurs in at least 5% of candidates; the selected attribute is the one closest to a 50/50 split, with a deterministic answer-cost tie-break.
- Never asks an active, unconstrained, or previously asked attribute. The response contains at most one `ask_attribute` and continues returning ranked Top-10 recommendations.
- Stops clarification at turn 8 and later. This expands recommendation coverage instead of delaying a possible hit.
- Optimized candidate coverage calculation to use fixed-vocabulary membership rather than repeated regular-expression compilation, preserving the policy while avoiding an unnecessary per-candidate latency cost.

The required ablation was also run with the same agent forced to return a structured question but no recommendations. As expected from the scoring contract, it scored HitRate@10 `0.000000`, MRR `0.000000`, MTTC `11.000000`, and TechnicalScore `0.000000`, versus the retained recommendation-plus-question policy at `0.560000`, `0.400071`, `7.200000`, and `0.476021`. A question-only policy is therefore not retained: it withholds valid Top-10 recommendations, violates the PRD's recommendation-on-every-turn design, and delays first-hit scoring.

## Iteration 6: semantic retrieval gate

Iteration 6 was evaluated only after the Iteration 5 full-public-set result. The environment has no installed local embedding/reranker runtime (`sentence_transformers`, `scikit-learn`, and `numpy` are absent). No network model, API, vector database, or undeclared dependency was added: the competition rules permit the organizer to disable network access, and a model that was not locally measured would not be reproducible.

Therefore the semantic path is **rejected for this freeze** and the agent falls back to the verified Iteration 5 FTS5 + deterministic reranking path. This follows the PRD's required fallback rule: only retain a local or legally accessible semantic model after it demonstrates stable public-set improvement within latency and resource limits. The final model disclosure is: **no LLM, no embedding model, no network calls, zero tokens, zero model cost**.

To rerun the deferred semantic experiment in a later, separately declared environment: install a pinned local embedding/reranker package, precompute catalog representations offline, merge lexical and semantic Top-N candidates, measure memory/latency/failure rate, and compare the same public set. It must be discarded unless it improves the frozen baseline without losing offline fallback.

## Tests

```text
python -m unittest discover -s tests -v
```

Result: 11/11 passed. The new regression verifies candidate-pool-based clarification eligibility and the turn-8 stop condition, in addition to API, state, override, Boundary, deterministic retrieval, and evaluator tests.

## Full public-set evaluation

```text
python -m evaluator.local_evaluator --output results.iteration5.json
```

| Metric | Iteration 3–4 | Iteration 5 / frozen Iteration 6 fallback | Change |
|---|---:|---:|---:|
| HitRate@10 | 0.515000 | 0.560000 | +0.045000 |
| MRR | 0.367405 | 0.400071 | +0.032666 |
| MTTC | 6.685000 | 7.200000 | +0.515000 |
| Efficiency | 0.431500 | 0.380000 | -0.051500 |
| TechnicalScore | 0.454021 | 0.476021 | +0.022000 |

The retained configuration improves the official aggregate score, HitRate@10, and MRR; the MTTC regression is explicitly recorded rather than hidden. Per-scenario HitRate@10 improves for Buying (0.525000 to 0.537500), Browsing (0.612500 to 0.637500), Intent Override (0.266667 to 0.366667), and Boundary (0.400000 to 0.700000).

## Compliance

- `evaluator/`, frozen catalog, and public set were not modified.
- Recommendations remain catalog-valid, unique, ordered, and limited to Top 10.
- No private data, API key, external service, or model credential is used.
- The official interface always supplies a legal response, including when no optional semantic model is available.
