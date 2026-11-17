import threading
import time

import pytest

from bibaifilter.core import runstore


def test_replace_file_waits_for_a_reader(tmp_path):
    dst = tmp_path / "state.json"
    dst.write_text('{"done": 1}', encoding="utf-8")
    src = tmp_path / "state.json.tmp"
    src.write_text('{"done": 2}', encoding="utf-8")
    reader = open(dst, encoding="utf-8")
    threading.Timer(0.3, reader.close).start()
    runstore.replace_file(src, dst)
    assert dst.read_text(encoding="utf-8") == '{"done": 2}'
    assert not src.exists()


def test_replace_file_gives_up_eventually(tmp_path, monkeypatch):
    calls = []

    def always_locked(a, b):
        calls.append(1)
        raise PermissionError("locked")

    monkeypatch.setattr(runstore.os, "replace", always_locked)
    monkeypatch.setattr(runstore.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        runstore.replace_file(tmp_path / "a", tmp_path / "b", attempts=5)
    assert len(calls) == 5


def test_write_state_survives_concurrent_reads(tmp_path):
    store = runstore.RunStore("r1", tmp_path)
    store.dir.mkdir(parents=True)
    store.write_state({"status": "running", "done": 0})
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            try:
                with open(store.dir / "state.json", encoding="utf-8") as fh:
                    fh.read()
            except (PermissionError, FileNotFoundError):
                pass
            time.sleep(0.005)

    threads = [threading.Thread(target=poll) for _ in range(3)]
    for t in threads:
        t.start()
    try:
        for i in range(200):
            store.write_state({"status": "running", "done": i})
    finally:
        stop.set()
        for t in threads:
            t.join()
    assert store.state()["done"] == 199
