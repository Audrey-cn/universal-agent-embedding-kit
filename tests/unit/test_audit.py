"""Tests for the uaek audit feature."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_audit_run_all_suites():
    """run_audit should aggregate all benchmark suites into a unified report."""
    from src.benchmark import run_audit

    result = run_audit(iterations=2)

    assert result["audit_version"] == "audit_v1"
    assert "generated_at" in result
    assert result["iterations"] == 2
    assert len(result["suite_results"]) >= 8  # at least the core suites

    # Proposition summary should be present and complete
    props = result["propositions"]
    assert props["p1_context_utilization"]["status"] == "complete"
    assert props["p2_self_grading_cheating"]["status"] == "complete"
    assert props["p3_cost_optimization"]["status"] == "complete"
    assert props["p4_real_scenario_benchmark"]["status"] == "complete"
    assert props["p5_cross_platform_verification"]["status"] == "complete"
    assert props["all_propositions_complete"] is True

    # Each proposition should have evidence_rung
    for key in ["p1_context_utilization", "p2_self_grading_cheating",
                "p3_cost_optimization", "p4_real_scenario_benchmark",
                "p5_cross_platform_verification"]:
        assert props[key]["evidence_rung"] >= 3

    # Gates should be present
    gates = result["gates"]
    assert "tests_passing" in gates
    assert "ci_remote_verified" in gates
    assert gates["external_baseline_available"] is False

    # Limitations should list known caveats
    assert len(result["limitations"]) >= 6

    # External baseline should be not_configured when no path given
    assert result["external_baseline"]["status"] == "not_configured"


def test_audit_with_baseline_path(tmp_path: Path):
    """run_audit should load external baseline when a valid path is given."""
    baseline = tmp_path / "test-baseline.json"
    baseline.write_text(json.dumps({
        "name": "test-baseline",
        "status": "provided",
        "source": "test",
        "metrics": {"score": 85},
    }))

    from src.benchmark import run_audit

    result = run_audit(iterations=1, baseline_path=baseline)
    assert result["external_baseline"]["status"] == "provided"
    assert result["external_baseline"]["name"] == "test-baseline"


def test_audit_cli_command():
    """uaek audit should run and produce a JSON report."""
    runner = CliRunner()
    result = runner.invoke(main, ["audit", "--iterations", "1", "--output", "-"])

    # It should succeed
    assert result.exit_code == 0

    # Should mention the written file
    assert "written" in result.output


def test_benchmark_suite_all_delegates_to_audit():
    """benchmark --suite all should delegate to run_audit."""
    from src.benchmark import run_benchmark

    result = run_benchmark(suite="all", iterations=1)
    assert "audit_version" in result
    assert len(result["suite_results"]) >= 8


def test_audit_cli_writes_json_file(tmp_path: Path):
    """uaek audit --output <file>.json should write valid JSON."""
    output = tmp_path / "test-audit.json"
    runner = CliRunner()
    result = runner.invoke(main, [
        "audit", "--iterations", "1", "--output", str(output),
    ])

    assert result.exit_code == 0
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["audit_version"] == "audit_v1"
    assert len(data["suite_results"]) >= 8
    assert data["propositions"]["all_propositions_complete"] is True
