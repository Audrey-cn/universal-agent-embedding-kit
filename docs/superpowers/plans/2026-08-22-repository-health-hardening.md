# Repository Health Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the confirmed code-execution, dependency, adapter, MCP portability, and evidence-drift gaps while preserving UAEK's `0.3.0.dev1` public contracts.

**Architecture:** Put process creation behind one bounded standard-library primitive, layer a task-specific restricted-Python policy over candidate grading, and keep trusted external adapter commands distinct from untrusted generated code. Remove ChromaDB from supported dependencies, add a wheel-installed MCP command, and derive active headline counts from versioned run evidence in CI.

**Tech Stack:** Python 3.11+, `subprocess`, `threading`, `resource` when available, `ast`, pytest, Ruff, Mypy, uv, setuptools, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-22-repository-health-hardening-design.md`

## Global Constraints

- Preserve CLI groups, HTTP routes, MCP tool names and JSON-RPC behavior, evidence artifact schemas, and package version `0.3.0.dev1`.
- Do not claim the subprocess boundary is a kernel sandbox; hostile-code isolation still requires an OS/container/VM boundary.
- Remove ChromaDB from every supported extra and prevent a globally installed copy from silently re-enabling it.
- Keep trusted user-selected adapter commands compatible with inherited credentials and configuration.
- Do not publish, push, create a release, or introduce a framework.
- Every behavior change follows RED → GREEN → focused regression → full verification.

---

### Task 1: Build one bounded subprocess primitive

**Files:**
- Modify: `src/security/sandbox.py`
- Modify: `src/security/__init__.py`
- Test: `tests/unit/test_sandbox.py`

**Interfaces:**
- Produces: `run_bounded_process(command: Sequence[str], *, input_text: str | None = None, policy: SandboxPolicy | None = None, env: Mapping[str, str] | None = None, cwd: Path | str | None = None) -> SandboxResult`.
- Extends: `SandboxResult.output_truncated: bool`.
- Consumed by: Tasks 2, 3, and 4.

- [ ] **Step 1: Write failing validation and output-bound tests**

Add focused tests proving that invalid non-positive limits are rejected, a Unicode-heavy stdout/stderr producer is drained without retaining more than `max_output_bytes` encoded bytes, and `output_truncated` is true:

```python
def test_bounded_process_caps_combined_output_bytes() -> None:
    policy = SandboxPolicy(max_runtime_sec=5, max_output_bytes=64)
    result = run_bounded_process(
        [sys.executable, "-c", "import sys; print('界' * 1000); sys.stderr.write('x' * 1000)"],
        policy=policy,
    )
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 64
    assert result.output_truncated is True


@pytest.mark.parametrize("field,value", [("max_runtime_sec", 0), ("max_memory_mb", -1), ("max_output_bytes", 0)])
def test_bounded_process_rejects_invalid_limits(field: str, value: int) -> None:
    policy = SandboxPolicy()
    setattr(policy, field, value)
    with pytest.raises(ValueError, match=field):
        run_bounded_process([sys.executable, "-c", "pass"], policy=policy)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_sandbox.py -k 'bounded_process' -q`

Expected: collection/import failure for missing `run_bounded_process` or missing `output_truncated`.

- [ ] **Step 3: Implement the minimal bounded runner**

Use `subprocess.Popen` plus one drain thread per output stream. Drain all bytes to avoid pipe deadlock, append only while the shared byte budget remains, decode with replacement, and set `output_truncated` when bytes are discarded. Validate finite positive policy limits before `Popen`.

Use `start_new_session=True` on POSIX and `CREATE_NEW_PROCESS_GROUP` on Windows. On timeout, kill the complete POSIX process group with `os.killpg(process.pid, signal.SIGKILL)` and fall back to `process.kill()`. Import `resource` conditionally so the module imports on Windows. Apply `RLIMIT_AS`/`DATA`/`RSS`, CPU, process-count, and file-size limits only when available.

The function must pass the exact `env` and `cwd` supplied by the caller; it must not silently merge the parent environment.

- [ ] **Step 4: Migrate existing `SandboxedExecutor` methods**

Replace temporary single files with `TemporaryDirectory(prefix="uaek-sandbox-")`, set `HOME`, `TMPDIR`, `PYTHONPATH`, and `cwd` to that directory, and call `run_bounded_process`. Remove the duplicate `_run_subprocess` implementation while keeping its method as a thin compatibility delegate if tests use it.

- [ ] **Step 5: Add timeout process-group regression coverage**

Add a helper script that starts a child process, records its PID inside `tmp_path`, and sleeps. After timeout, assert the result is timed out and the child PID no longer exists, skipping only when the platform cannot inspect PIDs.

- [ ] **Step 6: Run focused tests and static checks**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_sandbox.py -q
.venv/bin/python -m ruff check src/security/sandbox.py tests/unit/test_sandbox.py
.venv/bin/python -m mypy src/security/sandbox.py
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit**

```bash
git add src/security/sandbox.py src/security/__init__.py tests/unit/test_sandbox.py
git commit -m "fix(security): bound subprocess execution"
```

---

### Task 2: Restrict and isolate capability candidate grading

**Files:**
- Create: `src/security/python_policy.py`
- Modify: `src/capability_tasks.py`
- Test: `tests/unit/test_capability_matrix.py`
- Test: `tests/unit/test_security.py`

**Interfaces:**
- Produces: `validate_candidate_code(code: str, entrypoint: str) -> list[str]`.
- Produces: `run_candidate_cases(code: str, entrypoint: str, args_list: list[tuple[Any, ...]], *, timeout: float) -> list[SandboxResult]`.
- Preserves: `grade_code(task, code, timeout=20.0, held_out=HELD_OUT_COUNT) -> dict[str, Any]` result schema.

- [ ] **Step 1: Write policy RED tests**

Cover valid solutions for all ten `CAPABILITY_TASKS`, plus rejection of imports, top-level calls, `open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `locals`, `getattr`, `setattr`, `vars`, and any dunder name or attribute.

```python
@pytest.mark.parametrize(
    "code,diagnostic",
    [
        ("import os\ndef two_sum(nums, target): return []", "imports"),
        ("def two_sum(nums, target): return open('/etc/passwd').read()", "open"),
        ("def two_sum(nums, target): return ().__class__.__mro__", "dunder"),
        ("print('side effect')\ndef two_sum(nums, target): return []", "top-level"),
    ],
)
def test_grade_code_rejects_unsafe_candidate_syntax(code: str, diagnostic: str) -> None:
    result = grade_code(get_task("two_sum"), code)
    assert result["status"] == "fail"
    assert diagnostic in result["error"].lower()
```

- [ ] **Step 2: Run the policy tests and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_capability_matrix.py -k 'unsafe_candidate or all_reference' -q`

Expected: unsafe candidates currently execute or fail for the wrong reason.

- [ ] **Step 3: Implement AST validation**

Parse with `ast.parse`. Permit module docstrings and undecorated function definitions at top level. Reject import/class/with/global/nonlocal nodes, top-level executable statements, dangerous calls, and identifiers or attributes containing `__`. Require the named entrypoint to be defined exactly once.

The restricted runtime builtins must be an explicit dictionary containing only ordinary task helpers such as `abs`, `all`, `any`, `bool`, `dict`, `enumerate`, `filter`, `float`, `int`, `isinstance`, `len`, `list`, `map`, `max`, `min`, `range`, `reversed`, `round`, `set`, `sorted`, `str`, `sum`, `tuple`, `zip`, `Exception`, and `ValueError`.

- [ ] **Step 4: Implement isolated batch execution**

Build a trusted wrapper that reads candidate source and cases from JSON files, executes the validated source with `exec(compile(...), {"__builtins__": SAFE_BUILTINS})`, invokes the entrypoint, and emits the existing case-result JSON. Run it through `run_bounded_process` with a minimal environment and temporary `HOME`/cwd.

Do not use `importlib.util.spec_from_file_location` for candidate code. Convert policy rejection, truncation, timeout, invalid JSON, and runtime exceptions into `_grade_result(..., error=...)` without raising.

- [ ] **Step 5: Add environment and filesystem regression tests**

Set a sentinel secret in the parent environment and create a sentinel file outside the grader temp directory. Candidate attempts to read either must be rejected by policy. Also prove the ordinary correct solutions and held-out grading remain unchanged.

- [ ] **Step 6: Run focused suites**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_capability_matrix.py tests/unit/test_security.py -q
.venv/bin/python -m ruff check src/security/python_policy.py src/capability_tasks.py tests/unit/test_capability_matrix.py
.venv/bin/python -m mypy src/security/python_policy.py src/capability_tasks.py
```

- [ ] **Step 7: Commit**

```bash
git add src/security/python_policy.py src/capability_tasks.py tests/unit/test_capability_matrix.py tests/unit/test_security.py
git commit -m "fix(security): isolate capability grading"
```

---

### Task 3: Remove parent-process execution from scenario and property verification

**Files:**
- Modify: `src/security/python_policy.py`
- Modify: `src/scenario_benchmark.py`
- Modify: `src/verify/property_test.py`
- Test: `tests/unit/test_scenario_benchmark.py`
- Test: `tests/unit/test_scenario_pack_2.py`
- Test: `tests/unit/test_scenario_pack_3.py`
- Test: `tests/unit/test_advanced_verification.py`

**Interfaces:**
- Produces: `run_restricted_harness(code: str, entrypoint: str, harness: str, payload: dict[str, Any], *, timeout: float) -> SandboxResult` for repository-owned harnesses.
- Preserves: `evaluate_scenario(...)` report schema and `property_test_verify(...) -> VerificationResult`.

- [ ] **Step 1: Write failing parent-isolation tests**

For `evaluate_scenario`, pass code containing a top-level filesystem or environment side effect and assert a structured `load_error`/zero score while the sentinel remains unchanged. For `property_test_verify`, write an artifact containing `os.environ[...]` or `open(...)` and assert `passed=False` with a policy diagnostic.

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_scenario_benchmark.py -k isolation -q
.venv/bin/python -m pytest tests/unit/test_advanced_verification.py -k property_verify -q
```

Expected: current direct `exec` performs or attempts the side effect.

- [ ] **Step 3: Move scenario execution to a trusted harness**

Serialize scenario checks and reuse-probe data. The child harness executes validated candidate code with restricted builtins, runs equality checks, performs the repository-owned dependency swap in the same restricted namespace, and emits per-dimension pass counts plus load error. The parent retains score aggregation only.

- [ ] **Step 4: Move property verification to a trusted harness**

The child harness imports repository-owned `PropertyTester`, executes validated artifact code with restricted builtins, runs idempotent and/or no-crash checks using the requested trials and seed, and serializes only pass status, property type, trial counts, and safe counterexample representations. The parent reconstructs the existing `VerificationResult` shape.

- [ ] **Step 5: Run all scenario/property tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_scenario_benchmark.py tests/unit/test_scenario_pack_2.py tests/unit/test_scenario_pack_3.py tests/unit/test_advanced_verification.py -q
.venv/bin/python -m ruff check src/scenario_benchmark.py src/verify/property_test.py
.venv/bin/python -m mypy src/scenario_benchmark.py src/verify/property_test.py
```

- [ ] **Step 6: Commit**

```bash
git add src/security/python_policy.py src/scenario_benchmark.py src/verify/property_test.py tests/unit/test_scenario_benchmark.py tests/unit/test_scenario_pack_2.py tests/unit/test_scenario_pack_3.py tests/unit/test_advanced_verification.py
git commit -m "fix(verify): isolate dynamic Python checks"
```

---

### Task 4: Make command-adapter resource controls effective

**Files:**
- Modify: `src/adapters/command.py`
- Modify: `src/adapters/readiness.py`
- Test: `tests/unit/test_agent_adapter.py`

**Interfaces:**
- Consumes: `run_bounded_process` from Task 1.
- Preserves: `CommandAgentAdapter.__init__` and `AdapterRunResult` public fields.

- [ ] **Step 1: Write RED tests for configured limits**

Add real adapter scripts proving `max_output_bytes=128` produces a structured output-limit failure, `timeout_seconds=0.05` times out, and parent environment is still visible to the trusted adapter command. Add constructor rejection tests for empty/negative/non-finite timeout, memory, and output limits.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_agent_adapter.py -k 'limit or environment' -q`

Expected: the current post-capture truncation or missing validation fails assertions.

- [ ] **Step 3: Replace adapter-local process code**

Delete `_make_preexec`. Construct `SandboxPolicy` from `timeout_seconds`, `max_memory_mb`, and `max_output_bytes`; invoke `run_bounded_process` with `env=os.environ.copy()` and the JSON request as stdin. Treat `output_truncated` as a distinct adapter failure before JSON parsing. Preserve trace logging and invalid-JSON diagnostics.

- [ ] **Step 4: Strengthen readiness checks**

Add one required readiness check that verifies bounded output diagnostics. Keep live external credentials outside deterministic readiness.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_agent_adapter.py -q
.venv/bin/python -m ruff check src/adapters/command.py src/adapters/readiness.py tests/unit/test_agent_adapter.py
.venv/bin/python -m mypy src/adapters/command.py src/adapters/readiness.py
```

Then commit:

```bash
git add src/adapters/command.py src/adapters/readiness.py tests/unit/test_agent_adapter.py
git commit -m "fix(adapter): enforce configured process limits"
```

---

### Task 5: Retire ChromaDB and repair supported dependency sets

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/memory/vector_backends.py`
- Modify: `docs/architecture.md`
- Modify: `docs/support-matrix.md`
- Modify: `README.md`
- Modify: `README.zh.md`
- Test: `tests/unit/test_memory_advanced.py`
- Test: `tests/unit/test_productization.py`

**Interfaces:**
- Preserves symbol: `ChromaBackend` as a compatibility stub.
- Changes: `ChromaBackend(...)` always raises `RuntimeError` with a retirement message.
- Changes: `detect_chromadb() -> False` without importing `chromadb`.

- [ ] **Step 1: Write dependency and compatibility RED tests**

```python
def test_chromadb_backend_is_retired_without_importing_installed_package(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "chromadb", object())
    assert detect_chromadb() is False
    with pytest.raises(RuntimeError, match="retired"):
        ChromaBackend()


def test_supported_extras_do_not_include_chromadb() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    memory = project["optional-dependencies"]["memory"]
    assert all(not item.startswith("chromadb") for item in memory)
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_memory_advanced.py tests/unit/test_productization.py -k chroma -q`

- [ ] **Step 3: Remove and lock dependencies**

Remove `chromadb` from the memory extra and the Mypy override. Keep `sentence-transformers>=2.0`. Replace `ChromaBackend` with the compatibility stub and make `detect_chromadb` return `False`. Update active docs to name `SimpleBackend` as the supported store.

Run `uv lock` and then confirm `rg 'name = "chromadb"|name = "aiohttp"' uv.lock` returns no supported-path entries. If `aiohttp` remains through sentence-transformers, constrain it to a non-vulnerable version in the memory extra and refresh the lock.

- [ ] **Step 4: Audit core and all supported extras**

```bash
uv export --no-dev --no-emit-project --format requirements-txt --output-file /tmp/uaek-core.txt
uv export --all-extras --no-dev --no-emit-project --format requirements-txt --output-file /tmp/uaek-all.txt
uvx pip-audit==2.10.1 -r /tmp/uaek-core.txt
uvx pip-audit==2.10.1 -r /tmp/uaek-all.txt
```

Expected: both audits exit 0 with no known vulnerabilities.

- [ ] **Step 5: Run focused tests and commit**

```bash
.venv/bin/python -m pytest tests/unit/test_memory_advanced.py tests/unit/test_productization.py -q
git add pyproject.toml uv.lock src/memory/vector_backends.py docs/architecture.md docs/support-matrix.md README.md README.zh.md tests/unit/test_memory_advanced.py tests/unit/test_productization.py
git commit -m "fix(memory): retire vulnerable chromadb integration"
```

---

### Task 6: Add a relocatable MCP command

**Files:**
- Modify: `pyproject.toml`
- Modify: `mcp/config.json`
- Modify: `docs/api/mcp.md`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/unit/test_productization.py`
- Test: `tests/unit/test_version_contract.py`
- Test: `tests/integration/test_runtime_contract.py`

**Interfaces:**
- Produces console script: `uaek-mcp = mcp.server:main`.
- Preserves: `python -m mcp` and `python -m mcp.server`.

- [ ] **Step 1: Write config and metadata RED tests**

Assert `pyproject.toml` contains `uaek-mcp`, `mcp/config.json["command"] == "uaek-mcp"`, and the serialized config contains none of `/Users/`, `/home/`, `cwd`, or `PYTHONPATH`.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_productization.py tests/unit/test_version_contract.py -k mcp -q`

- [ ] **Step 3: Add the script and portable config**

Update `[project.scripts]`, simplify `mcp/config.json` to the command, args, idle-timeout environment, and metadata, and document editable/source installation before host configuration.

- [ ] **Step 4: Strengthen installed-wheel CI smoke**

After wheel installation, `cd /tmp`, pipe initialize/tools-list/shutdown into `/tmp/release-venv/bin/uaek-mcp`, and validate nine tools. Keep the existing module smoke as compatibility coverage.

- [ ] **Step 5: Run focused tests and commit**

```bash
.venv/bin/python -m pytest tests/unit/test_productization.py tests/unit/test_version_contract.py tests/integration/test_runtime_contract.py -q
git add pyproject.toml mcp/config.json docs/api/mcp.md .github/workflows/ci.yml tests/unit/test_productization.py tests/unit/test_version_contract.py tests/integration/test_runtime_contract.py
git commit -m "feat(mcp): add portable server entrypoint"
```

---

### Task 7: Enforce headline evidence consistency

**Files:**
- Create: `scripts/check_headline_consistency.py`
- Modify: `src/benchmark.py`
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `VERIFICATION_SCORECARD.md`
- Modify: `benchmarks/results/capability-matrix.json`
- Modify: `benchmarks/results/benchmark-capability.json`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/unit/test_audit.py`
- Test: `tests/unit/test_run_ci_baseline.py`
- Test: `tests/unit/test_version_contract.py`

**Interfaces:**
- Produces: `derive_headline(artifact_dir: Path) -> str`, returning `"3/4"` for current evidence.
- Produces CLI: `python scripts/check_headline_consistency.py` with exit 0 only when all active surfaces agree.

- [ ] **Step 1: Write validator RED tests**

Create temporary capability-run artifacts yielding 2/4 and documents containing 3/4; assert the validator returns a diagnostic naming the mismatched file. Add a current-repository test expecting `3/4` in both README files, the scorecard current summary, and regenerated matrix metrics.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_audit.py tests/unit/test_version_contract.py -k headline -q`

- [ ] **Step 3: Implement the authority and validator**

Call `run_capability_readiness(Path("benchmarks/results/capability-runs"))`; format its two counts; inspect only active README files, the current scorecard summary, `capability-matrix.json`, and `benchmark-capability.json`. Exclude CHANGELOG and dated design/plan files. Diagnostics must contain the expected headline and every stale path.

Extend `_build_evidence_consistency` so `uaek audit` reports the same active-surface errors instead of maintaining a separate rule.

- [ ] **Step 4: Regenerate active artifacts and documentation**

Run the capability benchmark/matrix commands against existing artifacts, update English and Chinese README from 2/4 to 3/4, and label the older held-out regrade finding as historical without changing its recorded scores.

- [ ] **Step 5: Wire CI and run focused tests**

Add `python scripts/check_headline_consistency.py` after evidence validation. Run:

```bash
.venv/bin/python scripts/check_headline_consistency.py
.venv/bin/python -m pytest tests/unit/test_audit.py tests/unit/test_run_ci_baseline.py tests/unit/test_version_contract.py -q
```

- [ ] **Step 6: Commit**

```bash
git add scripts/check_headline_consistency.py src/benchmark.py README.md README.zh.md VERIFICATION_SCORECARD.md benchmarks/results/capability-matrix.json benchmarks/results/benchmark-capability.json .github/workflows/ci.yml tests/unit/test_audit.py tests/unit/test_run_ci_baseline.py tests/unit/test_version_contract.py
git commit -m "fix(evidence): gate active headline consistency"
```

---

### Task 8: Add dependency and formatting quality gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/setup.sh`
- Modify: `CONTRIBUTING.md`
- Modify: `SECURITY.md`
- Mechanically format: `src/**/*.py`, `api/**/*.py`, `mcp/**/*.py`, `tests/**/*.py`, `scripts/**/*.py`
- Test: `tests/unit/test_run_ci_baseline.py`
- Test: `tests/unit/test_productization.py`

**Interfaces:**
- CI guarantees Ruff lint + format, Mypy, tests/coverage, core/all-extras dependency audit, evidence consistency, and wheel smoke.

- [ ] **Step 1: Write CI/source-contract RED tests**

Assert the workflow contains `ruff format --check`, two `pip-audit` invocations over exported core/all requirements, and the headline validator. Assert `scripts/setup.sh --verify` runs format checking. Assert `SECURITY.md` names `0.3.0.dev1/main` and accurately describes subprocess limitations.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_run_ci_baseline.py tests/unit/test_productization.py -k 'format or audit or security' -q`

- [ ] **Step 3: Wire gates and documentation**

Use `uv export` plus `uvx pip-audit==2.10.1` in CI without adding `pip-audit` to runtime dependencies. Add format checking to setup and contribution commands. Update security support/version language and distinguish trusted adapters, restricted candidate execution, and the residual non-kernel boundary.

- [ ] **Step 4: Apply one isolated mechanical format batch**

Run `.venv/bin/python -m ruff format src api mcp tests scripts`. Inspect `git diff --stat` and confirm the batch contains formatting only outside files already changed for behavior.

- [ ] **Step 5: Run quality contract tests and commit**

```bash
.venv/bin/python -m pytest tests/unit/test_run_ci_baseline.py tests/unit/test_productization.py -q
.venv/bin/python -m ruff check src api mcp tests scripts
.venv/bin/python -m ruff format --check src api mcp tests scripts
git add .github/workflows/ci.yml scripts/setup.sh CONTRIBUTING.md SECURITY.md src api mcp tests scripts
git commit -m "chore: enforce repository quality gates"
```

---

### Task 9: Run complete release-boundary verification

**Files:**
- Update only if a verification defect is found: files directly responsible for that defect plus its regression test.

**Interfaces:**
- Consumes all previous tasks.
- Produces final verified implementation evidence; no new product interface.

- [ ] **Step 1: Run dependency and static gates**

```bash
uv lock --check
uv export --no-dev --no-emit-project --format requirements-txt --output-file /tmp/uaek-core.txt
uv export --all-extras --no-dev --no-emit-project --format requirements-txt --output-file /tmp/uaek-all.txt
uvx pip-audit==2.10.1 -r /tmp/uaek-core.txt
uvx pip-audit==2.10.1 -r /tmp/uaek-all.txt
.venv/bin/python -m ruff check src api mcp tests scripts
.venv/bin/python -m ruff format --check src api mcp tests scripts
.venv/bin/python -m mypy src api mcp
```

- [ ] **Step 2: Run the complete test and coverage gate**

```bash
.venv/bin/python -m pytest --cov=src --cov=api --cov=mcp --cov-report=term-missing --cov-report=json:/tmp/uaek-coverage.json --cov-fail-under=75
.venv/bin/python scripts/check_supported_coverage.py /tmp/uaek-coverage.json
```

- [ ] **Step 3: Run evidence gates**

```bash
.venv/bin/python scripts/check_headline_consistency.py
.venv/bin/uaek audit --iterations 1 --evidence-root benchmarks/evidence/fixtures --output /tmp/uaek-hardening-audit.json
```

Assert `errors == []`, `audit_passed is True`, and `evidence_consistency_passed is True` in the generated audit.

- [ ] **Step 4: Build and smoke the installed wheel outside the repository**

Create a guarded `mktemp -d`, build the wheel there, create a clean Python 3.11 venv, install with `uv pip`, change to the temporary directory, and verify:

```bash
uaek --version
uaek --help
uaek-mcp  # initialize, tools/list, shutdown via JSONL stdin
python -c 'import api.server, mcp.server, src; print(src.__version__)'
uaek benchmark --suite quick --iterations 1 --output ./smoke-results
```

Also start the HTTP server on an ephemeral localhost port and validate `/health` plus `/effort`.

- [ ] **Step 5: Review the final diff and repository state**

Run:

```bash
git diff --check
git status --short --branch
git log --oneline --decorate -12
```

Confirm no unrelated tracked files changed and no temporary credential/evidence files were added.

If Step 1–5 exposes a defect, return to the affected task, add a focused failing regression test,
fix only that defect, rerun that task's focused gate, and then repeat Task 9 from Step 1. When no
defect is found, do not create an empty verification commit.
