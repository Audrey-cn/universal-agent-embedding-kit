"""Skill Loader Implementation — 技能加载器实现"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .discovery import SkillDiscovery
from .interface import Skill, SkillLoader, SkillMetadata, SkillStatus


class SkillLoaderImpl(SkillLoader):
    """技能加载器实现"""

    def __init__(self, search_paths: list[Path] | None = None):
        self.discovery = SkillDiscovery(search_paths)
        self.skills: dict[str, Skill] = {}
        self._cache: dict[str, Skill] = {}

    def add_search_path(self, path: Path) -> None:
        """添加搜索路径"""
        self.discovery.add_search_path(path)

    def discover(self, search_path: Path | None = None) -> list[SkillMetadata]:
        """发现技能"""
        return self.discovery.discover(search_path)

    def load(self, name: str) -> Skill:
        """加载技能"""
        # 检查缓存
        if name in self._cache:
            return self._cache[name]

        # 发现技能
        metadata_list = self.discover()

        # 查找匹配的技能
        for metadata in metadata_list:
            if metadata.name == name:
                skill = self._load_skill(metadata)
                self._cache[name] = skill
                return skill

        raise KeyError(f"Skill '{name}' not found")

    def _load_skill(self, metadata: SkillMetadata) -> Skill:
        """加载技能文件"""
        if not metadata.path or not metadata.path.exists():
            raise FileNotFoundError(f"Skill file not found: {metadata.path}")

        content = metadata.path.read_text(encoding="utf-8")
        skill = Skill(metadata=metadata, content=content)
        skill.status = SkillStatus.LOADED
        return skill

    def execute(self, skill: Skill, context: dict[str, Any]) -> Any:
        """执行技能"""
        skill.status = SkillStatus.EXECUTING
        try:
            # 解析技能内容
            instructions = self._parse_instructions(skill.content)

            # 执行指令
            result = self._execute_instructions(instructions, context)

            skill.status = SkillStatus.COMPLETED
            skill.result = result
            return result
        except Exception as e:
            skill.status = SkillStatus.FAILED
            skill.error = e
            raise

    def _parse_instructions(self, content: str) -> list[dict[str, Any]]:
        """解析技能指令"""
        instructions: list[dict[str, Any]] = []
        lines = content.split("\n")
        current_section = None
        current_content: list[str] = []

        for line in lines:
            # 检测节标题
            if line.startswith("# "):
                if current_section:
                    instructions.append(
                        {
                            "type": "section",
                            "title": current_section,
                            "content": "\n".join(current_content),
                        }
                    )
                current_section = line[2:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        # 保存最后一个节
        if current_section:
            instructions.append(
                {
                    "type": "section",
                    "title": current_section,
                    "content": "\n".join(current_content),
                }
            )

        return instructions

    def _execute_instructions(
        self,
        instructions: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """执行指令"""
        results: dict[str, Any] = {}

        for instruction in instructions:
            if instruction["type"] == "section":
                # 将节内容添加到结果中
                results[instruction["title"]] = instruction["content"]

        return results

    def list_skills(self) -> list[SkillMetadata]:
        """列出所有可用技能"""
        return self.discover()

    def reload(self, name: str) -> Skill:
        """重新加载技能"""
        if name in self._cache:
            del self._cache[name]
        return self.load(name)

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
