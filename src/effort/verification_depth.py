"""Verification Depth — 验证深度映射"""

from __future__ import annotations

from typing import TypedDict

from .interface import EffortLevel


class VerificationDepthInfo(TypedDict):
    depth: int
    description: str
    description_en: str
    actions: list[str]


# 验证深度映射
VERIFICATION_DEPTHS: dict[EffortLevel, VerificationDepthInfo] = {
    EffortLevel.LOW: {
        "depth": 0,
        "description": "跳过验证",
        "description_en": "Skip verification",
        "actions": [],
    },
    EffortLevel.MEDIUM: {
        "depth": 1,
        "description": "一次自检",
        "description_en": "One self-check",
        "actions": ["self_check"],
    },
    EffortLevel.HIGH: {
        "depth": 2,
        "description": "完整自检",
        "description_en": "Full self-verification",
        "actions": ["self_check", "run_tests", "check_edge_cases"],
    },
    EffortLevel.XHIGH: {
        "depth": 3,
        "description": "全新上下文交叉验证",
        "description_en": "Fresh-context cross-verification",
        "actions": ["self_check", "run_tests", "check_edge_cases", "fresh_context_verify"],
    },
}


def get_verification_depth(level: EffortLevel, language: str = "en") -> str:
    """
    获取指定 Effort 级别的验证深度描述。

    Args:
        level: Effort 级别
        language: 语言（"zh" 或 "en"）

    Returns:
        str: 验证深度描述
    """
    depth_info = VERIFICATION_DEPTHS.get(level, VERIFICATION_DEPTHS[EffortLevel.MEDIUM])

    if language == "zh":
        return depth_info["description"]
    else:
        return depth_info["description_en"]


def get_verification_actions(level: EffortLevel) -> list[str]:
    """
    获取指定 Effort 级别的验证动作列表。

    Args:
        level: Effort 级别

    Returns:
        list[str]: 验证动作列表
    """
    depth_info = VERIFICATION_DEPTHS.get(level, VERIFICATION_DEPTHS[EffortLevel.MEDIUM])
    return depth_info["actions"]
