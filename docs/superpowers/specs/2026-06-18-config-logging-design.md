# UAEK Config And Logging Design

## Goal

Raise the evidence-backed product maturity score by completing the original execution manual items 7.4 and 7.5: configuration management and logging.

## Scope

- Add typed config loading for YAML and JSON files.
- Connect `uaek run --config` to memory and logging defaults.
- Add structured JSONL logging for local harness runs.
- Keep external Fable 5 benchmark claims unchanged until real external data exists.

## Components

- `src/config.py`: typed dataclasses and `load_config(path)`.
- `src/logger.py`: minimal JSONL event logger.
- `src/cli.py`: `run` command options `--config` and `--log-file`.
- `config/default.yaml`: default logging settings.

## Data Flow

1. CLI receives a task and optional config/log path.
2. `load_config` merges provided settings with safe defaults.
3. `AgentHarness` runs with configured memory storage and layer.
4. The run payload is optionally written to JSON.
5. `JsonlLogger` appends a compact `harness_run` event when logging is configured.

## Verification

- `tests/unit/test_config_logging.py` covers config loading, run config behavior, and log path override.
- Existing run, benchmark, and productization tests guard regressions.
- Full gates remain ruff, mypy, pytest, and coverage.

## Non-Goals

- No remote CI claim.
- No real Fable 5 baseline claim.
- No external Agent adapter implementation in this increment.
