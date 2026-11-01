"""ACL and rate limits use the authenticated principal, never caller claims."""

from __future__ import annotations

import asyncio

import pytest

from mcp.access import ToolAccessControl
from mcp.auth import MCPAuth, MCPRateLimiter
from mcp.server import (
    ERR_ACCESS_DENIED,
    ERR_AUTH_FAILED,
    ERR_RATE_LIMITED,
    MCPServer,
    create_server,
)

CLAIMED_ADMIN = [
    {"client_id": "admin"},
    {"headers": {"X-Client-ID": "admin"}},
    {"headers": {"x-client-id": "admin"}},
    {"headers": {"Client-ID": "admin"}},
    {"client_id": "admin", "headers": {"X-Client-ID": "admin"}},
]


@pytest.fixture(autouse=True)
def isolated_auth_environment(monkeypatch):
    monkeypatch.delenv("UAEK_MCP_TOKEN", raising=False)
    monkeypatch.delenv("UAEK_MCP_TOKEN_TTL", raising=False)


def _server(allowed_principal, *, auth=None):
    calls = []

    async def probe():
        calls.append("called")
        return {"allowed": True}

    access = ToolAccessControl()
    access.restrict_tool("probe", [allowed_principal])
    server = MCPServer(auth=auth, access_control=access)
    server.register_tool("probe", "No external side effects", {"type": "object"}, probe)
    return server, calls


def _call(server, meta):
    return asyncio.run(
        server.handle_request(
            {"id": 1, "method": "tools/call", "params": {"name": "probe"}, "_meta": meta}
        )
    )


@pytest.mark.parametrize("claim", CLAIMED_ADMIN)
@pytest.mark.parametrize("bearer", [False, True], ids=["direct-token", "bearer-token"])
def test_valid_token_cannot_select_another_acl_principal(claim, bearer):
    server, calls = _server("admin", auth=MCPAuth(token="test-token"))
    meta = {**claim, "headers": dict(claim.get("headers", {}))}
    if bearer:
        meta["headers"]["Authorization"] = "Bearer test-token"
    else:
        meta["token"] = "test-token"

    response = _call(server, meta)

    assert response.get("error", {}).get("code") == ERR_ACCESS_DENIED
    assert calls == []


@pytest.mark.parametrize("claim", CLAIMED_ADMIN)
def test_trusted_stdio_principal_does_not_change_with_caller_metadata(claim):
    server, calls = _server("default")

    response = _call(server, claim)

    assert "result" in response
    assert calls == ["called"]


@pytest.mark.parametrize("claim", CLAIMED_ADMIN)
@pytest.mark.parametrize("token", [None, "test-token"], ids=["trusted-stdio", "with-token"])
def test_changing_claimed_identity_cannot_reset_rate_limit(monkeypatch, claim, token):
    # Freeze only the clock; exercise the real token bucket without refill races.
    monkeypatch.setattr("mcp.auth.time.monotonic", lambda: 1000.0)
    server = MCPServer(auth=MCPAuth(token=token), rate_limiter=MCPRateLimiter(rate=1, burst=1))
    credentials = {"token": token} if token else {}

    def initialize(meta):
        return asyncio.run(server.handle_request({"id": 1, "method": "initialize", "_meta": meta}))

    assert "result" in initialize({**credentials, "client_id": "user"})
    assert initialize({**credentials, "client_id": "user"})["error"]["code"] == ERR_RATE_LIMITED
    response = initialize({**claim, **credentials})
    assert response.get("error", {}).get("code") == ERR_RATE_LIMITED


@pytest.mark.parametrize("claim", CLAIMED_ADMIN)
def test_configured_user_principal_cannot_impersonate_admin(claim):
    server, calls = _server("admin", auth=MCPAuth(token="test-token", principal_id="user"))

    response = _call(server, {**claim, "token": "test-token"})

    assert response.get("error", {}).get("code") == ERR_ACCESS_DENIED
    assert calls == []


def test_authorized_principal_succeeds_despite_conflicting_claim():
    server, calls = _server("admin", auth=MCPAuth(token="test-token", principal_id="admin"))

    response = _call(server, {"token": "test-token", "client_id": "user"})

    assert "result" in response
    assert calls == ["called"]


def test_rate_budgets_are_separated_only_by_server_configured_principals(monkeypatch):
    monkeypatch.setattr("mcp.auth.time.monotonic", lambda: 1000.0)
    limiter = MCPRateLimiter(rate=1, burst=1)
    user = MCPServer(auth=MCPAuth(principal_id="user"), rate_limiter=limiter)
    admin = MCPServer(auth=MCPAuth(principal_id="admin"), rate_limiter=limiter)
    request = {"id": 1, "method": "initialize", "_meta": {"client_id": "admin"}}

    assert "result" in asyncio.run(user.handle_request(request))
    assert asyncio.run(user.handle_request(request))["error"]["code"] == ERR_RATE_LIMITED
    assert "result" in asyncio.run(admin.handle_request(request))
    request["_meta"]["client_id"] = "another-claim"
    assert asyncio.run(admin.handle_request(request))["error"]["code"] == ERR_RATE_LIMITED


@pytest.mark.parametrize("meta", [{}, {"token": "wrong"}, {"headers": []}])
def test_failed_authentication_neither_dispatches_nor_uses_rate_budget(monkeypatch, meta):
    monkeypatch.setattr("mcp.auth.time.monotonic", lambda: 1000.0)
    server, calls = _server("user", auth=MCPAuth(token="test-token", principal_id="user"))
    server._rate_limiter = MCPRateLimiter(rate=1, burst=1)

    denied = _call(server, {**meta, "client_id": "admin"})
    allowed = _call(server, {"token": "test-token", "client_id": "user"})

    assert denied.get("error", {}).get("code") == ERR_AUTH_FAILED
    assert "result" in allowed
    assert calls == ["called"]


def test_expired_token_does_not_authenticate_a_principal(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("mcp.auth.time.monotonic", lambda: clock[0])
    auth = MCPAuth(token="test-token", ttl=1, principal_id="user")
    clock[0] = 1002.0

    assert auth.authenticate({"_meta": {"token": "test-token", "client_id": "admin"}}) is None
    assert auth.verify({"_meta": {"token": "test-token"}}) is False


@pytest.mark.parametrize("principal_id", ["", " ", None, 42])
def test_embedding_api_rejects_empty_or_non_string_principal(principal_id):
    with pytest.raises(ValueError, match="principal_id"):
        MCPAuth(principal_id=principal_id)


def test_environment_token_still_binds_to_server_configured_principal(monkeypatch):
    monkeypatch.setenv("UAEK_MCP_TOKEN", "environment-token")
    auth = MCPAuth(principal_id="host")
    request = {"_meta": {"token": "environment-token", "client_id": "admin"}}

    assert auth.authenticate(request) == "host"
    assert auth.verify(request) is True


def test_create_server_authorizes_its_configured_principal():
    server = create_server(auth=MCPAuth(token="test-token", principal_id="host"))
    response = asyncio.run(
        server.handle_request(
            {
                "id": 1,
                "method": "tools/call",
                "params": {"name": "uaek_effort", "arguments": {"task_description": "hello"}},
                "_meta": {"token": "test-token", "client_id": "admin"},
            }
        )
    )
    assert "result" in response
