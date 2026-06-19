# Score Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement benchmark result generation and a minimal Agent Harness so the project score can be aligned to fresh evidence.

**Architecture:** Add focused modules for benchmark and harness behavior. CLI remains a thin presentation layer. Documentation and score ledgers are updated only after tests and smoke commands pass.

**Tech Stack:** Python 3.11, Click, pytest, existing UAEK effort/workflow/memory services.

---

### Task 1: Benchmark Evidence Runner

**Files:**
- Create: `src/benchmark.py`
- Modify: `src/cli.py`
- Test: `tests/unit/test_score_alignment.py`

- [x] Write failing tests for `run_benchmark()` and `uaek benchmark --suite quick --output`.
- [x] Verify RED with `.venv/bin/python -m pytest tests/unit/test_score_alignment.py -q`.
- [x] Implement `run_benchmark()`, JSON output helper, and CLI integration.
- [x] Verify GREEN with `.venv/bin/python -m pytest tests/unit/test_score_alignment.py -q`.

### Task 2: Minimal Agent Harness

**Files:**
- Create: `src/harness/interface.py`
- Create: `src/harness/local.py`
- Modify: `src/harness/__init__.py`
- Test: `tests/unit/test_score_alignment.py`

- [x] Write failing test for task -> effort -> workflow -> verification -> memory -> report.
- [x] Verify RED with `.venv/bin/python -m pytest tests/unit/test_score_alignment.py -q`.
- [x] Implement dataclasses and local harness pipeline.
- [x] Verify GREEN with `.venv/bin/python -m pytest tests/unit/test_score_alignment.py -q`.

### Task 3: Score and Ledger Sync

**Files:**
- Modify: `README.md`
- Modify: `PROGRESS_TRACKER.md`
- Modify: `VERIFICATION_SCORECARD.md`
- Modify: `FRAMEWORK_REVIEW.md`
- Modify: `PROJECT_AUDIT_REPORT.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `.agent-workflow/findings.json`
- Modify: `.agent-workflow/goals.json`

- [x] Run focused and full verification.
- [x] Update score from 68/100 to the evidence-backed post-harness/post-benchmark score.
- [x] Mark F008/F009 resolved, keep F007 open or partial because external Fable 5 baseline is still absent.
- [x] Record command outputs in `progress.md`.
