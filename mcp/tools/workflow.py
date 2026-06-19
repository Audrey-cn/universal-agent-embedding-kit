"""MCP Tools — 工作流工具"""

from __future__ import annotations

from typing import Any


def register_workflow_tool(server) -> None:
    """注册工作流工具"""
    workflows: dict[str, dict[str, Any]] = {}

    async def workflow_create(
        workflow_id: str,
        workflow_type: str = "sequential",
    ) -> dict[str, Any]:
        """创建工作流"""
        if workflow_type not in {"sequential", "parallel"}:
            raise ValueError(f"Unsupported workflow type: {workflow_type}")
        workflows[workflow_id] = {
            "id": workflow_id,
            "type": workflow_type,
            "tasks": [],
        }

        return {
            "workflow_id": workflow_id,
            "type": workflow_type,
            "status": "created",
        }

    async def workflow_add_task(
        workflow_id: str,
        task_id: str,
        task_name: str,
        func_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        """添加任务到工作流"""
        if workflow_id not in workflows:
            raise KeyError(f"Workflow not found: {workflow_id}")
        workflows[workflow_id]["tasks"].append(
            {
                "id": task_id,
                "name": task_name,
                "action": func_name,
                "args": args or [],
                "kwargs": kwargs or {},
                "dependencies": dependencies or [],
            }
        )
        return {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "status": "added",
        }

    async def workflow_execute(
        workflow_id: str,
    ) -> dict[str, Any]:
        """执行工作流"""
        from src.workflow import execute_workflow_config

        if workflow_id not in workflows:
            raise KeyError(f"Workflow not found: {workflow_id}")
        return execute_workflow_config(workflows[workflow_id])

    server.register_tool(
        name="uaek_workflow_create",
        description="创建工作流",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "工作流 ID",
                },
                "workflow_type": {
                    "type": "string",
                    "enum": ["sequential", "parallel"],
                    "description": "工作流类型",
                    "default": "sequential",
                },
            },
            "required": ["workflow_id"],
        },
        handler=workflow_create,
    )

    server.register_tool(
        name="uaek_workflow_add_task",
        description="添加任务到工作流",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "工作流 ID",
                },
                "task_id": {
                    "type": "string",
                    "description": "任务 ID",
                },
                "task_name": {
                    "type": "string",
                    "description": "任务名称",
                },
                "func_name": {
                    "type": "string",
                    "description": "函数名称",
                },
                "args": {
                    "type": "array",
                    "description": "位置参数",
                },
                "kwargs": {
                    "type": "object",
                    "description": "关键字参数",
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "依赖任务 ID 列表",
                },
            },
            "required": ["workflow_id", "task_id", "task_name", "func_name"],
        },
        handler=workflow_add_task,
    )

    server.register_tool(
        name="uaek_workflow_execute",
        description="执行工作流",
        input_schema={
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "工作流 ID",
                },
            },
            "required": ["workflow_id"],
        },
        handler=workflow_execute,
    )
