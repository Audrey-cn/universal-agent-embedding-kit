"""Tests for platform run artifact recording and readiness scoring."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_platform_discovery_declares_supported_local_tools():
    """Discovery should know the local platform names we want to validate."""
    from src.platform_runs import discover_platforms

    platforms = discover_platforms()
    providers = {platform["provider"] for platform in platforms}

    assert {"codex", "claude_code", "mimo_code", "hermes"}.issubset(providers)
    assert all("available" in platform for platform in platforms)


def test_platform_run_record_wraps_adapter_result_and_validates(tmp_path: Path):
    """Platform artifacts should preserve adapter provenance and validation state."""
    from src.platform_runs import record_platform_run, validate_platform_run_artifact

    adapter_result_path = _write_adapter_result(tmp_path)
    output_path = tmp_path / "platform-run.json"

    artifact = record_platform_run(
        adapter_result_path=adapter_result_path,
        provider="codex",
        evidence_level="local_command",
        output_path=output_path,
        source="uaek adapter run fixture",
        command=["codex", "exec", "fixture task"],
    )

    assert artifact["schema"] == "platform_run_v1"
    assert artifact["provider"] == "codex"
    assert artifact["task"] == "platform artifact task"
    assert artifact["status"] == "completed"
    assert artifact["evidence_level"] == "local_command"
    assert artifact["provenance"]["command"] == ["codex", "exec", "fixture task"]
    assert output_path.exists()

    validation = validate_platform_run_artifact(output_path)
    assert validation["valid"] is True
    assert validation["provider"] == "codex"
    assert validation["evidence_level"] == "local_command"
    assert validation["is_live_external"] is False
    assert validation["errors"] == []


def test_platform_run_validation_rejects_incomplete_artifacts(tmp_path: Path):
    """Validation should reject artifacts that cannot support score evidence."""
    from src.platform_runs import validate_platform_run_artifact

    invalid_path = tmp_path / "invalid-platform-run.json"
    invalid_path.write_text(
        json.dumps(
            {
                "schema": "platform_run_v1",
                "provider": "codex",
                "evidence_level": "pretend-live",
            }
        ),
        encoding="utf-8",
    )

    validation = validate_platform_run_artifact(invalid_path)

    assert validation["valid"] is False
    assert "task is required" in validation["errors"]
    assert "unsupported evidence_level: pretend-live" in validation["errors"]


def test_cli_platform_record_and_validate(tmp_path: Path):
    """CLI should record and validate platform run artifacts."""
    adapter_result_path = _write_adapter_result(tmp_path)
    platform_run_path = tmp_path / "platform-run.json"
    runner = CliRunner()

    record_result = runner.invoke(
        main,
        [
            "platform",
            "record",
            "--adapter-result",
            str(adapter_result_path),
            "--provider",
            "codex",
            "--evidence-level",
            "local_command",
            "--source",
            "cli test",
            "--command",
            "codex",
            "--command",
            "exec",
            "--output",
            str(platform_run_path),
        ],
    )

    assert record_result.exit_code == 0
    assert "Platform Run" in record_result.output
    assert platform_run_path.exists()

    validate_result = runner.invoke(main, ["platform", "validate", str(platform_run_path)])

    assert validate_result.exit_code == 0
    assert "valid" in validate_result.output.lower()


def test_cli_platform_discover_writes_provider_probe(tmp_path: Path):
    """CLI discovery should write machine-readable platform availability."""
    output_path = tmp_path / "platform-discovery.json"

    result = CliRunner().invoke(main, ["platform", "discover", "--output", str(output_path)])

    assert result.exit_code == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    providers = {platform["provider"] for platform in payload["platforms"]}
    assert {"codex", "claude_code", "mimo_code", "hermes"}.issubset(providers)


def test_benchmark_platform_suite_records_artifact_readiness_score(tmp_path: Path):
    """Platform benchmark should score artifact readiness without claiming live runs."""
    from src.benchmark import run_benchmark, write_benchmark_result

    result = run_benchmark("platform", iterations=1)

    assert result["suite"] == "platform"
    assert result["status"] == "completed"
    assert result["scorecard"]["previous_score"] == 90
    assert result["scorecard"]["current_score"] == 91
    assert "F018_PLATFORM_RUN_ARTIFACTS" in result["scorecard"]["resolved_findings"]
    assert "LIVE_EXTERNAL_PLATFORM_RUNS" in result["scorecard"]["remaining_findings"]
    assert result["platform_run_readiness"]["status"] == "completed"
    assert result["platform_run_readiness"]["artifact_schema"] == "platform_run_v1"
    assert result["platform_run_readiness"]["metrics"]["passed_required_checks"] == 3
    assert result["platform_run_readiness"]["metrics"]["known_platforms"] >= 4

    output_path = write_benchmark_result(result, tmp_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["scorecard"]["current_score"] == 91
    assert data["platform_run_readiness"]["metrics"]["live_external_artifacts"] == 0


def _write_adapter_result(tmp_path: Path) -> Path:
    adapter_result_path = tmp_path / "adapter-result.json"
    adapter_result_path.write_text(
        json.dumps(
            {
                "provider": "codex",
                "task": "platform artifact task",
                "success": True,
                "output": "platform artifact output",
                "trace_id": "trace-platform-001",
                "return_code": 0,
                "duration_ms": 12.5,
                "stdout": "{\"success\": true}",
                "stderr": "",
                "artifacts": {"file": "result.txt"},
                "metrics": {"steps": 1},
                "request": {"task": "platform artifact task", "context": {}, "metadata": {}},
                "error": None,
            }
        ),
        encoding="utf-8",
    )
    return adapter_result_path
