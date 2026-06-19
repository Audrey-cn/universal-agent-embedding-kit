"""Tests for effort module - improving coverage"""

from src.effort import EffortLevel, EffortResult, classify
from src.effort.classifier import EffortClassifier
from src.effort.dispatch_phrases import get_dispatch_phrase
from src.effort.metrics import ComplexityMetrics
from src.effort.verification_depth import get_verification_actions, get_verification_depth


class TestComplexityMetricsAdvanced:
    """ComplexityMetrics 高级测试"""

    def test_estimate_file_count_simple(self):
        """测试简单任务文件数估计"""
        assert ComplexityMetrics._estimate_file_count("fix typo") == 1

    def test_estimate_file_count_complex(self):
        """测试复杂任务文件数估计"""
        count = ComplexityMetrics._estimate_file_count("refactor system module")
        assert count >= 3

    def test_estimate_dependency_depth(self):
        """测试依赖深度估计"""
        assert ComplexityMetrics._estimate_dependency_depth("simple task") == 0
        assert ComplexityMetrics._estimate_dependency_depth("integrate API database") >= 2

    def test_estimate_ambiguity(self):
        """测试模糊度估计"""
        assert ComplexityMetrics._estimate_ambiguity("fix") > 0.5
        # 长描述应该有低模糊度
        long_desc = (
            "implement the authentication module with JWT tokens and OAuth2 support for the system"
        )
        assert ComplexityMetrics._estimate_ambiguity(long_desc) <= 0.3

    def test_estimate_reversibility(self):
        """测试可逆度估计"""
        assert ComplexityMetrics._estimate_reversibility("simple edit") == 0.8
        assert ComplexityMetrics._estimate_reversibility("deploy to production") == 0.2
        assert ComplexityMetrics._estimate_reversibility("delete database") == 0.2

    def test_infer_task_type_all(self):
        """测试所有任务类型推断"""
        assert ComplexityMetrics._infer_task_type("implement function") == "coding"
        assert ComplexityMetrics._infer_task_type("fix bug") == "debugging"
        assert ComplexityMetrics._infer_task_type("refactor code") == "refactoring"
        assert ComplexityMetrics._infer_task_type("test function") == "testing"
        assert ComplexityMetrics._infer_task_type("research topic") == "research"
        assert ComplexityMetrics._infer_task_type("write documentation") == "documentation"
        assert ComplexityMetrics._infer_task_type("random stuff") == "general"

    def test_calculate_keyword_complexity(self):
        """测试关键词复杂度"""
        assert ComplexityMetrics._calculate_keyword_complexity("simple task") == 0.0
        assert (
            ComplexityMetrics._calculate_keyword_complexity("architecture security performance")
            == 1.0
        )


class TestEffortClassifierAdvanced:
    """EffortClassifier 高级测试"""

    def test_classify_all_levels(self):
        """测试所有级别分类"""
        classifier = EffortClassifier()

        # LOW
        metrics = ComplexityMetrics(
            file_count=1,
            dependency_depth=0,
            ambiguity=0.2,
            reversibility=0.8,
            task_type="general",
            keyword_complexity=0.0,
        )
        result = classifier.classify(metrics)
        assert result.level == EffortLevel.LOW

        # MEDIUM
        metrics = ComplexityMetrics(
            file_count=5,
            dependency_depth=2,
            ambiguity=0.5,
            reversibility=0.6,
            task_type="coding",
            keyword_complexity=0.3,
        )
        result = classifier.classify(metrics)
        assert result.level == EffortLevel.MEDIUM

        # HIGH
        metrics = ComplexityMetrics(
            file_count=10,
            dependency_depth=3,
            ambiguity=0.7,
            reversibility=0.5,
            task_type="coding",
            keyword_complexity=0.5,
        )
        result = classifier.classify(metrics)
        assert result.level == EffortLevel.HIGH

        # XHIGH (low reversibility)
        metrics = ComplexityMetrics(
            file_count=5,
            dependency_depth=2,
            ambiguity=0.3,
            reversibility=0.1,
            task_type="coding",
            keyword_complexity=0.3,
        )
        result = classifier.classify(metrics)
        assert result.level == EffortLevel.XHIGH

    def test_confidence_calculation(self):
        """测试置信度计算"""
        classifier = EffortClassifier()
        metrics = ComplexityMetrics(
            file_count=1,
            dependency_depth=0,
            ambiguity=0.1,
            reversibility=0.9,
            task_type="general",
            keyword_complexity=0.0,
        )
        result = classifier.classify(metrics)
        assert 0.0 <= result.confidence <= 1.0

    def test_reasoning_generation(self):
        """测试理由生成"""
        classifier = EffortClassifier()
        metrics = ComplexityMetrics(
            file_count=10,
            dependency_depth=4,
            ambiguity=0.8,
            reversibility=0.2,
            task_type="coding",
            keyword_complexity=0.7,
        )
        result = classifier.classify(metrics)
        assert len(result.reasoning) > 0
        assert "文件" in result.reasoning or "依赖" in result.reasoning


class TestDispatchPhrasesAdvanced:
    """DispatchPhrases 高级测试"""

    def test_all_levels_english(self):
        """测试所有级别的英文短语"""
        for level in EffortLevel:
            phrase = get_dispatch_phrase(level, "en")
            assert len(phrase) > 0

    def test_all_levels_chinese(self):
        """测试所有级别的中文短语"""
        for level in EffortLevel:
            phrase = get_dispatch_phrase(level, "zh")
            assert len(phrase) > 0

    def test_phrase_content(self):
        """测试短语内容"""
        assert "routine" in get_dispatch_phrase(EffortLevel.LOW, "en").lower()
        assert "standard" in get_dispatch_phrase(EffortLevel.MEDIUM, "en").lower()
        assert "complex" in get_dispatch_phrase(EffortLevel.HIGH, "en").lower()
        # XHIGH 短语包含 "sensitivity" 而不是 "critical"
        assert (
            "sensitivity" in get_dispatch_phrase(EffortLevel.XHIGH, "en").lower()
            or "critical" in get_dispatch_phrase(EffortLevel.XHIGH, "en").lower()
        )


class TestVerificationDepthAdvanced:
    """VerificationDepth 高级测试"""

    def test_all_levels(self):
        """测试所有级别"""
        for level in EffortLevel:
            depth = get_verification_depth(level, "en")
            assert len(depth) > 0

    def test_actions(self):
        """测试验证动作"""
        assert get_verification_actions(EffortLevel.LOW) == []
        assert "self_check" in get_verification_actions(EffortLevel.MEDIUM)
        assert "run_tests" in get_verification_actions(EffortLevel.HIGH)
        assert "fresh_context_verify" in get_verification_actions(EffortLevel.XHIGH)


class TestEffortIntegration:
    """Effort 集成测试"""

    def test_classify_with_all_params(self):
        """测试带所有参数的分类"""
        result = classify(
            "implement auth module",
            file_count=5,
            dependency_depth=3,
            ambiguity=0.5,
            reversibility=0.6,
            language="en",
        )
        assert isinstance(result, EffortResult)
        assert result.level in EffortLevel

    def test_classify_chinese_output(self):
        """测试中文输出"""
        result = classify("实现认证模块", language="zh")
        assert len(result.dispatch_phrase) > 0

    def test_classify_consistency(self):
        """测试分类一致性"""
        # 相同输入应该产生相同输出
        r1 = classify("implement auth module")
        r2 = classify("implement auth module")
        assert r1.level == r2.level
        assert r1.metrics["score"] == r2.metrics["score"]
