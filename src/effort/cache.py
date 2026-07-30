"""Effort Cache — Effort 分类器缓存复用与反馈学习

RESEARCH_PROPOSAL.md 命题3（P1）：
"缓存复用：相似任务的中间结果可以跨代理复用"
"预测性调度：在任务开始前预测其复杂度和所需 Effort 级别"

实现：
- 基于任务指纹的缓存：对相似任务复用分类结果
- 反馈学习：根据实际执行结果调整后续分类
- LRU 淘汰策略：控制缓存大小
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from .interface import EffortLevel, EffortResult


@dataclass
class CacheEntry:
    """缓存条目"""
    fingerprint: str
    result: EffortResult
    task_description: str
    hit_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def access(self) -> None:
        """记录访问"""
        self.hit_count += 1
        self.last_accessed = time.time()


@dataclass
class FeedbackRecord:
    """反馈记录"""
    task_description: str
    predicted_level: EffortLevel
    actual_difficulty: float  # 0.0-1.0，实际难度
    was_accurate: bool
    timestamp: float = field(default_factory=time.time)


class EffortCache:
    """Effort 分类器缓存

    特性：
    1. 任务指纹匹配：基于任务描述的语义哈希
    2. 相似度阈值：仅当相似度 >= 阈值时复用
    3. LRU 淘汰：超过 max_size 时淘汰最久未使用的条目
    4. 反馈学习：根据实际执行结果校准分类
    """

    def __init__(self, max_size: int = 100, similarity_threshold: float = 0.8):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._feedback: list[FeedbackRecord] = []
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold

        # 反馈学习的校准参数
        self._level_bias: dict[EffortLevel, float] = {
            EffortLevel.LOW: 0.0,
            EffortLevel.MEDIUM: 0.0,
            EffortLevel.HIGH: 0.0,
            EffortLevel.XHIGH: 0.0,
        }

    def get(self, task_description: str) -> EffortResult | None:
        """查找缓存：基于任务描述指纹匹配"""
        fingerprint = self._compute_fingerprint(task_description)

        # 精确匹配
        if fingerprint in self._cache:
            entry = self._cache[fingerprint]
            entry.access()
            self._cache.move_to_end(fingerprint)
            return entry.result

        # 模糊匹配：基于关键词交集
        best_match = self._fuzzy_match(task_description)
        if best_match is not None:
            entry = self._cache[best_match.fingerprint]
            entry.access()
            self._cache.move_to_end(best_match.fingerprint)
            return entry.result

        return None

    def put(self, task_description: str, result: EffortResult) -> None:
        """存入缓存"""
        if self.max_size <= 0:
            return
        # 输入验证：限制任务描述长度
        if len(task_description) > 10000:
            return  # 拒绝过长的输入
        fingerprint = self._compute_fingerprint(task_description)

        if fingerprint in self._cache:
            self._cache.move_to_end(fingerprint)
            return

        # LRU 淘汰
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[fingerprint] = CacheEntry(
            fingerprint=fingerprint,
            result=result,
            task_description=task_description,
        )

    def record_feedback(
        self,
        task_description: str,
        predicted_level: EffortLevel,
        actual_difficulty: float,
        was_accurate: bool,
    ) -> None:
        """记录反馈用于学习

        Args:
            task_description: 任务描述
            predicted_level: 预测的 Effort 级别
            actual_difficulty: 实际难度（0.0-1.0）
            was_accurate: 预测是否准确
        """
        self._feedback.append(FeedbackRecord(
            task_description=task_description,
            predicted_level=predicted_level,
            actual_difficulty=actual_difficulty,
            was_accurate=was_accurate,
        ))

        # 限制反馈历史大小
        if len(self._feedback) > 500:
            self._feedback = self._feedback[-500:]

        # 更新校准偏差
        if not was_accurate:
            levels = [EffortLevel.LOW, EffortLevel.MEDIUM, EffortLevel.HIGH, EffortLevel.XHIGH]
            try:
                idx = levels.index(predicted_level)
                # 如果实际难度更高，增加偏差（向上调整）
                target_idx = min(3, max(0, int(actual_difficulty * 4)))
                if target_idx > idx:
                    self._level_bias[predicted_level] += 0.05
                elif target_idx < idx:
                    self._level_bias[predicted_level] -= 0.05
            except ValueError:
                pass

    def get_calibrated_level(self, original_level: EffortLevel) -> EffortLevel:
        """根据反馈学习校准 Effort 级别"""
        bias = self._level_bias.get(original_level, 0.0)
        levels = [EffortLevel.LOW, EffortLevel.MEDIUM, EffortLevel.HIGH, EffortLevel.XHIGH]
        try:
            idx = levels.index(original_level)
            adjusted = max(0, min(3, idx + round(bias * 2)))
            return levels[adjusted]
        except ValueError:
            return original_level

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total_feedback = len(self._feedback)
        accurate = sum(1 for f in self._feedback if f.was_accurate)
        accuracy = accurate / max(1, total_feedback)

        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "hit_count": sum(e.hit_count for e in self._cache.values()),
            "feedback_count": total_feedback,
            "feedback_accuracy": accuracy,
            "level_bias": {k.value: v for k, v in self._level_bias.items()},
            "similarity_threshold": self.similarity_threshold,
        }

    def clear(self) -> None:
        """清空缓存和反馈"""
        self._cache.clear()
        self._feedback.clear()
        for key in self._level_bias:
            self._level_bias[key] = 0.0

    def _compute_fingerprint(self, task_description: str) -> str:
        """计算任务指纹"""
        # 标准化：去空格、小写
        normalized = " ".join(task_description.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _fuzzy_match(self, task_description: str) -> CacheEntry | None:
        """模糊匹配：基于关键词 Jaccard 相似度"""
        query_words = set(task_description.lower().split())
        if not query_words:
            return None

        best_entry: CacheEntry | None = None
        best_similarity = 0.0

        for entry in self._cache.values():
            entry_words = set(entry.task_description.lower().split())
            if not entry_words:
                continue

            # Jaccard 相似度
            intersection = query_words & entry_words
            union = query_words | entry_words
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_entry = entry

        return best_entry


# --------------------------------------------------------------------------- #
# 带缓存的 classify 函数
# --------------------------------------------------------------------------- #

# 全局缓存实例
_global_cache: EffortCache | None = None


def get_global_cache() -> EffortCache:
    """获取全局 Effort 缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = EffortCache()
    return _global_cache


def classify_with_cache(
    task_description: str,
    file_count: int | None = None,
    dependency_depth: int | None = None,
    ambiguity: float | None = None,
    reversibility: float | None = None,
    language: str = "en",
    use_cache: bool = True,
) -> EffortResult:
    """带缓存的 Effort 分类

    Args:
        task_description: 任务描述
        file_count: 涉及文件数
        dependency_depth: 依赖深度
        ambiguity: 模糊度
        reversibility: 可逆度
        language: 语言
        use_cache: 是否使用缓存

    Returns:
        EffortResult: 分类结果
    """
    from .interface import classify

    cache = get_global_cache()

    if use_cache:
        cached = cache.get(task_description)
        if cached is not None:
            # 应用反馈校准
            calibrated_level = cache.get_calibrated_level(cached.level)
            if calibrated_level != cached.level:
                # 返回校准后的结果
                return EffortResult(
                    level=calibrated_level,
                    confidence=cached.confidence * 0.9,  # 校准后降低置信度
                    dispatch_phrase=cached.dispatch_phrase,
                    verification_depth=cached.verification_depth,
                    reasoning=f"{cached.reasoning} (calibrated from {cached.level.value})",
                    metrics=cached.metrics,
                )
            return cached

    # 缓存未命中，执行分类
    result = classify(
        task_description=task_description,
        file_count=file_count,
        dependency_depth=dependency_depth,
        ambiguity=ambiguity,
        reversibility=reversibility,
        language=language,
    )

    if use_cache:
        cache.put(task_description, result)

    return result


def record_classification_feedback(
    task_description: str,
    predicted_level: EffortLevel,
    actual_difficulty: float,
    was_accurate: bool,
) -> None:
    """记录分类反馈"""
    cache = get_global_cache()
    cache.record_feedback(task_description, predicted_level, actual_difficulty, was_accurate)
