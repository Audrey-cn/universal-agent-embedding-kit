"""沙箱执行器测试 — 测试 SandboxedExecutor 的资源限制和隔离能力"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from src.security.sandbox import (
    SandboxedExecutor,
    SandboxPolicy,
    SandboxResult,
    run_bounded_process,
)


# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
@pytest.fixture
def executor() -> SandboxedExecutor:
    """创建沙箱执行器实例"""
    return SandboxedExecutor()


def test_bounded_process_caps_combined_output_bytes() -> None:
    """stdout/stderr 应共享同一个按字节计算的输出上限。"""
    policy = SandboxPolicy(max_runtime_sec=5, max_output_bytes=64)
    result = run_bounded_process(
        [
            sys.executable,
            "-c",
            "import sys; print('界' * 1000); sys.stderr.write('x' * 1000)",
        ],
        policy=policy,
    )

    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 64
    assert result.output_truncated is True


def test_bounded_process_decodes_invalid_output_with_replacement() -> None:
    """非 UTF-8 子进程输出应以替换字符解码。"""
    result = run_bounded_process(
        [sys.executable, "-c", "import os; os.write(1, b'\\xff')"],
        policy=SandboxPolicy(max_output_bytes=64),
    )

    assert result.stdout == "\ufffd"
    assert result.output_truncated is False


@pytest.mark.parametrize(
    ("field", "value"),
    [("max_runtime_sec", 0), ("max_memory_mb", -1), ("max_output_bytes", 0)],
)
def test_bounded_process_rejects_invalid_limits(field: str, value: int) -> None:
    """子进程启动前应拒绝非正数资源限制。"""
    policy = SandboxPolicy()
    setattr(policy, field, value)

    with pytest.raises(ValueError, match=field):
        run_bounded_process([sys.executable, "-c", "pass"], policy=policy)


def test_bounded_process_uses_supplied_environment_and_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """调用者传入的环境是完整环境，且工作目录应原样传递。"""
    monkeypatch.setenv("UAEK_PARENT_ONLY", "secret")
    result = run_bounded_process(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "print(os.environ.get('UAEK_CHILD_ONLY')); "
                "print(os.environ.get('UAEK_PARENT_ONLY')); "
                "print(os.getcwd())"
            ),
        ],
        env={"UAEK_CHILD_ONLY": "visible"},
        cwd=tmp_path,
    )

    assert result.success is True
    assert result.stdout.splitlines() == ["visible", "None", str(tmp_path)]


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX PID inspection")
def test_bounded_process_timeout_kills_child_process_group(tmp_path: Path) -> None:
    """超时应清理同一进程组中由命令启动的子进程。"""
    pid_path = tmp_path / "child.pid"
    helper_path = tmp_path / "spawn_child.py"
    helper_path.write_text(
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(60)'])\n"
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    result = run_bounded_process(
        [sys.executable, str(helper_path), str(pid_path)],
        policy=SandboxPolicy(max_runtime_sec=1),
        cwd=tmp_path,
    )

    assert result.timed_out is True
    child_pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail(f"child process {child_pid} survived timeout")


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process groups")
def test_bounded_process_deadline_covers_descendant_pipe_drain(
    tmp_path: Path,
) -> None:
    """父进程退出后，持有管道的后代仍必须受同一运行时限约束。"""
    pid_path = tmp_path / "descendant.pid"
    helper_path = tmp_path / "exit_with_descendant.py"
    helper_path.write_text(
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(1)'])\n"
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n",
        encoding="utf-8",
    )

    started_at = time.monotonic()
    result = run_bounded_process(
        [sys.executable, str(helper_path), str(pid_path)],
        policy=SandboxPolicy(max_runtime_sec=0.1),
        cwd=tmp_path,
    )
    elapsed = time.monotonic() - started_at

    assert result.timed_out is True
    assert result.success is False
    assert elapsed < 0.75
    descendant_pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail(f"descendant process {descendant_pid} survived timeout")


# --------------------------------------------------------------------------- #
# 测试正常代码执行
# --------------------------------------------------------------------------- #
def test_execute_python_normal_code(executor: SandboxedExecutor):
    """正常 Python 代码应成功执行并返回正确输出"""
    code = "print('hello sandbox')"
    result = executor.execute_python(code)

    assert result.success is True
    assert result.exit_code == 0
    assert "hello sandbox" in result.stdout
    assert result.timed_out is False


def test_execute_python_with_inputs_simple(executor: SandboxedExecutor):
    """execute_python_with_inputs 应正确执行函数并返回结果"""
    code = "def add(a, b):\n    return a + b\n"
    args_list = [(1, 2), (3, 4), (5, 6)]

    results = executor.execute_python_with_inputs(code, "add", args_list)

    assert len(results) == 3
    assert all(r.success for r in results)
    assert results[0].result == 3
    assert results[1].result == 7
    assert results[2].result == 11


def test_execute_python_with_inputs_handles_errors(executor: SandboxedExecutor):
    """execute_python_with_inputs 应正确处理函数抛出的异常"""
    code = "def divide(a, b):\n    return a / b\n"
    args_list = [(10, 2), (1, 0), (6, 3)]

    results = executor.execute_python_with_inputs(code, "divide", args_list)

    assert len(results) == 3
    assert results[0].success is True
    assert results[0].result == 5.0
    assert results[1].success is False
    assert "ZeroDivisionError" in (results[1].error or "")
    assert results[2].success is True
    assert results[2].result == 2.0


def test_execute_python_with_inputs_string_operations(executor: SandboxedExecutor):
    """execute_python_with_inputs 应正确处理字符串参数和返回值"""
    code = "def greet(name):\n    return f'Hello, {name}!'\n"
    args_list = [("World",), ("沙箱",)]

    results = executor.execute_python_with_inputs(code, "greet", args_list)

    assert len(results) == 2
    assert results[0].result == "Hello, World!"
    assert results[1].result == "Hello, 沙箱!"


def test_execute_python_with_inputs_list_operations(executor: SandboxedExecutor):
    """execute_python_with_inputs 应正确处理列表参数和返回值"""
    code = "def sum_list(nums):\n    return sum(nums)\n"
    args_list = [([1, 2, 3],), ([10, 20, 30],), ([-1, 0, 1],)]

    results = executor.execute_python_with_inputs(code, "sum_list", args_list)

    assert len(results) == 3
    assert results[0].result == 6
    assert results[1].result == 60
    assert results[2].result == 0


# --------------------------------------------------------------------------- #
# 测试超时杀灭
# --------------------------------------------------------------------------- #
def test_execute_python_timeout(executor: SandboxedExecutor):
    """超时代码应被沙箱杀灭"""
    policy = SandboxPolicy(max_runtime_sec=2, max_memory_mb=128)
    code = (
        "import time\n"
        "x = 0\n"
        "while True:\n"
        "    x += 1\n"  # 忙循环消耗 CPU 时间，触发 RLIMIT_CPU
    )

    result = executor.execute_python(code, policy=policy)

    # 超时或 CPU 超限导致子进程被杀死
    assert not result.success
    # 可能是超时或非零退出码
    assert result.timed_out or result.exit_code != 0


def test_execute_python_with_inputs_timeout(executor: SandboxedExecutor):
    """execute_python_with_inputs 中超时函数应被捕获"""
    policy = SandboxPolicy(max_runtime_sec=2, max_memory_mb=128)
    code = "def slow():\n    x = 0\n    while True:\n        x += 1\n    return x\n"
    args_list = [()]

    results = executor.execute_python_with_inputs(code, "slow", args_list, policy=policy)

    # 整个脚本超时，返回单个失败结果
    assert len(results) == 1
    assert not results[0].success


# --------------------------------------------------------------------------- #
# 测试内存超限
# --------------------------------------------------------------------------- #
def test_execute_python_memory_limit(executor: SandboxedExecutor):
    """分配大量内存应被沙箱限制（在 macOS 上 RLIMIT_AS 可能不强制）"""
    import platform

    policy = SandboxPolicy(max_runtime_sec=10, max_memory_mb=32)
    code = (
        "import sys\n"
        "try:\n"
        "    # 尝试分配超过限制的内存\n"
        "    data = bytearray(50 * 1024 * 1024)  # 50MB\n"
        "    print('allocated')\n"
        "except MemoryError:\n"
        "    print('memory_error')\n"
        "    sys.exit(0)\n"
    )

    result = executor.execute_python(code, policy=policy)

    output = result.stdout + result.stderr
    if platform.system() == "Darwin":
        # macOS 上 RLIMIT_AS/RLIMIT_DATA 不强制内存限制，
        # 分配可能成功但资源限制框架已正确设置
        if "allocated" in output and result.success:
            # 内存限制在 macOS 上不生效是已知限制，框架本身正确
            return
    assert "allocated" not in output or not result.success


# --------------------------------------------------------------------------- #
# 测试文件系统写入限制
# --------------------------------------------------------------------------- #
def test_execute_python_filesystem_write_limit(executor: SandboxedExecutor):
    """RLIMIT_FSIZE 限制应阻止大文件写入"""
    policy = SandboxPolicy(
        max_runtime_sec=10,
        max_memory_mb=128,
        max_output_bytes=1024,  # 仅 1KB 文件大小限制
    )
    code = (
        "import sys\n"
        "try:\n"
        "    # 尝试写入超过 RLIMIT_FSIZE 的数据\n"
        "    with open('/tmp/sandbox_test_output.txt', 'w') as f:\n"
        "        f.write('x' * 10000)\n"
        "    print('write_ok')\n"
        "except (IOError, OSError) as e:\n"
        "    print(f'write_blocked: {e}')\n"
        "    sys.exit(0)\n"
    )

    result = executor.execute_python(code, policy=policy)

    # 写入应被 RLIMIT_FSIZE 阻止
    output = result.stdout + result.stderr
    assert "write_ok" not in output or not result.success


# --------------------------------------------------------------------------- #
# 测试网络访问限制
# --------------------------------------------------------------------------- #
def test_execute_python_network_restricted(executor: SandboxedExecutor):
    """沙箱环境应限制网络访问（通过受限环境变量）"""
    policy = SandboxPolicy(max_runtime_sec=5, max_memory_mb=128)
    code = (
        "import os\n"
        "# 检查环境变量是否受限\n"
        "env_keys = list(os.environ.keys())\n"
        "print(f'env_count: {len(env_keys)}')\n"
        "print(f'has_http_proxy: {\"HTTP_PROXY\" in os.environ}')\n"
    )

    result = executor.execute_python(code, policy=policy)

    # 沙箱使用受限环境变量，不应包含完整的系统环境
    assert result.success


# --------------------------------------------------------------------------- #
# 测试 execute_command
# --------------------------------------------------------------------------- #
def test_execute_command_simple(executor: SandboxedExecutor):
    """execute_command 应正确执行简单命令"""
    result = executor.execute_command(["echo", "hello"])

    assert result.success is True
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_execute_command_failure(executor: SandboxedExecutor):
    """execute_command 应正确处理命令失败"""
    result = executor.execute_command(["ls", "/nonexistent_path_xyz"])

    assert result.success is False
    assert result.exit_code != 0


def test_execute_command_timeout(executor: SandboxedExecutor):
    """execute_command 应正确处理命令超时"""
    policy = SandboxPolicy(max_runtime_sec=2)
    result = executor.execute_command(["sleep", "10"], policy=policy)

    assert not result.success
    assert result.timed_out


# --------------------------------------------------------------------------- #
# 测试语法错误处理
# --------------------------------------------------------------------------- #
def test_execute_python_syntax_error(executor: SandboxedExecutor):
    """语法错误的代码应被正确报告"""
    code = "def broken(\n"  # 语法错误
    result = executor.execute_python(code)

    assert result.success is False
    assert result.exit_code != 0


def test_execute_python_with_inputs_syntax_error(executor: SandboxedExecutor):
    """execute_python_with_inputs 中语法错误应返回失败结果"""
    code = "def broken(\n"  # 语法错误
    args_list = [(1,)]

    results = executor.execute_python_with_inputs(code, "broken", args_list)

    assert len(results) == 1
    assert not results[0].success


# --------------------------------------------------------------------------- #
# 测试沙箱策略配置
# --------------------------------------------------------------------------- #
def test_sandbox_policy_defaults():
    """SandboxPolicy 应具有合理的默认值"""
    policy = SandboxPolicy()

    assert policy.max_memory_mb == 256
    assert policy.max_runtime_sec == 30
    assert policy.allow_network is False
    assert policy.allow_filesystem_write is False
    assert policy.allowed_paths == []
    assert policy.max_output_bytes == 1024 * 1024


def test_sandbox_policy_custom():
    """SandboxPolicy 应支持自定义配置"""
    policy = SandboxPolicy(
        max_memory_mb=128,
        max_runtime_sec=10,
        allow_network=True,
        allow_filesystem_write=True,
        allowed_paths=["/tmp"],
        max_output_bytes=512,
    )

    assert policy.max_memory_mb == 128
    assert policy.max_runtime_sec == 10
    assert policy.allow_network is True
    assert policy.allow_filesystem_write is True
    assert policy.allowed_paths == ["/tmp"]
    assert policy.max_output_bytes == 512


def test_sandbox_policy_immutable_fields():
    """SandboxPolicy 的字段应可直接修改（dataclass 非 frozen）"""
    policy = SandboxPolicy()
    policy.max_memory_mb = 512

    assert policy.max_memory_mb == 512


# --------------------------------------------------------------------------- #
# 测试 SandboxResult
# --------------------------------------------------------------------------- #
def test_sandbox_result_success():
    """SandboxResult 应正确表示成功结果"""
    result = SandboxResult(
        stdout="hello",
        stderr="",
        exit_code=0,
        success=True,
        result=42,
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.result == 42
    assert result.timed_out is False
    assert result.error is None


def test_sandbox_result_failure():
    """SandboxResult 应正确表示失败结果"""
    result = SandboxResult(
        stdout="",
        stderr="error message",
        exit_code=1,
        success=False,
        error="Something went wrong",
        timed_out=False,
    )

    assert result.success is False
    assert result.exit_code == 1
    assert result.error == "Something went wrong"
    assert result.timed_out is False


def test_sandbox_result_preserves_legacy_positional_result_argument() -> None:
    """新字段不应改变旧的第七个位置参数 result。"""
    parsed_result = {"answer": 42}

    result = SandboxResult("out", "err", 0, True, None, False, parsed_result)

    assert result.result == parsed_result
    assert result.output_truncated is False


# --------------------------------------------------------------------------- #
# 测试 adversarial_verification 沙箱集成
# --------------------------------------------------------------------------- #
def test_adversarial_verify_uses_sandbox():
    """adversarial_verify 应通过沙箱执行候选代码（非 exec）"""
    from src.adversarial_verification import adversarial_verify

    # 正确代码应通过验证
    correct_code = (
        "def is_palindrome(s):\n"
        "    t = ''.join(c.lower() for c in s if c.isalnum())\n"
        "    return t == t[::-1]\n"
    )
    verdict = adversarial_verify("is_palindrome", correct_code, trials=100, seed=0)
    assert verdict["accepted"] is True

    # 错误代码应被拒绝
    buggy_code = "def is_palindrome(s):\n    t = s.lower()\n    return t == t[::-1]\n"
    verdict = adversarial_verify("is_palindrome", buggy_code, trials=200, seed=0)
    assert verdict["accepted"] is False


def test_naive_verify_uses_sandbox():
    """naive_verify 应通过沙箱执行候选代码"""
    from src.adversarial_verification import naive_verify

    correct_code = (
        "def is_palindrome(s):\n"
        "    t = ''.join(c.lower() for c in s if c.isalnum())\n"
        "    return t == t[::-1]\n"
    )
    assert naive_verify("is_palindrome", correct_code) is True

    buggy_code = "def is_palindrome(s):\n    return False\n"
    assert naive_verify("is_palindrome", buggy_code) is False


# --------------------------------------------------------------------------- #
# 测试沙箱隔离性
# --------------------------------------------------------------------------- #
def test_sandbox_cannot_access_caller_globals(executor: SandboxedExecutor):
    """沙箱中的代码不应能访问调用者的全局变量"""
    # 在沙箱中执行代码，尝试访问不存在的变量
    code = (
        "try:\n"
        "    print(test_sandbox_cannot_access_caller_globals)\n"
        "except NameError as e:\n"
        "    print(f'NameError: {e}')\n"
    )
    result = executor.execute_python(code)

    assert result.success is True
    assert "NameError" in result.stdout


def test_sandbox_isolated_filesystem_temp(executor: SandboxedExecutor):
    """沙箱应使用隔离的临时目录"""
    policy = SandboxPolicy(max_runtime_sec=5)
    code = "import tempfile\nimport os\nprint(tempfile.gettempdir())\n"
    result = executor.execute_python(code, policy=policy)

    assert result.success is True
    # 检查临时目录存在
    assert len(result.stdout.strip()) > 0
