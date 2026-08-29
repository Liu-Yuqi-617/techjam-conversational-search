# Iteration 7–10 Validation and Release Record

Date: 2026-08-29 (SGT)  
Frozen runtime: Python 3.14.5, Python standard library, SQLite FTS5. The project has no third-party runtime dependency.

## Iteration 7: optional local LLM planner

`starter/llm.py` adds a narrowly scoped Ollama adapter. It is disabled by default and accepts only English JSON for intent, override, slots, and clarification planning. It has no catalog handle, never receives a target, and cannot create ASINs or recommendations. Temperature is `0`; the default HTTP timeout is `1.5` seconds.

Rules run first. A validated model result can fill an empty soft slot or resolve an otherwise ambiguous route, but cannot replace an explicit hard user constraint. Explicitly detected rule overrides remain authoritative. Timeout, service error, empty output, malformed JSON, and invalid schema return the same legal deterministic response within that turn. Per-turn token counts are reported only for that turn.

No local Ollama model was installed or measured in this environment, so an LLM-on public-set score is intentionally not claimed. The adapter is retained as an experiment-only, opt-in path; the final configuration keeps it off. Regression tests simulate model output and failures without a network call.

## Iteration 8: ablation and freeze

All runs use the frozen public set and current deterministic code. The generated result files are local ignored artifacts.

| Variant | HitRate@10 | MRR | MTTC | TechnicalScore | Decision |
|---|---:|---:|---:|---:|---|
| FTS5 + reranking + clarification, profile off, LLM off | 0.560000 | 0.400071 | 7.200000 | 0.476021 | retained |
| Same, profile soft weight `1` | 0.555000 | 0.369514 | 6.925000 | 0.469854 | rejected |
| Semantic retrieval | not run | not run | not run | not run | rejected: no reproducible local model |
| LLM on | not run | not run | not run | not run | not retained: no installed, measured Ollama model |
| Question-only (Iteration 5) | 0.000000 | 0.000000 | 11.000000 | 0.000000 | rejected |

The frozen choices are stored in `docs/final_config.json`: deterministic FTS5 retrieval, no semantic model, profile weight `0`, clarification through turn 7, and LLM disabled. Hard constraints always precede profile and model signals.

## Iteration 9: fault and compliance audit

The regression suite covers empty messages, isolated sessions, valid recommendations, Boundary states, explicit override, turn-8 clarification stop, model timeout/failure fallback, invalid-result isolation, token accounting, and evaluator normalization. The default path requires no network and no secret. No catalog, public labels, or evaluator code was changed.

Operational checks recorded during this run: cold index build was approximately 2.3 seconds on the local workstation; model-free token usage is zero. The local evaluator result reports valid catalog IDs, unique Top-10 output, and zero tokens. A real Ollama experiment must measure provider/model/version, P50/P95 latency, failure rate, tokens, resource use, and local hardware before it can be enabled.

## Iteration 10: reproducible final run

```powershell
python -m venv --clear .venv
.\.venv\bin\python.exe -m unittest discover -s tests -v
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.json
```

The MSYS2 Python available on this workstation creates `.venv/bin/python.exe`. A standard Windows CPython installation instead uses `.venv\Scripts\python.exe`; use the equivalent interpreter path. `py` is not installed on this workstation, so it is not a reproducible command here.

Final disclosure: **no LLM or embedding model enabled; no provider/model/version; zero token usage; zero model cost; no network requirement; deterministic rule fallback is the primary path.** Optional Ollama settings are documented in `.env.example`; never commit a real credential or enable it without a measured local model.
