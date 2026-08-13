from __future__ import annotations

import subprocess
import sys

import src.memory as memory
import src.verify as verify
import src.workflow as workflow
from api.server import api_root_payload
from mcp.server import create_server
from src.version import __version__


def test_public_python_exports_remain_available() -> None:
    assert {"MemoryService", "MemoryPersistence", "MemoryEntry"} <= set(memory.__all__)
    assert {"verify", "VerificationType", "VerificationResult"} <= set(verify.__all__)
    assert {"build_workflow", "execute_workflow_config", "WorkflowResult"} <= set(workflow.__all__)


def test_http_discovery_contract_is_versioned() -> None:
    payload = api_root_payload()
    assert payload["version"] == __version__
    assert payload["endpoints"] == [
        "GET /",
        "GET /health",
        "POST /verify",
        "POST /effort",
        "POST /workflow",
        "POST /memory",
    ]


def test_mcp_tool_names_and_schema_keys_remain_stable() -> None:
    tools = create_server().tools
    assert set(tools) == {
        "uaek_verify",
        "uaek_effort",
        "uaek_workflow_create",
        "uaek_workflow_add_task",
        "uaek_workflow_execute",
        "uaek_memory_add",
        "uaek_memory_query",
        "uaek_memory_delete",
        "uaek_memory_compress",
    }
    assert all({"name", "description", "inputSchema"} <= set(tool) for tool in tools.values())


def test_cli_help_keeps_documented_command_groups() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    for command in ("benchmark", "capability", "evidence", "audit"):
        assert command in completed.stdout
