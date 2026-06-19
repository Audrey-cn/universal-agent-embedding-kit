"""Workflow runtime helpers for product entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .interface import Task, Workflow, WorkflowResult
from .parallel import ParallelScheduler
from .sequential import SequentialScheduler


def load_workflow_config(config_path: Path) -> dict[str, Any]:
    """Load a workflow config from YAML or JSON."""
    raw = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("Workflow config must be an object")
    return data


def execute_workflow_config(config: dict[str, Any]) -> dict[str, Any]:
    """Build and execute a workflow config, returning a serializable result."""
    workflow = build_workflow(config)
    result = workflow.execute()
    return serialize_workflow_result(result)


def build_workflow(config: dict[str, Any]) -> Workflow:
    """Build a Workflow from a serializable config."""
    workflow_id = str(config.get("id") or config.get("workflow_id") or "workflow")
    workflow_type = str(config.get("type", "sequential"))
    tasks_data = config.get("tasks", [])
    if not isinstance(tasks_data, list):
        raise ValueError("Workflow config field 'tasks' must be a list")

    if workflow_type == "parallel":
        workflow: Workflow = ParallelScheduler(
            workflow_id,
            max_workers=int(config.get("max_workers", 4)),
            fail_fast=bool(config.get("fail_fast", False)),
        )
    elif workflow_type == "sequential":
        workflow = SequentialScheduler(workflow_id, fail_fast=bool(config.get("fail_fast", True)))
    else:
        raise ValueError(f"Unsupported workflow type: {workflow_type}")

    for index, task_data in enumerate(tasks_data):
        if not isinstance(task_data, dict):
            raise ValueError(f"Workflow task at index {index} must be an object")
        task = _task_from_config(task_data)
        workflow.add_task(task)

    return workflow


def serialize_workflow_result(result: WorkflowResult) -> dict[str, Any]:
    """Serialize WorkflowResult for CLI/API/MCP responses."""
    tasks = [_serialize_task(task) for task in result.tasks]
    return {
        "workflow_id": result.workflow_id,
        "success": result.success,
        "duration": result.duration,
        "tasks": tasks,
        "completed_tasks": [task for task in tasks if task["status"] == "completed"],
        "failed_tasks": [task for task in tasks if task["status"] == "failed"],
        "skipped_tasks": [task for task in tasks if task["status"] == "skipped"],
        "task_results": {task.id: task.result for task in result.tasks},
        "errors": [str(error) for error in result.errors],
    }


def _task_from_config(task_data: dict[str, Any]) -> Task:
    task_id = str(task_data.get("id") or "")
    task_name = str(task_data.get("name") or task_id)
    action = str(task_data.get("action") or task_data.get("func_name") or "noop")
    args = task_data.get("args", [])
    kwargs = task_data.get("kwargs", {})
    dependencies = task_data.get("dependencies", [])

    if not isinstance(args, list):
        raise ValueError(f"Task {task_id} args must be a list")
    if not isinstance(kwargs, dict):
        raise ValueError(f"Task {task_id} kwargs must be an object")
    if not isinstance(dependencies, list):
        raise ValueError(f"Task {task_id} dependencies must be a list")

    return Task(
        id=task_id,
        name=task_name,
        func=lambda *call_args, **call_kwargs: _run_builtin_action(
            action,
            *call_args,
            **call_kwargs,
        ),
        args=tuple(args),
        kwargs=kwargs,
        dependencies=[str(dep) for dep in dependencies],
        metadata={"action": action},
    )


def _run_builtin_action(action: str, *args: Any, **kwargs: Any) -> Any:
    if action == "noop":
        return None
    if action == "echo":
        if "value" in kwargs:
            return kwargs["value"]
        return args[0] if args else ""
    if action == "concat":
        separator = str(kwargs.get("separator", ""))
        return separator.join(str(arg) for arg in args)
    if action == "sum":
        return sum(float(arg) for arg in args)
    if action == "effort":
        from src.effort import classify

        task_description = str(kwargs.get("task_description") or (args[0] if args else ""))
        result = classify(task_description)
        return {
            "level": result.level.value,
            "confidence": result.confidence,
            "dispatch_phrase": result.dispatch_phrase,
            "verification_depth": result.verification_depth,
        }
    if action == "fail":
        raise RuntimeError(str(kwargs.get("message", args[0] if args else "Task failed")))
    raise ValueError(f"Unsupported workflow action: {action}")


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "name": task.name,
        "status": task.status.value,
        "result": task.result,
        "error": str(task.error) if task.error else None,
        "dependencies": task.dependencies,
        "metadata": task.metadata,
    }
