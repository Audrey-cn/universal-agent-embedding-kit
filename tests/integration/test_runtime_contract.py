from __future__ import annotations

import json
import subprocess
import sys


def test_package_mcp_entrypoint_executes_a_safe_workflow() -> None:
    """`python -m mcp` must expose the same usable workflow surface as mcp.server."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "uaek_workflow_create",
                "arguments": {"workflow_id": "contract", "workflow_type": "sequential"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "uaek_workflow_add_task",
                "arguments": {
                    "workflow_id": "contract",
                    "task_id": "echo",
                    "task_name": "Echo",
                    "func_name": "echo",
                    "args": ["shared-result"],
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "uaek_workflow_execute",
                "arguments": {"workflow_id": "contract"},
            },
        },
        {"jsonrpc": "2.0", "id": 5, "method": "shutdown", "params": {}},
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "mcp"],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert [response["id"] for response in responses] == [1, 2, 3, 4, 5]
    assert all("error" not in response for response in responses)
    workflow = json.loads(responses[3]["result"]["content"][0]["text"])
    assert workflow["success"] is True
    assert workflow["task_results"] == {"echo": "shared-result"}


def test_package_mcp_entrypoint_rejects_malformed_json() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "mcp"],
        input='{not-json}\n{"jsonrpc":"2.0","id":2,"method":"shutdown","params":{}}\n',
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert responses[0]["error"]["code"] == -32700
    assert responses[1]["id"] == 2


def test_package_mcp_entrypoint_preserves_method_dependent_no_id_behavior() -> None:
    requests = [
        {"jsonrpc": "2.0", "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}},
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "mcp"],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert [response["id"] for response in responses] == [None, None, 3]
    assert responses[0]["result"]["serverInfo"]["name"] == "uaek"
    assert "tools" in responses[1]["result"]
    assert responses[2] == {"jsonrpc": "2.0", "id": 3, "result": {}}
