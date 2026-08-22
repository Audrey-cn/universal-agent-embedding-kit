"""Token Budget Manager — Token预算管理

为上下文窗口的不同组件分配token预算，超配额时自动触发压缩。

RESEARCH_PROPOSAL.md 命题1（P0）+ 命题3（P1）：
- 上下文超过~40%利用率后性能急剧下降，需要精确控制
- 不同组件（系统提示词、工具定义、对话历史、记忆）各有预算

预算池：
- system_prompt: 系统提示词
- tool_definitions: 工具定义
- conversation_history: 对话历史
- memory: 记忆/上下文
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class BudgetPool(Enum):
    """预算池类型"""

    SYSTEM_PROMPT = "system_prompt"
    TOOL_DEFINITIONS = "tool_definitions"
    CONVERSATION_HISTORY = "conversation_history"
    MEMORY = "memory"


# 默认预算分配（占总token窗口的比例）
DEFAULT_BUDGET_ALLOCATION: dict[BudgetPool, float] = {
    BudgetPool.SYSTEM_PROMPT: 0.15,  # 15%
    BudgetPool.TOOL_DEFINITIONS: 0.10,  # 10%
    BudgetPool.CONVERSATION_HISTORY: 0.50,  # 50%
    BudgetPool.MEMORY: 0.25,  # 25%
}


@dataclass
class PoolStatus:
    """预算池状态"""

    pool: BudgetPool
    allocated: int  # 分配的token数
    used: int  # 已使用的token数
    utilization: float  # 使用率 (0.0-1.0)
    over_budget: bool  # 是否超预算

    def __str__(self) -> str:
        status = "OVER" if self.over_budget else "OK"
        return f"[{self.pool.value}] {self.used}/{self.allocated} ({self.utilization:.0%}) {status}"


@dataclass
class BudgetSnapshot:
    """预算快照"""

    timestamp: float
    total_tokens: int
    pools: dict[BudgetPool, PoolStatus]
    overall_utilization: float
    over_budget_pools: list[BudgetPool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_tokens": self.total_tokens,
            "pools": {
                p.value: {
                    "allocated": s.allocated,
                    "used": s.used,
                    "utilization": s.utilization,
                    "over_budget": s.over_budget,
                }
                for p, s in self.pools.items()
            },
            "overall_utilization": self.overall_utilization,
            "over_budget_pools": [p.value for p in self.over_budget_pools],
        }


class TokenBudget:
    """Token预算管理器

    特性：
    1. 多池分配：为不同组件分配独立的token预算
    2. 超配额检测：实时监控各池使用率
    3. 动态调整：支持运行时调整预算分配
    4. 自动压缩触发：超配额时通知回调
    """

    def __init__(
        self,
        total_tokens: int = 100000,
        allocation: dict[BudgetPool, float] | None = None,
        over_budget_threshold: float = 0.8,
    ):
        self.total_tokens = total_tokens
        self.allocation = allocation or dict(DEFAULT_BUDGET_ALLOCATION)
        self.over_budget_threshold = over_budget_threshold

        # 各池已使用token计数
        self._usage: dict[BudgetPool, int] = {pool: 0 for pool in BudgetPool}

        # 快照历史
        self._snapshots: list[BudgetSnapshot] = []

        # 超配额回调
        self._callbacks: list[Callable[[BudgetPool, PoolStatus], None]] = []

    @property
    def allocated(self) -> dict[BudgetPool, int]:
        """各池分配的token数"""
        return {pool: int(self.total_tokens * ratio) for pool, ratio in self.allocation.items()}

    def register_callback(self, callback: Callable[[BudgetPool, PoolStatus], None]) -> None:
        """注册超配额回调"""
        self._callbacks.append(callback)

    def track_usage(self, pool: BudgetPool, tokens: int) -> None:
        """记录token使用量

        Args:
            pool: 预算池
            tokens: 使用的token数
        """
        if tokens <= 0:
            return
        self._usage[pool] += tokens

        # 检查是否超配额
        status = self._pool_status(pool)
        if status.over_budget:
            self._notify_callbacks(pool, status)

    def set_usage(self, pool: BudgetPool, tokens: int) -> None:
        """直接设置token使用量（替换而非累加）"""
        self._usage[pool] = max(0, tokens)

        status = self._pool_status(pool)
        if status.over_budget:
            self._notify_callbacks(pool, status)

    def reset_pool(self, pool: BudgetPool) -> None:
        """重置单个池的使用量"""
        self._usage[pool] = 0

    def reset_all(self) -> None:
        """重置所有池"""
        for pool in BudgetPool:
            self._usage[pool] = 0

    def is_over_budget(self, pool: BudgetPool | None = None) -> bool:
        """检查是否超预算

        Args:
            pool: 指定池，None 表示检查任一池
        """
        if pool is not None:
            return self._pool_status(pool).over_budget
        return any(self._pool_status(p).over_budget for p in BudgetPool)

    def get_utilization(self, pool: BudgetPool | None = None) -> float:
        """获取利用率"""
        if pool is not None:
            return self._pool_status(pool).utilization
        allocated = self.allocated
        total_allocated = sum(allocated.values())
        total_used = sum(self._usage.values())
        return total_used / max(1, total_allocated)

    def get_status(self) -> BudgetSnapshot:
        """获取完整预算状态"""
        pools = {pool: self._pool_status(pool) for pool in BudgetPool}
        over_budget = [p for p, s in pools.items() if s.over_budget]

        snapshot = BudgetSnapshot(
            timestamp=time.time(),
            total_tokens=self.total_tokens,
            pools=pools,
            overall_utilization=self.get_utilization(),
            over_budget_pools=over_budget,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def adjust_allocation(self, pool: BudgetPool, new_ratio: float) -> None:
        """动态调整预算分配

        Args:
            pool: 要调整的池
            new_ratio: 新的分配比例
        """
        if new_ratio < 0 or new_ratio > 1:
            raise ValueError(f"Allocation ratio must be between 0 and 1, got {new_ratio}")

        # 调整目标池，其他池按比例缩放
        old_ratio = self.allocation.get(pool, 0)
        delta = new_ratio - old_ratio

        if delta == 0:
            return

        # 从其他池中按比例扣除
        other_pools = [p for p in BudgetPool if p != pool]
        other_total = sum(self.allocation.get(p, 0) for p in other_pools)

        if other_total <= 0 and delta > 0:
            raise ValueError("Cannot increase allocation: no budget available from other pools")

        self.allocation[pool] = new_ratio

        if other_total > 0:
            for p in other_pools:
                current = self.allocation.get(p, 0)
                self.allocation[p] = max(0.01, current - delta * (current / other_total))

        # 归一化确保总和为1
        total = sum(self.allocation.values())
        if total > 0:
            for p in self.allocation:
                self.allocation[p] /= total

    def snapshot(self) -> BudgetSnapshot:
        """创建快照（不记录历史）"""
        return self.get_status()

    def get_history(self, limit: int = 20) -> list[BudgetSnapshot]:
        """获取历史快照"""
        return self._snapshots[-limit:]

    def clear_history(self) -> None:
        """清除历史"""
        self._snapshots.clear()

    def _pool_status(self, pool: BudgetPool) -> PoolStatus:
        """计算单个池的状态"""
        allocated = self.allocated.get(pool, 0)
        used = self._usage.get(pool, 0)
        utilization = used / max(1, allocated)
        over_budget = utilization >= self.over_budget_threshold

        return PoolStatus(
            pool=pool,
            allocated=allocated,
            used=used,
            utilization=utilization,
            over_budget=over_budget,
        )

    def _notify_callbacks(self, pool: BudgetPool, status: PoolStatus) -> None:
        """通知超配额回调"""
        for callback in self._callbacks:
            try:
                callback(pool, status)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Token估算工具
# --------------------------------------------------------------------------- #


def estimate_tokens(text: str) -> int:
    """粗略估算文本的token数

    使用简单的启发式方法：英文约 1 token/4 字符，中文约 1 token/1.5 字符。
    对于精确计数，应使用模型特定的 tokenizer。
    """
    if not text:
        return 0

    # 粗略估算
    total_chars = len(text)

    # 统计中文字符
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f")

    # 中文约 1 token/1.5 字符，英文约 1 token/4 字符
    cjk_tokens = cjk_count / 1.5
    other_tokens = (total_chars - cjk_count) / 4

    return max(1, int(cjk_tokens + other_tokens))


def estimate_memory_tokens(entries: list[Any]) -> int:
    """估算记忆条目的总token数"""
    total = 0
    for entry in entries:
        content = getattr(entry, "content", str(entry))
        total += estimate_tokens(content)
    return total
