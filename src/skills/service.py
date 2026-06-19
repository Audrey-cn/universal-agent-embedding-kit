"""Skill product service for project-level skill files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .discovery import SkillDiscovery
from .executor import SkillExecutor
from .interface import Skill, SkillMetadata


class SkillService:
    """Discover and execute standard SKILL.md and flat project markdown skills."""

    def __init__(self, search_paths: list[Path] | None = None):
        self.search_paths = search_paths or [Path("skills")]
        self.executor = SkillExecutor()

    def list_skills(self) -> list[dict[str, Any]]:
        """List discovered skills as dictionaries for product entrypoints."""
        return [self.metadata_to_dict(metadata) for metadata in self.discover()]

    def run(self, name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Load and execute a discovered skill by name."""
        metadata = self.get_metadata(name)
        if not metadata.path:
            raise FileNotFoundError(f"Skill path not found for {name}")
        content = metadata.path.read_text(encoding="utf-8")
        skill = Skill(metadata=metadata, content=content)
        result = self.executor.execute(skill, context or {})
        return {
            "name": metadata.name,
            "description": metadata.description,
            "path": str(metadata.path),
            "status": skill.status.value,
            **result,
        }

    def get_metadata(self, name: str) -> SkillMetadata:
        """Return metadata for a skill name."""
        for metadata in self.discover():
            if metadata.name == name:
                return metadata
        raise KeyError(f"Skill '{name}' not found")

    def discover(self) -> list[SkillMetadata]:
        """Discover both nested SKILL.md and flat Markdown skills."""
        discovered: dict[str, SkillMetadata] = {}
        standard_discovery = SkillDiscovery(self.search_paths)
        for metadata in standard_discovery.discover():
            discovered[metadata.name] = metadata

        for search_path in self.search_paths:
            if search_path.is_file() and search_path.suffix.lower() == ".md":
                metadata = self._metadata_from_markdown(search_path)
                discovered.setdefault(metadata.name, metadata)
            elif search_path.is_dir():
                for markdown_file in sorted(search_path.glob("*.md")):
                    metadata = self._metadata_from_markdown(markdown_file)
                    discovered.setdefault(metadata.name, metadata)

        return sorted(discovered.values(), key=lambda item: item.name)

    def metadata_to_dict(self, metadata: SkillMetadata) -> dict[str, Any]:
        """Serialize skill metadata."""
        return {
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "tags": metadata.tags,
            "dependencies": metadata.dependencies,
            "path": str(metadata.path) if metadata.path else "",
        }

    def _metadata_from_markdown(self, path: Path) -> SkillMetadata:
        content = path.read_text(encoding="utf-8")
        match = SkillDiscovery.METADATA_PATTERN.search(content)
        if match:
            parsed = yaml.safe_load(match.group(1))
            if isinstance(parsed, dict):
                parsed["path"] = path
                if "name" not in parsed:
                    parsed["name"] = path.stem
                return SkillMetadata.from_dict(parsed)
        return SkillMetadata(
            name=path.stem,
            description=f"Skill from {path}",
            path=path,
        )
