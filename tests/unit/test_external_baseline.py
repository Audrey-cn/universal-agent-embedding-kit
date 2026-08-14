from __future__ import annotations

from typing import Any

import pytest

from src.evidence.baseline import validate_external_baseline


def _baseline(**overrides: Any) -> dict[str, Any]:
    baseline = {
        "schema": "external_baseline_v1",
        "name": "authorized-reference",
        "source_ref": "artifact://external/run-42",
        "model": "reference-model",
        "runtime": "reference-runtime",
        "evaluated_at": "2026-08-09T00:00:00Z",
        "task_set_digest": "tasks-abc",
        "grader_version": "grader-v3",
        "samples_per_task": 3,
        "metrics": {"mean_score": 0.92},
        "limitations": ["Authorized fixture used for contract validation only."],
    }
    baseline.update(overrides)
    return baseline


def test_baseline_is_provided_only_when_task_and_grader_match() -> None:
    result = validate_external_baseline(
        _baseline(), expected_task_digest="tasks-abc", expected_grader_version="grader-v3"
    )

    assert result["status"] == "provided"
    assert result["compatible"] is True


def test_baseline_digest_mismatch_is_incompatible_not_provided() -> None:
    result = validate_external_baseline(
        _baseline(), expected_task_digest="different", expected_grader_version="grader-v3"
    )

    assert result["status"] == "incompatible"
    assert result["compatible"] is False
    assert any("task_set_digest" in error for error in result["errors"])


def test_baseline_grader_mismatch_is_incompatible() -> None:
    result = validate_external_baseline(
        _baseline(), expected_task_digest="tasks-abc", expected_grader_version="grader-v4"
    )

    assert result["status"] == "incompatible"
    assert any("grader_version" in error for error in result["errors"])


def test_baseline_rejects_incomplete_or_secret_material() -> None:
    baseline = _baseline(samples_per_task=2, limitations=[], authorization="Bearer credential")
    baseline.pop("runtime")

    result = validate_external_baseline(baseline)

    assert result["status"] == "invalid"
    assert result["compatible"] is False
    assert any("runtime" in error for error in result["errors"])
    assert any("samples_per_task" in error for error in result["errors"])
    assert any("secret material" in error for error in result["errors"])


def test_current_not_configured_baseline_remains_readable() -> None:
    result = validate_external_baseline(
        {
            "schema": "external_baseline_v1",
            "name": "external",
            "status": "not_configured",
            "reason": "No approved baseline supplied.",
            "metrics": {},
            "limitations": ["No external comparison is claimed."],
        }
    )

    assert result == {
        "status": "not_configured",
        "compatible": False,
        "name": "external",
        "reason": "No approved baseline supplied.",
        "metrics": {},
        "limitations": ["No external comparison is claimed."],
        "errors": [],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", 42),
        ("reason", []),
        ("metrics", []),
        ("limitations", "No comparison"),
        ("limitations", [42]),
    ],
)
def test_current_not_configured_baseline_rejects_invalid_field_types(
    field: str, value: object
) -> None:
    baseline: dict[str, object] = {
        "schema": "external_baseline_v1",
        "name": "external",
        "status": "not_configured",
        "reason": "No approved baseline supplied.",
        "metrics": {},
        "limitations": ["No external comparison is claimed."],
    }
    baseline[field] = value

    result = validate_external_baseline(baseline)

    assert result["status"] == "invalid"
    assert result["compatible"] is False
    assert any(field in error for error in result["errors"])


def test_current_not_configured_baseline_rejects_secret_material() -> None:
    result = validate_external_baseline(
        {
            "schema": "external_baseline_v1",
            "name": "external",
            "status": "not_configured",
            "reason": "No approved baseline supplied.",
            "metrics": {},
            "limitations": ["No external comparison is claimed."],
            "api_key": "placeholder",
        }
    )

    assert result["status"] == "invalid"
    assert result["compatible"] is False
    assert any("secret material" in error for error in result["errors"])


def test_pre_03_not_configured_shape_is_invalid() -> None:
    result = validate_external_baseline(
        {"schema_version": "1.0", "status": "not_configured", "source": "legacy"}
    )

    assert result["status"] == "invalid"
    assert any("schema" in error for error in result["errors"])
