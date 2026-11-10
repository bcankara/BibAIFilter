"""BM25 lexical baseline — ranks records against the topic/criteria text offline.

A transparent, free baseline: an LLM ranking is only useful if it beats this
on the same records. Okapi BM25 with k1 = 1.5, b = 0.75 over title + abstract +
keywords, lower-cased word tokens, a small English stop-word list.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

from .records import Record

_STOP = set("""a an and are as at be by for from has have in into is it its of on or that the
their this to was were will with which we our these those using use based study paper""".split())
_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def bm25_scores(records: Sequence[Record], query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
    docs = [tokenize(" ".join([r.title, r.abstract, r.keywords])) for r in records]
    q = tokenize(query)
    if not docs or not q:
        return [0.0] * len(docs)
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1.0
    df = Counter()
    for d in docs:
        df.update(set(d))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in set(q)}
    out = []
    for d in docs:
        tf = Counter(d)
        dl = len(d)
        s = 0.0
        for t in q:
            f = tf.get(t, 0)
            if f:
                s += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
        out.append(s)
    return out
