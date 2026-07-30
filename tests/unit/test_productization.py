"""Tests for productized UAEK runtime entrypoints."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from api import server as api_server
from api.server import UAEKHandler
from mcp.server import create_server as create_mcp_server
from src.cli import main
from src.memory.service import MemoryService
from src.skills.service import SkillService
from src.workflow.runtime import execute_workflow_config, load_workflow_config


def test_packaging_includes_documented_api_and_mcp_packages():
    """Wheel package discovery should include every documented runtime entrypoint."""
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    include = set(data["tool"]["setuptools"]["packages"]["find"]["include"])

    assert "src*" in include
    assert "api*" in include
    assert "mcp*" in include


def test_packaging_uses_non_deprecated_license_metadata():
    """Build metadata should avoid setuptools license deprecation warnings."""
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["license"] == "MIT"
    assert not any(
        classifier.startswith("License ::")
        for classifier in data["project"].get("classifiers", [])
    )


def test_mcp_module_runs_stdio_initialize_and_tools_list():
    """`python -m mcp.server` should be a real stdio JSON-RPC MCP server."""
    requests = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}}),
        ]
    ) + "\n"

    completed = subprocess.run(
        [sys.executable, "-m", "mcp.server"],
        input=requests,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 0
    responses = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    assert [response["id"] for response in responses[:2]] == [1, 2]
    assert responses[0]["result"]["serverInfo"]["name"] == "uaek"
    tool_names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert {"uaek_verify", "uaek_effort", "uaek_memory_query"}.issubset(tool_names)


def test_workflow_config_executes_builtin_actions(tmp_path: Path):
    """Workflow configs should execute real tasks, not placeholders."""
    config_path = tmp_path / "workflow.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "id": "demo-workflow",
                "type": "sequential",
                "tasks": [
                    {
                        "id": "collect",
                        "name": "Collect signal",
                        "action": "echo",
                        "args": ["alpha"],
                    },
                    {
                        "id": "combine",
                        "name": "Combine signal",
                        "action": "concat",
                        "args": ["alpha", "-", "beta"],
                        "dependencies": ["collect"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = execute_workflow_config(load_workflow_config(config_path))

    assert result["workflow_id"] == "demo-workflow"
    assert result["success"] is True
    assert [task["id"] for task in result["completed_tasks"]] == ["collect", "combine"]
    assert result["task_results"]["collect"] == "alpha"
    assert result["task_results"]["combine"] == "alpha-beta"


def test_workflow_config_rejects_actions_outside_safe_allowlist(tmp_path: Path):
    """Workflow configs should enforce the configured safe action surface."""
    config_path = tmp_path / "workflow.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "id": "unsafe-workflow",
                "tasks": [
                    {
                        "id": "verify",
                        "name": "Verify arbitrary path",
                        "action": "verify",
                        "args": ["."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowed"):
        execute_workflow_config(load_workflow_config(config_path))


def test_memory_service_add_query_compress_and_restore(tmp_path: Path):
    """Memory service should persist real entries across instances."""
    store = tmp_path / "memory"
    service = MemoryService(store)

    entry = service.add(
        "Architecture decision: keep workflow actions safe",
        layer="l3",
        importance=0.9,
        tags=["decision"],
    )
    service.add("Temporary debug output", layer="l3", importance=0.1, tags=["debug"])

    query_result = service.query("workflow", layer="l3", tags=["decision"])
    assert query_result["total"] == 1
    assert query_result["results"][0]["id"] == entry["id"]

    compressed = service.compress(layer="l3", target_ratio=0.5)
    assert compressed["after"] == 1
    service.persist()

    restored = MemoryService(store)
    restored_result = restored.query("workflow", layer="l3")
    assert restored_result["total"] == 1
    assert restored_result["results"][0]["content"].startswith("Architecture decision")


def test_skill_service_discovers_flat_markdown_skills():
    """The project-level skills/*.md files should be usable by the product entrypoints."""
    service = SkillService([Path("skills")])

    skills = service.list_skills()
    names = {skill["name"] for skill in skills}

    assert "verification-framework" in names
    result = service.run("verification-framework", {"artifact": "src/cli.py"})
    assert result["name"] == "verification-framework"
    assert "验证框架" in result["output"]


def test_cli_workflow_memory_and_skill_paths(tmp_path: Path):
    """CLI commands should expose real workflow, memory, and skill behavior."""
    runner = CliRunner()
    workflow_config = tmp_path / "workflow.yaml"
    workflow_config.write_text(
        yaml.safe_dump(
            {
                "id": "cli-workflow",
                "tasks": [{"id": "say", "name": "Say", "action": "echo", "args": ["hello cli"]}],
            }
        ),
        encoding="utf-8",
    )
    memory_store = tmp_path / "memory"

    workflow_result = runner.invoke(main, ["workflow", "--config", str(workflow_config)])
    assert workflow_result.exit_code == 0
    assert "cli-workflow" in workflow_result.output
    assert "say" in workflow_result.output

    add_result = runner.invoke(
        main,
        [
            "memory",
            "add",
            "Decision: CLI memory persists",
            "--store",
            str(memory_store),
            "--layer",
            "l3",
            "--tag",
            "decision",
        ],
    )
    assert add_result.exit_code == 0
    assert "added" in add_result.output

    query_result = runner.invoke(
        main,
        ["memory", "query", "CLI memory", "--store", str(memory_store), "--layer", "l3"],
    )
    assert query_result.exit_code == 0
    assert "CLI memory persists" in query_result.output

    skill_result = runner.invoke(main, ["skill", "run", "verification-framework"])
    assert skill_result.exit_code == 0
    assert "verification-framework" in skill_result.output


def test_api_workflow_and_memory_use_real_services():
    """API handlers should return real workflow results and stored memory query results."""
    api_server.MEMORY_SERVICE.clear()
    handler = UAEKHandler.__new__(UAEKHandler)
    responses: list[tuple[int, dict]] = []
    handler._respond = lambda status, data: responses.append((status, data))

    handler._handle_workflow(
        {
            "id": "api-workflow",
            "tasks": [{"id": "echo", "name": "Echo", "action": "echo", "args": ["hello api"]}],
        }
    )
    assert responses[-1][0] == 200
    assert responses[-1][1]["task_results"]["echo"] == "hello api"

    handler._handle_memory(
        {
            "action": "add",
            "content": "API memory stores workflow facts",
            "layer": "l2",
            "tags": ["api"],
        }
    )
    handler._handle_memory({"action": "query", "query": "workflow", "layer": "l2"})
    assert responses[-1][0] == 200
    assert responses[-1][1]["total"] == 1
    assert "workflow facts" in responses[-1][1]["results"][0]["content"]


def test_mcp_workflow_and_memory_tools_are_stateful():
    """MCP workflow/memory tools should maintain state across calls on one server."""
    server = create_mcp_server()

    async def call_tool(name: str, arguments: dict) -> dict:
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        assert "error" not in response
        return json.loads(response["result"]["content"][0]["text"])

    async def scenario() -> None:
        await call_tool(
            "uaek_workflow_create",
            {"workflow_id": "mcp-workflow", "workflow_type": "sequential"},
        )
        await call_tool(
            "uaek_workflow_add_task",
            {
                "workflow_id": "mcp-workflow",
                "task_id": "echo",
                "task_name": "Echo",
                "func_name": "echo",
                "args": ["hello mcp"],
            },
        )
        workflow_result = await call_tool(
            "uaek_workflow_execute",
            {"workflow_id": "mcp-workflow"},
        )
        assert workflow_result["task_results"]["echo"] == "hello mcp"

        await call_tool(
            "uaek_memory_add",
            {"content": "MCP memory is queryable", "layer": "l2", "tags": ["mcp"]},
        )
        memory_result = await call_tool(
            "uaek_memory_query",
            {"query": "queryable", "layer": "l2"},
        )
        assert memory_result["total"] == 1
        assert memory_result["results"][0]["content"] == "MCP memory is queryable"

    asyncio.run(scenario())


def test_mcp_validates_tool_arguments_before_calling_handlers():
    """MCP tools/call should enforce required fields, types, enums, and unknown args."""
    server = create_mcp_server()

    async def scenario() -> None:
        missing = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "uaek_workflow_create", "arguments": {}},
            }
        )
        assert missing["error"]["code"] == -32602
        assert "missing required field 'workflow_id'" in missing["error"]["message"]

        invalid_enum = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "uaek_workflow_create",
                    "arguments": {"workflow_id": "bad", "workflow_type": "shell"},
                },
            }
        )
        assert invalid_enum["error"]["code"] == -32602
        assert "workflow_type" in invalid_enum["error"]["message"]

        unknown = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "uaek_memory_query",
                    "arguments": {"query": "x", "surprise": True},
                },
            }
        )
        assert unknown["error"]["code"] == -32602
        assert "unknown field 'surprise'" in unknown["error"]["message"]

    asyncio.run(scenario())


def test_mcp_workflow_tool_schema_limits_actions_to_safe_allowlist():
    server = create_mcp_server()
    tool = next(tool for tool in server.tools.values() if tool["name"] == "uaek_workflow_add_task")
    enum = tool["inputSchema"]["properties"]["func_name"]["enum"]

    assert "echo" in enum
    assert "verify" not in enum
