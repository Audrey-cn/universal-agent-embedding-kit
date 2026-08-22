"""Memory Layers — 记忆层实现

实现 RESEARCH_PROPOSAL.md 命题1 的分层记忆系统：
- L1（当前对话）→ L2（当前任务）→ L3（跨会话）
- 自适应压缩：根据任务类型和信息密度动态决定压缩阈值
- 跨层 promotion/demotion：高重要性条目自动提升到更持久层
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .interface import MemoryEntry, MemoryLayer, MemoryLayerType, MemoryQuery

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


class L1CurrentContext(MemoryLayer):
    """L1: 当前对话上下文

    自适应压缩阈值：默认 40%（设计文档目标），
    可根据信息密度（独特内容占比）动态调整。
    """

    # 自适应压缩参数
    DEFAULT_COMPRESSION_THRESHOLD = 0.4  # 40% 利用率触发压缩（设计文档目标）
    MIN_COMPRESSION_THRESHOLD = 0.3
    MAX_COMPRESSION_THRESHOLD = 0.6

    def __init__(self, max_size: int = 100):
        super().__init__(MemoryLayerType.L1_CURRENT, max_size)
        self._compression_threshold = self.DEFAULT_COMPRESSION_THRESHOLD
        self._promotion_target: L2TaskContext | None = None
        self._knowledge_graph: KnowledgeGraph | None = None

    def set_promotion_target(self, target: L2TaskContext) -> None:
        """设置 promotion 目标层"""
        self._promotion_target = target

    def set_knowledge_graph(self, kg: KnowledgeGraph) -> None:
        """设置知识图谱引用"""
        self._knowledge_graph = kg

    def _evict(self) -> None:
        """淘汰最旧的条目"""
        if not self.entries:
            return
        oldest_id = min(self.entries.keys(), key=lambda k: self.entries[k].timestamp)
        del self.entries[oldest_id]

    def compress(self) -> None:
        """自适应压缩：根据信息密度动态调整阈值

        设计目标（EMBEDDABLE_TARGETS.md）：
        "不是固定阈值压缩，而是根据任务类型和信息密度动态决定什么保留、什么丢弃"
        """
        utilization = len(self.entries) / max(1, self.max_size)
        if utilization < self._compression_threshold:
            return

        # 计算信息密度：独特内容占比越高，信息密度越大
        unique_ratio = self._calculate_information_density()
        # 信息密度高 → 提高阈值（更多保留），信息密度低 → 降低阈值（更多压缩）
        self._compression_threshold = (
            self.DEFAULT_COMPRESSION_THRESHOLD + (unique_ratio - 0.5) * 0.2
        )
        self._compression_threshold = max(
            self.MIN_COMPRESSION_THRESHOLD,
            min(self.MAX_COMPRESSION_THRESHOLD, self._compression_threshold),
        )

        # 按重要性排序
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, int(len(sorted_entries) * (1.0 - self._compression_threshold)))
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        # 被淘汰的高重要性条目：promote 到 L2
        for entry in sorted_entries[keep_count:]:
            if entry.importance > 0.7 and self._promotion_target is not None:
                self._promotion_target.add(entry)
                # 同时添加到知识图谱
                if self._knowledge_graph is not None:
                    self._knowledge_graph.ingest_memory_entry(
                        entry.id,
                        entry.content,
                        importance=entry.importance,
                        tags=entry.tags,
                    )

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def _calculate_information_density(self) -> float:
        """计算信息密度：独特内容占比"""
        if len(self.entries) <= 1:
            return 0.5
        all_words: set[str] = set()
        total_words = 0
        for entry in self.entries.values():
            words = entry.content.lower().split()
            all_words.update(words)
            total_words += len(words)
        if total_words == 0:
            return 0.5
        return len(all_words) / total_words

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：关键词匹配；空查询或 '*' 返回全部"""
        results = []
        query_lower = query.query.strip().lower()
        match_all = not query_lower or query_lower == "*"

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if match_all or query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]


class L2TaskContext(MemoryLayer):
    """L2: 当前任务上下文

    支持 promotion 到 L3（高重要性、持久化条目）和
    demotion 回 L1（低重要性、临时条目）。
    """

    def __init__(self, max_size: int = 500):
        super().__init__(MemoryLayerType.L2_TASK, max_size)
        self._promotion_target: L3PersistentContext | None = None
        self._demotion_target: L1CurrentContext | None = None

    def set_promotion_target(self, target: L3PersistentContext) -> None:
        """设置 promotion 目标层（L3）"""
        self._promotion_target = target

    def set_demotion_target(self, target: L1CurrentContext) -> None:
        """设置 demotion 目标层（L1）"""
        self._demotion_target = target

    def _evict(self) -> None:
        """淘汰：移除最旧且低重要性的条目"""
        if not self.entries:
            return
        oldest_id = min(self.entries.keys(), key=lambda k: self.entries[k].timestamp)
        # 淘汰前尝试 promotion
        entry = self.entries[oldest_id]
        if entry.importance > 0.8 and self._promotion_target is not None:
            self._promotion_target.add(entry)
        del self.entries[oldest_id]

    def compress(self) -> None:
        """压缩：移除低重要性条目，高重要性条目 promote 到 L3"""
        if len(self.entries) <= self.max_size * 0.5:
            return

        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, len(sorted_entries) // 2)
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        # 被淘汰的高重要性条目：promote 到 L3
        for entry in sorted_entries[keep_count:]:
            if entry.importance > 0.8 and self._promotion_target is not None:
                self._promotion_target.add(entry)

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def promote_to_l3(self, entry_id: str) -> bool:
        """手动将条目提升到 L3"""
        entry = self.entries.get(entry_id)
        if entry is None or self._promotion_target is None:
            return False
        self._promotion_target.add(entry)
        del self.entries[entry_id]
        return True

    def demote_to_l1(self, entry_id: str) -> bool:
        """手动将条目降级到 L1"""
        entry = self.entries.get(entry_id)
        if entry is None or self._demotion_target is None:
            return False
        self._demotion_target.add(entry)
        del self.entries[entry_id]
        return True

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：关键词 + 标签匹配；空查询或 '*' 返回全部"""
        results = []
        query_lower = query.query.strip().lower()
        match_all = not query_lower or query_lower == "*"

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if match_all or query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]


class L3PersistentContext(MemoryLayer):
    """L3: 跨会话持久化上下文

    支持 demotion 回 L2（不再活跃的持久化条目）。
    """

    def __init__(self, max_size: int = 5000):
        super().__init__(MemoryLayerType.L3_PERSISTENT, max_size)
        self._demotion_target: L2TaskContext | None = None

    def set_demotion_target(self, target: L2TaskContext) -> None:
        """设置 demotion 目标层（L2）"""
        self._demotion_target = target

    def _evict(self) -> None:
        """淘汰：移除最旧且低重要性的条目"""
        if not self.entries:
            return
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (e.importance, e.timestamp),
        )
        if sorted_entries:
            del self.entries[sorted_entries[0].id]

    def compress(self) -> None:
        """压缩：保留高重要性条目，低重要性条目 demote 到 L2"""
        if len(self.entries) <= self.max_size * 0.8:
            return

        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, int(len(sorted_entries) * 0.8))
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        # 被淘汰的低重要性条目：demote 到 L2
        for entry in sorted_entries[keep_count:]:
            if self._demotion_target is not None:
                self._demotion_target.add(entry)

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def demote_to_l2(self, entry_id: str) -> bool:
        """手动将条目降级到 L2"""
        entry = self.entries.get(entry_id)
        if entry is None or self._demotion_target is None:
            return False
        self._demotion_target.add(entry)
        del self.entries[entry_id]
        return True

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：全内容搜索；空查询或 '*' 返回全部"""
        results = []
        query_lower = query.query.strip().lower()
        match_all = not query_lower or query_lower == "*"

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if match_all or query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]
