# Repository Risk Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore all quality gates, protect the `0.3.0.dev1` public contract, remove verified pre-0.3 compatibility behavior, and harden confirmed input-boundary defects without adding features.

**Architecture:** Work in independently verifiable batches. Stabilize the MCP transport first, encode public contracts at the entrypoint boundaries, then remove only compatibility paths proven to be pre-0.3 and harden HTTP parsing through small helpers while leaving endpoint behavior intact.

**Tech Stack:** Python 3.11+, standard library HTTP/JSON/signal/select APIs, pytest, Ruff, Mypy, uv, setuptools.

## Global Constraints

- `0.3.0.dev1` is the compatibility baseline.
- Preserve documented Python imports, CLI commands, HTTP routes, MCP tools, and versioned 0.3 evidence semantics.
- Base runtime dependencies remain PyYAML, Rich, and Click only.
- Do not remove cross-platform fallbacks that support Python 3.11+ on documented operating systems.
- Every behavior change follows RED → GREEN → focused regression → full verification.
- Do not publish, push, open a pull request, or release without separate authorization.

---

### Task 1: Stabilize the MCP stdio lifecycle

**Files:**
- Modify: `mcp/server.py`
- Modify: `tests/unit/test_mcp_stdio.py`
- Verify: `tests/integration/test_runtime_contract.py`

**Interfaces:**
- Consumes: `run_stdio(input_stream=None, output_stream=None, server=None, idle_timeout=None)` and `UAEK_MCP_IDLE_TIMEOUT`.
- Produces: the same newline-delimited JSON-RPC output, idle/EOF/shutdown behavior, and `python -m mcp[.server]` entrypoints.

- [ ] **Step 1: Add failing configuration and cleanup tests**

Add these tests to `tests/unit/test_mcp_stdio.py`, using monkeypatches so they complete without waiting:

```python
def test_invalid_idle_timeout_env_fails_before_signal_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UAEK_MCP_IDLE_TIMEOUT", "invalid")
    installed: list[int] = []
    monkeypatch.setattr(signal, "signal", lambda signum, handler: installed.append(signum))

    with pytest.raises(ValueError, match="UAEK_MCP_IDLE_TIMEOUT"):
        asyncio.run(run_stdio(input_stream=io.StringIO(""), output_stream=io.StringIO()))

    assert installed == []


def test_signal_handlers_are_restored_when_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenInput(io.StringIO):
        def readline(self, *args: object, **kwargs: object) -> str:
            raise RuntimeError("read failed")

    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(signal, "signal", lambda signum, handler: calls.append((signum, handler)) or f"old-{signum}")

    with pytest.raises(RuntimeError, match="read failed"):
        asyncio.run(run_stdio(input_stream=BrokenInput(), output_stream=io.StringIO(), idle_timeout=0))

    assert calls[-2:] == [
        (signal.SIGTERM, f"old-{signal.SIGTERM}"),
        (signal.SIGINT, f"old-{signal.SIGINT}"),
    ]
```

- [ ] **Step 2: Run focused tests and static checks to verify RED**

Run:

```bash
uv run pytest tests/unit/test_mcp_stdio.py -q
uv run ruff check mcp/server.py tests/unit/test_mcp_stdio.py
uv run mypy mcp/server.py
```

Expected: the new invalid-environment test fails, Ruff reports import/line formatting, and Mypy reports the `readable` assignment type conflict.

- [ ] **Step 3: Refactor timeout parsing and polling state**

In `mcp/server.py`:

- move `io` into sorted standard-library import order and move `argparse` to module scope;
- add `_resolve_idle_timeout(value: float | None) -> float` that parses the environment before installing signal handlers, rejects non-numeric and negative values with a message naming `UAEK_MCP_IDLE_TIMEOUT`, and preserves `0` as disabled;
- type the select result as `is_readable: bool` rather than reusing a variable that alternates between `list[TextIO]` and `bool`;
- type `_signal_handler(signum: int, frame: object) -> None`;
- remove the duplicated select-support comment and format the shutdown request test below 100 characters;
- keep signal restoration in `finally`.

Use this shape for the helper and polling assignment:

```python
def _resolve_idle_timeout(value: float | None) -> float:
    if value is not None:
        timeout = value
    else:
        raw = os.environ.get("UAEK_MCP_IDLE_TIMEOUT", "300")
        try:
            timeout = float(raw)
        except ValueError as exc:
            raise ValueError("UAEK_MCP_IDLE_TIMEOUT must be a number") from exc
    if timeout < 0:
        raise ValueError("idle timeout must be non-negative")
    return timeout


ready_streams, _, _ = select.select([input_stream], [], [], poll_interval)
is_readable = bool(ready_streams)
```

- [ ] **Step 4: Verify GREEN and transport compatibility**

Run:

```bash
uv run pytest tests/unit/test_mcp_stdio.py tests/integration/test_runtime_contract.py -q
uv run ruff check mcp/server.py tests/unit/test_mcp_stdio.py
uv run mypy mcp/server.py
```

Expected: all commands pass and both `python -m mcp` and `python -m mcp.server` continue to emit the established response shapes.

- [ ] **Step 5: Commit the MCP stabilization**

```bash
git add mcp/server.py tests/unit/test_mcp_stdio.py
git commit -m "fix(mcp): stabilize stdio lifecycle gates"
```

---

### Task 2: Codify the `0.3.0.dev1` public contract

**Files:**
- Create: `tests/unit/test_public_contract.py`
- Modify: `tests/integration/test_runtime_contract.py`
- Read: `src/__init__.py`, `src/memory/__init__.py`, `src/verify/__init__.py`, `src/workflow/__init__.py`
- Read: `docs/api/http.md`, `docs/api/mcp.md`

**Interfaces:**
- Consumes: current exported `__all__` collections, API discovery payload, CLI help, and MCP tool schemas.
- Produces: behavior-level deletion guards for the `0.3.0.dev1` compatibility boundary.

- [ ] **Step 1: Add public export and discovery contract tests**

Create `tests/unit/test_public_contract.py` with exact contract assertions:

```python
from __future__ import annotations

import subprocess
import sys

import src.memory as memory
import src.verify as verify
import src.workflow as workflow
from api.server import api_root_payload
from mcp.server import create_server
from src.version import __version__


def test_public_python_exports_remain_available() -> None:
    assert {"MemoryService", "MemoryPersistence", "MemoryEntry"} <= set(memory.__all__)
    assert {"verify", "VerificationType", "VerificationResult"} <= set(verify.__all__)
    assert {"build_workflow", "execute_workflow_config", "WorkflowResult"} <= set(workflow.__all__)


def test_http_discovery_contract_is_versioned() -> None:
    payload = api_root_payload()
    assert payload["version"] == __version__
    assert payload["endpoints"] == [
        "GET /",
        "GET /health",
        "POST /verify",
        "POST /effort",
        "POST /workflow",
        "POST /memory",
    ]


def test_mcp_tool_names_and_schema_keys_remain_stable() -> None:
    tools = create_server().tools
    assert set(tools) == {
        "uaek_verify",
        "uaek_effort",
        "uaek_workflow_create",
        "uaek_workflow_add_task",
        "uaek_workflow_execute",
        "uaek_memory_add",
        "uaek_memory_query",
        "uaek_memory_compress",
    }
    assert all({"name", "description", "inputSchema"} <= set(tool) for tool in tools.values())


def test_cli_help_keeps_documented_command_groups() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    for command in ("benchmark", "capability", "evidence", "audit"):
        assert command in completed.stdout
```

- [ ] **Step 2: Preserve exact MCP notification behavior in integration coverage**

Add a subprocess contract test to `tests/integration/test_runtime_contract.py` asserting a notification without `id` emits no response, while a subsequent shutdown request does emit its established response. This resolves the contradictory unit-test comment without changing the 0.3 transport behavior.

- [ ] **Step 3: Run the contract suite**

Run:

```bash
uv run pytest tests/unit/test_public_contract.py tests/integration/test_runtime_contract.py -q
```

Expected: all tests pass against the current 0.3 surface.

- [ ] **Step 4: Commit the compatibility boundary**

```bash
git add tests/unit/test_public_contract.py tests/integration/test_runtime_contract.py
git commit -m "test: lock the 0.3 public contract"
```

---

### Task 3: Remove the pre-0.3 baseline example compatibility path

**Files:**
- Modify: `src/evidence/baseline.py`
- Modify: `tests/unit/test_external_baseline.py`
- Verify: `tests/unit/test_audit.py`
- Verify: `tests/unit/test_evidence_cli.py`

**Interfaces:**
- Consumes: `validate_external_baseline(source, expected_task_digest=None, expected_grader_version=None)`.
- Produces: only `external_baseline_v1` inputs; keeps the result statuses `provided`, `incompatible`, `invalid`, and `not_configured` for valid current-schema artifacts.

- [ ] **Step 1: Replace the legacy fixture with current-schema expectations**

Replace `test_legacy_not_configured_example_remains_readable` with two tests:

```python
def test_current_not_configured_baseline_remains_readable() -> None:
    result = validate_external_baseline(
        {
            "schema": "external_baseline_v1",
            "name": "external",
            "status": "not_configured",
            "reason": "No approved baseline supplied.",
            "metrics": {},
            "limitations": ["No external comparison is claimed."],
        }
    )
    assert result["status"] == "not_configured"
    assert result["reason"] == "No approved baseline supplied."


def test_pre_03_not_configured_shape_is_invalid() -> None:
    result = validate_external_baseline(
        {"schema_version": "1.0", "status": "not_configured", "source": "legacy"}
    )
    assert result["status"] == "invalid"
    assert any("schema" in error for error in result["errors"])
```

- [ ] **Step 2: Run the new rejection test to verify RED**

Run:

```bash
uv run pytest tests/unit/test_external_baseline.py::test_pre_03_not_configured_shape_is_invalid -q
```

Expected: FAIL because the early return currently accepts the pre-0.3 shape.

- [ ] **Step 3: Validate schema before classifying `not_configured`**

In `validate_external_baseline`, allow the abbreviated `not_configured` result only when
`baseline.get("schema") == EXTERNAL_BASELINE_SCHEMA`. A pre-0.3 `schema_version` artifact must flow
through structural validation and return `invalid`. For the current shape, use only the current
`reason`, `metrics`, and `limitations` fields; remove fallbacks to `source` and `notes`.

- [ ] **Step 4: Verify baseline and audit behavior**

Run:

```bash
uv run pytest tests/unit/test_external_baseline.py tests/unit/test_audit.py tests/unit/test_evidence_cli.py -q
```

Expected: all tests pass; current-schema `not_configured` remains non-evidence and old shapes are invalid.

- [ ] **Step 5: Commit the legacy baseline removal**

```bash
git add src/evidence/baseline.py tests/unit/test_external_baseline.py
git commit -m "refactor(evidence): drop pre-0.3 baseline shape"
```

---

### Task 4: Remove duplicate legacy filtering from semantic guardrails

**Files:**
- Modify: `src/guardrails.py`
- Modify: `src/security/semantic_guard.py`
- Modify: `tests/unit/test_security.py`

**Interfaces:**
- Consumes: `SemanticInputFilter.check(text) -> GuardResult` and `SemanticOutputFilter.check(text) -> GuardResult`.
- Produces: the same semantic-filter classes and `GuardResult` shape without constructing or invoking the pre-0.3 `InputFilter`/`OutputFilter` fallback path.

- [ ] **Step 1: Encode retained detections in the semantic rule set**

Move the two behaviors currently proven only by the legacy fallback into direct semantic-guard tests:

```python
def test_semantic_guard_blocks_windows_recursive_delete() -> None:
    result = SemanticGuard().check_injection("del /s /q C:\\*")
    assert result.blocked is True


def test_semantic_guard_blocks_plain_password_assignment() -> None:
    result = SemanticGuard().full_check("password = 'admin123'", check_output=True)
    assert result.blocked is True
```

Both detections are already implemented by `SemanticGuard`; this step moves their proof from the
wrapper fallback to the actual owner. Do not add duplicate patterns.

- [ ] **Step 2: Verify semantic coverage before removing the fallback**

Run:

```bash
uv run pytest tests/unit/test_security.py -q
```

Expected: both direct semantic tests pass before deletion.

- [ ] **Step 3: Remove the dual-filter implementation**

In `SemanticInputFilter` and `SemanticOutputFilter`, remove `_legacy_filter`, the second `check`, and
legacy-specific reason construction. Return the `SemanticGuard` result directly. Keep the public
`InputFilter`, `OutputFilter`, and `GuardrailsSystem(semantic_mode=False)` APIs because they are part
of the 0.3 public surface; rename tests and comments from “legacy compatibility” to “keyword filter
contract” without changing their assertions.

The simplified methods should be:

```python
class SemanticInputFilter:
    def __init__(self) -> None:
        self._semantic_guard = SemanticGuard()

    def check(self, text: str) -> GuardResult:
        return self._semantic_guard.check_injection(text)


class SemanticOutputFilter:
    def __init__(self) -> None:
        self._semantic_guard = SemanticGuard()

    def check(self, text: str) -> GuardResult:
        return self._semantic_guard.full_check(text, check_output=True)
```

- [ ] **Step 4: Verify no detection or public-type regression**

Run:

```bash
uv run pytest tests/unit/test_security.py -q
uv run ruff check src/guardrails.py src/security/semantic_guard.py tests/unit/test_security.py
uv run mypy src/guardrails.py src/security/semantic_guard.py
```

Expected: all existing keyword and semantic contracts pass with a single semantic path.

- [ ] **Step 5: Commit the guardrail simplification**

```bash
git add src/guardrails.py src/security/semantic_guard.py tests/unit/test_security.py
git commit -m "refactor(security): remove duplicate semantic fallback"
```

---

### Task 5: Bound and validate HTTP request parsing

**Files:**
- Modify: `api/server.py`
- Modify: `tests/unit/test_api.py`
- Modify: `docs/api/http.md`

**Interfaces:**
- Consumes: all existing HTTP routes and JSON request objects.
- Produces: the same successful endpoint responses; malformed length/body/root inputs return JSON 400 responses and oversized bodies return JSON 413 responses.

- [ ] **Step 1: Add failing parser-boundary tests**

Add a handler factory using `io.BytesIO` and focused tests for:

```python
def test_post_rejects_non_object_json() -> None:
    handler, responses = make_post_handler("/effort", b"[]")
    handler.do_POST()
    assert responses == [(400, {"error": "JSON body must be an object"})]


def test_post_rejects_invalid_content_length() -> None:
    handler, responses = make_post_handler("/effort", b"{}", content_length="invalid")
    handler.do_POST()
    assert responses == [(400, {"error": "Invalid Content-Length"})]


def test_post_rejects_body_over_limit() -> None:
    handler, responses = make_post_handler(
        "/effort", b"{}", content_length=str(MAX_REQUEST_BODY_BYTES + 1)
    )
    handler.do_POST()
    assert responses == [(413, {"error": "Request body too large"})]
```

The helper sets `path`, `headers`, `rfile`, and a captured `_respond` method on
`UAEKHandler.__new__(UAEKHandler)`.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/test_api.py -q
```

Expected: invalid length raises `ValueError`, arrays reach handlers and fail with 500-like behavior,
and no request-size limit exists.

- [ ] **Step 3: Introduce one bounded JSON-object parser**

In `api/server.py`, define `MAX_REQUEST_BODY_BYTES = 1_048_576` and add
`_read_json_object(self) -> tuple[dict[str, Any] | None, tuple[int, str] | None]`. It must:

- parse a missing length as zero;
- reject non-integer or negative length with `(400, "Invalid Content-Length")`;
- reject a length above the limit before reading with `(413, "Request body too large")`;
- reject invalid UTF-8 or JSON with `(400, "Invalid JSON")`;
- reject a JSON root that is not an object with `(400, "JSON body must be an object")`.

Have `do_POST` call the helper and return `_respond(status, {"error": message})` on an error. Do not
change individual endpoint success shapes.

- [ ] **Step 4: Document and verify the HTTP boundary**

Add a short “Request limits” section to `docs/api/http.md` stating that POST bodies must be JSON
objects and are limited to 1 MiB. Then run:

```bash
uv run pytest tests/unit/test_api.py tests/integration/test_integration.py -q
uv run ruff check api/server.py tests/unit/test_api.py
uv run mypy api/server.py
```

Expected: all commands pass.

- [ ] **Step 5: Commit the HTTP hardening**

```bash
git add api/server.py tests/unit/test_api.py docs/api/http.md
git commit -m "fix(api): bound and validate JSON request bodies"
```

---

### Task 6: Produce the severity-ranked audit record

**Files:**
- Create: `docs/audits/2026-08-14-repository-quality-audit.md`
- Read: all files changed in Tasks 1–5

**Interfaces:**
- Produces: a durable audit record separating fixed findings, retained compatibility, and residual risks.

- [ ] **Step 1: Write the audit record from verified evidence**

Create the report with this exact structure:

```markdown
# Repository Quality Audit — 2026-08-14

## Scope and baseline
## Fixed findings
### High
### Medium
### Low
## Removed pre-0.3 compatibility
## Retained 0.3 contracts
## Performance assessment
## Residual risks
## Verification evidence
```

For each finding include file, observable impact, reproduction/test, correction, and verification.
Do not assign a severity to line length or file size alone. Record untouched large modules as residual
maintainability risks only when responsibilities are demonstrably mixed.

- [ ] **Step 2: Check the report against the actual diff**

Run:

```bash
git diff --check 0d4de16..HEAD
git status --short
rg -n "TBD|TODO|FIXME|/Users/audrey|Bearer [A-Za-z0-9]" docs/audits/2026-08-14-repository-quality-audit.md
```

Expected: no placeholders, local absolute paths, or credential-like examples occur in the report.

- [ ] **Step 3: Commit the audit record**

```bash
git add docs/audits/2026-08-14-repository-quality-audit.md
git commit -m "docs: record repository quality audit"
```

---

### Task 7: Run final quality gates and installed-package smoke tests

**Files:**
- Review: all files changed by this plan

**Interfaces:**
- Produces: fresh verification evidence for the complete refactor.

- [ ] **Step 1: Run formatting, lint, and type gates**

```bash
uv run ruff format --check src api mcp tests scripts
uv run ruff check src api mcp tests scripts
uv run mypy src api mcp
```

Expected: all commands exit 0.

- [ ] **Step 2: Run focused supported-coverage and complete test gates**

```bash
uv run pytest tests/unit/test_supported_coverage_gate.py -q
uv run pytest -q --cov=src --cov=api --cov=mcp --cov-report=term-missing
```

Expected: all tests pass, supported-module coverage passes, and aggregate coverage is at least 75%.

- [ ] **Step 3: Verify lock and wheel installation**

```bash
uv lock --check
uv build --wheel
```

Create an explicit temporary directory, install the newly built wheel, and run:

```bash
UAEK_SMOKE_DIR=$(mktemp -d)
python -m venv "$UAEK_SMOKE_DIR/venv"
"$UAEK_SMOKE_DIR/venv/bin/pip" install dist/uaek-0.3.0.dev1-py3-none-any.whl
"$UAEK_SMOKE_DIR/venv/bin/uaek" --help
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' '{"jsonrpc":"2.0","id":2,"method":"shutdown","params":{}}' | "$UAEK_SMOKE_DIR/venv/bin/python" -m mcp
```

Expected: installation succeeds, CLI help exits 0, and MCP returns two valid JSON response lines.
Remove only the explicit path printed by `mktemp -d` after validating that `UAEK_SMOKE_DIR` is
non-empty and is not `/`, a workspace root, or a home directory.

- [ ] **Step 4: Inspect the final diff and repository state**

```bash
git status --short
git diff --stat 0d4de16..HEAD
git diff --check 0d4de16..HEAD
git log --oneline 0d4de16..HEAD
```

Confirm every changed file maps to this plan and no generated build artifacts, benchmark results,
credentials, or unrelated cleanup are tracked.

- [ ] **Step 5: Use `superpowers:verification-before-completion` and then `superpowers:finishing-a-development-branch`**

Re-run any gate whose evidence is stale, report exact results and residual risks, then offer the
supported integration choices without pushing or opening a pull request automatically.
