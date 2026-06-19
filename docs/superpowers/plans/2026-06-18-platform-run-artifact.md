# Platform Run Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a platform run artifact layer so external Agent runs can be recorded, validated and included in benchmark evidence.

**Architecture:** Keep the artifact logic in a focused `src/platform_runs.py` module. CLI remains a presentation layer for record/validate commands, and `src/benchmark.py` only consumes readiness output for scorecards.

**Tech Stack:** Python dataclasses/dicts, Click CLI, pytest, existing benchmark JSON writer.

---

### Task 1: Platform Run Module

**Files:**
- Create: `src/platform_runs.py`
- Test: `tests/unit/test_platform_runs.py`

- [x] Write failing tests for `record_platform_run`, `validate_platform_run_artifact`, and `run_platform_artifact_readiness`.
- [x] Run `.venv/bin/python -m pytest tests/unit/test_platform_runs.py -q` and confirm RED failures mention missing module/API.
- [x] Implement schema creation, validation and readiness output.
- [x] Re-run the focused test and confirm it passes.

### Task 2: CLI And Benchmark Integration

**Files:**
- Modify: `src/cli.py`
- Modify: `src/benchmark.py`
- Test: `tests/unit/test_platform_runs.py`

- [x] Add RED tests for `uaek platform record`, `uaek platform validate`, and `benchmark --suite platform`.
- [x] Run focused tests and confirm RED failures mention missing CLI group or unsupported suite.
- [x] Add `platform` Click group with `record` and `validate` commands.
- [x] Add `platform` to supported benchmark suites and output `platform_run_readiness`.
- [x] Re-run focused tests and confirm GREEN.

### Task 3: Evidence And Docs Sync

**Files:**
- Create: `benchmarks/results/platform-runs/*-platform-run.json`
- Create/modify: `benchmarks/results/benchmark-platform.json`
- Modify: `README.md`
- Modify: `VERIFICATION_SCORECARD.md`
- Modify: `FRAMEWORK_REVIEW.md`
- Modify: `PROJECT_AUDIT_REPORT.md`
- Modify: `PROGRESS_TRACKER.md`
- Modify: `task_plan.md`, `findings.md`, `progress.md`
- Modify: `.agent-workflow/findings.json`, `.agent-workflow/goals.json`

- [x] Run CLI smoke to write and validate a platform artifact.
- [x] Run `uaek benchmark --suite platform --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results`.
- [x] Update score language to 91/100 platform-artifact-readiness口径.
- [x] Keep live external platform run as an open limitation unless a `live_external` artifact exists.
- [x] Run final ruff, mypy, pytest and coverage gates.
