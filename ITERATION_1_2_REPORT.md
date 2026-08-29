# Iteration 1–2 Validation Record

Date: 2026-08-29 (SGT)  
Runtime: Python 3.14.5; Python standard library and SQLite FTS5 only. No model, network call, token usage, or external service is used.

## Scope and compliance

- Kept `evaluator/`, `data/public_set.jsonl`, and `data/catalog.jsonl` unchanged.
- Built the FTS5 index from the catalog at startup over title, categories, features, details, store, and description; retained price, rating, and review count for deterministic reranking.
- Retrieval uses a lexically ordered Top-120 candidate pool, hard budget filtering, field/category matching, rating and review-count signals, then a score/ASIN stable tie-break.
- Added isolated per-session state. Every supported slot carries `value`, `operator`, `level`, `status`, `source_turn`, `confidence`, and `explicit`. The active query is rebuilt from current slots rather than concatenating raw message history.
- `no preference for <attribute>` becomes `unconstrained`; `reset` replaces the full session state.

## Test evidence

Command:

```text
python -m unittest discover -s tests -v
```

Result: 6/6 passed. The added regression suite covers three English examples for each supported attribute and checks deterministic unique retrieval, budget operators, cumulative state, boundary handling, and reset isolation.

## Public-set evaluation

Command:

```text
python -m evaluator.local_evaluator --output results.iteration2.json
```

| Metric | Iteration 0 baseline | Iteration 1–2 |
|---|---:|---:|
| HitRate@10 | 0.125000 | 0.160000 |
| MRR | 0.068034 | 0.079185 |
| MTTC | 9.810000 | 9.485000 |
| Efficiency | 0.119000 | 0.151500 |
| TechnicalScore | 0.106710 | 0.134056 |

The generated evaluator artifact is `results.iteration2.json`; it contains the required overall and scenario metrics.

## Measured local performance

On the supplied 50,000-row catalog, the index build took 2.231 seconds. Twenty repeated structured retrieval calls averaged 43.793 ms with a P95 of 50.103 ms. These are local development measurements, not a hardware-independent guarantee.
