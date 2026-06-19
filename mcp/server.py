"""UAEK MCP Server — Model Context Protocol 服务端"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

# MCP 服务端实现（简化版，实际使用需要 mcp 库）
# 这里提供的是接口定义和工具注册逻辑


class MCPServer:
    """MCP 服务端"""

    def __init__(self, name: str = "uaek", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

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

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理请求"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return self._handle_initialize(request_id)
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        elif method == "tools/call":
            return await self._handle_call_tool(request_id, params)
        else:
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

    async def _handle_call_tool(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """处理调用工具请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self._handlers:
            return self._error_response(request_id, -32602, f"Tool not found: {tool_name}")

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
        except Exception as e:
            return self._error_response(request_id, -32000, str(e))

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


def create_server() -> MCPServer:
    """创建 MCP 服务端"""
    from .tools.effort import register_effort_tool
    from .tools.memory import register_memory_tool
    from .tools.verify import register_verify_tool
    from .tools.workflow import register_workflow_tool

    server = MCPServer(name="uaek", version="1.0.0")

    # 注册工具
    register_verify_tool(server)
    register_effort_tool(server)
    register_workflow_tool(server)
    register_memory_tool(server)

    return server
