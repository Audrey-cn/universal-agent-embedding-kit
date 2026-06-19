"""Live external task matrix scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.platform_runs import validate_platform_run_artifact

DEFAULT_PLATFORM_RUN_DIR = Path("benchmarks/results/platform-runs")
EXPECTED_PROVIDERS = {"codex", "claude_code", "mimo_code", "hermes"}


def run_live_matrix_readiness(
    artifact_dir: Path | str = DEFAULT_PLATFORM_RUN_DIR,
) -> dict[str, Any]:
    """Evaluate live_external coverage across all expected Agent platforms."""
    artifact_path = Path(artifact_dir)
    artifacts = [_validated_artifact(path, data) for path, data in _load_artifacts(artifact_path)]
    provider_statuses = [
        _provider_status(provider, artifacts) for provider in sorted(EXPECTED_PROVIDERS)
    ]

    live_provider_count = sum(1 for item in provider_statuses if item["status"] == "live")
    blocked_provider_count = sum(1 for item in provider_statuses if item["status"] == "blocked")
    missing_provider_count = sum(
        1 for item in provider_statuses if item["status"] in {"missing", "missing_live"}
    )
    full_matrix = live_provider_count == len(EXPECTED_PROVIDERS)
    diagnostics_ready = all(
        item["status"] in {"live", "blocked"} for item in provider_statuses
    )

    checks = [
        {
            "id": "full_live_per_platform_matrix",
            "required": True,
            "status": "pass" if full_matrix else "fail",
            "evidence": f"{live_provider_count}/4 providers have valid live_external artifacts",
        },
        {
            "id": "blocked_attempt_diagnostics",
            "required": True,
            "status": "pass" if diagnostics_ready else "fail",
            "evidence": (
                f"{blocked_provider_count} blocked providers; "
                f"{missing_provider_count} providers missing live diagnostics"
            ),
        },
    ]

    recommended_score = _recommended_score(full_matrix, live_provider_count, diagnostics_ready)
    return {
        "status": "completed" if full_matrix else "partial",
        "artifact_dir": str(artifact_path),
        "expected_providers": sorted(EXPECTED_PROVIDERS),
        "provider_statuses": provider_statuses,
        "checks": checks,
        "metrics": {
            "platform_artifacts": len(artifacts),
            "expected_provider_count": len(EXPECTED_PROVIDERS),
            "live_provider_count": live_provider_count,
            "blocked_provider_count": blocked_provider_count,
            "missing_provider_count": missing_provider_count,
            "live_matrix_pass_rate": round(live_provider_count / len(EXPECTED_PROVIDERS), 4),
        },
        "previous_score": 96,
        "recommended_score": recommended_score,
        "score_delta": recommended_score - 96,
        "resolved_findings": _resolved_findings(full_matrix, recommended_score),
        "remaining_findings": _remaining_findings(full_matrix, diagnostics_ready),
        "limitations": [
            "Live matrix readiness does not claim a retired Fable 5 rerun.",
            "A blocked provider is diagnostic evidence, not live success evidence.",
            "Remote CI and release publication remain separate evidence tracks.",
        ],
    }


def _load_artifacts(artifact_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not artifact_dir.exists():
        return []
    artifacts: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(artifact_dir.glob("*-platform-run.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            artifacts.append((path, data))
    return artifacts


def _validated_artifact(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    validation = validate_platform_run_artifact(data)
    adapter_result = data.get("adapter_result")
    error = ""
    if isinstance(adapter_result, dict):
        error = str(adapter_result.get("error") or adapter_result.get("stderr") or "")
    return {
        "path": str(path),
        "provider": validation["provider"],
        "status": validation["status"],
        "evidence_level": validation["evidence_level"],
        "valid": validation["valid"],
        "errors": validation["errors"],
        "is_live_external": validation["is_live_external"],
        "adapter_success": validation["adapter_success"],
        "error": error,
    }


def _provider_status(provider: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    provider_artifacts = [item for item in artifacts if item["provider"] == provider]
    live_artifacts = [item for item in provider_artifacts if item["is_live_external"]]
    live_attempts = [
        item for item in provider_artifacts if item["evidence_level"] == "live_external"
    ]

    if live_artifacts:
        return {
            "provider": provider,
            "status": "live",
            "live_artifacts": len(live_artifacts),
            "attempted_live_artifacts": len(live_attempts),
            "evidence_paths": [item["path"] for item in live_artifacts],
            "errors": [],
        }
    if live_attempts:
        errors = _flatten_errors(live_attempts)
        return {
            "provider": provider,
            "status": "blocked",
            "live_artifacts": 0,
            "attempted_live_artifacts": len(live_attempts),
            "evidence_paths": [item["path"] for item in live_attempts],
            "errors": errors,
        }
    if provider_artifacts:
        return {
            "provider": provider,
            "status": "missing_live",
            "live_artifacts": 0,
            "attempted_live_artifacts": 0,
            "evidence_paths": [item["path"] for item in provider_artifacts],
            "errors": ["provider has artifacts but no live_external attempt"],
        }
    return {
        "provider": provider,
        "status": "missing",
        "live_artifacts": 0,
        "attempted_live_artifacts": 0,
        "evidence_paths": [],
        "errors": ["provider has no platform artifacts"],
    }


def _flatten_errors(artifacts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for item in artifacts:
        errors.extend(str(error) for error in item["errors"])
        if item["error"]:
            errors.append(str(item["error"]))
    return errors or ["live_external attempt did not produce valid live evidence"]


def _recommended_score(full_matrix: bool, live_provider_count: int, diagnostics_ready: bool) -> int:
    if full_matrix:
        return 98
    if live_provider_count >= 3 and diagnostics_ready:
        return 97
    return 96


def _resolved_findings(full_matrix: bool, recommended_score: int) -> list[str]:
    resolved = ["F017_LIVE_EXTERNAL_TASK_ARTIFACT"]
    if recommended_score >= 97:
        resolved.append("F022_LIVE_MATRIX_PARTIAL")
    if full_matrix:
        resolved.append("F023_FULL_LIVE_PER_PLATFORM_MATRIX")
    return resolved


def _remaining_findings(full_matrix: bool, diagnostics_ready: bool) -> list[str]:
    remaining = ["DIRECT_RETIRED_MODEL_UNAVAILABLE", "CI_REMOTE_UNVERIFIED"]
    if not full_matrix:
        remaining.append("FULL_LIVE_PER_PLATFORM_MATRIX")
    if not diagnostics_ready:
        remaining.append("LIVE_MATRIX_DIAGNOSTICS_INCOMPLETE")
    return remaining
