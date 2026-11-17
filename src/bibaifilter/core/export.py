"""Excel and CSV exports of a run.

Sheets of ``results.xlsx``:

* ``Records``  – one row per record: original fields, mean score / majority
  decision over valid repetitions, SD, number of valid and failed calls,
  relevant flag, BM25 score.
* ``Calls``    – one row per call: repetition, position in the shuffled order,
  status (ok / extracted / truncated / empty / error ...), score or decision,
  requested and served model, mismatch flag, finish reason, tokens, latency,
  attempts, estimated cost, timestamps.
* ``Run``      – configuration, the parameters actually sent, counts by status,
  tool and environment versions, prompt and input hashes.
* ``Prompt``   – the template as used.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from .bm25 import bm25_scores
from .parsing import VALID_STATUSES
from .runstore import RunStore


def record_summary(store: RunStore) -> pd.DataFrame:
    cfg = store.config
    records = store.records()
    calls = store.final_calls()
    by_rid: dict[int, list[dict]] = defaultdict(list)
    for c in calls:
        by_rid[c["rid"]].append(c)
    query = cfg.topic + ("\n" + cfg.criteria if cfg.criteria else "")
    bm = bm25_scores(records, query)
    rows = []
    for rec, b in zip(records, bm):
        cs = by_rid.get(rec.rid, [])
        valid = [c for c in cs if c["status"] in VALID_STATUSES]
        row: dict[str, Any] = {
            "rid": rec.rid, "title": rec.title, "year": rec.year, "doi": rec.doi, "source": rec.source,
            "n_calls": len(cs), "n_valid": len(valid), "n_failed": len(cs) - len(valid),
            "statuses": ", ".join(f"{k}:{v}" for k, v in sorted(Counter(c["status"] for c in cs).items())),
        }
        if cfg.task == "score":
            vals = [c["score"] for c in valid]
            row["mean_score"] = float(np.mean(vals)) if vals else None
            row["sd_score"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else None
            row["min_score"] = min(vals) if vals else None
            row["max_score"] = max(vals) if vals else None
            row["relevant"] = (row["mean_score"] >= cfg.threshold) if vals else None
        else:
            dec = Counter(c["decision"] for c in valid)
            row["include"] = dec.get("include", 0)
            row["uncertain"] = dec.get("uncertain", 0)
            row["exclude"] = dec.get("exclude", 0)
            if valid:
                top = dec.most_common()
                row["majority_decision"] = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "tie"
                # recall-oriented rule: keep unless every valid repetition excluded
                row["keep_for_full_text"] = dec.get("exclude", 0) < len(valid)
            else:
                row["majority_decision"] = None
                row["keep_for_full_text"] = None
        row["bm25"] = round(b, 4)
        row["label"] = rec.label
        row["reference_score"] = rec.reference_score
        rows.append(row)
    return pd.DataFrame(rows)


def calls_frame(store: RunStore) -> pd.DataFrame:
    cols = ["call_id", "rid", "repetition", "order_index", "status", "score", "decision", "reason",
            "requested_model", "served_model", "model_mismatch", "finish_reason", "response_text",
            "input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens", "cost_usd",
            "latency_s", "n_attempts", "http_status", "error", "retried_without", "request_id",
            "system_fingerprint", "record_hash", "prompt_sha256", "started_at", "finished_at"]
    rows = []
    for c in store.final_calls():
        r = {k: c.get(k) for k in cols}
        if isinstance(r.get("retried_without"), list):
            r["retried_without"] = ", ".join(r["retried_without"])
        rows.append(r)
    return pd.DataFrame(rows, columns=cols)


def run_info(store: RunStore) -> pd.DataFrame:
    m = store.manifest
    cfg = dict(m.get("config", {}))
    settings = cfg.pop("settings", {})
    template = cfg.pop("template", "")
    calls = store.final_calls()
    params_sent = calls[0].get("params_sent") if calls else None
    served = sorted({c.get("served_model") for c in calls if c.get("served_model")})
    counts = Counter(c["status"] for c in calls)
    rows: list[tuple[str, Any]] = [
        ("Tool", f"BibAIFilter {m.get('tool', {}).get('version')}"),
        ("Run id", m.get("run_id")),
        ("Created (UTC)", m.get("created_at")),
        ("Started (UTC)", m.get("started_at")),
        ("Finished (UTC)", m.get("finished_at")),
        ("Status", store.state().get("status")),
    ]
    rows += [(f"Config: {k}", v) for k, v in cfg.items()]
    rows += [(f"Requested setting: {k}", v) for k, v in settings.items()]
    if params_sent:
        rows += [(f"Sent to API: {k}", json.dumps(v) if isinstance(v, (dict, list)) else v)
                 for k, v in params_sent.items()]
    rows += [("Served model(s)", ", ".join(served) or "not reported"),
             ("Calls with served-model mismatch", sum(1 for c in calls if c.get("model_mismatch")))]
    rows += [(f"Calls with status '{k}'", v) for k, v in sorted(counts.items())]
    rows += [("Estimated cost (USD)", m.get("cost_usd_estimate")),
             ("Prompt SHA-256", m.get("prompt_sha256")),
             ("Input file", cfg.get("input_file")), ("Input SHA-256", cfg.get("input_sha256")),
             ("Python", m.get("environment", {}).get("python")),
             ("Platform", m.get("environment", {}).get("platform")),
             ("Packages", json.dumps(m.get("environment", {}).get("packages")))]
    return pd.DataFrame(rows, columns=["Item", "Value"])


def write_excel(store: RunStore, path: Optional[Path] = None) -> Path:
    path = path or (store.dir / "results.xlsx")
    tmp = path.with_suffix(".tmp.xlsx")
    with pd.ExcelWriter(tmp, engine="openpyxl") as xw:
        record_summary(store).to_excel(xw, sheet_name="Records", index=False)
        calls_frame(store).to_excel(xw, sheet_name="Calls", index=False)
        run_info(store).to_excel(xw, sheet_name="Run", index=False)
        pd.DataFrame({"template": [store.config.template]}).to_excel(xw, sheet_name="Prompt", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = min(60, max(10, max(len(str(c.value or "")) for c in col[:200]) + 2))
                ws.column_dimensions[col[0].column_letter].width = width
            ws.freeze_panes = "A2"
    tmp.replace(path)
    return path


def write_csv(store: RunStore, path: Optional[Path] = None) -> Path:
    path = path or (store.dir / "calls.csv")
    calls_frame(store).to_csv(path, index=False)
    return path


def safe_name(name: str) -> str:
    import re

    s = re.sub(r"[^\w\-. ]+", "_", name, flags=re.UNICODE).strip(" ._")
    return (s or "run")[:80]


def export_run(store: RunStore, folder: Path) -> list[Path]:
    """Copy a run's results into a user-chosen folder.

    Writes ``<name>.xlsx`` (Records, Calls, Run, Prompt sheets), ``<name>_calls.csv``,
    ``<name>_calls.jsonl`` (full call log) and ``<name>_manifest.json``.
    """
    import shutil

    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    base = safe_name(store.config.name)
    out = [write_excel(store, folder / f"{base}.xlsx"), write_csv(store, folder / f"{base}_calls.csv")]
    for src, suffix in (("calls.jsonl", "_calls.jsonl"), ("manifest.json", "_manifest.json")):
        dst = folder / f"{base}{suffix}"
        shutil.copyfile(store.dir / src, dst)
        out.append(dst)
    store.update_manifest(export_dir=str(folder.resolve()))
    return out
