"""Vector Search — 向量搜索"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from .vector_backends import (
    ChromaBackend,
    SimpleBackend,
    VectorBackend,
    cosine_similarity,
    detect_sentence_transformers,
)


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
        return cosine_similarity(self.embedding, other.embedding)


class VectorStore:
    """向量存储 — 支持可插拔后端（SimpleBackend / ChromaBackend）"""

    def __init__(self, dimension: int = 384, backend: VectorBackend | None = None):
        self.dimension = dimension
        self._backend = backend if backend is not None else SimpleBackend(dimension=dimension)
        self.documents: dict[str, VectorDocument] = {}

    @classmethod
    def use_chromadb(cls, persist_dir: str | None = None, dimension: int = 384) -> VectorStore:
        """使用 ChromaDB 后端创建 VectorStore"""
        backend = ChromaBackend(persist_dir=persist_dir)
        return cls(dimension=dimension, backend=backend)

    @property
    def backend_name(self) -> str:
        """当前后端名称"""
        return type(self._backend).__name__

    def add(self, doc: VectorDocument):
        """添加文档"""
        if len(doc.embedding) != self.dimension:
            raise ValueError(f"Embedding dimension must be {self.dimension}")
        self.documents[doc.id] = doc
        self._backend.add(doc.id, doc.embedding, doc.metadata)

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[VectorDocument, float]]:
        """搜索最相似的文档"""
        if len(query_embedding) != self.dimension:
            raise ValueError(f"Query embedding dimension must be {self.dimension}")

        backend_results = self._backend.search(query_embedding, top_k)

        results: list[tuple[VectorDocument, float]] = []
        for doc_id, score in backend_results:
            doc = self.documents.get(doc_id)
            if doc is not None:
                results.append((doc, score))
        return results

    def remove(self, doc_id: str) -> bool:
        """删除文档（先后端删除，再本地删除，保证一致性）"""
        if not self._backend.delete(doc_id):
            return False
        self.documents.pop(doc_id, None)
        return True

    def size(self) -> int:
        """获取文档数量"""
        return self._backend.count()


class SimpleEmbedding:
    """嵌入模型 — 自动检测并使用最佳可用模型

    优先级：sentence-transformers > 词袋模型
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vocabulary: dict[str, int] = {}
        self._model = None

        # 尝试加载 sentence-transformers 语义模型
        if detect_sentence_transformers():
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                # 使用模型的实际维度
                self.dimension = self._model.get_sentence_embedding_dimension()
            except Exception:
                self._model = None

    def encode(self, text: str) -> list[float]:
        """编码文本为向量"""
        if self._model is not None:
            # 使用语义模型编码
            embedding = self._model.encode(text, convert_to_numpy=True).tolist()
            return cast(list[float], embedding)

        # 降级到词袋模型
        return self._bag_of_words_encode(text)

    def _bag_of_words_encode(self, text: str) -> list[float]:
        """词袋模型编码（fallback）"""
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

    def __init__(self, dimension: int = 384, backend: VectorBackend | None = None):
        self.store = VectorStore(dimension=dimension, backend=backend)
        self.embedder = SimpleEmbedding(dimension=dimension)

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
