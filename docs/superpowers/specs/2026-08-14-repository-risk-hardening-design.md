# Repository Risk Hardening Design

## Objective

Perform a repository-wide quality review and a bounded refactor of UAEK. Remove compatibility
code that exists only for releases before `0.3.0.dev1`, while preserving the observable public
contracts of `0.3.0.dev1` across the Python API, CLI, HTTP API, and MCP server.

The work is risk-driven rather than a general rewrite. Every product-code change must address a
reproducible defect, a demonstrated security or performance risk, an obsolete compatibility path,
or a maintainability problem in code already being changed.

## Current Baseline

The baseline was measured on `main` at commit `ba0d71a`:

- 705 tests pass.
- Aggregate coverage is 77.30%, above the configured 75% floor.
- `uv lock --check` and wheel construction pass.
- Ruff reports three errors in the recent MCP stdio lifecycle change.
- Mypy reports one type error in the same MCP stdio loop.
- Several core modules exceed 700 lines, but file size alone is not sufficient reason to split
  them.

The existing August 9 quality-hardening plan is historical context. Work already completed there
must not be repeated unless current verification proves a regression.

## Compatibility Boundary

`0.3.0.dev1` is the compatibility baseline.

The following observable behavior must remain compatible:

- documented Python imports, callable names, parameters, return shapes, and exception categories;
- CLI command names, accepted options, exit semantics, and documented JSON output shapes;
- HTTP routes, accepted request fields, response status codes, and response JSON shapes;
- MCP tool names, input schemas, JSON-RPC behavior, and successful/error response shapes;
- versioned `0.3` evidence artifacts and validation semantics.

Compatibility does not require preserving private helpers, internal module layout, implementation
classes that are not exported, undocumented aliases from releases before 0.3, or tests whose only
purpose is to keep those older behaviors alive.

Before deleting a suspected legacy path, the implementation phase must identify its callers and
classify it as either part of the 0.3 contract or removable pre-0.3 behavior. Ambiguous cases stay
unchanged until the contract can be established from active documentation and exported interfaces.

## Recommended Approach

Use risk-prioritized, contract-protected batches.

First, restore the existing quality gates around MCP stdio lifecycle behavior. Next, codify the
current public surface with focused contract tests. Then review and remove verified pre-0.3
compatibility paths. Finally, investigate high-risk boundaries and refactor only the modules touched
by confirmed findings.

This approach is preferred over module-by-module cleanup or a repository-wide architecture rewrite
because it keeps each change independently testable and makes regressions attributable to a small
diff.

## Workstreams

### 1. MCP stdio lifecycle stabilization

Treat the current Ruff and Mypy failures as a concrete regression. Preserve the documented idle
timeout, EOF, shutdown, notification, and signal behavior while simplifying the polling loop and
making its state explicitly typed. Signal handlers must always be restored, including exceptional
paths. Invalid idle-timeout configuration must fail predictably rather than crashing after partial
startup.

The stdio transport must remain newline-delimited JSON-RPC and must not introduce a new runtime
dependency.

### 2. Public contract protection

Create or consolidate focused tests for the four public surfaces. Tests should assert behavior rather
than private implementation structure. Existing integration tests should be reused where they already
express the contract.

The contract inventory will also serve as the deletion boundary: an old branch can be removed only
when it is neither required by active 0.3 documentation nor exercised as an intended 0.3 behavior.

### 3. Legacy compatibility removal

Audit code explicitly labeled `legacy`, `compatibility`, `deprecated`, or carrying old schema/version
branches. Initial candidates include the dual legacy filters in `src/guardrails.py` and the legacy
baseline fixture path. These are candidates, not predetermined deletions.

For each candidate:

1. Identify exports and runtime callers.
2. Determine whether active 0.3 documentation promises the behavior.
3. Add or update a contract test for the retained 0.3 behavior.
4. Remove only the redundant pre-0.3 path.
5. Run focused and cross-surface regression tests.

The refactor must not reinterpret legitimate cross-platform fallback code as release compatibility.
For example, platform-specific resource-limit fallbacks remain when they support Python 3.11+ on
documented operating systems.

### 4. Security and performance boundaries

Review boundaries that accept untrusted or external input:

- subprocess and candidate-code execution;
- filesystem paths and artifact writes;
- HTTP request parsing and body handling;
- MCP authentication, rate limiting, tool arguments, and error handling;
- memory persistence and restore behavior.

Only evidence-backed findings enter the implementation scope. A finding must have a failing test,
minimal reproduction, or a direct invariant violation. Security fixes take priority over performance
and maintainability work. Performance changes require a representative measurement or a clearly
bounded complexity defect; speculative caching or concurrency is out of scope.

### 5. Targeted structural refactoring

Split a large module only when a confirmed fix would otherwise deepen mixed responsibilities. New
units must have one clear purpose and preserve existing public imports through the current public
facade. Do not mechanically divide scenario data, benchmark corpora, or cohesive modules based only
on line count.

Entrypoints remain thin and delegate shared behavior to `src` service/runtime modules. Business logic
must not be duplicated across CLI, HTTP, and MCP.

## Error Handling and Data Safety

Public errors must remain compatible at the category and response-shape level. Internal exceptions
may be narrowed or clarified when the public adapter continues to return the documented status or
JSON-RPC error.

File writes that replace durable state must remain atomic. Path-derived outputs must stay within their
declared destination. Subprocesses must continue to use argument arrays rather than shell execution,
and untrusted candidate execution must retain resource and timeout limits.

## Testing and Verification

Every behavior change follows a red-green-refactor loop:

1. Add a focused test that fails for the demonstrated problem.
2. Run it and record the expected failure.
3. Implement the smallest correction or removal.
4. Run the focused test and neighboring contract tests.
5. Run the complete repository gates before declaring the batch complete.

Final acceptance requires:

- all existing and new tests pass;
- aggregate coverage remains at least 75%;
- supported-module coverage checks pass;
- Ruff passes over `src`, `api`, `mcp`, `tests`, and `scripts`;
- Mypy passes over `src`, `api`, and `mcp`;
- `uv lock --check` passes;
- wheel build and installed CLI smoke checks pass;
- the final diff contains no secrets, local paths, generated benchmark results, or unrelated cleanup.

Where a security or performance concern cannot be reproduced, report it as residual risk rather than
claiming it was fixed.

## Non-Goals

- No new product features or public endpoints.
- No compatibility promise for releases earlier than `0.3.0.dev1`.
- No wholesale rewrite of the verification, benchmark, memory, or workflow systems.
- No dependency expansion unless a confirmed critical issue cannot be fixed with the standard library
  or existing dependencies.
- No arbitrary coverage increase for low-risk data modules solely to improve the aggregate number.
- No publishing, pushing, pull request creation, or release action as part of the refactor unless
  separately authorized.

## Deliverables

- A severity-ranked audit record tied to concrete files and evidence.
- Contract tests defining the retained `0.3.0.dev1` behavior.
- Small, reviewable refactor batches for confirmed findings.
- Removal of verified pre-0.3 compatibility code.
- A final verification report listing commands run, results, and residual risks.
