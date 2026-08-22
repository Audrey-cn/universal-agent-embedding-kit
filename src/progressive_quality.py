"""Progressive Quality — 渐进式质量引擎

RESEARCH_PROPOSAL.md 命题3（P0）核心组件：
"渐进式质量：先快速给出 80% 质量的答案，再按需细化到 100%"

设计目标：
- 三级质量门控：快速(FAST) → 标准(STANDARD) → 深度(DEEP)
- 按需升级：低质量门通过后才升级到更高质量门
- 成本优化：大多数任务在 FAST 或 STANDARD 级别即可完成
- 早期失败：在低质量门发现问题时快速失败，避免浪费资源

质量门控级别：
- FAST (Tier 1): 语法检查 + 基本 lint → 捕获 80% 的简单错误
- STANDARD (Tier 2): 完整测试 + 构建验证 → 追加 15% 的覆盖率
- DEEP (Tier 3): 对抗性验证 + 多视角检查 → 追加 5% 的边界情况
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .verify.interface import VerificationResult, VerificationType, verify


class QualityTier(Enum):
    """质量等级"""

    FAST = "fast"  # 快速检查：语法 + 基本 lint
    STANDARD = "standard"  # 标准检查：完整测试 + 构建
    DEEP = "deep"  # 深度检查：对抗性 + 多视角


@dataclass
class TierResult:
    """单个质量等级的验证结果"""

    tier: QualityTier
    passed: bool
    results: list[VerificationResult]
    duration_ms: float
    summary: str


@dataclass
class ProgressiveQualityResult:
    """渐进式质量验证结果"""

    artifact_path: Path
    tiers_completed: list[QualityTier]
    final_tier: QualityTier
    overall_passed: bool
    tier_results: list[TierResult]
    total_duration_ms: float
    summary: str
    recommendation: str  # 建议下一步操作

    @property
    def passed_fast(self) -> bool:
        return self._tier_passed(QualityTier.FAST)

    @property
    def passed_standard(self) -> bool:
        return self._tier_passed(QualityTier.STANDARD)

    @property
    def passed_deep(self) -> bool:
        return self._tier_passed(QualityTier.DEEP)

    def _tier_passed(self, tier: QualityTier) -> bool:
        for tr in self.tier_results:
            if tr.tier == tier:
                return tr.passed
        return False


class ProgressiveQuality:
    """渐进式质量验证器

    使用方式：
        pq = ProgressiveQuality()
        result = pq.verify(artifact_path, criteria_path)
        # result 会显示到哪个 tier 为止通过

    配置：
        pq = ProgressiveQuality(
            stop_on_fail=True,     # 失败时停止，不继续升级
            max_tier=QualityTier.STANDARD,  # 最高只到 STANDARD
        )
    """

    # 各等级对应的验证类型
    TIER_VERIFICATION_TYPES: dict[QualityTier, list[VerificationType]] = {
        QualityTier.FAST: [VerificationType.LINT],
        QualityTier.STANDARD: [VerificationType.TEST, VerificationType.BUILD],
        QualityTier.DEEP: [VerificationType.ADVERSARIAL, VerificationType.MULTI_PERSPECTIVE],
    }

    def __init__(
        self,
        stop_on_fail: bool = True,
        max_tier: QualityTier = QualityTier.DEEP,
        tier_hooks: dict[QualityTier, Callable[[Path, Path | None], bool]] | None = None,
    ):
        self.stop_on_fail = stop_on_fail
        self.max_tier = max_tier
        self._tier_hooks = tier_hooks or {}

    def verify(
        self,
        artifact_path: Path,
        criteria_path: Path | None = None,
        start_tier: QualityTier = QualityTier.FAST,
    ) -> ProgressiveQualityResult:
        """渐进式质量验证

        Args:
            artifact_path: 产出物路径
            criteria_path: 验收标准路径
            start_tier: 起始质量等级（默认从 FAST 开始）

        Returns:
            ProgressiveQualityResult: 包含各等级验证结果
        """
        tiers = self._get_tiers(start_tier)
        tier_results: list[TierResult] = []
        overall_start = time.monotonic()
        final_tier = start_tier
        overall_passed = True

        for tier in tiers:
            tr = self._run_tier(tier, artifact_path, criteria_path)
            tier_results.append(tr)
            final_tier = tier

            if not tr.passed:
                overall_passed = False
                if self.stop_on_fail:
                    break
            # 如果通过，继续升级到下一个 tier

        total_duration = (time.monotonic() - overall_start) * 1000

        # 生成摘要
        summary = self._build_summary(tier_results, overall_passed)
        recommendation = self._build_recommendation(tier_results, overall_passed)

        return ProgressiveQualityResult(
            artifact_path=artifact_path,
            tiers_completed=[tr.tier for tr in tier_results],
            final_tier=final_tier,
            overall_passed=overall_passed,
            tier_results=tier_results,
            total_duration_ms=total_duration,
            summary=summary,
            recommendation=recommendation,
        )

    def _get_tiers(self, start_tier: QualityTier) -> list[QualityTier]:
        """获取从 start_tier 到 max_tier 的等级列表"""
        tier_order = [QualityTier.FAST, QualityTier.STANDARD, QualityTier.DEEP]
        try:
            start_idx = tier_order.index(start_tier)
            end_idx = tier_order.index(self.max_tier)
        except ValueError:
            return [start_tier]
        return tier_order[start_idx : end_idx + 1]

    def _run_tier(
        self,
        tier: QualityTier,
        artifact_path: Path,
        criteria_path: Path | None,
    ) -> TierResult:
        """运行单个质量等级的验证"""
        tier_start = time.monotonic()
        vtypes = self.TIER_VERIFICATION_TYPES.get(tier, [])
        results: list[VerificationResult] = []

        for vtype in vtypes:
            try:
                result = verify(artifact_path, criteria_path, verification_type=vtype)
                results.append(result)
            except Exception as e:
                results.append(
                    VerificationResult(
                        passed=False,
                        verdict="FAIL",
                        evidence=f"Error: {e}",
                        verification_type=vtype,
                        artifact_path=artifact_path,
                        criteria_path=criteria_path,
                        notes=f"Tier {tier.value} verification error: {e}",
                    )
                )

        # 运行自定义钩子
        if tier in self._tier_hooks:
            try:
                hook_passed = self._tier_hooks[tier](artifact_path, criteria_path)
                if not hook_passed:
                    results.append(
                        VerificationResult(
                            passed=False,
                            verdict="FAIL",
                            evidence=f"Custom hook for tier {tier.value} failed",
                            verification_type=VerificationType.TEST,
                            artifact_path=artifact_path,
                            criteria_path=criteria_path,
                        )
                    )
            except Exception as e:
                results.append(
                    VerificationResult(
                        passed=False,
                        verdict="FAIL",
                        evidence=f"Custom hook error: {e}",
                        verification_type=VerificationType.TEST,
                        artifact_path=artifact_path,
                        criteria_path=criteria_path,
                    )
                )

        tier_passed = all(r.passed for r in results) if results else True
        duration = (time.monotonic() - tier_start) * 1000

        return TierResult(
            tier=tier,
            passed=tier_passed,
            results=results,
            duration_ms=duration,
            summary=self._tier_summary(tier, tier_passed, results),
        )

    def _tier_summary(
        self,
        tier: QualityTier,
        passed: bool,
        results: list[VerificationResult],
    ) -> str:
        """生成单个等级的摘要"""
        status = "PASS" if passed else "FAIL"
        checks = ", ".join(r.verification_type.value for r in results)
        return f"[{tier.value.upper()}] {status}: {checks}"

    def _build_summary(
        self,
        tier_results: list[TierResult],
        overall_passed: bool,
    ) -> str:
        """构建整体摘要"""
        lines = []
        for tr in tier_results:
            lines.append(tr.summary)
        overall = "ALL PASSED" if overall_passed else "FAILED"
        lines.append(f"Overall: {overall}")
        return " | ".join(lines)

    def _build_recommendation(
        self,
        tier_results: list[TierResult],
        overall_passed: bool,
    ) -> str:
        """生成建议"""
        if overall_passed:
            return "All quality tiers passed. Ready for deployment."
        if not tier_results:
            return "No verification results. Check artifact path."

        last_tier = tier_results[-1].tier
        if last_tier == QualityTier.FAST:
            return (
                "FAST tier failed. Fix basic syntax/lint issues before proceeding. "
                "Expected: no syntax errors, no lint violations."
            )
        elif last_tier == QualityTier.STANDARD:
            return (
                "STANDARD tier failed. Tests or build failed. "
                "Fix failing tests and ensure build succeeds before DEEP verification."
            )
        elif last_tier == QualityTier.DEEP:
            return (
                "DEEP tier failed. Adversarial or multi-perspective checks found issues. "
                "Review boundary cases and security concerns."
            )
        return "Review failed verification results and fix issues."


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #


def progressive_verify(
    artifact_path: Path,
    criteria_path: Path | None = None,
    max_tier: QualityTier = QualityTier.DEEP,
    stop_on_fail: bool = True,
) -> ProgressiveQualityResult:
    """渐进式质量验证的便捷入口

    Args:
        artifact_path: 产出物路径
        criteria_path: 验收标准路径
        max_tier: 最高验证等级
        stop_on_fail: 失败时是否停止

    Returns:
        ProgressiveQualityResult
    """
    pq = ProgressiveQuality(stop_on_fail=stop_on_fail, max_tier=max_tier)
    return pq.verify(artifact_path, criteria_path)


def quick_verify(artifact_path: Path) -> ProgressiveQualityResult:
    """快速验证：仅运行 FAST 等级"""
    return progressive_verify(artifact_path, max_tier=QualityTier.FAST)


def standard_verify(
    artifact_path: Path, criteria_path: Path | None = None
) -> ProgressiveQualityResult:
    """标准验证：运行 FAST + STANDARD 等级"""
    return progressive_verify(artifact_path, criteria_path, max_tier=QualityTier.STANDARD)


def deep_verify(artifact_path: Path, criteria_path: Path | None = None) -> ProgressiveQualityResult:
    """深度验证：运行全部三个等级"""
    return progressive_verify(artifact_path, criteria_path, max_tier=QualityTier.DEEP)
