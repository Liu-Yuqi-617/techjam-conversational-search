# TechJam Conversational Shopping Copilot

## Project overview

This project is a conversational shopping agent for the TechJam Conversational E-Commerce Search Challenge. Given an anonymized user profile and an English shopping message, the agent must recommend the hidden target product within ten turns. Every response may include a ranked Top-10 list, one clarification question, or both.

The default submission is an offline, deterministic system built with Python's standard library and SQLite FTS5. It indexes the local product catalog in memory, extracts conversational slots such as category, colour, material, budget, and use case, retrieves a bounded lexical candidate set, and deterministically reranks candidates. The agent also keeps per-session state, handles explicit intent overrides, and asks one candidate-informed clarification question when it is useful.

An optional local Ollama integration is available in `starter/llm.py`. It is disabled by default. When enabled, an LLM can assist only with dialogue planning: intent routing, soft slot completion, override detection, and clarification planning. It cannot access the catalog, hidden target, or generate ASINs. Invalid JSON, timeouts, unavailable services, and empty model responses immediately fall back to the offline rules.

### Current public-set result

The retained configuration was evaluated on the frozen 200-session public set.

| Metric | Result |
|---|---:|
| HitRate@10 | 0.575000 |
| MRR | 0.406877 |
| MTTC | 7.125000 |
| Technical Score | 0.487063 |
| Default model token usage | 0 |

The latest retained improvement preserves the previous product category as a soft hint when the user changes only an attribute, for example: `I need blue shoes` followed by `Actually, I need black instead.` The complete comparison is in [ITERATION_11_RETRIEVAL_REPORT.md](ITERATION_11_RETRIEVAL_REPORT.md).

## Setup and installation

### Prerequisites

- Python 3.10 or later
- The released catalog at `data/catalog.jsonl`
- The released public set at `data/public_set.jsonl`

The default agent has no third-party Python dependencies. It uses only the standard library and SQLite FTS5.

### Create a virtual environment

From the repository root:

```powershell
python -m venv --clear .venv
```

On this workstation, the MSYS2 Python virtual environment executable is:

```powershell
.\.venv\bin\python.exe
```

With a standard Windows CPython installation, use this equivalent path instead:

```powershell
.\.venv\Scripts\python.exe
```

### Prepare the catalog

Download `catalog.jsonl.gz` from the repository release, unpack it, and place it in `data/catalog.jsonl`. Validate it with the supplied `data/SHA256SUMS` file before running the evaluator.

```powershell
gzip -dk catalog.jsonl.gz
Move-Item catalog.jsonl data\catalog.jsonl
```

The catalog, public set, virtual environment, result files, and secrets are covered by `.gitignore` and should not be committed.

### Optional: install and enable a local LLM

The LLM path is an experiment, not a requirement. Install [Ollama](https://ollama.com/download), download a local model, and confirm that the Ollama service is available:

```powershell
ollama pull qwen3:1.7b
ollama list
```

If `ollama serve` reports that port `127.0.0.1:11434` is already in use, the service is normally already running; do not start a second instance.

Enable the optional planner only in the current PowerShell session:

```powershell
$env:SHOPPING_LLM_ENABLED='1'
$env:SHOPPING_LLM_MODEL='qwen3:1.7b'
$env:OLLAMA_HOST='http://127.0.0.1:11434'
$env:SHOPPING_LLM_TIMEOUT_SECONDS='0.5'
```

The timeout applies to each model request. For a slow local model, keep the timeout short so the agent can fall back to the deterministic path instead of delaying the full evaluation.

## Reproducing results

Run the regression suite:

```powershell
.\.venv\bin\python.exe -m unittest discover -s tests -v
```

Run the default offline public-set evaluation:

```powershell
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.json
```

The command writes the overall metrics, per-scenario metrics, per-session rankings, and token totals to `results.json`. Use a different filename to preserve separate experiments:

```powershell
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.offline_run1.json
```

To reproduce an LLM-on experiment after setting the Ollama environment variables above:

```powershell
.\.venv\bin\python.exe -m evaluator.local_evaluator --output results.llm_on.json
```

Compare the resulting `recommended_technical_score` against the default offline reference of `0.487063`. Only retain an LLM configuration if it produces a stable improvement and acceptable latency. The final frozen configuration is documented in [docs/final_config.json](docs/final_config.json).

## Limitations and future improvements

The current system is deliberately conservative and lexical-first. Its main limitations are:

- **Vocabulary mismatch:** FTS5 can miss a relevant product when the user and catalog use different wording. A locally reproducible embedding or reranking model could improve semantic matching, but it must be benchmarked with the same public set and retain an offline fallback.
- **Literal attribute extraction:** The deterministic slot dictionaries cover common shopping terms but not every synonym, brand spelling, size notation, or compound request. A broader normalization layer and carefully evaluated LLM-assisted extraction could improve recall.
- **Intent override ambiguity:** The retained category-preservation fix improves partial overrides, but more nuanced multi-constraint replacements still require stronger state interpretation.
- **LLM latency:** The optional LLM is called over a local HTTP service and may be slow on modest hardware. Given more time, we would gate calls to genuinely ambiguous turns, add model warm-up and latency instrumentation, and compare smaller models against the offline baseline.
- **No semantic model in the frozen submission:** No locally installed embedding/reranker was available for a reproducible experiment. A future version would precompute catalog embeddings locally, merge lexical and semantic candidates, and measure accuracy, memory use, P50/P95 latency, failure rate, tokens, and cost.

The project intentionally keeps the offline SQLite path as the required baseline. This makes the system deterministic, testable, cost-free, and usable when the network or an optional model service is unavailable.

## Repository layout

```text
starter/agent.py                  dialogue state, FTS5 retrieval, reranking, clarification
starter/state.py                  session and slot state
starter/llm.py                    optional Ollama JSON planner and safe fallback
evaluator/local_evaluator.py      local public-set simulator and scorer
tests/                            regression and evaluator tests
docs/final_config.json            frozen configuration
ITERATION_7_10_REPORT.md          LLM, freeze, and compliance record
ITERATION_11_RETRIEVAL_REPORT.md  retrieval and override experiment record
```

## Compliance

- Do not modify the evaluator, public labels, or catalog when reporting results.
- Do not commit the catalog, public set, result files, local virtual environment, credentials, or API keys.
- The default configuration has no network dependency, API key, model cost, or model token usage.
- If an optional LLM is enabled, record its provider, model/version, tokens, latency, resource usage, failure rate, network requirement, and estimated cost before retaining it.
- See [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md) for catalog provenance and redistribution requirements.
