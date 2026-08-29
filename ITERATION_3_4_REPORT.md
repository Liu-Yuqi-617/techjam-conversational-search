# Iteration 3–4 Validation Record

Date: 2026-08-29 (SGT)  
Runtime: Python 3.14.5; Python standard library and SQLite FTS5 only. No model, network call, token usage, or external service is used.

## Scope and compliance

- Kept `evaluator/`, `data/public_set.jsonl`, and `data/catalog.jsonl` unchanged.
- Added a deterministic Buying/Browsing router using purchase/exploration language, known category, and active hard-constraint count. Every route still retrieves and returns recommendations on the first turn.
- Stored route and reason only in per-session debug state; customer-facing messages expose neither evaluation logic nor internal scores.
- Added explicit English override recognition for `actually`, `instead`, `change of plan`, `ignore earlier`, and `now I need`. Before extracting replacement values, active old slots are marked `replaced`, so query construction cannot retain stale values.
- Preserved Boundary behavior: an attribute declared to have no preference becomes `unconstrained`, is excluded from active query terms, and is never asked again.
- Added a single-attribute browsing refinement policy. It asks only an unanswered, constrained-capable field while continuing to return the ranked Top-K list; it stops asking after turn 7.

## Test evidence

Command:

```text
python -m unittest discover -s tests -v
```

Result: 10/10 passed. New regressions verify immediate Buying recommendation, Browsing recommendation plus one structured question, removal of stale slots after an explicit override at turn 3, and non-repetition after a Boundary response.

## Public-set evaluation

Command:

```text
python -m evaluator.local_evaluator --output results.iteration4.json
```

| Metric | Iteration 1–2 | Iteration 3–4 | Change |
|---|---:|---:|---:|
| HitRate@10 | 0.160000 | 0.515000 | +0.355000 |
| MRR | 0.079185 | 0.367405 | +0.288220 |
| MTTC | 9.485000 | 6.685000 | -2.800000 |
| Efficiency | 0.151500 | 0.431500 | +0.280000 |
| TechnicalScore | 0.134056 | 0.454021 | +0.319965 |

Per-scenario values from `results.iteration4.json`:

| Scenario | HitRate@10 | MRR | MTTC |
|---|---:|---:|---:|
| Buying | 0.525000 | 0.315580 | 6.325000 |
| Browsing | 0.612500 | 0.461265 | 5.875000 |
| Intent Override | 0.266667 | 0.266667 | 9.466667 |
| Boundary | 0.400000 | 0.333333 | 7.700000 |

The generated artifact is `results.iteration4.json`. The largest gain is in Browsing because structured clarification obtains a useful constraint while Top-10 recommendations remain available every turn. The next planned optimization should focus on Intent Override ranking, while preserving this offline deterministic fallback.
