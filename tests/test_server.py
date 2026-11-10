import io
import json
import time

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BIBAIFILTER_HOME", str(tmp_path))
    monkeypatch.setenv("BIBAIFILTER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    from bibaifilter.server import app as appmod

    return TestClient(appmod.app), appmod


def _xlsx():
    df = pd.DataFrame({"Title": ["Peer tutoring in reading", "Protein folding", ""],
                       "Abstract": ["Primary school trial", "Molecular dynamics", ""],
                       "Author Keywords": ["education", "biology", ""],
                       "label_included": [1, 0, 0]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def test_end_to_end(client, monkeypatch):
    c, appmod = client
    assert c.get("/api/health").json()["ok"]
    prov = {p["id"]: p for p in c.get("/api/providers").json()}
    assert prov["openai"]["key"]["configured"] and "sk-test" not in json.dumps(prov)
    up = c.post("/api/datasets", files={"file": ("recs.xlsx", _xlsx())}).json()
    assert up["mapping"]["title"] == "Title" and up["mapping"]["label"] == "label_included"
    m = c.post(f"/api/datasets/{up['id']}/mapping", json={"mapping": up["mapping"]}).json()
    assert m["n_records"] == 3 and m["n_empty"] == 1 and m["n_label_include"] == 1

    # replace the network with a mock provider
    def handler(request):
        body = json.loads(request.content)
        score = 6 if "Peer tutoring" in body["messages"][0]["content"] else 1
        return httpx.Response(200, json={"model": "gpt-6-luna-2026-09-01", "choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps({"score": score})}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 4}})

    from bibaifilter.core import engine as eng_mod

    orig = eng_mod.Engine.__init__

    def patched(self, store, api_key, progress=None, transport=None, sleep=None):
        orig(self, store, api_key, progress, httpx.MockTransport(handler))

    monkeypatch.setattr(eng_mod.Engine, "__init__", patched)
    from bibaifilter.core.prompts import PRESETS

    payload = {"dataset_id": up["id"], "template": PRESETS["score-v2"].template, "topic": "education",
               "provider": "openai", "model": "gpt-6-luna", "repetitions": 2,
               "settings": {"temperature": 0, "reasoning": "none"}}
    est = c.post("/api/estimate", json=payload).json()
    assert est["n_calls"] == 6 and est["price_known"]
    run_id = c.post("/api/runs", json=payload).json()["run_id"]
    for _ in range(100):
        st = c.get(f"/api/runs/{run_id}").json()["state"]
        if st.get("status") in ("completed", "failed", "stopped"):
            break
        time.sleep(0.05)
    assert st["status"] == "completed", st
    calls = c.get(f"/api/runs/{run_id}/calls").json()
    assert calls["total"] == 6 and sum(r["status"] == "skipped" for r in calls["rows"]) == 2
    an = c.get(f"/api/runs/{run_id}/analysis").json()
    assert an["screening"]["model_decision"]["recall"] == 1.0
    assert "bm25_ranking" in an["screening"]
    r = c.get(f"/api/runs/{run_id}/download/xlsx")
    assert r.status_code == 200 and len(r.content) > 1000
    assert c.get(f"/api/runs/{run_id}/download/jsonl").status_code == 200
    # results were copied to the export folder when the run ended
    detail = c.get(f"/api/runs/{run_id}").json()["manifest"]
    from pathlib import Path
    out = Path(detail["export_dir"])
    names = sorted(p.name for p in out.iterdir())
    assert any(n.endswith(".xlsx") for n in names) and any(n.endswith("_calls.jsonl") for n in names)
    # export again to a folder of the user's choice
    target = out.parent / "my results"
    r = c.post(f"/api/runs/{run_id}/export", json={"output_dir": str(target)}).json()
    assert len(r["files"]) == 4 and target.exists()
    ws = c.get("/api/workspace").json()
    assert ws["source"].startswith("environment")
    listing = c.get("/api/fs/list", params={"path": str(out.parent)}).json()
    assert "my results" in listing["dirs"]


def test_keys_are_stored_outside_the_workspace(client, tmp_path, monkeypatch):
    c, _ = client
    from bibaifilter import keys

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY")
    assert c.put("/api/keys/anthropic", json={"key": "sk-ant-secret-123456"}).status_code == 200
    assert (tmp_path / "config" / "secrets.json").exists()
    assert not (tmp_path / "secrets.json").exists()
    st = {p["id"]: p for p in c.get("/api/providers").json()}["anthropic"]["key"]
    assert st["configured"] and "secret" not in str(st)


def test_remote_host_and_cross_origin_refused(client):
    c, _ = client
    assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    r = c.put("/api/keys/openai", json={"key": "x"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_prompt_templates_and_exact_preview(client):
    c, _ = client
    up = c.post("/api/datasets", files={"file": ("recs.xlsx", _xlsx())}).json()
    tpl = "Topic: {TOPIC}\nTitle: {TITLE}\nAbstract: {ABSTRACT}\nScore 1-7."
    saved = c.post("/api/prompts", json={"label": "My short prompt", "task": "score", "template": tpl}).json()
    assert any(p["id"] == saved["id"] and not p["builtin"] for p in c.get("/api/presets").json())
    assert c.post("/api/prompts", json={"label": "bad", "template": "no fields"}).status_code == 400
    pv = c.post("/api/preview", json={"dataset_id": up["id"], "template": tpl, "topic": "education",
                                       "provider": "anthropic", "model": "claude-haiku-5-5"}).json()
    assert pv["prompt"].startswith("Topic: education\nTitle: Peer tutoring")
    body = pv["request_body"]
    assert body["messages"][0]["content"] == pv["prompt"]
    assert "temperature" not in body  # Claude 5.x rejects it; default settings respect that
    assert body["thinking"] == {"type": "disabled"}  # deterministic default: lowest reasoning
    assert c.delete(f"/api/prompts/{saved['id']}").status_code == 200
