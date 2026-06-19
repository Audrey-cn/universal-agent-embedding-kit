"""Memory Interface — 记忆接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryLayerType(Enum):
    """记忆层类型"""

    L1_CURRENT = "l1_current"  # 当前对话
    L2_TASK = "l2_task"  # 当前任务
    L3_PERSISTENT = "l3_persistent"  # 跨会话持久化


@dataclass
class MemoryEntry:
    """记忆条目"""

    id: str
    content: str
    layer: MemoryLayerType
    importance: float = 0.5  # 0.0-1.0
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            raise ValueError("Memory entry id cannot be empty")


@dataclass
class MemoryQuery:
    """记忆查询"""

    query: str
    layer: MemoryLayerType | None = None
    tags: list[str] = field(default_factory=list)
    limit: int = 10
    min_importance: float = 0.0


class MemoryLayer(ABC):
    """记忆层基类"""

    def __init__(self, layer_type: MemoryLayerType, max_size: int = 1000):
        self.layer_type = layer_type
        self.max_size = max_size
        self.entries: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> None:
        """添加记忆条目"""
        if len(self.entries) >= self.max_size:
            self._evict()
        self.entries[entry.id] = entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        """获取记忆条目"""
        return self.entries.get(entry_id)

    def remove(self, entry_id: str) -> bool:
        """删除记忆条目"""
        if entry_id in self.entries:
            del self.entries[entry_id]
            return True
        return False

    def clear(self) -> None:
        """清除所有记忆"""
        self.entries.clear()

    @abstractmethod
    def _evict(self) -> None:
        """淘汰策略"""
        ...

    @abstractmethod
    def compress(self) -> None:
        """压缩记忆"""
        ...

    @abstractmethod
    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索记忆"""
        ...

    def __len__(self) -> int:
        return len(self.entries)


class ContextManager(ABC):
    """上下文管理器基类"""

    @abstractmethod
    def add_memory(self, entry: MemoryEntry) -> None:
        """添加记忆"""
        ...

    @abstractmethod
    def query(self, query: MemoryQuery) -> list[MemoryEntry]:
        """查询记忆"""
        ...

    @abstractmethod
    def compress(self) -> dict[str, int]:
        """压缩记忆，返回各层压缩结果"""
        ...

    @abstractmethod
    def get_utilization(self) -> dict[str, float]:
        """获取各层利用率"""
        ...

    @abstractmethod
    def persist(self) -> None:
        """持久化记忆"""
        ...

    @abstractmethod
    def restore(self) -> None:
        """恢复记忆"""
        ...
