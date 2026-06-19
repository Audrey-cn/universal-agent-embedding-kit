# Excellence Evidence Design

## Context

UAEK is at 91/100 under the platform-artifact-readiness product score. That score proves platform evidence can be discovered, recorded and validated, but it intentionally keeps `LIVE_EXTERNAL_PLATFORM_RUNS`, `FULL_CROSS_PLATFORM_MATRIX` and `ADVERSARIAL_SELF_IMPROVEMENT_SUITE` open.

The next score target is 95+. This requires stronger evidence, not a score-only edit.

## Goal

Add an excellence evidence suite that moves the product maturity score above 95 only when the repository contains auditable evidence for:

- at least one successful `live_external` platform task artifact;
- a cross-platform artifact matrix covering Codex, Claude Code/App, Mimo Code and Hermes;
- adversarial validation checks that reject forged or incomplete live artifacts;
- a deterministic self-improvement scoring loop that resolves open findings only when evidence exists.

## Scoring Boundary

`benchmark --suite excellence` may recommend 96/100 when every required check passes. If no valid `live_external` task artifact exists, the suite must stay below 95 even if all readiness checks pass.

This remains an excellence-readiness product score. It is not a direct Fable 5 rerun because the reference model is retired. It is also not a claim that every platform completed a live task unless each provider has its own valid `live_external` artifact.

## Architecture

- `src/platform_runs.py` keeps the artifact schema and becomes stricter for `live_external` evidence.
- `src/excellence.py` reads platform artifacts, validates evidence, runs adversarial fixtures, computes a cross-platform matrix and returns score evidence.
- `src/benchmark.py` exposes the `excellence` suite and scorecard.
- `src/cli.py` adds `excellence` to `uaek benchmark --suite`.

## Required Artifacts

- `benchmarks/results/platform-runs/*-platform-run.json`: existing local command artifacts plus at least one live task artifact.
- `benchmarks/results/benchmark-excellence.json`: scorecard with current score, evidence metrics, checks and limitations.

## Verification

- TDD RED tests for strict live artifact validation and excellence scoring.
- GREEN implementation in focused modules.
- CLI smoke for `uaek benchmark --suite excellence`.
- Full ruff, mypy, pytest and coverage gates.
- JSON/YAML artifact validity checks.
