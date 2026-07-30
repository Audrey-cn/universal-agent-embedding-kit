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
    MULTI_PERSPECTIVE = "multi_perspective"  # 多视角一致性检查
    COGNITIVE_PANEL = "cognitive_panel"  # 认知智囊团对抗性审查


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
    from .diff_runner import DiffRunner
    from .lint_runner import LintRunner
    from .render_runner import RenderRunner
    from .test_runner import TestRunner

    runners = [TestRunner(), BuildRunner(), LintRunner(), RenderRunner(), DiffRunner()]

    # 如果指定了验证类型，直接路由到对应的运行器
    if verification_type:
        type_to_runner: dict[VerificationType, VerificationRunner] = {
            VerificationType.TEST: TestRunner(),
            VerificationType.BUILD: BuildRunner(),
            VerificationType.LINT: LintRunner(),
            VerificationType.RENDER: RenderRunner(),
            VerificationType.DIFF: DiffRunner(),
        }
        runner = type_to_runner.get(verification_type)
        if runner:
            return runner.run(artifact_path, criteria_path)

        # 对抗性验证：委托给独立的 adversarial_verification 模块
        if verification_type == VerificationType.ADVERSARIAL:
            return _run_adversarial_verification(artifact_path, criteria_path)

        # 多视角一致性检查
        if verification_type == VerificationType.MULTI_PERSPECTIVE:
            return _run_multi_perspective_verification(artifact_path, criteria_path)

        # 认知智囊团对抗性审查
        if verification_type == VerificationType.COGNITIVE_PANEL:
            return _run_cognitive_panel_verification(artifact_path, criteria_path)

        # 未知验证类型
        return VerificationResult(
            passed=False,
            verdict="INDETERMINATE",
            evidence=f"Verification type '{verification_type.value}' is not yet implemented",
            verification_type=verification_type,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"No runner available for {verification_type.value}",
        )

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


def _run_adversarial_verification(
    artifact_path: Path,
    criteria_path: Path | None = None,
) -> VerificationResult:
    """对抗性验证：委托给独立的 adversarial_verification 模块。

    从 artifact_path 读取代码，从 criteria_path 读取任务配置，
    然后运行对抗性验证（differential + crash-safety）。
    """
    from src.adversarial_verification import REFERENCE_SOLUTIONS, adversarial_verify

    try:
        code = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Cannot read artifact: {e}",
            verification_type=VerificationType.ADVERSARIAL,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"Artifact read error: {e}",
        )

    # 从 criteria_path 或 artifact 文件名推断 task_id
    task_id = None
    if criteria_path and criteria_path.exists():
        try:
            import json
            criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
            task_id = criteria.get("task_id")
        except Exception:
            pass
    if not task_id:
        # 从文件名推断
        task_id = artifact_path.stem

    if task_id not in REFERENCE_SOLUTIONS:
        return VerificationResult(
            passed=False,
            verdict="INDETERMINATE",
            evidence=f"Task '{task_id}' has no reference oracle in adversarial verification",
            verification_type=VerificationType.ADVERSARIAL,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"Unknown task_id: {task_id}. Available: {list(REFERENCE_SOLUTIONS.keys())}",
        )

    result = adversarial_verify(task_id, code, trials=200, seed=0)

    if result["accepted"]:
        return VerificationResult(
            passed=True,
            verdict="PASS",
            evidence=f"Adversarial verification passed ({result['trials_run']} trials, "
                     f"perspectives: {result['perspectives']})",
            verification_type=VerificationType.ADVERSARIAL,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes="Passed crash_safety + differential checks",
        )
    else:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Failed perspective: {result['failed_perspective']}. "
                     f"Reason: {result['reason']}. "
                     f"Counterexample: {result['counterexample']}",
            verification_type=VerificationType.ADVERSARIAL,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"Failed at trial {result['trials_run']}",
        )


def _run_multi_perspective_verification(
    artifact_path: Path,
    criteria_path: Path | None = None,
) -> VerificationResult:
    """多视角一致性检查：委托给 multi_perspective 模块。

    从 correctness、boundary、security、maintainability 四个视角
    交叉验证同一产出物，防止单一视角的盲点。
    """
    from .multi_perspective import multi_perspective_verify

    try:
        mp_result = multi_perspective_verify(
            artifact_path,
            criteria_path,
            strict_mode=True,
        )
    except Exception as e:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Multi-perspective verification error: {e}",
            verification_type=VerificationType.MULTI_PERSPECTIVE,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"Error: {e}",
        )

    return VerificationResult(
        passed=mp_result.overall_passed,
        verdict="PASS" if mp_result.overall_passed else "FAIL",
        evidence=mp_result.summary,
        verification_type=VerificationType.MULTI_PERSPECTIVE,
        artifact_path=artifact_path,
        criteria_path=criteria_path,
        notes=f"Score: {mp_result.overall_score:.2%}, "
              f"Consensus: {mp_result.consensus_level}, "
              f"Failed: {[p.perspective.value for p in mp_result.failed_perspectives]}",
    )


def _run_cognitive_panel_verification(
    artifact_path: Path,
    criteria_path: Path | None = None,
) -> VerificationResult:
    """认知智囊团对抗性审查：委托给 cognitive_panel 模块。

    通过五个认知角色（反驳者/机会发现者/外行旁观者/破局者/落地执行者）
    对方案进行对抗性审查，检测 AI 迎合性偏差。
    """
    from .cognitive_panel import cognitive_panel_verify

    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Cannot read artifact: {e}",
            verification_type=VerificationType.COGNITIVE_PANEL,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=f"Artifact read error: {e}",
        )

    # 从 criteria_path 读取上下文
    context = ""
    if criteria_path and criteria_path.exists():
        try:
            import json
            criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
            context = criteria.get("context", "")
        except Exception:
            pass

    result = cognitive_panel_verify(content, context)

    return VerificationResult(
        passed=result.overall_passed,
        verdict="PASS" if result.overall_passed else "FAIL",
        evidence=result.summary,
        verification_type=VerificationType.COGNITIVE_PANEL,
        artifact_path=artifact_path,
        criteria_path=criteria_path,
        notes=f"Score: {result.overall_score:.2%}, "
              f"Sycophancy risk: {result.sycophancy_risk:.0%}, "
              f"Consensus: {result.consensus_level}",
    )
