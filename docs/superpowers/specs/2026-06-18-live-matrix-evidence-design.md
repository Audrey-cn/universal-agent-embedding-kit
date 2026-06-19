# Live Matrix Evidence Design

## Goal

Move beyond 96/100 excellence-readiness by measuring whether every discovered platform has a valid `live_external` task artifact.

## Scope

This phase adds a dedicated `live_matrix` benchmark. It does not claim a retired Fable 5 rerun, remote CI success, release readiness, or cost superiority. It only evaluates live task evidence for Codex, Claude Code/App, Mimo Code, and Hermes.

## Evidence Rules

- A provider counts as live only when at least one artifact validates with `is_live_external = true`.
- Failed `live_external` artifacts are loaded as blocked attempts but never counted as live.
- Providers without a live artifact are classified as `blocked` when there is a failed live attempt, otherwise `missing`.
- A partial matrix with three live providers and structured diagnostics for the fourth can recommend 97/100.
- A full matrix with four live providers can recommend 98/100.

## Components

- `src/live_matrix.py` loads `platform_run_v1` artifacts and computes per-provider live status.
- `src/benchmark.py` exposes `suite="live_matrix"` and scorecard language.
- `src/cli.py` adds `live_matrix` to benchmark choices and output.
- `tests/unit/test_live_matrix.py` covers partial and full matrices plus CLI wiring.

## Data Flow

```text
platform_run_v1 artifacts
  -> validate_platform_run_artifact
  -> per-provider live/blocked/missing status
  -> live_matrix readiness report
  -> benchmark-live_matrix.json scorecard
```

## Current Expected Outcome

Codex already has valid live evidence. Mimo Code and Hermes can run non-interactive sentinel tasks on this machine and should be promoted to `live_external` artifacts. Claude App currently fails in a headless Electron entrypoint with IndexedDB lock/timeout behavior, so it should remain a blocked live attempt unless a working CLI path appears.
