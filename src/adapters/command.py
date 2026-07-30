"""Command-backed external Agent Adapter."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.logger import JsonlLogger

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
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                preexec_fn=self._make_preexec(),
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

    @staticmethod
    def _make_preexec() -> Callable[[], None]:
        """构建 preexec_fn，在子进程中设置资源限制（CPU/内存/进程数/文件大小）"""
        # 捕获当前实例的资源限制配置
        # 注意：preexec_fn 在子进程中执行，不能访问 self
        def _set_limits() -> None:
            # 内存限制 —— 尝试多种方式以兼容不同平台（macOS 不支持 RLIMIT_AS）
            mem_bytes = 512 * 1024 * 1024  # 512MB
            for rlimit_attr in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
                try:
                    attr = getattr(resource, rlimit_attr, None)
                    if attr is not None:
                        resource.setrlimit(attr, (mem_bytes, mem_bytes))
                except (OSError, ValueError):
                    continue

            # CPU 时间限制
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
            except (OSError, ValueError):
                pass

            # 进程数限制（防止 fork 炸弹）
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
            except (OSError, ValueError):
                pass

            # 文件大小限制
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE, (_MAX_OUTPUT_BYTES, _MAX_OUTPUT_BYTES)
                )
            except (OSError, ValueError):
                pass

            # 创建新的进程组，便于超时杀灭
            os.setpgrp()

        return _set_limits

    def _result_from_completed(
        self,
        request: AdapterRequest,
        payload: dict[str, Any],
        trace_id: str,
        started: float,
        completed: subprocess.CompletedProcess[str],
    ) -> AdapterRunResult:
        stdout = (completed.stdout or "")[:self.max_output_bytes]
        stderr = (completed.stderr or "")[:self.max_output_bytes]
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
