"""Validate active capability headlines against versioned raw run artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.capability_matrix import DEFAULT_CAPABILITY_RUN_DIR, run_capability_readiness

ACTIVE_TEXT_SURFACES = (
    Path("README.md"),
    Path("README.zh.md"),
    Path("VERIFICATION_SCORECARD.md"),
)
ACTIVE_JSON_SURFACES = (
    Path("benchmarks/results/capability-matrix.json"),
    Path("benchmarks/results/benchmark-capability.json"),
)


def derive_headline(artifact_dir: Path) -> str:
    """Derive the graded-live provider headline from raw capability run artifacts."""
    readiness = run_capability_readiness(artifact_dir)
    metrics = readiness["metrics"]
    graded = int(metrics["graded_live_provider_count"])
    expected = int(metrics["expected_provider_count"])
    return f"{graded}/{expected}"


def validate_headline_consistency(
    artifact_dir: Path = DEFAULT_CAPABILITY_RUN_DIR,
    repository_root: Path = Path("."),
) -> dict[str, Any]:
    """Return diagnostics for active surfaces that disagree with raw run evidence."""
    expected = derive_headline(Path(artifact_dir))
    root = Path(repository_root)
    stale_paths: list[str] = []

    for relative_path in ACTIVE_TEXT_SURFACES:
        path = root / relative_path
        if not _text_surface_matches(path, relative_path, expected):
            stale_paths.append(str(path))

    for relative_path in ACTIVE_JSON_SURFACES:
        path = root / relative_path
        if not _json_surface_matches(path, relative_path, expected):
            stale_paths.append(str(path))

    return {
        "expected_headline": expected,
        "stale_paths": stale_paths,
        "errors": [
            f"headline mismatch: expected headline: {expected}; stale path: {path}"
            for path in stale_paths
        ],
    }


def _text_surface_matches(path: Path, relative_path: Path, expected: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    if relative_path.name == "README.md":
        candidates = [line for line in text.splitlines() if "Cross-platform matrix" in line]
    elif relative_path.name == "README.zh.md":
        candidates = [line for line in text.splitlines() if "跨平台矩阵" in line]
    else:
        current_summary = text.partition("## 评分维度")[0]
        table_candidates = [
            line
            for line in current_summary.splitlines()
            if "Capability matrix CLI" in line or "Capability benchmark CLI" in line
        ]
        summary_candidates = [
            line.partition("因此当前是")[2]
            for line in current_summary.splitlines()
            if "因此当前是" in line
        ]
        candidates = [*table_candidates, *summary_candidates]
    return bool(candidates) and all(_first_ratio(line) == expected for line in candidates)


def _first_ratio(text: str) -> str | None:
    match = re.search(r"(?<!\d)\d+/\d+(?!\d)", text)
    return match.group(0) if match else None


def _json_surface_matches(path: Path, relative_path: Path, expected: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False

    readiness = (
        data.get("capability_readiness") if relative_path.name.startswith("benchmark-") else data
    )
    if not isinstance(readiness, dict):
        return False
    metrics = readiness.get("metrics")
    if not isinstance(metrics, dict):
        return False
    try:
        actual = (
            f"{int(metrics['graded_live_provider_count'])}/"
            f"{int(metrics['expected_provider_count'])}"
        )
    except (KeyError, TypeError, ValueError):
        return False
    return actual == expected
