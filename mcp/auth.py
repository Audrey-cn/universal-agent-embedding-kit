"""MCP 认证与限流模块"""

from __future__ import annotations

import os
import secrets
import threading
import time
from typing import Any


class MCPAuth:
    """MCP 认证管理器

    支持 Bearer token 认证，带 TTL 过期机制。
    开发模式（未配置 token）：允许所有请求通过。
    生产模式（配置了 UAEK_MCP_TOKEN）：请求必须携带有效的 Bearer token。

    配置方式：
    - UAEK_MCP_TOKEN: 认证 token（设置即启用认证）
    - UAEK_MCP_TOKEN_TTL: token 有效期（秒），默认 3600（1小时）
    """

    def __init__(self, token: str | None = None, ttl: int | None = None):
        # 优先使用传入的 token，其次读取环境变量
        self._token = token or os.environ.get("UAEK_MCP_TOKEN")
        self._enabled = self._token is not None

        # Token 过期时间：默认 1 小时，可通过环境变量配置
        env_ttl = os.environ.get("UAEK_MCP_TOKEN_TTL")
        self._ttl = ttl or (int(env_ttl) if env_ttl and env_ttl.isdigit() else 3600)
        self._token_created_at = time.monotonic()

    @property
    def enabled(self) -> bool:
        """认证是否已启用"""
        return self._enabled

    def verify(self, request: dict[str, Any]) -> bool:
        """验证请求是否合法

        从请求中提取 Authorization header 中的 Bearer token 进行比对。
        如果认证未启用（开发模式），始终返回 True。

        Args:
            request: JSON-RPC 请求字典，可包含 _meta.headers 或 _meta.token

        Returns:
            True 表示认证通过，False 表示认证失败
        """
        if not self._enabled:
            return True

        # 检查 token 是否过期
        if time.monotonic() - self._token_created_at > self._ttl:
            return False

        # 从请求的 _meta 中提取 token
        meta = request.get("_meta", {})
        if not isinstance(meta, dict):
            return False

        # 支持两种方式传递 token：
        # 1. _meta.token 直接传递
        # 2. _meta.headers.Authorization 中的 Bearer token
        token = self._extract_token(meta)
        if token is None:
            return False

        # 使用恒定时间比较防止时序攻击
        # （_enabled 已保证 _token 非空，此处显式守卫供类型检查与防御）
        if self._token is None:
            return False
        return secrets.compare_digest(token, self._token)

    def _extract_token(self, meta: dict[str, Any]) -> str | None:
        """从 meta 中提取 token"""
        # 直接 token
        direct_token = meta.get("token")
        if isinstance(direct_token, str) and direct_token:
            return direct_token

        # Bearer token from Authorization header
        headers = meta.get("headers", {})
        if isinstance(headers, dict):
            auth_header = headers.get("Authorization", "")
            if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
                return auth_header[7:]

        return None


class MCPRateLimiter:
    """令牌桶限流器

    使用令牌桶算法控制请求速率，线程安全。
    支持突发流量（burst），平滑限流。

    配置方式：
    - UAEK_MCP_RATE: 每秒令牌填充速率（默认 100）
    - UAEK_MCP_BURST: 桶容量/最大突发（默认 200）
    """

    # 最大客户端桶数量，防止内存耗尽 DoS
    _MAX_BUCKETS = 10_000

    def __init__(self, rate: int | None = None, burst: int | None = None):
        # 支持环境变量配置，带异常处理
        self._rate = rate or self._parse_env_int("UAEK_MCP_RATE", 100)
        self._burst = burst or self._parse_env_int("UAEK_MCP_BURST", 200)

        # 每个 client_id 对应一个桶，线程安全
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _parse_env_int(key: str, default: int) -> int:
        """安全解析环境变量为整数"""
        val = os.environ.get(key)
        if val and val.lstrip("-").isdigit():
            return int(val)
        return default

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def burst(self) -> int:
        return self._burst

    def consume(self, client_id: str = "default") -> bool:
        """消费一个令牌（线程安全）

        Args:
            client_id: 客户端标识，用于区分不同的限流桶

        Returns:
            True 表示令牌可用（请求通过），False 表示被限流
        """
        with self._lock:
            if client_id not in self._buckets:
                # 防止恶意客户端耗尽内存
                if len(self._buckets) >= self._MAX_BUCKETS:
                    return False
                self._buckets[client_id] = _TokenBucket(self._rate, self._burst)

            return self._buckets[client_id].consume()

    def get_status(self, client_id: str = "default") -> dict[str, Any]:
        """获取当前限流状态（用于监控，线程安全）"""
        with self._lock:
            if client_id not in self._buckets:
                return {"tokens": self._burst, "rate": self._rate, "burst": self._burst}

            bucket = self._buckets[client_id]
            return {
                "tokens": bucket.tokens,
                "rate": self._rate,
                "burst": self._burst,
                "last_refill": bucket.last_refill,
            }


class _TokenBucket:
    """令牌桶实现"""

    def __init__(self, rate: int, burst: int):
        self._rate = rate  # 每秒填充令牌数
        self._burst = burst  # 桶容量
        self._tokens = float(burst)  # 当前令牌数，初始满桶
        self._last_refill = time.monotonic()

    @property
    def tokens(self) -> float:
        return self._tokens

    @property
    def last_refill(self) -> float:
        return self._last_refill

    def consume(self) -> bool:
        """消费一个令牌，先补充再消费"""
        self._refill()

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True

        return False

    def _refill(self) -> None:
        """根据经过的时间补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now
