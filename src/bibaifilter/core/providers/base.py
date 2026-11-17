"""Common provider interface and the HTTP call with a bounded, logged retry policy.

Adapters talk to the providers' HTTP APIs directly (``httpx``), not through
vendor SDKs, so the request body that is logged is byte-for-byte what was sent
and an SDK upgrade cannot change behaviour silently.

Retry policy: only HTTP 408/409/429, 5xx and network/timeouts are retried, at
most ``max_attempts`` times in total, with exponential backoff and jitter, and
honouring ``Retry-After``. Any other error fails the call at once. Every attempt
is reported to the caller so it can be logged. A failed call never produces a
score.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


@dataclass
class CallSettings:
    """What the user asked for. ``None`` means "do not send; use the provider default"."""

    temperature: Optional[float] = None
    reasoning: Optional[str] = None  # e.g. "none" | "minimal" | "low" | "medium" | "high"
    max_output_tokens: Optional[int] = None
    structured: bool = True
    seed: Optional[int] = None
    timeout_s: float = 120.0
    max_attempts: int = 5


@dataclass
class PreparedRequest:
    url: str
    headers: dict[str, str]
    body: dict[str, Any]
    # What was actually put on the wire for the settings the user controls,
    # e.g. {"temperature": 0.2} or {"temperature": "not sent (unsupported)"}.
    params_sent: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    text: Optional[str]
    served_model: Optional[str] = None
    finish_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    request_id: Optional[str] = None
    system_fingerprint: Optional[str] = None
    raw: Optional[dict] = None


@dataclass
class Attempt:
    n: int
    started: float
    latency_s: float
    http_status: Optional[int]
    error: Optional[str]
    retry_after_s: Optional[float] = None


@dataclass
class CallOutcome:
    result: Optional[ProviderResult]
    attempts: list[Attempt]
    error: Optional[str] = None
    http_status: Optional[int] = None


class ProviderError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class Adapter:
    """Base class; one subclass per wire protocol."""

    provider: str = ""
    default_base_url: str = ""
    key_env: str = ""
    needs_key: bool = True

    def __init__(self, api_key: Optional[str], base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = (base_url or self.default_base_url).rstrip("/")

    # -- to implement -----------------------------------------------------
    def prepare(self, model: "Any", prompt: str, task: str, settings: CallSettings) -> PreparedRequest:
        raise NotImplementedError

    def parse(self, data: dict, headers: httpx.Headers) -> ProviderResult:
        raise NotImplementedError

    # -- shared -----------------------------------------------------------
    @staticmethod
    def redact(headers: dict[str, str]) -> dict[str, str]:
        out = {}
        for k, v in headers.items():
            if k.lower() in ("authorization", "x-api-key", "x-goog-api-key", "api-key"):
                out[k] = "***"
            else:
                out[k] = v
        return out


def _retry_after(resp: httpx.Response) -> Optional[float]:
    h = resp.headers.get("retry-after")
    if not h:
        return None
    try:
        return max(0.0, float(h))
    except ValueError:
        return None


async def send(client: httpx.AsyncClient, adapter: Adapter, req: PreparedRequest,
               settings: CallSettings, sleep=asyncio.sleep) -> CallOutcome:
    attempts: list[Attempt] = []
    last_err, last_status = None, None
    for n in range(1, max(1, settings.max_attempts) + 1):
        t0 = time.time()
        resp = None
        try:
            resp = await client.post(req.url, headers=req.headers, json=req.body, timeout=settings.timeout_s)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            attempts.append(Attempt(n, t0, time.time() - t0, None, f"{type(exc).__name__}: {exc}"))
            last_err, last_status = f"{type(exc).__name__}", None
            delay = None
        else:
            dt = time.time() - t0
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    attempts.append(Attempt(n, t0, dt, 200, "invalid JSON body"))
                    return CallOutcome(None, attempts, "invalid JSON body", 200)
                attempts.append(Attempt(n, t0, dt, 200, None))
                try:
                    result = adapter.parse(data, resp.headers)
                except Exception as exc:  # malformed provider payload
                    return CallOutcome(None, attempts, f"unexpected response shape: {exc}", 200)
                result.raw = data
                return CallOutcome(result, attempts)
            body = resp.text[:2000]
            ra = _retry_after(resp)
            attempts.append(Attempt(n, t0, dt, resp.status_code, body, ra))
            last_err, last_status = f"HTTP {resp.status_code}: {body}", resp.status_code
            if resp.status_code not in RETRYABLE_STATUS:
                return CallOutcome(None, attempts, last_err, last_status)
            delay = ra
        if n >= settings.max_attempts:
            break
        if delay is None:
            delay = min(60.0, 2.0 ** n) * (0.5 + random.random())
        await sleep(delay)
    return CallOutcome(None, attempts, last_err or "failed", last_status)
