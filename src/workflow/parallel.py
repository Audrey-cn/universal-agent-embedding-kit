"""Parallel Scheduler — 并行调度器"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .dag import DAG
from .interface import Task, TaskStatus, Workflow, WorkflowResult


class ParallelScheduler(Workflow):
    """并行调度器"""

    def __init__(
        self,
        workflow_id: str,
        max_workers: int = 4,
        fail_fast: bool = False,
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
                raise KeyError(f"Dependency {dep_id} not found")
            self.dag.add_edge(dep_id, task.id)

    def _mark_dependents_as_skipped(self, failed_task_id: str) -> None:
        """标记依赖失败任务的任务为跳过"""
        dependents = self.dag.get_dependents(failed_task_id)
        for dep_id in dependents:
            task = self.tasks[dep_id]
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
                # 递归标记依赖此任务的任务
                self._mark_dependents_as_skipped(dep_id)

    def execute(self) -> WorkflowResult:
        """并行执行工作流"""
        start_time = time.time()
        errors = []
        completed: set[str] = set()

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

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                # 获取可以执行的任务
                ready = self.dag.get_ready_nodes(completed) - completed

                # 过滤掉已经失败、跳过或阻塞的任务
                ready = {t_id for t_id in ready if self.tasks[t_id].status in {TaskStatus.PENDING}}

                if not ready:
                    # 检查是否所有任务都已完成、失败或跳过
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

                    # 检查是否有失败的任务导致阻塞
                    failed = {t.id for t in self.tasks.values() if t.status == TaskStatus.FAILED}
                    for failed_id in failed:
                        self._mark_dependents_as_skipped(failed_id)

                    # 再次检查
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

                    # 如果没有可执行的任务且没有全部完成，可能是死锁
                    if not ready:
                        break

                # 提交任务
                futures = {}
                for task_id in ready:
                    task = self.tasks[task_id]
                    # 检查依赖是否都成功完成
                    deps = self.dag.get_dependencies(task_id)
                    if any(self.tasks[dep_id].status == TaskStatus.FAILED for dep_id in deps):
                        task.status = TaskStatus.SKIPPED
                        completed.add(task_id)
                        continue

                    future = executor.submit(task.run)
                    futures[future] = task_id

                # 等待完成
                for future in as_completed(futures):
                    task_id = futures[future]
                    try:
                        future.result()
                        completed.add(task_id)
                    except Exception as e:
                        errors.append(e)
                        # 标记依赖此失败任务的任务为跳过
                        self._mark_dependents_as_skipped(task_id)
                        if self.fail_fast:
                            # 取消所有未完成的任务
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
