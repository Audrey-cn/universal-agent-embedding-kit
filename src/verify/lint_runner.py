"""Lint Runner — 代码检查运行器"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .interface import VerificationResult, VerificationRunner, VerificationType


class LintRunner(VerificationRunner):
    """运行代码检查工具"""

    LINT_COMMANDS = {
        ".py": ["ruff", "check"],
        ".js": ["npx", "eslint"],
        ".ts": ["npx", "eslint"],
        ".go": ["golangci-lint", "run"],
        ".rs": ["cargo", "clippy"],
    }

    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否有对应的 linter"""
        if artifact_path.is_file():
            return artifact_path.suffix in self.LINT_COMMANDS
        if artifact_path.is_dir():
            # 检查目录下是否有对应文件
            for ext in self.LINT_COMMANDS:
                if any(artifact_path.rglob(f"*{ext}")):
                    return True
        return False

    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行 linter"""
        try:
            # 确定 linter 命令
            cmd: list[str] | None
            if artifact_path.is_file():
                ext = artifact_path.suffix
                if ext not in self.LINT_COMMANDS:
                    return VerificationResult(
                        passed=False,
                        verdict="INDETERMINATE",
                        evidence=f"No linter for {ext} files",
                        verification_type=VerificationType.LINT,
                        artifact_path=artifact_path,
                        criteria_path=criteria_path,
                        notes=f"Unsupported file type: {ext}",
                    )
                cmd = [*self.LINT_COMMANDS[ext], str(artifact_path)]
            else:
                # 对目录，使用第一个匹配的 linter
                cmd = None
                for ext, lint_cmd in self.LINT_COMMANDS.items():
                    if any(artifact_path.rglob(f"*{ext}")):
                        cmd = [*lint_cmd, str(artifact_path)]
                        break

                if cmd is None:
                    return VerificationResult(
                        passed=False,
                        verdict="INDETERMINATE",
                        evidence="No source files found",
                        verification_type=VerificationType.LINT,
                        artifact_path=artifact_path,
                        criteria_path=criteria_path,
                        notes="No source files to lint",
                    )

            # 运行 linter
            assert cmd is not None
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # linter 返回 0 表示无问题
            passed = result.returncode == 0
            evidence = result.stdout + result.stderr

            return VerificationResult(
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                evidence=evidence,
                verification_type=VerificationType.LINT,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Command: {' '.join(cmd)}, Exit code: {result.returncode}",
            )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence="Lint timed out (120s)",
                verification_type=VerificationType.LINT,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Timeout after 120 seconds",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=str(e),
                verification_type=VerificationType.LINT,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Error: {e}",
            )
