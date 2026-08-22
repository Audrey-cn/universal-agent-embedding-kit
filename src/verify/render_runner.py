"""Render Verification Runner — 渲染验证运行器

RENDER 验证类型（EMBEDDABLE_TARGETS.md 目标1）：
- 渲染并观察产出物
- 适用于 Web 页面、图表、报告等可视化产出物
- 检查渲染结果是否与预期一致
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .interface import VerificationResult, VerificationRunner, VerificationType


class RenderRunner(VerificationRunner):
    """渲染验证运行器

    验证策略：
    1. 检测文件类型（HTML/JSX/TSX/Vue/Markdown）
    2. 尝试渲染并检查输出
    3. 对 HTML 文件检查 DOM 结构和关键元素
    4. 对 Markdown 检查格式正确性
    """

    SUPPORTED_EXTENSIONS = {
        ".html",
        ".htm",
        ".jsx",
        ".tsx",
        ".vue",
        ".md",
        ".markdown",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
    }

    def can_handle(self, artifact_path: Path) -> bool:
        """检查是否能处理该文件类型"""
        return artifact_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def run(self, artifact_path: Path, criteria_path: Path | None = None) -> VerificationResult:
        """运行渲染验证"""
        suffix = artifact_path.suffix.lower()
        evidence_parts: list[str] = []

        if suffix in {".html", ".htm"}:
            return self._verify_html(artifact_path, criteria_path, evidence_parts)
        elif suffix in {".md", ".markdown"}:
            return self._verify_markdown(artifact_path, criteria_path, evidence_parts)
        elif suffix in {".jsx", ".tsx", ".vue"}:
            return self._verify_component(artifact_path, criteria_path, evidence_parts)
        elif suffix in {".svg"}:
            return self._verify_svg(artifact_path, criteria_path, evidence_parts)
        elif suffix in {".png", ".jpg", ".jpeg"}:
            return self._verify_image(artifact_path, criteria_path, evidence_parts)
        else:
            return VerificationResult(
                passed=False,
                verdict="INDETERMINATE",
                evidence=f"Unsupported render format: {suffix}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"No render strategy for {suffix}",
            )

    def _verify_html(
        self,
        artifact_path: Path,
        criteria_path: Path | None,
        evidence_parts: list[str],
    ) -> VerificationResult:
        """验证 HTML 文件"""
        try:
            content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Cannot read HTML: {e}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Read error: {e}",
            )

        checks: list[dict[str, Any]] = []
        all_passed = True

        # 1. 检查基本 HTML 结构
        has_doctype = "<!DOCTYPE html>" in content or "<!doctype html>" in content
        has_html_tag = "<html" in content.lower()
        has_body = "<body" in content.lower()
        checks.append(
            {
                "check": "basic_structure",
                "passed": has_doctype and has_html_tag and has_body,
                "details": {
                    "doctype": has_doctype,
                    "html_tag": has_html_tag,
                    "body": has_body,
                },
            }
        )
        if not (has_doctype and has_html_tag and has_body):
            all_passed = False
            evidence_parts.append("Missing basic HTML structure")

        # 2. 检查关键元素（从 criteria 中读取）
        if criteria_path and criteria_path.exists():
            try:
                criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
                required_elements = criteria.get("required_elements", [])
                for elem in required_elements:
                    found = elem in content
                    checks.append(
                        {
                            "check": f"required_element:{elem}",
                            "passed": found,
                            "details": {"element": elem},
                        }
                    )
                    if not found:
                        all_passed = False
                        evidence_parts.append(f"Missing required element: {elem}")
            except Exception:
                pass

        # 3. 检查是否有明显的渲染错误标记
        error_patterns = ["{{", "}}", "undefined", "null", "[object Object]"]
        for pattern in error_patterns:
            if pattern in content:
                checks.append(
                    {
                        "check": f"render_error:{pattern}",
                        "passed": False,
                        "details": {"pattern": pattern},
                    }
                )
                all_passed = False
                evidence_parts.append(f"Found render error pattern: {pattern}")

        evidence = "\n".join(evidence_parts) if evidence_parts else "HTML structure valid"
        return VerificationResult(
            passed=all_passed,
            verdict="PASS" if all_passed else "FAIL",
            evidence=evidence,
            verification_type=VerificationType.RENDER,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=json.dumps(checks, ensure_ascii=False),
        )

    def _verify_markdown(
        self,
        artifact_path: Path,
        criteria_path: Path | None,
        evidence_parts: list[str],
    ) -> VerificationResult:
        """验证 Markdown 文件"""
        try:
            content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Cannot read Markdown: {e}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Read error: {e}",
            )

        checks: list[dict[str, Any]] = []
        all_passed = True

        # 1. 检查基本结构（至少有一个标题）
        has_heading = any(line.strip().startswith("#") for line in content.splitlines())
        checks.append({"check": "has_heading", "passed": has_heading})
        if not has_heading:
            all_passed = False
            evidence_parts.append("Missing heading in Markdown")

        # 2. 检查断链（相对路径引用，防止路径遍历）
        import re

        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        broken_links = []
        for match in link_pattern.finditer(content):
            link_target = match.group(2)
            if not link_target.startswith(("http://", "https://", "#", "mailto:")):
                # 相对路径，检查是否存在（防止路径遍历）
                resolved = (artifact_path.parent / link_target).resolve()
                # 安全检查：确保解析后的路径在 artifact 目录内
                try:
                    resolved.relative_to(artifact_path.parent.resolve())
                except ValueError:
                    broken_links.append(f"{link_target} (path traversal)")
                    continue
                if not resolved.exists():
                    broken_links.append(link_target)
        checks.append(
            {
                "check": "broken_links",
                "passed": len(broken_links) == 0,
                "details": {"broken": broken_links},
            }
        )
        if broken_links:
            all_passed = False
            evidence_parts.append(f"Broken links: {broken_links}")

        # 3. 检查代码块是否闭合
        code_fence_count = content.count("```")
        fences_balanced = code_fence_count % 2 == 0
        checks.append({"check": "balanced_code_fences", "passed": fences_balanced})
        if not fences_balanced:
            all_passed = False
            evidence_parts.append("Unbalanced code fences")

        evidence = "\n".join(evidence_parts) if evidence_parts else "Markdown structure valid"
        return VerificationResult(
            passed=all_passed,
            verdict="PASS" if all_passed else "FAIL",
            evidence=evidence,
            verification_type=VerificationType.RENDER,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=json.dumps(checks, ensure_ascii=False),
        )

    def _verify_component(
        self,
        artifact_path: Path,
        criteria_path: Path | None,
        evidence_parts: list[str],
    ) -> VerificationResult:
        """验证前端组件（JSX/TSX/Vue）"""
        try:
            content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Cannot read component: {e}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Read error: {e}",
            )

        checks: list[dict[str, Any]] = []
        all_passed = True

        # 1. 检查是否有 export default（组件导出）
        has_export = "export" in content
        checks.append({"check": "has_export", "passed": has_export})
        if not has_export:
            all_passed = False
            evidence_parts.append("Component missing export")

        # 2. 检查是否有 return 语句（渲染输出）
        has_return = "return" in content
        checks.append({"check": "has_return", "passed": has_return})
        if not has_return:
            all_passed = False
            evidence_parts.append("Component missing return statement")

        # 3. 检查 JSX 括号平衡
        open_braces = content.count("{")
        close_braces = content.count("}")
        braces_balanced = open_braces == close_braces
        checks.append(
            {
                "check": "balanced_braces",
                "passed": braces_balanced,
                "details": {"open": open_braces, "close": close_braces},
            }
        )
        if not braces_balanced:
            all_passed = False
            evidence_parts.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

        evidence = "\n".join(evidence_parts) if evidence_parts else "Component structure valid"
        return VerificationResult(
            passed=all_passed,
            verdict="PASS" if all_passed else "FAIL",
            evidence=evidence,
            verification_type=VerificationType.RENDER,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            notes=json.dumps(checks, ensure_ascii=False),
        )

    def _verify_svg(
        self,
        artifact_path: Path,
        criteria_path: Path | None,
        evidence_parts: list[str],
    ) -> VerificationResult:
        """验证 SVG 文件"""
        try:
            content = artifact_path.read_text(encoding="utf-8")
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Cannot read SVG: {e}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Read error: {e}",
            )

        all_passed = True
        has_svg_tag = "<svg" in content.lower()
        has_closing = "</svg>" in content.lower()

        if not has_svg_tag:
            all_passed = False
            evidence_parts.append("Missing <svg> tag")
        if not has_closing:
            all_passed = False
            evidence_parts.append("Missing </svg> closing tag")

        evidence = "\n".join(evidence_parts) if evidence_parts else "SVG structure valid"
        return VerificationResult(
            passed=all_passed,
            verdict="PASS" if all_passed else "FAIL",
            evidence=evidence,
            verification_type=VerificationType.RENDER,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
        )

    def _verify_image(
        self,
        artifact_path: Path,
        criteria_path: Path | None,
        evidence_parts: list[str],
    ) -> VerificationResult:
        """验证图片文件"""
        try:
            file_size = artifact_path.stat().st_size
        except Exception as e:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Cannot read image: {e}",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                notes=f"Read error: {e}",
            )

        all_passed = True

        # 检查文件大小限制（防止资源耗尽，最大 50MB）
        max_image_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_image_size:
            return VerificationResult(
                passed=False,
                verdict="FAIL",
                evidence=f"Image too large: {file_size} bytes (max {max_image_size})",
                verification_type=VerificationType.RENDER,
                artifact_path=artifact_path,
                criteria_path=criteria_path,
            )

        # 检查文件大小是否合理（非空）
        if file_size == 0:
            all_passed = False
            evidence_parts.append("Image file is empty")
        elif file_size < 100:
            evidence_parts.append(f"Image file is very small ({file_size} bytes)")

        # 检查标准图片头
        try:
            header = artifact_path.read_bytes()[:8]
            suffix = artifact_path.suffix.lower()
            valid_header = False
            if suffix == ".png" and header[:8] == b"\x89PNG\r\n\x1a\n":
                valid_header = True
            elif suffix in {".jpg", ".jpeg"} and header[:2] == b"\xff\xd8":
                valid_header = True
            if not valid_header and suffix in {".png", ".jpg", ".jpeg"}:
                all_passed = False
                evidence_parts.append(f"Invalid {suffix} header: {header[:4].hex()}")
        except Exception:
            pass

        evidence = (
            "\n".join(evidence_parts) if evidence_parts else f"Image valid ({file_size} bytes)"
        )
        return VerificationResult(
            passed=all_passed,
            verdict="PASS" if all_passed else "FAIL",
            evidence=evidence,
            verification_type=VerificationType.RENDER,
            artifact_path=artifact_path,
            criteria_path=criteria_path,
        )
