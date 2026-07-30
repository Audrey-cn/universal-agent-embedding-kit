"""Fresh Context Verifier — 全新上下文验证器"""

from __future__ import annotations

import subprocess
import sys
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
            if not criteria_path.is_file():
                return VerificationResult(
                    passed=False,
                    verdict="INDETERMINATE",
                    evidence=f"Criteria file not found: {criteria_path}",
                    verification_type=verification_type,
                    artifact_path=artifact_path,
                    criteria_path=criteria_path,
                    notes="Fresh context verification requires a criteria file",
                )
            # Read the criteria to prove the verifier received an explicit spec;
            # the local command runners are still responsible for objective checks.
            criteria_path.read_text(encoding="utf-8")

            command, cwd = self._command_for(artifact_path, verification_type)
            if command is None:
                return VerificationResult(
                    passed=False,
                    verdict="INDETERMINATE",
                    evidence=f"Unknown verification type: {verification_type.value}",
                    verification_type=verification_type,
                    artifact_path=artifact_path,
                    criteria_path=criteria_path,
                    notes=f"No fresh-context runner for {verification_type.value}",
                )

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(cwd),
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

    def _command_for(
        self,
        artifact_path: Path,
        verification_type: VerificationType,
    ) -> tuple[list[str] | None, Path]:
        """Build a subprocess command without interpolating untrusted text into code."""
        cwd = artifact_path if artifact_path.is_dir() else artifact_path.parent
        if verification_type == VerificationType.TEST:
            return [sys.executable, "-m", "pytest", str(artifact_path), "-v"], cwd
        if verification_type == VerificationType.BUILD:
            return [sys.executable, "-m", "build"], cwd
        if verification_type == VerificationType.LINT:
            cache_dir = self._project_root(artifact_path) / ".ruff_cache"
            return [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--cache-dir",
                str(cache_dir),
                str(artifact_path),
            ], cwd
        return None, cwd

    def _project_root(self, start: Path) -> Path:
        candidate = start if start.is_dir() else start.parent
        for path in [candidate, *candidate.parents]:
            if (path / "pyproject.toml").exists():
                return path
            if path == path.parent:
                break
        return candidate
