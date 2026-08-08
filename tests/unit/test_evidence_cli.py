from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from src.cli import main
from src.evidence.campaign import attach_sample_metadata


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _campaign(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "campaign.json",
        {
            "schema": "evidence_campaign_v1",
            "campaign_id": "fixture-campaign",
            "task_set_digest": "a" * 64,
            "grader_version": "capability-grader-v1",
            "artifact_dir": str(tmp_path / "runs"),
            "providers": [
                {
                    "provider": "fixture-runtime-a",
                    "backend_family": "fixture-family-a",
                    "command": ["fixture-agent"],
                    "output_mode": "plain",
                    "sample_count": 1,
                    "seed_start": 10,
                }
            ],
        },
    )


def _campaign_artifact(tmp_path: Path) -> Path:
    artifact = {
        "schema": "capability_run_v1",
        "provider": "fixture-runtime-a",
        "status": "completed",
        "evidence_level": "contract",
        "task_results": [{"task_id": "two_sum", "passed": 1, "total": 1, "status": "pass"}],
        "metrics": {"suite_pass_rate": 1.0},
        "provenance": {"source": "fixture", "command": ["fixture-agent"]},
        "error": None,
    }
    sample = {
        "campaign_id": "fixture-campaign",
        "provider": "fixture-runtime-a",
        "backend_family": "fixture-family-a",
        "sample_id": "fixture-runtime-a-001",
        "seed": 10,
        "task_set_digest": "a" * 64,
        "grader_version": "capability-grader-v1",
    }
    return _write(tmp_path / "artifact.json", attach_sample_metadata(artifact, sample))


def _cost_ledger(tmp_path: Path) -> Path:
    sessions = []
    for index, cohort in enumerate(("warm", "mixed", "cold"), start=1):
        sessions.append(
            {
                "session_id": f"cost-{index}",
                "cohort": cohort,
                "input_tokens": 10,
                "cache_read_tokens": 5,
                "cache_write_tokens": 1,
                "output_tokens": 2,
                "elapsed_seconds": 1,
                "session_gap_seconds": 30,
                "baseline_cost": 1.0,
                "measured_cost": 0.8,
            }
        )
    return _write(tmp_path / "cost.json", {"schema": "cost_evidence_v1", "sessions": sessions})


def _session(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "session.json",
        {
            "schema": "session_evidence_v1",
            "evidence_type": "deterministic_scenario",
            "scenario_id": "fixture-scenario",
            "grader_output": {"passed": True},
        },
    )


def test_evidence_campaign_validate_outputs_machine_json(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["evidence", "campaign", "validate", str(_campaign(tmp_path)), "--output", "-"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["valid"] is True


def test_evidence_campaign_aggregate_and_dry_run(tmp_path: Path) -> None:
    aggregate = CliRunner().invoke(
        main,
        [
            "evidence",
            "campaign",
            "aggregate",
            str(_campaign_artifact(tmp_path)),
            "--output",
            "-",
        ],
    )
    dry_run = CliRunner().invoke(
        main,
        ["evidence", "campaign", "run", str(_campaign(tmp_path)), "--dry-run", "--output", "-"],
    )

    assert aggregate.exit_code == 0
    assert json.loads(aggregate.output)["backend_family_count"] == 1
    assert dry_run.exit_code == 0
    assert json.loads(dry_run.output)["status"] == "dry_run"


def test_evidence_campaign_run_forwards_resume_flag(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_campaign(source: str, *, dry_run: bool, resume: bool) -> dict[str, object]:
        captured.update(source=source, dry_run=dry_run, resume=resume)
        return {"status": "completed"}

    monkeypatch.setattr("src.evidence.cli.run_campaign", fake_run_campaign)

    result = CliRunner().invoke(
        main,
        ["evidence", "campaign", "run", str(_campaign(tmp_path)), "--resume", "--output", "-"],
    )

    assert result.exit_code == 0
    assert captured["resume"] is True


def test_evidence_cost_and_session_commands_emit_json(tmp_path: Path) -> None:
    cost = _cost_ledger(tmp_path)
    session = _session(tmp_path)

    cost_result = CliRunner().invoke(
        main, ["evidence", "cost", "aggregate", str(cost), "--output", "-"]
    )
    session_result = CliRunner().invoke(
        main, ["evidence", "session", "aggregate", str(session), "--output", "-"]
    )

    assert cost_result.exit_code == 0
    assert set(json.loads(cost_result.output)["cohorts"]) == {"warm", "mixed", "cold"}
    assert session_result.exit_code == 0
    assert json.loads(session_result.output)["deterministic_scenario_count"] == 1


def test_evidence_cost_and_baseline_validation_commands(tmp_path: Path) -> None:
    baseline = _write(
        tmp_path / "baseline.json",
        {
            "status": "not_configured",
            "name": "external",
            "reason": "No authorized baseline is available.",
        },
    )
    cost_result = CliRunner().invoke(
        main, ["evidence", "cost", "validate", str(_cost_ledger(tmp_path)), "--output", "-"]
    )
    baseline_result = CliRunner().invoke(
        main, ["evidence", "baseline", "validate", str(baseline), "--output", "-"]
    )

    assert cost_result.exit_code == 0
    assert json.loads(cost_result.output)["valid"] is True
    assert baseline_result.exit_code == 0
    assert json.loads(baseline_result.output)["status"] == "not_configured"


def test_evidence_validation_file_output_ends_with_newline(tmp_path: Path) -> None:
    output = tmp_path / "validation.json"
    result = CliRunner().invoke(
        main,
        ["evidence", "session", "validate", str(_session(tmp_path)), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8").endswith("\n")
