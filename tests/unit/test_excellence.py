"""Tests for 95+ excellence evidence scoring."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main
from src.platform_runs import validate_platform_run_artifact


def test_failed_live_external_artifact_is_invalid_for_score_evidence():
    """A failed live artifact must not count as live external evidence."""
    artifact = _platform_artifact(
        provider="codex",
        evidence_level="live_external",
        status="failed",
        success=False,
        output="",
    )

    validation = validate_platform_run_artifact(artifact)

    assert validation["valid"] is False
    assert validation["is_live_external"] is False
    assert "live_external artifacts must be completed successful runs" in validation["errors"]


def test_live_external_artifact_requires_nonempty_output_and_provenance():
    """Live evidence should be strong enough to audit after the fact."""
    artifact = _platform_artifact(
        provider="codex",
        evidence_level="live_external",
        status="completed",
        success=True,
        output="",
        command=[],
        source="",
    )

    validation = validate_platform_run_artifact(artifact)

    assert validation["valid"] is False
    assert validation["is_live_external"] is False
    assert "live_external artifacts require nonempty adapter output" in validation["errors"]
    assert "live_external artifacts require provenance source and command" in validation["errors"]


def test_excellence_readiness_stays_below_95_without_live_artifact(tmp_path: Path):
    """Readiness evidence alone must not be enough for a 95+ score."""
    from src.excellence import run_excellence_readiness

    _write_platform_matrix(tmp_path, include_live=False)

    result = run_excellence_readiness(tmp_path)

    assert result["status"] == "partial"
    assert result["recommended_score"] == 94
    assert result["metrics"]["live_external_artifacts"] == 0
    assert "LIVE_EXTERNAL_PLATFORM_RUNS" in result["remaining_findings"]
    assert _check_status(result, "live_external_task_artifact") == "fail"


def test_excellence_readiness_recommends_96_with_live_artifact(tmp_path: Path):
    """One valid live task plus matrix/adversarial/self-improvement evidence reaches 95+."""
    from src.excellence import run_excellence_readiness

    _write_platform_matrix(tmp_path, include_live=True)

    result = run_excellence_readiness(tmp_path)

    assert result["status"] == "completed"
    assert result["previous_score"] == 91
    assert result["recommended_score"] == 96
    assert result["score_delta"] == 5
    assert result["metrics"]["live_external_artifacts"] == 1
    assert result["metrics"]["represented_platforms"] == 4
    assert result["metrics"]["successful_platforms"] >= 3
    assert result["metrics"]["adversarial_checks_passed"] == 3
    assert result["self_improvement"]["status"] == "completed"
    assert _check_status(result, "live_external_task_artifact") == "pass"


def test_benchmark_excellence_suite_uses_existing_artifacts():
    """Benchmark runner should expose excellence score evidence."""
    from src.benchmark import run_benchmark

    result = run_benchmark("excellence", iterations=1)

    assert result["suite"] == "excellence"
    assert result["scorecard"]["current_score"] >= 95
    assert result["excellence_readiness"]["status"] == "completed"


def test_cli_benchmark_excellence_suite(tmp_path: Path):
    """CLI should generate machine-readable excellence benchmark evidence."""
    output_path = tmp_path / "benchmark-excellence.json"

    result = CliRunner().invoke(
        main,
        [
            "benchmark",
            "--suite",
            "excellence",
            "--iterations",
            "1",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "excellence"
    assert payload["scorecard"]["current_score"] >= 95
    assert payload["excellence_readiness"]["metrics"]["live_external_artifacts"] >= 1


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")


def _write_platform_matrix(path: Path, include_live: bool) -> None:
    providers = [
        ("codex", "completed", True, "codex local probe"),
        ("claude_code", "failed", False, ""),
        ("mimo_code", "completed", True, "mimo local probe"),
        ("hermes", "completed", True, "hermes local probe"),
    ]
    for provider, status, success, output in providers:
        artifact = _platform_artifact(
            provider=provider,
            evidence_level="local_command",
            status=status,
            success=success,
            output=output,
            task=f"{provider} local probe",
        )
        _write_json(path / f"{provider}-platform-run.json", artifact)

    if include_live:
        artifact = _platform_artifact(
            provider="codex",
            evidence_level="live_external",
            status="completed",
            success=True,
            output="UAEK_LIVE_TASK_OK",
            task="codex live excellence task",
            command=["codex", "exec", "Reply exactly UAEK_LIVE_TASK_OK"],
        )
        _write_json(path / "codex-live-platform-run.json", artifact)


def _platform_artifact(
    provider: str,
    evidence_level: str,
    status: str,
    success: bool,
    output: str,
    task: str = "excellence task",
    command: list[str] | None = None,
    source: str = "test fixture",
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
            "stderr": "",
            "artifacts": {},
            "metrics": {"steps": 1},
            "request": {"task": task, "context": {}, "metadata": {}},
            "error": None if success else "failed fixture",
        },
        "provenance": {
            "source": source,
            "command": command if command is not None else ["fixture", provider],
            "adapter_result_path": f"/tmp/{provider}-adapter-result.json",
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
