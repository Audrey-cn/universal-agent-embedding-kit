"""Command-backed external Agent Adapter."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.logger import JsonlLogger

from .interface import AdapterRequest, AdapterRunResult


class CommandAgentAdapter:
    """Invoke a JSON-speaking external command as an Agent adapter."""

    def __init__(
        self,
        command: list[str] | tuple[str, ...],
        provider: str = "command-agent",
        timeout_seconds: float = 60.0,
        trace_path: Path | str | None = None,
    ):
        if not command:
            raise ValueError("CommandAgentAdapter requires at least one command token")
        self.command = list(command)
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.trace_path = Path(trace_path) if trace_path else None

    def run(self, request: AdapterRequest) -> AdapterRunResult:
        """Run the adapter command and normalize success or failure."""
        trace_id = str(request.metadata.get("trace_id") or uuid4())
        payload = request.to_payload(trace_id=trace_id)
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            result = self._failure_result(
                request=request,
                payload=payload,
                trace_id=trace_id,
                started=started,
                error=f"Adapter command timed out after {self.timeout_seconds:g}s",
                stdout=_coerce_output(exc.stdout),
                stderr=_coerce_output(exc.stderr),
                return_code=None,
            )
            self._record_trace(result)
            return result

        result = self._result_from_completed(request, payload, trace_id, started, completed)
        self._record_trace(result)
        return result

    def _result_from_completed(
        self,
        request: AdapterRequest,
        payload: dict[str, Any],
        trace_id: str,
        started: float,
        completed: subprocess.CompletedProcess[str],
    ) -> AdapterRunResult:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return self._failure_result(
                request=request,
                payload=payload,
                trace_id=trace_id,
                started=started,
                error=f"Invalid JSON from adapter stdout: {exc.msg}",
                stdout=stdout,
                stderr=stderr,
                return_code=completed.returncode,
            )

        if not isinstance(data, dict):
            return self._failure_result(
                request=request,
                payload=payload,
                trace_id=trace_id,
                started=started,
                error="Adapter stdout JSON must be an object",
                stdout=stdout,
                stderr=stderr,
                return_code=completed.returncode,
            )

        adapter_success = bool(data.get("success", completed.returncode == 0))
        success = adapter_success and completed.returncode == 0
        error = data.get("error")
        if completed.returncode != 0 and not error:
            error = f"Adapter command exited with return code {completed.returncode}"
        artifacts = _dict_or_empty(data.get("artifacts"))
        metrics = _dict_or_empty(data.get("metrics"))

        return AdapterRunResult(
            provider=self.provider,
            task=request.task,
            success=success,
            output=str(data.get("output", "")),
            artifacts=artifacts,
            metrics=metrics,
            trace_id=trace_id,
            return_code=completed.returncode,
            duration_ms=_duration_ms(started),
            stdout=stdout,
            stderr=stderr,
            request=payload,
            error=str(error) if error else None,
        )

    def _failure_result(
        self,
        request: AdapterRequest,
        payload: dict[str, Any],
        trace_id: str,
        started: float,
        error: str,
        stdout: str,
        stderr: str,
        return_code: int | None,
    ) -> AdapterRunResult:
        return AdapterRunResult(
            provider=self.provider,
            task=request.task,
            success=False,
            output="",
            artifacts={},
            metrics={},
            trace_id=trace_id,
            return_code=return_code,
            duration_ms=_duration_ms(started),
            stdout=stdout,
            stderr=stderr,
            request=payload,
            error=error,
        )

    def _record_trace(self, result: AdapterRunResult) -> None:
        JsonlLogger(self.trace_path).record(
            "adapter_run",
            {
                "provider": result.provider,
                "task": result.task,
                "success": result.success,
                "trace_id": result.trace_id,
                "return_code": result.return_code,
                "duration_ms": result.duration_ms,
                "error": result.error,
            },
        )


def _duration_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 4)


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
