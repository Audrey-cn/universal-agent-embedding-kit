"""Build Runner — 构建运行器"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .interface import VerificationResult, VerificationRunner, VerificationType


class BuildRunner(VerificationRunner):
    """运行构建命令"""

    BUILD_COMMANDS = {
        "pyproject.toml": ["python", "-m", "build"],
        "package.json": ["npm", "run", "build"],
        "Makefile": ["make", "build"],
        "Cargo.toml": ["cargo", "build"],
        "go.mod": ["go", "build", "./..."],
    }

    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否有构建配置"""
        if artifact_path.is_dir():
            for config_file in self.BUILD_COMMANDS:
                if (artifact_path / config_file).exists():
                    return True
        return False

    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行构建"""
        try:
            # 查找构建命令
            build_cmd = None
            for config_file, cmd in self.BUILD_COMMANDS.items():
                if (artifact_path / config_file).exists():
                    build_cmd = cmd
                    break

            if not build_cmd:
                return VerificationResult(
                    passed=False,
                    verdict="INDETERMINATE",
                    evidence="No build configuration found",
                    verification_type=VerificationType.BUILD,
                    artifact_path=artifact_path,
                    criteria_path=criteria_path,
                    notes="Cannot determine build system",
                )

            # 运行构建
            result = subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(artifact_path),
            )

            passed = result.returncode == 0
            evidence = result.stdout + result.stderr

            return VerificationResult(
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                evidence=evidence,
                verification_type=VerificationType.BUILD,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Command: {' '.join(build_cmd)}, Exit code: {result.returncode}",
            )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence="Build timed out (600s)",
                verification_type=VerificationType.BUILD,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Timeout after 600 seconds",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=str(e),
                verification_type=VerificationType.BUILD,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Error: {e}",
            )
