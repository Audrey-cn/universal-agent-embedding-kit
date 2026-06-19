"""Tests for config management and structured run logging."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_load_config_reads_default_yaml():
    """Config loader should expose the execution-manual settings as typed data."""
    from src.config import load_config

    config = load_config(Path("config/default.yaml"))

    assert config.version == "0.1.0-alpha"
    assert config.memory.storage_path == ".uaek/memory"
    assert config.memory.default_layer == "l2"
    assert "effort" in config.workflow.safe_actions
    assert config.verification.test_command == ".venv/bin/python -m pytest"


def test_cli_run_uses_config_memory_and_logging(tmp_path: Path):
    """uaek run --config should use configured memory defaults and log destination."""
    memory_path = tmp_path / "configured-memory"
    log_path = tmp_path / "configured-run.jsonl"
    config_path = tmp_path / "uaek.yaml"
    output_path = tmp_path / "run.json"
    config_path.write_text(
        f"""
uaek:
  memory:
    storage_path: "{memory_path}"
    default_layer: "l3"
  logging:
    enabled: true
    file_path: "{log_path}"
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        [
            "run",
            "configured harness task",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["memory"]["layer"] == "l3"
    assert (memory_path / "l3_persistent.json").exists()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "harness_run"
    assert records[-1]["task"] == "configured harness task"
    assert records[-1]["success"] is True


def test_cli_run_log_file_overrides_config(tmp_path: Path):
    """--log-file should override the configured logging path for one run."""
    config_log_path = tmp_path / "configured.jsonl"
    override_log_path = tmp_path / "override.jsonl"
    config_path = tmp_path / "uaek.yaml"
    config_path.write_text(
        f"""
uaek:
  logging:
    enabled: true
    file_path: "{config_log_path}"
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        [
            "run",
            "override logging path",
            "--config",
            str(config_path),
            "--log-file",
            str(override_log_path),
        ],
    )

    assert result.exit_code == 0
    assert override_log_path.exists()
    assert not config_log_path.exists()
