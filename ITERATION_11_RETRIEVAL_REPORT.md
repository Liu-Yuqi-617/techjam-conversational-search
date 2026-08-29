# Retrieval and Override Follow-up Validation

Date: 2026-08-29 (SGT)

This follow-up tested the three agreed changes against the same frozen 200-session public set. The previous frozen score was `0.476021`.

| Variant | HitRate@10 | MRR | MTTC | TechnicalScore | Decision |
|---|---:|---:|---:|---:|---|
| Previous frozen baseline | 0.560000 | 0.400071 | 7.200000 | 0.476021 | reference |
| Preserve product class on attribute-only override | 0.575000 | 0.406877 | 7.125000 | 0.487063 | retained |
| Retained override fix + strict AND hard-constraint retrieval | 0.570000 | 0.362827 | 7.125000 | 0.471348 | reverted |

## Retained change: partial intent override

When a customer says, for example, “I need blue shoes” followed by “Actually, I need black instead,” the new code retains `shoes` as a soft inherited product class while replacing the explicitly changed colour. If the replacement message names a new category, that explicit category remains authoritative.

This improves the Intent Override scenario: HitRate@10 rises from `0.366667` to `0.466667`, MRR from `0.350000` to `0.395370`, and MTTC from `8.866667` to `8.366667`.

## Reverted changes: hard filter and strict-to-broad query

The strict variant ran an AND FTS query for all hard attributes, filtered candidate rows that did not contain every explicit value, and backfilled with broad candidates only when none survived. It slightly improved some override hits but sharply reduced MRR, especially in browsing, because catalog wording is incomplete and a literal filter discarded useful candidates. The strict filter and strict-to-broad code were removed after this result.

## Verification

```powershell
.\.venv\bin\python.exe -m unittest discover -s tests -v
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.json
```

The regression suite passes 17 tests after the strict-path rollback. No evaluator, catalog, public labels, or network dependency was changed.
