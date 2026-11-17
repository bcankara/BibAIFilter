# Changelog

## 1.0.0 — 2026-11

First release.

- Browser interface served by a local FastAPI server; `pip install` / `pipx install`, single `bibaifilter` command; Docker image.
- Two tasks: relevance score on a 1–7 scale for a topic, and eligibility screening against explicit criteria (include / exclude / uncertain with a reason).
- Per-call audit log (`calls.jsonl`): requested and served model, parameters actually sent, all HTTP attempts, finish reason, raw answer, parse status, tokens including reasoning tokens, latency, estimated cost, request id.
- Run manifest with tool, Python and package versions, configuration, prompt text and SHA-256, input file SHA-256.
- A failed, empty, truncated or unparsable answer gets **no score** but a status; out-of-range values are not clamped, the first number in a free-text answer is not taken, and no default value is ever written.
- The model is never substituted; the model named in each response is stored and mismatches are flagged.
- At most 5 attempts per call, only for HTTP 408/409/429/5xx and timeouts, honouring `Retry-After`.
- Temperature and reasoning settings are sent only where the model accepts them, and what was sent is logged; output-token limits sized for reasoning models.
- Structured output (JSON schema) for OpenAI, Anthropic, Gemini, OpenRouter and Ollama; JSON mode for DeepSeek.
- Providers: OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, Ollama, any OpenAI-compatible endpoint. Model catalogue with parameter rules and list prices (checked 2026-11-10).
- Analyses: stability across repetitions; agreement with a reference score (Spearman with exact permutation p, bootstrap CI, Kendall, MAE, bias, CCC, ICC(A,1)); screening metrics against labels (recall, precision, specificity, F1, ROC AUC, WSS@95, recall at 10/25/50 %); BM25 baseline; run comparison with identical-vector detection.
- Inputs: Excel, CSV/TSV (Scopus), RIS, BibTeX, Web of Science plain text; column-mapping guesses; optional label and reference-score columns.
- Cost estimate before a run, cost cap, resume after interruption, random record order per repetition with a recorded seed, bounded concurrency.
- Workspace folder chosen in Settings; results exported to a folder chosen per run.
- API keys are kept in the environment, the system keychain or a user-only file in the configuration folder; never in run files.
- Headless runs from a JSON spec (`bibaifilter run`), `analyze`, `baseline`, `models`, `check` commands.
