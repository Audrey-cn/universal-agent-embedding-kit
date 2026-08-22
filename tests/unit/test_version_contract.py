"""Cross-surface release version contract."""

from __future__ import annotations

import asyncio
import json
import tomllib
from pathlib import Path

import yaml
from click.testing import CliRunner

from src.cli import main

EXPECTED_VERSION = "0.3.0.dev1"
ACTIVE_PORTABLE_DOCS = (
    "README.md",
    "README.zh.md",
    "CONTRIBUTING.md",
    "docs/support-matrix.md",
    "SOP.md",
    "EXECUTION_MANUAL.md",
    "VERIFICATION_SCORECARD.md",
    "docs/guides/capability-batch.md",
)


def test_release_version_is_consistent_across_runtime_surfaces():
    """Python exports and typed defaults should use the release version authority."""
    from src import __version__
    from src.config import UAEKConfig
    from src.version import get_version

    assert get_version() == EXPECTED_VERSION
    assert __version__ == EXPECTED_VERSION
    assert UAEKConfig().version == EXPECTED_VERSION


def test_release_metadata_files_use_the_same_version():
    """Build, YAML, and MCP metadata should not carry independent release numbers."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    default_config = yaml.safe_load(Path("config/default.yaml").read_text(encoding="utf-8"))
    mcp_config = json.loads(Path("mcp/config.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert default_config["uaek"]["version"] == EXPECTED_VERSION
    assert mcp_config["version"] == EXPECTED_VERSION


def test_mcp_metadata_uses_the_portable_console_command() -> None:
    """The checked-in host template must select the packaged MCP executable."""
    mcp_config = json.loads(Path("mcp/config.json").read_text(encoding="utf-8"))

    assert mcp_config["command"] == "uaek-mcp"


def test_active_release_docs_use_current_setup_and_portable_paths() -> None:
    documents = {
        name: Path(name).read_text(encoding="utf-8") for name in ACTIVE_PORTABLE_DOCS
    }

    assert "# UAEK 0.3 Support Matrix" in documents["docs/support-matrix.md"]
    assert EXPECTED_VERSION in documents["docs/support-matrix.md"]
    for name in ("README.md", "README.zh.md", "CONTRIBUTING.md"):
        assert "bash scripts/setup.sh --verify" in documents[name]
    for name, content in documents.items():
        assert "/Users/audrey" not in content, name


def test_active_headline_surfaces_match_versioned_capability_runs() -> None:
    """Active docs and generated summaries must agree with versioned raw run evidence."""
    from scripts.check_headline_consistency import (
        derive_headline,
        validate_headline_consistency,
    )

    artifact_dir = Path("benchmarks/results/capability-runs")
    assert derive_headline(artifact_dir) == "3/4"

    validation = validate_headline_consistency(artifact_dir, Path("."))
    assert validation == {
        "expected_headline": "3/4",
        "stale_paths": [],
        "errors": [],
    }

    matrix = json.loads(
        Path("benchmarks/results/capability-matrix.json").read_text(encoding="utf-8")
    )
    benchmark = json.loads(
        Path("benchmarks/results/benchmark-capability.json").read_text(encoding="utf-8")
    )
    assert matrix["metrics"]["graded_live_provider_count"] == 3
    assert matrix["metrics"]["expected_provider_count"] == 4
    assert benchmark["capability_readiness"]["metrics"][
        "graded_live_provider_count"
    ] == 3
    assert benchmark["capability_readiness"]["metrics"]["expected_provider_count"] == 4
    for readiness in (matrix, benchmark["capability_readiness"]):
        assert "hermes 8/10" not in "\n".join(readiness["limitations"])


def test_cli_reports_release_version():
    """The installed command should report the shared release version."""
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"uaek, version {EXPECTED_VERSION}"


def test_api_and_mcp_report_release_version():
    """Network entrypoints should advertise the package release version."""
    from api.server import api_root_payload
    from mcp.server import MCPServer

    assert api_root_payload()["version"] == EXPECTED_VERSION
    response = asyncio.run(
        MCPServer().handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
    )

    assert response is not None
    assert response["result"]["serverInfo"]["version"] == EXPECTED_VERSION
