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
