"""Lint Runner — 代码检查运行器"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .interface import VerificationResult, VerificationRunner, VerificationType


def _resolve_bin(name: str) -> str:
    """Resolve a binary, preferring the current venv's bin/ over PATH."""
    found = shutil.which(name)
    if found:
        return found
    venv_bin = Path(sys.executable).parent / name
    if venv_bin.exists():
        return str(venv_bin)
    return name


class LintRunner(VerificationRunner):
    """运行代码检查工具"""

    LINT_COMMANDS: dict[str, list[str]] = {
        ".py": ["ruff", "check"],  # resolved lazily
        ".js": ["npx", "eslint"],
        ".ts": ["npx", "eslint"],
        ".go": ["golangci-lint", "run"],
        ".rs": ["cargo", "clippy"],
    }

    @classmethod
    def _cmd_for(cls, ext: str) -> list[str] | None:
        if ext not in cls.LINT_COMMANDS:
            return None
        cmd = list(cls.LINT_COMMANDS[ext])
        if ext == ".py":
            cmd[0] = _resolve_bin("ruff")
        return cmd

    @staticmethod
    def _find_project_root(start: Path) -> Path:
        """向上查找包含 pyproject.toml 的项目根目录，否则用 start 的父目录"""
        candidate = start if start.is_dir() else start.parent
        for d in [candidate, *candidate.parents]:
            if (d / "pyproject.toml").exists():
                return d
            if d == d.parent:  # 文件系统根
                break
        return candidate

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
                lint_cmd = self._cmd_for(ext)
                if lint_cmd is None:
                    return VerificationResult(
                        passed=False,
                        verdict="INDETERMINATE",
                        evidence=f"No linter for {ext} files",
                        verification_type=VerificationType.LINT,
                        artifact_path=artifact_path,
                        criteria_path=criteria_path,
                        notes=f"Unsupported file type: {ext}",
                    )
                cmd = [*lint_cmd, str(artifact_path)]
            else:
                # 对目录，使用第一个匹配的 linter
                cmd = None
                for ext in self.LINT_COMMANDS:
                    lint_cmd = self._cmd_for(ext)
                    if lint_cmd and any(artifact_path.rglob(f"*{ext}")):
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
            # ruff: 注入 --cache-dir，避免在非项目目录下缓存路径出错
            if cmd[0].endswith("ruff"):
                project_root = self._find_project_root(artifact_path)
                cache_dir = project_root / ".ruff_cache"
                # --cache-dir 是 check 子命令的参数，插入到 check 之后
                cmd = [cmd[0], cmd[1], "--cache-dir", str(cache_dir), *cmd[2:]]
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
