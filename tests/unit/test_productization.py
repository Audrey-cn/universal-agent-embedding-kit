"""Tests for productized UAEK runtime entrypoints."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
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
from src.memory.interface import MemoryLayerType
from src.memory.service import MemoryService
from src.memory.vector import VectorStore
from src.skills.service import SkillService
from src.workflow.runtime import execute_workflow_config, load_workflow_config


def test_packaging_includes_documented_api_and_mcp_packages():
    """Wheel package discovery should include every documented runtime entrypoint."""
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    include = set(data["tool"]["setuptools"]["packages"]["find"]["include"])

    assert "src*" in include
    assert "api*" in include
    assert "mcp*" in include


def test_mcp_console_script_and_host_config_are_relocatable() -> None:
    """Installed hosts must launch MCP without repository-specific paths."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    config_text = Path("mcp/config.json").read_text(encoding="utf-8")
    config = json.loads(config_text)

    assert pyproject["project"]["scripts"]["uaek-mcp"] == "mcp.server:main"
    assert config["command"] == "uaek-mcp"
    expected_keys = {"name", "version", "description", "type", "command", "args", "env", "_note"}
    assert expected_keys <= set(config)
    assert config["env"]["UAEK_MCP_IDLE_TIMEOUT"] == "300"
    for forbidden in ("/Users/", "/home/", "cwd", "PYTHONPATH"):
        assert forbidden not in config_text


def test_packaging_uses_non_deprecated_license_metadata():
    """Build metadata should avoid setuptools license deprecation warnings."""
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["license"] == "MIT"
    assert not any(
        classifier.startswith("License ::") for classifier in data["project"].get("classifiers", [])
    )


def test_supported_extras_do_not_include_chromadb() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    memory = project["optional-dependencies"]["memory"]

    assert all(not item.startswith("chromadb") for item in memory)


def test_memory_documentation_names_the_supported_and_retired_vector_paths() -> None:
    """User-facing memory guidance must not advertise the retired ChromaDB integration."""
    manual = Path("EXECUTION_MANUAL.md").read_text(encoding="utf-8")
    store_doc = inspect.getdoc(VectorStore) or ""
    chroma_doc = inspect.getdoc(VectorStore.use_chromadb) or ""

    assert "ChromaDB" not in manual
    assert "SimpleBackend" in manual
    assert "sentence-transformers" in manual
    assert "SimpleBackend" in store_doc
    assert "retired" in chroma_doc
    assert "always raises" in chroma_doc
    assert "SimpleBackend" in chroma_doc


def test_development_dependencies_and_ci_use_one_lock_contract() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = "\n".join(data["project"]["optional-dependencies"]["dev"])
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "black" not in dev_dependencies
    assert "pytest-asyncio" not in dev_dependencies
    assert "uv==0.11.32" in workflow
    assert "uv lock --check" in workflow


def test_docker_development_environment_contains_all_runtime_entrypoints() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    dockerignore_path = Path(".dockerignore")

    assert "COPY . ." in dockerfile
    assert dockerfile.index("COPY . .") < dockerfile.index('pip install --no-cache-dir ".[dev]"')
    for mount in ("./src:/app/src", "./api:/app/api", "./mcp:/app/mcp", "./tests:/app/tests"):
        assert mount in compose
    assert dockerignore_path.exists()
    ignored = {
        line.strip()
        for line in dockerignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    required_ignores = {
        ".git",
        ".venv",
        ".worktrees",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
    }
    assert required_ignores <= ignored


def test_setup_verify_exits_nonzero_when_a_quality_gate_fails(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    scripts_dir = repository / "scripts"
    venv_bin = repository / ".venv" / "bin"
    fake_bin = tmp_path / "fake-bin"
    scripts_dir.mkdir(parents=True)
    venv_bin.mkdir(parents=True)
    fake_bin.mkdir()
    setup_script = scripts_dir / "setup.sh"
    setup_script.write_text(Path("scripts/setup.sh").read_text(encoding="utf-8"), encoding="utf-8")
    (venv_bin / "activate").write_text("", encoding="utf-8")

    fake_python = """#!/usr/bin/env bash
if [[ "$1" == "--version" ]]; then
  echo "Python 3.12.0"
  exit 0
fi
if [[ "$*" == *"-m ruff check"* ]]; then
  exit 9
fi
exit 0
"""
    for command in ("python3.11", "python"):
        path = fake_bin / command
        path.write_text(fake_python, encoding="utf-8")
        path.chmod(0o755)
    fake_pip = fake_bin / "pip"
    fake_pip.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_pip.chmod(0o755)

    result = subprocess.run(
        ["bash", str(setup_script), "--verify"],
        cwd=repository,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 9


def test_setup_verify_runs_the_format_gate(tmp_path: Path) -> None:
    """Setup verification should fail when Ruff reports unformatted Python sources."""
    repository = tmp_path / "repository"
    scripts_dir = repository / "scripts"
    venv_bin = repository / ".venv" / "bin"
    fake_bin = tmp_path / "fake-bin"
    scripts_dir.mkdir(parents=True)
    venv_bin.mkdir(parents=True)
    fake_bin.mkdir()
    setup_script = scripts_dir / "setup.sh"
    setup_script.write_text(Path("scripts/setup.sh").read_text(encoding="utf-8"), encoding="utf-8")
    (venv_bin / "activate").write_text("", encoding="utf-8")

    fake_python = """#!/usr/bin/env bash
if [[ "$1" == "--version" ]]; then
  echo "Python 3.12.0"
  exit 0
fi
if [[ "$*" == *"-m ruff format --check"* ]]; then
  exit 9
fi
exit 0
"""
    for command in ("python3.11", "python"):
        path = fake_bin / command
        path.write_text(fake_python, encoding="utf-8")
        path.chmod(0o755)
    fake_pip = fake_bin / "pip"
    fake_pip.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_pip.chmod(0o755)

    result = subprocess.run(
        ["bash", str(setup_script), "--verify"],
        cwd=repository,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 9


def test_contribution_commands_include_the_format_gate() -> None:
    """Contributor instructions should match the formatting gate enforced by CI."""
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "ruff format --check src api mcp tests scripts" in contributing


def test_security_policy_describes_supported_version_and_execution_boundaries() -> None:
    """Security guidance should distinguish trust boundaries without promising isolation."""
    policy = Path("SECURITY.md").read_text(encoding="utf-8").lower()

    assert "0.3.0.dev1" in policy
    assert "main" in policy
    assert "trusted adapters" in policy
    assert "restricted candidate execution" in policy
    assert "not a kernel-level sandbox" in policy


def test_security_policy_distinguishes_restricted_and_bounded_only_candidate_paths() -> None:
    """Security guidance should not apply the restricted policy to every candidate path."""
    policy = Path("SECURITY.md").read_text(encoding="utf-8").lower()

    assert "benchmark candidate python is checked" not in policy
    restricted = policy.split("### restricted candidate execution", 1)[1].split(
        "### adversarial verification", 1
    )[0]
    assert "capability grading" in restricted
    assert "scenario verification" in restricted
    assert "property verification" in restricted
    assert "restrictive ast policy" in restricted
    assert "limited builtins" in restricted

    adversarial = policy.split("### adversarial verification", 1)[1].split(
        "### residual isolation boundary", 1
    )[0]
    assert "bounded subprocess" in adversarial
    assert "does not use the restricted ast or limited-builtins policy" in adversarial
    assert "container or virtual machine" in adversarial


def test_mcp_module_runs_stdio_initialize_and_tools_list():
    """`python -m mcp.server` should be a real stdio JSON-RPC MCP server."""
    requests = (
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}}),
            ]
        )
        + "\n"
    )

    completed = subprocess.run(
        [sys.executable, "-m", "mcp.server"],
        input=requests,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 0
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
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


def test_memory_service_rejects_duplicate_explicit_ids(tmp_path: Path) -> None:
    service = MemoryService(tmp_path / "memory", autoload=False)
    service.add("first", entry_id="duplicate")

    with pytest.raises(ValueError, match="duplicate memory entry id"):
        service.add("second", entry_id="duplicate")


def test_generated_memory_ids_do_not_repeat_after_eviction(tmp_path: Path, monkeypatch) -> None:
    service = MemoryService(tmp_path / "memory", autoload=False)
    service.layers[MemoryLayerType.L1_CURRENT].max_size = 1
    monkeypatch.setattr("src.memory.service.time.time", lambda: 1.234)

    ids = [service.add(f"entry-{index}")["id"] for index in range(3)]

    assert len(set(ids)) == 3


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
