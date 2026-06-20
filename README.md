![CI](https://github.com/Audrey-cn/universal-agent-embedding-kit/actions/workflows/ci.yml/badge.svg)

# UAEK — Universal Agent Embedding Kit

A model-agnostic, embeddable kit that gives any agent platform stronger
**verification, context management, effort routing, memory, and workflow** — plus
a benchmark suite built around one principle: **report numbers that survive an
attack, not numbers that look good.**

UAEK started as a study of what made a now-retired frontier agent ("Fable 5")
effective, on the thesis that *the advantage was engineering, not the model*. It
targets the specific weaknesses that study surfaced, and measures each one
honestly — including where the honest answer is "less impressive than we hoped."

```bash
pip install -e '.[dev]'
uaek --help
uaek benchmark --suite adversarial   # cheating-rate evidence
uaek capability matrix               # cross-platform graded task matrix
python -m pytest -q                  # 389 tests passing
```

## What's inside

| Component | Module | Does |
|-----------|--------|------|
| Universal verification | `src/verify`, `src/adversarial_verification.py` | execution-grounded, adversarial (not self-graded) checks |
| Adaptive context manager | `src/context_management.py` | relevance filtering + compression vs context rot |
| Effort dispatch | `src/effort` | classify task → right-size effort |
| Cost model | `src/cost_model.py` | cache-aware cost accounting (prompt/KV cache) |
| Real-scenario benchmark | `src/scenario_benchmark.py` | multi-dimensional scoring (catches regressions a pass/fail misses) |
| Cross-platform capability | `src/capability_matrix.py` | drive + objectively grade real agent platforms |
| Workflow / memory / skills / harness | `src/workflow`, `src/memory`, `src/skills`, `src/harness` | orchestration primitives |

Exposed three ways: CLI (`uaek`), HTTP API (`api/`), and MCP server (`mcp/`).

## Honest evidence

Every number below is the result of a deliberate **red-team round** (independent
agents trying to prove each metric inflated) followed by **hardening** to a value
that survives. Numbers came *down* in that process — that's the point. Each is
tagged with its rung on the evidence ladder (see `docs/methodology.md`).

| Dimension | Result | Rung | Honest caveat |
|-----------|--------|------|---------------|
| Self-grading cheating rate | naive ~60–71% → **adversarial 0%** (target <10%) | 3 (real agent code) | scoped to this corpus + input generator, **not** a proof of impossibility |
| Context utilization | adaptive **0.85** expected accuracy @70% util vs naive 0.57 | 3 (real needle test) | live needle test recalled 6/6 @31K tokens — validates retrieval is tractable, does **not** prove the adaptive advantage live |
| Cost reduction | modeled −43% (−49% w/ 1h cache tier); **real warm-session −82%, 92% cache hit** | 4 (real token bill) | TTL-conditional; a fully-cold session costs *more* than baseline |
| Real-scenario benchmark | multi-dimensional; flags a feature-complete-but-regressing solution a pass/fail accepts | 3 (real agent solutions) | seed + framework, not yet 100+ live multi-hour sessions |
| Cross-platform matrix | **4/4** providers pass objectively-graded live code tasks | 4 (live) | one CLI is configured to route to a shared model backend; measures platform-runtime embeddability, not 4 independent models |

Gates: **389 tests pass**, ruff + mypy clean. Full breakdown and provenance in
[`VERIFICATION_SCORECARD.md`](VERIFICATION_SCORECARD.md).

## The methodology is the product

The most reusable thing here isn't a number — it's the discipline:

- **Evidence-strength ladder** — ① deterministic local benchmark → ② stress/adversarial → ③ real data → ④ live measurement → ⑤ external validation. "Improving" a metric means climbing the ladder, never turning a knob.
- **Red-team hardening** — before reporting a self-measured number, spawn independent agents to *prove it's inflated*, then harden until it survives.

See [`docs/methodology.md`](docs/methodology.md), the research framing in
[`RESEARCH_PROPOSAL.md`](RESEARCH_PROPOSAL.md), and the operating procedure in
[`SOP.md`](SOP.md) / [`EXECUTION_MANUAL.md`](EXECUTION_MANUAL.md).

## Limitations (read these)

- Benchmarks are **deterministic local models with live spot-checks**, not a
  large-scale live evaluation. Where a claim is modeled, it says so.
- Live measurements lean on a single dominant provider; multi-provider /
  multi-sample scaling and **external (rung-5) validation are open work**.
- The original reference model is retired, so there is **no direct baseline**;
  comparisons use documented figures and proxy validation, never a fabricated
  rerun.

## License

MIT — see [`LICENSE`](LICENSE).

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

[中文版](README.zh.md) | [CHANGELOG](CHANGELOG.md)
