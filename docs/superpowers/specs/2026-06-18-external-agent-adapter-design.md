# External Agent Adapter Design

## Context

The proxy validation round recovered the evidence-backed product score to 88/100 after the direct reference model became unavailable. The next missing capability is a real external Agent adapter contract. This increment implements the smallest locally verifiable adapter surface: a command-backed adapter that can invoke any executable speaking a JSON protocol.

## Goals

- Add a stable `AdapterRequest` and `AdapterRunResult` interface.
- Implement `CommandAgentAdapter`, which sends a JSON payload to an external command over stdin.
- Require the command to return a JSON object on stdout with `success`, `output`, optional `artifacts`, and optional `metrics`.
- Capture stdout, stderr, return code, duration, timeout, and parsing failures in a normalized result.
- Add `uaek adapter run` so adapter readiness is user-visible from the CLI.
- Add a benchmark suite that records adapter readiness without claiming live platform superiority.

## Protocol

Request payload:

```json
{
  "task": "implement benchmark evidence pipeline",
  "context": {"repo": "uaek"},
  "metadata": {"trace_id": "trace-123"}
}
```

Expected stdout JSON:

```json
{
  "success": true,
  "output": "completed",
  "artifacts": {},
  "metrics": {}
}
```

The adapter treats invalid JSON, non-zero return codes, and timeouts as failed runs while preserving raw stdout/stderr for diagnosis.

## Scoring Boundary

This is an adapter-readiness increment, not a live Codex/Claude/OpenHands benchmark. If the command adapter contract, CLI run, trace writing, and benchmark readiness check pass, the product maturity score can move from 88/100 to 90/100 under an adapter-readiness口径. Remaining gaps stay explicit:

- live external platform runs;
- remote CI run records;
- full cross-platform matrix;
- adversarial/self-improvement benchmark suites.

## Verification

- RED test first for `src.adapters`, CLI `uaek adapter run`, and `benchmark --suite adapter`.
- GREEN focused tests for adapter behavior and benchmark proxy regression.
- CLI smoke with a deterministic Python fixture command.
- Full ruff, mypy, pytest, and coverage gates before claiming completion.
