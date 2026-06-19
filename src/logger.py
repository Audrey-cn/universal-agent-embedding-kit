"""Structured JSONL logging for UAEK product entrypoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlLogger:
    """Append structured records to a JSON Lines file."""

    def __init__(self, file_path: Path | str | None, enabled: bool = True):
        self.file_path = Path(file_path) if file_path else None
        self.enabled = enabled

    def record(self, event: str, payload: dict[str, Any]) -> Path | None:
        """Write one event record and return the log path when logging is active."""
        if not self.enabled or self.file_path is None:
            return None

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **payload,
        }
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return self.file_path
