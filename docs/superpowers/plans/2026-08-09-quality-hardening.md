# UAEK 0.3 Quality Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the concrete path, data-loss, false-green, portability, and documentation drift risks found by the lightweight quality audit without expanding the 0.3 feature surface.

**Architecture:** Harden the existing boundaries in place: campaign validation owns safe artifact names and resumability, memory persistence owns durable writes and unique IDs, and repository tooling owns reproducible setup/container contracts. Keep CLI/API/MCP behavior shared and preserve the base install's three-dependency shape.

**Tech Stack:** Python 3.11+, pytest, Click, PyYAML, uv, Bash, Docker, GitHub Actions.

## Global Constraints

- Base runtime dependencies remain PyYAML, Rich, and Click only.
- Optional memory integrations remain lazy and outside the base install.
- Existing evidence artifacts remain immutable; successful samples are validated before reuse.
- Historical planning documents remain historical; only active instructions and current-state facts are normalized.
- Every Python behavior change follows RED → GREEN → focused regression → full verification.

---

### Task 1: Safe and resumable evidence campaigns

**Files:**
- Modify: `src/evidence/campaign.py`
- Test: `tests/unit/test_evidence_campaign.py`

**Interfaces:**
- Consumes: `validate_campaign_artifact(source)` and immutable per-sample JSON files.
- Produces: safe `sample_id` validation and `run_campaign(..., resume: bool = False)` behavior.

- [ ] **Step 1: Write failing path-safety tests**

Add tests that reject explicit and generated IDs containing `/`, `\\`, `..`, leading dots, or whitespace-only path components.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/unit/test_evidence_campaign.py -q`

Expected: traversal manifests are currently accepted.

- [ ] **Step 3: Implement minimal safe-ID validation**

Use one compiled slug pattern (`[A-Za-z0-9][A-Za-z0-9._-]*`) and reject `.`/`..`; validate both provider-derived and explicit IDs before building paths. Resolve each output and require its parent to equal the resolved artifact directory.

- [ ] **Step 4: Write and verify failing resume tests**

Create one valid completed artifact, rerun with `resume=True`, and assert the completed sample is validated and skipped while remaining samples run. Assert the default still refuses collisions.

- [ ] **Step 5: Implement minimal resume behavior**

When `resume=True`, reuse only an existing artifact that passes campaign validation and whose embedded sample metadata exactly matches the planned sample. Return `reused_artifact_paths` separately from newly written paths.

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest tests/unit/test_evidence_campaign.py tests/unit/test_evidence_cli.py -q`

---

### Task 2: Durable and collision-free memory

**Files:**
- Modify: `src/memory/persistence.py`
- Modify: `src/memory/service.py`
- Modify: `api/server.py`
- Test: `tests/unit/test_memory.py`
- Test: `tests/unit/test_api.py`

**Interfaces:**
- Consumes: `MemoryPersistence.save/load` and `MemoryService.add`.
- Produces: atomic per-layer replacement, explicit corrupt-data errors, UUID-backed default IDs, and duplicate-ID rejection.

- [ ] **Step 1: Write failing corruption and duplicate-ID tests**

Assert malformed persisted JSON raises `ValueError` naming the corrupt file; assert adding the same explicit ID twice raises `ValueError`; assert API adds do not provide a timestamp-derived ID.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/unit/test_memory.py tests/unit/test_api.py -q`

- [ ] **Step 3: Implement atomic writes and explicit corruption**

Serialize first, write a same-directory temporary file, flush and `fsync`, then `os.replace`. Delete an uninstalled temporary file in `finally`. Wrap malformed JSON/schema data in `ValueError` without interpreting it as an empty store.

- [ ] **Step 4: Implement unique IDs and collision rejection**

Use `uuid.uuid4().hex` for generated IDs, reject an ID already present in any layer, and let the API call `MemoryService.add` without overriding `entry_id`.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/unit/test_memory.py tests/unit/test_memory_coverage.py tests/unit/test_api.py tests/unit/test_productization.py -q`

---

### Task 3: Truthful setup gates and lean development dependencies

**Files:**
- Modify: `scripts/setup.sh`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/unit/test_productization.py`

**Interfaces:**
- Produces: non-zero setup exit on any failed gate and a lockfile checked by CI.

- [ ] **Step 1: Write failing setup-exit test**

Run `setup.sh --verify` in a temporary fixture repository with a fake Python command that fails Ruff, and assert the script exits non-zero.

- [ ] **Step 2: Verify RED and fix setup**

Replace `command && success || warning` chains with plain fail-fast commands followed by success messages. Keep `--verify` explicit.

- [ ] **Step 3: Remove unused development facts**

Remove `black`, its configuration block, and `pytest-asyncio`; the project uses Ruff formatting and has no async pytest tests.

- [ ] **Step 4: Regenerate and gate the lock**

Run `uv lock` against the canonical default index. Add a pinned uv install plus `uv lock --check` to CI before package installation.

- [ ] **Step 5: Verify**

Run: `uv lock --check`, the setup contract test, Ruff, and Mypy.

---

### Task 4: Reproducible development container

**Files:**
- Create: `.dockerignore`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Test: `tests/unit/test_productization.py`

**Interfaces:**
- Produces: a container that installs after source copy and contains CLI/API/MCP plus repository test fixtures.

- [ ] **Step 1: Write failing Docker contract test**

Assert `COPY . .` precedes `pip install`, the compose mounts include `src`, `api`, `mcp`, and tests, and `.dockerignore` excludes VCS/worktree/venv/build caches.

- [ ] **Step 2: Verify RED and implement**

Add `.dockerignore`, copy the filtered repository before `pip install .[dev]`, and add API/MCP live-edit mounts to compose.

- [ ] **Step 3: Verify**

Run the contract test. If Docker exists, build the image and run CLI/API/MCP smoke plus pytest; otherwise record the unverified runtime boundary.

---

### Task 5: One current 0.3 documentation surface

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/support-matrix.md`
- Modify: `SOP.md`
- Modify: `EXECUTION_MANUAL.md`
- Modify: `VERIFICATION_SCORECARD.md`
- Modify: `docs/guides/capability-batch.md`
- Test: `tests/unit/test_version_contract.py`

**Interfaces:**
- Produces: current version/setup facts and portable examples; historical plan files remain unchanged.

- [ ] **Step 1: Extend the version contract test**

Assert the active support matrix names `0.3.0.dev1`, active setup examples use `--verify`, and active portable docs contain no `/Users/audrey` paths.

- [ ] **Step 2: Verify RED and update active docs**

Use repository-relative paths, rename the support matrix to 0.3, point README status to the workflow's main page rather than a duplicated run ID, and update the scorecard's current run to commit `ea1b2120c7ff` / run `31277812279`.

- [ ] **Step 3: Verify GREEN**

Run: `python -m pytest tests/unit/test_version_contract.py tests/unit/test_run_ci_baseline.py -q`.

---

### Task 6: Full verification and handoff

**Files:**
- Review all changed files only.

- [ ] **Step 1: Run complete quality gates**

Run Ruff over `src api mcp tests scripts`, Mypy over `src api mcp`, full pytest with coverage JSON and 75% floor, supported coverage checker, `uv lock --check`, and wheel build/install smoke.

- [ ] **Step 2: Inspect final diff and repository state**

Confirm no credential material, generated result artifacts, local paths, caches, or unrelated changes entered the branch.

- [ ] **Step 3: Use finishing-a-development-branch**

After fresh verification, present merge/push/keep/discard options without performing an external integration action until the user chooses.
