"""Tests for workflow module - improving coverage"""

import time

from src.workflow import Task, WorkflowResult
from src.workflow.conditional import ConditionalBranch
from src.workflow.dag import DAG
from src.workflow.parallel import ParallelScheduler
from src.workflow.sequential import SequentialScheduler


def dummy_task(x: int) -> int:
    return x


def failing_task():
    raise ValueError("Task failed")


def slow_task(x: int, delay: float = 0.01) -> int:
    time.sleep(delay)
    return x


class TestTaskAdvanced:
    """Task 高级测试"""

    def test_task_with_kwargs(self):
        """测试带关键字参数的任务"""
        task = Task(id="t1", name="Task 1", func=lambda x, y=10: x + y, args=(5,), kwargs={"y": 20})
        result = task.run()
        assert result == 25

    def test_task_metadata(self):
        """测试任务元数据"""
        task = Task(
            id="t1",
            name="Task 1",
            func=dummy_task,
            args=(1,),
            metadata={"priority": "high", "owner": "test"},
        )
        assert task.metadata["priority"] == "high"
        assert task.metadata["owner"] == "test"

    def test_task_str_representation(self):
        """测试任务字符串表示"""
        task = Task(id="t1", name="Task 1", func=dummy_task, args=(1,))
        assert task.id == "t1"
        assert task.name == "Task 1"


class TestDAGAdvanced:
    """DAG 高级测试"""

    def test_dag_complex_topology(self):
        """测试复杂拓扑"""
        dag = DAG()
        # 创建菱形依赖
        dag.add_node(Task(id="a", name="A", func=dummy_task, args=(1,)))
        dag.add_node(Task(id="b", name="B", func=dummy_task, args=(2,)))
        dag.add_node(Task(id="c", name="C", func=dummy_task, args=(3,)))
        dag.add_node(Task(id="d", name="D", func=dummy_task, args=(4,)))

        dag.add_edge("a", "b")
        dag.add_edge("a", "c")
        dag.add_edge("b", "d")
        dag.add_edge("c", "d")

        assert dag.has_cycle() is False
        order = dag.topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_dag_multiple_roots(self):
        """测试多根节点"""
        dag = DAG()
        dag.add_node(Task(id="a", name="A", func=dummy_task, args=(1,)))
        dag.add_node(Task(id="b", name="B", func=dummy_task, args=(2,)))
        dag.add_node(Task(id="c", name="C", func=dummy_task, args=(3,)))

        dag.add_edge("a", "c")
        dag.add_edge("b", "c")

        roots = dag.get_root_nodes()
        assert roots == {"a", "b"}

    def test_dag_multiple_leaves(self):
        """测试多叶子节点"""
        dag = DAG()
        dag.add_node(Task(id="a", name="A", func=dummy_task, args=(1,)))
        dag.add_node(Task(id="b", name="B", func=dummy_task, args=(2,)))
        dag.add_node(Task(id="c", name="C", func=dummy_task, args=(3,)))

        dag.add_edge("a", "b")
        dag.add_edge("a", "c")

        leaves = dag.get_leaf_nodes()
        assert leaves == {"b", "c"}

    def test_dag_contains(self):
        """测试节点包含检查"""
        dag = DAG()
        dag.add_node(Task(id="a", name="A", func=dummy_task, args=(1,)))
        assert "a" in dag
        assert "b" not in dag

    def test_dag_len(self):
        """测试 DAG 长度"""
        dag = DAG()
        dag.add_node(Task(id="a", name="A", func=dummy_task, args=(1,)))
        dag.add_node(Task(id="b", name="B", func=dummy_task, args=(2,)))
        assert len(dag) == 2


class TestSequentialSchedulerAdvanced:
    """SequentialScheduler 高级测试"""

    def test_sequential_with_complex_dependencies(self):
        """测试复杂依赖的顺序执行"""
        workflow = SequentialScheduler("complex-seq")
        workflow.add_task(Task(id="a", name="A", func=dummy_task, args=(1,)))
        workflow.add_task(Task(id="b", name="B", func=dummy_task, args=(2,), dependencies=["a"]))
        workflow.add_task(Task(id="c", name="C", func=dummy_task, args=(3,), dependencies=["a"]))
        workflow.add_task(
            Task(id="d", name="D", func=dummy_task, args=(4,), dependencies=["b", "c"])
        )

        result = workflow.execute()
        assert result.success is True
        assert len(result.completed_tasks) == 4

    def test_sequential_reset_and_rerun(self):
        """测试重置后重新运行"""
        workflow = SequentialScheduler("reset-seq")
        workflow.add_task(Task(id="t1", name="T1", func=dummy_task, args=(1,)))

        result1 = workflow.execute()
        assert result1.success is True

        workflow.reset()
        result2 = workflow.execute()
        assert result2.success is True

    def test_sequential_error_propagation(self):
        """测试错误传播"""
        workflow = SequentialScheduler("error-seq", fail_fast=False)
        workflow.add_task(Task(id="t1", name="T1", func=failing_task))
        workflow.add_task(Task(id="t2", name="T2", func=dummy_task, args=(1,)))
        workflow.add_task(Task(id="t3", name="T3", func=dummy_task, args=(2,)))

        result = workflow.execute()
        assert result.success is False
        assert len(result.errors) > 0


class TestParallelSchedulerAdvanced:
    """ParallelScheduler 高级测试"""

    def test_parallel_with_max_workers(self):
        """测试最大工作线程数"""
        workflow = ParallelScheduler("parallel-workers", max_workers=2)
        for i in range(5):
            workflow.add_task(Task(id=f"t{i}", name=f"T{i}", func=slow_task, args=(i,)))

        result = workflow.execute()
        assert result.success is True
        assert len(result.completed_tasks) == 5

    def test_parallel_with_mixed_dependencies(self):
        """测试混合依赖"""
        workflow = ParallelScheduler("mixed-deps", max_workers=2)
        workflow.add_task(Task(id="a", name="A", func=dummy_task, args=(1,)))
        workflow.add_task(Task(id="b", name="B", func=dummy_task, args=(2,)))
        workflow.add_task(Task(id="c", name="C", func=dummy_task, args=(3,), dependencies=["a"]))
        workflow.add_task(Task(id="d", name="D", func=dummy_task, args=(4,), dependencies=["b"]))

        result = workflow.execute()
        assert result.success is True

    def test_parallel_fail_fast_cancels(self):
        """测试快速失败取消"""
        workflow = ParallelScheduler("fail-fast", max_workers=2, fail_fast=True)
        workflow.add_task(Task(id="t1", name="T1", func=failing_task))
        workflow.add_task(
            Task(id="t2", name="T2", func=slow_task, args=(1,), kwargs={"delay": 1.0})
        )

        result = workflow.execute()
        assert result.success is False


class TestConditionalBranchAdvanced:
    """ConditionalBranch 高级测试"""

    def test_multiple_branches(self):
        """测试多分支"""
        branch = ConditionalBranch("multi-branch")
        branch.add_branch(
            name="branch1",
            condition=lambda ctx: ctx.get("value", 0) > 10,
            true_task=Task(id="t1", name="T1", func=dummy_task, args=(1,)),
        )
        branch.add_branch(
            name="branch2",
            condition=lambda ctx: ctx.get("value", 0) > 5,
            true_task=Task(id="t2", name="T2", func=dummy_task, args=(2,)),
        )

        results = branch.execute({"value": 8})
        assert "t2" in results
        assert "t1" not in results

    def test_branch_with_exception(self):
        """测试分支异常处理"""
        branch = ConditionalBranch("error-branch")
        branch.add_branch(
            name="branch1",
            condition=lambda ctx: True,
            true_task=Task(id="t1", name="T1", func=failing_task),
        )

        results = branch.execute({})
        assert "t1" in results
        assert isinstance(results["t1"], ValueError)


class TestWorkflowResultAdvanced:
    """WorkflowResult 高级测试"""

    def test_workflow_result_str(self):
        """测试结果字符串表示"""
        result = WorkflowResult(
            workflow_id="test",
            tasks=[],
            success=True,
            duration=1.5,
        )
        assert "SUCCESS" in str(result)
        assert "test" in str(result)

    def test_workflow_result_with_errors(self):
        """测试带错误的结果"""
        result = WorkflowResult(
            workflow_id="test",
            tasks=[],
            success=False,
            duration=1.0,
            errors=[ValueError("error1"), TypeError("error2")],
        )
        assert len(result.errors) == 2
        assert result.success is False

    def test_workflow_result_metadata(self):
        """测试结果元数据"""
        result = WorkflowResult(
            workflow_id="test",
            tasks=[],
            success=True,
            duration=1.0,
            metadata={"version": "1.0", "author": "test"},
        )
        assert result.metadata["version"] == "1.0"
