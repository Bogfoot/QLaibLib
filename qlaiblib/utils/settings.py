"""Persisted settings for QLaibLib dashboards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_SETTINGS_DIR = Path.home() / ".qlaiblib"
_SETTINGS_PATH = _SETTINGS_DIR / "settings.json"

_DEFAULTS: Dict[str, Any] = {
    "delays_ps": {},
    "channels": {},
    "pairs": {},
    "histogram": {
        "start_ps": -8000.0,
        "end_ps": 8000.0,
        "step_ps": 50.0,
    },
}


def load() -> Dict[str, Any]:
    if _SETTINGS_PATH.exists():
        try:
            with _SETTINGS_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            merged = _DEFAULTS | data
            merged.setdefault("delays_ps", {})
            merged.setdefault("channels", {})
            merged.setdefault("pairs", {})
            merged.setdefault("histogram", {}).update(
                {k: merged["histogram"].get(k, v) for k, v in _DEFAULTS["histogram"].items()}
            )
            return merged
        except Exception:
            pass
    return json.loads(json.dumps(_DEFAULTS))


def save(data: Dict[str, Any]) -> None:
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
