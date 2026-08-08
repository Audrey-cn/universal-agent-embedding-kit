from __future__ import annotations

from typing import Any

from src.evidence.cost import aggregate_cost_evidence, validate_cost_ledger


def _session(
    session_id: str,
    cohort: str,
    *,
    baseline_cost: float,
    measured_cost: float,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "cohort": cohort,
        "input_tokens": 800,
        "cache_read_tokens": 200,
        "cache_write_tokens": 100,
        "output_tokens": 300,
        "elapsed_seconds": 12.5,
        "session_gap_seconds": 60.0,
        "baseline_cost": baseline_cost,
        "measured_cost": measured_cost,
    }


def _ledger() -> dict[str, Any]:
    return {
        "schema": "cost_evidence_v1",
        "sessions": [
            _session("warm-1", "warm", baseline_cost=1.0, measured_cost=0.6),
            _session("warm-2", "warm", baseline_cost=1.0, measured_cost=0.8),
            _session("mixed-1", "mixed", baseline_cost=1.0, measured_cost=1.0),
            _session("cold-1", "cold", baseline_cost=1.0, measured_cost=1.2),
        ],
    }


def test_cost_aggregation_keeps_warm_mixed_and_cold_separate() -> None:
    result = aggregate_cost_evidence(_ledger())

    assert set(result["cohorts"]) == {"warm", "mixed", "cold"}
    assert result["cohorts"]["warm"]["mean_reduction"] > 0
    assert result["cohorts"]["cold"]["mean_reduction"] < 0
    assert "combined_reduction" not in result
    assert "mean_reduction" not in result


def test_cost_aggregation_reports_cohort_statistics() -> None:
    result = aggregate_cost_evidence(_ledger())
    warm = result["cohorts"]["warm"]

    assert warm["sample_count"] == 2
    assert warm["mean_reduction"] == 0.3
    assert warm["median_reduction"] == 0.3
    assert warm["mean_cache_hit_rate"] == 0.2
    assert len(warm["confidence_interval_95"]) == 2


def test_cost_ledger_rejects_missing_tokens_and_unknown_cohort() -> None:
    invalid = _ledger()
    invalid["sessions"][0]["cohort"] = "lukewarm"
    del invalid["sessions"][0]["cache_read_tokens"]
    validation = validate_cost_ledger(invalid)

    assert validation["valid"] is False
    assert any("cohort" in error for error in validation["errors"])
    assert any("cache_read_tokens" in error for error in validation["errors"])


def test_cost_ledger_rejects_duplicate_ids_negative_values_and_secrets() -> None:
    invalid = _ledger()
    invalid["sessions"][1]["session_id"] = "warm-1"
    invalid["sessions"][2]["elapsed_seconds"] = -1
    invalid["api_key"] = "credential"
    validation = validate_cost_ledger(invalid)

    assert validation["valid"] is False
    assert any("duplicate session_id" in error for error in validation["errors"])
    assert any("elapsed_seconds" in error for error in validation["errors"])
    assert any("secret material" in error for error in validation["errors"])


def test_cost_ledger_requires_positive_baseline_cost() -> None:
    invalid = _ledger()
    invalid["sessions"][0]["baseline_cost"] = 0

    validation = validate_cost_ledger(invalid)

    assert validation["valid"] is False
    assert any("baseline_cost" in error for error in validation["errors"])
