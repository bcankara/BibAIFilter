# Changelog

## 2.0.0 “Lantern” — 2026-11

Complete rewrite as a local web application. Version 1.x is kept on the `v1` branch.

### Added
- Browser interface served by a local FastAPI server; `pip install` / `pipx install`, single `bibaifilter` command; Docker image.
- Eligibility screening task (include / exclude / uncertain with a reason) next to the 1–7 relevance score.
- Per-call audit log (`calls.jsonl`): requested and served model, parameters actually sent, all HTTP attempts, finish reason, raw answer, parse status, tokens including reasoning tokens, latency, estimated cost, request id.
- Run manifest with tool, Python and package versions, configuration, prompt text and SHA-256, input file SHA-256.
- Structured output (JSON schema) for OpenAI, Anthropic, Gemini, OpenRouter and Ollama; JSON mode for DeepSeek.
- Providers: OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, Ollama, any OpenAI-compatible endpoint. Model catalogue with parameter rules and list prices (checked 2026-11-10).
- Analyses: stability across repetitions; agreement with a reference score (Spearman with exact permutation p, bootstrap CI, Kendall, MAE, bias, CCC, ICC(A,1)); screening metrics against labels (recall, precision, specificity, F1, ROC AUC, WSS@95, recall at 10/25/50 %); BM25 baseline; run comparison with identical-vector detection.
- Inputs: Excel, CSV/TSV (Scopus), RIS, BibTeX, Web of Science plain text; column-mapping guesses; optional label and reference-score columns.
- Cost estimate before a run, cost cap, resume after interruption, random record order per repetition with a recorded seed, bounded concurrency.
- Workspace folder chosen in Settings; results exported to a folder chosen per run.
- Headless runs from a JSON spec (`bibaifilter run`), `analyze`, `baseline`, `models`, `check` commands.

### Changed (behaviour that differs from 1.x)
- A failed, empty, truncated or unparsable answer has **no score** and a status. 1.x wrote 4 without a flag.
- The model is **never substituted**. 1.x could switch to another model of the same provider during the connection test or after a model-not-found error.
- Out-of-range values are not clamped; the first number in a free-text answer is not taken; phrases are not mapped to numbers.
- At most 5 attempts per call, only for HTTP 408/409/429/5xx and timeouts, honouring `Retry-After`. 1.x retried most errors without limit.
- Temperature and reasoning settings are sent only where the model accepts them, and what was sent is logged. 1.x recorded the configured temperature whether or not it was sent.
- Output-token limits sized for reasoning models (limits include reasoning tokens). 1.x used 10–20 tokens (1,024 for deepseek-reasoner).
- API keys are kept in the environment, the system keychain or a user-only file in the configuration folder; never in run files.

### Removed
- PyQt5 desktop interface (see branch `v1`).

## 1.x

See the `v1` branch: v1.0.0 (2025-04-22), v1.1.0 (2025-07-21) and the April 2026 release (2026-04-19).
