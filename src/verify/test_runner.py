"""Test Runner — 测试运行器"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .interface import VerificationResult, VerificationRunner, VerificationType


class TestRunner(VerificationRunner):
    """运行 pytest 测试套件"""

    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否是 Python 文件或包含测试"""
        if artifact_path.suffix == ".py":
            return True
        # 检查目录下是否有 test_*.py 文件
        if artifact_path.is_dir():
            return any(artifact_path.glob("test_*.py"))
        return False

    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行 pytest"""
        try:
            # 确定测试目标
            if artifact_path.is_file():
                test_target = str(artifact_path)
            else:
                test_target = str(artifact_path / "tests")

            # 运行 pytest
            result = subprocess.run(
                ["python", "-m", "pytest", test_target, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            passed = result.returncode == 0
            evidence = result.stdout + result.stderr

            return VerificationResult(
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                evidence=evidence,
                verification_type=VerificationType.TEST,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Exit code: {result.returncode}",
            )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence="Test execution timed out (300s)",
                verification_type=VerificationType.TEST,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Timeout after 300 seconds",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=str(e),
                verification_type=VerificationType.TEST,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Error: {e}",
            )
