"""MCP Tools — Effort 工具"""

from __future__ import annotations

from typing import Any


def register_effort_tool(server) -> None:
    """注册 Effort 工具"""

    async def effort(
        task_description: str,
        file_count: int | None = None,
        dependency_depth: int | None = None,
        ambiguity: float | None = None,
        reversibility: float | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """分类 Effort 级别"""
        from src.effort import classify

        result = classify(
            task_description,
            file_count=file_count,
            dependency_depth=dependency_depth,
            ambiguity=ambiguity,
            reversibility=reversibility,
            language=language,
        )

        return {
            "level": result.level.value,
            "confidence": result.confidence,
            "dispatch_phrase": result.dispatch_phrase,
            "verification_depth": result.verification_depth,
            "reasoning": result.reasoning,
            "metrics": result.metrics,
        }

    server.register_tool(
        name="uaek_effort",
        description="根据任务复杂度分类 Effort 级别",
        input_schema={
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "任务描述",
                },
                "file_count": {
                    "type": "integer",
                    "description": "涉及文件数（可选）",
                },
                "dependency_depth": {
                    "type": "integer",
                    "description": "依赖深度（可选）",
                },
                "ambiguity": {
                    "type": "number",
                    "description": "模糊度 0.0-1.0（可选）",
                },
                "reversibility": {
                    "type": "number",
                    "description": "可逆度 0.0-1.0（可选）",
                },
                "language": {
                    "type": "string",
                    "enum": ["en", "zh"],
                    "description": "语言",
                    "default": "en",
                },
            },
            "required": ["task_description"],
        },
        handler=effort,
    )
