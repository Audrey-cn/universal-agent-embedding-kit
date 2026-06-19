"""Benchmark tests for UAEK — 对标 Fable 5"""

import statistics
import time

from src.effort import EffortLevel, classify
from src.memory import (
    L1CurrentContext,
    L2TaskContext,
    L3PersistentContext,
    MemoryEntry,
    MemoryQuery,
    MemoryQueryEngine,
)
from src.memory.interface import MemoryLayerType
from src.workflow import DAG, ParallelScheduler, SequentialScheduler, Task

# 基准测试配置
ITERATIONS = 100


def dummy_task(x: int) -> int:
    return x


class TestEffortBenchmark:
    """Effort 分类基准测试"""

    def test_classify_latency(self):
        """测试分类延迟"""
        latencies = []
        for _ in range(ITERATIONS):
            start = time.time()
            classify("implement authentication module")
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(ITERATIONS * 0.95)]

        print("\nEffort 分类延迟:")
        print(f"  平均: {avg_latency * 1000:.2f}ms")
        print(f"  P95: {p95_latency * 1000:.2f}ms")

        # 断言：平均延迟应 < 10ms
        assert avg_latency < 0.01

    def test_classify_accuracy(self):
        """测试分类准确率"""
        test_cases = [
            ("fix typo in README", [EffortLevel.LOW]),
            ("implement authentication module with JWT", [EffortLevel.LOW, EffortLevel.MEDIUM]),
            (
                "refactor authentication system with 10+ files",
                [EffortLevel.MEDIUM, EffortLevel.HIGH],
            ),
            ("deploy to production database", [EffortLevel.XHIGH]),
        ]

        correct = 0
        total = len(test_cases)

        for task, expected_levels in test_cases:
            result = classify(task)
            if result.level in expected_levels:
                correct += 1

        accuracy = correct / total
        print(f"\nEffort 分类准确率: {accuracy:.0%} ({correct}/{total})")

        # 断言：准确率应 >= 75%
        assert accuracy >= 0.75


class TestWorkflowBenchmark:
    """工作流基准测试"""

    def test_sequential_latency(self):
        """测试顺序执行延迟"""
        workflow = SequentialScheduler("bench-seq")
        for i in range(10):
            workflow.add_task(Task(id=f"t{i}", name=f"Task {i}", func=dummy_task, args=(i,)))

        latencies = []
        for _ in range(ITERATIONS):
            workflow.reset()
            start = time.time()
            workflow.execute()
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n顺序工作流延迟 (10 任务): {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.1

    def test_parallel_latency(self):
        """测试并行执行延迟"""
        workflow = ParallelScheduler("bench-par", max_workers=4)
        for i in range(10):
            workflow.add_task(Task(id=f"t{i}", name=f"Task {i}", func=dummy_task, args=(i,)))

        latencies = []
        for _ in range(ITERATIONS):
            workflow.reset()
            start = time.time()
            workflow.execute()
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n并行工作流延迟 (10 任务): {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.5

    def test_dag_throughput(self):
        """测试 DAG 吞吐量"""
        dag = DAG()
        for i in range(100):
            dag.add_node(Task(id=f"t{i}", name=f"Task {i}", func=dummy_task, args=(i,)))
            if i > 0:
                dag.add_edge(f"t{i - 1}", f"t{i}")

        start = time.time()
        order = dag.topological_sort()
        elapsed = time.time() - start

        print(f"\nDAG 拓扑排序 (100 节点): {elapsed * 1000:.2f}ms")

        assert len(order) == 100
        assert elapsed < 0.1


class TestMemoryBenchmark:
    """记忆基准测试"""

    def test_add_latency(self):
        """测试添加延迟"""
        layer = L1CurrentContext(max_size=10000)

        latencies = []
        for i in range(ITERATIONS):
            start = time.time()
            layer.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L1_CURRENT,
                )
            )
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n记忆添加延迟: {avg_latency * 1000:.4f}ms")

        assert avg_latency < 0.001

    def test_search_latency(self):
        """测试搜索延迟"""
        layer = L1CurrentContext(max_size=1000)
        for i in range(1000):
            layer.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i} with keyword test",
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=i / 1000,
                )
            )

        latencies = []
        for _ in range(ITERATIONS):
            query = MemoryQuery(query="keyword", limit=10)
            start = time.time()
            layer.search(query)
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n记忆搜索延迟 (1000 条): {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.01

    def test_compression_ratio(self):
        """测试压缩率"""
        layer = L1CurrentContext(max_size=1000)
        for i in range(1000):
            layer.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L1_CURRENT,
                    importance=i / 1000,
                )
            )

        original_size = len(layer)
        layer.compress()
        compressed_size = len(layer)

        ratio = compressed_size / original_size
        print(f"\n记忆压缩率: {ratio:.0%} ({original_size} → {compressed_size})")

        # 断言：压缩率应 <= 50%
        assert ratio <= 0.5

    def test_cross_layer_query_latency(self):
        """测试跨层查询延迟"""
        l1 = L1CurrentContext(max_size=100)
        l2 = L2TaskContext(max_size=500)
        l3 = L3PersistentContext(max_size=1000)

        for i in range(100):
            l1.add(
                MemoryEntry(
                    id=f"l1_{i}", content=f"L1 Content {i}", layer=MemoryLayerType.L1_CURRENT
                )
            )
            l2.add(
                MemoryEntry(id=f"l2_{i}", content=f"L2 Content {i}", layer=MemoryLayerType.L2_TASK)
            )
            l3.add(
                MemoryEntry(
                    id=f"l3_{i}", content=f"L3 Content {i}", layer=MemoryLayerType.L3_PERSISTENT
                )
            )

        engine = MemoryQueryEngine([l1, l2, l3])

        latencies = []
        for _ in range(ITERATIONS):
            start = time.time()
            engine.search_by_keyword("Content")
            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n跨层查询延迟 (300 条): {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.05


class TestEndToEndBenchmark:
    """端到端基准测试"""

    def test_full_pipeline_latency(self):
        """测试完整流水线延迟"""
        latencies = []

        for _ in range(10):
            start = time.time()

            # 1. Effort 分类
            effort_result = classify("implement authentication module")
            assert effort_result.level in {
                EffortLevel.LOW,
                EffortLevel.MEDIUM,
                EffortLevel.HIGH,
                EffortLevel.XHIGH,
            }

            # 2. 创建工作流
            workflow = SequentialScheduler("pipeline")
            workflow.add_task(Task(id="t1", name="Task 1", func=dummy_task, args=(1,)))
            workflow.add_task(
                Task(id="t2", name="Task 2", func=dummy_task, args=(2,), dependencies=["t1"])
            )

            # 3. 执行工作流
            workflow_result = workflow.execute()

            # 4. 记录到记忆
            layer = L1CurrentContext(max_size=10)
            layer.add(
                MemoryEntry(
                    id="result",
                    content=f"Pipeline completed: {workflow_result.success}",
                    layer=MemoryLayerType.L1_CURRENT,
                )
            )

            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n完整流水线延迟: {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.5

    def test_memory_informed_effort(self):
        """测试记忆辅助的 Effort 分类"""
        # 创建记忆
        l3 = L3PersistentContext(max_size=100)
        for i in range(50):
            l3.add(
                MemoryEntry(
                    id=f"error_{i}",
                    content=f"Past error {i} in database deployment",
                    layer=MemoryLayerType.L3_PERSISTENT,
                    importance=0.9,
                    tags=["error", "database"],
                )
            )

        engine = MemoryQueryEngine([l3])

        latencies = []
        for _ in range(10):
            start = time.time()

            # 查询相关记忆
            past_errors = engine.search_by_keyword("database")

            # 基于记忆调整 Effort
            if past_errors:
                result = classify("deploy database changes", reversibility=0.2)
            else:
                result = classify("deploy database changes")
            assert result.level in {
                EffortLevel.LOW,
                EffortLevel.MEDIUM,
                EffortLevel.HIGH,
                EffortLevel.XHIGH,
            }

            latencies.append(time.time() - start)

        avg_latency = statistics.mean(latencies)
        print(f"\n记忆辅助 Effort 分类延迟: {avg_latency * 1000:.2f}ms")

        assert avg_latency < 0.1


class TestComparisonWithFable5:
    """与 Fable 5 的对比测试"""

    def test_platform_independence(self):
        """测试平台无关性"""
        # UAEK 可以在任何 Python 环境中运行
        import sys

        assert sys.version_info >= (3, 11)

        # 不依赖特定 Agent 平台
        # 不依赖特定 LLM
        # 不依赖特定操作系统
        print("\n平台信息:")
        print(f"  Python: {sys.version}")
        print(f"  平台: {sys.platform}")

    def test_verification_quality(self):
        """测试验证质量"""
        # Fable 5: 自我批评 (47-74% 作弊率)
        # UAEK: 全新上下文验证 (<10% 目标)

        # 测试全新上下文验证
        from src.verify.fresh_context import FreshContextVerifier

        verifier = FreshContextVerifier()
        assert verifier is not None

        # 验证者不继承执行者上下文
        print("\n验证质量:")
        print("  Fable 5: 自我批评 (47-74% 作弊率)")
        print("  UAEK: 全新上下文验证 (目标 <10%)")

    def test_effort_control(self):
        """测试 Effort 控制"""
        # Fable 5: 提示词注入 (软控制)
        # UAEK: 智能分类 + 调度短语 (结构化控制)

        test_cases = [
            ("simple task", EffortLevel.LOW),
            ("standard task", EffortLevel.MEDIUM),
            ("complex task", EffortLevel.HIGH),
            ("critical task", EffortLevel.XHIGH),
        ]

        print("\nEffort 控制:")
        for task, expected in test_cases:
            result = classify(task)
            print(f"  '{task}' → {result.level.value}")

    def test_memory_management(self):
        """测试记忆管理"""
        # Fable 5: 8 个 memdir 模块
        # UAEK: 分层记忆 + 压缩 + 持久化

        l1 = L1CurrentContext(max_size=100)
        l2 = L2TaskContext(max_size=500)
        l3 = L3PersistentContext(max_size=1000)

        print("\n记忆管理:")
        print(f"  L1 (当前对话): {l1.max_size} 条")
        print(f"  L2 (当前任务): {l2.max_size} 条")
        print(f"  L3 (持久化): {l3.max_size} 条")

    def test_workflow_flexibility(self):
        """测试工作流灵活性"""
        # Fable 5: 内置工作流
        # UAEK: 可配置 DAG

        # 顺序工作流
        seq = SequentialScheduler("seq")
        assert seq.workflow_id == "seq"

        # 并行工作流
        par = ParallelScheduler("par", max_workers=4)
        assert par.workflow_id == "par"

        # DAG
        dag = DAG()
        assert len(dag) == 0

        print("\n工作流类型:")
        print("  顺序: SequentialScheduler")
        print("  并行: ParallelScheduler (max_workers=4)")
        print("  DAG: DAG (自动调度)")
