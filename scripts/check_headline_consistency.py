#!/usr/bin/env python3
"""Fail when current capability, context or cost headlines drift from evidence."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from src.capability_matrix import DEFAULT_CAPABILITY_RUN_DIR
from src.headline_consistency import derive_headline, validate_headline_consistency
from src.model_headlines import validate_model_headlines

__all__ = ["derive_headline", "main", "validate_headline_consistency"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_CAPABILITY_RUN_DIR)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    validation = validate_headline_consistency(args.artifact_dir, args.repository_root)
    if validation["errors"]:
        print(f"expected headline: {validation['expected_headline']}")
        for path in validation["stale_paths"]:
            print(f"stale path: {path}")
        return 1

    model_errors = validate_model_headlines(args.repository_root)
    if model_errors:
        for error in model_errors:
            print(error)
        return 1
    print(f"headline consistency passed: {validation['expected_headline']}; modeled context/cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
