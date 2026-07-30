"""Diff Verification Runner — 差异验证运行器

DIFF 验证类型（EMBEDDABLE_TARGETS.md 目标1）：
- 与规格对比
- 将产出物与验收标准/规格文档进行比对
- 检查是否满足规格要求
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from .interface import VerificationResult, VerificationRunner, VerificationType


class DiffRunner(VerificationRunner):
    """差异验证运行器

    验证策略：
    1. 对比产出物与规格文档
    2. 支持文本差异、JSON 结构差异、键值对差异
    3. 检查覆盖率（产出物是否覆盖了规格要求的所有点）
    """

    SUPPORTED_EXTENSIONS = {
        ".txt", ".md", ".py", ".ts", ".js", ".json", ".yaml", ".yml",
        ".html", ".css", ".toml", ".ini", ".cfg",
    }

    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否能处理该文件类型"""
        return artifact_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行差异验证"""
        if criteria_path is None:
            return VerificationResult(
                passed=False,
                verdict="INDETERMINATE",
                evidence="DIFF verification requires a criteria/spec file",
                verification_type=VerificationType.DIFF,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="No criteria_path provided for diff comparison",
            )

        if not criteria_path.exists():
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Criteria file not found: {criteria_path}",
                verification_type=VerificationType.DIFF,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes="Criteria file does not exist",
            )

        try:
            artifact_content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False, verdict="FAIL",
                evidence=f"Cannot read artifact: {e}",
                verification_type=VerificationType.DIFF,
                artifact_path=artifact_path, criteria_path=criteria_path,
                notes=f"Artifact read error: {e}",
            )

        try:
            criteria_text = criteria_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False, verdict="FAIL",
                evidence=f"Cannot read criteria: {e}",
                verification_type=VerificationType.DIFF,
                artifact_path=artifact_path, criteria_path=criteria_path,
                notes=f"Criteria read error: {e}",
            )

        # 根据 criteria 文件类型选择策略
        if criteria_path.suffix == ".json":
            return self._diff_json(criteria_text, artifact_content, artifact_path, criteria_path)
        else:
            return self._diff_text(criteria_text, artifact_content, artifact_path, criteria_path)

    def _diff_json(
        self,
        criteria_text: str,
        artifact_content: str,
        artifact_path: Path,
        criteria_path: Path,
    ) -> VerificationResult:
        """JSON 结构差异对比"""
        checks: list[dict[str, Any]] = []
        all_passed = True

        try:
            criteria = json.loads(criteria_text)
        except json.JSONDecodeError as e:
            return VerificationResult(
                passed=False, verdict="FAIL",
                evidence=f"Invalid criteria JSON: {e}",
                verification_type=VerificationType.DIFF,
                artifact_path=artifact_path, criteria_path=criteria_path,
                notes="Criteria is not valid JSON",
            )

        try:
            artifact = json.loads(artifact_content)
        except json.JSONDecodeError:
            # 如果 artifact 不是 JSON，尝试作为文本对比
            return self._diff_text(criteria_text, artifact_content, artifact_path, criteria_path)

        # 检查 criteria 中的 key 是否都在 artifact 中存在
        if isinstance(criteria, dict):
            if not isinstance(artifact, dict):
                return VerificationResult(
                    passed=False,
                    verdict="FAIL",
                    evidence=(
                        "JSON shape mismatch: criteria is an object but artifact "
                        f"is {type(artifact).__name__}"
                    ),
                    verification_type=VerificationType.DIFF,
                    artifact_path=artifact_path,
                    criteria_path=criteria_path,
                    notes="Artifact JSON must be an object for object criteria",
                )
            missing_keys = [k for k in criteria if k not in artifact]
            extra_keys = [k for k in artifact if k not in criteria]
            checks.append({
                "check": "json_keys_coverage",
                "passed": len(missing_keys) == 0,
                "details": {"missing": missing_keys, "extra": extra_keys},
            })
            if missing_keys:
                all_passed = False

            # 值匹配检查
            mismatches = []
            for key in criteria:
                if key in artifact:
                    if criteria[key] != artifact[key]:
                        mismatches.append({
                            "key": key,
                            "expected": criteria[key],
                            "actual": artifact[key],
                        })
            checks.append({
                "check": "json_values_match",
                "passed": len(mismatches) == 0,
                "details": {"mismatches": mismatches},
            })
            if mismatches:
                all_passed = False

        elif isinstance(criteria, list):
            # 检查列表元素覆盖率
            if isinstance(artifact, list):
                missing_items = [item for item in criteria if item not in artifact]
                checks.append({
                    "check": "json_list_coverage",
                    "passed": len(missing_items) == 0,
                    "details": {"missing": missing_items},
                })
                if missing_items:
                    all_passed = False
            else:
                return VerificationResult(
                    passed=False,
                    verdict="FAIL",
                    evidence=(
                        "JSON shape mismatch: criteria is a list but artifact "
                        f"is {type(artifact).__name__}"
                    ),
                    verification_type=VerificationType.DIFF,
                    artifact_path=artifact_path,
                    criteria_path=criteria_path,
                    notes="Artifact JSON must be a list for list criteria",
                )

        verdict = "PASS" if all_passed else "FAIL"
        evidence = (
            f"JSON diff: {len(checks)} checks, "
            f"{sum(1 for c in checks if c['passed'])} passed, "
            f"{sum(1 for c in checks if not c['passed'])} failed"
        )
        return VerificationResult(
            passed=all_passed,
            verdict=verdict,
            evidence=evidence,
            verification_type=VerificationType.DIFF,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=json.dumps(checks, ensure_ascii=False),
        )

    def _diff_text(
        self,
        criteria_text: str,
        artifact_content: str,
        artifact_path: Path,
        criteria_path: Path,
    ) -> VerificationResult:
        """文本差异对比"""
        checks: list[dict[str, Any]] = []
        all_passed = True

        # 1. 计算相似度
        criteria_lines = criteria_text.splitlines()
        artifact_lines = artifact_content.splitlines()

        matcher = difflib.SequenceMatcher(None, criteria_lines, artifact_lines)
        similarity = matcher.ratio()
        checks.append({
            "check": "text_similarity",
            "passed": similarity >= 0.5,
            "details": {"similarity": round(similarity, 4)},
        })
        if similarity < 0.5:
            all_passed = False

        # 2. 生成 unified diff
        diff = list(difflib.unified_diff(
            criteria_lines,
            artifact_lines,
            fromfile=f"spec/{criteria_path.name}",
            tofile=f"artifact/{artifact_path.name}",
            lineterm="",
        ))

        # 3. 检查规格中的关键要求是否在产出物中
        # 提取规格中的 checklist 项（以 - [ ] 或 * [ ] 开头的行）
        checklist_items = []
        for line in criteria_lines:
            stripped = line.strip()
            if stripped.startswith(("- [ ]", "* [ ]", "- [x]", "* [x]", "- [X]", "* [X]")):
                checklist_items.append(stripped)

        if checklist_items:
            artifact_lower = artifact_content.lower()
            covered = 0
            uncovered = []
            for item in checklist_items:
                # 提取 checklist 的描述文本
                desc = item[5:].strip().lower() if len(item) > 5 else ""
                if desc and desc in artifact_lower:
                    covered += 1
                elif desc:
                    uncovered.append(desc)

            coverage_rate = covered / len(checklist_items) if checklist_items else 1.0
            checks.append({
                "check": "checklist_coverage",
                "passed": coverage_rate >= 0.8,
                "details": {
                    "total": len(checklist_items),
                    "covered": covered,
                    "uncovered": uncovered,
                    "coverage_rate": round(coverage_rate, 4),
                },
            })
            if coverage_rate < 0.8:
                all_passed = False

        # 4. 检查规格中的关键词是否在产出物中
        # 提取规格中的标题行作为关键要求
        spec_keywords = []
        for line in criteria_lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # 提取标题中的关键词
                title = stripped.lstrip("#").strip()
                if title and len(title) > 3:
                    spec_keywords.append(title.lower())

        if spec_keywords:
            artifact_lower = artifact_content.lower()
            found_keywords = 0
            missing_keywords = []
            for kw in spec_keywords:
                if kw in artifact_lower:
                    found_keywords += 1
                else:
                    missing_keywords.append(kw)

            kw_coverage = found_keywords / len(spec_keywords) if spec_keywords else 1.0
            checks.append({
                "check": "keyword_coverage",
                "passed": kw_coverage >= 0.6,
                "details": {
                    "total": len(spec_keywords),
                    "found": found_keywords,
                    "missing": missing_keywords,
                    "coverage_rate": round(kw_coverage, 4),
                },
            })
            if kw_coverage < 0.6:
                all_passed = False

        verdict = "PASS" if all_passed else "FAIL"
        diff_summary = f"{len(diff)} diff lines" if diff else "no differences"
        evidence = (
            f"Text diff: similarity={similarity:.2%}, {diff_summary}, "
            f"{len(checks)} checks, "
            f"{sum(1 for c in checks if c['passed'])} passed"
        )

        return VerificationResult(
            passed=all_passed,
            verdict=verdict,
            evidence=evidence,
            verification_type=VerificationType.DIFF,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=json.dumps({
                "similarity": similarity,
                "diff_lines": len(diff),
                "checks": checks,
            }, ensure_ascii=False),
        )
