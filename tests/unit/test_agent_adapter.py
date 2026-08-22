"""Tests for external Agent Adapter readiness."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import main


def test_command_agent_adapter_runs_json_protocol_and_writes_trace(tmp_path: Path):
    """Command adapter should normalize a JSON-speaking external command."""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    script = _write_adapter_script(tmp_path)
    trace_path = tmp_path / "adapter-trace.jsonl"
    adapter = CommandAgentAdapter(
        [sys.executable, str(script)],
        provider="fixture-agent",
        timeout_seconds=5,
        trace_path=trace_path,
    )

    result = adapter.run(
        AdapterRequest(
            task="validate external adapter contract",
            context={"repo": "uaek"},
            metadata={"trace_id": "trace-001"},
        )
    )

    assert result.success is True
    assert result.provider == "fixture-agent"
    assert result.trace_id == "trace-001"
    assert result.output == "adapter handled: validate external adapter contract"
    assert result.artifacts["task"] == "validate external adapter contract"
    assert result.metrics["context_keys"] == 1
    assert result.return_code == 0
    assert "fixture stderr" in result.stderr
    assert result.duration_ms >= 0

    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert trace["event"] == "adapter_run"
    assert trace["provider"] == "fixture-agent"
    assert trace["success"] is True
    assert trace["trace_id"] == "trace-001"


def test_command_agent_adapter_reports_invalid_json_and_timeout(tmp_path: Path):
    """Adapter failures should preserve diagnostics instead of raising."""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    bad_script = tmp_path / "bad_adapter.py"
    bad_script.write_text("print('not json')\n", encoding="utf-8")

    bad_result = CommandAgentAdapter(
        [sys.executable, str(bad_script)],
        provider="bad-agent",
    ).run(AdapterRequest(task="bad output"))

    assert bad_result.success is False
    assert bad_result.error
    assert "Invalid JSON" in bad_result.error
    assert bad_result.stdout.strip() == "not json"

    slow_script = tmp_path / "slow_adapter.py"
    slow_script.write_text(
        "import time\ntime.sleep(1)\n",
        encoding="utf-8",
    )

    timeout_result = CommandAgentAdapter(
        [sys.executable, str(slow_script)],
        provider="slow-agent",
        timeout_seconds=0.05,
    ).run(AdapterRequest(task="timeout"))

    assert timeout_result.success is False
    assert timeout_result.error
    assert "timed out" in timeout_result.error.lower()


def test_command_adapter_reports_output_limit_before_parsing_json(tmp_path: Path):
    """Adapter output beyond its shared byte budget is a distinct failure."""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    script = tmp_path / "large_output_adapter.py"
    script.write_text(
        "import sys\nsys.stdout.write('x' * 256)\n",
        encoding="utf-8",
    )

    result = CommandAgentAdapter(
        [sys.executable, str(script)],
        max_output_bytes=128,
    ).run(AdapterRequest(task="bounded output"))

    assert result.success is False
    assert result.error == "Adapter command output exceeded 128 bytes"
    assert "Invalid JSON" not in result.error
    assert len(result.stdout.encode("utf-8")) <= 128


def test_command_adapter_enforces_configured_runtime_limit(tmp_path: Path):
    """The adapter timeout must bound an otherwise idle child process."""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    script = tmp_path / "slow_adapter.py"
    script.write_text("import time\ntime.sleep(1)\n", encoding="utf-8")

    result = CommandAgentAdapter(
        [sys.executable, str(script)],
        timeout_seconds=0.05,
    ).run(AdapterRequest(task="bounded runtime"))

    assert result.success is False
    assert result.error == "Adapter command timed out after 0.05s"


def test_command_adapter_preserves_parent_environment_for_trusted_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """User-selected adapter commands retain parent credentials and configuration."""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    environment_key = "UAEK_ADAPTER_TEST_TOKEN"
    monkeypatch.setenv(environment_key, "visible-to-trusted-command")
    script = tmp_path / "environment_adapter.py"
    script.write_text(
        "import json\n"
        "import os\n"
        "import sys\n"
        "json.load(sys.stdin)\n"
        f"print(json.dumps({{'success': True, 'output': os.environ[{environment_key!r}]}}))\n",
        encoding="utf-8",
    )

    result = CommandAgentAdapter([sys.executable, str(script)]).run(
        AdapterRequest(task="environment")
    )

    assert result.success is True
    assert result.output == "visible-to-trusted-command"


def test_command_adapter_rejects_an_empty_command():
    """An adapter command requires at least one executable token."""
    from src.adapters import CommandAgentAdapter

    with pytest.raises(ValueError, match="command token"):
        CommandAgentAdapter([])


@pytest.mark.parametrize(
    ("kwargs", "field_name"),
    [
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": -1}, "timeout_seconds"),
        ({"timeout_seconds": math.inf}, "timeout_seconds"),
        ({"timeout_seconds": math.nan}, "timeout_seconds"),
        ({"max_memory_mb": 0}, "max_memory_mb"),
        ({"max_memory_mb": -1}, "max_memory_mb"),
        ({"max_memory_mb": math.inf}, "max_memory_mb"),
        ({"max_memory_mb": math.nan}, "max_memory_mb"),
        ({"max_output_bytes": 0}, "max_output_bytes"),
        ({"max_output_bytes": -1}, "max_output_bytes"),
        ({"max_output_bytes": math.inf}, "max_output_bytes"),
        ({"max_output_bytes": math.nan}, "max_output_bytes"),
    ],
)
def test_command_adapter_rejects_non_positive_or_non_finite_limits(
    kwargs: dict[str, float], field_name: str
):
    """Constructor rejects invalid limits instead of deferring unsafe process setup."""
    from src.adapters import CommandAgentAdapter

    with pytest.raises(ValueError, match=field_name):
        CommandAgentAdapter([sys.executable, "-c", "pass"], **kwargs)


def test_cli_adapter_run_writes_output_and_trace(tmp_path: Path):
    """uaek adapter run should expose the command adapter contract."""
    script = _write_adapter_script(tmp_path)
    output_path = tmp_path / "adapter-result.json"
    trace_path = tmp_path / "adapter-trace.jsonl"

    result = CliRunner().invoke(
        main,
        [
            "adapter",
            "run",
            "cli adapter task",
            "--provider",
            "fixture-agent",
            "--command",
            sys.executable,
            "--command",
            str(script),
            "--context",
            '{"source":"cli"}',
            "--output",
            str(output_path),
            "--trace",
            str(trace_path),
        ],
    )

    assert result.exit_code == 0
    assert "Adapter Run" in result.output
    assert output_path.exists()
    assert trace_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["provider"] == "fixture-agent"
    assert payload["output"] == "adapter handled: cli adapter task"
    assert payload["request"]["context"] == {"source": "cli"}


def test_benchmark_adapter_suite_records_readiness_score(tmp_path: Path):
    """Adapter benchmark should score readiness without claiming live platform runs."""
    from src.benchmark import run_benchmark, write_benchmark_result

    result = run_benchmark("adapter", iterations=1)

    assert result["suite"] == "adapter"
    assert result["status"] == "completed"
    assert result["scorecard"]["previous_score"] == 88
    assert result["scorecard"]["current_score"] == 90
    assert "F016_EXTERNAL_ADAPTER_CONTRACT" in result["scorecard"]["resolved_findings"]
    assert "LIVE_EXTERNAL_PLATFORM_RUNS" in result["scorecard"]["remaining_findings"]
    assert result["adapter_readiness"]["status"] == "completed"
    assert result["adapter_readiness"]["metrics"]["required_checks"] == 4
    assert result["adapter_readiness"]["metrics"]["passed_required_checks"] == 4
    assert any(
        check["id"] == "bounded_output_diagnostics" and check["status"] == "pass"
        for check in result["adapter_readiness"]["checks"]
    )

    output_path = write_benchmark_result(result, tmp_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["scorecard"]["current_score"] == 90
    assert data["adapter_readiness"]["protocol"] == "stdin_stdout_json_v1"


def _write_adapter_script(tmp_path: Path) -> Path:
    script = tmp_path / "adapter_fixture.py"
    script.write_text(
        "import json\n"
        "import sys\n"
        "payload = json.load(sys.stdin)\n"
        "sys.stderr.write('fixture stderr\\n')\n"
        "print(json.dumps({\n"
        "    'success': True,\n"
        "    'output': 'adapter handled: ' + payload['task'],\n"
        "    'artifacts': {'task': payload['task']},\n"
        "    'metrics': {'context_keys': len(payload.get('context', {}))},\n"
        "}))\n",
        encoding="utf-8",
    )
    return script
