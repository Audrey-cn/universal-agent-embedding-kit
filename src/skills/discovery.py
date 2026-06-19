"""Skill Discovery — 技能发现"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .interface import SkillMetadata


class SkillDiscovery:
    """技能发现器"""

    SKILL_FILE_PATTERN = "SKILL.md"
    METADATA_PATTERN = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n",
        re.DOTALL | re.MULTILINE,
    )

    def __init__(self, search_paths: list[Path] | None = None):
        self.search_paths = search_paths or []

    def add_search_path(self, path: Path) -> None:
        """添加搜索路径"""
        if path not in self.search_paths:
            self.search_paths.append(path)

    def discover(self, search_path: Path | None = None) -> list[SkillMetadata]:
        """发现技能"""
        paths = [search_path] if search_path else self.search_paths
        skills = []

        for path in paths:
            if not path.exists():
                continue
            skills.extend(self._discover_in_path(path))

        return skills

    def _discover_in_path(self, path: Path) -> list[SkillMetadata]:
        """在指定路径中发现技能"""
        skills = []

        if path.is_file():
            if path.name == self.SKILL_FILE_PATTERN:
                metadata = self._parse_metadata(path)
                if metadata:
                    skills.append(metadata)
        elif path.is_dir():
            # 递归搜索 SKILL.md 文件
            for skill_file in path.rglob(self.SKILL_FILE_PATTERN):
                metadata = self._parse_metadata(skill_file)
                if metadata:
                    skills.append(metadata)

        return skills

    def _parse_metadata(self, skill_path: Path) -> SkillMetadata | None:
        """解析技能元数据"""
        try:
            content = skill_path.read_text(encoding="utf-8")
            match = self.METADATA_PATTERN.search(content)

            if match:
                # 使用 PyYAML 解析
                metadata_str = match.group(1)
                metadata = yaml.safe_load(metadata_str)
                if isinstance(metadata, dict):
                    metadata["path"] = skill_path
                    return SkillMetadata.from_dict(metadata)
            else:
                # 没有元数据，使用文件名作为名称
                return SkillMetadata(
                    name=skill_path.parent.name,
                    description=f"Skill from {skill_path}",
                    path=skill_path,
                )
            return None
        except Exception:
            return None
