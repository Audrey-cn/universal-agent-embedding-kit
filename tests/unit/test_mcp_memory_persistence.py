"""Real storage regressions for MCP restarts and competing memory writers."""

from __future__ import annotations

import asyncio
import builtins
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mcp.server import create_server
from src.memory import MemoryService
from src.memory.interface import MemoryEntry, MemoryLayerType
from src.memory.persistence import MemoryPersistence


@pytest.fixture(autouse=True)
def isolated_memory_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    temporary = tmp_path / "tmp"
    home.mkdir()
    temporary.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(temporary))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("UAEK_MCP_TOKEN", raising=False)


def _stdio(*calls: tuple[str, dict]) -> list[dict]:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": index,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        for index, (name, arguments) in enumerate(calls, 1)
    ]
    requests.append({"jsonrpc": "2.0", "id": len(requests) + 1, "method": "shutdown"})
    responses = _stdio_wire("".join(json.dumps(request) + "\n" for request in requests))
    assert len(responses) == len(requests), responses
    return responses[:-1]


def _stdio_wire(requests: str) -> list[dict]:
    completed = subprocess.run(
        [sys.executable, "-m", "mcp.server", "--idle-timeout", "0"],
        input=requests,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return [json.loads(line) for line in completed.stdout.splitlines()]


def _payload(response: dict) -> dict:
    assert "error" not in response, response
    return json.loads(response["result"]["content"][0]["text"])


def _store() -> Path:
    return Path.home() / ".uaek" / "memory"


def _file_bytes() -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in _store().glob("*.json")}


def _seed() -> list[dict]:
    return [
        _payload(response)
        for response in _stdio(
            ("uaek_memory_add", {"content": "historic l1 decision", "layer": "l1"}),
            ("uaek_memory_add", {"content": "historic l2 decision", "layer": "l2"}),
            ("uaek_memory_add", {"content": "historic l3 decision", "layer": "l3"}),
        )
    ]


def test_stdio_restart_queries_persisted_history() -> None:
    _seed()

    result = _payload(_stdio(("uaek_memory_query", {"query": "historic"}))[0])

    assert {entry["content"] for entry in result["results"]} == {
        "historic l1 decision",
        "historic l2 decision",
        "historic l3 decision",
    }


@pytest.mark.parametrize("operation", ["add", "compress", "delete"])
def test_stdio_restart_mutations_preserve_unrelated_history(operation: str) -> None:
    historical = _seed()
    if operation == "add":
        arguments = {"content": "new decision"}
    elif operation == "compress":
        arguments = {"layer": "l1", "target_ratio": 1.0}
    else:
        arguments = {"entry_id": historical[0]["id"]}

    result = _payload(_stdio((f"uaek_memory_{operation}", arguments))[0])
    if operation == "delete":
        assert result["removed"] is True
    contents = {entry["content"] for entry in MemoryService(_store()).query("")["results"]}
    expected = {"historic l1 decision", "historic l2 decision", "historic l3 decision"}
    if operation == "add":
        expected.add("new decision")
    elif operation == "delete":
        expected.remove("historic l1 decision")
    assert contents == expected
    assert _payload(_stdio(("uaek_memory_query", {"query": ""}))[0])["total"] == len(expected)


@pytest.mark.parametrize(
    "broken",
    [
        b'{"truncated":',
        b"\xffnot-utf8",
        b'[{"id":"bad","content":7,"layer":"l1_current"}]',
        b'[{"id":"bad","content":"x","layer":"unknown"}]',
        b'[{"id":"bad","content":"x","layer":"l1_current","importance":"high"}]',
        b'[{"id":"bad","content":"x","layer":"l1_current","tags":null}]',
        b'[{"id":"same","content":"one","layer":"l1_current"},'
        b'{"id":"same","content":"two","layer":"l1_current"}]',
    ],
)
def test_corrupt_startup_rejects_tools_without_changing_original_bytes(broken: bytes) -> None:
    historical = _seed()
    (_store() / "l1_current.json").write_bytes(broken)
    original = _file_bytes()

    responses = _stdio(
        ("uaek_memory_query", {"query": "historic"}),
        ("uaek_memory_add", {"content": "must not overwrite"}),
        ("uaek_memory_compress", {}),
        ("uaek_memory_delete", {"entry_id": historical[1]["id"]}),
    )

    for response in responses:
        assert "result" not in response, response
        assert response["error"]["code"] == -32000
        assert "corrupt memory file" in response["error"]["message"]
    assert _file_bytes() == original


@pytest.mark.parametrize("operation", ["add", "compress", "delete"])
def test_corruption_after_connection_rejects_write_and_preserves_bytes(operation: str) -> None:
    historical = _seed()
    server = create_server()
    (_store() / "l3_persistent.json").write_bytes(b'{"truncated":')
    original = _file_bytes()
    arguments = {
        "add": {"content": "must not overwrite"},
        "compress": {},
        "delete": {"entry_id": historical[0]["id"]},
    }[operation]

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": f"uaek_memory_{operation}", "arguments": arguments},
            }
        )
    )

    assert response is not None
    assert "result" not in response, response
    assert response["error"]["code"] == -32000
    assert "corrupt memory file" in response.get("error", {}).get("message", "")
    assert _file_bytes() == original


def test_reconnected_mcp_instance_refreshes_before_next_write() -> None:
    _seed()
    first = create_server()
    second = create_server()

    async def add(server, content: str) -> dict:
        return await server._handlers["uaek_memory_add"](content=content)

    asyncio.run(add(first, "first connection decision"))
    asyncio.run(add(second, "second connection decision"))
    asyncio.run(add(first, "first connection again decision"))

    assert MemoryService(_store()).query("")["total"] == 6


def test_stale_service_cannot_overwrite_another_services_commit() -> None:
    _seed()
    stale = MemoryService(_store())
    current = MemoryService(_store())
    current.add("another writer decision")
    current.persist()
    original = _file_bytes()
    stale.add("stale writer decision")

    with pytest.raises(RuntimeError, match="changed.*restore"):
        stale.persist()

    assert _file_bytes() == original
    stale.restore()
    stale.add("retried writer decision")
    stale.persist()
    assert MemoryService(_store()).query("")["total"] == 5


def test_unloaded_service_cannot_overwrite_existing_storage() -> None:
    _seed()
    original = _file_bytes()
    unloaded = MemoryService(_store(), autoload=False)
    unloaded.add("unloaded writer decision")

    with pytest.raises(RuntimeError, match="restore"):
        unloaded.persist()

    assert _file_bytes() == original


def test_failed_restore_cannot_be_followed_by_destructive_persist() -> None:
    _seed()
    service = MemoryService(_store())
    (_store() / "l3_persistent.json").write_bytes(b'{"truncated":')
    original = _file_bytes()

    with pytest.raises(ValueError, match="corrupt memory file"):
        service.restore()
    service.add("must not overwrite")
    with pytest.raises((ValueError, RuntimeError)):
        service.persist()

    assert _file_bytes() == original


@pytest.mark.parametrize("conflict", ["corrupt", "stale"])
def test_clear_cannot_bypass_storage_validation(conflict: str) -> None:
    _seed()
    service = MemoryService(_store())
    if conflict == "corrupt":
        (_store() / "l3_persistent.json").write_bytes(b'{"truncated":')
    else:
        other = MemoryService(_store())
        other.add("another writer decision")
        other.persist()
    original = _file_bytes()

    with pytest.raises((ValueError, RuntimeError)):
        service.clear()

    assert _file_bytes() == original


def test_restore_discards_derived_indexes_of_deleted_entries() -> None:
    service = MemoryService(_store())
    added = service.add("obsolete architecture decision", entry_id="obsolete")
    service.index_to_vector(added["id"])
    service.persist()
    other = MemoryService(_store())
    other.remove("obsolete")
    other.add("current architecture decision", entry_id="current")
    other.persist()

    service.restore()

    assert service.vector_store.size() == 0
    entities = service.graph_query()["entities"]
    assert {entity["name"] for entity in entities} == {"current"}


def test_storage_lock_is_cross_process_bounded_and_released_on_process_exit() -> None:
    service = MemoryService(_store())
    script = (
        "from pathlib import Path\n"
        "from src.memory.persistence import MemoryPersistence\n"
        "with MemoryPersistence(Path.home() / '.uaek' / 'memory').locked():\n"
        " print('locked', flush=True)\n"
        " input()\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "locked"
        service.add("waiting writer decision")
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="busy"):
            service.persist()
        assert time.monotonic() - started < 4
    finally:
        process.kill()
        process.communicate(timeout=5)

    service.persist()
    assert MemoryService(_store()).query("")["total"] == 1


@pytest.mark.skipif(os.name != "posix", reason="simulates missing POSIX lock support")
def test_unavailable_platform_lock_rejects_write_without_changing_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed()
    service = MemoryService(_store())
    service.add("must not overwrite")
    original = _file_bytes()
    real_import = builtins.__import__

    def import_without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("platform has no fcntl")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_fcntl)

    with pytest.raises(RuntimeError, match="locking is unavailable"):
        service.persist()

    assert _file_bytes() == original


@pytest.mark.parametrize("number", ["1e309", "Infinity", "-Infinity", "NaN"])
def test_stdio_nonfinite_write_rejected_and_history_readable_after_restart(number: str) -> None:
    _seed()
    original = _file_bytes()
    responses = _stdio_wire(
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
        '{"name":"uaek_memory_add","arguments":{"content":"invalid decision",'
        '"importance":' + number + "}}}\n"
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":'
        '{"name":"uaek_memory_query","arguments":{"query":"historic"}}}\n'
        '{"jsonrpc":"2.0","id":3,"method":"shutdown"}\n'
    )

    assert _file_bytes() == original
    assert "result" not in responses[0]
    assert "error" in responses[0]
    assert _payload(responses[1])["total"] == 3
    assert _payload(_stdio(("uaek_memory_query", {"query": "historic"}))[0])["total"] == 3


@pytest.mark.parametrize("entrypoint", ["service", "save_all", "save"])
@pytest.mark.parametrize(
    "invalid",
    ["importance_inf", "importance_huge", "metadata_nan", "metadata_set", "content", "tags"],
)
def test_invalid_candidate_cannot_replace_any_committed_layer(
    entrypoint: str, invalid: str
) -> None:
    _seed()
    service = MemoryService(_store())
    original = _file_bytes()
    candidate = MemoryEntry(id="invalid", content="invalid decision", layer=MemoryLayerType.L2_TASK)
    if invalid == "importance_inf":
        candidate.importance = float("inf")
    elif invalid == "importance_huge":
        candidate.importance = 10**399
    elif invalid == "metadata_nan":
        candidate.metadata = {"nested": [{"value": float("nan")}]}  # nested finite JSON check
    elif invalid == "metadata_set":
        candidate.metadata = {"nested": {"unsupported"}}
    elif invalid == "content":
        candidate.content = 7  # type: ignore[assignment]
    else:
        candidate.tags = [None]  # type: ignore[list-item]
    service.add("earlier valid candidate decision", layer="l1")
    service.layers[MemoryLayerType.L2_TASK].add(candidate)
    layers = {
        layer_type: list(layer.entries.values()) for layer_type, layer in service.layers.items()
    }

    with pytest.raises(ValueError):
        if entrypoint == "service":
            service.persist()
        elif entrypoint == "save_all":
            service.persistence.save_all(layers)
        else:
            service.persistence.save(layers[MemoryLayerType.L2_TASK], MemoryLayerType.L2_TASK)

    assert _file_bytes() == original
    assert MemoryService(_store()).query("historic")["total"] == 3


def test_oversized_persisted_integer_disables_memory_without_crashing_other_tools() -> None:
    _seed()
    path = _store() / "l1_current.json"
    data = json.loads(path.read_text())
    data[0]["importance"] = 10**399
    path.write_text(json.dumps(data), encoding="utf-8")
    original = _file_bytes()

    responses = _stdio(
        ("uaek_memory_query", {"query": "historic"}),
        ("uaek_effort", {"task_description": "fix typo"}),
    )

    assert responses[0]["error"]["code"] == -32000
    assert "corrupt memory file" in responses[0]["error"]["message"]
    assert "l1_current.json" in responses[0]["error"]["message"]
    assert _payload(responses[1])["level"] in {"low", "medium", "high"}
    assert _file_bytes() == original


def test_busy_initialization_recovers_on_same_server_after_lock_release() -> None:
    _seed()
    persistence = MemoryPersistence(_store())
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "uaek_memory_query", "arguments": {"query": "historic"}},
    }

    with persistence.locked():
        server = create_server()
        blocked = asyncio.run(server.handle_request(request))
        assert blocked is not None
        assert blocked["error"]["code"] == -32000
        assert "busy" in blocked["error"]["message"]

    recovered = asyncio.run(server.handle_request(request))
    assert recovered is not None
    assert _payload(recovered)["total"] == 3
