"""Tests for focused coverage floors on release-supported modules."""

from __future__ import annotations

from scripts.check_supported_coverage import SUPPORTED_MODULE_FLOORS, check_supported_coverage


def _report_at_floors() -> dict:
    return {
        "files": {
            module: {"summary": {"percent_covered": floor}}
            for module, floor in SUPPORTED_MODULE_FLOORS.items()
        }
    }


def test_supported_coverage_reports_missing_and_low_modules():
    """Missing and below-floor supported modules should both fail the gate."""
    report = {
        "files": {
            "api/server.py": {"summary": {"percent_covered": 49.9}},
        }
    }

    errors = check_supported_coverage(report)

    assert "api/server.py: 49.90% < 50.00%" in errors
    assert any("mcp/server.py: missing" in error for error in errors)


def test_supported_coverage_accepts_recorded_floors():
    """A report at every recorded floor should pass exactly."""
    assert check_supported_coverage(_report_at_floors()) == []


def test_supported_coverage_rejects_malformed_summary():
    """Malformed coverage JSON should fail closed instead of raising."""
    report = _report_at_floors()
    report["files"]["src/memory/service.py"] = {"summary": {"percent_covered": "unknown"}}

    errors = check_supported_coverage(report)

    assert "src/memory/service.py: invalid percent_covered" in errors
