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

    # Proposition summary should be present. Some propositions can honestly be
    # partial when their underlying evidence is conditional or incomplete.
    props = result["propositions"]
    assert props["p1_context_utilization"]["status"] == "complete"
    assert props["p2_self_grading_cheating"]["status"] == "complete"
    assert props["p3_cost_optimization"]["status"] in {"complete", "partial"}
    assert props["p4_real_scenario_benchmark"]["status"] == "complete"
    assert props["p5_cross_platform_verification"]["status"] in {"complete", "partial"}
    assert props["all_propositions_complete"] is (
        all(
            props[key]["status"] == "complete"
            for key in [
                "p1_context_utilization",
                "p2_self_grading_cheating",
                "p3_cost_optimization",
                "p4_real_scenario_benchmark",
                "p5_cross_platform_verification",
            ]
        )
    )

    # Each proposition should have evidence_rung
    for key in ["p1_context_utilization", "p2_self_grading_cheating",
                "p3_cost_optimization", "p4_real_scenario_benchmark",
                "p5_cross_platform_verification"]:
        assert props[key]["evidence_rung"] >= 3

    # Gates should be present
    gates = result["gates"]
    assert "audit_passed" in gates
    assert "tests_passing" in gates
    assert "ci_remote_verified" in gates
    assert "evidence_consistency_passed" in gates
    assert gates["external_baseline_available"] is False

    evidence = result["evidence_index"]
    assert evidence["schema"] == "evidence_index_v1"
    assert evidence["consistency"]["status"] == "pass"
    assert evidence["capability"]["held_out"]["enabled_in_current_grader"] is True
    assert evidence["capability"]["held_out"]["held_out_count_per_task"] == 16
    assert evidence["headline"]["p4_real_scenario_benchmark"]["scenario_count"] >= 1

    # Limitations should list known caveats
    assert len(result["limitations"]) >= 6
    assert any("2/4" in item for item in result["limitations"])
    assert not any("4/4 graded-live" in item for item in result["limitations"])

    # External baseline should be not_configured when no path given
    assert result["external_baseline"]["status"] == "not_configured"


def test_audit_with_baseline_path(tmp_path: Path):
    """run_audit should load external baseline when a valid path is given."""
    from src.evidence.baseline import CURRENT_GRADER_VERSION, current_task_set_digest

    baseline = tmp_path / "test-baseline.json"
    baseline.write_text(json.dumps({
        "schema": "external_baseline_v1",
        "name": "test-baseline",
        "source_ref": "artifact://test/baseline",
        "model": "fixture-model",
        "runtime": "fixture-runtime",
        "evaluated_at": "2026-08-09T00:00:00Z",
        "task_set_digest": current_task_set_digest(),
        "grader_version": CURRENT_GRADER_VERSION,
        "samples_per_task": 3,
        "metrics": {"mean_score": 0.85},
        "limitations": ["Test fixture only."],
    }))

    from src.benchmark import run_audit

    result = run_audit(iterations=1, baseline_path=baseline)
    assert result["external_baseline"]["status"] == "provided"
    assert result["external_baseline"]["name"] == "test-baseline"
    assert result["evidence_index"]["external_baseline"]["status"] == "provided"


def test_audit_rejects_incompatible_baseline_for_availability_gate(tmp_path: Path):
    from src.benchmark import run_audit
    from src.evidence.baseline import CURRENT_GRADER_VERSION

    baseline = tmp_path / "incompatible.json"
    baseline.write_text(json.dumps({
        "schema": "external_baseline_v1",
        "name": "incompatible",
        "source_ref": "artifact://test/incompatible",
        "model": "fixture-model",
        "runtime": "fixture-runtime",
        "evaluated_at": "2026-08-09T00:00:00Z",
        "task_set_digest": "different-task-set",
        "grader_version": CURRENT_GRADER_VERSION,
        "samples_per_task": 3,
        "metrics": {"mean_score": 1.0},
        "limitations": ["Test fixture only."],
    }))

    result = run_audit(iterations=1, baseline_path=baseline)

    assert result["external_baseline"]["status"] == "incompatible"
    assert result["gates"]["external_baseline_available"] is False


def test_audit_records_explicit_ci_evidence():
    """External CI URLs should be recorded in the audit and evidence index."""
    from src.benchmark import run_audit

    result = run_audit(
        iterations=1,
        ci_run_url="https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/runs/1",
        ci_artifact_url="https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/runs/1/artifacts/2",
        ci_commit_sha="abc123",
    )

    assert result["gates"]["ci_remote_verified"] is True
    assert result["gates"]["ci_remote_run_url"].endswith("/actions/runs/1")
    assert result["gates"]["ci_artifact_url"].endswith("/artifacts/2")
    assert result["gates"]["ci_commit_sha"] == "abc123"
    assert result["evidence_index"]["ci"]["source"] == "explicit"
    assert result["evidence_index"]["ci"]["verified"] is True


def test_gate_summary_derives_live_and_baseline_status():
    """Gate completeness should come from evidence inputs, not constants."""
    from src.benchmark import _build_gate_summary

    completed = _build_gate_summary(
        {"live_matrix": {"live_matrix_readiness": {"status": "completed"}}},
        errors=[],
        propositions={},
        external_baseline={"status": "provided"},
    )
    partial = _build_gate_summary(
        {"live_matrix": {"live_matrix_readiness": {"status": "partial"}}},
        errors=[],
        propositions={},
        external_baseline={"status": "not_configured"},
    )

    assert completed["live_matrix_complete"] is True
    assert completed["external_baseline_available"] is True
    assert partial["live_matrix_complete"] is False
    assert partial["external_baseline_available"] is False


def test_audit_cli_records_explicit_ci_commit_sha():
    """The CLI should preserve an explicit remote commit in machine output."""
    result = CliRunner().invoke(
        main,
        [
            "audit",
            "--iterations",
            "1",
            "--ci-run-url",
            "https://github.com/org/repo/actions/runs/7",
            "--ci-commit-sha",
            "deadbeef",
            "--output",
            "-",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["gates"]["ci_commit_sha"] == "deadbeef"


def test_audit_cli_command():
    """uaek audit should run and produce a JSON report."""
    runner = CliRunner()
    result = runner.invoke(main, ["audit", "--iterations", "1", "--output", "-"])

    data = json.loads(result.output)
    assert result.exit_code == (0 if data["gates"]["audit_passed"] else 1)
    assert data["audit_version"] == "audit_v1"


def test_audit_fail_closed_when_suites_error(monkeypatch):
    """Audit should not report complete propositions when required suites fail."""
    import src.benchmark as benchmark

    def fail_suite(*args, **kwargs):
        raise RuntimeError("synthetic suite failure")

    monkeypatch.setattr(benchmark, "run_benchmark", fail_suite)

    result = benchmark.run_audit(iterations=1)

    assert len(result["errors"]) == 10
    assert result["suite_results"] == {}
    assert result["gates"]["audit_passed"] is False
    assert result["propositions"]["all_propositions_complete"] is False
    for key, proposition in result["propositions"].items():
        if key == "all_propositions_complete":
            continue
        assert proposition["status"] == "incomplete"
        assert all(value is None for value in proposition["key_result"].values())


def test_audit_cli_exits_nonzero_when_audit_semantics_fail(monkeypatch, tmp_path: Path):
    """Release gates should be able to fail on audit JSON semantics, not just process success."""
    import src.benchmark as benchmark

    def fake_audit(*args, **kwargs):
        return {
            "audit_version": "audit_v1",
            "generated_at": "2026-06-20T00:00:00+00:00",
            "iterations": 1,
            "suite_results": {},
            "errors": [{"suite": "proxy", "error": "missing config"}],
            "propositions": {
                "all_propositions_complete": False,
                "p1_context_utilization": {"status": "incomplete", "key_result": {}},
                "p2_self_grading_cheating": {"status": "incomplete", "key_result": {}},
                "p3_cost_optimization": {"status": "incomplete", "key_result": {}},
                "p4_real_scenario_benchmark": {"status": "incomplete", "key_result": {}},
                "p5_cross_platform_verification": {"status": "incomplete", "key_result": {}},
            },
            "gates": {
                "audit_passed": False,
                "benchmark_evidence_count": 0,
                "ci_remote_verified": False,
                "ci_remote_run_url": None,
                "external_baseline_available": False,
            },
            "limitations": [],
            "external_baseline": {"status": "not_configured"},
        }

    monkeypatch.setattr(benchmark, "run_audit", fake_audit)
    output = tmp_path / "audit.json"

    result = CliRunner().invoke(main, ["audit", "--iterations", "1", "--output", str(output)])

    assert result.exit_code == 1
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["gates"]["audit_passed"] is False


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
    assert data["gates"]["audit_passed"] is True
    assert data["propositions"]["all_propositions_complete"] is (
        all(
            data["propositions"][key]["status"] == "complete"
            for key in [
                "p1_context_utilization",
                "p2_self_grading_cheating",
                "p3_cost_optimization",
                "p4_real_scenario_benchmark",
                "p5_cross_platform_verification",
            ]
        )
    )
