# UAEK Architecture

UAEK is a model-agnostic agent runtime enhancement layer. It exposes the same shared services through a Click CLI, a standard-library HTTP API, and a JSON-RPC MCP server.

## Runtime plane

1. **Entrypoints** — `src/cli.py`, `api/server.py`, and `mcp/server.py` validate and normalize requests.
2. **Safety and effort** — `src/security`, `src/guardrails.py`, and `src/effort` reject unsafe work and size the reasoning/verification budget.
3. **Orchestration** — `src/workflow` executes sequential, parallel, DAG, or conditional workflows from declarative configuration.
4. **Adapters** — `src/adapters` connects local commands and model-independent A2A sessions.
5. **Verification** — `src/verify` supplies test, build, lint, diff, render, adversarial, property, formal, incremental, and multi-perspective checks.
6. **Memory** — `src/memory` provides layered persistence, compression, vector retrieval, decay, token budgets, and a knowledge graph.
7. **Outputs** — structured results flow to logs, reports, benchmark artifacts, and the unified audit.

The entrypoints must remain thin: domain behavior belongs in shared services so CLI, API, and MCP cannot silently diverge. `python -m mcp` and `python -m mcp.server` deliberately use the same server and stdio loop.

## Evidence plane

`src/benchmark.py`, the scenario/capability modules, and `uaek audit` measure product claims. Evidence follows five rungs: local benchmark, adversarial/stress, real data, live measurement, and external validation. A higher score without stronger evidence is not treated as progress.

## Trust boundaries

- Workflow actions are allowlisted before execution.
- MCP authentication, rate limiting, argument validation, and tool authorization run before handlers.
- Optional ChromaDB, sentence-transformers, and Z3 integrations are lazy and must not be required for the base install.
- Credentialed provider runs, remote pushes, and package publication are external operations and require explicit authorization.

