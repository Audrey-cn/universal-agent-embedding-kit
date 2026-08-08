from __future__ import annotations

import os
import subprocess
from typing import Any

from src.capability_tasks import get_task
from src.evidence.campaign import build_sample_plan, validate_campaign_manifest


def _campaign(**provider_overrides: Any) -> dict[str, Any]:
    provider = {
        "provider": "fixture-runtime",
        "backend_family": "fixture-family",
        "command": ["fixture-agent", "run"],
        "output_mode": "plain",
        "sample_count": 3,
        "seed_start": 101,
    }
    provider.update(provider_overrides)
    return {
        "schema": "evidence_campaign_v1",
        "campaign_id": "fixture-campaign",
        "task_set_digest": "a" * 64,
        "grader_version": "0.3.0.dev1",
        "providers": [provider],
    }


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
