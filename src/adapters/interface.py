"""Serializable adapter request and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterRequest:
    """Input payload sent to an external Agent adapter."""

    task: str
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self, trace_id: str | None = None) -> dict[str, Any]:
        """Convert the request into the stdin JSON protocol payload."""
        metadata = dict(self.metadata)
        if trace_id is not None:
            metadata.setdefault("trace_id", trace_id)
        return {
            "task": self.task,
            "context": self.context,
            "metadata": metadata,
        }


@dataclass
class AdapterRunResult:
    """Normalized output from an external Agent adapter run."""

    provider: str
    task: str
    success: bool
    output: str
    artifacts: dict[str, Any]
    metrics: dict[str, Any]
    trace_id: str
    return_code: int | None
    duration_ms: float
    stdout: str
    stderr: str
    request: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to plain JSON-serializable data."""
        return {
            "provider": self.provider,
            "task": self.task,
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "trace_id": self.trace_id,
            "return_code": self.return_code,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "request": self.request,
            "error": self.error,
        }
