"""Conditional Branch — 条件分支"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .interface import Task, TaskStatus


@dataclass
class BranchCondition:
    """分支条件"""

    name: str
    condition: Callable[..., bool]
    true_task: Task
    false_task: Task | None = None


class ConditionalBranch:
    """条件分支"""

    def __init__(self, name: str):
        self.name = name
        self.branches: list[BranchCondition] = []

    def add_branch(
        self,
        name: str,
        condition: Callable[..., bool],
        true_task: Task,
        false_task: Task | None = None,
    ) -> None:
        """添加分支条件"""
        self.branches.append(
            BranchCondition(
                name=name,
                condition=condition,
                true_task=true_task,
                false_task=false_task,
            )
        )

    def evaluate(self, context: dict[str, Any]) -> list[Task]:
        """评估条件并返回要执行的任务"""
        tasks_to_run = []

        for branch in self.branches:
            try:
                result = branch.condition(context)
                if result:
                    tasks_to_run.append(branch.true_task)
                elif branch.false_task:
                    tasks_to_run.append(branch.false_task)
            except Exception:
                # 条件评估失败，跳过此分支
                branch.true_task.status = TaskStatus.SKIPPED
                if branch.false_task:
                    branch.false_task.status = TaskStatus.SKIPPED

        return tasks_to_run

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """执行条件分支"""
        tasks_to_run = self.evaluate(context)
        results = {}

        for task in tasks_to_run:
            try:
                result = task.run()
                results[task.id] = result
            except Exception as e:
                results[task.id] = e

        return results
