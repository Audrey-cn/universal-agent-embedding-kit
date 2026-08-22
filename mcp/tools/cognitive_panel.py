"""MCP Tools — 认知智囊团工具"""

from __future__ import annotations

from typing import Any


def register_cognitive_panel_tool(server) -> None:
    """注册认知智囊团工具"""

    async def cognitive_panel(
        proposal: str,
        context: str = "",
        roles: list[str] | None = None,
        strict_mode: bool = True,
    ) -> dict[str, Any]:
        """认知智囊团审查"""
        from src.verify.cognitive_panel import (
            CognitiveRole,
            cognitive_panel_verify,
        )

        # 解析角色列表
        role_list = None
        if roles:
            role_list = []
            role_map = {r.value: r for r in CognitiveRole}
            for role_name in roles:
                if role_name in role_map:
                    role_list.append(role_map[role_name])
                else:
                    raise ValueError(
                        f"Unknown role '{role_name}'. Available: {list(role_map.keys())}"
                    )

        result = cognitive_panel_verify(
            proposal=proposal,
            context=context,
            roles=role_list,
            strict_mode=strict_mode,
        )

        return {
            "passed": result.overall_passed,
            "verdict": "PASS" if result.overall_passed else "FAIL",
            "overall_score": round(result.overall_score, 4),
            "sycophancy_risk": round(result.sycophancy_risk, 4),
            "consensus_level": result.consensus_level,
            "roles": [
                {
                    "role": r.role.value,
                    "passed": r.passed,
                    "score": round(r.score, 4),
                    "concerns": r.concerns,
                    "opportunities": r.opportunities,
                    "sycophancy_flags": r.sycophancy_flags,
                    "evidence": r.evidence,
                }
                for r in result.roles
            ],
            "all_concerns": result.all_concerns,
            "all_opportunities": result.all_opportunities,
            "all_sycophancy_flags": result.all_sycophancy_flags,
            "summary": result.summary,
        }

    server.register_tool(
        name="uaek_cognitive_panel",
        description=(
            "认知智囊团——五角色对抗性审查，检测AI迎合性偏差。"
            "五个角色：反驳者(找风险)、机会发现者(找更多选项)、"
            "外行旁观者(常识检验)、破局者(创新方案)、落地执行者(可行性过滤)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "proposal": {
                    "type": "string",
                    "description": "要审查的方案/决策/代码描述",
                },
                "context": {
                    "type": "string",
                    "description": "背景信息（可选）",
                    "default": "",
                },
                "roles": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "devils_advocate",
                            "opportunity_spotter",
                            "layperson",
                            "rule_breaker",
                            "executor",
                        ],
                    },
                    "description": "指定运行哪些角色（默认全部五个）",
                },
                "strict_mode": {
                    "type": "boolean",
                    "description": "严格模式：任何角色反对即不通过（默认 true）",
                    "default": True,
                },
            },
            "required": ["proposal"],
        },
        handler=cognitive_panel,
    )
