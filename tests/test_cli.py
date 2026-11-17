from datetime import datetime

import pytest

from bibaifilter.cli import run_id_for

NOW = datetime(2026, 11, 11, 1, 9, 29)


@pytest.mark.parametrize("model", ["llama3.1:8b", "gpt-oss:20b", "openai/gpt-6-luna", "qwen3:8b-q4_K_M",
                                   "claude-haiku-5-5", 'a<b>c"d|e?f*g'])
def test_run_id_is_a_valid_folder_name(tmp_path, model):
    rid = run_id_for(model, NOW)
    assert rid.startswith("20261111-010929-")
    assert not set(rid) & set(':/\\<>"|?*')
    (tmp_path / rid).mkdir()


def test_plain_model_ids_are_kept():
    assert run_id_for("claude-haiku-5-5", NOW) == "20261111-010929-claude-haiku-5-5"
    assert run_id_for("llama3.1:8b", NOW) == "20261111-010929-llama3.1_8b"
