"""Memory Decay — 记忆衰减机制

基于艾宾浩斯遗忘曲线实现记忆的时间衰减：
- score = importance * e^(-λ * days_since_access)
- 被频繁访问的记忆自动强化（access_count 加权）
- 支持可配置的衰减速率和半衰期

RESEARCH_PROPOSAL.md 命题1（P0）：
"不是固定阈值压缩，而是根据任务类型和信息密度动态决定什么保留、什么丢弃"
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass
class DecayConfig:
    """衰减配置"""

    # 衰减速率 λ（越大衰减越快，默认 0.05 对应约 14 天半衰期）
    decay_rate: float = 0.05
    # 半衰期（天），设置后自动计算 decay_rate
    half_life_days: float | None = None
    # 访问加权因子：每次访问增加的衰减抗性
    access_boost: float = 0.1
    # 最大访问加权上限
    max_access_boost: float = 0.5
    # 最小衰减分数（记忆不会完全消失）
    floor: float = 0.01

    def __post_init__(self):
        if self.half_life_days is not None and self.half_life_days > 0:
            # λ = ln(2) / half_life
            self.decay_rate = math.log(2) / self.half_life_days


def ebbinghaus_decay(
    importance: float,
    timestamp: float,
    last_accessed: float | None = None,
    access_count: int = 0,
    config: DecayConfig | None = None,
    now: float | None = None,
) -> float:
    """艾宾浩斯遗忘曲线衰减计算

    Args:
        importance: 初始重要性（0.0-1.0）
        timestamp: 创建时间戳
        last_accessed: 最后访问时间戳（None 表示从未访问）
        access_count: 访问次数
        config: 衰减配置
        now: 当前时间戳（默认当前时间）

    Returns:
        衰减后的分数（0.0-1.0）
    """
    if config is None:
        config = DecayConfig()
    if now is None:
        now = time.time()

    # 计算自上次访问以来的天数
    reference_time = last_accessed if last_accessed is not None else timestamp
    days_since_access = (now - reference_time) / 86400.0

    # 艾宾浩斯衰减：e^(-λ * days)
    decay_factor = math.exp(-config.decay_rate * days_since_access)

    # 访问强化：每次访问增加抗衰减能力
    access_resistance = min(
        config.access_boost * access_count,
        config.max_access_boost,
    )

    # 最终分数 = 重要性 × 衰减因子 + 访问强化
    score = importance * decay_factor + access_resistance

    return max(config.floor, min(1.0, score))


def compute_decayed_importance(
    importance: float,
    timestamp: float,
    last_accessed: float | None = None,
    access_count: int = 0,
    config: DecayConfig | None = None,
) -> float:
    """便捷函数：计算衰减后的重要性

    用于排序和淘汰决策，返回值可直接替换原始 importance。
    """
    return ebbinghaus_decay(
        importance=importance,
        timestamp=timestamp,
        last_accessed=last_accessed,
        access_count=access_count,
        config=config,
    )


def should_evict(
    importance: float,
    timestamp: float,
    last_accessed: float | None = None,
    access_count: int = 0,
    eviction_threshold: float = 0.1,
    max_age_days: float = 30.0,
    config: DecayConfig | None = None,
) -> bool:
    """判断记忆条目是否应该被淘汰

    Args:
        importance: 初始重要性
        timestamp: 创建时间戳
        last_accessed: 最后访问时间戳
        access_count: 访问次数
        eviction_threshold: 淘汰阈值（衰减后分数低于此值则淘汰）
        max_age_days: 最大保留天数（超过此天数强制淘汰）
        config: 衰减配置

    Returns:
        True 表示应该淘汰
    """
    now = time.time()
    days_since_creation = (now - timestamp) / 86400.0

    # 检查最大年龄
    if days_since_creation > max_age_days:
        return True

    # 检查衰减分数
    score = ebbinghaus_decay(
        importance=importance,
        timestamp=timestamp,
        last_accessed=last_accessed,
        access_count=access_count,
        config=config,
        now=now,
    )

    return score < eviction_threshold


# 预设衰减配置
DEFAULT_DECAY_CONFIG = DecayConfig()
FAST_DECAY_CONFIG = DecayConfig(half_life_days=3.0)   # 3天半衰期（快速遗忘）
SLOW_DECAY_CONFIG = DecayConfig(half_life_days=30.0)  # 30天半衰期（长期记忆）
