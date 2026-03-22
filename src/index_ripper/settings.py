from __future__ import annotations

import json
from typing import Any


def load_settings(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            content = file_obj.read().strip()
            return json.loads(content) if content else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def save_settings(path: str, data: dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, ensure_ascii=False, indent=2)
    except OSError:
        pass
