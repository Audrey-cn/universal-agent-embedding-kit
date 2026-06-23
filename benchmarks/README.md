# UAEK Benchmarks

The project now has a local quick benchmark runner:

```bash
.venv/bin/uaek benchmark --suite quick --iterations 2 --output benchmarks/results
```

This writes JSON evidence such as `benchmarks/results/benchmark-quick.json` with local effort, workflow, harness latency, and the current evidence-backed scorecard.

You can also attach an external-baseline metadata file:

```bash
.venv/bin/uaek benchmark --suite quick --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

`benchmarks/baselines/fable5.example.json` is only a schema example and intentionally records `status = not_configured`. Replace it with an authorized run artifact before making comparative Fable 5 claims.

When the reference model is unavailable or withdrawn, use the proxy validation suite instead of pretending a direct baseline exists:

```bash
.venv/bin/uaek benchmark --suite proxy --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

This writes `benchmarks/results/benchmark-proxy.json` with a GitHub-derived validation matrix and `direct_baseline.status = retired_unavailable`.

The adapter-readiness suite verifies the first external Agent Adapter contract without claiming a live platform benchmark:

```bash
.venv/bin/uaek benchmark --suite adapter --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

This writes `benchmarks/results/benchmark-adapter.json` with the `stdin_stdout_json_v1` protocol, command adapter checks, trace logging checks, and scorecard movement from 88 to 90 under an adapter-readiness口径.

The platform-artifact suite records the next layer of evidence readiness:

```bash
.venv/bin/uaek platform discover --output benchmarks/results/platform-discovery.json
.venv/bin/uaek benchmark --suite platform --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

This writes `benchmarks/results/platform-discovery.json` and `benchmarks/results/benchmark-platform.json`. Current local probes discovered Codex, Claude Code, Mimo Code and Hermes entrypoints. Codex, Mimo Code and Hermes version probes completed as `local_command` artifacts; the Claude App entrypoint exists, but its non-interactive version probe timed out and is recorded as a failed local-command artifact. None of these artifacts is a live external benchmark run.

The excellence-readiness suite is the 95+ product evidence gate:

```bash
.venv/bin/uaek benchmark --suite excellence --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

This writes `benchmarks/results/benchmark-excellence.json`. It requires at least one valid `live_external` task artifact, the four-platform artifact matrix, adversarial validation checks and a deterministic self-improvement scoring loop. The current evidence includes one Codex live task artifact returning `UAEK_LIVE_TASK_OK`. We do not roll this up into a single "/100" readiness score — per-dimension results and their evidence-ladder rungs live in [`../VERIFICATION_SCORECARD.md`](../VERIFICATION_SCORECARD.md). This is still not a retired Fable 5 rerun and not a full live run for every platform.

The live-matrix suite measures the next evidence layer:

```bash
.venv/bin/uaek benchmark --suite live_matrix --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

This writes `benchmarks/results/benchmark-live_matrix.json`. Under the hardened口径, "pass" means the full graded suite (10/10 tasks), and **2/4 providers clear it**; Mimo/Hermes partial artifacts (8–9/10) are retained as evidence but **not** counted as graded-live passes, and Claude App has a blocked live attempt caused by headless Electron/IndexedDB lock behavior. We do not report a rolled-up "/100" score here — see the per-dimension evidence and rungs in [`../VERIFICATION_SCORECARD.md`](../VERIFICATION_SCORECARD.md). The full 4/4 live matrix remains open.

The next benchmark stage should add full comparison data:

- task suite with at least 10 tasks;
- baseline, UAEK, and no-UAEK runs;
- correctness, cost/steps, verification catch rate, and context fidelity metrics;
- external Fable 5 baseline data under `benchmarks/baselines/` or `benchmarks/results/`;
- live external Agent platform run records for every target provider;
- a generated comparison report.

Until those external comparison artifacts exist, claims about outperforming Fable 5 should be treated as design goals rather than verified benchmark results.
