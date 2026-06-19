"""Tests for effort engine"""

from src.effort import EffortLevel, classify


class TestEffortClassifier:
    """测试 Effort 分类器"""

    def test_simple_task(self):
        """测试简单任务"""
        result = classify("fix typo in README")
        assert result.level in [EffortLevel.LOW, EffortLevel.MEDIUM]
        assert result.confidence > 0.0

    def test_complex_task(self):
        """测试复杂任务"""
        result = classify(
            "refactor authentication system with 10+ files",
            file_count=12,
            dependency_depth=4,
            ambiguity=0.3,
            reversibility=0.5,
        )
        assert result.level in [EffortLevel.HIGH, EffortLevel.XHIGH]
        assert result.confidence > 0.0

    def test_critical_task(self):
        """测试关键任务"""
        result = classify(
            "deploy to production database",
            file_count=5,
            dependency_depth=3,
            ambiguity=0.2,
            reversibility=0.1,
        )
        # 可逆度 < 0.3 应该强制 xhigh
        assert result.level == EffortLevel.XHIGH

    def test_dispatch_phrase_english(self):
        """测试英文调度短语"""
        result = classify("simple task", language="en")
        assert len(result.dispatch_phrase) > 0
        assert (
            "routine" in result.dispatch_phrase.lower()
            or "standard" in result.dispatch_phrase.lower()
        )

    def test_dispatch_phrase_chinese(self):
        """测试中文调度短语"""
        result = classify("简单任务", language="zh")
        assert len(result.dispatch_phrase) > 0
        assert "常规" in result.dispatch_phrase or "标准" in result.dispatch_phrase

    def test_verification_depth(self):
        """测试验证深度"""
        result = classify("simple task")
        assert len(result.verification_depth) > 0

    def test_reasoning(self):
        """测试分类理由"""
        result = classify("implement auth module")
        assert len(result.reasoning) > 0

    def test_metrics(self):
        """测试复杂度指标"""
        result = classify("test task", file_count=3, dependency_depth=2)
        assert "file_count" in result.metrics
        assert "dependency_depth" in result.metrics
        assert "score" in result.metrics


class TestEffortLevel:
    """测试 EffortLevel 枚举"""

    def test_values(self):
        """测试枚举值"""
        assert EffortLevel.LOW.value == "low"
        assert EffortLevel.MEDIUM.value == "medium"
        assert EffortLevel.HIGH.value == "high"
        assert EffortLevel.XHIGH.value == "xhigh"


class TestComplexityMetrics:
    """测试复杂度指标"""

    def test_from_task(self):
        """测试从任务描述创建指标"""
        from src.effort.metrics import ComplexityMetrics

        metrics = ComplexityMetrics.from_task("implement auth module")
        assert metrics.file_count > 0
        assert metrics.dependency_depth >= 0
        assert 0.0 <= metrics.ambiguity <= 1.0
        assert 0.0 <= metrics.reversibility <= 1.0
        assert len(metrics.task_type) > 0

    def test_task_type_inference(self):
        """测试任务类型推断"""
        from src.effort.metrics import ComplexityMetrics

        assert ComplexityMetrics._infer_task_type("implement function") == "coding"
        assert ComplexityMetrics._infer_task_type("fix bug") == "debugging"
        assert ComplexityMetrics._infer_task_type("research topic") == "research"
        assert ComplexityMetrics._infer_task_type("refactor code") == "refactoring"
        assert ComplexityMetrics._infer_task_type("test function") == "testing"
        assert ComplexityMetrics._infer_task_type("write documentation") == "documentation"
