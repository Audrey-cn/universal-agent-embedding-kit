"""Workflow Interface — 工作流接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class Task:
    """工作流任务"""

    id: str
    name: str
    func: Callable[..., Any]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Exception | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            raise ValueError("Task id cannot be empty")
        if not self.name:
            raise ValueError("Task name cannot be empty")

    def run(self) -> Any:
        """执行任务"""
        self.status = TaskStatus.RUNNING
        try:
            self.result = self.func(*self.args, **self.kwargs)
            self.status = TaskStatus.COMPLETED
            return self.result
        except Exception as e:
            self.error = e
            self.status = TaskStatus.FAILED
            raise

    def reset(self):
        """重置任务状态"""
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None


@dataclass
class WorkflowResult:
    """工作流执行结果"""

    workflow_id: str
    tasks: list[Task]
    success: bool
    duration: float  # 秒
    errors: list[Exception] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def completed_tasks(self) -> list[Task]:
        """已完成的任务"""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    @property
    def failed_tasks(self) -> list[Task]:
        """失败的任务"""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    @property
    def skipped_tasks(self) -> list[Task]:
        """跳过的任务"""
        return [t for t in self.tasks if t.status == TaskStatus.SKIPPED]

    def __str__(self) -> str:
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        return (
            f"{status} [{self.workflow_id}] "
            f"Completed: {len(self.completed_tasks)}, "
            f"Failed: {len(self.failed_tasks)}, "
            f"Duration: {self.duration:.2f}s"
        )


class Workflow(ABC):
    """工作流基类"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.tasks: dict[str, Task] = {}

    def add_task(self, task: Task) -> None:
        """添加任务"""
        if task.id in self.tasks:
            raise ValueError(f"Task {task.id} already exists")
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Task:
        """获取任务"""
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")
        return self.tasks[task_id]

    def get_dependencies(self, task_id: str) -> list[Task]:
        """获取任务的依赖"""
        task = self.get_task(task_id)
        return [self.tasks[dep_id] for dep_id in task.dependencies]

    def get_dependents(self, task_id: str) -> list[Task]:
        """获取依赖此任务的任务"""
        return [t for t in self.tasks.values() if task_id in t.dependencies]

    @abstractmethod
    def execute(self) -> WorkflowResult:
        """执行工作流"""
        ...

    def reset(self):
        """重置所有任务状态"""
        for task in self.tasks.values():
            task.reset()
