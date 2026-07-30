"""Workflow runtime helpers for product entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .conditional_workflow import ConditionalWorkflow
from .dag_workflow import DAGWorkflow
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


def execute_workflow_config(
    config: dict[str, Any],
    allowed_actions: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Build and execute a workflow config, returning a serializable result."""
    workflow = build_workflow(config, allowed_actions=allowed_actions)
    result = workflow.execute()
    return serialize_workflow_result(result)


def build_workflow(
    config: dict[str, Any],
    allowed_actions: list[str] | tuple[str, ...] | set[str] | None = None,
) -> Workflow:
    """Build a Workflow from a serializable config."""
    workflow_id = str(config.get("id") or config.get("workflow_id") or "workflow")
    workflow_type = str(config.get("type", "sequential"))
    allowed = set(allowed_actions) if allowed_actions is not None else _default_safe_actions()

    # ---- 条件分支工作流（特殊处理：任务在分支内部，不通过 flat tasks 列表） ----
    if workflow_type == "conditional":
        return _build_conditional_workflow(workflow_id, config, allowed)

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
    elif workflow_type == "dag":
        # 旧DAG工作流：基于拓扑排序调度，支持串行/并行两种模式
        workflow = DAGWorkflow(
            workflow_id,
            max_workers=int(config.get("max_workers", 1)),
            fail_fast=bool(config.get("fail_fast", True)),
        )
    else:
        raise ValueError(f"Unsupported workflow type: {workflow_type}")

    for index, task_data in enumerate(tasks_data):
        if not isinstance(task_data, dict):
            raise ValueError(f"Workflow task at index {index} must be an object")
        task = _task_from_config(task_data, allowed)
        workflow.add_task(task)

    return workflow


def _build_conditional_workflow(
    workflow_id: str,
    config: dict[str, Any],
    allowed: set[str],
) -> ConditionalWorkflow:
    """构建条件分支工作流"""
    context = config.get("context", {})
    if not isinstance(context, dict):
        raise ValueError("Conditional workflow 'context' must be an object")
    workflow = ConditionalWorkflow(workflow_id, context=context)

    conditions_data = config.get("conditions", [])
    if not isinstance(conditions_data, list):
        raise ValueError("Conditional workflow 'conditions' must be a list")

    for cond_data in conditions_data:
        if not isinstance(cond_data, dict):
            raise ValueError("Each condition must be an object")
        cond_name = str(cond_data.get("name", "condition"))

        # 构建 true 分支任务
        true_tasks_data = cond_data.get("true_tasks", [])
        if not isinstance(true_tasks_data, list) or len(true_tasks_data) == 0:
            raise ValueError(f"Condition '{cond_name}' must have at least one true_task")
        true_task = _task_from_config(true_tasks_data[0], allowed)

        # 构建 false 分支任务（可选）
        false_tasks_data = cond_data.get("false_tasks", [])
        false_task = None
        if false_tasks_data:
            if not isinstance(false_tasks_data, list):
                raise ValueError(f"Condition '{cond_name}' false_tasks must be a list")
            false_task = _task_from_config(false_tasks_data[0], allowed)

        workflow.add_condition(cond_name, cond_data, true_task, false_task)

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


def _task_from_config(task_data: dict[str, Any], allowed_actions: set[str]) -> Task:
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
    if action not in allowed_actions:
        allowed = ", ".join(sorted(allowed_actions))
        raise ValueError(f"Workflow action '{action}' is not allowed (allowed: {allowed})")

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


def _default_safe_actions() -> set[str]:
    from src.config import load_config

    return set(load_config().workflow.safe_actions)


def _run_builtin_action(action: str, *args: Any, **kwargs: Any) -> Any:
    if action in _ACTION_REGISTRY:
        return _ACTION_REGISTRY[action](*args, **kwargs)
    raise ValueError(f"Unsupported workflow action: {action}")


# ---- Public action registry ----

_ACTION_REGISTRY: dict[str, Any] = {}


def register_action(name: str, func: Any) -> None:
    """Register a custom workflow action callable.

    Args:
        name: Action name used in ``func_name`` when adding tasks.
        func: Callable invoked with ``(args, kwargs)`` from the task config.
    """
    _ACTION_REGISTRY[name] = func


def list_actions() -> list[str]:
    """Return the names of all registered actions."""
    return list(_ACTION_REGISTRY.keys())


# ---- Built-in actions (auto-registered) ----

def _action_noop(*_args: Any, **_kwargs: Any) -> None:
    return None


def _action_echo(*args: Any, **kwargs: Any) -> str:
    if "value" in kwargs:
        return str(kwargs["value"])
    return str(args[0]) if args else ""


def _action_concat(*args: Any, **kwargs: Any) -> str:
    separator = str(kwargs.get("separator", ""))
    return separator.join(str(arg) for arg in args)


def _action_sum(*args: Any, **kwargs: Any) -> float:
    return sum(float(arg) for arg in args)


def _action_effort(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.effort import classify
    task_description = str(kwargs.get("task_description") or (args[0] if args else ""))
    result = classify(task_description)
    return {
        "level": result.level.value,
        "confidence": result.confidence,
        "dispatch_phrase": result.dispatch_phrase,
        "verification_depth": result.verification_depth,
    }


def _action_fail(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError(str(kwargs.get("message", args[0] if args else "Task failed")))


def _action_verify(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path") or (args[0] if args else ".")))
    result = run_verify(artifact_path)
    return {
        "passed": result.passed,
        "verdict": result.verdict,
        "evidence": result.evidence,
        "verification_type": (
            str(result.verification_type.value) if result.verification_type else ""
        ),
    }


def _action_memory_add(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.memory import MemoryService
    svc = MemoryService()
    entry = svc.add(
        content=kwargs.get("content", args[0] if args else ""),
        layer=kwargs.get("layer", "l1"),
        importance=float(kwargs.get("importance", 0.5)),
        tags=kwargs.get("tags", []),
    )
    svc.persist()
    return entry


def _action_memory_query(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.memory import MemoryService
    svc = MemoryService()
    return svc.query(
        query=kwargs.get("query", args[0] if args else ""),
        layer=kwargs.get("layer"),
        tags=kwargs.get("tags", []),
        limit=int(kwargs.get("limit", 10)),
    )


def _action_verify_lint(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import VerificationType
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path", args[0] if args else ".")))
    result = run_verify(artifact_path, verification_type=VerificationType.LINT)
    return {"passed": result.passed, "verdict": result.verdict, "evidence": result.evidence[:500]}


def _action_verify_test(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import VerificationType
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path", args[0] if args else ".")))
    result = run_verify(artifact_path, verification_type=VerificationType.TEST)
    return {"passed": result.passed, "verdict": result.verdict, "evidence": result.evidence[:500]}


def _action_verify_render(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import VerificationType
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path", args[0] if args else ".")))
    criteria_path = kwargs.get("criteria_path")
    if criteria_path:
        criteria_path = Path(str(criteria_path))
    result = run_verify(
        artifact_path, criteria_path=criteria_path, verification_type=VerificationType.RENDER
    )
    return {"passed": result.passed, "verdict": result.verdict, "evidence": result.evidence[:500]}


def _action_verify_diff(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import VerificationType
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path", args[0] if args else ".")))
    criteria_path = kwargs.get("criteria_path")
    if criteria_path:
        criteria_path = Path(str(criteria_path))
    result = run_verify(
        artifact_path, criteria_path=criteria_path, verification_type=VerificationType.DIFF
    )
    return {"passed": result.passed, "verdict": result.verdict, "evidence": result.evidence[:500]}


def _action_verify_multi_perspective(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.verify.interface import VerificationType
    from src.verify.interface import verify as run_verify
    artifact_path = Path(str(kwargs.get("artifact_path", args[0] if args else ".")))
    criteria_path = kwargs.get("criteria_path")
    if criteria_path:
        criteria_path = Path(str(criteria_path))
    result = run_verify(
        artifact_path,
        criteria_path=criteria_path,
        verification_type=VerificationType.MULTI_PERSPECTIVE,
    )
    return {"passed": result.passed, "verdict": result.verdict, "evidence": result.evidence[:500],
            "notes": result.notes}


def _action_effort_cached(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from src.effort import classify_with_cache
    task_description = str(kwargs.get("task_description") or (args[0] if args else ""))
    result = classify_with_cache(task_description)
    return {
        "level": result.level.value,
        "confidence": result.confidence,
        "dispatch_phrase": result.dispatch_phrase,
        "verification_depth": result.verification_depth,
    }


# Auto-register built-in actions
_BUILTINS = {
    "noop": _action_noop,
    "echo": _action_echo,
    "concat": _action_concat,
    "sum": _action_sum,
    "effort": _action_effort,
    "effort_cached": _action_effort_cached,
    "fail": _action_fail,
    "verify": _action_verify,
    "memory_add": _action_memory_add,
    "memory_query": _action_memory_query,
    "verify_lint": _action_verify_lint,
    "verify_test": _action_verify_test,
    "verify_render": _action_verify_render,
    "verify_diff": _action_verify_diff,
    "verify_multi_perspective": _action_verify_multi_perspective,
}
_ACTION_REGISTRY.update(_BUILTINS)


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
