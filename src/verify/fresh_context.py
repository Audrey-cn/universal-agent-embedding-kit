"""Fresh Context Verifier — 全新上下文验证器"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .interface import VerificationResult, VerificationType


class FreshContextVerifier:
    """
    全新上下文验证器。

    核心原则：验证者不继承执行者的上下文。
    "만든 쪽의 컨텍스트를 물려받은 검증자는 같은 맹점을 공유한다"
    （A verifier that inherited the maker's context shares the same blind spots）
    """

    def verify(
        self,
        artifact_path: Path,
        criteria_path: Path,
        verification_type: VerificationType = VerificationType.TEST,
    ) -> VerificationResult:
        """
        在全新上下文中验证产出物。

        Args:
            artifact_path: 产出物路径
            criteria_path: 验收标准路径
            verification_type: 验证类型

        Returns:
            VerificationResult: 验证结果
        """
        try:
            # 读取验收标准
            criteria_text = criteria_path.read_text()

            # 构建验证脚本
            verify_script = self._build_verify_script(
                artifact_path, criteria_text, verification_type
            )

            # 在全新进程中运行验证（不继承当前上下文）
            result = subprocess.run(
                ["python", "-c", verify_script],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(artifact_path.parent),
            )

            passed = result.returncode == 0
            evidence = result.stdout + result.stderr

            return VerificationResult(
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                evidence=evidence,
                verification_type=verification_type,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Fresh context verification",
            )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence="Verification timed out (300s)",
                verification_type=verification_type,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Timeout after 300 seconds",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=str(e),
                verification_type=verification_type,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Error: {e}",
            )

    def _build_verify_script(
        self,
        artifact_path: Path,
        criteria_text: str,
        verification_type: VerificationType,
    ) -> str:
        """构建验证脚本"""
        return f"""
import sys
import subprocess
from pathlib import Path

artifact = Path("{artifact_path}")
criteria = '''{criteria_text}'''

# 检查产出物是否存在
if not artifact.exists():
    print(f"FAIL: Artifact not found: {{artifact}}")
    sys.exit(1)

# 根据验证类型运行检查
if "{verification_type.value}" == "test":
    result = subprocess.run(
        ["python", "-m", "pytest", str(artifact), "-v"],
        capture_output=True, text=True
    )
    print(result.stdout)
    print(result.stderr)
    sys.exit(result.returncode)

elif "{verification_type.value}" == "build":
    result = subprocess.run(
        ["python", "-m", "build"],
        capture_output=True, text=True, cwd=str(artifact.parent)
    )
    print(result.stdout)
    print(result.stderr)
    sys.exit(result.returncode)

elif "{verification_type.value}" == "lint":
    result = subprocess.run(
        ["python", "-m", "ruff", "check", str(artifact)],
        capture_output=True, text=True
    )
    print(result.stdout)
    print(result.stderr)
    sys.exit(result.returncode)

else:
    print(f"INDETERMINATE: Unknown verification type: {verification_type.value}")
    sys.exit(2)
"""
