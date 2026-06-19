"""Tests for quick score alignment features."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_benchmark_runner_writes_score_evidence(tmp_path: Path):
    """Benchmark runner should produce reusable JSON score evidence."""
    from src.benchmark import run_benchmark, write_benchmark_result

    result = run_benchmark("quick", iterations=2)

    assert result["suite"] == "quick"
    assert result["status"] == "completed"
    assert result["external_baseline"]["status"] == "not_configured"
    assert result["scorecard"]["previous_score"] == 68
    assert result["scorecard"]["current_score"] >= 74
    assert "F009" in result["scorecard"]["resolved_findings"]
    assert "F007" in result["scorecard"]["remaining_findings"]
    assert result["metrics"]["effort_latency_ms"] >= 0

    output_path = write_benchmark_result(result, tmp_path / "quick-score.json")
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["suite"] == "quick"
    assert data["scorecard"]["current_score"] == result["scorecard"]["current_score"]


def test_cli_benchmark_writes_result_file(tmp_path: Path):
    """CLI benchmark command should write a result JSON file."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["benchmark", "--suite", "quick", "--iterations", "2", "--output", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Score" in result.output
    output_path = tmp_path / "benchmark-quick.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["suite"] == "quick"
    assert data["scorecard"]["current_score"] >= 74


def test_local_harness_runs_full_pipeline(tmp_path: Path):
    """Local harness should run task -> effort -> workflow -> verify -> memory -> report."""
    from src.harness import AgentHarness, HarnessRequest
    from src.memory import MemoryService

    memory_service = MemoryService(tmp_path / "memory")
    harness = AgentHarness(memory_service=memory_service)

    result = harness.run(HarnessRequest(task="implement benchmark evidence pipeline"))
    payload = result.to_dict()

    assert result.success is True
    assert payload["effort"]["level"]
    assert payload["workflow"]["success"] is True
    assert payload["verification"]["passed"] is True
    assert payload["memory"]["entry_id"]
    assert payload["report"]["score"] == 1.0

    query_result = memory_service.query("benchmark evidence", layer="l2")
    assert query_result["total"] == 1
    assert "benchmark evidence pipeline" in query_result["results"][0]["content"]
