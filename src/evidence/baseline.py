"""Comparable external-baseline validation for the current capability grader."""

from __future__ import annotations

from typing import Any

from src.capability_tasks import CAPABILITY_TASKS
from src.evidence.common import (
    JsonObjectSource,
    contains_secret_material,
    load_json_object,
    require_string,
    stable_digest,
)

EXTERNAL_BASELINE_SCHEMA = "external_baseline_v1"
CURRENT_GRADER_VERSION = "capability-grader-v1"
_REQUIRED_STRINGS = (
    "name",
    "source_ref",
    "model",
    "runtime",
    "evaluated_at",
    "task_set_digest",
    "grader_version",
)


def current_task_set_digest() -> str:
    """Return a stable digest of every public task definition and assertion case."""

    return stable_digest(
        [
            {
                "task_id": task.task_id,
                "prompt": task.prompt,
                "entrypoint": task.entrypoint,
                "difficulty": task.difficulty,
                "cases": [{"args": case.args, "expected": case.expected} for case in task.cases],
            }
            for task in CAPABILITY_TASKS
        ]
    )


def validate_external_baseline(
    source: JsonObjectSource,
    expected_task_digest: str | None = None,
    expected_grader_version: str | None = None,
) -> dict[str, Any]:
    """Classify a baseline as provided, incompatible, invalid, or not configured."""

    baseline = load_json_object(source)
    if (
        baseline.get("schema") == EXTERNAL_BASELINE_SCHEMA
        and baseline.get("status") == "not_configured"
    ):
        return {
            "status": "not_configured",
            "compatible": False,
            "name": baseline.get("name", "external"),
            "reason": baseline.get("reason") or "Not configured.",
            "metrics": baseline.get("metrics", {}),
            "limitations": baseline.get("limitations", []),
            "errors": [],
        }

    structural_errors: list[str] = []
    if baseline.get("schema") != EXTERNAL_BASELINE_SCHEMA:
        structural_errors.append(f"schema must be {EXTERNAL_BASELINE_SCHEMA}")
    values = {
        field: require_string(baseline, field, structural_errors) for field in _REQUIRED_STRINGS
    }
    samples_per_task = baseline.get("samples_per_task")
    if (
        not isinstance(samples_per_task, int)
        or isinstance(samples_per_task, bool)
        or samples_per_task < 3
    ):
        structural_errors.append("samples_per_task must be an integer >= 3")
    metrics = baseline.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        structural_errors.append("metrics must be a non-empty object")
        metrics = {}
    limitations = baseline.get("limitations")
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(item, str) or not item.strip() for item in limitations)
    ):
        structural_errors.append("limitations must be a non-empty string list")
        limitations = []
    if contains_secret_material(baseline):
        structural_errors.append("baseline contains secret material")

    compatibility_errors: list[str] = []
    if expected_task_digest is not None and values["task_set_digest"] != expected_task_digest:
        compatibility_errors.append("task_set_digest does not match the current task set")
    if expected_grader_version is not None and values["grader_version"] != expected_grader_version:
        compatibility_errors.append("grader_version does not match the current grader")

    if structural_errors:
        status = "invalid"
    elif compatibility_errors:
        status = "incompatible"
    else:
        status = "provided"
    errors = [*structural_errors, *compatibility_errors]
    return {
        "status": status,
        "compatible": status == "provided",
        "errors": errors,
        **values,
        "samples_per_task": samples_per_task,
        "metrics": metrics,
        "limitations": limitations,
    }
