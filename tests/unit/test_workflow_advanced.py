from __future__ import annotations

from src.workflow.dag_workflow import DAGWorkflow
from src.workflow.interface import Task, TaskStatus
from src.workflow.recovery import (
    DynamicWorkflowManager,
    InjectionRule,
    RecoverableTask,
    RecoveryConfig,
    RecoveryStrategy,
    create_fallback_task,
)
from src.workflow.runtime import execute_workflow_config


def test_dag_workflow_obeys_dependencies_and_skips_failed_descendants() -> None:
    events: list[str] = []
    workflow = DAGWorkflow("dag", fail_fast=False)
    workflow.add_task(Task("first", "first", lambda: events.append("first")))
    workflow.add_task(
        Task(
            "fail",
            "fail",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            dependencies=["first"],
        )
    )
    workflow.add_task(
        Task(
            "blocked",
            "blocked",
            lambda: events.append("blocked"),
            dependencies=["fail"],
        )
    )
    workflow.add_task(Task("independent", "independent", lambda: events.append("independent")))

    result = workflow.execute()

    assert result.success is False
    assert set(events) == {"first", "independent"}
    assert workflow.get_task("fail").status is TaskStatus.FAILED
    assert workflow.get_task("blocked").status is TaskStatus.SKIPPED


def test_runtime_conditional_executes_exactly_one_branch() -> None:
    config = {
        "id": "conditional",
        "type": "conditional",
        "context": {"environment": "production"},
        "conditions": [
            {
                "name": "environment",
                "field": "environment",
                "operator": "==",
                "value": "production",
                "true_tasks": [{"id": "prod", "action": "echo", "args": ["prod"]}],
                "false_tasks": [{"id": "dev", "action": "echo", "args": ["dev"]}],
            }
        ],
    }

    result = execute_workflow_config(config, allowed_actions={"echo"})

    assert result["success"] is True
    assert result["task_results"] == {"prod": "prod", "dev": None}
    assert [task["id"] for task in result["completed_tasks"]] == ["prod"]
    assert [task["id"] for task in result["skipped_tasks"]] == ["dev"]


def test_recoverable_task_retries_then_succeeds_without_sleep() -> None:
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("retry")
        return "ok"

    recoverable = RecoverableTask(
        Task("flaky", "flaky", flaky),
        RecoveryConfig(max_retries=2, retry_delay_base=0),
    )

    assert recoverable.execute() == "ok"
    assert recoverable.attempts == 3
    assert recoverable.task.status is TaskStatus.COMPLETED


def test_recoverable_task_uses_fallback_and_skip_strategies() -> None:
    def failing() -> None:
        raise RuntimeError("fail")

    fallback = create_fallback_task("primary", "fallback", lambda: "safe")
    with_fallback = RecoverableTask(
        Task("primary", "primary", failing),
        RecoveryConfig(
            max_retries=0,
            retry_delay_base=0,
            strategy=RecoveryStrategy.FALLBACK,
            fallback_task=fallback,
        ),
    )
    skipped = RecoverableTask(
        Task("optional", "optional", failing),
        RecoveryConfig(max_retries=0, strategy=RecoveryStrategy.SKIP),
    )

    assert with_fallback.execute() == "safe"
    assert fallback.status is TaskStatus.COMPLETED
    assert skipped.execute() is None
    assert skipped.task.status is TaskStatus.SKIPPED


def test_dynamic_manager_deduplicates_injections_and_restores_checkpoint() -> None:
    manager = DynamicWorkflowManager()
    trigger = Task("build", "build", lambda: "artifact")
    injected = Task("verify", "verify", lambda: True)
    manager.add_injection_rule(
        InjectionRule("build", lambda task: task.result == "artifact", [injected])
    )
    manager.register_completion_hook("build", lambda _task: [injected])
    trigger.run()

    assert manager.on_task_completed(trigger) == [injected]
    assert manager.on_task_completed(trigger) == []
    checkpoint = manager.create_checkpoint({"build": trigger})
    trigger.reset()
    assert manager.get_latest_checkpoint() is checkpoint
    assert manager.rollback_to_checkpoint({"build": trigger}) is True
    assert trigger.status is TaskStatus.COMPLETED
    assert trigger.result == "artifact"
    assert manager.rollback_to_checkpoint({"build": trigger}) is False
