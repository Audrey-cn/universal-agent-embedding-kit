"""Tests for API server"""

import io
import tempfile

from api.server import MAX_REQUEST_BODY_BYTES, UAEKHandler, create_server


def make_post_handler(
    path: str, body: bytes, content_length: str | int | None = None
) -> tuple[UAEKHandler, list[tuple[int, dict[str, object]]]]:
    """Create a POST handler with an in-memory request body and captured responses."""
    handler = UAEKHandler.__new__(UAEKHandler)
    handler.path = path
    handler.command = "POST"
    handler.headers = {
        "Content-Length": str(len(body)) if content_length is None else str(content_length)
    }
    handler.rfile = io.BytesIO(body)
    responses: list[tuple[int, dict[str, object]]] = []
    handler._respond = lambda status, data: responses.append((status, data))
    return handler, responses


def test_post_rejects_non_object_json() -> None:
    """POST bodies that are JSON arrays must not reach endpoint handlers."""
    handler, responses = make_post_handler("/effort", b"[]")

    handler.do_POST()

    assert responses == [(400, {"error": "JSON body must be an object"})]


def test_post_rejects_invalid_content_length() -> None:
    """Malformed Content-Length values return a client error instead of raising."""
    handler, responses = make_post_handler("/effort", b"{}", content_length="invalid")

    handler.do_POST()

    assert responses == [(400, {"error": "Invalid Content-Length"})]


def test_post_rejects_body_over_limit() -> None:
    """Declared request bodies over 1 MiB are rejected before they are read."""
    handler, responses = make_post_handler(
        "/effort", b"{}", content_length=MAX_REQUEST_BODY_BYTES + 1
    )

    handler.do_POST()

    assert responses == [(413, {"error": "Request body too large"})]


class TestAPIEndpoints:
    """API 端点测试"""

    def test_root_endpoint(self):
        """测试根端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/"
        handler.command = "GET"

        # 模拟响应
        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler.do_GET()

        assert len(responses) == 1
        assert responses[0][0] == 200
        assert "name" in responses[0][1]

    def test_health_endpoint(self):
        """测试健康检查端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/health"
        handler.command = "GET"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler.do_GET()

        assert len(responses) == 1
        assert responses[0][0] == 200
        assert responses[0][1]["status"] == "ok"

    def test_effort_endpoint(self):
        """测试 Effort 端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/effort"
        handler.command = "POST"
        handler.headers = {"Content-Length": 0}
        handler.rfile = None

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond

        # 直接调用处理函数
        handler._handle_effort({"task_description": "implement auth module"})

        assert len(responses) == 1
        assert responses[0][0] == 200
        assert "level" in responses[0][1]

    def test_effort_endpoint_missing_param(self):
        """测试 Effort 端点缺少参数"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/effort"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler._handle_effort({})

        assert len(responses) == 1
        assert responses[0][0] == 400

    def test_verify_endpoint(self):
        """测试验证端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/verify"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    return 'hello'\n")
            f.flush()

            handler._handle_verify(
                {
                    "artifact_path": f.name,
                    "verification_type": "lint",
                }
            )

        assert len(responses) == 1
        assert responses[0][0] == 200

    def test_verify_endpoint_missing_param(self):
        """测试验证端点缺少参数"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/verify"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler._handle_verify({})

        assert len(responses) == 1
        assert responses[0][0] == 400

    def test_verify_fresh_context_requires_criteria_path(self):
        """fresh-context verification should require an explicit criteria file."""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/verify"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    return 'hello'\n")
            f.flush()
            handler._handle_verify({"artifact_path": f.name, "fresh_context": True})

        assert responses == [
            (400, {"error": "criteria_path is required when fresh_context is true"})
        ]

    def test_memory_endpoint_add(self):
        """测试记忆添加端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/memory"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler._handle_memory(
            {
                "action": "add",
                "content": "Test memory",
                "layer": "l1",
                "importance": 0.8,
            }
        )

        assert len(responses) == 1
        assert responses[0][0] == 200
        assert responses[0][1]["status"] == "added"

    def test_memory_endpoint_lets_service_generate_unique_id(self, monkeypatch):
        handler = UAEKHandler.__new__(UAEKHandler)
        captured = {}

        class StubMemoryService:
            def add(self, **kwargs):
                captured.update(kwargs)
                return {"id": "generated", **kwargs}

            def persist(self):
                return {"status": "persisted"}

        responses = []
        handler._respond = lambda status, data: responses.append((status, data))
        monkeypatch.setattr("api.server.MEMORY_SERVICE", StubMemoryService())

        handler._handle_memory(
            {"action": "add", "content": "Test memory", "layer": "l1", "importance": 0.8}
        )

        assert responses[0][0] == 200
        assert "entry_id" not in captured

    def test_memory_endpoint_query(self):
        """测试记忆查询端点"""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/memory"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler._handle_memory(
            {
                "action": "query",
                "query": "test",
            }
        )

        assert len(responses) == 1
        assert responses[0][0] == 200

    def test_workflow_endpoint_rejects_unsafe_action(self):
        """API workflow execution should enforce the safe action allowlist."""
        handler = UAEKHandler.__new__(UAEKHandler)
        handler.path = "/workflow"
        handler.command = "POST"

        responses = []

        def mock_respond(status, data):
            responses.append((status, data))

        handler._respond = mock_respond
        handler._handle_workflow(
            {
                "id": "unsafe-api-workflow",
                "tasks": [
                    {
                        "id": "verify",
                        "name": "Verify arbitrary path",
                        "action": "verify",
                        "args": ["."],
                    }
                ],
            }
        )

        assert responses[-1][0] == 400
        assert "not allowed" in responses[-1][1]["error"]

    def test_create_server(self):
        """测试创建服务器"""
        server = create_server("localhost", 0)  # 使用端口 0 让系统分配
        assert server is not None
        server.server_close()
