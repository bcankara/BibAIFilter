"""Command-line entry point: ``bibaifilter``.

    bibaifilter                    start the local web interface (opens the browser)
    bibaifilter serve --port 8765  same, with options
    bibaifilter run spec.json      headless, reproducible run from a JSON spec
    bibaifilter analyze RUN_ID     print the analysis of a finished run
    bibaifilter baseline FILE ...  BM25 baseline against labels/reference scores (no API)
    bibaifilter models             list the model catalogue
    bibaifilter check PROVIDER MODEL   one test call; reports, never changes the model
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from . import __version__


def _free_port(host: str, preferred: int) -> int:
    for p in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # same option uvicorn uses, so a port in TIME_WAIT after a restart is reused
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def cmd_serve(args) -> int:
    import uvicorn

    from .server.app import app

    host = args.host
    if host not in ("127.0.0.1", "localhost"):
        print("Warning: binding to a non-local address exposes your API keys' use to the network.")
        app.state.allow_remote = True
    port = _free_port(host, args.port)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', 'localhost') else host}:{port}/"
    print(f"BibAIFilter {__version__} — {url}  (data: {os.environ.get('BIBAIFILTER_HOME') or 'user data dir'})")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


def _load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    if "template_file" in spec:
        spec["template"] = (base / spec.pop("template_file")).read_text(encoding="utf-8")
    spec["input"] = str((base / spec["input"]).resolve())
    if spec.get("output_dir"):
        spec["output_dir"] = str((base / spec["output_dir"]).resolve())
    return spec


def cmd_run(args) -> int:
    from . import keys
    from .core import catalog
    from .core.analysis import analyze_run
    from .core.engine import Engine
    from .core.export import export_run, safe_name, write_excel
    from .paths import exports_dir
    from .core.prompts import PRESETS
    from .core.providers.base import CallSettings
    from .core.records import file_sha256, load_any, records_from_frame
    from .core.runstore import RunConfig, RunStore

    spec = _load_spec(Path(args.spec))
    path = Path(spec["input"])
    df, guessed, _ = load_any(path)
    mapping = {**guessed, **(spec.get("mapping") or {})}
    recs = records_from_frame(df, mapping)
    if spec.get("max_records"):
        recs = recs[: spec["max_records"]]
    template = spec.get("template") or PRESETS[spec.get("preset", "score-v2")].template
    cfg = RunConfig(
        name=spec.get("name", path.stem), task=spec.get("task", "score"), provider=spec["provider"],
        model=spec["model"], template=template, topic=spec["topic"], criteria=spec.get("criteria", ""),
        preset_id=spec.get("preset"), base_url=spec.get("base_url"),
        settings=CallSettings(**({"temperature": 0.0} | (spec.get("settings") or {}))), repetitions=spec.get("repetitions", 1),
        shuffle=spec.get("shuffle", True), seed=spec.get("seed", 20261110), threshold=spec.get("threshold", 4),
        concurrency=spec.get("concurrency", 2), max_cost_usd=spec.get("max_cost_usd"),
        input_file=path.name, input_sha256=file_sha256(path),
    )
    catalog.apply_defaults(catalog.get(cfg.provider, cfg.model), cfg.settings)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + (spec.get("run_suffix") or cfg.model.replace("/", "_"))[:40]
    store = RunStore.create(run_id, cfg, recs, catalog.get(cfg.provider, cfg.model).to_dict())
    store.update_manifest(column_mapping=mapping, spec_file=str(Path(args.spec).resolve()))
    key, src = keys.get_key(cfg.provider)
    print(f"Run {run_id}: {len(recs)} records x {cfg.repetitions} repetitions, {cfg.provider}/{cfg.model} (key: {src or 'none'})")

    def progress(st):
        last = st.get("last") or {}
        sys.stdout.write(f"\r  {st.get('done', 0)}/{st.get('total', 0)}  last: {last.get('status', '')} "
                         f"{last.get('score') if last.get('score') is not None else last.get('decision') or ''}   ")
        sys.stdout.flush()

    state = asyncio.run(Engine(store, key, progress).run())
    print()
    write_excel(store)
    folder = Path(spec["output_dir"]).expanduser() if spec.get("output_dir") else exports_dir() / f"{safe_name(cfg.name)}_{run_id}"
    files = export_run(store, folder)
    print(f"Status: {state['status']}{' — ' + state['message'] if state.get('message') else ''}")
    print(f"Results: {folder}  ({', '.join(f.name for f in files)})")
    print(json.dumps(analyze_run(store)["outcomes"], indent=2))
    return 0 if state["status"] == "completed" else 1


def cmd_analyze(args) -> int:
    from .core.analysis import analyze_run
    from .core.runstore import RunStore

    print(json.dumps(analyze_run(RunStore(args.run_id)), indent=2))
    return 0


def cmd_baseline(args) -> int:
    from .core import metrics
    from .core.bm25 import bm25_scores
    from .core.records import load_any, records_from_frame

    df, mapping, _ = load_any(Path(args.file))
    if args.label_col:
        mapping["label"] = args.label_col
    if args.reference_col:
        mapping["reference_score"] = args.reference_col
    recs = records_from_frame(df, mapping)
    query = args.query or ""
    if args.query_file:
        query = Path(args.query_file).read_text(encoding="utf-8")
    bm = bm25_scores(recs, query)
    out = {"n_records": len(recs), "query": query}
    ref = [r.reference_score for r in recs]
    if sum(v is not None for v in ref) >= 3:
        out["reference_agreement"] = metrics.agreement(bm, ref)
    labels = [r.label for r in recs]
    if any(v == 1 for v in labels):
        rr = metrics.ranked_recall(bm, labels)
        rr.pop("recall_curve", None)
        out["screening_ranking"] = {"roc_auc": metrics.roc_auc(bm, labels), **rr}
    print(json.dumps(metrics.json_safe(out), indent=2))
    return 0


def cmd_models(args) -> int:
    from .core import catalog

    print(f"Model catalogue (checked {catalog.CATALOG_DATE}); any other identifier can also be used.")
    for m in catalog.models(args.provider):
        price = f"${m.price_in}/{m.price_out} per 1M" if m.price_in is not None else "price unknown"
        print(f"  {m.provider:10s} {m.id:32s} {m.status:10s} temp={m.temperature:18s} {price}")
    return 0


def cmd_check(args) -> int:
    from . import keys
    from .core.engine import check_model

    key, _ = keys.get_key(args.provider)
    res = asyncio.run(check_model(args.provider, args.model, key, args.base_url))
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bibaifilter", description="LLM-assisted relevance scoring and screening.")
    p.add_argument("--version", action="version", version=f"BibAIFilter {__version__}")
    p.add_argument("--data-dir", help="where datasets, runs and settings are stored")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the web interface")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    r = sub.add_parser("run", help="headless run from a JSON spec")
    r.add_argument("spec")
    a = sub.add_parser("analyze", help="analysis of a run")
    a.add_argument("run_id")
    b = sub.add_parser("baseline", help="BM25 baseline (no API calls)")
    b.add_argument("file")
    b.add_argument("--query")
    b.add_argument("--query-file")
    b.add_argument("--label-col")
    b.add_argument("--reference-col")
    m = sub.add_parser("models", help="list the model catalogue")
    m.add_argument("--provider")
    c = sub.add_parser("check", help="test one model")
    c.add_argument("provider")
    c.add_argument("model")
    c.add_argument("--base-url")
    args = p.parse_args(argv)
    if args.data_dir:
        os.environ["BIBAIFILTER_HOME"] = str(Path(args.data_dir).expanduser().resolve())
    if args.cmd is None:
        args.cmd, args.host, args.port, args.no_browser = "serve", "127.0.0.1", 8765, False
    return {"serve": cmd_serve, "run": cmd_run, "analyze": cmd_analyze, "baseline": cmd_baseline,
            "models": cmd_models, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
