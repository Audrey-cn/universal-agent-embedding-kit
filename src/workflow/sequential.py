"""Sequential Scheduler — 顺序调度器"""

from __future__ import annotations

import time

from .dag import DAG
from .interface import Task, TaskStatus, Workflow, WorkflowResult


class SequentialScheduler(Workflow):
    """顺序调度器"""

    def __init__(self, workflow_id: str, fail_fast: bool = True):
        super().__init__(workflow_id)
        self.fail_fast = fail_fast
        self.dag = DAG()

    def add_task(self, task: Task) -> None:
        """添加任务到 DAG"""
        super().add_task(task)
        self.dag.add_node(task)
        for dep_id in task.dependencies:
            if dep_id not in self.dag.nodes:
                raise KeyError(f"Dependency {dep_id} not found")
            self.dag.add_edge(dep_id, task.id)

    def execute(self) -> WorkflowResult:
        """顺序执行工作流"""
        start_time = time.time()
        errors = []

        try:
            self.dag.validate()
        except Exception as e:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                tasks=list(self.tasks.values()),
                success=False,
                duration=time.time() - start_time,
                errors=[e],
            )

        # 按拓扑顺序执行
        order = self.dag.topological_sort()

        for task_id in order:
            task = self.tasks[task_id]

            # 如果任务已经被标记为跳过，跳过
            if task.status == TaskStatus.SKIPPED:
                continue

            # 检查依赖是否都成功完成
            deps = self.dag.get_dependencies(task_id)
            if any(self.tasks[dep_id].status == TaskStatus.FAILED for dep_id in deps):
                task.status = TaskStatus.SKIPPED
                continue

            try:
                task.run()
            except Exception as e:
                errors.append(e)
                if self.fail_fast:
                    # 跳过所有后续任务
                    for remaining_id in order[order.index(task_id) + 1 :]:
                        if self.tasks[remaining_id].status == TaskStatus.PENDING:
                            self.tasks[remaining_id].status = TaskStatus.SKIPPED
                    break

        duration = time.time() - start_time
        success = all(t.status == TaskStatus.COMPLETED for t in self.tasks.values())

        return WorkflowResult(
            workflow_id=self.workflow_id,
            tasks=list(self.tasks.values()),
            success=success,
            duration=duration,
            errors=errors,
        )
