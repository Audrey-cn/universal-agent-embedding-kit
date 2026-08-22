"""条件分支工作流 — 基于条件判断的流程分支调度"""

from __future__ import annotations

import time
from typing import Any

from .conditional import ConditionalBranch
from .interface import Task, TaskStatus, Workflow, WorkflowResult

# 支持的条件运算符映射
_OPERATORS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _evaluate_condition(condition_config: dict[str, Any], context: dict[str, Any]) -> bool:
    """根据配置评估条件表达式"""
    field = str(condition_config.get("field", ""))
    operator = str(condition_config.get("operator", "=="))
    compare_value = condition_config.get("value")

    if operator not in _OPERATORS:
        raise ValueError(f"Unsupported condition operator: {operator}")

    actual_value = context.get(field)
    return bool(_OPERATORS[operator](actual_value, compare_value))


class ConditionalWorkflow(Workflow):
    """条件分支工作流 — 根据上下文条件决定执行哪些任务

    配置格式（YAML）：
        type: conditional
        context:
          mode: production
        conditions:
          - name: check_mode
            field: mode
            operator: "=="
            value: production
            true_tasks:
              - id: prod_task
                name: Production Task
                action: echo
                args: ["running in production"]
            false_tasks:
              - id: staging_task
                name: Staging Task
                action: echo
                args: ["running in staging"]
    """

    def __init__(
        self,
        workflow_id: str,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(workflow_id)
        self.context = context or {}
        self.branch = ConditionalBranch(workflow_id)

    def add_condition(
        self,
        name: str,
        condition_config: dict[str, Any],
        true_task: Task,
        false_task: Task | None = None,
    ) -> None:
        """添加一个条件分支"""
        self.branch.add_branch(
            name=name,
            condition=lambda ctx, cfg=condition_config: _evaluate_condition(cfg, ctx),
            true_task=true_task,
            false_task=false_task,
        )

    def execute(self) -> WorkflowResult:
        """执行条件分支工作流"""
        start_time = time.time()
        errors: list[Exception] = []
        all_tasks: list[Task] = []

        # 评估所有条件分支，收集需要执行的任务
        tasks_to_run = self.branch.evaluate(self.context)
        # 同时收集所有分支中的任务（包括未执行的），用于报告
        for bc in self.branch.branches:
            if bc.true_task not in all_tasks:
                all_tasks.append(bc.true_task)
            if bc.false_task and bc.false_task not in all_tasks:
                all_tasks.append(bc.false_task)

        # 执行通过条件评估的任务
        for task in tasks_to_run:
            try:
                task.run()
            except Exception as e:
                errors.append(e)

        # 标记未执行的分支任务为跳过
        executed_ids = {t.id for t in tasks_to_run}
        for task in all_tasks:
            if task.id not in executed_ids and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED

        duration = time.time() - start_time
        success = all(t.status == TaskStatus.COMPLETED for t in tasks_to_run) and not errors

        return WorkflowResult(
            workflow_id=self.workflow_id,
            tasks=all_tasks,
            success=success,
            duration=duration,
            errors=errors,
        )
