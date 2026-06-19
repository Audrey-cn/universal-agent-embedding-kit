# Score Alignment Design

## Goal
Raise the evidence-backed product score by closing the two fastest real gaps: the benchmark CLI/results pipeline and the missing Agent Harness.

## Scope
This design implements:

- `uaek benchmark --suite quick --output <path>` as a reproducible local benchmark runner that writes JSON results.
- A minimal local Agent Harness that runs task -> effort -> workflow -> verification -> memory -> report.
- Score documentation updates based on verifiable local evidence.

This design does not claim a completed external Fable 5 benchmark. The benchmark runner records that the external baseline is not configured, so Fable 5 comparison remains a follow-up rather than a completed claim.

## Architecture
`src/benchmark.py` owns benchmark execution and JSON result generation. It uses the existing effort classifier, workflow runtime, and the new harness to produce local latency and capability evidence.

`src/harness/interface.py` defines request/result dataclasses. `src/harness/local.py` implements a conservative local pipeline using only existing safe primitives. The harness does not execute arbitrary user code.

The CLI calls `run_benchmark()` and writes the result to either a directory or a `.json` file. Documentation and scorecards consume the same evidence shape.

## Data Flow
1. CLI receives suite, iterations, and output path.
2. Benchmark runner executes effort, workflow, and harness checks.
3. Runner emits a JSON object with metrics, scorecard, resolved findings, and remaining limitations.
4. Harness stores a summary memory entry and returns a serializable report.

## Error Handling
Unsupported benchmark suites raise `ValueError`. Output directories are created if missing. Harness failures return a result with `success=false` and an error list rather than hiding partial execution.

## Testing
Tests are written first:

- Benchmark service writes a JSON-compatible result with scorecard evidence.
- CLI benchmark writes a result file and prints the score.
- Harness pipeline completes a local task and stores queryable memory evidence.

