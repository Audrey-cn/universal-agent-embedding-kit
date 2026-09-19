"""Complexity Metrics — 复杂度指标"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ComplexityMetrics:
    """复杂度指标"""

    file_count: int  # 涉及文件数
    dependency_depth: int  # 依赖深度
    ambiguity: float  # 模糊度 0.0-1.0
    reversibility: float  # 可逆度 0.0-1.0
    task_type: str  # 任务类型
    keyword_complexity: float  # 关键词复杂度 0.0-1.0

    @classmethod
    def from_task(
        cls,
        task_description: str,
        file_count: int | None = None,
        dependency_depth: int | None = None,
        ambiguity: float | None = None,
        reversibility: float | None = None,
    ) -> ComplexityMetrics:
        """从任务描述计算复杂度指标"""
        # 自动推断文件数
        if file_count is None:
            file_count = cls._estimate_file_count(task_description)

        # 自动推断依赖深度
        if dependency_depth is None:
            dependency_depth = cls._estimate_dependency_depth(task_description)

        # 自动推断模糊度
        if ambiguity is None:
            ambiguity = cls._estimate_ambiguity(task_description)

        # 自动推断可逆度
        if reversibility is None:
            reversibility = cls._estimate_reversibility(task_description)

        # 推断任务类型
        task_type = cls._infer_task_type(task_description)

        # 计算关键词复杂度
        keyword_complexity = cls._calculate_keyword_complexity(task_description)

        return cls(
            file_count=file_count,
            dependency_depth=dependency_depth,
            ambiguity=ambiguity,
            reversibility=reversibility,
            task_type=task_type,
            keyword_complexity=keyword_complexity,
        )

    @staticmethod
    def _estimate_file_count(description: str) -> int:
        """估计涉及文件数"""
        # 关键词匹配
        multi_file_indicators = [
            r"refactor",
            r"multiple",
            r"across",
            r"all",
            r"entire",
            r"system",
            r"module",
            r"package",
            r"library",
        ]
        count = 0
        for pattern in multi_file_indicators:
            if re.search(pattern, description, re.IGNORECASE):
                count += 3
        return max(1, count)

    @staticmethod
    def _estimate_dependency_depth(description: str) -> int:
        """估计依赖深度"""
        deep_indicators = [
            r"integrate",
            r"connect",
            r"import",
            r"depend",
            r"require",
            r"api",
            r"database",
            r"external",
            r"third.party",
        ]
        count = 0
        for pattern in deep_indicators:
            if re.search(pattern, description, re.IGNORECASE):
                count += 1
        return count

    @staticmethod
    def _estimate_ambiguity(description: str) -> float:
        """估计模糊度"""
        # 按空格分词（英文），中文按单字计数
        words = description.split()
        cjk_count = sum(1 for ch in description if "一" <= ch <= "鿿")
        word_count = len(words) + cjk_count  # CJK 字符各算一个词
        if word_count < 5:
            return 0.8
        elif word_count < 10:
            return 0.5
        elif word_count < 20:
            return 0.3
        else:
            return 0.1

    @staticmethod
    def _estimate_reversibility(description: str) -> float:
        """估计可逆度"""
        irreversible_indicators = [
            r"delete",
            r"remove",
            r"drop",
            r"destroy",
            r"deploy",
            r"publish",
            r"release",
            r"production",
            r"database",
            r"删除",
            r"移除",
            r"销毁",
            r"部署",
            r"发布",
            r"上线",
            r"生产",
            r"数据库",
            r"清空",
        ]
        for pattern in irreversible_indicators:
            if re.search(pattern, description, re.IGNORECASE):
                return 0.2
        return 0.8

    @staticmethod
    def _infer_task_type(description: str) -> str:
        """推断任务类型"""
        # 注意：顺序很重要，更具体的模式要先匹配
        type_patterns = {
            "refactoring": [
                r"refactor",
                r"restructure",
                r"reorganize",
                r"clean",
                r"重构",
                r"重组",
                r"整理",
            ],
            "debugging": [
                r"fix",
                r"bug",
                r"error",
                r"issue",
                r"debug",
                r"修复",
                r"调试",
                r"排障",
                r"报错",
            ],
            "research": [
                r"research",
                r"investigate",
                r"analyze",
                r"study",
                r"调研",
                r"研究",
                r"分析",
                r"评估",
            ],
            "testing": [
                r"test",
                r"verify",
                r"validate",
                r"check",
                r"测试",
                r"验证",
                r"校验",
                r"单测",
            ],
            "documentation": [
                r"document",
                r"write",
                r"readme",
                r"guide",
                r"文档",
                r"手册",
                r"指南",
                r"说明",
            ],
            "coding": [
                r"implement",
                r"code",
                r"function",
                r"class",
                r"module",
                r"实现",
                r"开发",
                r"编码",
                r"模块",
                r"接口",
                r"函数",
            ],
        }
        for task_type, patterns in type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description, re.IGNORECASE):
                    return task_type
        return "general"

    @staticmethod
    def _calculate_keyword_complexity(description: str) -> float:
        """计算关键词复杂度"""
        complex_words = [
            "architecture",
            "system",
            "integration",
            "optimization",
            "security",
            "performance",
            "scalability",
            "concurrency",
            "distributed",
            "microservice",
            "database",
            "authentication",
            # 中文复杂度关键词（子串匹配，CJK 无词边界）
            "架构",
            "重构",
            "迁移",
            "集成",
            "优化",
            "性能",
            "并发",
            "分布式",
            "微服务",
            "数据库",
            "认证",
            "鉴权",
            "安全",
            "加密",
            "兼容",
            "扩展",
            "高可用",
        ]
        count = sum(1 for word in complex_words if word in description.lower())
        return min(1.0, count / 3.0)  # 归一化到 0-1
