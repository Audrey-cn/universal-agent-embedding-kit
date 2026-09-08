"""Tests for config management and structured run logging."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_load_config_reads_default_yaml():
    """Config loader should expose the execution-manual settings as typed data."""
    from src.config import load_config
    from src.version import SOURCE_VERSION

    config = load_config(Path("config/default.yaml"))

    assert config.version == SOURCE_VERSION
    assert config.memory.storage_path == ".uaek/harness-memory"
    assert config.memory.default_layer == "l2"
    assert "effort" in config.workflow.safe_actions
    assert config.verification.test_command == ".venv/bin/python -m pytest"


def test_load_config_no_path_reads_repo_default_and_tags_source():
    """load_config() with no path reads the repo default file and tags its source."""
    from src.config import load_config

    config = load_config()

    assert config.source.endswith("config/default.yaml")
    # The repo default file is aligned with the built-in defaults, so loading it
    # is behavior-neutral (storage path and allowlist unchanged).
    assert config.memory.storage_path == ".uaek/harness-memory"
    assert set(config.workflow.safe_actions) == {"noop", "echo", "concat", "sum", "effort", "fail"}


def test_load_config_env_override_wins(tmp_path: Path, monkeypatch):
    """$UAEK_CONFIG takes precedence over the repo default file."""
    from src.config import load_config

    override = tmp_path / "override.yaml"
    override.write_text(
        'uaek:\n  memory:\n    storage_path: "custom-path"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("UAEK_CONFIG", str(override))

    config = load_config()

    assert config.source == str(override)
    assert config.memory.storage_path == "custom-path"


def test_load_config_env_missing_file_raises(tmp_path: Path, monkeypatch):
    """A UAEK_CONFIG pointing at a missing file must fail loudly, not silently fall back."""
    import pytest

    from src.config import load_config

    monkeypatch.setenv("UAEK_CONFIG", str(tmp_path / "missing.yaml"))

    with pytest.raises(ValueError, match="UAEK_CONFIG"):
        load_config()


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
