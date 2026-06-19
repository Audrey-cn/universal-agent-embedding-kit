"""MCP Tools — 验证工具"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def register_verify_tool(server) -> None:
    """注册验证工具"""

    async def verify(
        artifact_path: str,
        criteria_path: str | None = None,
        verification_type: str | None = None,
        fresh_context: bool = False,
    ) -> dict[str, Any]:
        """运行验证"""
        from src.verify import VerificationType
        from src.verify import verify as run_verify

        artifact = Path(artifact_path)
        criteria = Path(criteria_path) if criteria_path else None

        vtype = None
        if verification_type:
            vtype = VerificationType(verification_type)

        if fresh_context:
            from src.verify.fresh_context import FreshContextVerifier

            verifier = FreshContextVerifier()
            result = verifier.verify(
                artifact, criteria or Path("."), vtype or VerificationType.TEST
            )
        else:
            result = run_verify(artifact, criteria, vtype)

        return {
            "passed": result.passed,
            "verdict": result.verdict,
            "evidence": result.evidence[:1000],  # 限制长度
            "verification_type": result.verification_type.value,
            "artifact_path": str(result.artifact_path),
            "notes": result.notes,
        }

    server.register_tool(
        name="uaek_verify",
        description="运行验证：测试、构建、lint、全新上下文验证",
        input_schema={
            "type": "object",
            "properties": {
                "artifact_path": {
                    "type": "string",
                    "description": "产出物路径",
                },
                "criteria_path": {
                    "type": "string",
                    "description": "验收标准路径（可选）",
                },
                "verification_type": {
                    "type": "string",
                    "enum": ["test", "build", "lint", "render", "diff", "adversarial"],
                    "description": "验证类型（可选，默认自动检测）",
                },
                "fresh_context": {
                    "type": "boolean",
                    "description": "是否使用全新上下文验证",
                    "default": False,
                },
            },
            "required": ["artifact_path"],
        },
        handler=verify,
    )
