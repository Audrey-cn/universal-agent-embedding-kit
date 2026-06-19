"""Tests for workflow engine"""

import time

import pytest

from src.workflow import (
    DAG,
    ConditionalBranch,
    ParallelScheduler,
    SequentialScheduler,
    Task,
    TaskStatus,
    WorkflowResult,
)
from src.workflow.dag import CycleError


# 测试辅助函数
def dummy_task(x: int) -> int:
    """简单任务：返回输入值"""
    return x


def slow_task(x: int, delay: float = 0.1) -> int:
    """慢任务：延迟后返回输入值"""
    time.sleep(delay)
    return x


def failing_task() -> None:
    """失败任务：抛出异常"""
    raise ValueError("Task failed")


def add_task(a: int, b: int) -> int:
    """加法任务"""
    return a + b


class TestTask:
    """测试 Task"""

    def test_task_creation(self):
        """测试任务创建"""
        task = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        assert task.id == "t1"
        assert task.name == "Task 1"
        assert task.status == TaskStatus.PENDING

    def test_task_run(self):
        """测试任务执行"""
        task = Task(id="t1", name="Task 1", func=dummy_task, args=(42,))
        result = task.run()
        assert result == 42
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 42

    def test_task_run_failure(self):
        """测试任务执行失败"""
        task = Task(id="t1", name="Task 1", func=failing_task)
        with pytest.raises(ValueError, match="Task failed"):
            task.run()
        assert task.status == TaskStatus.FAILED
        assert isinstance(task.error, ValueError)

    def test_task_reset(self):
        """测试任务重置"""
        task = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        task.run()
        assert task.status == TaskStatus.COMPLETED

        task.reset()
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None

    def test_task_invalid_id(self):
        """测试无效任务 ID"""
        with pytest.raises(ValueError, match="Task id cannot be empty"):
            Task(id="", name="Task 1", func=dummy_task)

    def test_task_invalid_name(self):
        """测试无效任务名称"""
        with pytest.raises(ValueError, match="Task name cannot be empty"):
            Task(id="t1", name="", func=dummy_task)


class TestDAG:
    """测试 DAG"""

    def test_dag_creation(self):
        """测试 DAG 创建"""
        dag = DAG()
        assert len(dag) == 0

    def test_dag_add_node(self):
        """测试添加节点"""
        dag = DAG()
        task = Task(id="t1", name="Task 1", func=dummy_task)
        dag.add_node(task)
        assert "t1" in dag
        assert len(dag) == 1

    def test_dag_add_edge(self):
        """测试添加边"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")

        assert "t2" in dag.get_dependents("t1")
        assert "t1" in dag.get_dependencies("t2")

    def test_dag_no_cycle(self):
        """测试无循环依赖"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        t3 = Task(id="t3", name="Task 3", func=dummy_task, dependencies=["t2"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_node(t3)
        dag.add_edge("t1", "t2")
        dag.add_edge("t2", "t3")

        assert dag.has_cycle() is False

    def test_dag_with_cycle(self):
        """测试有循环依赖"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task)
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")
        dag.add_edge("t2", "t1")

        assert dag.has_cycle() is True

    def test_dag_validate_no_cycle(self):
        """测试验证无循环"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task)
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")

        dag.validate()  # 不应该抛出异常

    def test_dag_validate_with_cycle(self):
        """测试验证有循环"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task)
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")
        dag.add_edge("t2", "t1")

        with pytest.raises(CycleError):
            dag.validate()

    def test_dag_topological_sort(self):
        """测试拓扑排序"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        t3 = Task(id="t3", name="Task 3", func=dummy_task, dependencies=["t2"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_node(t3)
        dag.add_edge("t1", "t2")
        dag.add_edge("t2", "t3")

        order = dag.topological_sort()
        assert order.index("t1") < order.index("t2")
        assert order.index("t2") < order.index("t3")

    def test_dag_root_nodes(self):
        """测试获取根节点"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")

        assert dag.get_root_nodes() == {"t1"}

    def test_dag_leaf_nodes(self):
        """测试获取叶子节点"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_edge("t1", "t2")

        assert dag.get_leaf_nodes() == {"t2"}

    def test_dag_get_ready_nodes(self):
        """测试获取可执行节点"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, dependencies=["t1"])
        t3 = Task(id="t3", name="Task 3", func=dummy_task, dependencies=["t1"])
        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_node(t3)
        dag.add_edge("t1", "t2")
        dag.add_edge("t1", "t3")

        # 初始状态：只有 t1 可以执行
        assert dag.get_ready_nodes(set()) == {"t1"}

        # t1 完成后：t2 和 t3 可以执行
        assert dag.get_ready_nodes({"t1"}) == {"t2", "t3"}

    def test_dag_duplicate_node(self):
        """测试重复节点"""
        dag = DAG()
        t1 = Task(id="t1", name="Task 1", func=dummy_task)
        dag.add_node(t1)

        with pytest.raises(ValueError, match="Node t1 already exists"):
            dag.add_node(t1)

    def test_dag_missing_node(self):
        """测试缺失节点"""
        dag = DAG()
        with pytest.raises(KeyError, match="Node t1 not found"):
            dag.get_dependencies("t1")


class TestSequentialScheduler:
    """测试 SequentialScheduler"""

    def test_sequential_execution(self):
        """测试顺序执行"""
        workflow = SequentialScheduler("test-workflow")
        t1 = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(2,))
        t3 = Task(id="t3", name="Task 3", func=dummy_task, args=(3,))

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3)

        result = workflow.execute()
        assert result.success is True
        assert len(result.completed_tasks) == 3
        assert len(result.failed_tasks) == 0

    def test_sequential_with_dependencies(self):
        """测试带依赖的顺序执行"""
        workflow = SequentialScheduler("test-workflow")
        t1 = Task(id="t1", name="Task 1", func=add_task, args=(1, 2))
        t2 = Task(id="t2", name="Task 2", func=add_task, args=(3, 4), dependencies=["t1"])

        workflow.add_task(t1)
        workflow.add_task(t2)

        result = workflow.execute()
        assert result.success is True
        assert t1.result == 3
        assert t2.result == 7

    def test_sequential_fail_fast(self):
        """测试快速失败"""
        workflow = SequentialScheduler("test-workflow", fail_fast=True)
        t1 = Task(id="t1", name="Task 1", func=failing_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(1,), dependencies=["t1"])

        workflow.add_task(t1)
        workflow.add_task(t2)

        result = workflow.execute()
        assert result.success is False
        assert t1.status == TaskStatus.FAILED
        assert t2.status == TaskStatus.SKIPPED

    def test_sequential_no_fail_fast(self):
        """测试不快速失败"""
        workflow = SequentialScheduler("test-workflow", fail_fast=False)
        t1 = Task(id="t1", name="Task 1", func=failing_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(1,))

        workflow.add_task(t1)
        workflow.add_task(t2)

        result = workflow.execute()
        assert result.success is False
        assert t1.status == TaskStatus.FAILED
        assert t2.status == TaskStatus.COMPLETED

    def test_sequential_cycle_detection(self):
        """测试循环依赖检测"""
        workflow = SequentialScheduler("test-workflow")
        t1 = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(2,))

        workflow.add_task(t1)
        workflow.add_task(t2)

        # 手动添加循环边
        workflow.dag.add_edge("t1", "t2")
        workflow.dag.add_edge("t2", "t1")

        result = workflow.execute()
        assert result.success is False
        assert len(result.errors) > 0


class TestParallelScheduler:
    """测试 ParallelScheduler"""

    def test_parallel_execution(self):
        """测试并行执行"""
        workflow = ParallelScheduler("test-workflow", max_workers=2)
        t1 = Task(id="t1", name="Task 1", func=slow_task, args=(1,), kwargs={"delay": 0.1})
        t2 = Task(id="t2", name="Task 2", func=slow_task, args=(2,), kwargs={"delay": 0.1})
        t3 = Task(id="t3", name="Task 3", func=slow_task, args=(3,), kwargs={"delay": 0.1})

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3)

        result = workflow.execute()
        assert result.success is True
        assert len(result.completed_tasks) == 3

    def test_parallel_with_dependencies(self):
        """测试带依赖的并行执行"""
        workflow = ParallelScheduler("test-workflow", max_workers=2)
        t1 = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(2,), dependencies=["t1"])
        t3 = Task(id="t3", name="Task 3", func=dummy_task, args=(3,), dependencies=["t1"])

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3)

        result = workflow.execute()
        assert result.success is True
        assert len(result.completed_tasks) == 3

    def test_parallel_skip_on_dependency_failure(self):
        """测试依赖失败时跳过"""
        workflow = ParallelScheduler("test-workflow", max_workers=2)
        t1 = Task(id="t1", name="Task 1", func=failing_task)
        t2 = Task(id="t2", name="Task 2", func=dummy_task, args=(1,), dependencies=["t1"])

        workflow.add_task(t1)
        workflow.add_task(t2)

        result = workflow.execute()
        assert result.success is False
        assert t1.status == TaskStatus.FAILED
        # t2 应该被跳过，因为它依赖于失败的 t1
        assert t2.status in [TaskStatus.SKIPPED, TaskStatus.BLOCKED]


class TestConditionalBranch:
    """测试 ConditionalBranch"""

    def test_conditional_true_branch(self):
        """测试条件为真的分支"""
        branch = ConditionalBranch("test-branch")
        true_task = Task(id="true", name="True Task", func=dummy_task, args=(1,))
        false_task = Task(id="false", name="False Task", func=dummy_task, args=(0,))

        branch.add_branch(
            name="test",
            condition=lambda ctx: ctx.get("value", 0) > 0,
            true_task=true_task,
            false_task=false_task,
        )

        results = branch.execute({"value": 1})
        assert "true" in results
        assert true_task.status == TaskStatus.COMPLETED

    def test_conditional_false_branch(self):
        """测试条件为假的分支"""
        branch = ConditionalBranch("test-branch")
        true_task = Task(id="true", name="True Task", func=dummy_task, args=(1,))
        false_task = Task(id="false", name="False Task", func=dummy_task, args=(0,))

        branch.add_branch(
            name="test",
            condition=lambda ctx: ctx.get("value", 0) > 0,
            true_task=true_task,
            false_task=false_task,
        )

        results = branch.execute({"value": -1})
        assert "false" in results
        assert false_task.status == TaskStatus.COMPLETED

    def test_conditional_no_false_branch(self):
        """测试没有假分支"""
        branch = ConditionalBranch("test-branch")
        true_task = Task(id="true", name="True Task", func=dummy_task, args=(1,))

        branch.add_branch(
            name="test",
            condition=lambda ctx: ctx.get("value", 0) > 0,
            true_task=true_task,
        )

        results = branch.execute({"value": -1})
        assert len(results) == 0


class TestWorkflowResult:
    """测试 WorkflowResult"""

    def test_workflow_result_properties(self):
        """测试 WorkflowResult 属性"""
        t1 = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        t1.run()

        t2 = Task(id="t2", name="Task 2", func=failing_task)
        try:
            t2.run()
        except ValueError:
            pass

        t3 = Task(id="t3", name="Task 3", func=dummy_task, args=(3,))
        t3.status = TaskStatus.SKIPPED

        result = WorkflowResult(
            workflow_id="test",
            tasks=[t1, t2, t3],
            success=False,
            duration=1.0,
        )

        assert len(result.completed_tasks) == 1
        assert len(result.failed_tasks) == 1
        assert len(result.skipped_tasks) == 1
