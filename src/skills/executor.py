"""Skill Executor — 技能执行器"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .interface import Skill, SkillStatus


class SkillExecutor:
    """技能执行器"""

    def __init__(self):
        self.variables: dict[str, Any] = {}
        self.functions: dict[str, Callable] = {}

    def set_variable(self, name: str, value: Any) -> None:
        """设置变量"""
        self.variables[name] = value

    def register_function(self, name: str, func: Callable) -> None:
        """注册函数"""
        self.functions[name] = func

    def execute(self, skill: Skill, context: dict[str, Any] | None = None) -> Any:
        """执行技能"""
        skill.status = SkillStatus.EXECUTING
        try:
            # 合并上下文
            exec_context = {**self.variables, **(context or {})}

            # 解析并执行技能内容
            result = self._execute_content(skill.content, exec_context)

            skill.status = SkillStatus.COMPLETED
            skill.result = result
            return result
        except Exception as e:
            skill.status = SkillStatus.FAILED
            skill.error = e
            raise

    def _execute_content(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """执行技能内容"""
        result = {
            "instructions": [],
            "variables": {},
            "output": "",
        }

        # 提取变量
        variables = self._extract_variables(content)
        result["variables"] = variables

        # 提取指令
        instructions = self._extract_instructions(content)
        result["instructions"] = instructions

        # 生成输出
        output = self._generate_output(content, context)
        result["output"] = output

        return result

    def _extract_variables(self, content: str) -> dict[str, str]:
        """提取变量"""
        variables = {}
        # 匹配 {{variable}} 格式
        pattern = re.compile(r"\{\{(\w+)\}\}")
        for match in pattern.finditer(content):
            var_name = match.group(1)
            if var_name not in variables:
                variables[var_name] = f"<{var_name}>"
        return variables

    def _extract_instructions(self, content: str) -> list[str]:
        """提取指令"""
        instructions = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            # 以数字开头的行视为指令
            if re.match(r"^\d+\.", line):
                instructions.append(line)
            # 以 - 开头的行视为列表项
            elif line.startswith("- "):
                instructions.append(line[2:])

        return instructions

    def _generate_output(self, content: str, context: dict[str, Any]) -> str:
        """生成输出"""
        # 替换变量
        output = content
        for key, value in context.items():
            output = output.replace(f"{{{{{key}}}}}", str(value))
        return output

    def validate(self, skill: Skill) -> list[str]:
        """验证技能"""
        errors = []

        # 检查技能名称
        if not skill.metadata.name:
            errors.append("Skill name is empty")

        # 检查技能内容
        if not skill.content:
            errors.append("Skill content is empty")

        # 检查依赖
        for dep in skill.metadata.dependencies:
            if dep not in self.functions:
                errors.append(f"Missing dependency: {dep}")

        return errors
