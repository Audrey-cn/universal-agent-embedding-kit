"""Vector Search — 向量搜索"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorDocument:
    """向量文档"""

    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any]

    def similarity(self, other: VectorDocument) -> float:
        """计算余弦相似度"""
        if len(self.embedding) != len(other.embedding):
            raise ValueError("Embedding dimensions must match")

        dot_product = sum(a * b for a, b in zip(self.embedding, other.embedding))
        norm_a = math.sqrt(sum(a * a for a in self.embedding))
        norm_b = math.sqrt(sum(b * b for b in other.embedding))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class VectorStore:
    """向量存储"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.documents: dict[str, VectorDocument] = {}

    def add(self, doc: VectorDocument):
        """添加文档"""
        if len(doc.embedding) != self.dimension:
            raise ValueError(f"Embedding dimension must be {self.dimension}")
        self.documents[doc.id] = doc

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[VectorDocument, float]]:
        """搜索最相似的文档"""
        if len(query_embedding) != self.dimension:
            raise ValueError(f"Query embedding dimension must be {self.dimension}")

        query = VectorDocument(id="query", content="", embedding=query_embedding, metadata={})

        results = []
        for doc in self.documents.values():
            score = query.similarity(doc)
            results.append((doc, score))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def remove(self, doc_id: str) -> bool:
        """删除文档"""
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False

    def size(self) -> int:
        """获取文档数量"""
        return len(self.documents)


class SimpleEmbedding:
    """简单嵌入模型（基于词频）"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vocabulary: dict[str, int] = {}

    def encode(self, text: str) -> list[float]:
        """编码文本为向量"""
        # 简单的词袋模型
        words = text.lower().split()
        embedding = [0.0] * self.dimension

        for word in words:
            if word not in self.vocabulary:
                self.vocabulary[word] = len(self.vocabulary) % self.dimension
            idx = self.vocabulary[word]
            embedding[idx] += 1.0

        # 归一化
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding


class VectorSearchEngine:
    """向量搜索引擎"""

    def __init__(self, dimension: int = 384):
        self.store = VectorStore(dimension)
        self.embedder = SimpleEmbedding(dimension)

    def add_document(self, doc_id: str, content: str, metadata: dict[str, Any] | None = None):
        """添加文档"""
        embedding = self.embedder.encode(content)
        doc = VectorDocument(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.store.add(doc)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, str, float]]:
        """搜索文档"""
        query_embedding = self.embedder.encode(query)
        results = self.store.search(query_embedding, top_k)
        return [(doc.id, doc.content, score) for doc, score in results]

    def remove(self, doc_id: str) -> bool:
        """删除文档"""
        return self.store.remove(doc_id)

    def size(self) -> int:
        """获取文档数量"""
        return self.store.size()
