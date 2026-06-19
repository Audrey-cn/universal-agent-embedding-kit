"""Skill Interface — 技能接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SkillStatus(Enum):
    """技能状态"""

    DISCOVERED = "discovered"
    LOADED = "loaded"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SkillMetadata:
    """技能元数据"""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillMetadata:
        """从字典创建元数据"""
        # 处理 path 字段
        path = data.get("path")
        if path and not isinstance(path, Path):
            path = Path(path)

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            parameters=data.get("parameters", {}),
            path=path,
        )


@dataclass
class Skill:
    """技能"""

    metadata: SkillMetadata
    content: str  # SKILL.md 内容
    status: SkillStatus = SkillStatus.DISCOVERED
    result: Any = None
    error: Exception | None = None

    def __post_init__(self):
        if not self.metadata.name:
            raise ValueError("Skill name cannot be empty")

    def reset(self):
        """重置技能状态"""
        self.status = SkillStatus.DISCOVERED
        self.result = None
        self.error = None


class SkillLoader(ABC):
    """技能加载器基类"""

    @abstractmethod
    def discover(self, search_path: Path) -> list[SkillMetadata]:
        """发现技能"""
        ...

    @abstractmethod
    def load(self, name: str) -> Skill:
        """加载技能"""
        ...

    @abstractmethod
    def execute(self, skill: Skill, context: dict[str, Any]) -> Any:
        """执行技能"""
        ...
