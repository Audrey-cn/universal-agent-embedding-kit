"""向量搜索后端 — 可插拔的向量存储后端"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度（模块级复用函数）"""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class VectorBackend(ABC):
    """向量搜索后端抽象基类"""

    @abstractmethod
    def add(self, doc_id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        """添加文档向量"""
        ...

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        """搜索最相似的文档，返回 (doc_id, score) 列表"""
        ...

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """删除文档，返回是否成功"""
        ...

    @abstractmethod
    def count(self) -> int:
        """获取文档数量"""
        ...


class SimpleBackend(VectorBackend):
    """基于内存的 O(n) 线性搜索后端（fallback）"""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self._embeddings: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def add(self, doc_id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        if len(embedding) != self._dimension:
            raise ValueError(f"嵌入维度必须为 {self._dimension}，实际为 {len(embedding)}")
        self._embeddings[doc_id] = embedding
        self._metadata[doc_id] = metadata

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        if len(query_embedding) != self._dimension:
            raise ValueError(f"查询嵌入维度必须为 {self._dimension}")

        results: list[tuple[str, float]] = []
        for doc_id, embedding in self._embeddings.items():
            score = cosine_similarity(query_embedding, embedding)
            results.append((doc_id, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._embeddings:
            del self._embeddings[doc_id]
            self._metadata.pop(doc_id, None)
            return True
        return False

    def count(self) -> int:
        return len(self._embeddings)


class _RetiredChromaError(RuntimeError, ImportError):
    """Keeps callers that handled the former missing-package error compatible."""


class ChromaBackend(VectorBackend):
    """Retired compatibility name for the removed ChromaDB integration."""

    def __init__(self, persist_dir: str | None = None):
        del persist_dir
        raise _RetiredChromaError(
            "ChromaBackend (chromadb integration) has been retired for security reasons; "
            "use SimpleBackend instead."
        )

    def add(self, doc_id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        raise NotImplementedError("ChromaBackend has been retired")

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        raise NotImplementedError("ChromaBackend has been retired")

    def delete(self, doc_id: str) -> bool:
        raise NotImplementedError("ChromaBackend has been retired")

    def count(self) -> int:
        raise NotImplementedError("ChromaBackend has been retired")


def detect_chromadb() -> bool:
    """ChromaDB is retired and is never considered available."""
    return False


def detect_sentence_transformers() -> bool:
    """检测 sentence-transformers 是否可用"""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False
