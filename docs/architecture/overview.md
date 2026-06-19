# UAEK Architecture Overview

UAEK is organized as a reusable core library with thin product entrypoints.

## Core Layers

- `src/verify`: verification runners for tests, builds, lint, and fresh-context checks.
- `src/effort`: task complexity and effort classification.
- `src/workflow`: DAG, sequential, parallel, and config-driven workflow execution.
- `src/memory`: layered memory, persistence, compression, querying, and a stateful service facade.
- `src/skills`: skill discovery, loading, execution, and project-level markdown skill support.
- `src/harness`: local task pipeline that composes effort, workflow, verification, memory, and report output.
- `src/adapters`: external Agent Adapter interfaces and the command-backed stdin/stdout JSON adapter.
- `src/platform_runs.py`: platform run artifact recording, validation, and local platform discovery.
- `src/excellence.py`: excellence-readiness evaluator for live evidence, platform matrix, adversarial checks, and scoring loops.
- `src/live_matrix.py`: per-provider live external task matrix evaluator.
- `src/benchmark.py`: local benchmark and score evidence runner.

## Product Entrypoints

- CLI: `src/cli.py`, installed as `uaek`.
- HTTP API: `api/server.py`.
- MCP: `mcp/server.py` plus `mcp/tools/*`.

The product entrypoints should call shared runtime/service modules instead of duplicating business logic. Current shared product facades are:

- `src/workflow/runtime.py`
- `src/memory/service.py`
- `src/skills/service.py`
- `src/harness/local.py`
- `src/adapters/command.py`
- `src/platform_runs.py`
- `src/excellence.py`
- `src/live_matrix.py`
- `src/benchmark.py`

## Data Flow

```text
task/config
  -> effort/workflow runtime
  -> safe built-in task action
  -> verification/memory/skill services
  -> serializable result for CLI/API/MCP

external task
  -> AdapterRequest JSON over stdin
  -> command-backed external Agent
  -> AdapterRunResult JSON + JSONL trace

platform evidence
  -> adapter result JSON
  -> platform_run_v1 artifact
  -> validation + benchmark readiness score

excellence evidence
  -> validated live_external artifact
  -> cross-platform artifact matrix
  -> adversarial + self-improvement checks
  -> excellence readiness score

live matrix evidence
  -> per-provider live_external artifacts
  -> blocked/missing diagnostics
  -> live matrix readiness score
```

The local harness composes safe UAEK primitives and does not execute arbitrary user code. The command adapter is intentionally explicit: the user supplies the external command, UAEK supplies the protocol, timeout, normalization and trace capture.
