# UAEK 0.2 Support Matrix

UAEK `0.2.0rc1` is an alpha release candidate. This matrix separates release-supported paths
from advanced experiments so that a module's presence is not mistaken for a stability promise.

## Release-supported

| Capability | Public surface | Support promise |
|---|---|---|
| Package and version metadata | wheel, `uaek --version`, Python import | Version-consistent and release-gated |
| Core verification | test, build, lint and fresh-context runners | Behavior-tested; failures are structured |
| Effort routing | Python API and CLI | Deterministic classification contract |
| Workflow execution | sequential, parallel, DAG and conditional shared runtime | CLI/API/MCP contract tested; safe-action allowlist enforced |
| Memory | layered persistence, query, compression and restore | Local persistence and round-trip behavior tested |
| Security | workflow guardrails, MCP auth/access/rate limiting, sandbox primitives | Fail-closed boundary behavior tested |
| Entrypoints | Click CLI, HTTP API, JSON-RPC MCP | Shared workflow results and package smoke tested |
| Evidence | benchmarks, capability matrix and `uaek audit` | Evidence rung and limitations required; audit consistency gated |

Release-supported modules have both the global 75% coverage gate and focused non-regression floors
for the API server, MCP server, workflow runtime, sandbox, core test runner, and memory service.

## Experimental

| Capability | Module | Boundary |
|---|---|---|
| Render verification | `src/verify/render_runner.py` | Prototype contract; renderer/platform coverage is incomplete |
| Formal verification | `src/verify/formal_verify.py` | Optional Z3 integration; unavailable dependency is a valid outcome |
| Multi-perspective verification | `src/verify/multi_perspective.py` | Research interface; aggregation contract may change before 1.0 |
| Cognitive panel | `src/verify/cognitive_panel.py` | Research interface; not a release-critical path |
| Incremental verification | `src/verify/incremental.py` | Cache/invalidation experiment; not yet a stable public API |

Experimental APIs may change before UAEK 1.0. They must not be described as externally validated
or release-complete solely because the module imports successfully.

