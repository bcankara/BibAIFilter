"""API key storage.

Lookup order: environment variable (e.g. ``OPENAI_API_KEY``) -> operating-system
keyring (if the optional ``keyring`` package works on this system) -> a file
``secrets.json`` in the user's configuration folder, readable only by the
current user (mode 0600).
Keys are never written to run folders, logs or exports, and the web API only
reports whether a key is set and where it comes from.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .core.providers import PROVIDER_INFO
from .paths import config_dir

_SERVICE = "BibAIFilter"


def _secrets_file() -> Path:
    # In the user's configuration folder, not in the workspace: a workspace is meant
    # to be backed up and shared, keys are not.
    return config_dir() / "secrets.json"


def _keyring():
    try:
        import keyring  # type: ignore

        backend = keyring.get_keyring()
        name = type(backend).__name__.lower()
        if "fail" in name or "null" in name:
            return None
        if "chainer" in name and not getattr(backend, "backends", None):
            return None
        return keyring
    except Exception:
        return None


def _read_file() -> dict:
    p = _secrets_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_file(data: dict) -> None:
    p = _secrets_file()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, p)


def get_key(provider: str) -> tuple[Optional[str], Optional[str]]:
    """Return (key, source)."""
    env = PROVIDER_INFO.get(provider, {}).get("key_env")
    if env and os.environ.get(env):
        return os.environ[env], f"environment ({env})"
    kr = _keyring()
    if kr is not None:
        try:
            v = kr.get_password(_SERVICE, provider)
            if v:
                return v, "system keyring"
        except Exception:
            pass
    v = _read_file().get(provider)
    if v:
        return v, "local file (owner-only)"
    return None, None


def set_key(provider: str, key: str) -> str:
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(_SERVICE, provider, key)
            return "system keyring"
        except Exception:
            pass
    data = _read_file()
    data[provider] = key
    _write_file(data)
    return "local file (owner-only)"


def delete_key(provider: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(_SERVICE, provider)
        except Exception:
            pass
    data = _read_file()
    if provider in data:
        del data[provider]
        _write_file(data)


def status() -> dict[str, dict]:
    out = {}
    for prov in PROVIDER_INFO:
        key, src = get_key(prov)
        out[prov] = {"configured": bool(key), "source": src,
                     "hint": (key[:3] + "…" + key[-4:]) if key and len(key) > 10 else None}
    return out
