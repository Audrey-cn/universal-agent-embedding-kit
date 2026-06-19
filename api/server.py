"""UAEK API Server — HTTP 接口"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.memory import MemoryService

MEMORY_SERVICE = MemoryService(Path(".uaek/api-memory"))


class UAEKHandler(BaseHTTPRequestHandler):
    """UAEK HTTP 请求处理器"""

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._respond(
                200,
                {
                    "name": "UAEK API",
                    "version": "1.0.0",
                    "endpoints": [
                        "GET /",
                        "GET /health",
                        "POST /verify",
                        "POST /effort",
                        "POST /workflow",
                        "POST /memory",
                    ],
                },
            )
        elif path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path

        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        if path == "/verify":
            self._handle_verify(data)
        elif path == "/effort":
            self._handle_effort(data)
        elif path == "/workflow":
            self._handle_workflow(data)
        elif path == "/memory":
            self._handle_memory(data)
        else:
            self._respond(404, {"error": "Not found"})

    def _handle_verify(self, data: dict[str, Any]):
        """处理验证请求"""
        from src.verify import VerificationType, verify

        artifact_path = data.get("artifact_path")
        criteria_path = data.get("criteria_path")
        verification_type = data.get("verification_type")
        fresh_context = data.get("fresh_context", False)

        if not artifact_path:
            self._respond(400, {"error": "artifact_path is required"})
            return

        try:
            artifact = Path(artifact_path)
            criteria = Path(criteria_path) if criteria_path else None
            vtype = VerificationType(verification_type) if verification_type else None

            if fresh_context:
                from src.verify.fresh_context import FreshContextVerifier

                verifier = FreshContextVerifier()
                result = verifier.verify(
                    artifact, criteria or Path("."), vtype or VerificationType.TEST
                )
            else:
                result = verify(artifact, criteria, vtype)

            self._respond(
                200,
                {
                    "passed": result.passed,
                    "verdict": result.verdict,
                    "evidence": result.evidence[:1000],
                    "verification_type": result.verification_type.value,
                    "notes": result.notes,
                },
            )
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _handle_effort(self, data: dict[str, Any]):
        """处理 Effort 分类请求"""
        from src.effort import classify

        task_description = data.get("task_description")
        if not task_description:
            self._respond(400, {"error": "task_description is required"})
            return

        try:
            result = classify(
                task_description,
                file_count=data.get("file_count"),
                dependency_depth=data.get("dependency_depth"),
                ambiguity=data.get("ambiguity"),
                reversibility=data.get("reversibility"),
                language=data.get("language", "en"),
            )

            self._respond(
                200,
                {
                    "level": result.level.value,
                    "confidence": result.confidence,
                    "dispatch_phrase": result.dispatch_phrase,
                    "verification_depth": result.verification_depth,
                    "reasoning": result.reasoning,
                    "metrics": result.metrics,
                },
            )
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _handle_workflow(self, data: dict[str, Any]):
        """处理工作流请求"""
        from src.workflow import execute_workflow_config

        try:
            result = execute_workflow_config(
                {
                    "id": data.get("id") or data.get("workflow_id") or "api-workflow",
                    "type": data.get("type", "sequential"),
                    "max_workers": data.get("max_workers", 4),
                    "fail_fast": data.get("fail_fast", True),
                    "tasks": data.get("tasks", []),
                }
            )
            self._respond(200, result)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _handle_memory(self, data: dict[str, Any]):
        """处理记忆请求"""
        action = data.get("action", "query")

        try:
            if action == "add":
                content = data.get("content")
                layer = data.get("layer", "l1")
                importance = data.get("importance", 0.5)
                tags = data.get("tags", [])
                if not isinstance(content, str):
                    self._respond(400, {"error": "content must be a string"})
                    return
                if not isinstance(layer, str):
                    self._respond(400, {"error": "layer must be a string"})
                    return
                if not isinstance(importance, int | float):
                    self._respond(400, {"error": "importance must be a number"})
                    return
                if not isinstance(tags, list):
                    self._respond(400, {"error": "tags must be a list"})
                    return

                entry = MEMORY_SERVICE.add(
                    entry_id=f"api_{int(time.time() * 1000)}",
                    content=content,
                    layer=layer,
                    importance=importance,
                    tags=tags,
                )
                MEMORY_SERVICE.persist()

                self._respond(
                    200,
                    {
                        "id": entry["id"],
                        "content": entry["content"],
                        "layer": layer,
                        "status": "added",
                    },
                )
            elif action == "query":
                query_text = data.get("query", "")
                self._respond(
                    200,
                    MEMORY_SERVICE.query(
                        str(query_text),
                        layer=data.get("layer"),
                        tags=data.get("tags") or [],
                        min_importance=data.get("min_importance", 0.0),
                        limit=data.get("limit", 10),
                    ),
                )
            elif action == "compress":
                result = MEMORY_SERVICE.compress(
                    layer=data.get("layer"),
                    target_ratio=data.get("target_ratio", 0.5),
                )
                MEMORY_SERVICE.persist()
                self._respond(200, result)
            elif action == "persist":
                self._respond(200, MEMORY_SERVICE.persist())
            elif action == "restore":
                self._respond(200, MEMORY_SERVICE.restore())
            elif action == "clear":
                self._respond(200, MEMORY_SERVICE.clear())
            elif action == "stats":
                self._respond(200, MEMORY_SERVICE.stats())
            else:
                self._respond(400, {"error": f"Unknown action: {action}"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status: int, data: dict[str, Any]):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def create_server(host: str = "localhost", port: int = 8000) -> HTTPServer:
    """创建 HTTP 服务器"""
    return HTTPServer((host, port), UAEKHandler)


def run_server(host: str = "localhost", port: int = 8000):
    """运行服务器"""
    server = create_server(host, port)
    print(f"UAEK API Server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run_server(host, port)
