"""Integration tests for UAEK"""

import tempfile
from pathlib import Path

from src.effort import EffortLevel, classify
from src.memory import (
    L1CurrentContext,
    L2TaskContext,
    L3PersistentContext,
    MemoryEntry,
    MemoryPersistence,
    MemoryQuery,
    MemoryQueryEngine,
    UtilizationMonitor,
)
from src.memory.interface import MemoryLayerType
from src.skills import Skill, SkillExecutor, SkillMetadata, SkillStatus
from src.verify import VerificationResult, VerificationType, verify
from src.workflow import DAG, ParallelScheduler, SequentialScheduler, Task


# 测试辅助函数
def dummy_task(x: int) -> int:
    return x


def failing_task():
    raise ValueError("Task failed")


class TestEndToEnd:
    """端到端集成测试"""

    def test_effort_then_workflow(self):
        """测试 Effort 分类 -> 工作流执行"""
        # 1. 分析任务
        result = classify("implement user authentication module")
        assert result.level in [EffortLevel.MEDIUM, EffortLevel.HIGH, EffortLevel.XHIGH]

        # 2. 创建工作流
        workflow = SequentialScheduler("auth-workflow")
        t1 = Task(id="design", name="设计", func=dummy_task, args=(1,))
        t2 = Task(id="implement", name="实现", func=dummy_task, args=(2,), dependencies=["design"])
        t3 = Task(id="test", name="测试", func=dummy_task, args=(3,), dependencies=["implement"])

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3)

        # 3. 执行工作流
        wf_result = workflow.execute()
        assert wf_result.success is True
        assert len(wf_result.completed_tasks) == 3

    def test_effort_then_verify(self):
        """测试 Effort 分类 -> 验证"""
        # 1. 分析任务
        result = classify("fix typo in README")
        assert result.level == EffortLevel.LOW

        # 2. 创建测试目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 pyproject.toml 以触发 BUILD 验证
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'test'\n")

            # 3. 验证（使用 BUILD）
            v_result = verify(Path(tmpdir), verification_type=VerificationType.BUILD)
            # BUILD 可能失败（因为没有实际项目），但不应该抛出异常
            assert v_result is not None
            assert isinstance(v_result, VerificationResult)

    def test_workflow_with_memory(self):
        """测试工作流 + 记忆管理"""
        # 1. 创建记忆
        l1 = L1CurrentContext(max_size=10)
        l2 = L2TaskContext(max_size=50)

        # 2. 添加任务相关记忆
        l1.add(
            MemoryEntry(
                id="task_start",
                content="开始实现认证模块",
                layer=MemoryLayerType.L1_CURRENT,
                importance=0.7,
                tags=["task"],
            )
        )

        l2.add(
            MemoryEntry(
                id="decision_1",
                content="决定使用 JWT 认证",
                layer=MemoryLayerType.L2_TASK,
                importance=0.9,
                tags=["decision"],
            )
        )

        # 3. 查询记忆
        engine = MemoryQueryEngine([l1, l2])
        results = engine.search_by_keyword("认证")
        assert len(results) == 2

        # 4. 执行工作流
        workflow = SequentialScheduler("auth-workflow")
        t1 = Task(id="implement", name="实现", func=dummy_task, args=(1,))
        workflow.add_task(t1)

        wf_result = workflow.execute()
        assert wf_result.success is True

        # 5. 添加完成记忆
        l1.add(
            MemoryEntry(
                id="task_done",
                content="认证模块实现完成",
                layer=MemoryLayerType.L1_CURRENT,
                importance=0.8,
                tags=["task", "completed"],
            )
        )

        assert len(l1) == 2

    def test_skill_with_executor(self):
        """测试技能加载 + 执行"""
        # 1. 创建技能
        metadata = SkillMetadata(name="test-skill", description="测试技能")
        skill = Skill(
            metadata=metadata,
            content="# 测试技能\n\n1. 步骤一\n2. 步骤二\n3. 步骤三",
        )

        # 2. 执行技能
        executor = SkillExecutor()
        result = executor.execute(skill, context={"task": "实现认证模块"})

        assert skill.status == SkillStatus.COMPLETED
        assert "instructions" in result
        assert len(result["instructions"]) == 3

    def test_memory_compression_pipeline(self):
        """测试记忆压缩流水线"""
        # 1. 创建记忆层
        l1 = L1CurrentContext(max_size=100)

        # 2. 添加大量记忆
        for i in range(60):
            l1.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=i / 60,
                )
            )

        assert len(l1) == 60

        # 3. 压缩
        l1.compress()
        assert len(l1) <= 30

        # 4. 查询
        query = MemoryQuery(query="Content", limit=5)
        results = l1.search(query)
        assert len(results) <= 5

    def test_context_manager_integration(self):
        """测试上下文管理器集成"""
        # 1. 创建所有层
        l1 = L1CurrentContext(max_size=10)
        l2 = L2TaskContext(max_size=50)
        l3 = L3PersistentContext(max_size=100)

        # 2. 添加记忆
        l1.add(
            MemoryEntry(
                id="current",
                content="当前对话内容",
                layer=MemoryLayerType.L1_CURRENT,
                importance=0.5,
            )
        )

        l2.add(
            MemoryEntry(
                id="task",
                content="任务相关决策",
                layer=MemoryLayerType.L2_TASK,
                importance=0.8,
                tags=["decision"],
            )
        )

        l3.add(
            MemoryEntry(
                id="persistent",
                content="项目架构决策",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.9,
                tags=["architecture"],
            )
        )

        # 3. 跨层查询
        engine = MemoryQueryEngine([l1, l2, l3])

        # 查询所有"决策"
        results = engine.search_by_tags(["decision"])
        assert len(results) >= 1

        # 查询高重要性
        results = engine.search_by_importance(0.8)
        assert len(results) == 2

        # 4. 获取统计
        stats = engine.get_statistics()
        assert stats["total"] == 3

    def test_utilization_monitoring(self):
        """测试利用率监控"""
        # 1. 创建监控器
        monitor = UtilizationMonitor(threshold=0.4)

        # 2. 创建记忆层
        l1 = L1CurrentContext(max_size=10)

        # 3. 添加记忆直到超过阈值
        for i in range(5):
            l1.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L1_CURRENT,
                )
            )

        # 4. 检查利用率
        snapshot = monitor.check(l1)
        assert snapshot.utilization == 0.5
        assert snapshot.current_size == 5

        # 5. 获取历史
        history = monitor.get_history()
        assert len(history) == 1

    def test_persistence_roundtrip(self):
        """测试持久化往返"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 创建持久化管理器
            persistence = MemoryPersistence(Path(tmpdir))

            # 2. 创建记忆
            entries = [
                MemoryEntry(
                    id="e1",
                    content="Content 1",
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=0.8,
                    tags=["test"],
                ),
                MemoryEntry(
                    id="e2",
                    content="Content 2",
                    layer=MemoryLayerType.L2_TASK,
                    importance=0.6,
                ),
            ]

            # 3. 保存
            persistence.save(entries, MemoryLayerType.L1_CURRENT)

            # 4. 加载
            loaded = persistence.load(MemoryLayerType.L1_CURRENT)
            assert len(loaded) == 2
            assert loaded[0].content == "Content 1"
            assert loaded[0].importance == 0.8
            assert "test" in loaded[0].tags

    def test_parallel_workflow_with_memory(self):
        """测试并行工作流 + 记忆"""
        # 1. 创建记忆
        l1 = L1CurrentContext(max_size=100)

        # 2. 创建并行工作流
        workflow = ParallelScheduler("parallel-workflow", max_workers=2)
        t1 = Task(id="t1", name="任务1", func=dummy_task, args=(1,))
        t2 = Task(id="t2", name="任务2", func=dummy_task, args=(2,))
        t3 = Task(id="t3", name="任务3", func=dummy_task, args=(3,))

        workflow.add_task(t1)
        workflow.add_task(t2)
        workflow.add_task(t3)

        # 3. 执行
        result = workflow.execute()
        assert result.success is True

        # 4. 记录结果到记忆
        for task in result.completed_tasks:
            l1.add(
                MemoryEntry(
                    id=f"result_{task.id}",
                    content=f"{task.name} 完成，结果: {task.result}",
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=0.7,
                )
            )

        assert len(l1) == 3

    def test_dag_with_conditional(self):
        """测试 DAG + 条件分支"""
        # 1. 创建 DAG
        dag = DAG()
        t1 = Task(id="check", name="检查", func=dummy_task, args=(1,))
        t2 = Task(id="success", name="成功路径", func=dummy_task, args=(2,))
        t3 = Task(id="failure", name="失败路径", func=dummy_task, args=(3,))

        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_node(t3)
        dag.add_edge("check", "success")
        dag.add_edge("check", "failure")

        # 2. 验证 DAG
        dag.validate()
        assert dag.has_cycle() is False

        # 3. 获取拓扑排序
        order = dag.topological_sort()
        assert order.index("check") < order.index("success")
        assert order.index("check") < order.index("failure")


class TestCrossComponent:
    """跨组件测试"""

    def test_effort_affects_verification(self):
        """测试 Effort 影响验证策略"""
        # LOW Effort - 跳过验证
        low_result = classify("fix typo", language="en")
        assert low_result.level == EffortLevel.LOW
        assert (
            "skip" in low_result.verification_depth.lower()
            or "跳过" in low_result.verification_depth
        )

        # XHIGH Effort - 全新上下文验证
        xhigh_result = classify(
            "deploy to production database",
            reversibility=0.1,
            language="en",
        )
        assert xhigh_result.level == EffortLevel.XHIGH
        assert (
            "fresh" in xhigh_result.verification_depth.lower()
            or "全新" in xhigh_result.verification_depth
        )

    def test_memory_informs_effort(self):
        """测试记忆影响 Effort 分类"""
        # 创建记忆
        l3 = L3PersistentContext(max_size=100)
        l3.add(
            MemoryEntry(
                id="past_error",
                content="上次部署数据库时出错，需要特别小心",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.9,
                tags=["error", "database"],
            )
        )

        # 查询相关记忆
        engine = MemoryQueryEngine([l3])
        past_errors = engine.search_by_keyword("数据库")
        assert len(past_errors) > 0

        # 基于记忆调整 Effort
        if past_errors:
            result = classify("deploy database changes", reversibility=0.2)
            assert result.level == EffortLevel.XHIGH

    def test_workflow_tracks_memory(self):
        """测试工作流追踪记忆"""
        # 1. 创建记忆和工作流
        l1 = L1CurrentContext(max_size=100)
        workflow = SequentialScheduler("tracked-workflow")

        # 2. 定义带记忆的任务
        def task_with_memory(task_id: str, content: str):
            l1.add(
                MemoryEntry(
                    id=f"task_{task_id}",
                    content=content,
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=0.7,
                )
            )
            return content

        t1 = Task(id="t1", name="任务1", func=task_with_memory, args=("t1", "任务1完成"))
        t2 = Task(id="t2", name="任务2", func=task_with_memory, args=("t2", "任务2完成"))

        workflow.add_task(t1)
        workflow.add_task(t2)

        # 3. 执行
        result = workflow.execute()
        assert result.success is True

        # 4. 验证记忆被记录
        assert len(l1) == 2
        query = MemoryQuery(query="完成", limit=10)
        results = l1.search(query)
        assert len(results) == 2
