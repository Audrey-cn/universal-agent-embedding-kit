"""Context Compressor — 上下文压缩器"""

from __future__ import annotations

from .interface import MemoryEntry


class ContextCompressor:
    """上下文压缩器"""

    # 重要性关键词
    HIGH_IMPORTANCE_KEYWORDS = [
        "decision",
        "constraint",
        "error",
        "failure",
        "bug",
        "requirement",
        "specification",
        "architecture",
        "design",
        "decision",
        "决定",
        "约束",
        "错误",
        "失败",
        "需求",
        "规格",
    ]

    LOW_IMPORTANCE_KEYWORDS = [
        "debug",
        "log",
        "output",
        "temporary",
        "draft",
        "调试",
        "日志",
        "输出",
        "临时",
        "草稿",
    ]

    def compress(self, entries: list[MemoryEntry], target_ratio: float = 0.5) -> list[MemoryEntry]:
        """
        压缩记忆条目。

        Args:
            entries: 原始记忆条目
            target_ratio: 目标压缩率（0.0-1.0）

        Returns:
            压缩后的记忆条目
        """
        if not entries:
            return []

        # 计算目标数量
        target_count = max(1, int(len(entries) * target_ratio))

        # 计算每个条目的重要性分数
        scored_entries = []
        for entry in entries:
            score = self._calculate_importance(entry)
            scored_entries.append((score, entry))

        # 按重要性排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # 保留前 N 个
        return [entry for _, entry in scored_entries[:target_count]]

    def _calculate_importance(self, entry: MemoryEntry) -> float:
        """计算条目重要性"""
        score = entry.importance

        # 关键词加权
        content_lower = entry.content.lower()
        for keyword in self.HIGH_IMPORTANCE_KEYWORDS:
            if keyword in content_lower:
                score += 0.1
        for keyword in self.LOW_IMPORTANCE_KEYWORDS:
            if keyword in content_lower:
                score -= 0.05

        # 标签加权
        if "decision" in entry.tags or "决定" in entry.tags:
            score += 0.2
        if "error" in entry.tags or "错误" in entry.tags:
            score += 0.15

        return min(1.0, max(0.0, score))

    def merge_similar(
        self, entries: list[MemoryEntry], threshold: float = 0.8
    ) -> list[MemoryEntry]:
        """合并相似条目"""
        if len(entries) <= 1:
            return entries

        merged = []
        used = set()

        for i, entry1 in enumerate(entries):
            if i in used:
                continue

            # 查找相似条目
            similar = [entry1]
            for j, entry2 in enumerate(entries[i + 1 :], i + 1):
                if j in used:
                    continue
                if self._similarity(entry1, entry2) >= threshold:
                    similar.append(entry2)
                    used.add(j)

            # 合并相似条目
            if len(similar) > 1:
                merged.append(self._merge_entries(similar))
            else:
                merged.append(entry1)
            used.add(i)

        return merged

    def _similarity(self, entry1: MemoryEntry, entry2: MemoryEntry) -> float:
        """计算两个条目的相似度"""
        # 简单的关键词重叠计算
        words1 = set(entry1.content.lower().split())
        words2 = set(entry2.content.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _merge_entries(self, entries: list[MemoryEntry]) -> MemoryEntry:
        """合并多个条目"""
        # 使用最重要的条目作为基础
        base = max(entries, key=lambda e: e.importance)

        # 合并内容
        contents = [e.content for e in entries]
        merged_content = "\n---\n".join(contents)

        # 合并标签
        tags = list(set(tag for e in entries for tag in e.tags))

        return MemoryEntry(
            id=base.id,
            content=merged_content,
            layer=base.layer,
            importance=max(e.importance for e in entries),
            timestamp=max(e.timestamp for e in entries),
            metadata=base.metadata,
            tags=tags,
        )

    def extract_summary(self, entries: list[MemoryEntry], max_length: int = 500) -> str:
        """提取摘要"""
        if not entries:
            return ""

        # 按重要性排序
        sorted_entries = sorted(entries, key=lambda e: e.importance, reverse=True)

        summary_parts = []
        current_length = 0

        for entry in sorted_entries:
            # 截断内容
            content = entry.content[:200]
            if current_length + len(content) > max_length:
                break
            summary_parts.append(content)
            current_length += len(content)

        return "\n---\n".join(summary_parts)
