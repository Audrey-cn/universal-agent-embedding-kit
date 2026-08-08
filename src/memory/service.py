"""Stateful memory service for CLI/API/MCP entrypoints.

整合了 RESEARCH_PROPOSAL.md 命题1 的全部能力：
- 三层记忆（L1/L2/L3）
- 自适应压缩（利用率监控 + 自动触发）
- 知识图谱索引（结构化记忆）
- 混合查询（关键词 + 语义向量 + 图谱关系）
- 跨层 promotion/demotion
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .compression import ContextCompressor
from .interface import MemoryEntry, MemoryLayer, MemoryLayerType, MemoryQuery
from .knowledge_graph import KnowledgeGraph
from .layers import L1CurrentContext, L2TaskContext, L3PersistentContext
from .monitor import UtilizationMonitor
from .persistence import MemoryPersistence
from .query import MemoryQueryEngine
from .vector import VectorDocument, VectorStore
from .vector_backends import detect_chromadb


class MemoryService:
    """Small stateful facade over the layered memory primitives.

    整合了知识图谱、利用率监控、向量搜索和混合查询。
    """

    def __init__(self, storage_path: Path | str | None = None, autoload: bool = True):
        if storage_path is None:
            storage_path = Path.home() / ".uaek" / "memory"
        self.storage_path = Path(storage_path)
        self.persistence = MemoryPersistence(self.storage_path)

        # 创建三层记忆
        l1 = L1CurrentContext()
        l2 = L2TaskContext()
        l3 = L3PersistentContext()

        # 建立跨层 promotion/demotion 链路
        l1.set_promotion_target(l2)
        l2.set_promotion_target(l3)
        l2.set_demotion_target(l1)
        l3.set_demotion_target(l2)

        self.layers: dict[MemoryLayerType, MemoryLayer] = {
            MemoryLayerType.L1_CURRENT: l1,
            MemoryLayerType.L2_TASK: l2,
            MemoryLayerType.L3_PERSISTENT: l3,
        }
        self.compressor = ContextCompressor()

        # 利用率监控器（40% 阈值，符合设计文档目标）
        self._monitor = UtilizationMonitor(threshold=0.4)
        self._monitor.register_callback(self._on_utilization_high)

        # 知识图谱
        self._knowledge_graph = KnowledgeGraph()
        l1.set_knowledge_graph(self._knowledge_graph)

        # 自动检测并选择最优向量后端
        self._vector_store: VectorStore | None = None
        if autoload:
            self.restore()

    def add(
        self,
        content: str,
        layer: str | MemoryLayerType = "l1",
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        entry_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a memory entry and return a serializable representation."""
        layer_type = self.resolve_layer(layer)
        resolved_entry_id = entry_id or self._new_entry_id()
        if any(
            layer_object.get(resolved_entry_id) is not None
            for layer_object in self.layers.values()
        ):
            raise ValueError(f"duplicate memory entry id: {resolved_entry_id}")
        entry = MemoryEntry(
            id=resolved_entry_id,
            content=content,
            layer=layer_type,
            importance=float(importance),
            timestamp=time.time(),
            metadata=metadata or {},
            tags=tags or [],
        )
        self.layers[layer_type].add(entry)

        # 同步到知识图谱
        self._knowledge_graph.ingest_memory_entry(
            entry.id, entry.content,
            importance=entry.importance,
            tags=entry.tags,
        )

        # 利用率监控：添加后检查
        self._monitor.check(self.layers[layer_type])

        return self.entry_to_dict(entry)

    def query(
        self,
        query: str,
        layer: str | MemoryLayerType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 10,
        enable_vector: bool = False,
        enable_graph: bool = False,
    ) -> dict[str, Any]:
        """混合查询：关键词 + 语义向量 + 知识图谱

        Args:
            query: 查询字符串
            layer: 限定的记忆层
            tags: 标签过滤
            min_importance: 最低重要性
            limit: 返回数量上限
            enable_vector: 是否启用向量语义搜索
            enable_graph: 是否启用知识图谱搜索
        """
        selected_layer = self.resolve_layer(layer) if layer else None
        layers = [self.layers[selected_layer]] if selected_layer else list(self.layers.values())

        results: list[MemoryEntry] = []
        seen_ids: set[str] = set()

        # 1. 关键词搜索（MemoryQueryEngine）
        engine = MemoryQueryEngine(layers)
        keyword_results = engine.search(
            MemoryQuery(
                query=query,
                layer=selected_layer,
                tags=tags or [],
                min_importance=float(min_importance),
                limit=int(limit),
            )
        )
        for entry in keyword_results:
            if entry.id not in seen_ids:
                results.append(entry)
                seen_ids.add(entry.id)

        # 2. 向量语义搜索（如果启用且有向量后端）
        if enable_vector and query.strip():
            vector_results = self._vector_search(query, limit=limit)
            for entry in vector_results:
                if entry.id not in seen_ids:
                    results.append(entry)
                    seen_ids.add(entry.id)

        # 3. 知识图谱搜索（如果启用）
        if enable_graph and query.strip():
            graph_results = self._graph_search(query, limit=limit)
            for entry in graph_results:
                if entry.id not in seen_ids:
                    results.append(entry)
                    seen_ids.add(entry.id)

        # 按重要性排序
        results.sort(key=lambda e: e.importance, reverse=True)

        return {
            "query": query,
            "layer": self.layer_to_short(selected_layer) if selected_layer else None,
            "results": [self.entry_to_dict(entry) for entry in results[:limit]],
            "total": len(results[:limit]),
            "sources": {
                "keyword": len(keyword_results),
                "vector": len(vector_results) if enable_vector else 0,
                "graph": len(graph_results) if enable_graph else 0,
            },
        }

    def _vector_search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """向量语义搜索"""
        try:
            vs = self.vector_store
            if vs.size() == 0:
                return []
            # 先把查询文本转成向量，再做语义搜索
            query_embedding = self._simple_embed(query, dimension=vs.dimension)
            results = vs.search(query_embedding, top_k=min(limit, vs.size()))
            entries: list[MemoryEntry] = []
            for doc, score in results:
                # 从各层中查找匹配的记忆条目
                for layer_obj in self.layers.values():
                    entry = layer_obj.get(doc.id)
                    if entry is not None:
                        entry.importance = max(entry.importance, score)
                        entries.append(entry)
                        break
            return entries
        except Exception:
            return []

    def _graph_search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """知识图谱搜索"""
        graph_entities = self._knowledge_graph.search(query=query, limit=limit)
        entries: list[MemoryEntry] = []
        for entity in graph_entities:
            # 从实体ID反查记忆条目
            entry_id = entity.name  # entity.name 就是记忆条目ID
            for layer_obj in self.layers.values():
                entry = layer_obj.get(entry_id)
                if entry is not None:
                    entries.append(entry)
                    break
        return entries

    def compress(
        self,
        layer: str | MemoryLayerType | None = None,
        target_ratio: float = 0.5,
    ) -> dict[str, Any]:
        """Compress selected memory layers with the existing compressor."""
        target_layers = [self.resolve_layer(layer)] if layer else list(self.layers.keys())
        before = sum(len(self.layers[layer_type]) for layer_type in target_layers)

        for layer_type in target_layers:
            entries = list(self.layers[layer_type].entries.values())
            compressed = self.compressor.compress(entries, target_ratio=target_ratio)
            self.layers[layer_type].entries = {entry.id: entry for entry in compressed}

        after = sum(len(self.layers[layer_type]) for layer_type in target_layers)
        return {
            "layer": self.layer_to_short(target_layers[0]) if layer else None,
            "target_ratio": target_ratio,
            "before": before,
            "after": after,
            "status": "compressed",
        }

    def remove(self, entry_id: str, layer: str | MemoryLayerType | None = None) -> dict[str, Any]:
        """Remove a memory entry by id, optionally scoped to a layer."""
        target_layers = [self.resolve_layer(layer)] if layer else list(self.layers.keys())
        for layer_type in target_layers:
            if self.layers[layer_type].remove(entry_id):
                return {"removed": True, "layer": self.layer_to_short(layer_type)}
        return {"removed": False, "layer": None}

    def persist(self) -> dict[str, Any]:
        """Persist all memory layers."""
        self.persistence.save_all(
            {layer_type: list(layer.entries.values()) for layer_type, layer in self.layers.items()}
        )
        return {"status": "persisted", "storage_path": str(self.storage_path), **self.stats()}

    def restore(self) -> dict[str, Any]:
        """Restore all memory layers from storage."""
        loaded = self.persistence.load_all()
        for layer_type, entries in loaded.items():
            self.layers[layer_type].entries = {entry.id: entry for entry in entries}
        return {"status": "restored", "storage_path": str(self.storage_path), **self.stats()}

    def clear(self, clear_storage: bool = True) -> dict[str, Any]:
        """Clear in-memory state, and storage by default."""
        for layer in self.layers.values():
            layer.clear()
        if clear_storage:
            self.persistence.clear()
        if self._vector_store is not None:
            self._vector_store = None
        self._knowledge_graph.clear()
        self._monitor.clear_history()
        return {"status": "cleared", **self.stats()}

    # ---- 利用率监控 ----

    def _on_utilization_high(self, snapshot) -> None:
        """利用率超过阈值时的回调：自动触发压缩"""
        layer_type = snapshot.layer_type
        self.layers[layer_type].compress()

    def check_utilization(self) -> dict[str, Any]:
        """检查所有层的利用率"""
        snapshots = self._monitor.check_all(list(self.layers.values()))
        return {
            "snapshots": [
                {
                    "layer": self.layer_to_short(s.layer_type),
                    "utilization": s.utilization,
                    "current_size": s.current_size,
                    "max_size": s.max_size,
                }
                for s in snapshots
            ],
            "threshold": self._monitor.threshold,
        }

    def get_utilization(self) -> dict[str, float]:
        """获取各层利用率（兼容 ContextManager 接口）"""
        return {
            short: len(layer) / max(1, layer.max_size)
            for layer_type, layer in self.layers.items()
            if (short := self.layer_to_short(layer_type)) is not None
        }

    # ---- 知识图谱 ----

    @property
    def knowledge_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self._knowledge_graph

    def graph_query(
        self,
        query: str = "",
        entity_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """查询知识图谱"""
        from .knowledge_graph import EntityType
        et = EntityType(entity_type) if entity_type else None
        entities = self._knowledge_graph.search(query=query, entity_type=et, limit=limit)
        return {
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type.value,
                    "content": e.content[:200],
                    "importance": e.importance,
                    "tags": e.tags,
                }
                for e in entities
            ],
            "graph_stats": self._knowledge_graph.stats(),
        }

    # ---- 跨层操作 ----

    def promote(self, entry_id: str, from_layer: str, to_layer: str) -> dict[str, Any]:
        """手动将条目从一层提升到另一层"""
        from_lt = self.resolve_layer(from_layer)
        to_lt = self.resolve_layer(to_layer)
        entry = self.layers[from_lt].get(entry_id)
        if entry is None:
            return {"promoted": False, "error": f"Entry {entry_id} not found in {from_layer}"}
        self.layers[to_lt].add(entry)
        self.layers[from_lt].remove(entry_id)
        return {
            "promoted": True,
            "from": from_layer,
            "to": to_layer,
            "entry": self.entry_to_dict(entry),
        }

    def demote(self, entry_id: str, from_layer: str, to_layer: str) -> dict[str, Any]:
        """手动将条目从一层降级到另一层"""
        return self.promote(entry_id, from_layer, to_layer)

    # ---- 向量存储 ----

    @property
    def vector_store(self) -> VectorStore:
        """获取向量存储，自动选择最优后端"""
        if self._vector_store is None:
            if detect_chromadb() and self.storage_path.exists():
                try:
                    chroma_dir = str(self.storage_path / "chroma")
                    self._vector_store = VectorStore.use_chromadb(persist_dir=chroma_dir)
                except Exception:
                    self._vector_store = VectorStore()
            else:
                self._vector_store = VectorStore()
        return self._vector_store

    def index_to_vector(
        self, entry_id: str, embedding: list[float] | None = None
    ) -> dict[str, Any]:
        """将记忆条目索引到向量存储"""
        entry = None
        for layer_obj in self.layers.values():
            e = layer_obj.get(entry_id)
            if e is not None:
                entry = e
                break
        if entry is None:
            return {"indexed": False, "error": f"Entry {entry_id} not found"}

        vs = self.vector_store
        if embedding is None:
            # 使用简单的 bag-of-words 作为 fallback embedding
            embedding = self._simple_embed(entry.content, dimension=vs.dimension)
        vs.add(
            VectorDocument(
                id=entry_id,
                content=entry.content[:500],
                embedding=embedding,
                metadata={
                    "content": entry.content[:500],
                    "importance": entry.importance,
                    "tags": ",".join(entry.tags),
                },
            )
        )
        return {"indexed": True, "entry_id": entry_id, "backend": vs.backend_name}

    def _simple_embed(self, text: str, dimension: int = 384) -> list[float]:
        """简单的字符级 embedding（fallback，实际应使用 sentence-transformers）"""
        import hashlib
        # 使用 hash 生成确定性向量
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(dimension):
            byte_val = h[i % len(h)]
            vec.append((byte_val / 255.0) * 2 - 1)  # 归一化到 [-1, 1]
        return vec

    # ---- 统计 ----

    def stats(self) -> dict[str, Any]:
        """Return layer counts, backend information, and graph stats."""
        layers = {
            self.layer_to_short(layer_type): len(layer) for layer_type, layer in self.layers.items()
        }
        result: dict[str, Any] = {
            "layers": layers,
            "total": sum(layers.values()),
            "vector_backend": (
                self._vector_store.backend_name if self._vector_store else "not_initialized"
            ),
            "knowledge_graph": self._knowledge_graph.stats(),
        }
        return result

    # ---- 工具方法 ----

    def resolve_layer(self, layer: str | MemoryLayerType | None) -> MemoryLayerType:
        """Resolve public layer identifiers."""
        if isinstance(layer, MemoryLayerType):
            return layer
        mapping = {
            "l1": MemoryLayerType.L1_CURRENT,
            "l1_current": MemoryLayerType.L1_CURRENT,
            "l2": MemoryLayerType.L2_TASK,
            "l2_task": MemoryLayerType.L2_TASK,
            "l3": MemoryLayerType.L3_PERSISTENT,
            "l3_persistent": MemoryLayerType.L3_PERSISTENT,
        }
        key = str(layer or "l1").lower()
        if key not in mapping:
            raise ValueError(f"Unknown memory layer: {layer}")
        return mapping[key]

    def layer_to_short(self, layer_type: MemoryLayerType | None) -> str | None:
        if layer_type is None:
            return None
        return {
            MemoryLayerType.L1_CURRENT: "l1",
            MemoryLayerType.L2_TASK: "l2",
            MemoryLayerType.L3_PERSISTENT: "l3",
        }[layer_type]

    def entry_to_dict(self, entry: MemoryEntry) -> dict[str, Any]:
        """Serialize a MemoryEntry."""
        return {
            "id": entry.id,
            "content": entry.content,
            "layer": self.layer_to_short(entry.layer),
            "importance": entry.importance,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
            "tags": entry.tags,
        }

    def _new_entry_id(self) -> str:
        return f"mem_{uuid4().hex}"
