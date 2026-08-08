"""Validation and deterministic expansion for multi-sample evidence campaigns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.capability_matrix import OUTPUT_MODES
from src.evidence.common import (
    JsonObjectSource,
    contains_secret_material,
    load_json_object,
    require_string,
)

CAMPAIGN_SCHEMA = "evidence_campaign_v1"
CAMPAIGN_VALIDATION_SCHEMA = "evidence_campaign_validation_v1"


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
