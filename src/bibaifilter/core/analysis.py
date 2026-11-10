"""Run-level and multi-run analyses that the interface and the CLI report.

``analyze_run`` combines, for one run:
* call outcomes (counts by status, served models, mismatches, tokens, cost, time),
* stability across repetitions,
* agreement of record means with a numeric reference column (e.g. mean human
  rating), with the BM25 baseline computed on the same records next to it,
* screening performance against include/exclude labels, again with BM25.

``compare_runs`` reports pairwise Spearman correlations of record means and
flags runs with identical score vectors.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

import numpy as np

from . import metrics
from .bm25 import bm25_scores
from .parsing import VALID_STATUSES
from .runstore import RunStore


def _scores_by_record(store: RunStore) -> dict[int, list[Optional[float]]]:
    out: dict[int, list[Optional[float]]] = defaultdict(list)
    task = store.config.task
    for c in store.final_calls():
        if c["status"] == "skipped":
            continue
        if task == "score":
            out[c["rid"]].append(c["score"] if c["status"] in VALID_STATUSES else None)
        else:
            d = c.get("decision") if c["status"] in VALID_STATUSES else None
            # include = 1, uncertain = 0.5, exclude = 0 (for ranking and stability)
            out[c["rid"]].append(None if d is None else {"include": 1.0, "uncertain": 0.5, "exclude": 0.0}[d])
    return out


def analyze_run(store: RunStore, n_boot: int = 2000) -> dict:
    cfg = store.config
    records = store.records()
    calls = store.final_calls()
    counts = Counter(c["status"] for c in calls)
    served = Counter(c.get("served_model") for c in calls if c.get("served_model"))
    lat = [c["latency_s"] for c in calls if c.get("latency_s") is not None]
    costs = [c["cost_usd"] for c in calls if c.get("cost_usd") is not None]
    tok_in = sum(c.get("input_tokens") or 0 for c in calls)
    tok_out = sum(c.get("output_tokens") or 0 for c in calls)
    tok_reason = sum(c.get("reasoning_tokens") or 0 for c in calls)
    out: dict = {
        "run_id": store.run_id,
        "task": cfg.task,
        "outcomes": {
            "n_calls": len(calls),
            "by_status": dict(counts),
            "valid_share": (sum(counts[s] for s in VALID_STATUSES) / len(calls)) if calls else None,
            "served_models": dict(served),
            "model_mismatch_calls": sum(1 for c in calls if c.get("model_mismatch")),
            "retried_calls": sum(1 for c in calls if (c.get("n_attempts") or 0) > 1),
            "tokens": {"input": tok_in, "output": tok_out, "reasoning": tok_reason},
            "cost_usd": round(sum(costs), 6) if costs else None,
            "cost_complete": len(costs) == sum(1 for c in calls if c.get("input_tokens") is not None),
            "latency_median_s": float(np.median(lat)) if lat else None,
            "latency_p90_s": float(np.percentile(lat, 90)) if lat else None,
        },
    }
    sbr = _scores_by_record(store)
    out["stability"] = metrics.stability(sbr)
    means = metrics.record_means(sbr)
    order = [r.rid for r in records]
    model_vec = [means.get(rid) for rid in order]
    query = cfg.topic + ("\n" + cfg.criteria if cfg.criteria else "")
    bm = bm25_scores(records, query)

    ref = [r.reference_score for r in records]
    if sum(v is not None for v in ref) >= 3:
        out["reference_agreement"] = {
            "model": metrics.agreement(model_vec, ref, n_boot=n_boot),
            "bm25_baseline": metrics.agreement(bm, ref, n_boot=n_boot),
        }
    labels = [r.label for r in records]
    if sum(v is not None for v in labels) >= 2 and 0 < sum(v for v in labels if v is not None):
        if cfg.task == "score":
            pred = [None if m is None else int(m >= cfg.threshold) for m in model_vec]
        else:
            # recall-oriented: keep unless every valid repetition said exclude
            pred = [None if m is None else int(m > 0) for m in model_vec]
        out["screening"] = {
            "model_decision": metrics.confusion(pred, labels),
            "model_ranking": {"roc_auc": metrics.roc_auc(model_vec, labels),
                              **metrics.ranked_recall(model_vec, labels, tiebreak=bm, seed=cfg.seed)},
            "bm25_ranking": {"roc_auc": metrics.roc_auc(bm, labels),
                             **metrics.ranked_recall(bm, labels, seed=cfg.seed)},
            "n_labelled": sum(v is not None for v in labels),
            "n_relevant": sum(v for v in labels if v is not None),
        }
    return metrics.json_safe(out)


def compare_runs(stores: list[RunStore]) -> dict:
    vectors, names = {}, []
    for s in stores:
        recs = s.records()
        means = metrics.record_means(_scores_by_record(s))
        name = s.config.name if s.config.name not in vectors else f"{s.config.name} [{s.run_id}]"
        names.append(name)
        vectors[name] = [None if means.get(r.rid) is None else round(means[r.rid], 9) for r in recs]
    same_records = len({len(v) for v in vectors.values()}) == 1
    return metrics.json_safe({
        "runs": names,
        "same_record_count": same_records,
        "spearman_matrix": metrics.correlation_matrix(vectors) if same_records else None,
        "identical_vectors": metrics.identical_vectors(vectors) if same_records else [],
    })
