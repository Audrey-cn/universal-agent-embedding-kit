"""向量后端测试 — 不依赖外部库"""

from __future__ import annotations

import pytest

from src.memory.vector import SimpleEmbedding, VectorDocument, VectorSearchEngine, VectorStore
from src.memory.vector_backends import (
    SimpleBackend,
    detect_chromadb,
    detect_sentence_transformers,
)


class TestSimpleBackend:
    """SimpleBackend 功能测试（不依赖外部库）"""

    def test_add_and_count(self):
        """测试添加文档和计数"""
        backend = SimpleBackend(dimension=3)
        assert backend.count() == 0

        backend.add("doc1", [1.0, 0.0, 0.0], {"key": "value"})
        assert backend.count() == 1

        backend.add("doc2", [0.0, 1.0, 0.0], {})
        assert backend.count() == 2

    def test_add_dimension_mismatch(self):
        """测试维度不匹配时抛出异常"""
        backend = SimpleBackend(dimension=3)
        with pytest.raises(ValueError, match="维度"):
            backend.add("doc1", [1.0, 0.0], {})

    def test_search(self):
        """测试线性搜索"""
        backend = SimpleBackend(dimension=3)
        backend.add("doc1", [1.0, 0.0, 0.0], {})
        backend.add("doc2", [0.0, 1.0, 0.0], {})
        backend.add("doc3", [0.5, 0.5, 0.0], {})

        results = backend.search([1.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        # doc1 应该最相似
        assert results[0][0] == "doc1"
        assert results[0][1] > results[1][1]

    def test_search_dimension_mismatch(self):
        """测试查询维度不匹配时抛出异常"""
        backend = SimpleBackend(dimension=3)
        backend.add("doc1", [1.0, 0.0, 0.0], {})
        with pytest.raises(ValueError, match="维度"):
            backend.search([1.0, 0.0], top_k=1)

    def test_delete(self):
        """测试删除文档"""
        backend = SimpleBackend(dimension=3)
        backend.add("doc1", [1.0, 0.0, 0.0], {})
        assert backend.count() == 1

        assert backend.delete("doc1") is True
        assert backend.count() == 0
        assert backend.delete("nonexistent") is False

    def test_search_top_k_larger_than_count(self):
        """测试 top_k 超过文档数量时返回所有结果"""
        backend = SimpleBackend(dimension=3)
        backend.add("doc1", [1.0, 0.0, 0.0], {})
        results = backend.search([1.0, 0.0, 0.0], top_k=10)
        assert len(results) == 1


class TestVectorStoreWithBackend:
    """VectorStore 后端集成测试"""

    def test_default_backend(self):
        """测试默认使用 SimpleBackend"""
        store = VectorStore(dimension=3)
        assert store.backend_name == "SimpleBackend"

        doc = VectorDocument(id="1", content="test", embedding=[1.0, 0.0, 0.0], metadata={})
        store.add(doc)
        assert store.size() == 1

    def test_backend_switch(self):
        """测试后端切换"""
        backend = SimpleBackend(dimension=3)
        store = VectorStore(dimension=3, backend=backend)
        assert store.backend_name == "SimpleBackend"

        doc = VectorDocument(id="1", content="test", embedding=[1.0, 0.0, 0.0], metadata={})
        store.add(doc)
        assert store.size() == 1

    def test_use_chromadb_class_method(self):
        """测试 use_chromadb 类方法"""
        # 在不安装 chromadb 的情况下，应该抛出 ImportError
        if not detect_chromadb():
            with pytest.raises(ImportError, match="chromadb"):
                VectorStore.use_chromadb()
        else:
            # chromadb 已安装时正常创建
            store = VectorStore.use_chromadb()
            assert store.backend_name == "ChromaBackend"

    def test_fallback_mechanism(self):
        """测试 fallback 机制：无 chromadb 时降级到 SimpleBackend"""
        store = VectorStore(dimension=3)
        assert store.backend_name == "SimpleBackend"

        doc = VectorDocument(id="1", content="test", embedding=[1.0, 0.0, 0.0], metadata={})
        store.add(doc)

        results = store.search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0][0].id == "1"

    def test_search_returns_document_objects(self):
        """测试 search 返回 VectorDocument 对象"""
        store = VectorStore(dimension=3)
        doc = VectorDocument(
            id="1", content="hello world", embedding=[1.0, 0.0, 0.0], metadata={"lang": "en"}
        )
        store.add(doc)

        results = store.search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        result_doc, score = results[0]
        assert result_doc.id == "1"
        assert result_doc.content == "hello world"
        assert result_doc.metadata == {"lang": "en"}
        assert score == pytest.approx(1.0)

    def test_remove(self):
        """测试删除文档"""
        store = VectorStore(dimension=3)
        doc = VectorDocument(id="1", content="test", embedding=[1.0, 0.0, 0.0], metadata={})
        store.add(doc)
        assert store.size() == 1

        assert store.remove("1") is True
        assert store.size() == 0
        assert store.remove("nonexistent") is False


class TestSimpleEmbedding:
    """SimpleEmbedding 测试"""

    def test_bag_of_words_encode(self):
        """测试词袋模型编码（基本功能）"""
        embedder = SimpleEmbedding(dimension=10)
        embedding = embedder.encode("hello world")
        assert len(embedding) == 10
        # 归一化后模长应为 1
        import math

        norm = math.sqrt(sum(x * x for x in embedding))
        assert norm == pytest.approx(1.0)

    def test_encode_consistency(self):
        """测试相同文本编码一致性"""
        embedder = SimpleEmbedding(dimension=10)
        e1 = embedder.encode("hello world")
        e2 = embedder.encode("hello world")
        assert e1 == e2

    def test_encode_different_texts(self):
        """测试不同文本产生不同编码"""
        embedder = SimpleEmbedding(dimension=10)
        e1 = embedder.encode("hello world")
        e2 = embedder.encode("goodbye world")
        assert e1 != e2

    def test_sentence_transformers_detection(self):
        """测试 sentence-transformers 检测函数"""
        result = detect_sentence_transformers()
        assert isinstance(result, bool)


class TestVectorSearchEngine:
    """VectorSearchEngine 集成测试"""

    def test_basic_search(self):
        """测试基本搜索功能"""
        engine = VectorSearchEngine(dimension=10)
        engine.add_document("1", "Python programming", {"lang": "python"})
        engine.add_document("2", "Java programming", {"lang": "java"})
        engine.add_document("3", "Cooking recipes", {"lang": "food"})

        results = engine.search("Python", top_k=1)
        assert len(results) == 1
        assert results[0][0] == "1"

    def test_search_without_matches(self):
        """测试无匹配时的搜索"""
        engine = VectorSearchEngine(dimension=10)
        results = engine.search("something", top_k=5)
        assert len(results) == 0

    def test_remove(self):
        """测试删除文档"""
        engine = VectorSearchEngine(dimension=10)
        engine.add_document("1", "test", {})
        assert engine.size() == 1
        assert engine.remove("1") is True
        assert engine.size() == 0

    def test_custom_backend(self):
        """测试使用自定义后端"""
        backend = SimpleBackend(dimension=10)
        engine = VectorSearchEngine(dimension=10, backend=backend)
        engine.add_document("1", "hello world", {})
        assert engine.size() == 1
        results = engine.search("hello", top_k=1)
        assert len(results) == 1


class TestDetectionFunctions:
    """检测函数测试"""

    def test_detect_chromadb(self):
        """测试 chromadb 检测"""
        result = detect_chromadb()
        assert isinstance(result, bool)

    def test_detect_sentence_transformers(self):
        """测试 sentence-transformers 检测"""
        result = detect_sentence_transformers()
        assert isinstance(result, bool)
