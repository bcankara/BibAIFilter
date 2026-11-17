"""Where BibAIFilter keeps its work.

The *workspace* folder holds ``datasets/``, ``runs/`` and ``exports/``. Order of
precedence:

1. the ``BIBAIFILTER_HOME`` environment variable (or ``bibaifilter --data-dir``),
2. the folder chosen in the interface (Settings → Workspace), remembered in a
   small file in the platform's configuration directory,
3. ``~/BibAIFilter`` (visible in the user's home folder, easy to find and back up).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def config_dir() -> Path:
    """Per-user configuration folder (workspace choice, API-key file). Never inside a workspace."""
    env = os.environ.get("BIBAIFILTER_CONFIG_DIR")
    if env:
        base = Path(env).expanduser()
    else:
        try:
            from platformdirs import user_config_dir

            base = Path(user_config_dir("BibAIFilter", appauthor=False))
        except Exception:  # pragma: no cover
            base = Path.home() / ".config" / "BibAIFilter"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _config_file() -> Path:
    return config_dir() / "config.json"


def _read_config() -> dict:
    p = _config_file()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


def default_workspace() -> Path:
    return Path.home() / "BibAIFilter"


def workspace_source() -> str:
    if os.environ.get("BIBAIFILTER_HOME"):
        return "environment (BIBAIFILTER_HOME)"
    if _read_config().get("workspace"):
        return "chosen in settings"
    return "default"


def data_home() -> Path:
    env = os.environ.get("BIBAIFILTER_HOME")
    chosen = _read_config().get("workspace")
    p = Path(env or chosen or default_workspace()).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_workspace(path: Optional[str]) -> Path:
    """Remember a workspace folder (``None`` resets to the default)."""
    cfg = _read_config()
    if path:
        p = Path(path).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        cfg["workspace"] = str(p)
    else:
        cfg.pop("workspace", None)
    _config_file().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return data_home()


def _sub(name: str) -> Path:
    p = data_home() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def datasets_dir() -> Path:
    return _sub("datasets")


def runs_dir() -> Path:
    return _sub("runs")


def exports_dir() -> Path:
    return _sub("exports")
