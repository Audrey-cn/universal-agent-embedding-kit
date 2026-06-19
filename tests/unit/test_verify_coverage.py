"""Tests for verify module - improving coverage"""

import tempfile
from pathlib import Path

from src.verify import VerificationResult, VerificationType, verify
from src.verify.build_runner import BuildRunner
from src.verify.fresh_context import FreshContextVerifier
from src.verify.lint_runner import LintRunner
from src.verify.test_runner import TestRunner


class TestTestRunnerCoverage:
    """TestRunner 覆盖率测试"""

    def test_run_with_test_file(self):
        """测试运行测试文件"""
        runner = TestRunner()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def test_example():\n    assert True\n")
            f.flush()
            result = runner.run(Path(f.name))
            assert isinstance(result, VerificationResult)

    def test_run_with_directory(self):
        """测试运行目录"""
        runner = TestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_example():\n    assert True\n")

            result = runner.run(Path(tmpdir))
            assert isinstance(result, VerificationResult)

    def test_can_handle_directory_with_tests(self):
        """测试能否处理包含测试的目录"""
        runner = TestRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_example():\n    pass\n")
            assert runner.can_handle(Path(tmpdir)) is True

    def test_can_handle_nonexistent(self):
        """测试能否处理不存在的路径"""
        runner = TestRunner()
        assert runner.can_handle(Path("/nonexistent")) is False


class TestBuildRunnerCoverage:
    """BuildRunner 覆盖率测试"""

    def test_run_with_package_json(self):
        """测试运行 package.json 构建"""
        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}')
            result = runner.run(Path(tmpdir))
            assert isinstance(result, VerificationResult)

    def test_run_with_makefile(self):
        """测试运行 Makefile 构建"""
        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Makefile").write_text("build:\n\techo done\n")
            result = runner.run(Path(tmpdir))
            assert isinstance(result, VerificationResult)

    def test_can_handle_various_configs(self):
        """测试能否处理各种配置"""
        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # pyproject.toml
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname='test'\n")
            assert runner.can_handle(Path(tmpdir)) is True

    def test_cannot_handle_no_config(self):
        """测试无法处理无配置的目录"""
        runner = BuildRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert runner.can_handle(Path(tmpdir)) is False


class TestLintRunnerCoverage:
    """LintRunner 覆盖率测试"""

    def test_run_with_python_file(self):
        """测试运行 Python 文件 lint"""
        runner = LintRunner()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    return 'hello'\n")
            f.flush()
            result = runner.run(Path(f.name))
            assert isinstance(result, VerificationResult)

    def test_run_with_directory(self):
        """测试运行目录 lint"""
        runner = LintRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("def hello():\n    return 'hello'\n")
            result = runner.run(Path(tmpdir))
            assert isinstance(result, VerificationResult)

    def test_can_handle_various_files(self):
        """测试能否处理各种文件"""
        runner = LintRunner()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            assert runner.can_handle(Path(f.name)) is True
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            assert runner.can_handle(Path(f.name)) is False

    def test_run_unsupported_file(self):
        """测试运行不支持的文件类型"""
        runner = LintRunner()
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("test content")
            f.flush()
            result = runner.run(Path(f.name))
            assert result.passed is False
            assert result.verdict == "INDETERMINATE"


class TestFreshContextVerifierCoverage:
    """FreshContextVerifier 覆盖率测试"""

    def test_verify_with_criteria(self):
        """测试带验收标准的验证"""
        verifier = FreshContextVerifier()
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "test.py"
            artifact.write_text("def hello():\n    return 'hello'\n")
            criteria = Path(tmpdir) / "spec.md"
            criteria.write_text("# Spec\n\nFunction should return string.")

            result = verifier.verify(artifact, criteria, VerificationType.LINT)
            assert isinstance(result, VerificationResult)

    def test_verify_nonexistent(self):
        """测试验证不存在的文件"""
        verifier = FreshContextVerifier()
        with tempfile.TemporaryDirectory() as tmpdir:
            criteria = Path(tmpdir) / "spec.md"
            criteria.write_text("# Spec")

            result = verifier.verify(Path("/nonexistent"), criteria)
            assert result.passed is False


class TestVerifyFunctionCoverage:
    """verify 函数覆盖率测试"""

    def test_verify_with_type(self):
        """测试指定验证类型"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    return 'hello'\n")
            f.flush()
            result = verify(Path(f.name), verification_type=VerificationType.LINT)
            assert isinstance(result, VerificationResult)

    def test_verify_directory(self):
        """测试验证目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("def hello():\n    return 'hello'\n")
            result = verify(Path(tmpdir))
            assert isinstance(result, VerificationResult)

    def test_verify_empty_directory(self):
        """测试验证空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify(Path(tmpdir))
            assert result.passed is False
            assert result.verdict == "INDETERMINATE"
