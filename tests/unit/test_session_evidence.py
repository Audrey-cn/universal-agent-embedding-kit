from __future__ import annotations

from typing import Any

from src.evidence.session import aggregate_session_evidence, validate_session_artifact


def _live_session(session_id: str, duration: float = 3700.0) -> dict[str, Any]:
    return {
        "schema": "session_evidence_v1",
        "evidence_type": "live_session",
        "session_id": session_id,
        "provenance": {
            "source": "provider://fixture/session-1",
            "recorded_at": "2026-08-09T00:00:00Z",
        },
        "duration_seconds": duration,
        "turn_count": 12,
        "checkpoints": [{"turn": 6, "status": "passing"}],
        "final_outcome": "completed",
        "grades": {
            "correctness": 0.9,
            "maintainability": 0.8,
            "security": 1.0,
            "documentation": 0.75,
        },
    }


def _deterministic_session(scenario_id: str) -> dict[str, Any]:
    return {
        "schema": "session_evidence_v1",
        "evidence_type": "deterministic_scenario",
        "scenario_id": scenario_id,
        "grader_output": {"passed": True, "score": 1.0},
    }


def test_session_aggregation_never_counts_deterministic_as_live() -> None:
    result = aggregate_session_evidence(
        [_live_session("live-1", duration=3700), _deterministic_session("scenario-1")]
    )

    assert result["live_session_count"] == 1
    assert result["deterministic_scenario_count"] == 1
    assert result["multi_hour_live_count"] == 1


def test_live_session_requires_provenance_turns_checkpoints_and_grades() -> None:
    artifact = _live_session("incomplete")
    artifact.pop("provenance")
    artifact["turn_count"] = 0
    artifact["checkpoints"] = []
    artifact["grades"] = {"correctness": 1.0}

    result = validate_session_artifact(artifact)

    assert result["valid"] is False
    assert {"provenance", "turn_count", "checkpoints", "grades"}.issubset(
        {error.split(":", 1)[0] for error in result["errors"]}
    )


def test_deterministic_scenario_requires_scenario_and_grader_output() -> None:
    artifact = _deterministic_session("scenario-1")
    artifact["grader_output"] = {}

    result = validate_session_artifact(artifact)

    assert result["valid"] is False
    assert any(error.startswith("grader_output:") for error in result["errors"])


def test_session_validation_rejects_unknown_types_and_secrets() -> None:
    artifact = _live_session("live-secret")
    artifact["evidence_type"] = "simulation"
    artifact["authorization"] = "Bearer credential"

    result = validate_session_artifact(artifact)

    assert result["valid"] is False
    assert any(error.startswith("evidence_type:") for error in result["errors"])
    assert any("secret material" in error for error in result["errors"])


def test_session_aggregation_reports_live_grade_means_only() -> None:
    result = aggregate_session_evidence(
        [
            _live_session("live-1", duration=100),
            _live_session("live-2", duration=200),
            _deterministic_session("scenario-1"),
        ]
    )

    assert result["live_grade_means"]["correctness"] == 0.9
    assert result["live_duration_seconds"] == 300
