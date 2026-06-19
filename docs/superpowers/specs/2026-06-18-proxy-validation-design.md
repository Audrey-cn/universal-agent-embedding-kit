# Proxy Validation Design

## Goal

The newest reference model is no longer available for direct baseline runs. UAEK should not claim a direct Fable 5 comparison without a runnable artifact. Instead, the project will add a proxy validation suite based on public GitHub benchmark practices, then score the remaining product maturity gap using reproducible local evidence.

## GitHub-Derived Practices

The proxy suite uses these public practices as design inputs:

- SWE-bench: real GitHub issue tasks, Docker-based reproducible execution, evaluation logs and result artifacts.
  Source: https://github.com/swe-bench/SWE-bench
- HAL harness: unified CLI across benchmarks, agent-agnostic adapters, trace/cost logging, local or cloud execution.
  Source: https://github.com/princeton-pli/hal-harness
- tau-bench / tau2-bench: tool-agent-user interaction, domain APIs, repeated pass measurements across turns.
  Sources: https://github.com/sierra-research/tau-bench and https://github.com/sierra-research/tau2-bench
- AppWorld: sandboxed application world, local APIs, task state reset and output directories.
  Source: https://github.com/StonyBrookNLP/appworld
- OSWorld: real computer environment evaluation and verified task repair process.
  Source: https://github.com/xlang-ai/OSWorld
- Inspect AI / ImpossibleBench / AgentSafety: reusable eval framework, model/tool-use scoring, adversarial and cheating-resistance checks.
  Sources: https://github.com/UKGovernmentBEIS/inspect_ai, https://github.com/safety-research/impossiblebench, https://github.com/OSU-NLP-Group/AgentSafety
- MLE-bench and MLAgentBench: objective grading scripts, sandboxed ML experimentation tasks and repeatable report artifacts.
  Sources: https://github.com/openai/mle-bench and https://github.com/snap-stanford/mlagentbench

## Scope

Add a `proxy` benchmark suite that:

- records a GitHub-derived validation matrix in machine-readable benchmark output;
- runs local evidence checks for harness execution, config/logging, CI gate definition and safe workflow actions;
- raises the evidence-backed product score from 82 to 88 when the proxy suite passes;
- explicitly marks the retired direct model baseline as unavailable, not completed.

## Non-Goals

- Do not claim a live Fable 5 run.
- Do not call unavailable or withdrawn external models.
- Do not install heavyweight benchmark dependencies such as SWE-bench, OSWorld or AppWorld in this repository.
- Do not mark remote GitHub Actions as verified while the workspace is not a Git repository.

## Components

- `src/proxy_validation.py`: source matrix and local proxy validation checks.
- `src/benchmark.py`: route `suite="proxy"` and include proxy validation evidence in scorecard output.
- `src/cli.py`: allow `uaek benchmark --suite proxy`.
- `tests/unit/test_proxy_validation.py`: TDD coverage for matrix sources, proxy result semantics and CLI output.

## Scoring

The score moves from 82/100 to 88/100 only under the proxy-validation label. This means UAEK has a reproducible side-validation package suitable for a withdrawn reference model scenario. The score does not represent direct superiority. After the local command adapter contract, remaining enhancement work becomes live external platform runs, remote CI evidence, cross-platform task runs and stronger adversarial/self-improvement benchmarks.
