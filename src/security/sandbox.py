"""代码执行沙箱 — 使用 subprocess + resource 限制隔离代码执行

不依赖 Docker 或外部工具，仅使用 Python 标准库（resource, signal, subprocess, tempfile）。
"""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

try:
    import resource as _resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows
    _resource = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# 沙箱策略
# --------------------------------------------------------------------------- #
@dataclass
class SandboxPolicy:
    """沙箱策略配置"""

    # 最大内存限制（MB）
    max_memory_mb: int = 256
    # 最大运行时间（秒）
    max_runtime_sec: int = 30
    # 是否允许网络访问（策略元数据；当前未做 OS 级强制）
    allow_network: bool = False
    # 是否允许文件系统写入（策略元数据；当前未做 OS 级强制）
    allow_filesystem_write: bool = False
    # 白名单路径（预留，当前版本未强制路径检查）
    allowed_paths: list[str] = field(default_factory=list)
    # 最大输出大小（字节）
    max_output_bytes: int = 1024 * 1024  # 1MB


# --------------------------------------------------------------------------- #
# 沙箱执行结果
# --------------------------------------------------------------------------- #
@dataclass
class SandboxResult:
    """沙箱执行结果"""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    success: bool = False
    error: str | None = None
    timed_out: bool = False
    output_truncated: bool = False
    result: Any = None  # 从 stdout 解析的 JSON 结果


def _validate_policy(policy: SandboxPolicy) -> None:
    for field_name in ("max_runtime_sec", "max_memory_mb", "max_output_bytes"):
        value = getattr(policy, field_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{field_name} must be finite and positive")


def _set_resource_limits(policy: SandboxPolicy) -> None:
    if _resource is None:
        return

    memory_bytes = int(policy.max_memory_mb * 1024 * 1024)
    for rlimit_name in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
        rlimit = getattr(_resource, rlimit_name, None)
        if rlimit is None:
            continue
        try:
            _resource.setrlimit(rlimit, (memory_bytes, memory_bytes))
        except (OSError, ValueError):
            pass

    process_limit = 64
    nproc_resource = getattr(_resource, "RLIMIT_NPROC", None)
    if sys.platform == "darwin" and nproc_resource is not None:
        # macOS accounts RLIMIT_NPROC per user, so lowering it below the
        # caller's existing process count prevents even one child process.
        process_limit = _resource.getrlimit(nproc_resource)[0]

    limits = (
        ("RLIMIT_CPU", math.ceil(policy.max_runtime_sec)),
        ("RLIMIT_NPROC", process_limit),
        ("RLIMIT_FSIZE", int(policy.max_output_bytes)),
    )
    for rlimit_name, limit in limits:
        rlimit = getattr(_resource, rlimit_name, None)
        if rlimit is None:
            continue
        try:
            _resource.setrlimit(rlimit, (limit, limit))
        except (OSError, ValueError):
            pass


def _truncate_text_to_byte_limit(text: str, limit: int) -> tuple[str, bool]:
    if len(text.encode("utf-8")) <= limit:
        return text, False

    retained: list[str] = []
    retained_bytes = 0
    for character in text:
        encoded_size = len(character.encode("utf-8"))
        if retained_bytes + encoded_size > limit:
            break
        retained.append(character)
        retained_bytes += encoded_size
    return "".join(retained), True


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (OSError, ProcessLookupError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def run_bounded_process(
    command: Sequence[str],
    *,
    input_text: str | None = None,
    policy: SandboxPolicy | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
) -> SandboxResult:
    """在有界资源和合并输出预算下运行子进程。

    ``env`` 是完整的子进程环境；本函数不会合并父进程环境。
    """
    active_policy = policy or SandboxPolicy()
    _validate_policy(active_policy)

    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
        "cwd": cwd,
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
        if _resource is not None:
            popen_kwargs["preexec_fn"] = lambda: _set_resource_limits(active_policy)
    elif os.name == "nt":  # pragma: no cover - exercised on Windows
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    except Exception as exc:
        return SandboxResult(error=f"沙箱执行异常: {exc}")

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    budget_lock = threading.Lock()
    remaining_bytes = int(active_policy.max_output_bytes)
    output_truncated = False

    def drain(stream: IO[bytes], destination: list[bytes]) -> None:
        nonlocal output_truncated, remaining_bytes
        while chunk := stream.read(8192):
            with budget_lock:
                retained_size = min(len(chunk), remaining_bytes)
                if retained_size:
                    destination.append(chunk[:retained_size])
                    remaining_bytes -= retained_size
                if retained_size < len(chunk):
                    output_truncated = True
        stream.close()

    drain_threads = [
        threading.Thread(target=drain, args=(process.stdout, stdout_chunks), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr_chunks), daemon=True),
    ]
    for thread in drain_threads:
        thread.start()

    input_thread: threading.Thread | None = None
    stdin = process.stdin
    if input_text is not None and stdin is not None:

        def write_input() -> None:
            try:
                stdin.write(input_text.encode("utf-8"))
            except (BrokenPipeError, OSError):
                pass
            finally:
                stdin.close()

        input_thread = threading.Thread(target=write_input, daemon=True)
        input_thread.start()

    timed_out = False
    try:
        process.wait(timeout=active_policy.max_runtime_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_group(process)
        process.wait()

    for thread in drain_threads:
        thread.join()
    if input_thread is not None:
        input_thread.join()

    with budget_lock:
        stdout_bytes = b"".join(stdout_chunks)
        stderr_bytes = b"".join(stderr_chunks)
        was_truncated = output_truncated

    stdout_decoded = stdout_bytes.decode("utf-8", errors="replace")
    stderr_decoded = stderr_bytes.decode("utf-8", errors="replace")
    stdout, stdout_decode_truncated = _truncate_text_to_byte_limit(
        stdout_decoded, int(active_policy.max_output_bytes)
    )
    remaining_decoded_bytes = int(active_policy.max_output_bytes) - len(
        stdout.encode("utf-8")
    )
    stderr, stderr_decode_truncated = _truncate_text_to_byte_limit(
        stderr_decoded, remaining_decoded_bytes
    )
    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=process.returncode,
        success=process.returncode == 0 and not timed_out,
        error=(
            f"执行超时（超过 {active_policy.max_runtime_sec} 秒）"
            if timed_out
            else None
        ),
        timed_out=timed_out,
        output_truncated=(
            was_truncated or stdout_decode_truncated or stderr_decode_truncated
        ),
    )


# --------------------------------------------------------------------------- #
# 轻量级沙箱执行器
# --------------------------------------------------------------------------- #
class SandboxedExecutor:
    """轻量级沙箱执行器（基于 subprocess + resource 限制）

    在隔离子进程中执行 Python 代码或命令，通过 preexec_fn 设置资源限制
    （CPU 时间、内存、进程数、文件大小），并提供超时控制。
    """

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #

    def execute_python(
        self, code: str, policy: SandboxPolicy | None = None
    ) -> SandboxResult:
        """在隔离子进程中执行 Python 代码

        Args:
            code: 要执行的 Python 代码字符串
            policy: 沙箱策略，为 None 时使用默认策略

        Returns:
            SandboxResult: 执行结果（stdout, stderr, exit_code, success, error）
        """
        if policy is None:
            policy = SandboxPolicy()

        with tempfile.TemporaryDirectory(prefix="uaek-sandbox-") as tmp_dir:
            script_path = Path(tmp_dir) / "candidate.py"
            script_path.write_text(code, encoding="utf-8")
            return run_bounded_process(
                [sys.executable, str(script_path)],
                policy=policy,
                env=self._sandbox_environment(tmp_dir),
                cwd=tmp_dir,
            )

    def execute_python_with_inputs(
        self,
        code: str,
        entrypoint: str,
        args_list: list[tuple[Any, ...]],
        policy: SandboxPolicy | None = None,
    ) -> list[SandboxResult]:
        """在隔离子进程中执行 Python 代码并用多组参数调用函数

        将代码定义和所有输入参数打包为一个脚本，在单个子进程中完成所有调用，
        避免多次启动子进程的开销。

        Args:
            code: 定义函数的 Python 代码字符串
            entrypoint: 要调用的函数名
            args_list: 多组调用参数，每组为一个 tuple
            policy: 沙箱策略

        Returns:
            list[SandboxResult]: 每组参数对应的执行结果。如果整个脚本执行失败，
                                 返回包含单个失败 SandboxResult 的列表。
        """
        if policy is None:
            policy = SandboxPolicy()

        # 构建包装脚本：定义函数 + 对每组参数调用并输出 JSON 结果
        wrapper = self._build_wrapper_script(code, entrypoint, args_list)

        with tempfile.TemporaryDirectory(prefix="uaek-sandbox-") as tmp_dir:
            script_path = Path(tmp_dir) / "candidate.py"
            script_path.write_text(wrapper, encoding="utf-8")
            result = run_bounded_process(
                [sys.executable, str(script_path)],
                policy=policy,
                env=self._sandbox_environment(tmp_dir),
                cwd=tmp_dir,
            )

            if not result.success:
                # 整个脚本执行失败（语法错误、超时、内存超限等）
                return [result]

            # 解析 JSON 结果行
            return self._parse_batch_results(result.stdout, result.stderr)

    def execute_command(
        self, cmd: list[str], policy: SandboxPolicy | None = None
    ) -> SandboxResult:
        """在隔离子进程中执行命令

        Args:
            cmd: 命令及其参数列表（如 ["python", "script.py"]）
            policy: 沙箱策略，为 None 时使用默认策略

        Returns:
            SandboxResult: 执行结果
        """
        if policy is None:
            policy = SandboxPolicy()

        with tempfile.TemporaryDirectory(prefix="uaek-sandbox-") as tmp_dir:
            return run_bounded_process(
                cmd,
                policy=policy,
                env=self._sandbox_environment(tmp_dir),
                cwd=tmp_dir,
            )

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sandbox_environment(tmp_dir: str) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": tmp_dir,
            "TMPDIR": tmp_dir,
            "LANG": "en_US.UTF-8",
            "PYTHONPATH": tmp_dir,
        }

    def _build_wrapper_script(
        self,
        code: str,
        entrypoint: str,
        args_list: list[tuple[Any, ...]],
    ) -> str:
        """构建包装脚本：定义函数后对每组参数调用并输出 JSON"""
        args_json = json.dumps(args_list)

        return (
            "import json\n"
            "import sys\n"
            "import traceback\n\n"
            f"{code}\n\n"
            "results = []\n"
            f"_args_list = json.loads({args_json!r})\n"
            "for _args in _args_list:\n"
            "    try:\n"
            f"        result = {entrypoint}(*_args)\n"
            "        results.append({'status': 'ok', 'value': result})\n"
            "    except Exception as _exc:\n"
            "        results.append("
            "{'status': 'error', 'error': f'{type(_exc).__name__}: {_exc}'})\n"
            "print(json.dumps(results))\n"
        )

    def _parse_batch_results(
        self, stdout: str, stderr: str
    ) -> list[SandboxResult]:
        """解析批量执行结果"""
        try:
            parsed = json.loads(stdout.strip() or "[]")
        except json.JSONDecodeError:
            return [
                SandboxResult(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=0,
                    success=False,
                    error=f"无法解析输出为 JSON: {stdout[:200]}",
                )
            ]

        if not isinstance(parsed, list):
            return [
                SandboxResult(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=0,
                    success=False,
                    error=f"期望 JSON 数组，得到: {type(parsed).__name__}",
                )
            ]

        results: list[SandboxResult] = []
        for item in parsed:
            if isinstance(item, dict) and item.get("status") == "ok":
                results.append(
                    SandboxResult(
                        stdout=json.dumps(item),
                        stderr="",
                        exit_code=0,
                        success=True,
                        result=item.get("value"),
                    )
                )
            elif isinstance(item, dict) and item.get("status") == "error":
                results.append(
                    SandboxResult(
                        stdout=json.dumps(item),
                        stderr="",
                        exit_code=0,
                        success=False,
                        error=item.get("error"),
                    )
                )
            else:
                results.append(
                    SandboxResult(
                        stdout=str(item),
                        stderr="",
                        exit_code=0,
                        success=False,
                        error=f"意外结果格式: {item}",
                    )
                )

        return results

    def _run_subprocess(
        self, cmd: list[str], policy: SandboxPolicy
    ) -> SandboxResult:
        """Compatibility delegate for callers using the former private helper."""
        return run_bounded_process(cmd, policy=policy)
