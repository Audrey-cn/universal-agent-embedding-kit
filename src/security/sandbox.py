"""代码执行沙箱 — 使用 subprocess + resource 限制隔离代码执行

不依赖 Docker 或外部工具，仅使用 Python 标准库（resource, signal, subprocess, tempfile）。
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
import warnings
from dataclasses import dataclass, field
from typing import Any


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
    # 是否允许网络访问（当前通过隔离环境变量实现基本限制）
    allow_network: bool = False
    # 是否允许文件系统写入（当前通过 RLIMIT_FSIZE 限制文件大小）
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
    result: Any = None  # 从 stdout 解析的 JSON 结果


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

        # 将代码写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            return self._run_subprocess(
                [sys.executable, tmp_path],
                policy=policy,
            )
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(wrapper)
            tmp_path = f.name

        try:
            result = self._run_subprocess(
                [sys.executable, tmp_path],
                policy=policy,
            )

            if not result.success:
                # 整个脚本执行失败（语法错误、超时、内存超限等）
                return [result]

            # 解析 JSON 结果行
            return self._parse_batch_results(result.stdout, result.stderr)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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

        return self._run_subprocess(cmd, policy=policy)

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #

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
        """在受资源限制的子进程中运行命令"""

        # 构建 preexec_fn 用于设置资源限制（仅 Unix/macOS）
        def _set_limits() -> None:
            # 内存限制 —— 尝试多种方式以兼容不同平台
            mem_bytes = policy.max_memory_mb * 1024 * 1024
            memory_limited = False
            # macOS 不支持 RLIMIT_AS，尝试 RLIMIT_DATA + RLIMIT_RSS
            for rlimit_attr in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
                try:
                    attr = getattr(resource, rlimit_attr, None)
                    if attr is not None:
                        resource.setrlimit(attr, (mem_bytes, mem_bytes))
                        memory_limited = True
                except (OSError, ValueError):
                    continue

            if not memory_limited and policy.max_memory_mb > 0:
                # 所有内存限制方式均失败（如 macOS），发出警告
                warnings.warn(
                    f"沙箱内存限制未生效：当前平台不支持 RLIMIT_AS/RLIMIT_DATA/RLIMIT_RSS。"
                    f"子进程可能分配超过 {policy.max_memory_mb}MB 内存。",
                    RuntimeWarning,
                    stacklevel=2,
                )

            # CPU 时间限制
            try:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (policy.max_runtime_sec, policy.max_runtime_sec),
                )
            except (OSError, ValueError):
                pass

            # 进程数限制（防止 fork 炸弹）
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            except (OSError, ValueError):
                pass

            # 文件大小限制
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    (policy.max_output_bytes, policy.max_output_bytes),
                )
            except (OSError, ValueError):
                pass

            # 创建新的进程组，便于超时杀灭
            os.setpgrp()

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=policy.max_runtime_sec + 5,  # 额外 5 秒缓冲
                preexec_fn=_set_limits,
                # 限制环境变量，减少信息泄露
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": "/tmp",  # 不暴露用户真实 HOME
                    "TMPDIR": tempfile.gettempdir(),
                    "LANG": "en_US.UTF-8",
                    # 不继承 PYTHONPATH，防止注入恶意模块
                    "PYTHONPATH": "",
                },
            )

            # 截断输出到最大限制
            stdout = (
                completed.stdout[:policy.max_output_bytes]
                if completed.stdout
                else ""
            )
            stderr = (
                completed.stderr[:policy.max_output_bytes]
                if completed.stderr
                else ""
            )

            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=completed.returncode,
                success=completed.returncode == 0,
                error=None,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                stdout="",
                stderr="",
                exit_code=-1,
                success=False,
                error=f"执行超时（超过 {policy.max_runtime_sec} 秒）",
                timed_out=True,
            )
        except Exception as exc:
            return SandboxResult(
                stdout="",
                stderr="",
                exit_code=-1,
                success=False,
                error=f"沙箱执行异常: {exc}",
                timed_out=False,
            )
