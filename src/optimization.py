"""Performance Optimizer — 性能优化器"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any


@dataclass
class PerformanceMetrics:
    """性能指标"""

    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0

    def update(self, elapsed: float):
        """更新指标"""
        self.call_count += 1
        self.total_time += elapsed
        self.min_time = min(self.min_time, elapsed)
        self.max_time = max(self.max_time, elapsed)
        self.avg_time = self.total_time / self.call_count

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "function": self.function_name,
            "calls": self.call_count,
            "total_ms": round(self.total_time * 1000, 4),
            "min_ms": round(self.min_time * 1000, 4),
            "max_ms": round(self.max_time * 1000, 4),
            "avg_ms": round(self.avg_time * 1000, 4),
        }


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self.metrics: dict[str, PerformanceMetrics] = {}

    def profile(self, func: Callable) -> Callable:
        """性能分析装饰器"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start

            if func.__name__ not in self.metrics:
                self.metrics[func.__name__] = PerformanceMetrics(function_name=func.__name__)
            self.metrics[func.__name__].update(elapsed)

            return result

        return wrapper

    def get_metrics(self) -> list[dict[str, Any]]:
        """获取所有指标"""
        return [m.to_dict() for m in self.metrics.values()]

    def get_summary(self) -> dict[str, Any]:
        """获取摘要"""
        total_calls = sum(m.call_count for m in self.metrics.values())
        total_time = sum(m.total_time for m in self.metrics.values())

        return {
            "total_functions": len(self.metrics),
            "total_calls": total_calls,
            "total_time_ms": round(total_time * 1000, 4),
            "functions": self.get_metrics(),
        }

    def reset(self):
        """重置指标"""
        self.metrics.clear()


# 全局性能分析器
profiler = PerformanceProfiler()


class Cache:
    """简单缓存"""

    def __init__(self, max_size: int = 1000, ttl: float = 300.0):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """设置缓存"""
        if len(self._cache) >= self.max_size:
            # 淘汰最旧的条目
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

    def clear(self):
        """清除缓存"""
        self._cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


def cached(cache: Cache, key_func: Callable[..., str] | None = None):
    """缓存装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func is not None:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"

            # 检查缓存
            result = cache.get(cache_key)
            if result is not None:
                return result

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            cache.set(cache_key, result)

            return result

        return wrapper

    return decorator


class BatchProcessor:
    """批处理器"""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self._buffer: list[Any] = []
        self._processor: Callable | None = None

    def set_processor(self, processor: Callable):
        """设置处理器"""
        self._processor = processor

    def add(self, item: Any):
        """添加项目"""
        self._buffer.append(item)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """刷新缓冲区"""
        if self._buffer and self._processor:
            self._processor(self._buffer)
            self._buffer.clear()

    def size(self) -> int:
        """获取缓冲区大小"""
        return len(self._buffer)


class ConnectionPool:
    """连接池"""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._pool: list[Any] = []
        self._in_use: set = set()

    def acquire(self) -> Any | None:
        """获取连接"""
        if self._pool:
            conn = self._pool.pop()
            self._in_use.add(id(conn))
            return conn
        return None

    def release(self, conn: Any):
        """释放连接"""
        conn_id = id(conn)
        if conn_id in self._in_use:
            self._in_use.discard(conn_id)
            if len(self._pool) < self.max_size:
                self._pool.append(conn)

    def size(self) -> int:
        """获取池大小"""
        return len(self._pool) + len(self._in_use)

    def available(self) -> int:
        """获取可用连接数"""
        return len(self._pool)
