"""MCP 安全测试 — 认证、授权、限流"""

from __future__ import annotations

import asyncio
import time

import pytest

from mcp.access import ToolAccessControl
from mcp.auth import MCPAuth, MCPRateLimiter
from mcp.server import ERR_ACCESS_DENIED, ERR_AUTH_FAILED, ERR_RATE_LIMITED, MCPServer

# ============================================================
# MCPAuth 测试
# ============================================================


class TestMCPAuth:
    """MCPAuth 认证管理器测试"""

    def test_dev_mode_allows_all(self):
        """开发模式（无 token）：所有请求都通过"""
        auth = MCPAuth()
        assert auth.enabled is False
        assert auth.verify({"method": "initialize", "id": 1}) is True
        assert auth.verify({"method": "tools/call", "id": 2, "params": {"name": "test"}}) is True

    def test_token_from_env(self, monkeypatch):
        """从环境变量读取 token"""
        monkeypatch.setenv("UAEK_MCP_TOKEN", "secret123")
        auth = MCPAuth()
        assert auth.enabled is True

    def test_token_from_constructor(self):
        """从构造函数传入 token"""
        auth = MCPAuth(token="my-token")
        assert auth.enabled is True

    def test_verify_with_direct_token(self):
        """通过 _meta.token 直接传递 token 验证通过"""
        auth = MCPAuth(token="secret123")
        request = {
            "method": "tools/call",
            "id": 1,
            "_meta": {"token": "secret123"},
        }
        assert auth.verify(request) is True

    def test_verify_with_bearer_header(self):
        """通过 Authorization header 中的 Bearer token 验证通过"""
        auth = MCPAuth(token="secret123")
        request = {
            "method": "tools/call",
            "id": 1,
            "_meta": {"headers": {"Authorization": "Bearer secret123"}},
        }
        assert auth.verify(request) is True

    def test_verify_invalid_token(self):
        """无效 token 被拒绝"""
        auth = MCPAuth(token="secret123")
        request = {
            "method": "tools/call",
            "id": 1,
            "_meta": {"token": "wrong-token"},
        }
        assert auth.verify(request) is False

    def test_verify_missing_token(self):
        """缺少 token 被拒绝"""
        auth = MCPAuth(token="secret123")
        request = {"method": "tools/call", "id": 1}
        assert auth.verify(request) is False

    def test_verify_empty_meta(self):
        """_meta 为空字典时拒绝"""
        auth = MCPAuth(token="secret123")
        request = {"method": "tools/call", "id": 1, "_meta": {}}
        assert auth.verify(request) is False

    def test_verify_non_dict_meta(self):
        """_meta 不是 dict 时拒绝"""
        auth = MCPAuth(token="secret123")
        request = {"method": "tools/call", "id": 1, "_meta": "invalid"}
        assert auth.verify(request) is False


# ============================================================
# MCPRateLimiter 测试
# ============================================================


class TestMCPRateLimiter:
    """MCPRateLimiter 令牌桶限流器测试"""

    def test_initial_consume_succeeds(self):
        """初始状态下消费令牌成功"""
        limiter = MCPRateLimiter(rate=100, burst=200)
        assert limiter.consume() is True

    def test_burst_limit(self):
        """突发流量限制：超过 burst 的请求被拒绝"""
        burst = 5
        limiter = MCPRateLimiter(rate=1, burst=burst)

        # 初始 burst 个请求应该全部通过
        for _ in range(burst):
            assert limiter.consume() is True

        # 第 burst+1 个请求被拒绝（令牌已耗尽）
        assert limiter.consume() is False

    def test_rate_limit_recovery(self):
        """限流恢复：等待后令牌补充"""
        limiter = MCPRateLimiter(rate=100, burst=5)

        # 耗尽令牌
        for _ in range(5):
            limiter.consume()

        # 等待足够时间恢复 1 个令牌
        time.sleep(0.02)

        # 应该能再消费一个
        assert limiter.consume() is True

    def test_per_client_isolation(self):
        """不同客户端有独立的限流桶"""
        limiter = MCPRateLimiter(rate=1, burst=3)

        # client_a 耗尽令牌
        for _ in range(3):
            assert limiter.consume("client_a") is True
        assert limiter.consume("client_a") is False

        # client_b 不受影响
        assert limiter.consume("client_b") is True

    def test_get_status(self):
        """获取限流状态"""
        limiter = MCPRateLimiter(rate=100, burst=200)
        limiter.consume()
        status = limiter.get_status()
        assert status["rate"] == 100
        assert status["burst"] == 200
        assert "tokens" in status


# ============================================================
# ToolAccessControl 测试
# ============================================================


class TestToolAccessControl:
    """ToolAccessControl 工具级访问控制测试"""

    def test_default_allow(self):
        """默认策略：所有工具拒绝所有客户端（安全优先）"""
        ac = ToolAccessControl()
        assert ac.allow_tool("any-client", "any-tool") is False
        assert ac.allow_tool("another-client", "uaek_verify") is False

    def test_restrict_tool(self):
        """限制工具只允许特定客户端"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin"])

        assert ac.allow_tool("admin", "uaek_verify") is True
        assert ac.allow_tool("user", "uaek_verify") is False

    def test_unrestricted_tool_remains_denied(self):
        """未授权的工具（默认拒绝）"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin"])

        # 默认策略为拒绝，未授权的工具也被拒绝
        assert ac.allow_tool("user", "uaek_effort") is False

    def test_open_tool(self):
        """open_tool 移除限制，恢复为默认策略（拒绝）"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin"])
        assert ac.allow_tool("user", "uaek_verify") is False

        ac.open_tool("uaek_verify")
        # 恢复为默认策略（拒绝），所以仍然拒绝
        assert ac.allow_tool("user", "uaek_verify") is False

    def test_set_default_allow_true(self):
        """设置默认允许策略"""
        ac = ToolAccessControl()
        ac.set_default_allow(True)

        assert ac.allow_tool("any-client", "any-tool") is True

    def test_get_policy(self):
        """获取策略信息"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin", "supervisor"])

        policy = ac.get_policy("uaek_verify")
        assert policy["restricted"] is True
        assert policy["allowed_clients"] == ["admin", "supervisor"]

    def test_allow_tool_for_client(self):
        """显式授权客户端调用工具"""
        ac = ToolAccessControl()
        # 默认拒绝
        assert ac.allow_tool("user", "uaek_verify") is False

        ac.allow_tool_for_client("uaek_verify", "user")
        assert ac.allow_tool("user", "uaek_verify") is True

    def test_allow_all_tools_for_client(self):
        """批量授权客户端调用多个工具"""
        ac = ToolAccessControl()
        tools = ["uaek_verify", "uaek_effort", "uaek_workflow"]
        ac.allow_all_tools_for_client(tools, "agent-1")

        for tool in tools:
            assert ac.allow_tool("agent-1", tool) is True
        # 其他客户端仍被拒绝
        assert ac.allow_tool("agent-2", "uaek_verify") is False


# ============================================================
# MCPServer 安全集成测试
# ============================================================


def _make_verify_tool():
    """创建一个简单的验证工具用于测试"""

    async def dummy_verify(artifact_path: str) -> dict[str, str]:
        return {"passed": True, "artifact_path": artifact_path}

    return {
        "name": "uaek_verify",
        "description": "测试用验证工具",
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_path": {"type": "string"},
            },
            "required": ["artifact_path"],
        },
        "handler": dummy_verify,
    }


class TestMCPServerSecurity:
    """MCPServer 安全集成测试"""

    @pytest.fixture
    def server(self):
        """创建带安全组件的测试 server"""
        srv = MCPServer(name="test", version="1.0.0")
        tool = _make_verify_tool()
        srv.register_tool(tool["name"], tool["description"], tool["input_schema"], tool["handler"])
        # 授予默认客户端访问权限
        srv._access_control.allow_tool_for_client("uaek_verify", "default")
        return srv

    def test_dev_mode_initialize_works(self, server):
        """开发模式：initialize 正常通过"""
        request = {"method": "initialize", "id": 1}
        response = asyncio.run(server.handle_request(request))
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "test"

    def test_dev_mode_tool_call_works(self, server):
        """开发模式：工具调用正常通过"""
        request = {
            "method": "tools/call",
            "id": 2,
            "params": {"name": "uaek_verify", "arguments": {"artifact_path": "/tmp/test"}},
        }
        response = asyncio.run(server.handle_request(request))
        assert response["id"] == 2
        assert "result" in response

    # ---- 认证测试 ----

    def test_auth_invalid_token_rejected(self):
        """无效 token 被拒绝"""
        auth = MCPAuth(token="secret123")
        server = MCPServer(name="test", auth=auth)

        request = {
            "method": "initialize",
            "id": 1,
            "_meta": {"token": "wrong"},
        }
        response = asyncio.run(server.handle_request(request))
        assert "error" in response
        assert response["error"]["code"] == ERR_AUTH_FAILED

    def test_auth_missing_token_rejected(self):
        """缺少 token 被拒绝"""
        auth = MCPAuth(token="secret123")
        server = MCPServer(name="test", auth=auth)

        request = {"method": "initialize", "id": 1}
        response = asyncio.run(server.handle_request(request))
        assert "error" in response
        assert response["error"]["code"] == ERR_AUTH_FAILED

    def test_auth_valid_token_passes(self):
        """有效 token 通过"""
        auth = MCPAuth(token="secret123")
        server = MCPServer(name="test", auth=auth)

        request = {
            "method": "initialize",
            "id": 1,
            "_meta": {"token": "secret123"},
        }
        response = asyncio.run(server.handle_request(request))
        assert "result" in response

    # ---- 限流测试 ----

    def test_rate_limit_exceeded_rejected(self):
        """超限请求被拒绝"""
        rate_limiter = MCPRateLimiter(rate=1, burst=3)
        server = MCPServer(name="test", rate_limiter=rate_limiter)

        # 前 3 个请求通过
        for i in range(3):
            request = {"method": "initialize", "id": i}
            response = asyncio.run(server.handle_request(request))
            assert "result" in response, f"Request {i} should pass"

        # 第 4 个请求被限流
        request = {"method": "initialize", "id": 99}
        response = asyncio.run(server.handle_request(request))
        assert "error" in response
        assert response["error"]["code"] == ERR_RATE_LIMITED

    # ---- 工具访问控制测试 ----

    def test_access_control_denied_tool_rejected(self):
        """未授权工具调用被拒绝"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin"])
        server = MCPServer(name="test", access_control=ac)
        tool = _make_verify_tool()
        server.register_tool(
            tool["name"], tool["description"], tool["input_schema"], tool["handler"]
        )

        # 以 "user" 身份调用被限制的工具
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {"name": "uaek_verify", "arguments": {"artifact_path": "/tmp/test"}},
            "_meta": {"client_id": "user"},
        }
        response = asyncio.run(server.handle_request(request))
        assert "error" in response
        assert response["error"]["code"] == ERR_ACCESS_DENIED

    def test_access_control_allowed_tool_passes(self):
        """已授权工具调用通过"""
        ac = ToolAccessControl()
        ac.restrict_tool("uaek_verify", ["admin"])
        server = MCPServer(name="test", access_control=ac)
        tool = _make_verify_tool()
        server.register_tool(
            tool["name"], tool["description"], tool["input_schema"], tool["handler"]
        )

        # 以 "admin" 身份调用
        request = {
            "method": "tools/call",
            "id": 1,
            "params": {"name": "uaek_verify", "arguments": {"artifact_path": "/tmp/test"}},
            "_meta": {"client_id": "admin"},
        }
        response = asyncio.run(server.handle_request(request))
        assert "result" in response

    # ---- 通知静默 ----

    def test_notification_silent_on_auth_failure(self):
        """通知请求认证失败时静默返回 None"""
        auth = MCPAuth(token="secret123")
        server = MCPServer(name="test", auth=auth)

        # notification 没有 id
        request = {"method": "notifications/initialized"}
        response = asyncio.run(server.handle_request(request))
        assert response is None

    def test_notification_silent_on_rate_limit(self):
        """通知请求被限流时静默返回 None"""
        rate_limiter = MCPRateLimiter(rate=1, burst=0)
        server = MCPServer(name="test", rate_limiter=rate_limiter)

        request = {"method": "notifications/initialized"}
        response = asyncio.run(server.handle_request(request))
        assert response is None


# ============================================================
# _extract_client_id 测试
# ============================================================


class TestClientIdExtraction:
    """客户端 ID 提取测试"""

    def test_default_client_id(self):
        """无 meta 信息时返回 default"""
        server = MCPServer()
        result = server._extract_client_id({"method": "test", "id": 1})
        assert result == "default"

    def test_explicit_client_id(self):
        """从 _meta.client_id 提取"""
        server = MCPServer()
        result = server._extract_client_id(
            {"method": "test", "id": 1, "_meta": {"client_id": "agent-42"}}
        )
        assert result == "agent-42"

    def test_header_client_id(self):
        """从 headers 提取 client ID"""
        server = MCPServer()
        result = server._extract_client_id(
            {
                "method": "test",
                "id": 1,
                "_meta": {"headers": {"X-Client-ID": "agent-42"}},
            }
        )
        assert result == "agent-42"

    def test_explicit_priority_over_header(self):
        """显式 client_id 优先于 header"""
        server = MCPServer()
        result = server._extract_client_id(
            {
                "method": "test",
                "id": 1,
                "_meta": {
                    "client_id": "explicit-id",
                    "headers": {"X-Client-ID": "header-id"},
                },
            }
        )
        assert result == "explicit-id"
