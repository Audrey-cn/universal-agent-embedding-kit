"""Context Compressor — 上下文压缩器

实现三级压缩分类（EMBEDDABLE_TARGETS.md 设计目标）：
- 保留（KEEP）：决策、约束、错误、未完成项
- 压缩（COMPRESS）：中间过程、重复讨论、已解决问题
- 丢弃（DISCARD）：调试输出、临时计算、草稿
"""

from __future__ import annotations

from enum import Enum

from .interface import MemoryEntry


class CompressionClass(Enum):
    """压缩分类"""
    KEEP = "keep"         # 保留：完整保留
    COMPRESS = "compress" # 压缩：摘要化
    DISCARD = "discard"   # 丢弃：直接移除


class ContextCompressor:
    """上下文压缩器

    三级分类策略（EMBEDDABLE_TARGETS.md）：
    - KEEP: 决策、约束、错误、未完成项 → 完整保留
    - COMPRESS: 中间过程、重复讨论、已解决问题 → 摘要化
    - DISCARD: 调试输出、临时计算、草稿 → 直接移除
    """

    # ---- KEEP 关键词（完整保留） ----
    KEEP_KEYWORDS = [
        "decision", "decide", "选择", "采用", "决定",
        "constraint", "constrain", "限制", "必须", "不能",
        "error", "bug", "fail", "failure", "错误", "失败",
        "requirement", "specification", "需求", "规格",
        "architecture", "design", "架构", "设计",
        "todo", "pending", "未完成", "待办",
        "security", "安全", "vulnerability", "漏洞",
    ]

    # ---- COMPRESS 关键词（摘要化） ----
    COMPRESS_KEYWORDS = [
        "discuss", "discussion", "讨论",
        "review", "审查", "检查",
        "refactor", "重构",
        "test", "测试", "验证",
        "implement", "实现", "开发",
        "update", "更新", "修改",
        "resolve", "解决", "修复",
    ]

    # ---- DISCARD 关键词（直接丢弃） ----
    DISCARD_KEYWORDS = [
        "debug", "调试",
        "log", "日志",
        "output", "输出",
        "temporary", "临时",
        "draft", "草稿",
        "print", "echo",
        "trace", "追踪",
    ]

    def classify_entry(self, entry: MemoryEntry) -> CompressionClass:
        """对单个条目进行三级分类

        分类规则（优先级从高到低）：
        1. 标签明确标记为 decision/error → KEEP
        2. 内容包含 KEEP 关键词 → KEEP
        3. 内容包含 DISCARD 关键词 → DISCARD
        4. 内容包含 COMPRESS 关键词 → COMPRESS
        5. 默认 → COMPRESS（保守策略）
        """
        content_lower = entry.content.lower()

        # 标签优先
        if any(t in ("decision", "error", "决定", "错误") for t in entry.tags):
            return CompressionClass.KEEP

        # KEEP 关键词匹配
        for kw in self.KEEP_KEYWORDS:
            if kw in content_lower:
                return CompressionClass.KEEP

        # DISCARD 关键词匹配
        for kw in self.DISCARD_KEYWORDS:
            if kw in content_lower:
                return CompressionClass.DISCARD

        # COMPRESS 关键词匹配
        for kw in self.COMPRESS_KEYWORDS:
            if kw in content_lower:
                return CompressionClass.COMPRESS

        # 默认：压缩（保守策略，不丢弃可能重要的信息）
        return CompressionClass.COMPRESS

    def compress(
        self,
        entries: list[MemoryEntry],
        target_ratio: float = 0.5,
        use_decay: bool = False,
    ) -> list[MemoryEntry]:
        """
        三级压缩：保留 → 压缩 → 丢弃。

        策略：
        1. KEEP 条目无条件保留
        2. DISCARD 条目直接移除
        3. COMPRESS 条目按重要性排序，保留高分部分
        4. 如果仍超过目标数量，进一步压缩 COMPRESS 条目

        Args:
            entries: 原始记忆条目
            target_ratio: 目标压缩率（0.0-1.0）
            use_decay: 是否使用衰减后的重要性排序

        Returns:
            压缩后的记忆条目
        """
        if not entries:
            return []

        # 分类
        keep_entries: list[MemoryEntry] = []
        compress_entries: list[MemoryEntry] = []
        discard_entries: list[MemoryEntry] = []

        for entry in entries:
            cls = self.classify_entry(entry)
            if cls == CompressionClass.KEEP:
                keep_entries.append(entry)
            elif cls == CompressionClass.COMPRESS:
                compress_entries.append(entry)
            else:
                discard_entries.append(entry)

        # 计算目标数量
        target_count = max(1, int(len(entries) * target_ratio))

        # KEEP 条目全部保留
        result = list(keep_entries)

        # 如果 KEEP 已经超过目标，压缩 KEEP 条目
        if len(result) >= target_count:
            result = self._rank_and_trim(result, target_count, use_decay)
            return result

        # 剩余空间分配给 COMPRESS 条目
        remaining = target_count - len(result)
        if remaining > 0 and compress_entries:
            # 按重要性排序 COMPRESS 条目
            compressed = self._rank_and_trim(compress_entries, remaining, use_decay)
            # 对 COMPRESS 条目进行摘要化
            result.extend(self._summarize_entries(compressed))

        return result

    def compress_with_report(
        self,
        entries: list[MemoryEntry],
        target_ratio: float = 0.5,
        use_decay: bool = False,
    ) -> tuple[list[MemoryEntry], dict[str, int | float]]:
        """压缩并返回分类统计报告"""
        if not entries:
            return [], {"keep": 0, "compress": 0, "discard": 0}

        keep_count = 0
        compress_count = 0
        discard_count = 0

        for entry in entries:
            cls = self.classify_entry(entry)
            if cls == CompressionClass.KEEP:
                keep_count += 1
            elif cls == CompressionClass.COMPRESS:
                compress_count += 1
            else:
                discard_count += 1

        compressed = self.compress(entries, target_ratio, use_decay)

        return compressed, {
            "keep": keep_count,
            "compress": compress_count,
            "discard": discard_count,
            "before": len(entries),
            "after": len(compressed),
            "ratio": len(compressed) / max(1, len(entries)),
        }

    def _rank_and_trim(
        self,
        entries: list[MemoryEntry],
        limit: int,
        use_decay: bool = False,
    ) -> list[MemoryEntry]:
        """按重要性排序并截断"""
        if use_decay:
            from .decay import compute_decayed_importance
            scored = [
                (compute_decayed_importance(
                    e.importance, e.timestamp, e.last_accessed, e.access_count,
                ), e)
                for e in entries
            ]
        else:
            scored = [(self._calculate_importance(e), e) for e in entries]

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def _summarize_entries(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """对 COMPRESS 条目进行摘要化

        摘要策略：
        - 截断长内容到 200 字符
        - 添加 [compressed] 标记
        """
        summarized = []
        for entry in entries:
            if len(entry.content) > 200:
                compressed = MemoryEntry(
                    id=entry.id,
                    content=entry.content[:200] + "... [compressed]",
                    layer=entry.layer,
                    importance=entry.importance * 0.8,  # 压缩后降低重要性
                    timestamp=entry.timestamp,
                    metadata=entry.metadata,
                    tags=entry.tags + ["compressed"],
                    last_accessed=entry.last_accessed,
                    access_count=entry.access_count,
                )
                summarized.append(compressed)
            else:
                summarized.append(entry)
        return summarized

    def _calculate_importance(self, entry: MemoryEntry) -> float:
        """计算条目重要性（关键词加权）"""
        score = entry.importance
        content_lower = entry.content.lower()

        for keyword in self.KEEP_KEYWORDS:
            if keyword in content_lower:
                score += 0.1
        for keyword in self.DISCARD_KEYWORDS:
            if keyword in content_lower:
                score -= 0.05

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
