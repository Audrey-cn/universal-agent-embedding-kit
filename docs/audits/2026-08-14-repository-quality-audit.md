# Repository Quality Audit — 2026-08-14

## Scope and baseline

This audit covers the risk-hardening changes from `0d4de16` through the final-review
fix wave. The compatibility boundary is the observable `0.3.0.dev1` behavior across
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
- **Observable impact:** POST handlers originally trusted `Content-Length`, read the
  declared number of bytes without a repository-defined limit, and allowed malformed
  roots and decoding failures to escape the JSON error boundary. Final review also
  found that Python accepted `NaN` and `Infinity`, while a 5,000-digit integer or deep
  nesting raised uncaught `ValueError` or `RecursionError`. A follow-up review found
  that syntactically valid exponent-overflow floats such as `1e9999` and `-1e9999`
  still decoded to positive or negative infinity and reached `/effort`.
- **Reproduction/test:** the original parser-boundary RED run established the size,
  length, and root defects. In the final-review RED run, five focused cases failed:
  three non-finite constants reached the endpoint, and oversized-integer and deeply
  nested payloads raised instead of returning 400. Negative length, invalid UTF-8,
  exact-limit acceptance, and pre-read 413 behavior were also characterized directly.
  Both exponent-overflow signs returned 200 in their follow-up RED run.
- **Correction:** all POST routes now use one JSON-object parser. It rejects invalid
  or negative lengths with 400, rejects declared bodies above 1 MiB with 413 before
  reading, rejects non-finite constants through `parse_constant`, maps JSON
  `ValueError` and `RecursionError` to 400, validates `parse_float` results are finite,
  and rejects non-object roots with 400. Successful endpoint response shapes were not
  changed.
- **Verification:** the final parser edge set passed 11 tests; `tests/unit/test_api.py`
  plus `tests/integration/test_integration.py` passed 39 tests; the complete suite
  passed 751 tests with 77.53% aggregate coverage.

### Medium

**MCP stdio timeout validation and signal cleanup were incomplete**

- **File:** `mcp/server.py`, with regression coverage in
  `tests/unit/test_mcp_stdio.py` and compatibility coverage in
  `tests/integration/test_runtime_contract.py`.
- **Observable impact:** the initial implementation did not validate malformed or
  negative timeout configuration cleanly. Final review found that explicit and
  environment-derived `nan`/`inf` values were still accepted. It also found that a
  successful SIGTERM replacement was not restored when SIGINT installation failed,
  and neither handler was restored when `fileno()` raised `ValueError` or
  `RuntimeError` before the loop's cleanup region.
- **Reproduction/test:** seven final-review lifecycle cases failed: four non-finite
  timeout cases, second-handler installation failure, and two exceptional `fileno()`
  paths. The earlier RED run also captured malformed/negative configuration and the
  Ruff/Mypy polling-state defects.
- **Correction:** `_resolve_idle_timeout` now parses before signal installation,
  names invalid environment configuration, rejects negative and non-finite values,
  and preserves explicit zero. Every successfully replaced handler is recorded as it
  is installed and restored by a cleanup region that also covers partial installation
  and `fileno()` failures.
- **Verification:** the seven focused lifecycle cases passed; the combined MCP stdio,
  MCP security, and runtime-contract suite passed 62 tests; full Ruff and Mypy gates
  passed.

**Semantic filtering drifted from the retained 0.3 boundary and exposed matches**

- **File:** `src/security/semantic_guard.py`, with public-wrapper regression coverage
  in `tests/unit/test_security.py`.
- **Observable impact:** semantic output filtering no longer blocked bare `BEGIN
  RSA/DSA/EC/OPENSSH PRIVATE KEY` markers after the duplicate fallback was removed.
  SSNs also drifted from input-only detection into output blocking, and SSNs plus
  short credentials were copied verbatim into `GuardResult.reason`.
- **Reproduction/test:** all seven focused security cases failed before the fix: four
  bare private-key variants, SSN output compatibility, SSN reason redaction, and short
  credential reason redaction. Final read-only review then found one overlapping case:
  an output credential whose value resembled an injection instruction was classified
  by the earlier injection check, exposing that value in result metadata; its focused
  regression test failed before the follow-up correction.
- **Correction:** the private-key semantic rule now accepts both bare and PEM-wrapped
  markers; output checks skip the input-only SSN rule; and sensitive-result metadata
  reports only the detection category, never the matched value. Output-sensitive
  detection runs before injection classification so overlapping credentials are also
  sanitized. Input SSNs and short credential assignments remain blocked in their
  respective input/output paths.
- **Verification:** the initial seven focused cases and the focused overlap case
  passed; all 96 semantic/keyword security tests passed; the combined security and
  MCP-security suite passed 132 tests.

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
  could originally bypass current-schema structural validation whenever its status was
  `not_configured`. After that path was removed, a current-schema abbreviated object
  could still return early with invalid field types or embedded secret material.
- **Reproduction/test:** the pre-0.3 rejection test initially returned
  `not_configured` instead of `invalid`. In final review, six additional cases with
  invalid `name`, `reason`, `metrics`, or `limitations` types and secret material also
  incorrectly returned `not_configured`.
- **Correction:** the abbreviated `not_configured` path now requires
  `schema: "external_baseline_v1"`; legacy `source` and `notes` fallbacks were
  removed; current abbreviated fields are type-checked; and secret detection runs
  before a result is returned. Valid current artifacts retain their exact result shape.
- **Verification:** the valid-shape case and six final-review rejection cases passed;
  the combined baseline, evidence, CI-baseline, and audit suite passed 68 tests.

**Duplicate semantic-wrapper fallback**

- **File:** `src/guardrails.py`, `src/security/semantic_guard.py`, and
  `tests/unit/test_security.py`.
- **Observable impact:** `SemanticInputFilter` and `SemanticOutputFilter` owned two
  filtering paths: `SemanticGuard` plus the pre-0.3 keyword-filter fallback. This
  masked which rule set owned retained detections and allowed the two paths to drift.
- **Reproduction/test:** direct semantic tests established ownership of Windows
  recursive-delete and plaintext-password detections. Subsequent reviews exposed SSN,
  short quoted/uppercase secret, and bare private-key cases that had to retain their
  established surface-specific behavior after fallback removal.
- **Correction:** semantic wrappers now return `SemanticGuard` results directly. The
  semantic rules retain input-only SSN, secret-assignment, and private-key detections,
  including uppercase secret variants and bare key markers. The separate public
  keyword filters were not removed.
- **Verification:** the final security suite passed 96 tests; Ruff and Mypy passed for
  the touched security files.

## Retained 0.3 contracts

- The user-approved observable `uaek_memory_delete` MCP tool is retained and
  documented as part of the `0.3.0.dev1` contract. The contract test locks all nine
  registered MCP tool names and the required top-level metadata keys.
- MCP no-id behavior remains method-dependent: recognized methods return their
  established response with `id:null`, while an unknown no-id method is silent. This
  was characterized in the subprocess integration test without changing production
  dispatch behavior.
- Documented Python exports from `src.memory`, `src.verify`, and `src.workflow` remain
  available; the HTTP discovery payload remains versioned and lists the established
  routes; CLI help retains the `benchmark`, `capability`, `evidence`, and `audit`
  command groups.
- Current `external_baseline_v1` artifacts retain the `provided`, `incompatible`,
  `invalid`, and `not_configured` result statuses. A valid current-schema abbreviated
  `not_configured` artifact retains its exact existing non-evidence result shape;
  malformed or secret-bearing abbreviations are invalid.
- SSNs remain blocked by `SemanticInputFilter` and allowed by `SemanticOutputFilter`;
  output credentials and both bare and PEM-wrapped supported private-key markers
  remain blocked. Sensitive matched values are not returned in `GuardResult` metadata.
- Idle timeout `0` remains the disabled setting; finite positive values retain their
  existing behavior.
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

- **Approved baseline formatting debt:** all 13 Python files changed since the
  hardening base pass Ruff's format check. The previously recorded formatting drift
  in untouched files remains technical debt for a separate mechanical-only change;
  this wave does not claim that the repository-wide format baseline is clean.
- **Intentional MCP contract granularity:** contract tests lock tool names and required
  top-level metadata keys, not every nested input-schema field or description string.
  Changes below that boundary still require review against active documentation.

No residual severity was assigned solely because a module is large; this audit did
not establish mixed responsibilities in an untouched large module.

## Verification evidence

- The clean pre-wave baseline was `uv run pytest -q`: 721 tests passed in 71.00
  seconds.
- Final-review TDD evidence: the initial security set went from 7 focused failures to
  7 passes, and the reviewer-found overlap went from 1 failure to 1 pass;
  abbreviated-baseline validation went from 6 failures and 1 pass to 7 passes; MCP
  lifecycle went from 7 failures to 7 passes; and HTTP parsing went from 5 failures
  and 4 passes to 9 passes. The HTTP exponent-overflow follow-up then went from 2
  focused failures to 2 passes. The no-id MCP integration characterization passed
  without a production dispatcher change.
- The changed-file format gate passed for all 13 Python files changed since
  `0d4de16`. `uv run ruff check src api mcp tests scripts` passed, and `uv run mypy
  src api mcp` passed with no issues in 107 source files.
- Final focused suites passed: MCP/runtime 62 tests, security 132 tests,
  baseline/evidence/audit 68 tests, and API/integration 39 tests. The supported-module
  coverage gate passed 3 tests.
- `uv run pytest -q --cov=src --cov=api --cov=mcp --cov-report=term-missing` passed
  751 tests in 76.33 seconds with 77.53% aggregate coverage, exceeding the 75% floor.
- `uv lock --check` and `uv build --wheel` passed; the latter produced
  `dist/uaek-0.3.0.dev1-py3-none-any.whl`. A fresh temporary venv installed that wheel
  successfully. Installed `uaek --help` passed; installed `python -m mcp`
  returned two validated JSON-RPC 2.0 response lines for initialize and shutdown. The
  guarded temporary directory was removed automatically after the smoke.
- Focused static checks passed in their implementation cycles, and the final diff
  whitespace and audit-consistency scans passed after the documentation update.
