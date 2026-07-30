"""MCP Tools — 记忆工具"""

from __future__ import annotations

from typing import Any


def register_memory_tool(server) -> None:
    """注册记忆工具"""
    from src.memory import MemoryService

    _service_error: str | None = None
    try:
        service = MemoryService(autoload=False)
    except (OSError, PermissionError) as exc:
        service = None
        _service_error = str(exc)

    async def memory_add(
        content: str,
        layer: str = "l1",
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """添加记忆"""
        if service is None:
            return {"error": f"Memory storage not available: {_service_error}"}
        entry = service.add(
            content=content,
            layer=layer,
            importance=importance,
            tags=tags or [],
        )
        service.persist()

        return {
            "id": entry["id"],
            "content": entry["content"],
            "layer": entry["layer"],
            "importance": entry["importance"],
            "status": "added",
        }

    async def memory_query(
        query: str,
        layer: str | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """查询记忆"""
        if service is None:
            return {"error": f"Memory storage not available: {_service_error}"}
        return service.query(
            query,
            layer=layer,
            tags=tags or [],
            min_importance=min_importance,
            limit=limit,
        )

    async def memory_compress(
        layer: str | None = None,
        target_ratio: float = 0.5,
    ) -> dict[str, Any]:
        """压缩记忆"""
        if service is None:
            return {"error": f"Memory storage not available: {_service_error}"}
        result = service.compress(layer=layer, target_ratio=target_ratio)
        service.persist()
        return result

    server.register_tool(
        name="uaek_memory_add",
        description="添加记忆",
        input_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "记忆内容",
                },
                "layer": {
                    "type": "string",
                    "enum": ["l1", "l2", "l3"],
                    "description": "记忆层",
                    "default": "l1",
                },
                "importance": {
                    "type": "number",
                    "description": "重要性 0.0-1.0",
                    "default": 0.5,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表",
                },
            },
            "required": ["content"],
        },
        handler=memory_add,
    )

    server.register_tool(
        name="uaek_memory_query",
        description="查询记忆",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询关键词",
                },
                "layer": {
                    "type": "string",
                    "enum": ["l1", "l2", "l3"],
                    "description": "记忆层",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签过滤",
                },
                "min_importance": {
                    "type": "number",
                    "description": "最小重要性",
                    "default": 0.0,
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        handler=memory_query,
    )

    async def memory_delete(
        entry_id: str,
        layer: str | None = None,
    ) -> dict[str, Any]:
        """删除记忆条目"""
        if service is None:
            return {"error": f"Memory storage not available: {_service_error}"}
        result = service.remove(entry_id, layer=layer)
        if result["removed"]:
            service.persist()
        return result

    server.register_tool(
        name="uaek_memory_delete",
        description="按 ID 删除记忆条目",
        input_schema={
            "type": "object",
            "properties": {
                "entry_id": {
                    "type": "string",
                    "description": "要删除的记忆条目 ID",
                },
                "layer": {
                    "type": "string",
                    "enum": ["l1", "l2", "l3"],
                    "description": "限定搜索的记忆层（可选）",
                },
            },
            "required": ["entry_id"],
        },
        handler=memory_delete,
    )

    server.register_tool(
        name="uaek_memory_compress",
        description="压缩记忆",
        input_schema={
            "type": "object",
            "properties": {
                "layer": {
                    "type": "string",
                    "enum": ["l1", "l2", "l3"],
                    "description": "记忆层",
                },
                "target_ratio": {
                    "type": "number",
                    "description": "目标压缩率",
                    "default": 0.5,
                },
            },
        },
        handler=memory_compress,
    )
