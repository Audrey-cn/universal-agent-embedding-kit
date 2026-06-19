"""Typed UAEK configuration loading."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MemoryConfig:
    """Memory defaults for product entrypoints."""

    storage_path: str = ".uaek/harness-memory"
    default_layer: str = "l2"


@dataclass(frozen=True)
class WorkflowConfig:
    """Workflow runtime defaults."""

    default_type: str = "sequential"
    safe_actions: list[str] = field(
        default_factory=lambda: ["noop", "echo", "concat", "sum", "effort", "fail"]
    )


@dataclass(frozen=True)
class SkillsConfig:
    """Skill discovery defaults."""

    search_paths: list[str] = field(default_factory=lambda: ["skills"])


@dataclass(frozen=True)
class VerificationConfig:
    """Local verification command defaults."""

    lint_command: str = ".venv/bin/python -m ruff check src api mcp tests"
    typecheck_command: str = ".venv/bin/python -m mypy src api mcp"
    test_command: str = ".venv/bin/python -m pytest"


@dataclass(frozen=True)
class LoggingConfig:
    """Structured logging defaults."""

    enabled: bool = True
    file_path: str | None = None


@dataclass(frozen=True)
class UAEKConfig:
    """Top-level UAEK configuration."""

    version: str = "0.1.0-alpha"
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable config data."""
        return asdict(self)


def load_config(path: Path | str | None = None) -> UAEKConfig:
    """Load a YAML/JSON UAEK config file, merging missing fields with defaults."""
    if path is None:
        return UAEKConfig()

    raw = _read_config_file(Path(path))
    data = raw.get("uaek", raw)
    if not isinstance(data, dict):
        raise ValueError("UAEK config must contain a mapping")

    return UAEKConfig(
        version=str(data.get("version", UAEKConfig().version)),
        memory=_memory_config(data.get("memory")),
        workflow=_workflow_config(data.get("workflow")),
        skills=_skills_config(data.get("skills")),
        verification=_verification_config(data.get("verification")),
        logging=_logging_config(data.get("logging")),
    )


def _read_config_file(path: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(raw_text)
    else:
        raw = yaml.safe_load(raw_text)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a mapping")
    return raw


def _memory_config(data: Any) -> MemoryConfig:
    defaults = MemoryConfig()
    mapping = data if isinstance(data, dict) else {}
    return MemoryConfig(
        storage_path=str(mapping.get("storage_path", defaults.storage_path)),
        default_layer=str(mapping.get("default_layer", defaults.default_layer)),
    )


def _workflow_config(data: Any) -> WorkflowConfig:
    defaults = WorkflowConfig()
    mapping = data if isinstance(data, dict) else {}
    return WorkflowConfig(
        default_type=str(mapping.get("default_type", defaults.default_type)),
        safe_actions=_string_list(mapping.get("safe_actions"), defaults.safe_actions),
    )


def _skills_config(data: Any) -> SkillsConfig:
    defaults = SkillsConfig()
    mapping = data if isinstance(data, dict) else {}
    return SkillsConfig(
        search_paths=_string_list(mapping.get("search_paths"), defaults.search_paths)
    )


def _verification_config(data: Any) -> VerificationConfig:
    defaults = VerificationConfig()
    mapping = data if isinstance(data, dict) else {}
    return VerificationConfig(
        lint_command=str(mapping.get("lint_command", defaults.lint_command)),
        typecheck_command=str(mapping.get("typecheck_command", defaults.typecheck_command)),
        test_command=str(mapping.get("test_command", defaults.test_command)),
    )


def _logging_config(data: Any) -> LoggingConfig:
    defaults = LoggingConfig()
    mapping = data if isinstance(data, dict) else {}
    file_path = mapping.get("file_path", defaults.file_path)
    return LoggingConfig(
        enabled=bool(mapping.get("enabled", defaults.enabled)),
        file_path=str(file_path) if file_path else None,
    )


def _string_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
