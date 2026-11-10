"""The run engine: records x repetitions -> provider calls -> parsed, logged results.

Rules (each answers a defect of version 1):

* No silent defaults: a failed or unparsable call has no score and a status.
* No model substitution: the requested model is always the one called; the
  model named in the provider's response is stored for every call and a
  mismatch is flagged.
* Parameters are logged as sent: a temperature that the model does not accept
  is not sent and is logged as such; if the API rejects a parameter, the call is
  repeated once without it and that is logged too.
* Bounded retries (see ``providers.base.send``), every attempt logged.
* Record order is shuffled per repetition with a recorded seed (optional), so
  position effects do not line up across repetitions.
* A run can be cancelled, resumed (errored calls are retried) and capped by
  estimated cost.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import asdict
from typing import Any, Callable, Optional

import httpx

from . import catalog
from .parsing import parse_decision, parse_score
from .prompts import fill, sha256
from .providers import make_adapter
from .providers.base import CallSettings, send
from .runstore import RunStore, utcnow

ProgressCb = Callable[[dict], None]


def call_order(n_records: int, repetitions: int, shuffle: bool, seed: int) -> list[tuple[int, int, int]]:
    """List of (repetition, order_index, record_index)."""
    out = []
    rng = random.Random(seed)
    for rep in range(1, repetitions + 1):
        idx = list(range(n_records))
        if shuffle:
            rng.shuffle(idx)
        out.extend((rep, pos, i) for pos, i in enumerate(idx))
    return out


def _param_rejected(error: Optional[str], name: str) -> bool:
    if not error:
        return False
    e = error.lower()
    return name in e and any(w in e for w in ("unsupported", "not supported", "does not support",
                                              "unrecognized", "unknown", "invalid", "not allowed",
                                              "deprecated", "cannot be used"))


class Engine:
    def __init__(self, store: RunStore, api_key: Optional[str], progress: Optional[ProgressCb] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None, sleep=asyncio.sleep):
        self.store = store
        self.cfg = store.config
        self.records = store.records()
        self.model = catalog.get(self.cfg.provider, self.cfg.model)
        self.adapter = make_adapter(self.cfg.provider, api_key, self.cfg.base_url)
        self.progress = progress or (lambda _: None)
        self.transport = transport
        self.sleep = sleep
        self.cancel_event = asyncio.Event()
        self.cost_total = 0.0
        self.cost_known = True

    # ------------------------------------------------------------------
    async def run(self) -> dict:
        cfg = self.cfg
        n = len(self.records)
        if cfg.max_records:
            n = min(n, cfg.max_records)
        plan = call_order(n, cfg.repetitions, cfg.shuffle, cfg.seed)
        done_ok = {r["call_id"] for r in self.store.calls() if r.get("status") != "error"}
        # cost already spent in a resumed run
        for r in self.store.final_calls():
            if r.get("cost_usd") is not None:
                self.cost_total += r["cost_usd"]
        todo = [p for p in plan if f"r{self.records[p[2]].rid}-k{p[0]}" not in done_ok]
        total = len(plan)
        state = {"status": "running", "total": total, "done": total - len(todo), "started_at": utcnow(),
                 "message": None}
        self.store.write_state(state)
        self.store.update_manifest(started_at=state["started_at"])
        self.progress(dict(state))

        sem = asyncio.Semaphore(max(1, cfg.concurrency))
        stop_reason: Optional[str] = None
        lock = asyncio.Lock()

        async with httpx.AsyncClient(transport=self.transport, http2=False) as client:

            async def worker(item: tuple[int, int, int]) -> None:
                nonlocal stop_reason
                if self.cancel_event.is_set():
                    return
                async with sem:
                    if self.cancel_event.is_set():
                        return
                    row = await self._one(client, *item)
                    self.store.append_call(row)
                    async with lock:
                        state["done"] += 1
                        if row.get("cost_usd") is not None:
                            self.cost_total += row["cost_usd"]
                        elif row["status"] != "skipped":
                            self.cost_known = False
                        state["cost_usd"] = round(self.cost_total, 6)
                        state["last"] = {k: row.get(k) for k in ("rid", "repetition", "status", "score", "decision")}
                        if cfg.max_cost_usd is not None and self.cost_total >= cfg.max_cost_usd:
                            stop_reason = f"cost cap of {cfg.max_cost_usd} USD reached"
                            self.cancel_event.set()
                        if row.get("status") == "error" and row.get("http_status") in (401, 403):
                            stop_reason = "authentication failed (HTTP %s)" % row["http_status"]
                            self.cancel_event.set()
                        self.store.write_state(state)
                        self.progress(dict(state))

            # Repetitions run in order; calls within a repetition run concurrently.
            for rep in range(1, cfg.repetitions + 1):
                batch = [p for p in todo if p[0] == rep]
                await asyncio.gather(*(worker(p) for p in batch))
                if self.cancel_event.is_set():
                    break

        counts = self.counts()
        if stop_reason:
            state["status"], state["message"] = "stopped", stop_reason
        elif self.cancel_event.is_set():
            state["status"], state["message"] = "cancelled", "cancelled by user"
        else:
            state["status"] = "completed"
        state["finished_at"] = utcnow()
        self.store.write_state(state)
        self.store.update_manifest(finished_at=state["finished_at"], counts=counts,
                                   cost_usd_estimate=round(self.cost_total, 6) if self.cost_known else None)
        self.progress(dict(state))
        return state

    def cancel(self) -> None:
        self.cancel_event.set()

    # ------------------------------------------------------------------
    async def _one(self, client: httpx.AsyncClient, rep: int, order_index: int, ridx: int) -> dict:
        cfg = self.cfg
        rec = self.records[ridx]
        call_id = f"r{rec.rid}-k{rep}"
        base = {
            "call_id": call_id, "rid": rec.rid, "repetition": rep, "order_index": order_index,
            "record_hash": rec.text_hash, "requested_model": cfg.model, "provider": cfg.provider,
            "started_at": utcnow(),
        }
        if rec.is_empty:
            return {**base, "status": "skipped", "score": None, "decision": None,
                    "error": "record has neither title nor abstract", "finished_at": utcnow()}

        prompt = fill(cfg.template, rec, cfg.topic, cfg.criteria)
        settings = CallSettings(**asdict(cfg.settings))
        req = self.adapter.prepare(self.model, prompt, cfg.task, settings)
        outcome = await send(client, self.adapter, req, settings, sleep=self.sleep)
        retried_without: list[str] = []

        # The API refused a sampling/reasoning parameter: repeat once without it.
        if outcome.result is None and outcome.http_status == 400:
            for pname in ("temperature", "seed", "top_p", "reasoning", "reasoning_effort"):
                if _param_rejected(outcome.error, pname):
                    if pname == "temperature":
                        settings.temperature = None
                    elif pname == "seed":
                        settings.seed = None
                    elif pname.startswith("reasoning"):
                        settings.reasoning = None
                    retried_without.append(pname)
            if retried_without:
                req2 = self.adapter.prepare(self.model, prompt, cfg.task, settings)
                for p in retried_without:
                    req2.params_sent[p] = f"not sent (rejected by API on first attempt)"
                outcome2 = await send(client, self.adapter, req2, settings, sleep=self.sleep)
                outcome2.attempts = outcome.attempts + outcome2.attempts
                outcome, req = outcome2, req2

        row = {
            **base,
            "prompt_sha256": sha256(prompt),
            "params_sent": req.params_sent,
            "retried_without": retried_without or None,
            "attempts": [asdict(a) for a in outcome.attempts],
            "n_attempts": len(outcome.attempts),
            "latency_s": round(sum(a.latency_s for a in outcome.attempts), 3),
            "http_status": outcome.http_status if outcome.result is None else 200,
        }
        if outcome.result is None:
            row.update(status="error", score=None, decision=None, error=outcome.error,
                       finished_at=utcnow())
            return row

        res = outcome.result
        parsed = (parse_score(res.text, res.finish_reason) if cfg.task == "score"
                  else parse_decision(res.text, res.finish_reason))
        cost = catalog.cost_usd(self.model, res.input_tokens, res.output_tokens, res.cached_tokens)
        served = res.served_model
        row.update(
            served_model=served,
            model_mismatch=bool(served) and not catalog.same_model(cfg.model, served),
            response_text=(res.text or "")[:4000],
            finish_reason=res.finish_reason,
            status=parsed.status,
            score=parsed.score,
            decision=parsed.decision,
            reason=parsed.reason,
            relevant=(None if parsed.score is None else parsed.score >= cfg.threshold) if cfg.task == "score"
            else (None if parsed.decision is None else parsed.decision != "exclude"),
            input_tokens=res.input_tokens,
            output_tokens=res.output_tokens,
            reasoning_tokens=res.reasoning_tokens,
            cached_tokens=res.cached_tokens,
            cost_usd=cost,
            request_id=res.request_id,
            system_fingerprint=res.system_fingerprint,
            finished_at=utcnow(),
        )
        return row

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.store.final_calls():
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out


async def check_model(provider: str, model_id: str, api_key: Optional[str], base_url: Optional[str] = None,
                      transport: Optional[httpx.AsyncBaseTransport] = None) -> dict[str, Any]:
    """Connection check. Reports; never changes the selected model."""
    from .records import Record

    model = catalog.get(provider, model_id)
    adapter = make_adapter(provider, api_key, base_url)
    rec = Record(rid=0, title="Effects of peer tutoring on reading comprehension in primary school",
                 abstract="A randomised trial of peer tutoring for reading in grade 3 classrooms.")
    from .prompts import SCORE_V2

    prompt = fill(SCORE_V2, rec, "education")
    settings = CallSettings(max_attempts=2, timeout_s=60)
    req = adapter.prepare(model, prompt, "score", settings)
    t0 = time.time()
    async with httpx.AsyncClient(transport=transport) as client:
        out = await send(client, adapter, req, settings)
    if out.result is None:
        return {"ok": False, "error": out.error, "http_status": out.http_status,
                "requested_model": model_id}
    parsed = parse_score(out.result.text, out.result.finish_reason)
    return {
        "ok": True, "requested_model": model_id, "served_model": out.result.served_model,
        "model_mismatch": bool(out.result.served_model) and not catalog.same_model(model_id, out.result.served_model),
        "answer": out.result.text, "parse_status": parsed.status, "score": parsed.score,
        "latency_s": round(time.time() - t0, 2), "params_sent": req.params_sent,
        "usage": {"input": out.result.input_tokens, "output": out.result.output_tokens,
                  "reasoning": out.result.reasoning_tokens},
    }
