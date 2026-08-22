# Repository Health Hardening Design

## Status

Approved in chat on 2026-08-22. This design hardens the existing `0.3.0.dev1`
architecture without publishing a release or changing the three-entrypoint product shape.

## Goals

- Stop capability grading and public verification helpers from executing external Python with the
  parent process environment and working directory.
- Make the lightweight subprocess boundary honest, resource-bounded, and reusable by the command
  adapter and code graders.
- Remove ChromaDB from UAEK-supported dependencies while preserving the built-in vector backend and
  optional sentence-transformer embeddings.
- Provide a relocatable MCP launch contract that works from an installed wheel without personal
  paths or `PYTHONPATH` mutation.
- Make headline evidence counts mechanically consistent across active documentation and CI.
- Preserve the documented Python, CLI, HTTP, MCP, evidence-artifact, and safe-workflow contracts of
  `0.3.0.dev1` unless this design explicitly retires a capability.

## Non-goals

- No PyPI publication, GitHub Release, push, or production deployment.
- No Docker-, VM-, or microservice-based sandbox service.
- No claim that a Python subprocess is a kernel security boundary.
- No new ORM, dependency injection framework, web framework, or package manager.
- No unrelated formatting or large-module refactor.

## Design choices

### 1. One bounded subprocess primitive

`src/security/sandbox.py` will own process creation, environment scrubbing, temporary working
directories, resource limits, bounded output collection, timeout handling, and process-group
termination. `CommandAgentAdapter` and Python-code grading will call this primitive instead of
maintaining separate `subprocess.run` implementations.

The primitive will accept an explicit command, stdin text, timeout, memory limit, output-byte
limit, working directory, and a complete environment mapping. It will return normalized stdout,
stderr, exit code, timeout, and truncation diagnostics. It will:

- let security-sensitive callers supply a minimal environment and fresh temporary `HOME`, `TMPDIR`,
  and working directory;
- start a new process group/session and terminate the complete group on timeout;
- read stdout and stderr incrementally with a combined upper bound rather than capturing unlimited
  output and truncating afterward;
- apply Unix `resource` limits when available and degrade explicitly on platforms without them;
- validate positive finite limits before process creation.

The external command itself is user-selected and therefore remains a trusted integration boundary.
`CommandAgentAdapter` will preserve its current inherited-environment behavior while documenting
that trust contract; candidate-code graders will supply a scrubbed environment and isolated paths.

The existing `SandboxPolicy.allow_network` and `allow_filesystem_write` fields will not be described
as OS-enforced controls. Standard-library subprocesses cannot provide a portable kernel network or
filesystem sandbox. Capability grading adds a second, task-specific language restriction described
below, and security documentation will retain the requirement to use OS/container isolation for
hostile code.

### 2. Restricted capability-code grading

Capability prompts require a Python function definition, not arbitrary programs. Before execution,
the grader will parse candidate code and reject imports, process/network/file primitives, dynamic
code execution, dunder access, top-level side effects, and calls to dangerous builtins. The allowed
surface will cover the syntax and ordinary builtins required by all ten current tasks.

Accepted code will run through the bounded subprocess primitive in an isolated temporary directory
with held-out inputs supplied as JSON. The result schema remains unchanged: pass counts, per-case
results, load/runtime errors, and timeouts remain structured.

`scenario_benchmark.evaluate_scenario` and `property_test_verify` will stop executing artifacts in
the parent process. They will either use the same restricted subprocess path or fail closed with a
structured diagnostic when the requested callable cannot be evaluated under the supported subset.
Built-in trusted reference helpers may remain in-process only when their source is repository-owned
and never derived from an external artifact.

Regression tests will attempt environment reads, home-file reads, file writes outside the temporary
directory, imports, dynamic execution, oversized output, infinite loops, and child-process survival.
The tests define the supported boundary; documentation will not claim resistance to interpreter or
kernel escapes.

### 3. ChromaDB retirement

`chromadb` will be removed from `project.optional-dependencies`. The `memory` extra will contain only
`sentence-transformers`; the `all` extra will continue to compose supported extras.

`SimpleBackend` remains the supported vector store. The public `ChromaBackend` symbol will be kept as
a compatibility stub for `0.3.0.dev1`: instantiation raises a stable `RuntimeError` explaining that
the integration was retired for security reasons. `detect_chromadb()` will return `False` and will
not import an independently installed ChromaDB package. This prevents a globally installed package
from silently re-enabling an unsupported backend.

Active documentation, type-check overrides, tests, lock data, and dependency examples will be
updated. CI will export and audit the core and all supported extras independently. `aiohttp` must no
longer appear through a UAEK-supported dependency path unless its resolved version passes the audit.

### 4. Portable MCP entrypoint

The wheel will expose `uaek-mcp = mcp.server:main`. `mcp/config.json` will invoke `uaek-mcp`, contain
no `cwd`, `PYTHONPATH`, home directory, or repository-specific interpreter, and remain valid JSON.
`python -m mcp` and `python -m mcp.server` remain supported.

Release smoke tests will install the wheel in a fresh virtual environment, change to an unrelated
directory, start `uaek-mcp`, and validate initialize, tools/list, and shutdown responses. This is the
portable contract; host-specific GUI configuration remains the host's responsibility.

### 5. Evidence consistency authority

The versioned capability run artifacts under `benchmarks/results/capability-runs/`, interpreted by
the current `run_capability_readiness` aggregator, are authoritative for the headline full-suite
provider count. A small validator will compare the derived
`graded_live_provider_count/expected_provider_count` against the checked-in capability matrix,
active README files, and the current scorecard summary. Historical changelog entries and dated
design documents are excluded.

The immediate active value is `3/4`. English and Chinese README text will be corrected. The validator
will fail CI when an active headline drifts. Historical held-out regrade artifacts retain their own
recorded scope and date; they will be labeled historical rather than rewritten to imply a rerun.

### 6. Quality and release gates

CI will add:

- Ruff format checking in addition to linting, after a single mechanical repository-format batch;
- dependency audits for core and all supported extras;
- restricted-code and process-boundary security tests;
- portable `uaek-mcp` installed-wheel smoke coverage;
- headline evidence consistency validation.

Coverage floors remain at 75% globally and at their existing supported-module thresholds. New shared
subprocess and restricted-grading code must be covered by focused regression tests. Docker build is
not made a release gate because the checked-in container remains explicitly development-only.

## Error handling and compatibility

- Rejected candidate code returns a grading failure with a concise policy diagnostic; it does not
  raise through CLI benchmark flows.
- Output-limit and timeout failures distinguish those causes from invalid JSON or non-zero exit.
- Candidate-code execution never inherits parent secrets. User-selected external adapter commands
  retain the parent environment for compatibility and are explicitly documented as trusted code.
- ChromaDB construction fails with a migration message; ordinary memory and vector behavior continue
  through `SimpleBackend`.
- The MCP tool names, schemas, JSON-RPC behavior, HTTP routes, CLI command groups, and package version
  remain unchanged.

## Verification standard

Completion requires fresh successful runs of:

1. Focused RED/GREEN tests for each changed behavior.
2. `uv lock --check` and dependency audits for core and all extras.
3. `ruff check` and `ruff format --check` for source, tests, and scripts.
4. `mypy src api mcp`.
5. The complete pytest suite with coverage and supported-module floors.
6. Wheel build, clean Python 3.11 installation, CLI/HTTP/MCP smoke tests from outside the repository.
7. `uaek audit` with zero errors and passing evidence-consistency semantics.
8. A clean tracked worktree except for the intended implementation changes.

## Residual risk

The restricted AST plus subprocess boundary materially reduces accidental or opportunistic malicious
code risk but is not a hardened multi-tenant sandbox. Users evaluating hostile code must still run
UAEK inside an OS/container/VM isolation boundary. Production HTTP authentication, TLS, concurrency,
PyPI publication, Windows support, and a `0.3` public release remain separate follow-up projects.
