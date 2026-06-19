"""Memory Query Engine — 记忆查询引擎"""

from __future__ import annotations

from .interface import MemoryEntry, MemoryLayer, MemoryLayerType, MemoryQuery


class MemoryQueryEngine:
    """记忆查询引擎"""

    def __init__(self, layers: list[MemoryLayer]):
        self.layers = layers

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索记忆"""
        results: list[MemoryEntry] = []

        for layer in self.layers:
            if query.layer and layer.layer_type != query.layer:
                continue
            layer_results = layer.search(query)
            results.extend(layer_results)

        # 去重
        seen_ids: set[str] = set()
        unique_results: list[MemoryEntry] = []
        for entry in results:
            if entry.id not in seen_ids:
                seen_ids.add(entry.id)
                unique_results.append(entry)

        # 按重要性排序
        unique_results.sort(key=lambda e: e.importance, reverse=True)

        return unique_results[: query.limit]

    def search_by_keyword(self, keyword: str, limit: int = 10) -> list[MemoryEntry]:
        """按关键词搜索"""
        query = MemoryQuery(query=keyword, limit=limit)
        return self.search(query)

    def search_by_tags(self, tags: list[str], limit: int = 10) -> list[MemoryEntry]:
        """按标签搜索"""
        query = MemoryQuery(query="", tags=tags, limit=limit)
        return self.search(query)

    def search_by_importance(self, min_importance: float, limit: int = 10) -> list[MemoryEntry]:
        """按重要性搜索"""
        query = MemoryQuery(query="", min_importance=min_importance, limit=limit)
        return self.search(query)

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """获取最近的记忆"""
        all_entries: list[MemoryEntry] = []
        for layer in self.layers:
            all_entries.extend(layer.entries.values())

        # 按时间排序
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        return all_entries[:limit]

    def get_by_layer(self, layer_type: MemoryLayerType, limit: int = 10) -> list[MemoryEntry]:
        """按层获取记忆"""
        for layer in self.layers:
            if layer.layer_type == layer_type:
                entries = list(layer.entries.values())
                entries.sort(key=lambda e: e.importance, reverse=True)
                return entries[:limit]
        return []

    def get_statistics(self) -> dict[str, int]:
        """获取统计信息"""
        stats: dict[str, int] = {}
        for layer in self.layers:
            stats[layer.layer_type.value] = len(layer)
        stats["total"] = sum(stats.values())
        return stats
