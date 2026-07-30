"""Tests for memory/context manager"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

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
from src.memory.service import MemoryService


# 测试辅助函数
def create_entry(
    entry_id: str,
    content: str,
    layer: MemoryLayerType = MemoryLayerType.L1_CURRENT,
    importance: float = 0.5,
    tags: list[str] | None = None,
) -> MemoryEntry:
    """创建测试记忆条目"""
    return MemoryEntry(
        id=entry_id,
        content=content,
        layer=layer,
        importance=importance,
        timestamp=time.time(),
        tags=tags or [],
    )


class TestMemoryEntry:
    """测试 MemoryEntry"""

    def test_entry_creation(self):
        """测试条目创建"""
        entry = create_entry("e1", "Test content")
        assert entry.id == "e1"
        assert entry.content == "Test content"
        assert entry.importance == 0.5

    def test_entry_invalid_id(self):
        """测试无效 ID"""
        with pytest.raises(ValueError, match="Memory entry id cannot be empty"):
            MemoryEntry(id="", content="Test", layer=MemoryLayerType.L1_CURRENT)


class TestL1CurrentContext:
    """测试 L1CurrentContext"""

    def test_add_entry(self):
        """测试添加条目"""
        layer = L1CurrentContext(max_size=10)
        entry = create_entry("e1", "Test content")
        layer.add(entry)
        assert len(layer) == 1

    def test_get_entry(self):
        """测试获取条目"""
        layer = L1CurrentContext(max_size=10)
        entry = create_entry("e1", "Test content")
        layer.add(entry)
        result = layer.get("e1")
        assert result is not None
        assert result.content == "Test content"

    def test_remove_entry(self):
        """测试删除条目"""
        layer = L1CurrentContext(max_size=10)
        entry = create_entry("e1", "Test content")
        layer.add(entry)
        assert layer.remove("e1") is True
        assert len(layer) == 0

    def test_evict(self):
        """测试淘汰策略"""
        layer = L1CurrentContext(max_size=2)
        layer.add(create_entry("e1", "Content 1", importance=0.3))
        layer.add(create_entry("e2", "Content 2", importance=0.7))
        layer.add(create_entry("e3", "Content 3", importance=0.5))

        # 应该淘汰最旧的条目
        assert len(layer) == 2

    def test_compress(self):
        """测试压缩（自适应压缩会根据信息密度调整阈值）"""
        layer = L1CurrentContext(max_size=100)
        for i in range(60):
            layer.add(create_entry(f"e{i}", f"Content {i}", importance=i / 60))

        layer.compress()
        # 自适应压缩后条目数应减少（但具体阈值由信息密度决定）
        assert len(layer) < 60

    def test_search(self):
        """测试搜索"""
        layer = L1CurrentContext(max_size=10)
        layer.add(create_entry("e1", "Python programming", importance=0.8))
        layer.add(create_entry("e2", "Java programming", importance=0.6))
        layer.add(create_entry("e3", "Python data science", importance=0.9))

        query = MemoryQuery(query="Python", limit=10)
        results = layer.search(query)
        assert len(results) == 2


class TestL2TaskContext:
    """测试 L2TaskContext"""

    def test_add_and_search(self):
        """测试添加和搜索"""
        layer = L2TaskContext(max_size=10)
        layer.add(create_entry("e1", "Implement authentication", tags=["coding"]))
        layer.add(create_entry("e2", "Write tests", tags=["testing"]))

        query = MemoryQuery(query="authentication", tags=["coding"])
        results = layer.search(query)
        assert len(results) == 1
        assert results[0].id == "e1"


class TestL3PersistentContext:
    """测试 L3PersistentContext"""

    def test_add_and_search(self):
        """测试添加和搜索"""
        layer = L3PersistentContext(max_size=100)
        layer.add(create_entry("e1", "Project architecture decision", importance=0.9))
        layer.add(create_entry("e2", "Daily log", importance=0.3))

        query = MemoryQuery(query="architecture", min_importance=0.5)
        results = layer.search(query)
        assert len(results) == 1
        assert results[0].id == "e1"


class TestContextCompressor:
    """测试 ContextCompressor"""

    def test_compress(self):
        """测试压缩"""
        compressor = ContextCompressor()
        entries = [
            create_entry("e1", "Important decision", importance=0.9),
            create_entry("e2", "Debug log", importance=0.2),
            create_entry("e3", "Error found", importance=0.8),
            create_entry("e4", "Temporary note", importance=0.1),
        ]

        compressed = compressor.compress(entries, target_ratio=0.5)
        assert len(compressed) == 2

    def test_merge_similar(self):
        """测试合并相似条目"""
        compressor = ContextCompressor()
        entries = [
            create_entry("e1", "Python programming language"),
            create_entry("e2", "Python programming language"),
            create_entry("e3", "Java programming language"),
        ]

        merged = compressor.merge_similar(entries, threshold=0.8)
        assert len(merged) < len(entries)

    def test_extract_summary(self):
        """测试提取摘要"""
        compressor = ContextCompressor()
        entries = [
            create_entry("e1", "A" * 200, importance=0.9),
            create_entry("e2", "B" * 200, importance=0.7),
        ]

        summary = compressor.extract_summary(entries, max_length=300)
        assert len(summary) <= 300


class TestKeyInfoExtractor:
    """测试 KeyInfoExtractor"""

    def test_extract_decisions(self):
        """测试提取决策"""
        extractor = KeyInfoExtractor()
        content = "We decided to use Python for this project."
        decisions = extractor.extract_decisions(content)
        assert len(decisions) > 0

    def test_extract_constraints(self):
        """测试提取约束"""
        extractor = KeyInfoExtractor()
        content = "The system must handle 1000 requests per second."
        constraints = extractor.extract_constraints(content)
        assert len(constraints) > 0

    def test_extract_errors(self):
        """测试提取错误"""
        extractor = KeyInfoExtractor()
        content = "Found a bug in the authentication module."
        errors = extractor.extract_errors(content)
        assert len(errors) > 0

    def test_calculate_importance(self):
        """测试计算重要性"""
        extractor = KeyInfoExtractor()
        content = "We decided to use Python. The system must handle errors."
        importance = extractor.calculate_importance(content)
        assert importance > 0.5

    def test_extract_tags(self):
        """测试提取标签"""
        extractor = KeyInfoExtractor()
        content = "We decided to use Python. Found a bug."
        tags = extractor.extract_tags(content)
        assert "decision" in tags
        assert "error" in tags


class TestUtilizationMonitor:
    """测试 UtilizationMonitor"""

    def test_check_utilization(self):
        """测试检查利用率"""
        monitor = UtilizationMonitor(threshold=0.4)
        layer = L1CurrentContext(max_size=10)

        for i in range(5):
            layer.add(create_entry(f"e{i}", f"Content {i}"))

        snapshot = monitor.check(layer)
        assert snapshot.utilization == 0.5
        assert snapshot.current_size == 5

    def test_threshold_callback(self):
        """测试阈值回调"""
        callback_called = False

        def callback(snapshot):
            nonlocal callback_called
            callback_called = True

        monitor = UtilizationMonitor(threshold=0.4)
        monitor.register_callback(callback)

        layer = L1CurrentContext(max_size=10)
        for i in range(5):
            layer.add(create_entry(f"e{i}", f"Content {i}"))

        monitor.check(layer)
        assert callback_called is True

    def test_get_history(self):
        """测试获取历史"""
        monitor = UtilizationMonitor(threshold=0.4)
        layer = L1CurrentContext(max_size=10)

        monitor.check(layer)
        monitor.check(layer)

        history = monitor.get_history()
        assert len(history) == 2


class TestMemoryPersistence:
    """测试 MemoryPersistence"""

    def test_save_and_load(self):
        """测试保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = MemoryPersistence(Path(tmpdir))
            entries = [
                create_entry("e1", "Content 1"),
                create_entry("e2", "Content 2"),
            ]

            persistence.save(entries, MemoryLayerType.L1_CURRENT)
            loaded = persistence.load(MemoryLayerType.L1_CURRENT)

            assert len(loaded) == 2
            assert loaded[0].content == "Content 1"

    def test_load_nonexistent(self):
        """测试加载不存在的数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = MemoryPersistence(Path(tmpdir))
            loaded = persistence.load(MemoryLayerType.L1_CURRENT)
            assert len(loaded) == 0

    def test_clear(self):
        """测试清除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = MemoryPersistence(Path(tmpdir))
            entries = [create_entry("e1", "Content 1")]

            persistence.save(entries, MemoryLayerType.L1_CURRENT)
            persistence.clear()

            loaded = persistence.load(MemoryLayerType.L1_CURRENT)
            assert len(loaded) == 0


class TestMemoryQueryEngine:
    """测试 MemoryQueryEngine"""

    def test_search(self):
        """测试搜索"""
        l1 = L1CurrentContext(max_size=10)
        l1.add(create_entry("e1", "Python programming", importance=0.8))
        l1.add(create_entry("e2", "Java programming", importance=0.6))

        engine = MemoryQueryEngine([l1])
        results = engine.search_by_keyword("Python")
        assert len(results) == 1

    def test_search_by_tags(self):
        """测试按标签搜索"""
        l1 = L1CurrentContext(max_size=10)
        l1.add(create_entry("e1", "Content 1", tags=["coding"]))
        l1.add(create_entry("e2", "Content 2", tags=["testing"]))

        engine = MemoryQueryEngine([l1])
        results = engine.search_by_tags(["coding"])
        assert len(results) == 1

    def test_get_statistics(self):
        """测试获取统计"""
        l1 = L1CurrentContext(max_size=10)
        l1.add(create_entry("e1", "Content 1"))

        engine = MemoryQueryEngine([l1])
        stats = engine.get_statistics()
        assert stats["l1_current"] == 1
        assert stats["total"] == 1


class TestVectorIntegration:
    """向量存储集成回归测试。

    历史 bug：service.py 曾按一个不存在的 VectorStore 接口调用
    （vs.backend.count() / vs.search(str) / vs.add(id, emb, meta)），
    导致 _vector_search 第一行就抛 AttributeError，被 except 静默吞成 []，
    向量语义搜索上线即失效且毫无症状。这组测试锁住真实 API 契约。
    """

    def test_index_to_vector_succeeds(self, tmp_path: Path):
        """index_to_vector 应成功写入，而不是抛异常"""
        service = MemoryService(tmp_path / "memory")
        added = service.add("the quick brown fox", layer="l1", importance=0.5)
        entry_id = added["id"]

        result = service.index_to_vector(entry_id)

        assert result["indexed"] is True
        assert result["entry_id"] == entry_id
        assert service.vector_store.size() == 1

    def test_vector_search_returns_indexed_entry(self, tmp_path: Path):
        """索引后用相同内容查询，_vector_search 必须返回该条目（不能静默为空）"""
        service = MemoryService(tmp_path / "memory")
        added = service.add("the quick brown fox", layer="l1", importance=0.5)
        service.index_to_vector(added["id"])

        results = service._vector_search("the quick brown fox", limit=5)

        assert len(results) == 1, "向量搜索路径失效：有数据却返回空"
        assert results[0].id == added["id"]

    def test_search_reports_vector_source(self, tmp_path: Path):
        """主搜索路径应在 sources['vector'] 里如实计数向量命中"""
        service = MemoryService(tmp_path / "memory")
        added = service.add("the quick brown fox", layer="l1", importance=0.5)
        service.index_to_vector(added["id"])

        out = service.query("the quick brown fox", enable_vector=True)

        assert out["sources"]["vector"] >= 1, "向量命中未被主搜索路径计入"
