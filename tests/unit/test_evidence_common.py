from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evidence.common import (
    contains_secret_material,
    load_json_object,
    require_string,
    stable_digest,
)


def test_load_json_object_accepts_mapping_and_path(tmp_path: Path) -> None:
    source = {"schema": "example_v1", "value": 1}
    assert load_json_object(source) == source

    path = tmp_path / "source.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    assert load_json_object(path) == source


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "source.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_json_object(path)


def test_require_string_records_missing_and_blank_fields() -> None:
    errors: list[str] = []
    assert require_string({"name": "fixture"}, "name", errors) == "fixture"
    assert require_string({"name": "  "}, "name", errors) is None
    assert require_string({}, "provider", errors) is None
    assert errors == ["name must be a non-empty string", "provider must be a non-empty string"]


def test_stable_digest_is_order_independent_for_objects() -> None:
    assert stable_digest({"b": 2, "a": 1}) == stable_digest({"a": 1, "b": 2})
    assert len(stable_digest({"a": 1})) == 64


@pytest.mark.parametrize(
    "value",
    [
        {"api_key": "secret-value"},
        {"nested": {"Authorization": "Bearer abc"}},
        {"command": ["tool", "--token", "abc"]},
        {"command": ["tool", "--api-key=abc"]},
        "Bearer abcdefghijklmnop",
    ],
)
def test_secret_scan_rejects_credential_fields_and_bearer_values(value: object) -> None:
    assert contains_secret_material(value) is True


def test_secret_scan_accepts_non_secret_metadata() -> None:
    assert contains_secret_material({"provider": "fixture", "seed": 3}) is False
    assert contains_secret_material({"command": ["tool", "--output", "json"]}) is False
