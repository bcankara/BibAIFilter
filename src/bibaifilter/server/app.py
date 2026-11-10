"""FastAPI application: JSON API under ``/api`` and the static web interface.

The server is meant to run on the user's own machine (``bibaifilter`` binds to
127.0.0.1). Requests whose Host is not local are rejected, and state-changing
requests from another origin are refused, so that a web page in the browser
cannot drive the local API.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .. import __codename__, __version__, keys
from ..core import analysis, catalog
from ..core.engine import Engine, check_model
from ..core.export import export_run, record_summary, safe_name, write_csv, write_excel
from ..core.prompts import PRESETS, sha256
from ..core.providers import PROVIDER_INFO
from ..core.providers.base import CallSettings
from ..core.records import FIELDS, Record, file_sha256, load_any, records_from_frame
from ..core.runstore import RunConfig, RunStore, list_runs
from ..paths import data_home, datasets_dir, default_workspace, exports_dir, runs_dir, set_workspace, workspace_source

WEB_DIR = Path(__file__).resolve().parent.parent / "_web"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"}

app = FastAPI(title="BibAIFilter", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
ENGINES: dict[str, Engine] = {}
TASKS: dict[str, asyncio.Task] = {}


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    if host not in LOCAL_HOSTS and not app.state.__dict__.get("allow_remote"):
        return JSONResponse({"detail": "BibAIFilter only accepts local connections"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin:
            o_host = origin.split("://", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0]
            if o_host not in LOCAL_HOSTS:
                return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
    return await call_next(request)


# --------------------------------------------------------------------------
# Info, keys, catalogue


@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "codename": __codename__, "data_dir": str(data_home())}


@app.get("/api/providers")
def providers():
    st = keys.status()
    return [{"id": p, **info, "key": st.get(p)} for p, info in PROVIDER_INFO.items()]


class KeyIn(BaseModel):
    key: str


@app.put("/api/keys/{provider}")
def put_key(provider: str, body: KeyIn):
    if provider not in PROVIDER_INFO:
        raise HTTPException(404, "unknown provider")
    if not body.key.strip():
        raise HTTPException(400, "empty key")
    where = keys.set_key(provider, body.key.strip())
    return {"stored_in": where}


@app.delete("/api/keys/{provider}")
def del_key(provider: str):
    keys.delete_key(provider)
    return {"ok": True}


@app.get("/api/catalog")
def get_catalog():
    return {"date": catalog.CATALOG_DATE, "models": [m.to_dict() for m in catalog.MODELS]}


class WorkspaceIn(BaseModel):
    path: Optional[str] = None


@app.get("/api/workspace")
def get_workspace():
    return {"path": str(data_home()), "source": workspace_source(), "default": str(default_workspace()),
            "exports": str(exports_dir())}


@app.put("/api/workspace")
def put_workspace(body: WorkspaceIn):
    if any(ENGINES):
        raise HTTPException(409, "stop running runs before changing the workspace")
    try:
        p = set_workspace(body.path)
    except OSError as exc:
        raise HTTPException(400, f"cannot use this folder: {exc}")
    return {"path": str(p), "source": workspace_source()}


@app.get("/api/fs/list")
def fs_list(path: Optional[str] = None):
    """Sub-folders of a folder, for the folder picker (local use only)."""
    base = Path(path).expanduser() if path else Path.home()
    try:
        base = base.resolve()
        dirs = sorted((d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")), key=str.lower)
    except OSError as exc:
        raise HTTPException(400, f"cannot open {base}: {exc}")
    roots = []
    if os.name == "nt":
        roots = [f"{c}:\\" for c in "CDEFGHIJ" if Path(f"{c}:\\").exists()]
    return {"path": str(base), "parent": str(base.parent) if base.parent != base else None,
            "dirs": dirs[:500], "home": str(Path.home()), "roots": roots}


class MkdirIn(BaseModel):
    path: str


@app.post("/api/fs/mkdir")
def fs_mkdir(body: MkdirIn):
    p = Path(body.path).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(400, str(exc))
    return {"path": str(p.resolve())}


def _prompts_file() -> Path:
    return data_home() / "prompts.json"


def _saved_prompts() -> list[dict]:
    f = _prompts_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except (OSError, ValueError):
        return []


@app.get("/api/presets")
def presets():
    """Built-in templates followed by the user's saved templates."""
    built_in = [{**p.__dict__, "builtin": True} for p in PRESETS.values()]
    return built_in + [{**p, "builtin": False} for p in _saved_prompts()]


class PromptIn(BaseModel):
    label: str
    task: str = "score"
    template: str
    description: str = ""


@app.post("/api/prompts")
def save_prompt(body: PromptIn):
    if body.task not in ("score", "eligibility"):
        raise HTTPException(400, "task must be 'score' or 'eligibility'")
    if "{TITLE}" not in body.template and "{ABSTRACT}" not in body.template:
        raise HTTPException(400, "the template must contain {TITLE} or {ABSTRACT}")
    items = [p for p in _saved_prompts() if p["label"] != body.label.strip()]
    item = {"id": "user-" + sha256(body.label.strip())[:10], "label": body.label.strip(), "task": body.task,
            "template": body.template, "description": body.description or "Saved template",
            "sha256": sha256(body.template), "saved_at": datetime.now().isoformat(timespec="seconds")}
    items.append(item)
    _prompts_file().write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return item


@app.delete("/api/prompts/{prompt_id}")
def delete_prompt(prompt_id: str):
    items = [p for p in _saved_prompts() if p["id"] != prompt_id]
    _prompts_file().write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True}


class PreviewIn(BaseModel):
    dataset_id: str
    mapping: Optional[dict[str, Optional[str]]] = None
    task: str = "score"
    template: str
    topic: str = ""
    criteria: str = ""
    provider: str = "openai"
    model: str = ""
    record_index: int = 0
    settings: Optional["SettingsIn"] = None


@app.post("/api/preview")
def preview(body: PreviewIn):
    """The exact request that the first call of the run would send (key removed)."""
    from ..core.prompts import fill, used_placeholders
    from ..core.providers import make_adapter

    mapping = body.mapping or _dataset_meta(body.dataset_id)["mapping"]
    recs = _records_for(body.dataset_id, mapping)
    if not recs:
        raise HTTPException(400, "the dataset has no records")
    rec = recs[max(0, min(body.record_index, len(recs) - 1))]
    prompt = fill(body.template, rec, body.topic, body.criteria)
    spec = catalog.get(body.provider, body.model or "unknown")
    settings = CallSettings(**(body.settings.model_dump() if body.settings else {}))
    catalog.apply_defaults(spec, settings)
    req = make_adapter(body.provider, "KEY", None).prepare(spec, prompt, body.task, settings)
    return {"record": rec.to_dict(), "prompt": prompt, "prompt_sha256": sha256(body.template),
            "placeholders": used_placeholders(body.template), "request_body": req.body,
            "params_sent": req.params_sent}


class CheckIn(BaseModel):
    provider: str
    model: str
    base_url: Optional[str] = None


@app.post("/api/check")
async def check(body: CheckIn):
    key, _ = keys.get_key(body.provider)
    return await check_model(body.provider, body.model, key, body.base_url)


# --------------------------------------------------------------------------
# Datasets


def _dataset_dir(ds_id: str) -> Path:
    d = datasets_dir() / ds_id
    if not d.is_dir() or "/" in ds_id or ".." in ds_id:
        raise HTTPException(404, "dataset not found")
    return d


def _dataset_meta(ds_id: str) -> dict:
    return json.loads((_dataset_dir(ds_id) / "meta.json").read_text(encoding="utf-8"))


@app.post("/api/datasets")
async def upload_dataset(file: UploadFile = File(...)):
    ds_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = datasets_dir() / ds_id
    d.mkdir(parents=True)
    name = Path(file.filename or "upload").name
    target = d / name
    with open(target, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        df, mapping, fmt = load_any(target)
    except Exception as exc:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(400, f"could not read the file: {exc}")
    meta = {"id": ds_id, "file": name, "sha256": file_sha256(target), "format": fmt,
            "columns": list(df.columns), "n_rows": len(df), "mapping": mapping,
            "uploaded_at": datetime.now().isoformat(timespec="seconds")}
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    head = df.head(5)
    preview = [{k: ("" if pd.isna(v) else str(v)) for k, v in row.items()} for row in head.to_dict(orient="records")]
    return {**meta, "preview": preview}


@app.get("/api/datasets")
def datasets():
    out = []
    for d in sorted(datasets_dir().iterdir(), reverse=True):
        if (d / "meta.json").exists():
            out.append(json.loads((d / "meta.json").read_text(encoding="utf-8")))
    return out


class MappingIn(BaseModel):
    mapping: dict[str, Optional[str]]


def _records_for(ds_id: str, mapping: dict[str, Optional[str]]) -> list[Record]:
    meta = _dataset_meta(ds_id)
    df, _, _ = load_any(_dataset_dir(ds_id) / meta["file"])
    return records_from_frame(df, mapping)


@app.post("/api/datasets/{ds_id}/mapping")
def apply_mapping(ds_id: str, body: MappingIn):
    recs = _records_for(ds_id, body.mapping)
    meta = _dataset_meta(ds_id)
    meta["mapping"] = body.mapping
    (_dataset_dir(ds_id) / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {
        "n_records": len(recs),
        "n_empty": sum(r.is_empty for r in recs),
        "n_without_abstract": sum(1 for r in recs if not r.abstract.strip()),
        "n_labelled": sum(r.label is not None for r in recs),
        "n_label_include": sum(1 for r in recs if r.label == 1),
        "n_reference": sum(r.reference_score is not None for r in recs),
        "preview": [r.to_dict() for r in recs[:5]],
    }


# --------------------------------------------------------------------------
# Runs


class SettingsIn(BaseModel):
    temperature: Optional[float] = 0.0  # the most deterministic value; not sent where unsupported
    reasoning: Optional[str] = None
    max_output_tokens: Optional[int] = None
    structured: bool = True
    seed: Optional[int] = None
    timeout_s: float = 120.0
    max_attempts: int = 5


PreviewIn.model_rebuild()


class RunIn(BaseModel):
    name: str = ""
    dataset_id: str
    mapping: Optional[dict[str, Optional[str]]] = None
    task: str = "score"
    preset_id: Optional[str] = "score-v2"
    template: str
    topic: str
    criteria: str = ""
    provider: str
    model: str
    base_url: Optional[str] = None
    settings: SettingsIn = Field(default_factory=SettingsIn)
    repetitions: int = 1
    shuffle: bool = True
    seed: int = 20261110
    threshold: int = 4
    concurrency: int = 2
    max_cost_usd: Optional[float] = None
    max_records: Optional[int] = None
    output_dir: Optional[str] = None  # where results are copied when the run ends


def _estimate(body: RunIn, recs: list[Record]) -> dict:
    from ..core.prompts import fill

    n = min(len(recs), body.max_records) if body.max_records else len(recs)
    sample = recs[: min(n, 50)] or [Record(rid=0)]
    chars = [len(fill(body.template, r, body.topic, body.criteria)) for r in sample]
    in_tok = (sum(chars) / len(chars)) / 4.0  # ~4 characters per token for English text
    spec = catalog.get(body.provider, body.model)
    eff = body.settings.reasoning or spec.recommended_reasoning
    out_tok = 20 if not spec.reasoning_style or eff in ("none", "minimal") else 600
    calls = n * body.repetitions
    cost = None
    if spec.price_in is not None and spec.price_out is not None:
        cost = calls * (in_tok * spec.price_in + out_tok * spec.price_out) / 1e6
    return {"n_records": n, "n_calls": calls, "input_tokens_per_call": round(in_tok),
            "output_tokens_per_call_assumed": out_tok, "cost_usd_estimate": None if cost is None else round(cost, 4),
            "price_known": cost is not None, "catalog_date": catalog.CATALOG_DATE,
            "note": "Rough estimate: 4 characters per token; reasoning models may use far more output tokens."}


@app.post("/api/estimate")
def estimate(body: RunIn):
    mapping = body.mapping or _dataset_meta(body.dataset_id)["mapping"]
    return _estimate(body, _records_for(body.dataset_id, mapping))


async def _start(store: RunStore) -> None:
    cfg = store.config
    key, _ = keys.get_key(cfg.provider)
    eng = Engine(store, key)
    ENGINES[store.run_id] = eng

    async def runner():
        try:
            await eng.run()
            write_excel(store)
            target = store.manifest.get("output_dir")
            if target:
                export_run(store, Path(target))
        except Exception as exc:  # surfaced in state.json
            st = store.state()
            st.update(status="failed", message=f"{type(exc).__name__}: {exc}")
            store.write_state(st)
        finally:
            ENGINES.pop(store.run_id, None)

    TASKS[store.run_id] = asyncio.create_task(runner())


@app.post("/api/runs")
async def create_run(body: RunIn):
    if body.task not in ("score", "eligibility"):
        raise HTTPException(400, "task must be 'score' or 'eligibility'")
    if body.task == "eligibility" and not body.criteria.strip():
        raise HTTPException(400, "eligibility screening needs criteria")
    if body.provider not in PROVIDER_INFO:
        raise HTTPException(400, "unknown provider")
    key, _ = keys.get_key(body.provider)
    if not key and body.provider not in ("ollama", "custom"):
        raise HTTPException(400, f"no API key set for {body.provider}")
    meta = _dataset_meta(body.dataset_id)
    mapping = body.mapping or meta["mapping"]
    recs = _records_for(body.dataset_id, mapping)
    if body.max_records:
        recs = recs[: body.max_records]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    settings = CallSettings(**body.settings.model_dump())
    catalog.apply_defaults(catalog.get(body.provider, body.model), settings)
    cfg = RunConfig(
        name=body.name or f"{body.model} · {body.topic[:40]}", task=body.task, provider=body.provider,
        model=body.model, template=body.template, topic=body.topic, criteria=body.criteria,
        preset_id=body.preset_id, base_url=body.base_url, settings=settings,
        repetitions=max(1, body.repetitions), shuffle=body.shuffle, seed=body.seed, threshold=body.threshold,
        concurrency=max(1, min(16, body.concurrency)), max_cost_usd=body.max_cost_usd,
        dataset_id=body.dataset_id, input_file=meta["file"], input_sha256=meta["sha256"],
    )
    store = RunStore.create(run_id, cfg, recs, catalog.get(body.provider, body.model).to_dict())
    out_dir = body.output_dir or str(exports_dir() / f"{safe_name(cfg.name)}_{run_id}")
    store.update_manifest(column_mapping=mapping, estimate=_estimate(body, recs), output_dir=out_dir)
    await _start(store)
    return {"run_id": run_id}


def _store(run_id: str) -> RunStore:
    if "/" in run_id or ".." in run_id:
        raise HTTPException(404, "run not found")
    s = RunStore(run_id)
    if not (s.dir / "manifest.json").exists():
        raise HTTPException(404, "run not found")
    return s


@app.get("/api/runs")
def runs():
    return list_runs()


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    s = _store(run_id)
    return {"manifest": s.manifest, "state": s.state(), "active": run_id in ENGINES}


@app.get("/api/runs/{run_id}/calls")
def run_calls(run_id: str, offset: int = 0, limit: int = 200, status: Optional[str] = None):
    rows = _store(run_id).final_calls()
    if status:
        rows = [r for r in rows if r["status"] == status]
    return {"total": len(rows), "rows": rows[offset: offset + limit]}


@app.get("/api/runs/{run_id}/records")
def run_records(run_id: str):
    df = record_summary(_store(run_id))
    return json.loads(df.to_json(orient="records"))


@app.get("/api/runs/{run_id}/analysis")
def run_analysis(run_id: str):
    """Analysis of a run, cached in the run folder until the call log changes."""
    s = _store(run_id)
    log = s.dir / "calls.jsonl"
    stamp = f"{log.stat().st_mtime_ns}:{log.stat().st_size}" if log.exists() else "none"
    cache = s.dir / "analysis.json"
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("_stamp") == stamp and run_id not in ENGINES:
                return cached["result"]
        except (OSError, ValueError):
            pass
    result = analysis.analyze_run(s)
    if run_id not in ENGINES:
        cache.write_text(json.dumps({"_stamp": stamp, "result": result}), encoding="utf-8")
    return result


class CompareIn(BaseModel):
    run_ids: list[str]


@app.post("/api/compare")
def compare(body: CompareIn):
    return analysis.compare_runs([_store(r) for r in body.run_ids])


@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str):
    eng = ENGINES.get(run_id)
    if not eng:
        raise HTTPException(409, "run is not active")
    eng.cancel()
    return {"ok": True}


@app.post("/api/runs/{run_id}/resume")
async def resume(run_id: str):
    if run_id in ENGINES:
        raise HTTPException(409, "run is already active")
    s = _store(run_id)
    await _start(s)
    return {"ok": True}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request):
    s = _store(run_id)

    async def gen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            st = s.state()
            payload = json.dumps(st)
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if st.get("status") in ("completed", "cancelled", "stopped", "failed") and run_id not in ENGINES:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/runs/{run_id}/download/{kind}")
def download(run_id: str, kind: str):
    s = _store(run_id)
    if kind == "xlsx":
        p = write_excel(s)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif kind == "csv":
        p, media = write_csv(s), "text/csv"
    elif kind == "jsonl":
        p, media = s.dir / "calls.jsonl", "application/x-ndjson"
    elif kind == "manifest":
        p, media = s.dir / "manifest.json", "application/json"
    else:
        raise HTTPException(404, "unknown download")
    return FileResponse(p, media_type=media, filename=f"bibaifilter_{run_id}_{p.name}")


class ExportIn(BaseModel):
    output_dir: Optional[str] = None


@app.post("/api/runs/{run_id}/export")
def export(run_id: str, body: ExportIn):
    s = _store(run_id)
    folder = body.output_dir or s.manifest.get("output_dir") or str(exports_dir() / f"{safe_name(s.config.name)}_{run_id}")
    try:
        files = export_run(s, Path(folder))
    except OSError as exc:
        raise HTTPException(400, f"cannot write to {folder}: {exc}")
    return {"folder": str(Path(folder).resolve()), "files": [f.name for f in files]}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    if run_id in ENGINES:
        raise HTTPException(409, "cancel the run first")
    shutil.rmtree(_store(run_id).dir)
    return {"ok": True}


# --------------------------------------------------------------------------
# Static web interface (Next.js static export)


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    if not (WEB_DIR / "index.html").exists():
        return Response(
            "<h1>BibAIFilter API is running</h1><p>The web interface is not bundled in this "
            "installation (developer checkout). Build it with <code>scripts/build_web.sh</code> or "
            "run <code>npm run dev</code> in <code>web/</code>. API docs: <a href='/api/docs'>/api/docs</a></p>",
            media_type="text/html")
    root = WEB_DIR.resolve()
    target = (WEB_DIR / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(404)
    if target.is_file():
        headers = {} if "/_next/static/" in f"/{path}" else {"Cache-Control": "no-cache"}
        return FileResponse(target, headers=headers)
    if (target / "index.html").is_file():
        return FileResponse(target / "index.html", headers={"Cache-Control": "no-cache"})
    if target.with_suffix(".html").is_file():
        return FileResponse(target.with_suffix(".html"), headers={"Cache-Control": "no-cache"})
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
