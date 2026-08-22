"""Command-backed external Agent Adapter."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from src.logger import JsonlLogger
from src.security import SandboxPolicy, SandboxResult, run_bounded_process

from .interface import AdapterRequest, AdapterRunResult

# 最大输出大小限制（1MB），防止命令输出过大导致内存问题
_MAX_OUTPUT_BYTES = 1024 * 1024


class CommandAgentAdapter:
    """Invoke a JSON-speaking external command as an Agent adapter."""

    # 默认资源限制
    DEFAULT_MAX_MEMORY_MB = 512
    DEFAULT_MAX_RUNTIME_SEC = 60
    DEFAULT_MAX_OUTPUT_BYTES = _MAX_OUTPUT_BYTES

    def __init__(
        self,
        command: list[str] | tuple[str, ...],
        provider: str = "command-agent",
        timeout_seconds: float = 60.0,
        trace_path: Path | str | None = None,
        max_memory_mb: int = 512,
        max_output_bytes: int = _MAX_OUTPUT_BYTES,
    ):
        if not command:
            raise ValueError("CommandAgentAdapter requires at least one command token")
        _validate_limit("timeout_seconds", timeout_seconds)
        _validate_limit("max_memory_mb", max_memory_mb)
        _validate_limit("max_output_bytes", max_output_bytes)
        self.command = list(command)
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.trace_path = Path(trace_path) if trace_path else None
        self.max_memory_mb = max_memory_mb
        self.max_output_bytes = max_output_bytes

    def run(self, request: AdapterRequest) -> AdapterRunResult:
        """Run the adapter command and normalize success or failure."""
        trace_id = str(request.metadata.get("trace_id") or uuid4())
        payload = request.to_payload(trace_id=trace_id)
        started = time.perf_counter()
        completed = run_bounded_process(
            self.command,
            input_text=json.dumps(payload, ensure_ascii=False),
            policy=SandboxPolicy(
                max_runtime_sec=cast(int, self.timeout_seconds),
                max_memory_mb=self.max_memory_mb,
                max_output_bytes=self.max_output_bytes,
            ),
            env=os.environ.copy(),
        )
        if completed.timed_out:
            result = self._failure_result(
                request=request,
                payload=payload,
                trace_id=trace_id,
                started=started,
                error=f"Adapter command timed out after {self.timeout_seconds:g}s",
                stdout=completed.stdout,
                stderr=completed.stderr,
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
        completed: SandboxResult,
    ) -> AdapterRunResult:
        stdout = completed.stdout
        stderr = completed.stderr
        if completed.output_truncated:
            return self._failure_result(
                request=request,
                payload=payload,
                trace_id=trace_id,
                started=started,
                error=f"Adapter command output exceeded {self.max_output_bytes} bytes",
                stdout=stdout,
                stderr=stderr,
                return_code=completed.exit_code,
            )
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
                return_code=completed.exit_code,
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
                return_code=completed.exit_code,
            )

        adapter_success = bool(data.get("success", completed.exit_code == 0))
        success = adapter_success and completed.exit_code == 0
        error = data.get("error")
        if completed.exit_code != 0 and not error:
            error = f"Adapter command exited with return code {completed.exit_code}"
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
            return_code=completed.exit_code,
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


def _validate_limit(field_name: str, value: object) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be finite and positive")


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
