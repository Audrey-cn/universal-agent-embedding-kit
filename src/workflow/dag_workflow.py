"""DAG工作流调度器 — 基于有向无环图的拓扑调度"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .dag import DAG
from .interface import Task, TaskStatus, Workflow, WorkflowResult


class DAGWorkflow(Workflow):
    """DAG工作流 — 基于有向无环图的任务调度器

    支持两种执行模式：
    - max_workers=1：按拓扑顺序串行执行（默认）
    - max_workers>1：并行执行互不依赖的节点
    """

    def __init__(
        self,
        workflow_id: str,
        max_workers: int = 1,
        fail_fast: bool = True,
    ):
        super().__init__(workflow_id)
        self.max_workers = max_workers
        self.fail_fast = fail_fast
        self.dag = DAG()

    def add_task(self, task: Task) -> None:
        """添加任务到 DAG"""
        super().add_task(task)
        self.dag.add_node(task)
        for dep_id in task.dependencies:
            if dep_id not in self.dag.nodes:
                raise KeyError(f"Dependency {dep_id} not found for task {task.id}")
            self.dag.add_edge(dep_id, task.id)

    def _mark_dependents_as_skipped(self, failed_task_id: str) -> None:
        """标记依赖失败任务的所有下游任务为跳过"""
        dependents = self.dag.get_dependents(failed_task_id)
        for dep_id in dependents:
            task = self.tasks[dep_id]
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
                self._mark_dependents_as_skipped(dep_id)

    def execute(self) -> WorkflowResult:
        """执行 DAG 工作流"""
        start_time = time.time()
        errors: list[Exception] = []

        # 验证 DAG 无循环
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

        if self.max_workers > 1:
            return self._execute_parallel(start_time, errors)
        else:
            return self._execute_sequential(start_time, errors)

    def _execute_sequential(self, start_time: float, errors: list[Exception]) -> WorkflowResult:
        """按拓扑顺序串行执行"""
        order = self.dag.topological_sort()

        for task_id in order:
            task = self.tasks[task_id]

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

    def _execute_parallel(self, start_time: float, errors: list[Exception]) -> WorkflowResult:
        """并行执行互不依赖的节点"""
        completed: set[str] = set()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                ready = self.dag.get_ready_nodes(completed) - completed
                ready = {t_id for t_id in ready if self.tasks[t_id].status in {TaskStatus.PENDING}}

                if not ready:
                    all_done = all(
                        t.status
                        in {
                            TaskStatus.COMPLETED,
                            TaskStatus.FAILED,
                            TaskStatus.SKIPPED,
                            TaskStatus.BLOCKED,
                        }
                        for t in self.tasks.values()
                    )
                    if all_done:
                        break

                    failed = {t.id for t in self.tasks.values() if t.status == TaskStatus.FAILED}
                    for failed_id in failed:
                        self._mark_dependents_as_skipped(failed_id)

                    all_done = all(
                        t.status
                        in {
                            TaskStatus.COMPLETED,
                            TaskStatus.FAILED,
                            TaskStatus.SKIPPED,
                            TaskStatus.BLOCKED,
                        }
                        for t in self.tasks.values()
                    )
                    if all_done:
                        break
                    if not ready:
                        break

                futures = {}
                for task_id in ready:
                    task = self.tasks[task_id]
                    deps = self.dag.get_dependencies(task_id)
                    if any(self.tasks[dep_id].status == TaskStatus.FAILED for dep_id in deps):
                        task.status = TaskStatus.SKIPPED
                        completed.add(task_id)
                        continue

                    future = executor.submit(task.run)
                    futures[future] = task_id

                for future in as_completed(futures):
                    task_id = futures[future]
                    try:
                        future.result()
                        completed.add(task_id)
                    except Exception as e:
                        errors.append(e)
                        self._mark_dependents_as_skipped(task_id)
                        if self.fail_fast:
                            for f in futures:
                                f.cancel()
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
