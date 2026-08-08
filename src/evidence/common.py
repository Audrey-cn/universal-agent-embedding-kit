"""Shared loading, validation, and redaction helpers for evidence artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

JsonObjectSource = Mapping[str, Any] | str | Path

_SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization"}
_SECRET_FLAG_SUFFIXES = ("token", "secret", "password", "api-key")
_BEARER_PATTERN = re.compile(r"\bbearer\s+\S+", re.IGNORECASE)


def load_json_object(source: JsonObjectSource) -> dict[str, Any]:
    """Load a JSON object from a mapping or UTF-8 path."""

    if isinstance(source, Mapping):
        data: Any = dict(source)
    else:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence source must contain a JSON object")
    return data


def require_string(data: Mapping[str, Any], field: str, errors: list[str]) -> str | None:
    """Return a required non-empty string, recording a stable validation error otherwise."""

    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return None
    return value.strip()


def stable_digest(value: Any) -> str:
    """Return the SHA-256 digest of canonical UTF-8 JSON."""

    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def contains_secret_material(value: Any) -> bool:
    """Detect credential-shaped keys, bearer values, and command-line secret flags."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in _SECRET_KEYS:
                return True
            if contains_secret_material(child):
                return True
        return False

    if isinstance(value, (list, tuple)):
        items = list(value)
        for index, child in enumerate(items):
            if isinstance(child, str) and child.startswith("-"):
                flag, separator, inline_value = child.partition("=")
                normalized_flag = flag.casefold().replace("_", "-")
                if normalized_flag.endswith(_SECRET_FLAG_SUFFIXES):
                    if separator and inline_value:
                        return True
                    if index + 1 < len(items):
                        return True
            if contains_secret_material(child):
                return True
        return False

    return isinstance(value, str) and _BEARER_PATTERN.search(value) is not None
