"""Workflow Recovery — 工作流错误恢复与动态节点注入

为 DAGWorkflow 和 ConditionalWorkflow 提供：
1. 错误恢复：自动重试（指数退避）、降级任务、回滚
2. 动态节点注入：运行时根据结果注入新任务
3. 事务性执行：支持部分回滚
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .interface import Task, TaskStatus


class RecoveryStrategy(Enum):
    """恢复策略"""

    RETRY = "retry"  # 重试（指数退避）
    FALLBACK = "fallback"  # 执行降级任务
    SKIP = "skip"  # 跳过并继续
    ABORT = "abort"  # 中止整个工作流
    ROLLBACK = "rollback"  # 回滚到检查点


@dataclass
class RecoveryConfig:
    """恢复配置"""

    max_retries: int = 3
    retry_delay_base: float = 1.0  # 基础延迟（秒）
    retry_backoff: float = 2.0  # 退避因子
    strategy: RecoveryStrategy = RecoveryStrategy.RETRY
    fallback_task: Task | None = None
    # 动态注入配置
    on_failure_inject: list[Task] = field(default_factory=list)
    on_success_inject: list[Task] = field(default_factory=list)


@dataclass
class Checkpoint:
    """工作流检查点"""

    checkpoint_id: str
    task_states: dict[str, TaskStatus]
    task_results: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class RecoverableTask:
    """可恢复的任务包装器

    包装一个 Task，添加重试、降级和动态注入能力。
    """

    def __init__(
        self,
        task: Task,
        recovery: RecoveryConfig | None = None,
    ):
        self.task = task
        self.recovery = recovery or RecoveryConfig()
        self.attempts = 0
        self.last_error: Exception | None = None

    def execute(self) -> Any:
        """执行任务，支持自动重试"""
        self.attempts = 0
        last_error = None

        for attempt in range(self.recovery.max_retries + 1):
            self.attempts = attempt + 1
            try:
                self.task.reset()
                result = self.task.run()
                return result
            except Exception as e:
                last_error = e
                self.last_error = e

                if attempt < self.recovery.max_retries:
                    delay = self.recovery.retry_delay_base * (self.recovery.retry_backoff**attempt)
                    time.sleep(delay)
                else:
                    # 所有重试耗尽
                    if self.recovery.strategy == RecoveryStrategy.FALLBACK:
                        return self._execute_fallback()
                    elif self.recovery.strategy == RecoveryStrategy.SKIP:
                        self.task.status = TaskStatus.SKIPPED
                        return None
                    elif self.recovery.strategy == RecoveryStrategy.ABORT:
                        raise
                    elif self.recovery.strategy == RecoveryStrategy.RETRY:
                        raise

        raise last_error  # type: ignore[misc]

    def _execute_fallback(self) -> Any:
        """执行降级任务"""
        if self.recovery.fallback_task is not None:
            try:
                self.recovery.fallback_task.reset()
                return self.recovery.fallback_task.run()
            except Exception:
                self.task.status = TaskStatus.FAILED
                raise
        self.task.status = TaskStatus.FAILED
        raise RuntimeError(f"Task {self.task.id} failed and no fallback configured")

    def get_dynamic_injections(self, success: bool) -> list[Task]:
        """获取需要动态注入的任务"""
        if success:
            return self.recovery.on_success_inject
        else:
            return self.recovery.on_failure_inject


class DynamicWorkflowManager:
    """动态工作流管理器

    支持运行时动态注入任务节点：
    - 根据任务执行结果注入新任务
    - 管理检查点用于回滚
    - 支持条件性任务注入
    """

    def __init__(self):
        self._dynamic_tasks: dict[str, Task] = {}
        self._injection_rules: list[InjectionRule] = []
        self._checkpoints: list[Checkpoint] = []
        self._completed_hooks: dict[str, list[Callable]] = {}

    def add_injection_rule(self, rule: InjectionRule) -> None:
        """添加动态注入规则"""
        self._injection_rules.append(rule)

    def register_completion_hook(
        self,
        task_id: str,
        hook: Callable[[Task], list[Task] | None],
    ) -> None:
        """注册任务完成后的钩子，返回要注入的新任务"""
        if task_id not in self._completed_hooks:
            self._completed_hooks[task_id] = []
        self._completed_hooks[task_id].append(hook)

    def on_task_completed(self, task: Task) -> list[Task]:
        """任务完成时调用，返回需要动态注入的新任务"""
        new_tasks: list[Task] = []

        # 调用注册的钩子
        for hook in self._completed_hooks.get(task.id, []):
            try:
                injected = hook(task)
                if injected:
                    for t in injected:
                        if t.id not in self._dynamic_tasks:
                            self._dynamic_tasks[t.id] = t
                            new_tasks.append(t)
            except Exception:
                pass

        # 检查注入规则
        for rule in self._injection_rules:
            if rule.matches(task):
                for t in rule.tasks_to_inject:
                    if t.id not in self._dynamic_tasks:
                        self._dynamic_tasks[t.id] = t
                        new_tasks.append(t)

        return new_tasks

    def create_checkpoint(self, tasks: dict[str, Task]) -> Checkpoint:
        """创建检查点"""
        cp = Checkpoint(
            checkpoint_id=f"cp_{len(self._checkpoints)}_{int(time.time())}",
            task_states={tid: t.status for tid, t in tasks.items()},
            task_results={tid: t.result for tid, t in tasks.items()},
        )
        self._checkpoints.append(cp)
        return cp

    def rollback_to_checkpoint(self, tasks: dict[str, Task]) -> bool:
        """回滚到最后一个检查点"""
        if not self._checkpoints:
            return False
        cp = self._checkpoints.pop()
        for tid, status in cp.task_states.items():
            if tid in tasks:
                tasks[tid].status = status
                if tid in cp.task_results:
                    tasks[tid].result = cp.task_results[tid]
        return True

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """获取最新检查点"""
        return self._checkpoints[-1] if self._checkpoints else None

    def clear(self) -> None:
        """清空所有动态任务和检查点"""
        self._dynamic_tasks.clear()
        self._injection_rules.clear()
        self._checkpoints.clear()
        self._completed_hooks.clear()


@dataclass
class InjectionRule:
    """动态注入规则

    当任务满足条件时，自动注入新任务到工作流中。
    """

    trigger_task_id: str
    condition: Callable[[Task], bool]
    tasks_to_inject: list[Task]
    description: str = ""

    def matches(self, task: Task) -> bool:
        """检查任务是否满足注入条件"""
        return task.id == self.trigger_task_id and self.condition(task)


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #


def make_recoverable(
    task: Task,
    max_retries: int = 3,
    strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
    fallback: Task | None = None,
    retry_delay: float = 1.0,
) -> RecoverableTask:
    """创建可恢复任务"""
    return RecoverableTask(
        task=task,
        recovery=RecoveryConfig(
            max_retries=max_retries,
            strategy=strategy,
            fallback_task=fallback,
            retry_delay_base=retry_delay,
        ),
    )


def create_fallback_task(
    task_id: str,
    name: str,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Task:
    """创建降级任务"""
    return Task(
        id=f"{task_id}_fallback",
        name=f"{name} (fallback)",
        func=func,
        args=args,
        kwargs=kwargs,
    )
