#!/usr/bin/env python
"""Fail when release-supported modules fall below recorded coverage floors."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SUPPORTED_MODULE_FLOORS: dict[str, float] = {
    "api/server.py": 50.0,
    "mcp/server.py": 70.0,
    "src/workflow/runtime.py": 60.0,
    "src/security/sandbox.py": 65.0,
    "src/verify/test_runner.py": 80.0,
    "src/memory/service.py": 70.0,
}


def check_supported_coverage(report: dict[str, Any]) -> list[str]:
    """Return deterministic diagnostics for missing, invalid, or low module coverage."""
    files = report.get("files", {})
    files = files if isinstance(files, dict) else {}
    errors: list[str] = []
    for module, floor in SUPPORTED_MODULE_FLOORS.items():
        entry = files.get(module)
        if not isinstance(entry, dict):
            errors.append(f"{module}: missing from coverage report")
            continue
        summary = entry.get("summary")
        if not isinstance(summary, dict):
            errors.append(f"{module}: invalid coverage summary")
            continue
        covered = summary.get("percent_covered")
        if not isinstance(covered, int | float):
            errors.append(f"{module}: invalid percent_covered")
            continue
        if float(covered) < floor:
            errors.append(f"{module}: {float(covered):.2f}% < {floor:.2f}%")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate one pytest-cov JSON report."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: check_supported_coverage.py <coverage.json>", file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read coverage report: {exc}", file=sys.stderr)
        return 2
    errors = check_supported_coverage(report)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"supported coverage passed: {len(SUPPORTED_MODULE_FLOORS)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
