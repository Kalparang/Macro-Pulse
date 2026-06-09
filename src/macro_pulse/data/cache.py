from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from ..core.paths import resolve_project_path


DEFAULT_CACHE_DIR = ".cache/macro_pulse"


class TtlCache:
    def __init__(self, cache_dir: str | Path | None = None):
        configured_dir = (
            cache_dir
            or os.environ.get("MACRO_PULSE_CACHE_DIR")
            or DEFAULT_CACHE_DIR
        )
        self.cache_dir = resolve_project_path(configured_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_text(self, key: str, ttl_seconds: int) -> str | None:
        payload = self._read_payload(key, ttl_seconds)
        if payload is None:
            return None
        value = payload.get("value")
        return str(value) if value is not None else None

    def set_text(self, key: str, value: str) -> None:
        self._write_payload(key, value)

    def get_json(self, key: str, ttl_seconds: int) -> Any | None:
        payload = self._read_payload(key, ttl_seconds)
        return None if payload is None else payload.get("value")

    def set_json(self, key: str, value: Any) -> None:
        self._write_payload(key, value)

    def _read_payload(self, key: str, ttl_seconds: int) -> dict[str, Any] | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

        created_at = float(payload.get("created_at", 0))
        if time.time() - created_at > ttl_seconds:
            return None
        return payload

    def _write_payload(self, key: str, value: Any) -> None:
        path = self._path_for_key(key)
        payload = {"created_at": time.time(), "value": value}
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

    def _path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"
