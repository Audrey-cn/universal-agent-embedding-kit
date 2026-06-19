# Platform Run Artifact Design

## Context

UAEK now has a command-backed external Agent Adapter and an adapter-readiness score of 90/100. The next gap is not another adapter contract; it is a durable way to record and validate real external platform runs when they become available.

This increment adds a platform run artifact layer. It can wrap an adapter result, mark the evidence level, validate the artifact, and include that readiness in benchmark output. It does not claim that Codex, Claude Code, OpenHands, or any other platform has completed a live benchmark unless the artifact explicitly records `evidence_level = "live_external"`.

## Goals

- Define `platform_run_v1` JSON artifact shape.
- Add validation for required fields, allowed evidence levels, success status and adapter payload provenance.
- Add `uaek platform record` to wrap an existing adapter result JSON into a platform run artifact.
- Add `uaek platform validate` for local gate checks.
- Add `benchmark --suite platform` to record platform-artifact readiness.
- Move the product score from 90 to 91 only under a platform-artifact-readiness口径.

## Artifact Shape

```json
{
  "schema": "platform_run_v1",
  "provider": "codex",
  "task": "adapter smoke task",
  "status": "completed",
  "evidence_level": "local_command",
  "run_id": "platform-...",
  "recorded_at": "2026-06-18T00:00:00+00:00",
  "adapter_result": {},
  "provenance": {
    "source": "uaek adapter run",
    "command": ["codex", "exec", "..."],
    "artifact_path": "benchmarks/results/platform-runs/codex-smoke.json"
  }
}
```

Allowed evidence levels:

- `contract`: schema or protocol proof only.
- `local_command`: local command-backed adapter run.
- `live_external`: real external platform task run with provider-specific artifact.

## Scoring Boundary

`benchmark --suite platform` can reach 91/100 when artifact recording, validation and score output are locally verified. It must keep `LIVE_EXTERNAL_PLATFORM_RUNS` open unless at least one valid artifact has `evidence_level = "live_external"`.

## Verification

- RED tests for module API, CLI record/validate and benchmark suite.
- GREEN tests using deterministic adapter result fixtures.
- CLI smoke that writes a platform run artifact under `benchmarks/results/platform-runs/`.
- Ruff, mypy, full pytest and coverage gates before updating score documents.
