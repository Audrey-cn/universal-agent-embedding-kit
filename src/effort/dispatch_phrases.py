"""Dispatch Phrases — 调度短语"""

from __future__ import annotations

from .interface import EffortLevel

# 调度短语映射（中英文）
DISPATCH_PHRASES = {
    EffortLevel.LOW: {
        "zh": "这是一个常规任务。不要过度推理，简洁处理。跳过自检。",
        "en": "This is a routine task. No over-deliberation, handle concisely. Skip self-review.",
    },
    EffortLevel.MEDIUM: {
        "zh": "这是一个标准任务。收集必要上下文，不超出任务范围。完成前进行一次关键需求自检。",
        "en": (
            "This is a standard task. Collect necessary context, don't exceed scope. "
            "One key requirement self-check before completion."
        ),
    },
    EffortLevel.HIGH: {
        "zh": "这是一个复杂任务。充分推理，但信息齐全后立即行动。完成前进行完整的需求自检。",
        "en": (
            "This is a complex task. Reason thoroughly, but act once information is complete. "
            "Full requirement self-check before completion."
        ),
    },
    EffortLevel.XHIGH: {
        "zh": (
            "这是最高敏感级别。审查所有边界情况，"
            "将每个判断与本次会话的实际证据对照。全新上下文交叉验证。"
        ),
        "en": (
            "This is the highest sensitivity level. Review all edge cases, "
            "cross-reference every judgment with actual evidence from this session. "
            "Fresh-context cross-verification."
        ),
    },
}


def get_dispatch_phrase(level: EffortLevel, language: str = "en") -> str:
    """
    获取指定 Effort 级别的调度短语。

    Args:
        level: Effort 级别
        language: 语言（"zh" 或 "en"）

    Returns:
        str: 调度短语
    """
    phrases = DISPATCH_PHRASES.get(level, DISPATCH_PHRASES[EffortLevel.MEDIUM])
    return phrases.get(language, phrases["en"])
