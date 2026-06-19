"""Utilization Monitor — 利用率监控器"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .interface import MemoryLayer, MemoryLayerType


@dataclass
class UtilizationSnapshot:
    """利用率快照"""

    timestamp: float
    layer_type: MemoryLayerType
    current_size: int
    max_size: int
    utilization: float  # 0.0-1.0

    def __str__(self) -> str:
        return (
            f"[{self.layer_type.value}] "
            f"{self.current_size}/{self.max_size} "
            f"({self.utilization:.0%})"
        )


class UtilizationMonitor:
    """利用率监控器"""

    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self.snapshots: list[UtilizationSnapshot] = []
        self._callbacks: list[Callable[[UtilizationSnapshot], None]] = []

    def register_callback(self, callback: Callable[[UtilizationSnapshot], None]) -> None:
        """注册回调函数"""
        self._callbacks.append(callback)

    def check(self, layer: MemoryLayer) -> UtilizationSnapshot:
        """检查利用率"""
        current_size = len(layer)
        max_size = layer.max_size
        utilization = current_size / max_size if max_size > 0 else 0.0

        snapshot = UtilizationSnapshot(
            timestamp=time.time(),
            layer_type=layer.layer_type,
            current_size=current_size,
            max_size=max_size,
            utilization=utilization,
        )

        self.snapshots.append(snapshot)

        # 检查是否超过阈值
        if utilization > self.threshold:
            self._notify_callbacks(snapshot)

        return snapshot

    def check_all(self, layers: list[MemoryLayer]) -> list[UtilizationSnapshot]:
        """检查所有层的利用率"""
        snapshots = []
        for layer in layers:
            snapshot = self.check(layer)
            snapshots.append(snapshot)
        return snapshots

    def _notify_callbacks(self, snapshot: UtilizationSnapshot) -> None:
        """通知回调函数"""
        for callback in self._callbacks:
            try:
                callback(snapshot)
            except Exception:
                pass

    def get_history(self, layer_type: MemoryLayerType | None = None) -> list[UtilizationSnapshot]:
        """获取历史记录"""
        if layer_type:
            return [s for s in self.snapshots if s.layer_type == layer_type]
        return self.snapshots

    def get_average_utilization(self, layer_type: MemoryLayerType) -> float:
        """获取平均利用率"""
        layer_snapshots = [s for s in self.snapshots if s.layer_type == layer_type]
        if not layer_snapshots:
            return 0.0
        return sum(s.utilization for s in layer_snapshots) / len(layer_snapshots)

    def get_peak_utilization(self, layer_type: MemoryLayerType) -> float:
        """获取峰值利用率"""
        layer_snapshots = [s for s in self.snapshots if s.layer_type == layer_type]
        if not layer_snapshots:
            return 0.0
        return max(s.utilization for s in layer_snapshots)

    def clear_history(self) -> None:
        """清除历史记录"""
        self.snapshots.clear()
