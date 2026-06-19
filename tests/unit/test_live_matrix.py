"""Tests for full live provider matrix scoring."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_live_matrix_scores_97_with_three_live_providers_and_one_blocked(tmp_path: Path):
    """A blocked provider should be diagnosed without pretending the matrix is full."""
    from src.live_matrix import run_live_matrix_readiness

    for provider in ["codex", "mimo_code", "hermes"]:
        _write_json(
            tmp_path / f"{provider}-live-platform-run.json",
            _platform_artifact(
                provider=provider,
                evidence_level="live_external",
                status="completed",
                success=True,
                output="UAEK_LIVE_TASK_OK",
                task=f"{provider} live matrix task",
            ),
        )
    _write_json(
        tmp_path / "claude-live-platform-run.json",
        _platform_artifact(
            provider="claude_code",
            evidence_level="live_external",
            status="failed",
            success=False,
            output="",
            error="Electron IndexedDB lock prevented headless run",
            task="claude live matrix task",
        ),
    )

    result = run_live_matrix_readiness(tmp_path)

    assert result["status"] == "partial"
    assert result["previous_score"] == 96
    assert result["recommended_score"] == 97
    assert result["metrics"]["live_provider_count"] == 3
    assert result["metrics"]["blocked_provider_count"] == 1
    assert result["metrics"]["missing_provider_count"] == 0
    assert "FULL_LIVE_PER_PLATFORM_MATRIX" in result["remaining_findings"]
    assert _provider_status(result, "claude_code")["status"] == "blocked"
    assert _check_status(result, "full_live_per_platform_matrix") == "fail"
    assert _check_status(result, "blocked_attempt_diagnostics") == "pass"


def test_live_matrix_scores_98_with_all_four_live_providers(tmp_path: Path):
    """Every expected provider needs valid live evidence before the full matrix closes."""
    from src.live_matrix import run_live_matrix_readiness

    for provider in ["codex", "claude_code", "mimo_code", "hermes"]:
        _write_json(
            tmp_path / f"{provider}-live-platform-run.json",
            _platform_artifact(
                provider=provider,
                evidence_level="live_external",
                status="completed",
                success=True,
                output="UAEK_LIVE_TASK_OK",
                task=f"{provider} live matrix task",
            ),
        )

    result = run_live_matrix_readiness(tmp_path)

    assert result["status"] == "completed"
    assert result["recommended_score"] == 98
    assert result["metrics"]["live_provider_count"] == 4
    assert result["remaining_findings"] == [
        "DIRECT_RETIRED_MODEL_UNAVAILABLE",
        "CI_REMOTE_UNVERIFIED",
    ]
    assert _check_status(result, "full_live_per_platform_matrix") == "pass"


def test_benchmark_live_matrix_suite_uses_existing_artifacts():
    """Benchmark runner should expose live matrix evidence separately from excellence."""
    from src.benchmark import run_benchmark

    result = run_benchmark("live_matrix", iterations=1)

    assert result["suite"] == "live_matrix"
    assert result["scorecard"]["previous_score"] == 96
    assert result["scorecard"]["current_score"] >= 96
    assert "live_matrix_readiness" in result


def test_cli_benchmark_live_matrix_suite(tmp_path: Path):
    """CLI should write live matrix benchmark evidence."""
    output_path = tmp_path / "benchmark-live_matrix.json"

    result = CliRunner().invoke(
        main,
        [
            "benchmark",
            "--suite",
            "live_matrix",
            "--iterations",
            "1",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "live_matrix"
    assert "live_matrix_readiness" in payload


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")


def _provider_status(result: dict, provider: str) -> dict:
    for item in result["provider_statuses"]:
        if item["provider"] == provider:
            return item
    raise AssertionError(f"missing provider {provider}")


def _platform_artifact(
    provider: str,
    evidence_level: str,
    status: str,
    success: bool,
    output: str,
    task: str,
    error: str | None = None,
) -> dict:
    return {
        "schema": "platform_run_v1",
        "run_id": f"platform-{provider}",
        "provider": provider,
        "task": task,
        "status": status,
        "evidence_level": evidence_level,
        "recorded_at": "2026-06-18T00:00:00+00:00",
        "adapter_result": {
            "provider": provider,
            "task": task,
            "success": success,
            "output": output,
            "trace_id": f"trace-{provider}",
            "return_code": 0 if success else 1,
            "duration_ms": 10.0,
            "stdout": output,
            "stderr": error or "",
            "artifacts": {},
            "metrics": {"steps": 1},
            "request": {"task": task, "context": {}, "metadata": {}},
            "error": error,
        },
        "provenance": {
            "source": "test fixture",
            "command": ["fixture", provider],
            "adapter_result_path": f"/tmp/{provider}-adapter-result.json",
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
