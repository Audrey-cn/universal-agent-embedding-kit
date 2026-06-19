"""Key Information Extractor — 关键信息提取器"""

from __future__ import annotations

import re

from .interface import MemoryEntry, MemoryLayerType


class KeyInfoExtractor:
    """关键信息提取器"""

    # 决策关键词
    DECISION_PATTERNS = [
        r"decided to",
        r"chose to",
        r"selected",
        r"determined",
        r"决定",
        r"选择",
        r"确定",
    ]

    # 约束关键词
    CONSTRAINT_PATTERNS = [
        r"must",
        r"required",
        r"constraint",
        r"limitation",
        r"restriction",
        r"必须",
        r"约束",
        r"限制",
    ]

    # 错误关键词
    ERROR_PATTERNS = [
        r"error",
        r"failed",
        r"bug",
        r"issue",
        r"problem",
        r"错误",
        r"失败",
        r"问题",
    ]

    # 需求关键词
    REQUIREMENT_PATTERNS = [
        r"requirement",
        r"specification",
        r"feature",
        r"need",
        r"需求",
        r"规格",
        r"功能",
    ]

    def extract_decisions(self, content: str) -> list[str]:
        """提取决策"""
        decisions = []
        for pattern in self.DECISION_PATTERNS:
            matches = re.findall(f".*{pattern}.*", content, re.IGNORECASE)
            decisions.extend(matches)
        return decisions

    def extract_constraints(self, content: str) -> list[str]:
        """提取约束"""
        constraints = []
        for pattern in self.CONSTRAINT_PATTERNS:
            matches = re.findall(f".*{pattern}.*", content, re.IGNORECASE)
            constraints.extend(matches)
        return constraints

    def extract_errors(self, content: str) -> list[str]:
        """提取错误"""
        errors = []
        for pattern in self.ERROR_PATTERNS:
            matches = re.findall(f".*{pattern}.*", content, re.IGNORECASE)
            errors.extend(matches)
        return errors

    def extract_requirements(self, content: str) -> list[str]:
        """提取需求"""
        requirements = []
        for pattern in self.REQUIREMENT_PATTERNS:
            matches = re.findall(f".*{pattern}.*", content, re.IGNORECASE)
            requirements.extend(matches)
        return requirements

    def extract_all(self, content: str) -> dict[str, list[str]]:
        """提取所有关键信息"""
        return {
            "decisions": self.extract_decisions(content),
            "constraints": self.extract_constraints(content),
            "errors": self.extract_errors(content),
            "requirements": self.extract_requirements(content),
        }

    def calculate_importance(self, content: str) -> float:
        """计算内容重要性"""
        score = 0.5  # 基础分数

        # 决策加权
        decisions = self.extract_decisions(content)
        score += len(decisions) * 0.1

        # 约束加权
        constraints = self.extract_constraints(content)
        score += len(constraints) * 0.1

        # 错误加权
        errors = self.extract_errors(content)
        score += len(errors) * 0.15

        # 需求加权
        requirements = self.extract_requirements(content)
        score += len(requirements) * 0.1

        return min(1.0, max(0.0, score))

    def extract_tags(self, content: str) -> list[str]:
        """提取标签"""
        tags = []

        if self.extract_decisions(content):
            tags.append("decision")
        if self.extract_constraints(content):
            tags.append("constraint")
        if self.extract_errors(content):
            tags.append("error")
        if self.extract_requirements(content):
            tags.append("requirement")

        return tags

    def create_memory_entry(
        self,
        content: str,
        layer: MemoryLayerType,
        entry_id: str,
    ) -> MemoryEntry:
        """创建记忆条目"""
        importance = self.calculate_importance(content)
        tags = self.extract_tags(content)

        return MemoryEntry(
            id=entry_id,
            content=content,
            layer=layer,
            importance=importance,
            tags=tags,
        )
