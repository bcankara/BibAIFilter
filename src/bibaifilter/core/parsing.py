"""Turning a model response into a score or decision — without silent defaults.

Version 1 returned a default score of 4 when a response was empty or could not
be parsed, took the first integer anywhere in the text and mapped phrases such
as "very relevant" to numbers. None of that happens here. Every parse returns a
``status``; only ``ok`` and ``extracted`` carry a value, every other status
leaves the value empty (``None``) and is counted and exported.

Statuses
--------
ok           the response is exactly the expected value (structured JSON or a bare value)
extracted    the value was the only candidate in a longer text (valid, but flagged)
empty        the visible answer is empty
truncated    the answer was cut off by the output-token limit (finish reason "length")
refused      the provider blocked or refused the request (safety / content filter)
out_of_range a number was returned, but not on the 1–7 scale
ambiguous    more than one candidate value appears in the text
unparsable   no candidate value in the text
error        the call failed (network, HTTP or provider error) — set by the engine
skipped      the record has neither title nor abstract — set by the engine
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

VALID_STATUSES = ("ok", "extracted")
ALL_STATUSES = ("ok", "extracted", "empty", "truncated", "refused", "out_of_range",
                "ambiguous", "unparsable", "error", "skipped")
DECISIONS = ("include", "exclude", "uncertain")


@dataclass
class Parsed:
    status: str
    score: Optional[int] = None
    decision: Optional[str] = None
    reason: Optional[str] = None

    @property
    def valid(self) -> bool:
        return self.status in VALID_STATUSES


def _strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    return m.group(1).strip() if m else t


def _load_json(text: str) -> Optional[Any]:
    t = _strip_fences(text)
    if not t or t[0] not in "{[":
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


def parse_score(text: Optional[str], finish_reason: Optional[str] = None,
                scale: tuple[int, int] = (1, 7)) -> Parsed:
    lo, hi = scale
    t = (text or "").strip()
    if finish_reason in ("length", "max_tokens", "MAX_TOKENS", "max_output_tokens"):
        # A cut-off answer is never trusted, even if it happens to contain a digit.
        return Parsed("truncated")
    if finish_reason in ("content_filter", "SAFETY", "refusal", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"):
        return Parsed("refused")
    if not t:
        return Parsed("empty")

    obj = _load_json(t)
    if isinstance(obj, dict) and "score" in obj:
        try:
            val = float(obj["score"])
        except (TypeError, ValueError):
            return Parsed("unparsable")
        if not val.is_integer():
            return Parsed("out_of_range")
        v = int(val)
        if lo <= v <= hi:
            return Parsed("ok", score=v, reason=obj.get("reason"))
        return Parsed("out_of_range")

    bare = re.fullmatch(r"\**\s*(-?\d+(?:\.\d+)?)\s*\**\.?", _strip_fences(t))
    if bare:
        val = float(bare.group(1))
        if val.is_integer() and lo <= int(val) <= hi:
            return Parsed("ok", score=int(val))
        return Parsed("out_of_range")

    # Longer text: accept only when exactly one in-scale integer appears and no
    # other number does (e.g. "Score: 5"). Anything like "on a scale of 1 to 7, 5"
    # is ambiguous and is NOT resolved by picking the first number.
    numbers = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", t)
    if not numbers:
        return Parsed("unparsable")
    distinct = set(numbers)
    if len(distinct) == 1:
        val = float(numbers[0])
        if val.is_integer() and lo <= int(val) <= hi:
            return Parsed("extracted", score=int(val))
        return Parsed("out_of_range")
    return Parsed("ambiguous")


def parse_decision(text: Optional[str], finish_reason: Optional[str] = None) -> Parsed:
    t = (text or "").strip()
    if finish_reason in ("length", "max_tokens", "MAX_TOKENS", "max_output_tokens"):
        return Parsed("truncated")
    if finish_reason in ("content_filter", "SAFETY", "refusal", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"):
        return Parsed("refused")
    if not t:
        return Parsed("empty")
    obj = _load_json(t)
    if isinstance(obj, dict) and "decision" in obj:
        d = str(obj.get("decision", "")).strip().lower()
        if d in DECISIONS:
            return Parsed("ok", decision=d, reason=(obj.get("reason") or None))
        return Parsed("unparsable")
    low = t.lower()
    if low.strip(" .\"'*") in DECISIONS:
        return Parsed("ok", decision=low.strip(" .\"'*"))
    found = [d for d in DECISIONS if re.search(rf"\b{d}\b", low)]
    if len(found) == 1:
        return Parsed("extracted", decision=found[0], reason=t[:500])
    if len(found) > 1:
        return Parsed("ambiguous")
    return Parsed("unparsable")


# JSON schemas sent to providers that support structured output.
SCORE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6, 7]}},
    "required": ["score"],
    "additionalProperties": False,
}

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "reason": {"type": "string"},
    },
    "required": ["decision", "reason"],
    "additionalProperties": False,
}
