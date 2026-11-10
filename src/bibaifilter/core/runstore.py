"""On-disk layout of a run — everything needed to audit or repeat it.

``<data>/runs/<run_id>/``

* ``manifest.json`` – tool and environment versions, the full run configuration,
  prompt template and its SHA-256, input file name and SHA-256, model catalogue
  entry, start and end time (UTC), final counts.
* ``records.json``  – the normalised records exactly as they were sent.
* ``calls.jsonl``   – one JSON line per call: requested and served model,
  parameters actually sent, every HTTP attempt, finish reason, raw answer text,
  parse status, score/decision, tokens, latency, estimated cost.
* ``state.json``    – status and progress (for the UI and for resuming).
* ``results.xlsx``  – export built from the files above.

API keys never enter any of these files.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .. import __version__
from ..paths import runs_dir
from .providers.base import CallSettings
from .records import Record

_LOCK = threading.Lock()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class RunConfig:
    name: str
    task: str  # "score" | "eligibility"
    provider: str
    model: str
    template: str
    topic: str
    criteria: str = ""
    preset_id: Optional[str] = None
    base_url: Optional[str] = None
    settings: CallSettings = field(default_factory=CallSettings)
    repetitions: int = 1
    shuffle: bool = True  # new random record order in every repetition (seeded)
    seed: int = 20261110
    threshold: int = 4  # score >= threshold counts as relevant (score task)
    concurrency: int = 2
    max_cost_usd: Optional[float] = None
    max_records: Optional[int] = None
    dataset_id: Optional[str] = None
    input_file: Optional[str] = None
    input_sha256: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunConfig":
        d = dict(d)
        s = d.pop("settings", None) or {}
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(settings=CallSettings(**{k: v for k, v in s.items() if k in CallSettings.__dataclass_fields__}), **known)


class RunStore:
    def __init__(self, run_id: str, root: Optional[Path] = None):
        self.run_id = run_id
        self.dir = (root or runs_dir()) / run_id

    # -- creation ----------------------------------------------------------
    @classmethod
    def create(cls, run_id: str, config: RunConfig, records: list[Record],
               model_entry: Optional[dict] = None, root: Optional[Path] = None) -> "RunStore":
        store = cls(run_id, root)
        store.dir.mkdir(parents=True, exist_ok=False)
        from .prompts import sha256

        manifest = {
            "schema": "bibaifilter.run/1",
            "run_id": run_id,
            "created_at": utcnow(),
            "tool": {"name": "BibAIFilter", "version": __version__},
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "packages": _package_versions(),
            },
            "config": config.to_dict(),
            "prompt_sha256": sha256(config.template),
            "model_catalog_entry": model_entry,
            "n_records": len(records),
        }
        store._write_json("manifest.json", manifest)
        store._write_json("records.json", [r.to_dict() for r in records])
        store.write_state({"status": "created", "done": 0, "total": len(records) * config.repetitions})
        (store.dir / "calls.jsonl").touch()
        return store

    # -- io -------------------------------------------------------------------
    def _write_json(self, name: str, obj: Any) -> None:
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.dir / name)

    def _read_json(self, name: str, default: Any = None) -> Any:
        p = self.dir / name
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    @property
    def manifest(self) -> dict:
        return self._read_json("manifest.json", {})

    def update_manifest(self, **fields: Any) -> None:
        with _LOCK:
            m = self.manifest
            m.update(fields)
            self._write_json("manifest.json", m)

    @property
    def config(self) -> RunConfig:
        return RunConfig.from_dict(self.manifest["config"])

    def records(self) -> list[Record]:
        return [Record.from_dict(d) for d in self._read_json("records.json", [])]

    def state(self) -> dict:
        return self._read_json("state.json", {})

    def write_state(self, state: dict) -> None:
        with _LOCK:
            state = dict(state)
            state["updated_at"] = utcnow()
            self._write_json("state.json", state)

    def append_call(self, row: dict) -> None:
        line = json.dumps(row, ensure_ascii=False, default=str)
        with _LOCK:
            with open(self.dir / "calls.jsonl", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def calls(self) -> Iterator[dict]:
        p = self.dir / "calls.jsonl"
        if not p.exists():
            return
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def final_calls(self) -> list[dict]:
        """Last logged row per call id (a resumed run may have retried an errored call)."""
        latest: dict[str, dict] = {}
        for row in self.calls():
            latest[row["call_id"]] = row
        return sorted(latest.values(), key=lambda r: (r["repetition"], r["order_index"]))


def _package_versions() -> dict[str, str]:
    out = {}
    try:
        from importlib.metadata import version
    except ImportError:  # pragma: no cover
        return out
    for pkg in ("httpx", "pandas", "numpy", "scipy", "openpyxl", "fastapi"):
        try:
            out[pkg] = version(pkg)
        except Exception:
            pass
    return out


def list_runs(root: Optional[Path] = None) -> list[dict]:
    base = root or runs_dir()
    out = []
    for d in sorted(base.iterdir(), reverse=True) if base.exists() else []:
        if not (d / "manifest.json").exists():
            continue
        s = RunStore(d.name, base)
        m = s.manifest
        cfg = m.get("config", {})
        out.append({
            "run_id": d.name, "name": cfg.get("name"), "task": cfg.get("task"),
            "provider": cfg.get("provider"), "model": cfg.get("model"),
            "created_at": m.get("created_at"), "n_records": m.get("n_records"),
            "repetitions": cfg.get("repetitions"), "state": s.state(),
            "counts": m.get("counts"),
        })
    return out
