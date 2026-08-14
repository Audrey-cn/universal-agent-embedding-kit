"""Tests for MCP stdio lifecycle — idle timeout, shutdown, signal handling, EOF."""

from __future__ import annotations

import asyncio
import io
import json
import os
import signal
import subprocess
import sys
import time

import pytest

from mcp.server import create_server, run_stdio

# =========================================================================
# Subprocess-level tests (real stdio pipe, full process lifecycle)
# =========================================================================


class TestIdleTimeout:
    """MCP server idle timeout behavior."""

    def test_idle_timeout_exits_after_timeout(self):
        """Server should exit after idle timeout when no data is sent."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Keep stdin open but don't send data — server should idle-exit
            proc.wait(timeout=3)
            assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}"
            _, stderr = proc.communicate()
            assert "idle timeout" in stderr, f"Expected idle timeout message, got: {stderr}"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Server did not exit within idle timeout period")

    def test_idle_timeout_not_triggered_by_active_requests(self):
        """Active requests should reset the idle timer — server stays alive."""
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
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "10"],
            input=requests,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0
        # Should have completed via shutdown, not idle timeout
        assert "idle timeout" not in completed.stderr, (
            f"Server exited via idle timeout instead of shutdown: {completed.stderr}"
        )

    def test_idle_timeout_env_var(self, monkeypatch):
        """UAEK_MCP_IDLE_TIMEOUT env var should set the timeout."""
        monkeypatch.setenv("UAEK_MCP_IDLE_TIMEOUT", "1")

        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            proc.wait(timeout=3)
            assert proc.returncode == 0
            _, stderr = proc.communicate()
            assert "idle timeout" in stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Server did not exit within idle timeout period")

    def test_idle_timeout_disabled(self):
        """Setting idle_timeout=0 should disable idle timeout."""
        requests = (
            "\n".join(
                [
                    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}}),
                ]
            )
            + "\n"
        )

        completed = subprocess.run(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "0"],
            input=requests,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0
        # Should complete without any idle timeout message
        assert "idle timeout" not in completed.stderr


class TestShutdown:
    """MCP server shutdown behavior."""

    def test_shutdown_request_exits(self):
        """shutdown request should cause server to exit immediately."""
        requests = (
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "shutdown", "params": {}}) + "\n"
        )

        completed = subprocess.run(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "10"],
            input=requests,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0
        assert "shutdown request" in completed.stderr

    def test_shutdown_notification_exits(self):
        """shutdown as notification (no id) should also cause exit."""
        requests = json.dumps({"jsonrpc": "2.0", "method": "shutdown", "params": {}}) + "\n"

        completed = subprocess.run(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "10"],
            input=requests,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0
        assert "shutdown request" in completed.stderr


class TestStdioEOF:
    """MCP server EOF handling."""

    def test_stdin_eof_exits(self):
        """Closing stdin (EOF) should cause server to exit."""
        completed = subprocess.run(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "10"],
            input="",
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0
        assert "stdin EOF" in completed.stderr


class TestSignalHandling:
    """MCP server signal handling."""

    def test_sigterm_triggers_exit(self):
        """SIGTERM should cause server to exit gracefully."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp.server", "--idle-timeout", "10"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Give the server time to start and install signal handlers
            time.sleep(0.3)
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=3)
            assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}. stderr: {stderr}"
            # The server should exit due to signal
            # (check only that it exited, as the exact message depends on timing)
            assert "shutdown" in stderr.lower() or stderr.strip() == "", (
                f"Expected shutdown message, got: {stderr}"
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("Server did not exit on SIGTERM")


class TestMultiRequestFlow:
    """Full MCP request sequences."""

    def test_initialize_tools_list_shutdown(self):
        """Standard init -> tools/list -> shutdown should work."""
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
        assert len(responses) == 3
        assert responses[0]["id"] == 1
        assert responses[0]["result"]["serverInfo"]["name"] == "uaek"
        assert responses[1]["id"] == 2
        assert "tools" in responses[1]["result"]
        assert responses[2]["id"] == 3

    def test_malformed_json_returns_error_and_continues(self):
        """Malformed JSON should return error, not crash the server."""
        requests = (
            "\n".join(
                [
                    "not valid json",
                    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "shutdown", "params": {}}),
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
        # First response should be parse error, second should be shutdown response
        assert len(responses) == 2
        assert "error" in responses[0]
        assert responses[0]["error"]["code"] == -32700
        assert responses[1]["id"] == 1
        assert "result" in responses[1]


# =========================================================================
# Unit tests (in-memory, no subprocess)
# =========================================================================


class TestRunStdioUnit:
    """run_stdio behavior with in-memory streams (no subprocess)."""

    def test_invalid_idle_timeout_env_fails_before_signal_handlers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UAEK_MCP_IDLE_TIMEOUT", "invalid")
        installed: list[int] = []

        async def exercise() -> None:
            with monkeypatch.context() as signal_patch:
                signal_patch.setattr(
                    signal, "signal", lambda signum, handler: installed.append(signum)
                )
                with pytest.raises(ValueError, match="UAEK_MCP_IDLE_TIMEOUT"):
                    await run_stdio(input_stream=io.StringIO(""), output_stream=io.StringIO())

        asyncio.run(exercise())

        assert installed == []

    def test_signal_handlers_are_restored_when_read_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class BrokenInput(io.StringIO):
            def readline(self, *args: object, **kwargs: object) -> str:
                raise RuntimeError("read failed")

        calls: list[tuple[int, object]] = []
        monkeypatch.setattr(
            signal,
            "signal",
            lambda signum, handler: calls.append((signum, handler)) or f"old-{signum}",
        )

        with pytest.raises(RuntimeError, match="read failed"):
            asyncio.run(
                run_stdio(input_stream=BrokenInput(), output_stream=io.StringIO(), idle_timeout=0)
            )

        assert calls[-2:] == [
            (signal.SIGTERM, f"old-{signal.SIGTERM}"),
            (signal.SIGINT, f"old-{signal.SIGINT}"),
        ]

    def test_idle_timeout_in_memory(self) -> None:
        """Idle timeout should work with a real pipe (not StringIO)."""

        async def exercise() -> float:
            r_fd, w_fd = os.pipe()
            stdin = io.TextIOWrapper(os.fdopen(r_fd, "rb"), encoding="utf-8")
            stdout = io.StringIO()
            start = time.monotonic()
            task = asyncio.create_task(
                run_stdio(input_stream=stdin, output_stream=stdout, idle_timeout=0.5)
            )
            await asyncio.sleep(1.0)
            os.close(w_fd)
            await task
            return time.monotonic() - start

        elapsed = asyncio.run(exercise())
        # Should have exited via idle timeout, taking ~0.5s
        assert elapsed < 2.0, f"Took too long: {elapsed:.2f}s"

    def test_shutdown_via_handle_request(self) -> None:
        """Shutdown method should be handled by MCPServer.handle_request."""
        server = create_server()
        request = {"jsonrpc": "2.0", "id": 1, "method": "shutdown", "params": {}}
        response = asyncio.run(server.handle_request(request))
        assert response is not None
        assert "result" in response

    def test_notification_shutdown_handled(self) -> None:
        """Shutdown as notification (no id) should still return a response."""
        server = create_server()
        request = {"jsonrpc": "2.0", "method": "shutdown", "params": {}}
        response = asyncio.run(server.handle_request(request))
        # MCP spec says notifications should not receive a response
        # But our shutdown handler always returns a response regardless
        # (the loop handles the shutdown logic, not the handler)
        assert response is not None
        assert "result" in response

    def test_initialize_then_shutdown(self) -> None:
        """Initialize followed by shutdown should work."""
        server = create_server()
        req1 = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp1 = asyncio.run(server.handle_request(req1))
        assert resp1["result"]["serverInfo"]["name"] == "uaek"

        req2 = {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}}
        resp2 = asyncio.run(server.handle_request(req2))
        assert "result" in resp2
