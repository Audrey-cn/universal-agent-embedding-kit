"""Validation and deterministic expansion for multi-sample evidence campaigns."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast

from src.capability_matrix import OUTPUT_MODES
from src.evidence.common import (
    JsonObjectSource,
    contains_secret_material,
    load_json_object,
    require_string,
)

CAMPAIGN_SCHEMA = "evidence_campaign_v1"
CAMPAIGN_VALIDATION_SCHEMA = "evidence_campaign_validation_v1"
CAMPAIGN_SUMMARY_SCHEMA = "evidence_campaign_summary_v1"
_SAMPLE_FIELDS = (
    "campaign_id",
    "provider",
    "backend_family",
    "sample_id",
    "seed",
    "task_set_digest",
    "grader_version",
)


def validate_campaign_manifest(source: JsonObjectSource) -> dict[str, Any]:
    """Validate a campaign without executing any provider command."""

    manifest = load_json_object(source)
    errors: list[str] = []
    if manifest.get("schema") != CAMPAIGN_SCHEMA:
        errors.append(f"schema must be {CAMPAIGN_SCHEMA}")
    campaign_id = require_string(manifest, "campaign_id", errors)
    task_set_digest = require_string(manifest, "task_set_digest", errors)
    grader_version = require_string(manifest, "grader_version", errors)
    if contains_secret_material(manifest):
        errors.append("campaign contains secret material")

    raw_providers = manifest.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        errors.append("providers must be a non-empty list")
        raw_providers = []

    providers: list[dict[str, Any]] = []
    seen_sample_ids: set[str] = set()
    for index, raw_provider in enumerate(raw_providers):
        if not isinstance(raw_provider, dict):
            errors.append(f"providers[{index}] must be an object")
            continue
        provider_errors: list[str] = []
        provider = require_string(raw_provider, "provider", provider_errors)
        backend_family = require_string(raw_provider, "backend_family", provider_errors)
        command = _string_list(raw_provider.get("command"), f"providers[{index}].command", errors)
        output_mode = raw_provider.get("output_mode")
        if output_mode not in OUTPUT_MODES:
            errors.append(f"providers[{index}].output_mode must be one of {sorted(OUTPUT_MODES)}")

        sample_count_value = raw_provider.get("sample_count")
        sample_count = (
            sample_count_value
            if isinstance(sample_count_value, int)
            and not isinstance(sample_count_value, bool)
            and sample_count_value >= 1
            else 0
        )
        if sample_count == 0:
            errors.append(f"providers[{index}].sample_count must be an integer >= 1")

        seeds = _resolve_seeds(raw_provider, sample_count, index, errors)
        sample_ids = _resolve_sample_ids(raw_provider, provider, sample_count, index, errors)
        for sample_id in sample_ids:
            if sample_id in seen_sample_ids:
                errors.append(f"duplicate sample_id: {sample_id}")
            seen_sample_ids.add(sample_id)

        errors.extend(f"providers[{index}].{error}" for error in provider_errors)
        providers.append(
            {
                "provider": provider,
                "backend_family": backend_family,
                "command": command,
                "output_mode": output_mode,
                "sample_count": sample_count,
                "seeds": seeds,
                "sample_ids": sample_ids,
                "provider_home": raw_provider.get("provider_home"),
                "provider_home_seed_paths": _optional_string_list(
                    raw_provider.get("provider_home_seed_paths"),
                    f"providers[{index}].provider_home_seed_paths",
                    errors,
                ),
                "timeout": _positive_number(raw_provider.get("timeout", 120.0), index, errors),
            }
        )

    artifact_dir = manifest.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not artifact_dir.strip():
        artifact_dir = str(Path("benchmarks/results/evidence") / (campaign_id or "invalid"))

    return {
        "schema": CAMPAIGN_VALIDATION_SCHEMA,
        "valid": not errors,
        "errors": errors,
        "campaign_id": campaign_id,
        "task_set_digest": task_set_digest,
        "grader_version": grader_version,
        "artifact_dir": artifact_dir,
        "providers": providers,
    }


def build_sample_plan(validation: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a valid manifest validation into a stable provider/sample plan."""

    if not validation.get("valid"):
        raise ValueError("cannot build a sample plan from an invalid campaign")
    samples: list[dict[str, Any]] = []
    for provider in validation["providers"]:
        for sample_id, seed in zip(provider["sample_ids"], provider["seeds"], strict=True):
            samples.append(
                {
                    "campaign_id": validation["campaign_id"],
                    "task_set_digest": validation["task_set_digest"],
                    "grader_version": validation["grader_version"],
                    "artifact_dir": validation["artifact_dir"],
                    **provider,
                    "sample_id": sample_id,
                    "seed": seed,
                }
            )
    return samples


def attach_sample_metadata(artifact: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    """Return an independent artifact carrying only stable sample identity metadata."""

    attached = cast(dict[str, Any], json.loads(json.dumps(artifact, ensure_ascii=False)))
    attached["sample"] = {field: sample.get(field) for field in _SAMPLE_FIELDS}
    return attached


def validate_campaign_artifact(source: JsonObjectSource) -> dict[str, Any]:
    """Validate the sample identity and aggregatable metrics of one campaign artifact."""

    artifact = load_json_object(source)
    errors: list[str] = []
    sample = artifact.get("sample")
    if not isinstance(sample, dict):
        errors.append("sample must be an object")
        sample = {}
    for field in _SAMPLE_FIELDS:
        value = sample.get(field)
        if field == "seed":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append("sample.seed must be an integer")
        elif not isinstance(value, str) or not value.strip():
            errors.append(f"sample.{field} must be a non-empty string")

    if artifact.get("provider") != sample.get("provider"):
        errors.append("artifact provider must match sample.provider")
    if artifact.get("status") not in {"completed", "failed"}:
        errors.append("status must be completed or failed")
    metrics = artifact.get("metrics")
    score = metrics.get("suite_pass_rate") if isinstance(metrics, dict) else None
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not 0.0 <= float(score) <= 1.0
    ):
        errors.append("metrics.suite_pass_rate must be between 0 and 1")
    if contains_secret_material(artifact):
        errors.append("artifact contains secret material")
    return {"valid": not errors, "errors": errors, "artifact": artifact}


def aggregate_campaign(artifacts: Iterable[JsonObjectSource]) -> dict[str, Any]:
    """Aggregate samples by provider and real backend family."""

    rows: list[dict[str, Any]] = []
    for source in artifacts:
        validation = validate_campaign_artifact(source)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        artifact = validation["artifact"]
        sample = artifact["sample"]
        rows.append(
            {
                "provider": sample["provider"],
                "backend_family": sample["backend_family"],
                "score": float(artifact["metrics"]["suite_pass_rate"]),
                "timed_out": _artifact_timed_out(artifact),
                "failed": artifact["status"] != "completed" or bool(artifact.get("error")),
            }
        )
    if not rows:
        raise ValueError("campaign aggregation requires at least one artifact")

    provider_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    family_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        provider_rows[row["provider"]].append(row)
        family_rows[row["backend_family"]].append(row)

    return {
        "schema": CAMPAIGN_SUMMARY_SCHEMA,
        "provider_count": len(provider_rows),
        "backend_family_count": len(family_rows),
        "providers": {
            name: _group_statistics(group) for name, group in sorted(provider_rows.items())
        },
        "backend_families": {
            name: _group_statistics(group) for name, group in sorted(family_rows.items())
        },
        "totals": _group_statistics(rows),
    }


def run_campaign(
    source: JsonObjectSource,
    runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Resolve and optionally execute every campaign sample exactly once."""

    validation = validate_campaign_manifest(source)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    sample_plan = build_sample_plan(validation)
    if dry_run:
        return {
            "schema": CAMPAIGN_SCHEMA,
            "campaign_id": validation["campaign_id"],
            "status": "dry_run",
            "sample_plan": sample_plan,
        }

    artifact_dir = Path(validation["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    resolved_runner = runner or _default_campaign_runner
    artifact_paths: list[Path] = []
    for sample in sample_plan:
        artifact = attach_sample_metadata(resolved_runner(sample), sample)
        artifact_validation = validate_campaign_artifact(artifact)
        if not artifact_validation["valid"]:
            raise ValueError("; ".join(artifact_validation["errors"]))
        artifact_path = artifact_dir / f"{sample['sample_id']}.json"
        with artifact_path.open("x", encoding="utf-8") as output:
            json.dump(artifact, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
        artifact_paths.append(artifact_path)

    summary = aggregate_campaign(artifact_paths)
    return {
        "schema": CAMPAIGN_SCHEMA,
        "campaign_id": validation["campaign_id"],
        "status": "completed",
        "artifact_paths": [str(path) for path in artifact_paths],
        "summary": summary,
    }


def _default_campaign_runner(sample: dict[str, Any]) -> dict[str, Any]:
    from src.capability_matrix import run_capability_suite_live

    return run_capability_suite_live(
        provider=sample["provider"],
        base_command=sample["command"],
        output_mode=sample["output_mode"],
        provider_home=sample["provider_home"],
        provider_home_seed_paths=tuple(sample["provider_home_seed_paths"]),
        timeout=sample["timeout"],
        source=f"evidence campaign:{sample['campaign_id']}",
        environment={"UAEK_SAMPLE_SEED": str(sample["seed"])},
    )


def _group_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [row["score"] for row in rows]
    mean = statistics.fmean(scores)
    standard_deviation = statistics.pstdev(scores)
    margin = 1.96 * standard_deviation / math.sqrt(len(scores))
    return {
        "sample_count": len(scores),
        "mean_score": round(mean, 6),
        "population_stddev": round(standard_deviation, 6),
        "min_score": min(scores),
        "max_score": max(scores),
        "confidence_interval_95": [
            round(max(0.0, mean - margin), 6),
            round(min(1.0, mean + margin), 6),
        ],
        "timeout_rate": sum(row["timed_out"] for row in rows) / len(rows),
        "failure_rate": sum(row["failed"] for row in rows) / len(rows),
    }


def _artifact_timed_out(artifact: dict[str, Any]) -> bool:
    messages = [artifact.get("error")]
    task_results = artifact.get("task_results")
    if isinstance(task_results, list):
        messages.extend(item.get("error") for item in task_results if isinstance(item, dict))
    return any(
        isinstance(message, str)
        and ("timed out" in message.casefold() or "timeout" in message.casefold())
        for message in messages
    )


def _resolve_seeds(
    provider: dict[str, Any], sample_count: int, index: int, errors: list[str]
) -> list[int]:
    if "seeds" in provider:
        seeds = provider["seeds"]
        if (
            not isinstance(seeds, list)
            or any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds)
            or len(seeds) != sample_count
        ):
            errors.append(f"providers[{index}].seeds must contain sample_count integers")
            return []
        return list(seeds)
    seed_start = provider.get("seed_start")
    if not isinstance(seed_start, int) or isinstance(seed_start, bool):
        errors.append(f"providers[{index}] requires integer seed_start or explicit seeds")
        return []
    return [seed_start + offset for offset in range(sample_count)]


def _resolve_sample_ids(
    provider: dict[str, Any],
    provider_name: str | None,
    sample_count: int,
    index: int,
    errors: list[str],
) -> list[str]:
    if "sample_ids" not in provider:
        if provider_name is None:
            return []
        return [f"{provider_name}-{offset:03d}" for offset in range(1, sample_count + 1)]
    sample_ids = provider["sample_ids"]
    if not isinstance(sample_ids, list) or any(
        not isinstance(sample_id, str) or not sample_id.strip() for sample_id in sample_ids
    ):
        errors.append(f"providers[{index}].sample_ids must contain non-empty strings")
        return []
    if sample_count and len(sample_ids) != sample_count:
        errors.append(f"providers[{index}].sample_ids must contain sample_count values")
    return [sample_id.strip() for sample_id in sample_ids]


def _string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"{field} must be a non-empty string list")
        return []
    return list(value)


def _optional_string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{field} must be a string list")
        return []
    return list(value)


def _positive_number(value: Any, index: int, errors: list[str]) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        errors.append(f"providers[{index}].timeout must be a positive number")
        return 120.0
    return float(value)
