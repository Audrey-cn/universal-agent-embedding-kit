"""Effort Classifier — Effort 分类器"""

from __future__ import annotations

from .dispatch_phrases import get_dispatch_phrase
from .interface import EffortLevel, EffortResult
from .metrics import ComplexityMetrics
from .verification_depth import get_verification_depth


class EffortClassifier:
    """Effort 分类器"""

    # 权重配置
    WEIGHTS = {
        "file_count": 0.25,
        "dependency_depth": 0.20,
        "ambiguity": 0.20,
        "reversibility": 0.15,
        "keyword_complexity": 0.20,
    }

    # 阈值配置
    THRESHOLDS = {
        EffortLevel.LOW: 0.3,
        EffortLevel.MEDIUM: 0.5,
        EffortLevel.HIGH: 0.7,
        EffortLevel.XHIGH: 0.9,
    }

    def classify(self, metrics: ComplexityMetrics, language: str = "en") -> EffortResult:
        """根据复杂度指标分类 Effort 级别"""
        # 计算综合分数
        score = self._calculate_score(metrics)

        # 确定 Effort 级别
        level = self._determine_level(score, metrics)

        # 生成调度短语
        dispatch_phrase = get_dispatch_phrase(level, language)

        # 生成验证深度描述
        verification_depth = get_verification_depth(level, language)

        # 生成分类理由
        reasoning = self._generate_reasoning(metrics, level, score)

        return EffortResult(
            level=level,
            confidence=self._calculate_confidence(metrics, score),
            dispatch_phrase=dispatch_phrase,
            verification_depth=verification_depth,
            reasoning=reasoning,
            metrics={
                "file_count": metrics.file_count,
                "dependency_depth": metrics.dependency_depth,
                "ambiguity": metrics.ambiguity,
                "reversibility": metrics.reversibility,
                "task_type": metrics.task_type,
                "keyword_complexity": metrics.keyword_complexity,
                "score": score,
            },
        )

    def _calculate_score(self, metrics: ComplexityMetrics) -> float:
        """计算综合分数"""
        # 归一化各指标
        file_score = min(1.0, metrics.file_count / 10.0)
        dep_score = min(1.0, metrics.dependency_depth / 5.0)
        amb_score = metrics.ambiguity
        rev_score = 1.0 - metrics.reversibility  # 不可逆 = 更高复杂度
        kw_score = metrics.keyword_complexity

        # 加权求和
        score = (
            self.WEIGHTS["file_count"] * file_score
            + self.WEIGHTS["dependency_depth"] * dep_score
            + self.WEIGHTS["ambiguity"] * amb_score
            + self.WEIGHTS["reversibility"] * rev_score
            + self.WEIGHTS["keyword_complexity"] * kw_score
        )

        return score

    def _determine_level(self, score: float, metrics: ComplexityMetrics) -> EffortLevel:
        """确定 Effort 级别"""
        # 特殊规则：安全相关任务强制 xhigh
        if metrics.reversibility < 0.3:
            return EffortLevel.XHIGH

        # 根据分数确定级别
        if score < self.THRESHOLDS[EffortLevel.LOW]:
            return EffortLevel.LOW
        elif score < self.THRESHOLDS[EffortLevel.MEDIUM]:
            return EffortLevel.MEDIUM
        elif score < self.THRESHOLDS[EffortLevel.HIGH]:
            return EffortLevel.HIGH
        else:
            return EffortLevel.XHIGH

    def _calculate_confidence(self, metrics: ComplexityMetrics, score: float) -> float:
        """计算置信度"""
        # 分数越接近阈值边界，置信度越低
        thresholds = sorted(self.THRESHOLDS.values())
        min_distance = min(abs(score - t) for t in thresholds)
        # 距离越远，置信度越高
        return min(1.0, min_distance * 3.0)

    def _generate_reasoning(
        self, metrics: ComplexityMetrics, level: EffortLevel, score: float
    ) -> str:
        """生成分类理由"""
        reasons = []

        if metrics.file_count > 5:
            reasons.append(f"涉及 {metrics.file_count} 个文件（多文件任务）")
        if metrics.dependency_depth > 2:
            reasons.append(f"依赖深度 {metrics.dependency_depth}（复杂依赖）")
        if metrics.ambiguity > 0.6:
            reasons.append(f"模糊度 {metrics.ambiguity:.0%}（需求不明确）")
        if metrics.reversibility < 0.4:
            reasons.append(f"可逆度 {metrics.reversibility:.0%}（高风险操作）")
        if metrics.keyword_complexity > 0.5:
            reasons.append("涉及复杂关键词（架构/安全/性能）")

        if not reasons:
            reasons.append("任务简单，无需深度推理")

        return f"综合分数 {score:.2f} → {level.value}。" + "；".join(reasons)
