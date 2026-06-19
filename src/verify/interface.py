"""Verification Framework Interface — 验证框架接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class VerificationType(Enum):
    """验证类型"""

    TEST = "test"  # 运行测试套件
    BUILD = "build"  # 尝试构建
    LINT = "lint"  # 代码检查
    RENDER = "render"  # 渲染并观察
    DIFF = "diff"  # 与规格对比
    ADVERSARIAL = "adversarial"  # 红队攻击


@dataclass
class VerificationResult:
    """验证结果"""

    passed: bool
    verdict: str  # PASS / FAIL / INDETERMINATE
    evidence: str  # 具体证据（测试输出、错误信息等）
    verification_type: VerificationType
    artifact_path: Path
    criteria_path: Path | None = None
    notes: str = ""

    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} [{self.verification_type.value}] {self.artifact_path}: {self.notes}"


class VerificationRunner(ABC):
    """验证运行器基类"""

    @abstractmethod
    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行验证"""
        ...

    @abstractmethod
    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否能处理该文件类型"""
        ...


def verify(
    artifact_path: Path,
    criteria_path: Path | None = None,
    verification_type: VerificationType | None = None,
) -> VerificationResult:
    """
    运行验证的主入口函数。

    Args:
        artifact_path: 产出物路径
        criteria_path: 验收标准路径（可选）
        verification_type: 验证类型（可选，默认自动检测）

    Returns:
        VerificationResult: 验证结果
    """
    from .build_runner import BuildRunner
    from .lint_runner import LintRunner
    from .test_runner import TestRunner

    runners = [TestRunner(), BuildRunner(), LintRunner()]

    # 如果指定了验证类型，使用对应的运行器
    if verification_type:
        for runner in runners:
            if runner.can_handle(artifact_path):
                return runner.run(artifact_path, criteria_path)

    # 自动检测：尝试所有运行器
    for runner in runners:
        if runner.can_handle(artifact_path):
            return runner.run(artifact_path, criteria_path)

    return VerificationResult(
        passed=False,
        verdict="INDETERMINATE",
        evidence="No suitable runner found",
        verification_type=verification_type or VerificationType.TEST,
        artifact_path=artifact_path,
        criteria_path=criteria_path,
        notes="Cannot determine verification type",
    )
