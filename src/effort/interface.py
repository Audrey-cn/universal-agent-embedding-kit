"""Effort Engine Interface — Effort 引擎接口"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EffortLevel(Enum):
    """Effort 级别"""

    LOW = "low"  # 简单任务，跳过自检
    MEDIUM = "medium"  # 标准任务，一次自检
    HIGH = "high"  # 复杂任务，完整自检
    XHIGH = "xhigh"  # 关键任务，全新上下文交叉验证


@dataclass
class EffortResult:
    """Effort 分类结果"""

    level: EffortLevel
    confidence: float  # 0.0 - 1.0
    dispatch_phrase: str  # 调度短语（注入到 Agent 提示词中）
    verification_depth: str  # 验证深度描述
    reasoning: str  # 分类理由
    metrics: dict  # 复杂度指标

    def __str__(self) -> str:
        return (
            f"Effort: {self.level.value} (confidence: {self.confidence:.0%})\n"
            f"Dispatch: {self.dispatch_phrase}\n"
            f"Verification: {self.verification_depth}\n"
            f"Reasoning: {self.reasoning}"
        )


def classify(
    task_description: str,
    file_count: int | None = None,
    dependency_depth: int | None = None,
    ambiguity: float | None = None,
    reversibility: float | None = None,
    language: str = "en",
) -> EffortResult:
    """
    根据任务描述和指标分类 Effort 级别。

    Args:
        task_description: 任务描述
        file_count: 涉及文件数（可选）
        dependency_depth: 依赖深度（可选）
        ambiguity: 模糊度 0.0-1.0（可选）
        reversibility: 可逆度 0.0-1.0（可选）
        language: 语言（"zh" 或 "en"，默认 "en"）

    Returns:
        EffortResult: 分类结果
    """
    from .classifier import EffortClassifier
    from .metrics import ComplexityMetrics

    # 计算复杂度指标
    metrics = ComplexityMetrics.from_task(
        task_description=task_description,
        file_count=file_count,
        dependency_depth=dependency_depth,
        ambiguity=ambiguity,
        reversibility=reversibility,
    )

    # 分类
    classifier = EffortClassifier()
    return classifier.classify(metrics, language=language)
