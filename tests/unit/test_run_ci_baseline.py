"""Tests for the next score-alignment release gates."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from src.cli import main


def test_cli_run_writes_harness_result(tmp_path: Path):
    """uaek run should expose the local harness as a reusable CLI entrypoint."""
    output_path = tmp_path / "run-result.json"
    memory_store = tmp_path / "memory"
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "run",
            "implement external adapter plan",
            "--output",
            str(output_path),
            "--memory-store",
            str(memory_store),
        ],
    )

    assert result.exit_code == 0
    assert "Harness" in result.output
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["task"] == "implement external adapter plan"
    assert payload["report"]["score"] == 1.0
    assert payload["memory"]["entry_id"]


def test_benchmark_accepts_external_baseline_file(tmp_path: Path):
    """Benchmark evidence should include provided external-baseline metadata."""
    from src.benchmark import run_benchmark

    baseline_path = tmp_path / "fable5-baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "name": "fable5",
                "status": "not_configured",
                "source": "example schema only",
                "metrics": {},
            }
        ),
        encoding="utf-8",
    )

    result = run_benchmark("quick", iterations=1, baseline_path=baseline_path)

    assert result["external_baseline"]["name"] == "fable5"
    assert result["external_baseline"]["status"] == "not_configured"
    assert result["external_baseline"]["path"].endswith("fable5-baseline.json")
    assert result["external_baseline"]["metrics"] == {}


def test_ci_workflow_defines_quality_gates():
    """CI should run the same local gates used to claim release readiness."""
    workflow_path = Path(".github/workflows/ci.yml")

    assert workflow_path.exists()
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert data["name"] == "CI"

    workflow_text = json.dumps(data, ensure_ascii=False)
    assert "ruff check src api mcp tests" in workflow_text
    assert "mypy src api mcp" in workflow_text
    assert "pytest" in workflow_text
    assert "--cov=src" in workflow_text
    assert "audit_passed" in workflow_text
    assert "errors" in workflow_text


def test_ci_workflow_uses_current_node24_actions():
    """CI should avoid action majors that emit GitHub's Node 20 deprecation warning."""
    data = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    uses = [
        step["uses"]
        for job in data["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]

    assert "actions/checkout@v7" in uses
    assert "actions/setup-python@v6" in uses
    assert "actions/checkout@v4" not in uses
    assert "actions/setup-python@v5" not in uses
