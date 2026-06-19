"""Excellence evidence scoring for 95+ product maturity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.platform_runs import validate_platform_run_artifact

DEFAULT_PLATFORM_RUN_DIR = Path("benchmarks/results/platform-runs")
EXPECTED_PROVIDERS = {"codex", "claude_code", "mimo_code", "hermes"}


def run_excellence_readiness(artifact_dir: Path | str = DEFAULT_PLATFORM_RUN_DIR) -> dict[str, Any]:
    """Evaluate 95+ evidence readiness from platform run artifacts."""
    artifact_path = Path(artifact_dir)
    artifacts = _load_platform_artifacts(artifact_path)
    validations = [_validated_artifact(path, data) for path, data in artifacts]

    represented = {item["provider"] for item in validations if item["provider"]}
    successful = {
        item["provider"]
        for item in validations
        if item["valid"] and item["status"] == "completed" and item["adapter_success"]
    }
    live_external = [item for item in validations if item["is_live_external"]]
    adversarial = _run_adversarial_checks()

    metrics: dict[str, Any] = {
        "platform_artifacts": len(validations),
        "valid_artifacts": sum(1 for item in validations if item["valid"]),
        "represented_platforms": len(represented),
        "successful_platforms": len(successful),
        "expected_platforms": len(EXPECTED_PROVIDERS),
        "live_external_artifacts": len(live_external),
        "adversarial_checks": len(adversarial),
        "adversarial_checks_passed": sum(1 for item in adversarial if item["status"] == "pass"),
    }
    self_improvement = _run_self_improvement_loop(metrics)

    checks = [
        {
            "id": "live_external_task_artifact",
            "required": True,
            "status": "pass" if metrics["live_external_artifacts"] >= 1 else "fail",
            "evidence": f"{metrics['live_external_artifacts']} valid live external task artifacts",
        },
        {
            "id": "cross_platform_artifact_matrix",
            "required": True,
            "status": (
                "pass"
                if represented.issuperset(EXPECTED_PROVIDERS)
                and metrics["successful_platforms"] >= 3
                else "fail"
            ),
            "evidence": (
                f"{metrics['represented_platforms']}/4 providers represented; "
                f"{metrics['successful_platforms']} providers have successful artifacts"
            ),
        },
        {
            "id": "adversarial_live_validation",
            "required": True,
            "status": (
                "pass"
                if metrics["adversarial_checks_passed"] == metrics["adversarial_checks"]
                else "fail"
            ),
            "evidence": (
                f"{metrics['adversarial_checks_passed']}/{metrics['adversarial_checks']} "
                "adversarial artifact checks passed"
            ),
        },
        {
            "id": "self_improvement_score_loop",
            "required": True,
            "status": "pass" if self_improvement["status"] == "completed" else "fail",
            "evidence": ", ".join(self_improvement["resolved_findings"]),
        },
    ]
    required = [check for check in checks if check["required"]]
    passed_required = [check for check in required if check["status"] == "pass"]
    all_required_pass = len(passed_required) == len(required)

    metrics["required_checks"] = len(required)
    metrics["passed_required_checks"] = len(passed_required)
    metrics["excellence_pass_rate"] = round(len(passed_required) / len(required), 4)

    recommended_score = 96 if all_required_pass else _partial_score(checks)
    return {
        "status": "completed" if all_required_pass else "partial",
        "artifact_dir": str(artifact_path),
        "expected_providers": sorted(EXPECTED_PROVIDERS),
        "checks": checks,
        "adversarial_checks": adversarial,
        "self_improvement": self_improvement,
        "metrics": metrics,
        "previous_score": 91,
        "recommended_score": recommended_score,
        "score_delta": recommended_score - 91,
        "resolved_findings": _resolved_findings(checks),
        "remaining_findings": _remaining_findings(checks),
        "limitations": [
            "Excellence readiness is not a retired Fable 5 rerun.",
            "A single live_external artifact does not prove every platform completed a live task.",
            "Remote CI and release publication remain separate evidence tracks.",
        ],
    }


def _load_platform_artifacts(artifact_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
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
    return {
        "path": str(path),
        "provider": validation["provider"],
        "status": validation["status"],
        "evidence_level": validation["evidence_level"],
        "valid": validation["valid"],
        "errors": validation["errors"],
        "is_live_external": validation["is_live_external"],
        "adapter_success": validation["adapter_success"],
    }


def _run_adversarial_checks() -> list[dict[str, Any]]:
    checks = [
        (
            "failed_live_not_counted",
            _artifact_fixture("codex", "live_external", "failed", False, "failed"),
            False,
        ),
        (
            "empty_live_output_rejected",
            _artifact_fixture("codex", "live_external", "completed", True, ""),
            False,
        ),
        (
            "local_command_not_live",
            _artifact_fixture("codex", "local_command", "completed", True, "ok"),
            True,
        ),
    ]
    results: list[dict[str, Any]] = []
    for check_id, artifact, expected_valid in checks:
        validation = validate_platform_run_artifact(artifact)
        status = "pass"
        if validation["valid"] != expected_valid:
            status = "fail"
        if check_id == "local_command_not_live" and validation["is_live_external"]:
            status = "fail"
        results.append(
            {
                "id": check_id,
                "status": status,
                "valid": validation["valid"],
                "is_live_external": validation["is_live_external"],
                "errors": validation["errors"],
            }
        )
    return results


def _run_self_improvement_loop(metrics: dict[str, Any]) -> dict[str, Any]:
    open_findings = [
        "LIVE_EXTERNAL_PLATFORM_RUNS",
        "FULL_CROSS_PLATFORM_MATRIX",
        "ADVERSARIAL_SELF_IMPROVEMENT_SUITE",
    ]
    resolved: list[str] = []
    if metrics["live_external_artifacts"] >= 1:
        resolved.append("LIVE_EXTERNAL_PLATFORM_RUNS")
    if metrics["represented_platforms"] >= 4 and metrics["successful_platforms"] >= 3:
        resolved.append("FULL_CROSS_PLATFORM_MATRIX")
    if metrics["adversarial_checks"] and (
        metrics["adversarial_checks_passed"] == metrics["adversarial_checks"]
    ):
        resolved.append("ADVERSARIAL_SELF_IMPROVEMENT_SUITE")

    remaining = [finding for finding in open_findings if finding not in resolved]
    return {
        "status": "completed" if not remaining else "partial",
        "before_score": 91,
        "after_score": 96 if not remaining else 94,
        "open_findings_before": open_findings,
        "resolved_findings": resolved,
        "remaining_findings": remaining,
    }


def _remaining_findings(checks: list[dict[str, Any]]) -> list[str]:
    remaining = ["DIRECT_RETIRED_MODEL_UNAVAILABLE", "CI_REMOTE_UNVERIFIED"]
    status_by_id = {check["id"]: check["status"] for check in checks}
    if status_by_id["live_external_task_artifact"] != "pass":
        remaining.append("LIVE_EXTERNAL_PLATFORM_RUNS")
    else:
        remaining.append("FULL_LIVE_PER_PLATFORM_MATRIX")
    if status_by_id["cross_platform_artifact_matrix"] != "pass":
        remaining.append("FULL_CROSS_PLATFORM_MATRIX")
    if status_by_id["adversarial_live_validation"] != "pass":
        remaining.append("ADVERSARIAL_VALIDATION_SUITE")
    if status_by_id["self_improvement_score_loop"] != "pass":
        remaining.append("ADVERSARIAL_SELF_IMPROVEMENT_SUITE")
    return remaining


def _resolved_findings(checks: list[dict[str, Any]]) -> list[str]:
    resolved = ["F018_PLATFORM_RUN_ARTIFACTS"]
    status_by_id = {check["id"]: check["status"] for check in checks}
    if status_by_id["live_external_task_artifact"] == "pass":
        resolved.append("F017_LIVE_EXTERNAL_TASK_ARTIFACT")
    if status_by_id["cross_platform_artifact_matrix"] == "pass":
        resolved.append("F019_CROSS_PLATFORM_ARTIFACT_MATRIX")
    if status_by_id["adversarial_live_validation"] == "pass":
        resolved.append("F020_ADVERSARIAL_LIVE_VALIDATION")
    if status_by_id["self_improvement_score_loop"] == "pass":
        resolved.append("F021_SELF_IMPROVEMENT_SCORE_LOOP")
    return resolved


def _partial_score(checks: list[dict[str, Any]]) -> int:
    status_by_id = {check["id"]: check["status"] for check in checks}
    if (
        status_by_id["cross_platform_artifact_matrix"] == "pass"
        and status_by_id["adversarial_live_validation"] == "pass"
    ):
        return 94
    passed = sum(1 for check in checks if check["status"] == "pass")
    return min(94, 91 + passed)


def _artifact_fixture(
    provider: str,
    evidence_level: str,
    status: str,
    success: bool,
    output: str,
) -> dict[str, Any]:
    return {
        "schema": "platform_run_v1",
        "run_id": f"fixture-{provider}",
        "provider": provider,
        "task": "adversarial fixture",
        "status": status,
        "evidence_level": evidence_level,
        "recorded_at": "2026-06-18T00:00:00+00:00",
        "adapter_result": {
            "provider": provider,
            "task": "adversarial fixture",
            "success": success,
            "output": output,
            "trace_id": f"trace-{provider}",
            "return_code": 0 if success else 1,
            "duration_ms": 1.0,
            "stdout": output,
            "stderr": "",
            "artifacts": {},
            "metrics": {},
            "request": {"task": "adversarial fixture", "context": {}, "metadata": {}},
            "error": None if success else "fixture failure",
        },
        "provenance": {
            "source": "adversarial fixture",
            "command": ["fixture", provider],
            "adapter_result_path": f"/tmp/{provider}.json",
        },
    }
