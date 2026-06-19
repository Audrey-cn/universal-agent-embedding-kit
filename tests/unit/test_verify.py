"""Tests for verification framework"""

import tempfile
from pathlib import Path

from src.verify import VerificationResult, VerificationType, verify


class TestVerificationResult:
    """测试 VerificationResult"""

    def test_pass_result(self):
        """测试通过的结果"""
        result = VerificationResult(
            passed=True,
            verdict="PASS",
            evidence="All tests passed",
            verification_type=VerificationType.TEST,
            artifact_path=Path("/tmp/test.py"),
        )
        assert result.passed is True
        assert "✅ PASS" in str(result)

    def test_fail_result(self):
        """测试失败的结果"""
        result = VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence="Test failed",
            verification_type=VerificationType.TEST,
            artifact_path=Path("/tmp/test.py"),
        )
        assert result.passed is False
        assert "❌ FAIL" in str(result)


class TestTestRunner:
    """测试 TestRunner"""

    def test_can_handle_python_file(self):
        """测试能否处理 Python 文件"""
        from src.verify.test_runner import TestRunner

        runner = TestRunner()
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"def test_example(): pass")
            f.flush()
            assert runner.can_handle(Path(f.name)) is True

    def test_cannot_handle_text_file(self):
        """测试能否处理文本文件"""
        from src.verify.test_runner import TestRunner

        runner = TestRunner()
        assert runner.can_handle(Path("/tmp/test.txt")) is False


class TestBuildRunner:
    """测试 BuildRunner"""

    def test_can_handle_pyproject(self):
        """测试能否处理 pyproject.toml"""
        from src.verify.build_runner import BuildRunner

        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").touch()
            assert runner.can_handle(Path(tmpdir)) is True

    def test_cannot_handle_empty_dir(self):
        """测试能否处理空目录"""
        from src.verify.build_runner import BuildRunner

        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert runner.can_handle(Path(tmpdir)) is False


class TestLintRunner:
    """测试 LintRunner"""

    def test_can_handle_python_file(self):
        """测试能否处理 Python 文件"""
        from src.verify.lint_runner import LintRunner

        runner = LintRunner()
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"def example(): pass")
            f.flush()
            assert runner.can_handle(Path(f.name)) is True

    def test_cannot_handle_text_file(self):
        """测试能否处理文本文件"""
        from src.verify.lint_runner import LintRunner

        runner = LintRunner()
        assert runner.can_handle(Path("/tmp/test.txt")) is False


class TestVerifyFunction:
    """测试 verify 函数"""

    def test_verify_nonexistent_file(self):
        """测试验证不存在的文件"""
        result = verify(Path("/nonexistent/file.py"))
        assert result.passed is False
        # 不存在的文件无法确定验证类型，返回 FAIL
        assert result.verdict in ["FAIL", "INDETERMINATE"]
