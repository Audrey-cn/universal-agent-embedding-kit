"""Tests for the real-scenario benchmark — research proposition 4.

Self-contained coding tasks (write two_sum) miss what real sessions test:
multi-step dependencies, ambiguity, and — crucially — not breaking existing
behavior. This suite scores solutions across multiple dimensions (correctness,
completeness/no-regression, context retention, robustness) so it can flag a
solution that ships the requested feature but regresses something else — a
failure a single pass/fail check passes.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_reference_solutions_score_full_marks():
    from src.scenario_benchmark import (
        REFERENCE_SOLUTIONS,
        SCENARIOS,
        evaluate_scenario,
    )

    for scenario in SCENARIOS:
        report = evaluate_scenario(scenario, REFERENCE_SOLUTIONS[scenario.scenario_id])
        assert report["overall"] == 1.0, scenario.scenario_id


def test_multidimensional_eval_flags_regression_single_passfail_misses():
    """The crux of proposition 4: a feature-complete but regressing solution."""
    from src.scenario_benchmark import FLAWED_SOLUTIONS, evaluate_scenario, get_scenario

    scenario = get_scenario("discount_feature")
    report = evaluate_scenario(scenario, FLAWED_SOLUTIONS["discount_feature"])

    # A correctness-only gate would accept it: the new feature works.
    assert report["dimensions"]["correctness"] == 1.0
    # But the multi-dimensional eval catches the regression it introduced.
    assert report["dimensions"]["completeness"] < 1.0
    assert report["overall"] < 1.0


def test_context_retention_catches_inline_reimplementation():
    """Red-teamed: the reuse probe flags a solution that passes black-box checks
    but reimplements the dependency instead of reusing it."""
    from src.scenario_benchmark import FLAWED_SOLUTIONS, evaluate_scenario, get_scenario

    scenario = get_scenario("running_total")
    report = evaluate_scenario(scenario, FLAWED_SOLUTIONS["running_total"])

    # Passes every output-equality dimension...
    assert report["dimensions"]["correctness"] == 1.0
    assert report["dimensions"]["completeness"] == 1.0
    # ...but the genuine reuse probe catches the inline reimplementation.
    assert report["dimensions"]["context_retention"] == 0.0


def test_genuine_reuse_passes_context_retention():
    from src.scenario_benchmark import REFERENCE_SOLUTIONS, evaluate_scenario, get_scenario

    scenario = get_scenario("running_total")
    report = evaluate_scenario(scenario, REFERENCE_SOLUTIONS["running_total"])

    assert report["dimensions"]["context_retention"] == 1.0


def test_scenarios_are_multistep_and_multidimensional():
    from src.scenario_benchmark import DIMENSIONS, SCENARIOS

    assert len(SCENARIOS) >= 2
    # Real scenarios cover more than one dimension and carry ambiguity notes.
    for scenario in SCENARIOS:
        dims = {check.dimension for check in scenario.checks}
        assert len(dims) >= 2
        assert scenario.ambiguity
    assert set(DIMENSIONS) >= {"correctness", "completeness"}


def test_run_scenario_readiness_reports_discrimination():
    from src.scenario_benchmark import run_scenario_readiness

    result = run_scenario_readiness()

    assert result["dimension"] == "4_real_scenario_benchmark"
    assert result["scenario_count"] >= 2
    assert result["reference_overall"] == 1.0
    assert result["flawed_overall"] < result["reference_overall"]
    assert result["flags_hidden_regression"] is True
    assert result["status"] == "completed"
    assert _check_status(result, "multidimensional_discrimination") == "pass"


def test_rung3_real_agent_scenario_solutions():
    """Rung-3: real agent solutions scored by the rubric, with the reuse probe verified live."""
    from src.scenario_benchmark import load_live_scenario_measurement, run_scenario_readiness

    live = load_live_scenario_measurement()
    if live is None:
        import pytest

        pytest.skip("no live scenario measurement artifact present")

    assert live["evidence_rung"] == 3
    assert len(live["runs"]) >= 1
    # The reuse probe was exercised on real agent code, not just constructed fixtures.
    assert live["context_retention_verified_on_real_code"] is True

    result = run_scenario_readiness()
    assert result["live_measurement"] is not None
    assert _check_status(result, "real_agent_solutions_scored_live") == "pass"


def test_benchmark_scenario_suite():
    from src.benchmark import run_benchmark

    result = run_benchmark("scenario", iterations=1)

    assert result["suite"] == "scenario"
    assert "scenario_readiness" in result


def test_cli_benchmark_scenario_suite(tmp_path: Path):
    output_path = tmp_path / "benchmark-scenario.json"

    result = CliRunner().invoke(
        main,
        ["benchmark", "--suite", "scenario", "--iterations", "1", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "scenario"
    assert "scenario_readiness" in payload


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")
