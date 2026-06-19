# Live Matrix Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `live_matrix` benchmark that evaluates live task evidence per provider and moves the score beyond 96 only when stronger matrix evidence exists.

**Architecture:** Add `src/live_matrix.py` as a focused evaluator over existing `platform_run_v1` artifacts. Wire it into `src/benchmark.py` and `src/cli.py`, then generate Mimo/Hermes live artifacts and a Claude blocked attempt artifact.

**Tech Stack:** Python, Click, pytest, existing command adapter, existing platform artifact validation.

---

### Task 1: Live Matrix Evaluator

**Files:**
- Create: `tests/unit/test_live_matrix.py`
- Create: `src/live_matrix.py`

- [x] Write RED tests for a partial 3/4 live matrix with Claude blocked.
- [x] Write RED tests for a full 4/4 live matrix.
- [x] Implement artifact loading, provider statuses, diagnostics, and score recommendations.
- [x] Re-run focused tests and confirm GREEN.

### Task 2: Benchmark And CLI Wiring

**Files:**
- Modify: `src/benchmark.py`
- Modify: `src/cli.py`
- Test: `tests/unit/test_live_matrix.py`

- [x] Add RED tests for `run_benchmark("live_matrix")` and `uaek benchmark --suite live_matrix`.
- [x] Add `live_matrix` to supported suites, scorecard logic and CLI choices.
- [x] Re-run focused tests and confirm GREEN.

### Task 3: Live Artifact Generation

**Files:**
- Create: `benchmarks/results/platform-runs/mimo-live-*`
- Create: `benchmarks/results/platform-runs/hermes-live-*`
- Create: `benchmarks/results/platform-runs/claude-live-*`
- Create/modify: `benchmarks/results/benchmark-live_matrix.json`

- [x] Generate Mimo Code live adapter output and platform artifact.
- [x] Generate Hermes live adapter output and platform artifact.
- [x] Record Claude App blocked live attempt without counting it as live evidence.
- [x] Run `uaek benchmark --suite live_matrix`.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`, `benchmarks/README.md`, `VERIFICATION_SCORECARD.md`
- Modify: `FRAMEWORK_REVIEW.md`, `PROJECT_AUDIT_REPORT.md`, `PROGRESS_TRACKER.md`
- Modify: `task_plan.md`, `findings.md`, `progress.md`
- Modify: `.agent-workflow/findings.json`, `.agent-workflow/goals.json`

- [x] Update score language to 97/100 when three providers have live evidence and Claude is blocked.
- [x] Keep full 4/4 live matrix as an open limitation.
- [x] Run ruff, mypy, focused tests, full pytest, coverage and JSON/YAML gates.
