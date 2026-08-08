"""Validation and cohort-preserving aggregation for cost evidence."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from src.evidence.common import JsonObjectSource, contains_secret_material, load_json_object

COST_SCHEMA = "cost_evidence_v1"
COST_SUMMARY_SCHEMA = "cost_evidence_summary_v1"
COHORTS = {"warm", "mixed", "cold"}
_NON_NEGATIVE_FIELDS = (
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "output_tokens",
    "elapsed_seconds",
    "session_gap_seconds",
    "measured_cost",
)


def validate_cost_ledger(source: JsonObjectSource) -> dict[str, Any]:
    """Validate cost sessions while preserving their declared cache cohort."""

    ledger = load_json_object(source)
    errors: list[str] = []
    if ledger.get("schema") != COST_SCHEMA:
        errors.append(f"schema must be {COST_SCHEMA}")
    if contains_secret_material(ledger):
        errors.append("cost ledger contains secret material")

    sessions = ledger.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        errors.append("sessions must be a non-empty list")
        sessions = []

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, session in enumerate(sessions):
        if not isinstance(session, dict):
            errors.append(f"sessions[{index}] must be an object")
            continue
        session_id = session.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            errors.append(f"sessions[{index}].session_id must be a non-empty string")
        elif session_id in seen_ids:
            errors.append(f"duplicate session_id: {session_id}")
        else:
            seen_ids.add(session_id)

        cohort = session.get("cohort")
        if cohort not in COHORTS:
            errors.append(f"sessions[{index}].cohort must be one of {sorted(COHORTS)}")

        for field in _NON_NEGATIVE_FIELDS:
            _validate_non_negative_number(session, field, index, errors)
        baseline_cost = session.get("baseline_cost")
        if (
            not isinstance(baseline_cost, (int, float))
            or isinstance(baseline_cost, bool)
            or baseline_cost <= 0
        ):
            errors.append(f"sessions[{index}].baseline_cost must be a positive number")
        normalized.append(dict(session))

    return {
        "schema": "cost_evidence_validation_v1",
        "valid": not errors,
        "errors": errors,
        "sessions": normalized,
    }


def aggregate_cost_evidence(source: JsonObjectSource) -> dict[str, Any]:
    """Report independent statistics for warm, mixed, and cold sessions."""

    validation = validate_cost_ledger(source)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in validation["sessions"]:
        grouped[session["cohort"]].append(session)
    return {
        "schema": COST_SUMMARY_SCHEMA,
        "cohorts": {
            cohort: _cohort_statistics(sessions) for cohort, sessions in sorted(grouped.items())
        },
    }


def _validate_non_negative_number(
    session: dict[str, Any], field: str, index: int, errors: list[str]
) -> None:
    value = session.get(field)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
        or not math.isfinite(float(value))
    ):
        errors.append(f"sessions[{index}].{field} must be a non-negative number")


def _cohort_statistics(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    reductions = [
        (float(session["baseline_cost"]) - float(session["measured_cost"]))
        / float(session["baseline_cost"])
        for session in sessions
    ]
    cache_hit_rates = []
    for session in sessions:
        input_tokens = float(session["input_tokens"])
        cache_read_tokens = float(session["cache_read_tokens"])
        cache_total = input_tokens + cache_read_tokens
        cache_hit_rates.append(cache_read_tokens / cache_total if cache_total else 0.0)

    mean = statistics.fmean(reductions)
    deviation = statistics.pstdev(reductions)
    margin = 1.96 * deviation / math.sqrt(len(reductions))
    return {
        "sample_count": len(sessions),
        "mean_reduction": round(mean, 6),
        "median_reduction": round(statistics.median(reductions), 6),
        "min_reduction": min(reductions),
        "max_reduction": max(reductions),
        "mean_cache_hit_rate": round(statistics.fmean(cache_hit_rates), 6),
        "confidence_interval_95": [
            round(max(-1.0, mean - margin), 6),
            round(min(1.0, mean + margin), 6),
        ],
    }
