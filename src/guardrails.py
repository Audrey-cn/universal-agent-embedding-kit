"""Guardrails — 安全防护"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardrailRule:
    """防护规则"""

    name: str
    description: str
    rule_type: str  # input, output, both
    severity: str  # low, medium, high, critical
    pattern: str | None = None  # 正则表达式
    keywords: list[str] = field(default_factory=list)
    action: str = "block"  # block, warn, log

    def matches(self, text: str) -> bool:
        """检查是否匹配"""
        text_lower = text.lower()

        # 检查关键词
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                return True

        # 检查正则表达式
        if self.pattern:
            if re.search(self.pattern, text, re.IGNORECASE):
                return True

        return False


class InputFilter:
    """输入过滤器"""

    def __init__(self):
        self.rules: list[GuardrailRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认规则"""
        # 注入检测
        self.rules.append(
            GuardrailRule(
                name="injection_detection",
                description="检测提示注入",
                rule_type="input",
                severity="high",
                keywords=[
                    "ignore previous instructions",
                    "ignore above",
                    "disregard",
                    "forget your instructions",
                    "you are now",
                    "new instructions",
                ],
                action="block",
            )
        )

        # 敏感信息检测
        self.rules.append(
            GuardrailRule(
                name="sensitive_info",
                description="检测敏感信息",
                rule_type="input",
                severity="medium",
                pattern=r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
                action="warn",
            )
        )

        # 恶意命令检测
        self.rules.append(
            GuardrailRule(
                name="malicious_command",
                description="检测恶意命令",
                rule_type="input",
                severity="critical",
                keywords=[
                    "rm -rf /",
                    "format c:",
                    "del /s /q",
                    "shutdown -s",
                ],
                action="block",
            )
        )

    def check(self, text: str) -> list[GuardrailRule]:
        """检查输入"""
        violations = []
        for rule in self.rules:
            if rule.rule_type in ("input", "both"):
                if rule.matches(text):
                    violations.append(rule)
        return violations

    def add_rule(self, rule: GuardrailRule):
        """添加规则"""
        self.rules.append(rule)


class OutputFilter:
    """输出过滤器"""

    def __init__(self):
        self.rules: list[GuardrailRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认规则"""
        # API 密钥泄露
        self.rules.append(
            GuardrailRule(
                name="api_key_leak",
                description="检测 API 密钥泄露",
                rule_type="output",
                severity="critical",
                pattern=r"(sk-[a-zA-Z0-9]{20,}|api[_-]?key[=:]\s*['\"][^'\"]+['\"])",
                action="block",
            )
        )

        # 密码泄露
        self.rules.append(
            GuardrailRule(
                name="password_leak",
                description="检测密码泄露",
                rule_type="output",
                severity="high",
                pattern=r"(password[=:]\s*['\"][^'\"]+['\"]|passwd[=:]\s*['\"][^'\"]+['\"])",
                action="block",
            )
        )

        # 私钥泄露
        self.rules.append(
            GuardrailRule(
                name="private_key_leak",
                description="检测私钥泄露",
                rule_type="output",
                severity="critical",
                keywords=[
                    "BEGIN RSA PRIVATE KEY",
                    "BEGIN DSA PRIVATE KEY",
                    "BEGIN EC PRIVATE KEY",
                    "BEGIN OPENSSH PRIVATE KEY",
                ],
                action="block",
            )
        )

    def check(self, text: str) -> list[GuardrailRule]:
        """检查输出"""
        violations = []
        for rule in self.rules:
            if rule.rule_type in ("output", "both"):
                if rule.matches(text):
                    violations.append(rule)
        return violations

    def add_rule(self, rule: GuardrailRule):
        """添加规则"""
        self.rules.append(rule)


@dataclass
class Requirement:
    """需求"""

    id: str
    description: str
    priority: str  # low, medium, high, critical
    status: str = "pending"  # pending, implemented, verified, failed
    artifacts: list[str] = field(default_factory=list)
    test_cases: list[str] = field(default_factory=list)


class RequirementTracer:
    """需求追踪器"""

    def __init__(self):
        self.requirements: dict[str, Requirement] = {}

    def add_requirement(self, req: Requirement):
        """添加需求"""
        self.requirements[req.id] = req

    def update_status(
        self,
        req_id: str,
        status: str,
        artifact: str | None = None,
        test_case: str | None = None,
    ):
        """更新状态"""
        if req_id in self.requirements:
            req = self.requirements[req_id]
            req.status = status
            if artifact:
                req.artifacts.append(artifact)
            if test_case:
                req.test_cases.append(test_case)

    def get_requirements(self, status: str | None = None) -> list[Requirement]:
        """获取需求"""
        if status:
            return [r for r in self.requirements.values() if r.status == status]
        return list(self.requirements.values())

    def get_coverage(self) -> dict[str, Any]:
        """获取覆盖率"""
        total = len(self.requirements)
        if total == 0:
            return {"total": 0, "implemented": 0, "verified": 0, "coverage": 0.0}

        implemented = sum(
            1 for r in self.requirements.values() if r.status in ("implemented", "verified")
        )
        verified = sum(1 for r in self.requirements.values() if r.status == "verified")

        return {
            "total": total,
            "implemented": implemented,
            "verified": verified,
            "coverage": verified / total if total > 0 else 0.0,
        }

    def trace(self, req_id: str) -> dict[str, Any]:
        """追踪需求"""
        if req_id not in self.requirements:
            return {"error": "Requirement not found"}

        req = self.requirements[req_id]
        return {
            "id": req.id,
            "description": req.description,
            "priority": req.priority,
            "status": req.status,
            "artifacts": req.artifacts,
            "test_cases": req.test_cases,
        }


class GuardrailsSystem:
    """安全防护系统"""

    def __init__(self):
        self.input_filter = InputFilter()
        self.output_filter = OutputFilter()
        self.requirement_tracer = RequirementTracer()

    def check_input(self, text: str) -> list[GuardrailRule]:
        """检查输入"""
        return self.input_filter.check(text)

    def check_output(self, text: str) -> list[GuardrailRule]:
        """检查输出"""
        return self.output_filter.check(text)

    def add_requirement(self, req: Requirement):
        """添加需求"""
        self.requirement_tracer.add_requirement(req)

    def update_requirement(self, req_id: str, status: str, artifact: str | None = None):
        """更新需求"""
        self.requirement_tracer.update_status(req_id, status, artifact)

    def get_report(self) -> dict[str, Any]:
        """获取报告"""
        return {
            "input_rules": len(self.input_filter.rules),
            "output_rules": len(self.output_filter.rules),
            "requirements": self.requirement_tracer.get_coverage(),
        }
