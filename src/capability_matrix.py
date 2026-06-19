"""Capability run artifacts and auto-graded cross-platform task matrix scoring.

This layer upgrades live evidence from "the platform launched" (live_matrix) to
"the platform solved real, objectively-graded code tasks". Each capability run
artifact records, per provider, how many tasks were fully passed by an isolated
test harness — not by model self-grading.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.capability_tasks import (
    CAPABILITY_TASKS,
    CapabilityTask,
    compute_capability_score,
    extract_code,
    grade_code,
    hardest_tier_passed,
    suite_difficulty_summary,
)

CAPABILITY_SCHEMA = "capability_run_v1"
RUN_STATUSES = {"completed", "failed"}
EVIDENCE_LEVELS = {"contract", "local_command", "live_external"}
EXPECTED_PROVIDERS = {"codex", "claude_code", "mimo_code", "hermes"}
DEFAULT_CAPABILITY_RUN_DIR = Path("benchmarks/results/capability-runs")

# Output extraction modes for live provider drivers.
OUTPUT_MODES = {"plain", "mimo_jsonl"}
BATCH_SCHEMA = "capability_batch_run_v1"


# --------------------------------------------------------------------------- #
# Live driver
# --------------------------------------------------------------------------- #
def run_capability_suite_live(
    provider: str,
    base_command: list[str] | tuple[str, ...],
    output_mode: str = "plain",
    provider_home: str | None = None,
    provider_home_seed_paths: tuple[str, ...] = (),
    tasks: tuple[CapabilityTask, ...] = CAPABILITY_TASKS,
    timeout: float = 120.0,
    source: str = "uaek capability run",
) -> dict[str, Any]:
    """Drive a provider command through the task suite and grade every answer.

    The task prompt is appended to ``base_command`` for each task. The provider's
    stdout is decoded according to ``output_mode``, candidate code is extracted
    and graded, and a ``capability_run_v1`` artifact is returned.
    """
    if output_mode not in OUTPUT_MODES:
        raise ValueError(f"Unsupported output_mode: {output_mode}")
    if provider_home is None and provider_home_seed_paths:
        raise ValueError("provider_home_seed_paths require provider_home")
    base = list(base_command)
    if not base:
        raise ValueError("run_capability_suite_live requires a base command")

    run_env = _build_run_environment(provider_home, provider_home_seed_paths)

    task_results: list[dict[str, Any]] = []
    for task in tasks:
        task_results.append(
            _run_one_task(
                base,
                task,
                output_mode,
                timeout,
                run_env,
            )
        )

    metrics = _suite_metrics(task_results)
    status = "completed" if metrics["tasks_passed"] >= 1 else "failed"
    first_error = next((item["error"] for item in task_results if item.get("error")), None)

    return {
        "schema": CAPABILITY_SCHEMA,
        "run_id": f"capability-{uuid4()}",
        "provider": provider,
        "task": f"{provider} capability suite ({len(tasks)} code tasks)",
        "status": status,
        "evidence_level": "live_external",
        "recorded_at": datetime.now(UTC).isoformat(),
        "suite": {"task_count": len(tasks), "task_ids": [task.task_id for task in tasks]},
        "task_results": task_results,
        "metrics": metrics,
        "provenance": {
            "source": source,
            "command": base,
            "output_mode": output_mode,
            "provider_home": provider_home,
            "provider_home_seed_paths": list(provider_home_seed_paths),
        },
        "error": None if status == "completed" else (first_error or "no task fully passed"),
    }


def _run_one_task(
    base: list[str],
    task: CapabilityTask,
    output_mode: str,
    timeout: float,
    run_env: dict[str, str] | None,
) -> dict[str, Any]:
    command = [*base, task.prompt]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        graded = {
            "task_id": task.task_id,
            "entrypoint": task.entrypoint,
            "difficulty": task.difficulty,
            "passed": 0,
            "total": len(task.cases),
            "pass_rate": 0.0,
            "status": "fail",
            "cases": [],
            "error": f"provider timed out after {timeout:g}s",
        }
        graded["duration_ms"] = _duration_ms(started)
        graded["code"] = ""
        return graded

    text = _decode_output(completed.stdout or "", output_mode)
    if completed.returncode != 0 and not text.strip():
        graded = {
            "task_id": task.task_id,
            "entrypoint": task.entrypoint,
            "difficulty": task.difficulty,
            "passed": 0,
            "total": len(task.cases),
            "pass_rate": 0.0,
            "status": "fail",
            "cases": [],
            "error": (completed.stderr or "provider returned no output").strip()[-300:],
        }
        graded["duration_ms"] = _duration_ms(started)
        graded["code"] = ""
        return graded

    code = extract_code(text)
    graded = grade_code(task, code)
    graded["code"] = code
    graded["duration_ms"] = _duration_ms(started)
    return graded


def _decode_output(stdout: str, output_mode: str) -> str:
    if output_mode == "plain":
        return stdout
    # mimo_jsonl: concatenate text parts from streamed JSONL events.
    parts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            part = event.get("part", {})
            text = part.get("text") if isinstance(part, dict) else None
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _build_run_environment(
    provider_home: str | None,
    seed_paths: tuple[str, ...] = (),
) -> dict[str, str] | None:
    """Build a provider-specific subprocess environment.

    Some provider CLIs write SQLite/WAL logs under HOME-related directories.
    When a writable provider_home is provided, redirect common writable paths
    to avoid permission-related failures in restricted execution contexts.
    """
    if provider_home is None:
        return None

    home_path = os.path.abspath(os.fspath(provider_home))
    os.makedirs(home_path, exist_ok=True)
    os.makedirs(os.path.join(home_path, ".config"), exist_ok=True)
    os.makedirs(os.path.join(home_path, ".cache"), exist_ok=True)
    os.makedirs(os.path.join(home_path, ".local", "share"), exist_ok=True)
    _seed_provider_home(home_path, seed_paths)

    env = os.environ.copy()
    env["HOME"] = home_path
    env["XDG_CONFIG_HOME"] = os.path.join(home_path, ".config")
    env["XDG_CACHE_HOME"] = os.path.join(home_path, ".cache")
    env["XDG_DATA_HOME"] = os.path.join(home_path, ".local", "share")
    return env


def _seed_provider_home(home_path: str, seed_paths: tuple[str, ...]) -> None:
    """Copy explicit config seeds into an isolated provider HOME.

    Absolute paths inside the caller's current HOME keep their relative layout,
    e.g. ``/Users/me/.hermes/config.yaml`` becomes
    ``<provider_home>/.hermes/config.yaml``.
    """
    if not seed_paths:
        return

    source_home = Path(os.path.expanduser("~")).resolve()
    target_home = Path(home_path)
    for seed in seed_paths:
        source = Path(os.path.expanduser(seed)).resolve()
        if not source.exists():
            raise FileNotFoundError(f"provider home seed does not exist: {source}")
        try:
            relative_target = source.relative_to(source_home)
        except ValueError:
            relative_target = Path(source.name)
        target = target_home / relative_target
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("logs", "sessions", "__pycache__"),
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def run_capability_manifest(
    manifest_path: Path | str,
    output_dir: Path | str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run a batch of provider capability recipes from a JSON manifest."""
    manifest_file = Path(manifest_path)
    validation = validate_capability_manifest(manifest_file, output_dir=output_dir, timeout=timeout)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    artifact_dir = Path(validation["artifact_dir"])

    runs: list[dict[str, Any]] = []
    for recipe in validation["providers"]:
        artifact = run_capability_suite_live(
            provider=recipe["provider"],
            base_command=recipe["command"],
            output_mode=recipe["output_mode"],
            provider_home=recipe["provider_home"],
            provider_home_seed_paths=tuple(recipe["provider_home_seed_paths"]),
            timeout=recipe["timeout"],
            source=f"uaek capability batch:{manifest_file}",
        )
        artifact_path = write_capability_run(artifact, artifact_dir / recipe["artifact_name"])
        validation = validate_capability_run_artifact(artifact)
        runs.append(
            {
                "provider": recipe["provider"],
                "artifact_path": str(artifact_path),
                "status": artifact["status"],
                "metrics": artifact["metrics"],
                "validation": validation,
            }
        )

    matrix = run_capability_readiness(artifact_dir)
    return {
        "schema": BATCH_SCHEMA,
        "manifest_path": str(manifest_file),
        "artifact_dir": str(artifact_dir),
        "status": "completed"
        if all(item["validation"]["is_graded_live"] for item in runs)
        else "partial",
        "runs": runs,
        "matrix": matrix,
    }


def validate_capability_manifest(
    manifest_path: Path | str,
    output_dir: Path | str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Validate and resolve a capability batch manifest without running providers."""
    manifest_file = Path(manifest_path)
    manifest = _load_manifest(manifest_file)
    errors: list[str] = []
    warnings: list[str] = []
    resolved_providers: list[dict[str, Any]] = []

    artifact_dir = _manifest_path(output_dir or manifest.get("artifact_dir"))
    provider_home_root = manifest.get("provider_home_root")
    provider_home_root_path = (
        _manifest_path(provider_home_root) if provider_home_root is not None else None
    )
    try:
        default_timeout = float(timeout if timeout is not None else manifest.get("timeout", 120.0))
    except (TypeError, ValueError):
        errors.append("timeout must be numeric")
        default_timeout = 120.0

    provider_recipes = manifest.get("providers")
    if not isinstance(provider_recipes, list) or not provider_recipes:
        errors.append("capability manifest requires a non-empty providers list")
        provider_recipes = []

    seen: set[str] = set()
    for index, recipe in enumerate(provider_recipes):
        if not isinstance(recipe, dict):
            errors.append(f"providers[{index}] must be an object")
            continue
        try:
            provider = _required_string(recipe, "provider", index)
            command = _required_string_list(recipe, "command", index)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if provider in seen:
            errors.append(f"providers[{index}].provider duplicates {provider}")
        seen.add(provider)

        output_mode = str(recipe.get("output_mode", "plain"))
        if output_mode not in OUTPUT_MODES:
            errors.append(f"providers[{index}].output_mode unsupported: {output_mode}")

        provider_home = recipe.get("provider_home")
        if provider_home is None and provider_home_root_path is not None:
            provider_home = str(provider_home_root_path / provider)
        seed_paths = _optional_string_list(recipe, "provider_home_seed_paths", index, errors)
        if seed_paths and provider_home is None:
            errors.append(f"providers[{index}].provider_home_seed_paths require provider_home")
        for seed in seed_paths:
            if not Path(os.path.expanduser(seed)).exists():
                warnings.append(f"providers[{index}] seed path not found locally: {seed}")

        try:
            run_timeout = float(recipe.get("timeout", default_timeout))
        except (TypeError, ValueError):
            errors.append(f"providers[{index}].timeout must be numeric")
            run_timeout = default_timeout

        artifact_name = str(recipe.get("artifact_name", f"{provider}-capability-run.json"))
        resolved_providers.append(
            {
                "provider": provider,
                "command": command,
                "output_mode": output_mode,
                "provider_home": str(provider_home) if provider_home is not None else None,
                "provider_home_seed_paths": seed_paths,
                "timeout": run_timeout,
                "artifact_name": artifact_name,
            }
        )

    missing_expected = sorted(EXPECTED_PROVIDERS - set(seen))
    if missing_expected:
        warnings.append(f"manifest does not cover expected providers: {missing_expected}")

    return {
        "schema": "capability_manifest_validation_v1",
        "manifest_path": str(manifest_file),
        "artifact_dir": str(artifact_dir),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "providers": resolved_providers,
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("capability manifest must be a JSON object")
    return data


def _manifest_path(value: Path | str | Any) -> Path:
    if value is None:
        return DEFAULT_CAPABILITY_RUN_DIR
    return Path(os.path.expanduser(os.fspath(value)))


def _required_string(recipe: dict[str, Any], field: str, index: int) -> str:
    value = recipe.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"providers[{index}].{field} must be a non-empty string")
    return value


def _required_string_list(recipe: dict[str, Any], field: str, index: int) -> list[str]:
    value = recipe.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ValueError(f"providers[{index}].{field} must be a non-empty list of strings")
    return list(value)


def _optional_string_list(
    recipe: dict[str, Any],
    field: str,
    index: int,
    errors: list[str],
) -> list[str]:
    value = recipe.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"providers[{index}].{field} must be a list of strings")
        return []
    return list(value)


# --------------------------------------------------------------------------- #
# Recording
# --------------------------------------------------------------------------- #
def write_capability_run(artifact: dict[str, Any], output_path: Path | str) -> Path:
    """Write a capability run artifact to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_capability_run_artifact(
    artifact: Path | str | dict[str, Any],
) -> dict[str, Any]:
    """Validate a capability_run_v1 artifact and return structured diagnostics."""
    data = _load_artifact(artifact)
    errors: list[str] = []

    if data.get("schema") != CAPABILITY_SCHEMA:
        errors.append(f"schema must be {CAPABILITY_SCHEMA}")
    if not data.get("provider"):
        errors.append("provider is required")
    if data.get("status") not in RUN_STATUSES:
        errors.append("status must be completed or failed")

    evidence_level = data.get("evidence_level")
    if evidence_level not in EVIDENCE_LEVELS:
        errors.append(f"unsupported evidence_level: {evidence_level}")

    task_results = data.get("task_results")
    if not isinstance(task_results, list) or not task_results:
        errors.append("task_results must be a non-empty list")
        task_results = []

    metrics = data.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    tasks_passed = int(metrics.get("tasks_passed", 0) or 0)
    suite_pass_rate = float(metrics.get("suite_pass_rate", 0.0) or 0.0)

    provenance = data.get("provenance")
    provenance_source = ""
    provenance_command: Any = []
    if isinstance(provenance, dict):
        provenance_source = str(provenance.get("source", "")).strip()
        provenance_command = provenance.get("command", [])

    for index, item in enumerate(task_results):
        if not isinstance(item, dict):
            errors.append(f"task_results[{index}] must be an object")
            continue
        for field in ("task_id", "passed", "total", "status"):
            if field not in item:
                errors.append(f"task_results[{index}] missing {field}")

    if evidence_level == "live_external":
        if data.get("status") != "completed":
            errors.append("live_external capability runs must be completed")
        if tasks_passed < 1:
            errors.append("live_external capability runs require at least one fully passed task")
        if suite_pass_rate <= 0:
            errors.append("live_external capability runs require positive suite_pass_rate")
        if (
            not provenance_source
            or not isinstance(provenance_command, list)
            or not provenance_command
        ):
            errors.append("live_external capability runs require provenance source and command")

    valid = not errors
    is_graded_live = (
        evidence_level == "live_external"
        and valid
        and data.get("status") == "completed"
        and tasks_passed >= 1
    )
    return {
        "valid": valid,
        "errors": errors,
        "schema": data.get("schema"),
        "provider": data.get("provider"),
        "status": data.get("status"),
        "evidence_level": evidence_level,
        "tasks_passed": tasks_passed,
        "tasks_total": int(metrics.get("tasks_attempted", len(task_results)) or len(task_results)),
        "suite_pass_rate": suite_pass_rate,
        "is_graded_live": is_graded_live,
    }


# --------------------------------------------------------------------------- #
# Matrix readiness
# --------------------------------------------------------------------------- #
def run_capability_readiness(
    artifact_dir: Path | str = DEFAULT_CAPABILITY_RUN_DIR,
) -> dict[str, Any]:
    """Score graded-capability coverage across all expected Agent platforms."""
    artifact_path = Path(artifact_dir)
    artifacts = [_validated(path, data) for path, data in _load_artifacts(artifact_path)]
    provider_statuses = [
        _provider_status(provider, artifacts) for provider in sorted(EXPECTED_PROVIDERS)
    ]

    graded_live_count = sum(1 for item in provider_statuses if item["status"] == "graded_live")
    blocked_count = sum(1 for item in provider_statuses if item["status"] == "blocked")
    missing_count = sum(
        1 for item in provider_statuses if item["status"] in {"missing", "missing_live"}
    )
    full_matrix = graded_live_count == len(EXPECTED_PROVIDERS)
    diagnostics_ready = all(
        item["status"] in {"graded_live", "blocked"} for item in provider_statuses
    )

    # Discrimination: rank graded providers by difficulty-weighted capability_score
    # and measure the spread so the matrix is a real capability comparison, not a
    # saturated "everyone scores 100" table.
    graded = [item for item in provider_statuses if item["status"] == "graded_live"]
    ranking = sorted(
        graded,
        key=lambda item: (item["capability_score"], item["tasks_passed"]),
        reverse=True,
    )
    scores = [item["capability_score"] for item in graded]
    score_spread = round(max(scores) - min(scores), 4) if scores else 0.0
    tier_summary = suite_difficulty_summary()
    has_hard_tier = tier_summary.get("hard", 0) >= 1

    checks = [
        {
            "id": "graded_live_capability_matrix",
            "required": True,
            "status": "pass" if full_matrix else "fail",
            "evidence": (
                f"{graded_live_count}/4 providers passed objectively graded live code tasks"
            ),
        },
        {
            "id": "blocked_attempt_diagnostics",
            "required": True,
            "status": "pass" if diagnostics_ready else "fail",
            "evidence": (
                f"{blocked_count} blocked providers; {missing_count} providers missing diagnostics"
            ),
        },
        {
            "id": "objective_grading_integrity",
            "required": True,
            "status": "pass" if all(item["valid"] for item in artifacts) else "fail",
            "evidence": "every recorded capability artifact validates against capability_run_v1",
        },
        {
            "id": "discriminative_task_suite",
            "required": False,
            "status": "pass" if has_hard_tier and len(tier_summary) >= 2 else "fail",
            "evidence": (
                f"suite spans {len(tier_summary)} difficulty tiers "
                f"({tier_summary}); observed capability_score spread {score_spread}"
            ),
        },
    ]

    recommended_score = _recommended_score(full_matrix, graded_live_count, diagnostics_ready)
    return {
        "status": "completed" if full_matrix else "partial",
        "artifact_dir": str(artifact_path),
        "expected_providers": sorted(EXPECTED_PROVIDERS),
        "provider_statuses": provider_statuses,
        "ranking": [
            {
                "provider": item["provider"],
                "capability_score": item["capability_score"],
                "tasks_passed": item["tasks_passed"],
                "tasks_total": item["tasks_total"],
                "hardest_tier_passed": item.get("hardest_tier_passed", ""),
            }
            for item in ranking
        ],
        "checks": checks,
        "metrics": {
            "capability_artifacts": len(artifacts),
            "expected_provider_count": len(EXPECTED_PROVIDERS),
            "graded_live_provider_count": graded_live_count,
            "blocked_provider_count": blocked_count,
            "missing_provider_count": missing_count,
            "graded_live_pass_rate": round(graded_live_count / len(EXPECTED_PROVIDERS), 4),
            "suite_difficulty_tiers": tier_summary,
            "capability_score_max": round(max(scores), 4) if scores else 0.0,
            "capability_score_min": round(min(scores), 4) if scores else 0.0,
            "capability_score_spread": score_spread,
        },
        "previous_score": 97,
        "recommended_score": recommended_score,
        "score_delta": recommended_score - 97,
        "resolved_findings": _resolved_findings(graded_live_count, full_matrix),
        "remaining_findings": _remaining_findings(
            full_matrix, graded_live_count, diagnostics_ready
        ),
        "limitations": [
            "Capability readiness grades real code tasks; it is not a retired Fable 5 rerun.",
            "A blocked provider (usage limit or headless lock) is a diagnostic, not graded "
            "success.",
            "A zero capability_score_spread means the suite did not separate the providers at "
            "this difficulty, not that they are proven equivalent.",
            "Remote CI and release publication remain separate evidence tracks.",
        ],
    }


def _recommended_score(full_matrix: bool, graded_live_count: int, diagnostics_ready: bool) -> int:
    if full_matrix:
        return 100
    if graded_live_count >= 3 and diagnostics_ready:
        return 99
    if graded_live_count >= 2 and diagnostics_ready:
        return 98
    return 97


def _provider_status(provider: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    provider_artifacts = [item for item in artifacts if item["provider"] == provider]
    graded = [item for item in provider_artifacts if item["is_graded_live"]]
    attempts = [item for item in provider_artifacts if item["evidence_level"] == "live_external"]

    if graded:
        best = max(graded, key=lambda item: item["capability_score"])
        return {
            "provider": provider,
            "status": "graded_live",
            "tasks_passed": best["tasks_passed"],
            "tasks_total": best["tasks_total"],
            "suite_pass_rate": best["suite_pass_rate"],
            "capability_score": best["capability_score"],
            "hardest_tier_passed": best["hardest_tier_passed"],
            "evidence_paths": [item["path"] for item in graded],
            "errors": [],
        }
    if attempts:
        return {
            "provider": provider,
            "status": "blocked",
            "tasks_passed": 0,
            "tasks_total": attempts[0]["tasks_total"],
            "suite_pass_rate": 0.0,
            "capability_score": 0.0,
            "hardest_tier_passed": "",
            "evidence_paths": [item["path"] for item in attempts],
            "errors": _flatten_errors(attempts),
        }
    if provider_artifacts:
        return {
            "provider": provider,
            "status": "missing_live",
            "tasks_passed": 0,
            "tasks_total": 0,
            "suite_pass_rate": 0.0,
            "capability_score": 0.0,
            "hardest_tier_passed": "",
            "evidence_paths": [item["path"] for item in provider_artifacts],
            "errors": ["provider has artifacts but no live_external capability attempt"],
        }
    return {
        "provider": provider,
        "status": "missing",
        "tasks_passed": 0,
        "tasks_total": 0,
        "suite_pass_rate": 0.0,
        "capability_score": 0.0,
        "hardest_tier_passed": "",
        "evidence_paths": [],
        "errors": ["provider has no capability artifacts"],
    }


def _flatten_errors(artifacts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for item in artifacts:
        errors.extend(str(error) for error in item["errors"])
        if item["error"]:
            errors.append(str(item["error"]))
    return errors or ["live_external attempt did not produce graded capability evidence"]


def _resolved_findings(graded_live_count: int, full_matrix: bool) -> list[str]:
    resolved = ["F022_LIVE_MATRIX_PARTIAL"]
    if graded_live_count >= 2:
        resolved.append("F024_GRADED_CAPABILITY_EVIDENCE")
    if graded_live_count >= 3:
        resolved.append("F025_MULTI_PLATFORM_CAPABILITY_MATRIX")
    if full_matrix:
        resolved.append("F026_FULL_GRADED_CAPABILITY_MATRIX")
    return resolved


def _remaining_findings(
    full_matrix: bool, graded_live_count: int, diagnostics_ready: bool
) -> list[str]:
    remaining = ["DIRECT_RETIRED_MODEL_UNAVAILABLE", "CI_REMOTE_UNVERIFIED"]
    if not full_matrix:
        remaining.append("FULL_GRADED_CAPABILITY_MATRIX")
    if graded_live_count < 3:
        remaining.append("MULTI_PLATFORM_CAPABILITY_MATRIX")
    if not diagnostics_ready:
        remaining.append("CAPABILITY_DIAGNOSTICS_INCOMPLETE")
    return remaining


def _suite_metrics(task_results: list[dict[str, Any]]) -> dict[str, Any]:
    tasks_attempted = len(task_results)
    tasks_passed = sum(1 for item in task_results if item["status"] == "pass")
    cases_passed = sum(int(item.get("passed", 0)) for item in task_results)
    cases_total = sum(int(item.get("total", 0)) for item in task_results)
    passed_by_tier: dict[str, int] = {}
    total_by_tier: dict[str, int] = {}
    for item in task_results:
        tier = str(item.get("difficulty", "easy"))
        total_by_tier[tier] = total_by_tier.get(tier, 0) + 1
        if item.get("status") == "pass":
            passed_by_tier[tier] = passed_by_tier.get(tier, 0) + 1
    return {
        "tasks_attempted": tasks_attempted,
        "tasks_passed": tasks_passed,
        "suite_pass_rate": round(tasks_passed / tasks_attempted, 4) if tasks_attempted else 0.0,
        "cases_passed": cases_passed,
        "cases_total": cases_total,
        "case_pass_rate": round(cases_passed / cases_total, 4) if cases_total else 0.0,
        "capability_score": compute_capability_score(task_results),
        "hardest_tier_passed": hardest_tier_passed(task_results),
        "tasks_passed_by_tier": passed_by_tier,
        "tasks_total_by_tier": total_by_tier,
    }


def _validated(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    validation = validate_capability_run_artifact(data)
    error = str(data.get("error") or "")
    raw_metrics = data.get("metrics")
    metrics: dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else {}
    raw_results = data.get("task_results")
    task_results: list[Any] = raw_results if isinstance(raw_results, list) else []
    # Prefer the stored capability_score; fall back to suite_pass_rate for older
    # artifacts (or fixtures) that predate difficulty-weighted scoring.
    if "capability_score" in metrics:
        capability_score = float(metrics.get("capability_score") or 0.0)
    elif task_results:
        capability_score = compute_capability_score(task_results)
    else:
        capability_score = validation["suite_pass_rate"]
    return {
        "path": str(path),
        "provider": validation["provider"],
        "status": validation["status"],
        "evidence_level": validation["evidence_level"],
        "valid": validation["valid"],
        "errors": validation["errors"],
        "is_graded_live": validation["is_graded_live"],
        "tasks_passed": validation["tasks_passed"],
        "tasks_total": validation["tasks_total"],
        "suite_pass_rate": validation["suite_pass_rate"],
        "capability_score": round(capability_score, 4),
        "hardest_tier_passed": str(metrics.get("hardest_tier_passed", "")),
        "error": error,
    }


def _load_artifacts(artifact_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not artifact_dir.exists():
        return []
    artifacts: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(artifact_dir.glob("*-capability-run.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            artifacts.append((path, data))
    return artifacts


def _load_artifact(artifact: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(artifact, dict):
        return artifact
    path = Path(artifact)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Capability run artifact must be a JSON object")
    return data


def _duration_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 4)
