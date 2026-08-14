# Repository Quality Audit — 2026-08-14

## Scope and baseline

This audit covers the risk-hardening changes from `0d4de16` through the Task 5 head
`b3234dd`. The compatibility boundary is the observable `0.3.0.dev1` behavior across
the Python API, CLI, HTTP API, MCP server, and versioned evidence artifacts.

The planning baseline recorded 705 passing tests and 77.30% aggregate coverage, with
`uv lock --check` and wheel construction passing. It also recorded three Ruff errors
and one Mypy error in the MCP stdio lifecycle. File length alone was not treated as a
finding, and no unrelated large module was split.

## Fixed findings

### High

**Unbounded and weakly validated HTTP request bodies**

- **File:** `api/server.py`, with regression coverage in `tests/unit/test_api.py` and
  boundary documentation in `docs/api/http.md`.
- **Observable impact:** POST handlers trusted `Content-Length`, read the declared
  number of bytes without a repository-defined limit, allowed a non-object JSON root
  to reach object-oriented handlers, and did not convert an invalid length or invalid
  UTF-8 into the documented JSON error boundary. A client could therefore request an
  unbounded read or trigger an uncaught parsing/type failure instead of a stable 4xx
  JSON response.
- **Reproduction/test:** the new parser tests exercise a non-object root, an invalid
  `Content-Length`, and a declared size above the limit. The initial focused run was
  red because the required `MAX_REQUEST_BODY_BYTES` boundary did not exist.
- **Correction:** all POST routes now use one JSON-object parser. It rejects invalid
  or negative lengths with 400, rejects declared bodies above 1 MiB with 413 before
  reading, maps malformed UTF-8/JSON to 400, and rejects non-object roots with 400.
  Successful endpoint response shapes were not changed.
- **Verification:** `uv run pytest tests/unit/test_api.py
  tests/integration/test_integration.py -q` passed 28 tests; Ruff and Mypy passed for
  the touched API files; the subsequent full suite passed 721 tests.

### Medium

**MCP stdio timeout configuration and quality gates were unstable**

- **File:** `mcp/server.py`, with regression coverage in
  `tests/unit/test_mcp_stdio.py` and compatibility coverage in
  `tests/integration/test_runtime_contract.py`.
- **Observable impact:** a non-numeric `UAEK_MCP_IDLE_TIMEOUT` raised a generic float
  conversion error, while a negative value was accepted and could silently defeat the
  intended automatic-release setting. The same loop also failed the repository Ruff
  and Mypy gates because of import/layout defects and a polling variable whose type
  alternated between a list and a boolean.
- **Reproduction/test:** the red unit run expected an error naming
  `UAEK_MCP_IDLE_TIMEOUT` but received `could not convert string to float`; Ruff
  reported import ordering and Mypy reported the polling assignment type conflict.
- **Correction:** `_resolve_idle_timeout` now parses before signal installation,
  names invalid environment configuration, rejects negative values, and preserves an
  explicit zero. Polling state and the signal callback are explicitly typed. Signal
  restoration in `finally` was retained and is now directly exercised after a read
  error; this cleanup path was characterized, not claimed as a newly repaired defect.
- **Verification:** the focused MCP and runtime-contract suite passed 18 tests, Ruff
  and Mypy passed, and the Task 1 full-suite follow-up passed 707 tests with exit code
  zero.

### Low

No additional low-severity runtime defect was changed. Formatting, import ordering,
and typing corrections in `mcp/server.py` are included with the lifecycle finding
above because they were part of the same reproducible gate failure.

## Removed pre-0.3 compatibility

**Retired external-baseline shape**

- **File:** `src/evidence/baseline.py`, related fixtures in
  `benchmarks/baselines/fable5.example.json`, `tests/unit/test_evidence_cli.py`,
  `tests/unit/test_external_baseline.py`, and `tests/unit/test_run_ci_baseline.py`.
- **Observable impact:** a pre-0.3 object using `schema_version`, `source`, or `notes`
  could bypass current-schema structural validation whenever its status was
  `not_configured`.
- **Reproduction/test:** the new pre-0.3 rejection test initially returned
  `not_configured` instead of `invalid`.
- **Correction:** the abbreviated `not_configured` path now requires
  `schema: "external_baseline_v1"`; legacy `source` and `notes` fallbacks were
  removed, and tracked consumers were migrated to the current schema.
- **Verification:** the focused baseline, audit, evidence CLI, and benchmark checks
  passed 25 tests in total; the full suite then passed 713 tests.

**Duplicate semantic-wrapper fallback**

- **File:** `src/guardrails.py`, `src/security/semantic_guard.py`, and
  `tests/unit/test_security.py`.
- **Observable impact:** `SemanticInputFilter` and `SemanticOutputFilter` owned two
  filtering paths: `SemanticGuard` plus the pre-0.3 keyword-filter fallback. This
  masked which rule set owned retained detections and allowed the two paths to drift.
- **Reproduction/test:** direct semantic tests established ownership of Windows
  recursive-delete and plaintext-password detections. Review tests then exposed SSN,
  short quoted secret, and uppercase secret cases that had to remain observable after
  fallback removal.
- **Correction:** semantic wrappers now return `SemanticGuard` results directly. The
  semantic rules retain the exposed SSN and secret-assignment detections, including
  uppercase variants. The separate public keyword filters were not removed.
- **Verification:** the final security suite passed 90 tests; Ruff and Mypy passed for
  the touched security files; review completed with no open findings.

## Retained 0.3 contracts

- The user-approved observable `uaek_memory_delete` MCP tool is retained and
  documented as part of the `0.3.0.dev1` contract. The contract test locks all nine
  registered MCP tool names and the required top-level metadata keys.
- MCP notifications without an `id` remain silent. A subsequent shutdown request with
  an `id` still emits its established JSON-RPC result.
- Documented Python exports from `src.memory`, `src.verify`, and `src.workflow` remain
  available; the HTTP discovery payload remains versioned and lists the established
  routes; CLI help retains the `benchmark`, `capability`, `evidence`, and `audit`
  command groups.
- Current `external_baseline_v1` artifacts retain the `provided`, `incompatible`,
  `invalid`, and `not_configured` result statuses. A valid current-schema abbreviated
  `not_configured` artifact retains its existing non-evidence semantics.
- `InputFilter`, `OutputFilter`, and `GuardrailsSystem(semantic_mode=False)` remain the
  public keyword-filter contracts even though semantic wrappers no longer call them as
  fallback implementations.

## Performance assessment

No representative benchmark established a performance regression or gain, so this
work makes no throughput or latency claim. Removing the duplicate semantic path
simplifies execution, but its effect was not measured. The 1 MiB HTTP limit establishes
a memory/resource bound for untrusted requests; it is a security and availability
control, not evidence of faster request handling. No cache, concurrency mechanism,
runtime dependency, or speculative large-module split was added.

## Residual risks

- **Approved baseline formatting debt:** the repository-wide `ruff format --check src
  api mcp tests scripts` gate reports 62 files needing reformatting, 56 of which were
  pre-existing and outside this hardening plan. Approval for Task 7 limits mechanical
  formatting to the six changed files reported by that gate and uses a format check of
  every Python file changed by the plan as its acceptance criterion. The remaining
  repository-wide drift is technical debt; a separate, dedicated formatting change is
  required before restoring the broad format gate.
- **Deferred documentation inconsistency:** `docs/api/mcp.md` says every input line
  receives a response, but the retained JSON-RPC notification contract deliberately
  emits no response for a line without an `id`. The subprocess contract test is the
  authoritative observed behavior; the wording remains to be reconciled.
- **Deferred HTTP edge coverage:** the parser branches for negative length, invalid
  UTF-8, an exactly 1 MiB body, and proving that a 413 occurs before any body read do
  not have direct tests. The implementation contains these branches and the focused
  and full suites pass, but this edge-level coverage gap remains non-blocking.
- **Intentional MCP contract granularity:** contract tests lock tool names and required
  top-level metadata keys, not every nested input-schema field or description string.
  Changes below that boundary still require review against active documentation.

No residual severity was assigned solely because a module is large; this audit did
not establish mixed responsibilities in an untouched large module.

## Verification evidence

- Final Task 7 adjusted format gate: `uv run ruff format --check` over all 13 Python
  files changed by this plan passed after formatting only `mcp/server.py`,
  `src/evidence/baseline.py`, `src/security/semantic_guard.py`,
  `tests/unit/test_mcp_stdio.py`, `tests/unit/test_run_ci_baseline.py`, and
  `tests/unit/test_security.py`. The repository-wide format check remains intentionally
  out of scope under the approved baseline-debt exception above.
- Final Task 7 static gates: `uv run ruff check src api mcp tests scripts` passed, and
  `uv run mypy src api mcp` passed with no issues in 107 source files.
- Final Task 7 focused suites: MCP/runtime passed 19 tests; external-baseline,
  evidence-CLI, CI-baseline, and audit passed 32 tests; security passed 90 tests.
- Final Task 7 complete suite: `uv run pytest -q --cov=src --cov=api --cov=mcp
  --cov-report=term-missing` passed 721 tests in 78.52 seconds with 77.44% aggregate
  coverage, exceeding the 75% requirement.
- Final Task 7 packaging: `uv lock --check` passed, `uv build --wheel` produced
  `dist/uaek-0.3.0.dev1-py3-none-any.whl`, and a fresh temporary venv installed that
  wheel successfully. Installed `uaek --help` passed; installed `python -m mcp`
  returned two validated JSON-RPC 2.0 response lines for initialize and shutdown.
- Public-contract characterization: `uv run pytest tests/unit/test_public_contract.py
  tests/integration/test_runtime_contract.py -q` passed 7 tests; its full suite passed
  712 tests.
- Latest behavior verification after all product-code changes: `uv run pytest -q`
  passed 721 tests in 70.57 seconds with exit code zero.
- Touched-file static checks passed in their task batches: Ruff for MCP, API, and
  security files; Mypy for `mcp/server.py`, `api/server.py`, `src/guardrails.py`, and
  `src/security/semantic_guard.py`.
- Every implementation batch reported `git diff --check` passing. The final audit
  consistency scan also checks the complete `0d4de16..HEAD` diff, worktree status, and
  this record for placeholders, local absolute paths, and credential-like examples.
