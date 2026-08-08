from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from src.capability_tasks import get_task
from src.evidence.campaign import (
    aggregate_campaign,
    attach_sample_metadata,
    build_sample_plan,
    run_campaign,
    validate_campaign_artifact,
    validate_campaign_manifest,
)


def _campaign(**provider_overrides: Any) -> dict[str, Any]:
    artifact_dir = provider_overrides.pop("artifact_dir", None)
    provider = {
        "provider": "fixture-runtime",
        "backend_family": "fixture-family",
        "command": ["fixture-agent", "run"],
        "output_mode": "plain",
        "sample_count": 3,
        "seed_start": 101,
    }
    provider.update(provider_overrides)
    manifest = {
        "schema": "evidence_campaign_v1",
        "campaign_id": "fixture-campaign",
        "task_set_digest": "a" * 64,
        "grader_version": "0.3.0.dev1",
        "providers": [provider],
    }
    if artifact_dir is not None:
        manifest["artifact_dir"] = artifact_dir
    return manifest


def test_campaign_expands_provider_samples_with_backend_identity() -> None:
    validation = validate_campaign_manifest(_campaign())

    assert validation["valid"] is True
    plan = build_sample_plan(validation)
    assert [(p["backend_family"], p["sample_id"], p["seed"]) for p in plan] == [
        ("fixture-family", "fixture-runtime-001", 101),
        ("fixture-family", "fixture-runtime-002", 102),
        ("fixture-family", "fixture-runtime-003", 103),
    ]


def test_campaign_accepts_explicit_seed_and_sample_id_lists() -> None:
    validation = validate_campaign_manifest(
        _campaign(seeds=[7, 11], sample_ids=["sample-a", "sample-b"], sample_count=2)
    )

    assert validation["valid"] is True
    plan = build_sample_plan(validation)
    assert [(item["sample_id"], item["seed"]) for item in plan] == [
        ("sample-a", 7),
        ("sample-b", 11),
    ]


def test_campaign_rejects_secrets_zero_samples_and_duplicate_sample_ids() -> None:
    manifest = _campaign(
        command=["fixture-agent", "--token", "credential"],
        sample_count=0,
        seeds=[],
        sample_ids=["duplicate", "duplicate"],
    )
    validation = validate_campaign_manifest(manifest)

    assert validation["valid"] is False
    assert any("secret material" in error for error in validation["errors"])
    assert any("sample_count" in error for error in validation["errors"])
    assert any("duplicate sample_id" in error for error in validation["errors"])


def test_campaign_rejects_seed_count_mismatch_and_backend_omission() -> None:
    validation = validate_campaign_manifest(
        _campaign(backend_family="", sample_count=2, seeds=[1])
    )

    assert validation["valid"] is False
    assert any("backend_family" in error for error in validation["errors"])
    assert any("seeds" in error for error in validation["errors"])


def test_live_runner_adds_sample_environment_without_mutating_parent(monkeypatch) -> None:
    from src.capability_matrix import run_capability_suite_live

    captured: list[dict[str, str] | None] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.append(kwargs.get("env"))
        return subprocess.CompletedProcess(args[0], 0, stdout="not code", stderr="")

    monkeypatch.setattr("src.capability_matrix.subprocess.run", fake_run)
    monkeypatch.delenv("UAEK_SAMPLE_SEED", raising=False)

    run_capability_suite_live(
        provider="fixture-runtime",
        base_command=["fixture-agent"],
        tasks=(get_task("two_sum"),),
        environment={"UAEK_SAMPLE_SEED": "101"},
    )

    assert captured[0] is not None
    assert captured[0]["UAEK_SAMPLE_SEED"] == "101"
    assert "UAEK_SAMPLE_SEED" not in os.environ


def _sample(
    provider: str = "fixture-runtime",
    backend_family: str = "fixture-family",
    sample_id: str = "sample-1",
    seed: int = 1,
) -> dict[str, Any]:
    return {
        "campaign_id": "fixture-campaign",
        "provider": provider,
        "backend_family": backend_family,
        "sample_id": sample_id,
        "seed": seed,
        "task_set_digest": "a" * 64,
        "grader_version": "0.3.0.dev1",
    }


def _artifact(score: float = 1.0, *, error: str | None = None) -> dict[str, Any]:
    status = "completed" if error is None else "failed"
    return {
        "schema": "capability_run_v1",
        "provider": "fixture-runtime",
        "status": status,
        "evidence_level": "live_external",
        "task_results": [
            {
                "task_id": "two_sum",
                "passed": int(score > 0),
                "total": 1,
                "status": "pass" if error is None else "fail",
                "error": error,
            }
        ],
        "metrics": {
            "tasks_passed": int(score > 0),
            "tasks_attempted": 1,
            "suite_pass_rate": score,
        },
        "provenance": {"source": "fixture", "command": ["fixture-agent"]},
        "error": error,
    }


def _sample_artifact(
    provider: str,
    backend_family: str,
    sample_id: str,
    score: float,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    artifact = _artifact(score, error=error)
    artifact["provider"] = provider
    return attach_sample_metadata(artifact, _sample(provider, backend_family, sample_id))


def test_attach_metadata_is_immutable_and_valid() -> None:
    artifact = _artifact()
    attached = attach_sample_metadata(artifact, _sample())

    assert "sample" not in artifact
    assert attached["sample"]["sample_id"] == "sample-1"
    assert validate_campaign_artifact(attached)["valid"] is True


def test_aggregate_groups_aliases_by_backend_family() -> None:
    result = aggregate_campaign(
        [
            _sample_artifact("claude-shell", "mimo-family", "s1", 1.0),
            _sample_artifact("mimo-cli", "mimo-family", "s2", 0.8),
            _sample_artifact("codex", "openai-family", "s3", 1.0),
        ]
    )

    assert result["backend_family_count"] == 2
    assert result["backend_families"]["mimo-family"]["sample_count"] == 2
    assert result["backend_families"]["mimo-family"]["mean_score"] == 0.9


def test_aggregate_reports_timeout_and_failure_rates() -> None:
    result = aggregate_campaign(
        [
            _sample_artifact("fixture", "family", "s1", 1.0),
            _sample_artifact("fixture", "family", "s2", 0.0, error="provider timed out"),
            _sample_artifact("fixture", "family", "s3", 0.0, error="grader failure"),
        ]
    )

    assert result["totals"]["timeout_rate"] == pytest.approx(1 / 3)
    assert result["totals"]["failure_rate"] == pytest.approx(2 / 3)


def test_run_campaign_executes_every_resolved_sample_once(tmp_path: Path) -> None:
    manifest = _campaign(artifact_dir=str(tmp_path / "artifacts"))
    calls: list[str] = []

    def fixture_runner(sample: dict[str, Any]) -> dict[str, Any]:
        calls.append(sample["sample_id"])
        return _artifact()

    result = run_campaign(manifest, runner=fixture_runner)

    assert calls == ["fixture-runtime-001", "fixture-runtime-002", "fixture-runtime-003"]
    assert result["status"] == "completed"
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 3


def test_run_campaign_dry_run_never_calls_runner(tmp_path: Path) -> None:
    def forbidden_runner(sample: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError(f"runner called for {sample['sample_id']}")

    manifest = _campaign(artifact_dir=str(tmp_path / "artifacts"))
    result = run_campaign(manifest, runner=forbidden_runner, dry_run=True)

    assert result["status"] == "dry_run"
    assert len(result["sample_plan"]) == 3
    assert not (tmp_path / "artifacts").exists()
