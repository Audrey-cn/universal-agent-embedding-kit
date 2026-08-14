"""UAEK MCP Server — Model Context Protocol 服务端"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import select
import signal
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any, TextIO

from src.version import __version__

from .access import ToolAccessControl
from .auth import MCPAuth, MCPRateLimiter

# JSON-RPC 标准错误码
# -32000 以下为 JSON-RPC 规范保留码
# 自定义错误码使用 -32000 以上
ERR_AUTH_FAILED = -32001  # 认证失败
ERR_RATE_LIMITED = -32002  # 被限流
ERR_ACCESS_DENIED = -32003  # 工具访问被拒绝


class MCPServer:
    """MCP 服务端"""

    def __init__(
        self,
        name: str = "uaek",
        version: str = __version__,
        auth: MCPAuth | None = None,
        rate_limiter: MCPRateLimiter | None = None,
        access_control: ToolAccessControl | None = None,
    ):
        self.name = name
        self.version = version
        self.tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

        # 安全组件（默认实例，开发模式下不拒绝请求）
        self._auth = auth or MCPAuth()
        self._rate_limiter = rate_limiter or MCPRateLimiter()
        self._access_control = access_control or ToolAccessControl()

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        """注册工具"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        self._handlers[name] = handler

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """处理请求"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        # JSON-RPC notifications (no id) must not receive a response
        is_notification = request_id is None

        # 1. 认证检查
        if not self._auth.verify(request):
            if is_notification:
                return None
            return self._error_response(
                request_id, ERR_AUTH_FAILED, "Access denied: invalid or missing token"
            )

        # 2. 速率限制检查
        client_id = self._extract_client_id(request)
        if not self._rate_limiter.consume(client_id):
            if is_notification:
                return None
            return self._error_response(
                request_id, ERR_RATE_LIMITED, "Rate limit exceeded, try again later"
            )

        if method == "initialize":
            return self._handle_initialize(request_id)
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        elif method == "tools/call":
            return await self._handle_call_tool(request_id, params, client_id)
        elif method == "shutdown":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        else:
            if is_notification:
                return None
            return self._error_response(request_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, request_id: Any) -> dict[str, Any]:
        """处理初始化请求"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            },
        }

    def _handle_list_tools(self, request_id: Any) -> dict[str, Any]:
        """处理列出工具请求"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": list(self.tools.values()),
            },
        }

    async def _handle_call_tool(
        self, request_id: Any, params: dict[str, Any], client_id: str = "default"
    ) -> dict[str, Any]:
        """处理调用工具请求"""
        if not isinstance(params, dict):
            return self._error_response(
                request_id, -32602, "Invalid params: params must be an object"
            )
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not isinstance(tool_name, str) or tool_name not in self._handlers:
            return self._error_response(request_id, -32602, f"Tool not found: {tool_name}")
        if not isinstance(arguments, dict):
            return self._error_response(
                request_id, -32602, "Invalid params: arguments must be an object"
            )

        # 工具级访问控制：检查客户端是否有权调用该工具
        if not self._access_control.allow_tool(client_id, tool_name):
            return self._error_response(
                request_id,
                ERR_ACCESS_DENIED,
                f"Access denied: tool '{tool_name}' is not allowed for this client",
            )

        validation_errors = self._validate_tool_arguments(tool_name, arguments)
        if validation_errors:
            return self._error_response(
                request_id, -32602, "Invalid params: " + "; ".join(validation_errors)
            )

        try:
            handler = self._handlers[tool_name]
            result = await handler(**arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False),
                        }
                    ],
                },
            }
        except (TypeError, ValueError) as e:
            return self._error_response(request_id, -32602, str(e))
        except Exception as e:
            return self._error_response(request_id, -32000, str(e))

    def _validate_tool_arguments(self, tool_name: str, arguments: dict[str, Any]) -> list[str]:
        """Validate a small JSON Schema subset used by registered MCP tools."""
        schema = self.tools[tool_name].get("inputSchema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = schema.get("required", []) if isinstance(schema, dict) else []
        errors: list[str] = []

        if isinstance(required, list):
            for field in required:
                if isinstance(field, str) and field not in arguments:
                    errors.append(f"missing required field '{field}'")

        if isinstance(properties, dict):
            for field in arguments:
                if field not in properties:
                    errors.append(f"unknown field '{field}'")
                    continue
                field_schema = properties[field]
                if isinstance(field_schema, dict):
                    errors.extend(
                        self._validate_schema_value(field, arguments[field], field_schema)
                    )
        return errors

    def _validate_schema_value(
        self,
        field: str,
        value: Any,
        schema: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        expected_type = schema.get("type")
        if isinstance(expected_type, str) and not self._matches_schema_type(value, expected_type):
            errors.append(f"field '{field}' must be {expected_type}")
        enum = schema.get("enum")
        if isinstance(enum, list) and value not in enum:
            errors.append(f"field '{field}' must be one of {enum}")
        items = schema.get("items")
        if expected_type == "array" and isinstance(items, dict) and isinstance(value, list):
            item_type = items.get("type")
            if isinstance(item_type, str):
                for index, item in enumerate(value):
                    if not self._matches_schema_type(item, item_type):
                        errors.append(f"field '{field}[{index}]' must be {item_type}")
        return errors

    def _matches_schema_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        return True

    def _error_response(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        """错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _extract_client_id(self, request: dict[str, Any]) -> str:
        """从请求中提取客户端标识

        优先从 _meta.client_id 提取，其次从 _meta.headers 中提取，
        默认返回 "default"。
        """
        meta = request.get("_meta", {})
        if not isinstance(meta, dict):
            return "default"

        # 显式指定的 client_id
        client_id = meta.get("client_id")
        if isinstance(client_id, str) and client_id:
            return client_id

        # 从 headers 中尝试提取
        headers = meta.get("headers", {})
        if isinstance(headers, dict):
            for key in ("X-Client-ID", "x-client-id", "Client-ID"):
                cid = headers.get(key)
                if isinstance(cid, str) and cid:
                    return cid

        return "default"


def create_server() -> MCPServer:
    """创建 MCP 服务端"""
    from .tools.effort import register_effort_tool
    from .tools.memory import register_memory_tool
    from .tools.verify import register_verify_tool
    from .tools.workflow import register_workflow_tool

    server = MCPServer(name="uaek")

    # 注册工具
    register_verify_tool(server)
    register_effort_tool(server)
    register_workflow_tool(server)
    register_memory_tool(server)

    # 授予默认客户端所有工具的访问权限
    server._access_control.allow_all_tools_for_client(list(server.tools.keys()), "default")

    return server


def _resolve_idle_timeout(value: float | None) -> float:
    if value is not None:
        timeout = value
    else:
        raw = os.environ.get("UAEK_MCP_IDLE_TIMEOUT", "300")
        try:
            timeout = float(raw)
        except ValueError as exc:
            raise ValueError("UAEK_MCP_IDLE_TIMEOUT must be a number") from exc
    if timeout < 0:
        raise ValueError("idle timeout must be non-negative")
    return timeout


async def run_stdio(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    server: MCPServer | None = None,
    idle_timeout: float | None = None,
) -> None:
    """Run a newline-delimited JSON-RPC loop for stdio MCP hosts.

    Args:
        idle_timeout: Seconds of inactivity before graceful shutdown.
            Defaults to UAEK_MCP_IDLE_TIMEOUT env var (or 300s).
            Set to 0 to disable.
    """
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    server = server or create_server()

    idle_timeout = _resolve_idle_timeout(idle_timeout)

    # Signal handling for graceful shutdown
    shutdown_flag = False

    def _signal_handler(signum: int, frame: object) -> None:
        nonlocal shutdown_flag
        shutdown_flag = True

    original_sigterm = signal.signal(signal.SIGTERM, _signal_handler)
    original_sigint = signal.signal(signal.SIGINT, _signal_handler)

    # Track idle time
    last_activity = time.monotonic()
    poll_interval = 1.0
    shutdown_reason = None

    # Check if the input stream supports select (needs a real file descriptor)
    try:
        input_stream.fileno()
        _select_supported = True
    except (io.UnsupportedOperation, AttributeError, OSError):
        _select_supported = False
    try:
        while not shutdown_flag:
            # Poll stdin with timeout for idle detection
            if _select_supported:
                try:
                    ready_streams, _, _ = select.select([input_stream], [], [], poll_interval)
                    is_readable = bool(ready_streams)
                except InterruptedError:
                    if shutdown_flag:
                        break
                    continue
            else:
                # Fallback for in-memory streams (StringIO, etc.)
                is_readable = True

            if is_readable:
                line = input_stream.readline()
                if not line:
                    shutdown_reason = "stdin EOF"
                    break
                if not line.strip():
                    continue

                last_activity = time.monotonic()

                request_id = None
                method = None
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError("JSON-RPC request must be an object")
                    request_id = request.get("id")
                    method = request.get("method")
                    response = await server.handle_request(request)
                except json.JSONDecodeError as exc:
                    response = server._error_response(request_id, -32700, f"Parse error: {exc.msg}")
                except Exception as exc:
                    response = server._error_response(request_id, -32600, str(exc))

                if response is None:
                    continue
                output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
                output_stream.flush()

                if method == "shutdown":
                    shutdown_reason = "shutdown request"
                    break
            else:
                # No data available - check idle timeout
                if idle_timeout and idle_timeout > 0:
                    idle_seconds = time.monotonic() - last_activity
                    if idle_seconds > idle_timeout:
                        shutdown_reason = f"idle timeout ({idle_timeout}s)"
                        break
    finally:
        signal.signal(signal.SIGTERM, original_sigterm)
        signal.signal(signal.SIGINT, original_sigint)

    if shutdown_reason:
        print(f"[uaek-mcp] shutdown: {shutdown_reason}", file=sys.stderr, flush=True)


def main() -> None:
    """Console entrypoint for `python -m mcp.server`."""
    parser = argparse.ArgumentParser(description="UAEK MCP Server")
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="Idle timeout in seconds (default: 300, 0 to disable)",
    )
    args = parser.parse_args()
    asyncio.run(run_stdio(idle_timeout=args.idle_timeout))


if __name__ == "__main__":
    main()
