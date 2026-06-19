"""Local Agent Harness implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.effort import classify
from src.memory import MemoryService
from src.workflow import execute_workflow_config

from .interface import HarnessRequest, HarnessResult


class AgentHarness:
    """Run a conservative local task pipeline using UAEK primitives."""

    def __init__(self, memory_service: MemoryService | None = None):
        self.memory_service = memory_service or MemoryService(Path(".uaek/harness-memory"))

    def run(self, request: HarnessRequest) -> HarnessResult:
        """Run task -> effort -> workflow -> verification -> memory -> report."""
        errors: list[str] = []
        effort_result = classify(request.task)
        effort = {
            "level": effort_result.level.value,
            "confidence": effort_result.confidence,
            "dispatch_phrase": effort_result.dispatch_phrase,
            "verification_depth": effort_result.verification_depth,
            "metrics": effort_result.metrics,
        }

        workflow: dict[str, Any]
        try:
            workflow = execute_workflow_config(
                request.workflow_config or self._default_workflow_config(request.task)
            )
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(str(exc))
            workflow = {
                "workflow_id": "harness-pipeline",
                "success": False,
                "duration": 0.0,
                "tasks": [],
                "completed_tasks": [],
                "failed_tasks": [],
                "skipped_tasks": [],
                "task_results": {},
                "errors": [str(exc)],
            }

        verification = self._verify_workflow(workflow)
        success = bool(workflow["success"] and verification["passed"] and not errors)
        memory = self._record_memory(request, effort, workflow, verification)
        report = {
            "summary": f"Harness completed task: {request.task}",
            "score": 1.0 if success else 0.0,
            "stages": ["effort", "workflow", "verification", "memory"],
            "limitations": [
                "local harness only",
                "no live external platform run artifact",
                "no arbitrary code execution",
            ],
        }

        return HarnessResult(
            task=request.task,
            success=success,
            effort=effort,
            workflow=workflow,
            verification=verification,
            memory=memory,
            report=report,
            errors=errors,
        )

    def _default_workflow_config(self, task: str) -> dict[str, Any]:
        return {
            "id": "harness-pipeline",
            "type": "sequential",
            "tasks": [
                {"id": "receive", "name": "Receive task", "action": "echo", "args": [task]},
                {
                    "id": "classify",
                    "name": "Classify effort",
                    "action": "effort",
                    "args": [task],
                    "dependencies": ["receive"],
                },
                {
                    "id": "summarize",
                    "name": "Summarize result",
                    "action": "concat",
                    "args": ["harness: ", task],
                    "dependencies": ["classify"],
                },
            ],
        }

    def _verify_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        passed = bool(workflow["success"] and not workflow["failed_tasks"])
        return {
            "passed": passed,
            "checks": ["workflow_success", "no_failed_tasks"],
            "evidence": {
                "workflow_id": workflow["workflow_id"],
                "completed": len(workflow["completed_tasks"]),
                "failed": len(workflow["failed_tasks"]),
            },
        }

    def _record_memory(
        self,
        request: HarnessRequest,
        effort: dict[str, Any],
        workflow: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        content = (
            f"Harness task: {request.task}; "
            f"effort={effort['level']}; "
            f"workflow_success={workflow['success']}; "
            f"verification_passed={verification['passed']}"
        )
        entry = self.memory_service.add(
            content,
            layer=request.memory_layer,
            importance=0.8,
            tags=request.tags,
            metadata={"workflow_id": workflow["workflow_id"]},
        )
        self.memory_service.persist()
        return {
            "entry_id": entry["id"],
            "layer": entry["layer"],
            "tags": entry["tags"],
        }
