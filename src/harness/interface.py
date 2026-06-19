"""Interfaces for the local Agent Harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarnessRequest:
    """Input for a harness run."""

    task: str
    workflow_config: dict[str, Any] | None = None
    memory_layer: str = "l2"
    tags: list[str] = field(default_factory=lambda: ["harness"])


@dataclass
class HarnessResult:
    """Serializable result for a harness run."""

    task: str
    success: bool
    effort: dict[str, Any]
    workflow: dict[str, Any]
    verification: dict[str, Any]
    memory: dict[str, Any]
    report: dict[str, Any]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to plain data for APIs, CLI, and benchmark output."""
        return {
            "task": self.task,
            "success": self.success,
            "effort": self.effort,
            "workflow": self.workflow,
            "verification": self.verification,
            "memory": self.memory,
            "report": self.report,
            "errors": self.errors,
        }

