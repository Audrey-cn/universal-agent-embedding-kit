"""Tests for memory module - improving coverage"""

import tempfile
from pathlib import Path

from src.memory import (
    ContextCompressor,
    KeyInfoExtractor,
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


class TestL2TaskContextCoverage:
    """L2TaskContext 覆盖率测试"""

    def test_evict(self):
        """测试淘汰策略"""
        layer = L2TaskContext(max_size=2)
        layer.add(
            MemoryEntry(id="e1", content="Content 1", layer=MemoryLayerType.L2_TASK, timestamp=1.0)
        )
        layer.add(
            MemoryEntry(id="e2", content="Content 2", layer=MemoryLayerType.L2_TASK, timestamp=2.0)
        )
        layer.add(
            MemoryEntry(id="e3", content="Content 3", layer=MemoryLayerType.L2_TASK, timestamp=3.0)
        )
        assert len(layer) == 2

    def test_compress(self):
        """测试压缩"""
        layer = L2TaskContext(max_size=100)
        for i in range(60):
            layer.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L2_TASK,
                    importance=i / 60,
                )
            )
        layer.compress()
        assert len(layer) <= 30

    def test_search_with_tags(self):
        """测试带标签的搜索"""
        layer = L2TaskContext(max_size=10)
        layer.add(
            MemoryEntry(
                id="e1",
                content="Test content",
                layer=MemoryLayerType.L2_TASK,
                tags=["test", "important"],
            )
        )
        query = MemoryQuery(query="Test", tags=["important"])
        results = layer.search(query)
        assert len(results) == 1


class TestL3PersistentContextCoverage:
    """L3PersistentContext 覆盖率测试"""

    def test_evict(self):
        """测试淘汰策略"""
        layer = L3PersistentContext(max_size=2)
        layer.add(
            MemoryEntry(
                id="e1",
                content="Content 1",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.3,
                timestamp=1.0,
            )
        )
        layer.add(
            MemoryEntry(
                id="e2",
                content="Content 2",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.7,
                timestamp=2.0,
            )
        )
        layer.add(
            MemoryEntry(
                id="e3",
                content="Content 3",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.5,
                timestamp=3.0,
            )
        )
        assert len(layer) == 2

    def test_compress(self):
        """测试压缩"""
        layer = L3PersistentContext(max_size=100)
        for i in range(90):
            layer.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L3_PERSISTENT,
                    importance=i / 90,
                )
            )
        layer.compress()
        assert len(layer) <= 72  # 80% of 90

    def test_search_with_min_importance(self):
        """测试带最小重要性的搜索"""
        layer = L3PersistentContext(max_size=10)
        layer.add(
            MemoryEntry(
                id="e1",
                content="Important content",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.9,
            )
        )
        layer.add(
            MemoryEntry(
                id="e2",
                content="Less important",
                layer=MemoryLayerType.L3_PERSISTENT,
                importance=0.3,
            )
        )
        query = MemoryQuery(query="content", min_importance=0.5)
        results = layer.search(query)
        assert len(results) == 1


class TestContextCompressorCoverage:
    """ContextCompressor 覆盖率测试"""

    def test_compress_empty(self):
        """测试压缩空列表"""
        compressor = ContextCompressor()
        result = compressor.compress([])
        assert len(result) == 0

    def test_compress_single(self):
        """测试压缩单个条目"""
        compressor = ContextCompressor()
        entries = [MemoryEntry(id="e1", content="Test", layer=MemoryLayerType.L1_CURRENT)]
        result = compressor.compress(entries, target_ratio=0.5)
        assert len(result) == 1

    def test_merge_similar_empty(self):
        """测试合并空列表"""
        compressor = ContextCompressor()
        result = compressor.merge_similar([])
        assert len(result) == 0

    def test_merge_similar_single(self):
        """测试合并单个条目"""
        compressor = ContextCompressor()
        entries = [MemoryEntry(id="e1", content="Test", layer=MemoryLayerType.L1_CURRENT)]
        result = compressor.merge_similar(entries)
        assert len(result) == 1

    def test_extract_summary_empty(self):
        """测试提取空摘要"""
        compressor = ContextCompressor()
        result = compressor.extract_summary([])
        assert result == ""


class TestKeyInfoExtractorCoverage:
    """KeyInfoExtractor 覆盖率测试"""

    def test_extract_all(self):
        """测试提取所有信息"""
        extractor = KeyInfoExtractor()
        content = "We decided to use Python. The system must handle errors. Found a bug."
        result = extractor.extract_all(content)
        assert "decisions" in result
        assert "constraints" in result
        assert "errors" in result

    def test_create_memory_entry(self):
        """测试创建记忆条目"""
        extractor = KeyInfoExtractor()
        entry = extractor.create_memory_entry(
            "We decided to use Python",
            MemoryLayerType.L1_CURRENT,
            "e1",
        )
        assert entry.id == "e1"
        assert "decision" in entry.tags
        assert entry.importance > 0.5


class TestUtilizationMonitorCoverage:
    """UtilizationMonitor 覆盖率测试"""

    def test_check_all(self):
        """测试检查所有层"""
        monitor = UtilizationMonitor(threshold=0.4)
        l1 = L1CurrentContext(max_size=10)
        l2 = L2TaskContext(max_size=50)

        for i in range(5):
            l1.add(
                MemoryEntry(id=f"l1_{i}", content=f"Content {i}", layer=MemoryLayerType.L1_CURRENT)
            )
            l2.add(MemoryEntry(id=f"l2_{i}", content=f"Content {i}", layer=MemoryLayerType.L2_TASK))

        snapshots = monitor.check_all([l1, l2])
        assert len(snapshots) == 2

    def test_get_average_utilization(self):
        """测试获取平均利用率"""
        monitor = UtilizationMonitor(threshold=0.4)
        layer = L1CurrentContext(max_size=10)

        for i in range(5):
            layer.add(
                MemoryEntry(id=f"e{i}", content=f"Content {i}", layer=MemoryLayerType.L1_CURRENT)
            )

        monitor.check(layer)
        avg = monitor.get_average_utilization(MemoryLayerType.L1_CURRENT)
        assert avg == 0.5

    def test_get_peak_utilization(self):
        """测试获取峰值利用率"""
        monitor = UtilizationMonitor(threshold=0.4)
        layer = L1CurrentContext(max_size=10)

        for i in range(5):
            layer.add(
                MemoryEntry(id=f"e{i}", content=f"Content {i}", layer=MemoryLayerType.L1_CURRENT)
            )

        monitor.check(layer)
        peak = monitor.get_peak_utilization(MemoryLayerType.L1_CURRENT)
        assert peak == 0.5

    def test_clear_history(self):
        """测试清除历史"""
        monitor = UtilizationMonitor(threshold=0.4)
        layer = L1CurrentContext(max_size=10)
        monitor.check(layer)
        assert len(monitor.snapshots) == 1

        monitor.clear_history()
        assert len(monitor.snapshots) == 0


class TestMemoryPersistenceCoverage:
    """MemoryPersistence 覆盖率测试"""

    def test_save_and_load_all(self):
        """测试保存和加载所有层"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = MemoryPersistence(Path(tmpdir))

            layers = {
                MemoryLayerType.L1_CURRENT: [
                    MemoryEntry(id="e1", content="L1 Content", layer=MemoryLayerType.L1_CURRENT),
                ],
                MemoryLayerType.L2_TASK: [
                    MemoryEntry(id="e2", content="L2 Content", layer=MemoryLayerType.L2_TASK),
                ],
            }

            persistence.save_all(layers)
            loaded = persistence.load_all()

            assert len(loaded[MemoryLayerType.L1_CURRENT]) == 1
            assert len(loaded[MemoryLayerType.L2_TASK]) == 1

    def test_delete(self):
        """测试删除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = MemoryPersistence(Path(tmpdir))
            entries = [MemoryEntry(id="e1", content="Content", layer=MemoryLayerType.L1_CURRENT)]

            persistence.save(entries, MemoryLayerType.L1_CURRENT)
            assert persistence.delete(MemoryLayerType.L1_CURRENT) is True
            assert persistence.delete(MemoryLayerType.L2_TASK) is False


class TestMemoryQueryEngineCoverage:
    """MemoryQueryEngine 覆盖率测试"""

    def test_get_recent(self):
        """测试获取最近的记忆"""
        l1 = L1CurrentContext(max_size=10)
        for i in range(5):
            l1.add(
                MemoryEntry(
                    id=f"e{i}",
                    content=f"Content {i}",
                    layer=MemoryLayerType.L1_CURRENT,
                    timestamp=float(i),
                )
            )

        engine = MemoryQueryEngine([l1])
        recent = engine.get_recent(limit=3)
        assert len(recent) == 3
        assert recent[0].timestamp > recent[-1].timestamp

    def test_get_by_layer(self):
        """测试按层获取"""
        l1 = L1CurrentContext(max_size=10)
        l2 = L2TaskContext(max_size=50)

        l1.add(MemoryEntry(id="e1", content="L1", layer=MemoryLayerType.L1_CURRENT))
        l2.add(MemoryEntry(id="e2", content="L2", layer=MemoryLayerType.L2_TASK))

        engine = MemoryQueryEngine([l1, l2])
        l1_entries = engine.get_by_layer(MemoryLayerType.L1_CURRENT)
        assert len(l1_entries) == 1
        assert l1_entries[0].id == "e1"
