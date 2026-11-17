"""Analyses of runs: stability, agreement with a reference, screening performance.

All functions take plain Python/NumPy data so they can be used on any run,
including runs made with other tools. Nothing here calls a provider.

* Stability across repetitions of one run (between-repetition SD, number of
  records whose score varied, share of valid calls).
* Agreement with a numeric reference such as the mean human rating:
  Spearman's rho with an exact permutation p value for n <= 10 and a seeded
  bootstrap CI, Kendall's tau-b, MAE, mean bias, Lin's concordance correlation,
  ICC(A,1).
* Screening performance against include/exclude labels: confusion counts,
  recall, precision, specificity, F1, ROC AUC of the scores, WSS@95 and
  recall at fixed screening fractions.
* Run-to-run comparison, including detection of identical score vectors.
"""

from __future__ import annotations

import itertools
import math
from typing import Iterable, Optional, Sequence

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Stability


def stability(scores_by_record: dict[int, list[Optional[float]]]) -> dict:
    """``scores_by_record`` maps record id -> list of repetition scores (None = missing)."""
    sds, varied, n_valid, n_total = [], 0, 0, 0
    for vals in scores_by_record.values():
        v = [x for x in vals if x is not None]
        n_total += len(vals)
        n_valid += len(v)
        if len(v) >= 2:
            sd = float(np.std(v, ddof=1))
            sds.append(sd)
            if len(set(v)) > 1:
                varied += 1
    return {
        "n_records": len(scores_by_record),
        "n_calls": n_total,
        "n_valid": n_valid,
        "valid_share": (n_valid / n_total) if n_total else None,
        "mean_between_repetition_sd": float(np.mean(sds)) if sds else None,
        "max_between_repetition_sd": float(np.max(sds)) if sds else None,
        "n_records_with_variation": varied,
    }


def record_means(scores_by_record: dict[int, list[Optional[float]]]) -> dict[int, Optional[float]]:
    out = {}
    for rid, vals in scores_by_record.items():
        v = [x for x in vals if x is not None]
        out[rid] = float(np.mean(v)) if v else None
    return out


# ---------------------------------------------------------------------------
# Agreement with a numeric reference


def _paired(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None
             and not (isinstance(x, float) and math.isnan(x)) and not (isinstance(y, float) and math.isnan(y))]
    if not pairs:
        return np.array([]), np.array([])
    x, y = zip(*pairs)
    return np.asarray(x, float), np.asarray(y, float)


def spearman_exact_p(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    """Two-sided exact permutation p value of Spearman's rho (all n! orderings; n <= 10).

    Ties are handled by using mid-ranks; permuting y leaves both rank variances
    unchanged, so comparing |sum(rx_c * ry_c[perm])| is equivalent to comparing |rho|.
    """
    n = len(x)
    if n < 3 or n > 10:
        return None
    rx = stats.rankdata(x) - (n + 1) / 2
    ry = stats.rankdata(y) - (n + 1) / 2
    if not rx.any() or not ry.any():
        return None
    obs = abs(float(rx @ ry)) - 1e-9
    count = total = 0
    perms = itertools.permutations(range(n))
    while True:
        chunk = np.array(list(itertools.islice(perms, 200_000)), dtype=np.int8)
        if chunk.size == 0:
            break
        vals = np.abs(ry[chunk] @ rx)
        count += int((vals >= obs).sum())
        total += len(chunk)
    return count / total


def ccc(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if len(x) < 2:
        return None
    sxy = np.cov(x, y, ddof=1)[0, 1]
    den = np.var(x, ddof=1) + np.var(y, ddof=1) + (x.mean() - y.mean()) ** 2
    return float(2 * sxy / den) if den else None


def icc_a1(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    """ICC(A,1): two-way, absolute agreement, single measures (McGraw & Wong), two raters."""
    data = np.column_stack([x, y])
    n, k = data.shape
    if n < 2:
        return None
    grand = data.mean()
    ss_r = k * ((data.mean(axis=1) - grand) ** 2).sum()
    ss_c = n * ((data.mean(axis=0) - grand) ** 2).sum()
    ss_e = ((data - grand) ** 2).sum() - ss_r - ss_c
    msr, msc, mse = ss_r / (n - 1), ss_c / (k - 1), ss_e / ((n - 1) * (k - 1))
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / den) if den else None


def agreement(model: Sequence[Optional[float]], reference: Sequence[Optional[float]],
              n_boot: int = 2000, seed: int = 20261110) -> dict:
    x, y = _paired(model, reference)
    n = len(x)
    out: dict = {"n": n}
    if n < 3:
        return out
    rho = stats.spearmanr(x, y).statistic
    out["spearman_rho"] = None if np.isnan(rho) else float(rho)
    out["spearman_p_exact"] = spearman_exact_p(x, y)
    if out["spearman_p_exact"] is None:
        p = stats.spearmanr(x, y).pvalue
        out["spearman_p_asymptotic"] = None if np.isnan(p) else float(p)
    tau = stats.kendalltau(x, y).statistic
    out["kendall_tau_b"] = None if np.isnan(tau) else float(tau)
    out["mae"] = float(np.mean(np.abs(x - y)))
    out["mean_bias"] = float(np.mean(x - y))
    out["ccc"] = ccc(x, y)
    out["icc_a1"] = icc_a1(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if np.std(x[idx]) == 0 or np.std(y[idx]) == 0:
            continue
        boots.append(stats.spearmanr(x[idx], y[idx]).statistic)
    if len(boots) >= 100:
        out["spearman_ci95_percentile"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
        out["bootstrap_seed"] = seed
        out["bootstrap_resamples_used"] = len(boots)
    return out


# ---------------------------------------------------------------------------
# Screening performance against labels


def confusion(pred: Sequence[Optional[int]], labels: Sequence[Optional[int]]) -> dict:
    tp = fp = tn = fn = 0
    for p, l in zip(pred, labels):
        if p is None or l is None:
            continue
        if p and l:
            tp += 1
        elif p and not l:
            fp += 1
        elif not p and l:
            fn += 1
        else:
            tn += 1

    def div(a, b):
        return a / b if b else None

    recall = div(tp, tp + fn)
    precision = div(tp, tp + fp)
    f1 = (2 * recall * precision / (recall + precision)) if recall and precision else (0.0 if recall == 0 or precision == 0 else None)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "recall": recall, "precision": precision,
            "specificity": div(tn, tn + fp), "npv": div(tn, tn + fn), "f1": f1,
            "proportion_flagged": div(tp + fp, tp + fp + tn + fn)}


def roc_auc(scores: Sequence[Optional[float]], labels: Sequence[Optional[int]]) -> Optional[float]:
    s, l = _paired(scores, labels)
    pos, neg = s[l == 1], s[l == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def ranked_recall(scores: Sequence[Optional[float]], labels: Sequence[Optional[int]],
                  tiebreak: Optional[Sequence[float]] = None, seed: int = 0) -> dict:
    """Screen records in descending score order and report work saved.

    Ties are broken by ``tiebreak`` (e.g. BM25), then randomly with ``seed``;
    records without a score go last. WSS@r = (N - n_screened)/N - (1 - r).
    """
    labels = list(labels)
    n_all = len(labels)
    idx = [i for i in range(n_all) if labels[i] is not None]
    if not idx or sum(labels[i] for i in idx) == 0:
        return {}
    rng = np.random.default_rng(seed)
    noise = rng.random(n_all)
    tb = list(tiebreak) if tiebreak is not None else [0.0] * n_all

    def key(i):
        s = scores[i]
        return (0 if s is not None else 1, -(s if s is not None else 0), -tb[i], noise[i])

    order = sorted(idx, key=key)
    n = len(order)
    n_pos = sum(labels[i] for i in order)
    found, curve, out = 0, [], {}
    targets = {0.95: None, 1.0: None}
    for k, i in enumerate(order, start=1):
        found += labels[i]
        curve.append(found / n_pos)
        for r in targets:
            if targets[r] is None and found / n_pos >= r - 1e-12:
                targets[r] = k
    for r, k in targets.items():
        tag = "95" if r == 0.95 else "100"
        out[f"screened_for_recall_{tag}"] = k
        out[f"wss_{tag}"] = ((n - k) / n - (1 - r)) if k else None
    for frac in (0.1, 0.25, 0.5):
        k = max(1, int(round(frac * n)))
        out[f"recall_at_{int(frac * 100)}pct"] = curve[k - 1]
    out["n"] = n
    out["n_relevant"] = n_pos
    out["recall_curve"] = curve
    return out


# ---------------------------------------------------------------------------
# Run-to-run comparison


def identical_vectors(vectors: dict[str, Sequence[Optional[float]]], tol: float = 1e-9) -> list[tuple[str, str]]:
    """Pairs of runs whose per-record vectors are identical (same records, same values)."""
    names = list(vectors)
    pairs = []
    for a, b in itertools.combinations(names, 2):
        va, vb = vectors[a], vectors[b]
        if len(va) != len(vb):
            continue
        if all((x is None and y is None) or (x is not None and y is not None and abs(x - y) <= tol)
               for x, y in zip(va, vb)):
            pairs.append((a, b))
    return pairs


def correlation_matrix(vectors: dict[str, Sequence[Optional[float]]]) -> dict[str, dict[str, Optional[float]]]:
    out: dict[str, dict[str, Optional[float]]] = {}
    for a in vectors:
        out[a] = {}
        for b in vectors:
            x, y = _paired(vectors[a], vectors[b])
            if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
                out[a][b] = None
            else:
                out[a][b] = float(stats.spearmanr(x, y).statistic)
    return out


def safe(values: Iterable) -> list:
    """JSON-safe copy (NaN -> None)."""
    return [None if (isinstance(v, float) and math.isnan(v)) else v for v in values]


def json_safe(obj):
    """Recursively replace NaN/inf and NumPy scalars so the result is valid JSON."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj
