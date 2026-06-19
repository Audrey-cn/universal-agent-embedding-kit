# Excellence Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move UAEK from 91/100 platform-artifact-readiness to 95+ excellence-readiness using reproducible code, artifacts, documentation and verification gates.

**Architecture:** Add a focused `src/excellence.py` evaluator that consumes `platform_run_v1` artifacts and returns a score-ready evidence report. Tighten live artifact validation in `src/platform_runs.py`, then wire the new suite through `src/benchmark.py` and `src/cli.py`.

**Tech Stack:** Python, Click, pytest, existing JSON artifact writer, existing platform/adapters modules.

---

### Task 1: Strict Live Artifact Validation

**Files:**
- Modify: `src/platform_runs.py`
- Test: `tests/unit/test_excellence.py`

- [x] Write RED tests showing failed or incomplete `live_external` artifacts are invalid for score evidence.
- [x] Run `.venv/bin/python -m pytest tests/unit/test_excellence.py -q` and confirm expected failures.
- [x] Update `validate_platform_run_artifact` so `is_live_external` is true only for completed, successful, nonempty-output artifacts with provenance.
- [x] Re-run focused tests and confirm GREEN.

### Task 2: Excellence Evidence Evaluator

**Files:**
- Create: `src/excellence.py`
- Test: `tests/unit/test_excellence.py`

- [x] Add RED tests for `run_excellence_readiness` with no live artifact and with one valid live artifact.
- [x] Implement artifact loading, provider matrix, adversarial validation and self-improvement scoring loop.
- [x] Re-run focused tests and confirm GREEN.

### Task 3: Benchmark And CLI Wiring

**Files:**
- Modify: `src/benchmark.py`
- Modify: `src/cli.py`
- Test: `tests/unit/test_excellence.py`

- [x] Add RED tests for `run_benchmark("excellence")` and `uaek benchmark --suite excellence`.
- [x] Add `excellence` to supported suites, benchmark output and CLI choices.
- [x] Re-run focused tests and confirm GREEN.

### Task 4: Evidence Generation And Score Sync

**Files:**
- Create: `benchmarks/results/platform-runs/*-live-*-platform-run.json`
- Create/modify: `benchmarks/results/benchmark-excellence.json`
- Modify: `README.md`, `benchmarks/README.md`, `VERIFICATION_SCORECARD.md`
- Modify: `FRAMEWORK_REVIEW.md`, `PROJECT_AUDIT_REPORT.md`, `PROGRESS_TRACKER.md`
- Modify: `task_plan.md`, `findings.md`, `progress.md`
- Modify: `.agent-workflow/findings.json`, `.agent-workflow/goals.json`

- [x] Generate at least one valid `live_external` task artifact from an installed external platform.
- [x] Run `.venv/bin/uaek benchmark --suite excellence --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results`.
- [x] Update score language to 96/100 excellence-readiness when evidence proves every required check.
- [x] Keep direct retired-model and full live-per-platform claims out of the score language.
- [x] Run final ruff, mypy, pytest, coverage and JSON/YAML gates.
