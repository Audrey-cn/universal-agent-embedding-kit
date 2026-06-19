"""Memory Layers — 记忆层实现"""

from __future__ import annotations

from .interface import MemoryEntry, MemoryLayer, MemoryLayerType, MemoryQuery


class L1CurrentContext(MemoryLayer):
    """L1: 当前对话上下文"""

    def __init__(self, max_size: int = 100):
        super().__init__(MemoryLayerType.L1_CURRENT, max_size)

    def _evict(self) -> None:
        """淘汰最旧的条目"""
        if not self.entries:
            return
        oldest_id = min(self.entries.keys(), key=lambda k: self.entries[k].timestamp)
        del self.entries[oldest_id]

    def compress(self) -> None:
        """压缩：移除低重要性条目"""
        if len(self.entries) <= self.max_size * 0.5:
            return

        # 按重要性排序，保留前 50%
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, len(sorted_entries) // 2)
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：关键词匹配"""
        results = []
        query_lower = query.query.lower()

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if query_lower in entry.content.lower():
                results.append(entry)

        # 按重要性排序
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]


class L2TaskContext(MemoryLayer):
    """L2: 当前任务上下文"""

    def __init__(self, max_size: int = 500):
        super().__init__(MemoryLayerType.L2_TASK, max_size)

    def _evict(self) -> None:
        """淘汰：移除已完成任务的条目"""
        if not self.entries:
            return
        # 淘汰最旧的条目
        oldest_id = min(self.entries.keys(), key=lambda k: self.entries[k].timestamp)
        del self.entries[oldest_id]

    def compress(self) -> None:
        """压缩：合并相似条目，移除重复"""
        if len(self.entries) <= self.max_size * 0.5:
            return

        # 简单压缩：移除低重要性条目
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, len(sorted_entries) // 2)
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：关键词 + 标签匹配"""
        results = []
        query_lower = query.query.lower()

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]


class L3PersistentContext(MemoryLayer):
    """L3: 跨会话持久化上下文"""

    def __init__(self, max_size: int = 5000):
        super().__init__(MemoryLayerType.L3_PERSISTENT, max_size)

    def _evict(self) -> None:
        """淘汰：移除最旧且低重要性的条目"""
        if not self.entries:
            return
        # 优先淘汰低重要性条目
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (e.importance, e.timestamp),
        )
        if sorted_entries:
            del self.entries[sorted_entries[0].id]

    def compress(self) -> None:
        """压缩：保留高重要性条目"""
        if len(self.entries) <= self.max_size * 0.8:
            return

        # 保留前 80% 的高重要性条目
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.importance,
            reverse=True,
        )
        keep_count = max(1, int(len(sorted_entries) * 0.8))
        keep_ids = {e.id for e in sorted_entries[:keep_count]}

        self.entries = {k: v for k, v in self.entries.items() if k in keep_ids}

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索：全内容搜索"""
        results = []
        query_lower = query.query.lower()

        for entry in self.entries.values():
            if query.min_importance > 0 and entry.importance < query.min_importance:
                continue
            if query.tags and not any(t in entry.tags for t in query.tags):
                continue
            if query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[: query.limit]
