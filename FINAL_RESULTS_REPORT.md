# Final Public-Set Results Report

## Scope

This report records the two retained 200-session public-set evaluation
artifacts. The offline artifact is the reproducible submission baseline. The
Qwen artifact is an optional local-LLM experiment and is not the default
submission configuration.

## Result comparison

| Metric | Offline deterministic | Qwen3:1.7b literal supplement |
|---|---:|---:|
| Artifact | `results.offline_final.json` | `results.qwen3-1.7b.literal-supplement.200.json` |
| Sample count | 200 | 200 |
| HitRate@10 | 0.575000 | 0.620000 |
| MRR | 0.406877 | 0.387756 |
| MTTC | 7.125000 | 6.625000 |
| Efficiency | 0.387500 | 0.437500 |
| Technical Score | 0.487063 | 0.513827 |
| Prompt tokens | 0 | 261,780 |
| Completion tokens | 0 | 11,652 |
| Total tokens | 0 | 273,432 |
| Recorded LLM fallbacks | none | 1 `TimeoutError` |

The offline result has been re-run from the current checkout with the planner
explicitly disabled. Every summary metric and all 200 session records matched
`results.offline_final.json`.

## Artifact integrity

| Artifact | SHA-256 |
|---|---|
| `results.offline_final.json` | `3B86C02A4E3CC4B83D507C43E7803C8B9F6289ACC4D49D35476C2C412757FEB2` |
| `results.qwen3-1.7b.literal-supplement.200.json` | `6AA25F0F1B03F3199DB32073A33806B6A01C0A1789E7414A034880520BA903AF` |

## Reproduction

Use Python 3.10+ with the released `data/catalog.jsonl` and
`data/public_set.jsonl`. The verified catalog SHA-256 is
`DA979B05A68AF864CB0DCF9EE6A81C010C7E66A57978AD286C7A2E005FC69A67`.

```powershell
python -m venv --clear .venv
$env:SHOPPING_LLM_ENABLED='0'
.\.venv\bin\python.exe -m unittest discover -s tests -v
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.repro_offline_final.json
```

On a standard Windows CPython environment, use
`.\.venv\Scripts\python.exe` instead of `.\.venv\bin\python.exe`.

The optional LLM experiment requires Ollama and the same `qwen3:1.7b` model
build and runtime:

```powershell
$env:SHOPPING_LLM_ENABLED='1'
$env:SHOPPING_LLM_MODEL='qwen3:1.7b'
$env:OLLAMA_HOST='http://127.0.0.1:11434'
$env:SHOPPING_LLM_TIMEOUT_SECONDS='1.5'
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.qwen3-1.7b.literal-supplement.200.repro.json
```

Local LLM output can differ between Ollama runtime versions or model digests,
including at temperature zero. Record `ollama list`, the model digest, hardware,
and fallback count alongside any new LLM run. The stored LLM artifact was not
re-run during this verification.

## Submission note

The two raw JSON artifacts remain unchanged in the repository root. They are
intentionally ignored by Git as generated evaluation outputs; upload the exact
files named above with this report when the submission portal accepts result
artifacts.

## Team contributions

Add the team-member names and their specific responsibilities here before
final submission. The competition requires this disclosure, and no names or
attributions are inferred in this report.
