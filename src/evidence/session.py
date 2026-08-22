"""Strict separation of deterministic scenarios from recorded live sessions."""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from typing import Any

from src.evidence.common import JsonObjectSource, contains_secret_material, load_json_object

SESSION_SCHEMA = "session_evidence_v1"
SESSION_SUMMARY_SCHEMA = "session_evidence_summary_v1"
LIVE_SESSION = "live_session"
DETERMINISTIC_SCENARIO = "deterministic_scenario"
GRADE_FIELDS = ("correctness", "maintainability", "security", "documentation")
MULTI_HOUR_SECONDS = 3600


def validate_session_artifact(source: JsonObjectSource) -> dict[str, Any]:
    """Validate one live or deterministic artifact without conflating the two."""

    artifact = load_json_object(source)
    errors: list[str] = []
    if artifact.get("schema") != SESSION_SCHEMA:
        errors.append(f"schema: must be {SESSION_SCHEMA}")
    if contains_secret_material(artifact):
        errors.append("artifact: contains secret material")

    evidence_type = artifact.get("evidence_type")
    if evidence_type == LIVE_SESSION:
        _validate_live_session(artifact, errors)
    elif evidence_type == DETERMINISTIC_SCENARIO:
        _validate_deterministic_scenario(artifact, errors)
    else:
        errors.append("evidence_type: must be live_session or deterministic_scenario")

    return {"valid": not errors, "errors": errors, "artifact": artifact}


def aggregate_session_evidence(artifacts: Iterable[JsonObjectSource]) -> dict[str, Any]:
    """Count and summarize live and deterministic evidence in disjoint buckets."""

    live: list[dict[str, Any]] = []
    deterministic: list[dict[str, Any]] = []
    for source in artifacts:
        validation = validate_session_artifact(source)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        artifact = validation["artifact"]
        if artifact["evidence_type"] == LIVE_SESSION:
            live.append(artifact)
        else:
            deterministic.append(artifact)

    grade_means = (
        {
            field: round(statistics.fmean(item["grades"][field] for item in live), 6)
            for field in GRADE_FIELDS
        }
        if live
        else {}
    )
    return {
        "schema": SESSION_SUMMARY_SCHEMA,
        "live_session_count": len(live),
        "deterministic_scenario_count": len(deterministic),
        "multi_hour_live_count": sum(
            float(item["duration_seconds"]) >= MULTI_HOUR_SECONDS for item in live
        ),
        "live_duration_seconds": sum(float(item["duration_seconds"]) for item in live),
        "live_grade_means": grade_means,
    }


def _validate_live_session(artifact: dict[str, Any], errors: list[str]) -> None:
    if not _non_empty_string(artifact.get("session_id")):
        errors.append("session_id: must be a non-empty string")

    provenance = artifact.get("provenance")
    if (
        not isinstance(provenance, dict)
        or not _non_empty_string(provenance.get("source"))
        or not _non_empty_string(provenance.get("recorded_at"))
    ):
        errors.append("provenance: source and recorded_at are required")

    duration = artifact.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        errors.append("duration_seconds: must be a positive number")

    turn_count = artifact.get("turn_count")
    if not isinstance(turn_count, int) or isinstance(turn_count, bool) or turn_count <= 0:
        errors.append("turn_count: must be a positive integer")

    checkpoints = artifact.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        errors.append("checkpoints: must be a non-empty list")
    if not _non_empty_string(artifact.get("final_outcome")):
        errors.append("final_outcome: must be a non-empty string")

    grades = artifact.get("grades")
    if not isinstance(grades, dict):
        errors.append(f"grades: requires {', '.join(GRADE_FIELDS)}")
        return
    missing_or_invalid = [field for field in GRADE_FIELDS if not _bounded_grade(grades.get(field))]
    if missing_or_invalid:
        errors.append(f"grades: invalid or missing {', '.join(missing_or_invalid)}")


def _validate_deterministic_scenario(artifact: dict[str, Any], errors: list[str]) -> None:
    if not _non_empty_string(artifact.get("scenario_id")):
        errors.append("scenario_id: must be a non-empty string")
    grader_output = artifact.get("grader_output")
    if not isinstance(grader_output, dict) or not grader_output:
        errors.append("grader_output: must be a non-empty object")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bounded_grade(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )
