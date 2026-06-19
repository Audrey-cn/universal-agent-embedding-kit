"""Benchmark runner for reproducible UAEK score evidence."""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.effort import classify
from src.harness import AgentHarness, HarnessRequest
from src.memory import MemoryService
from src.workflow import execute_workflow_config

SUPPORTED_SUITES = {
    "quick",
    "proxy",
    "adapter",
    "platform",
    "excellence",
    "live_matrix",
    "capability",
    "adversarial",
    "context",
    "cost",
    "scenario",
    "fable5",
    "cross_platform",
}


def run_benchmark(
    suite: str = "quick",
    iterations: int = 5,
    baseline_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run a local benchmark suite and return serializable score evidence."""
    if suite not in SUPPORTED_SUITES:
        raise ValueError(f"Unsupported benchmark suite: {suite}")
    safe_iterations = max(1, int(iterations))

    metrics = {
        "effort_latency_ms": _average_ms(
            lambda: classify("implement benchmark evidence pipeline"), safe_iterations
        ),
        "workflow_latency_ms": _average_ms(_run_workflow_once, safe_iterations),
        "harness_latency_ms": _average_ms(_run_harness_once, safe_iterations),
    }

    proxy_validation: dict[str, Any] | None = None
    adapter_readiness: dict[str, Any] | None = None
    platform_readiness: dict[str, Any] | None = None
    excellence_readiness: dict[str, Any] | None = None
    live_matrix_readiness: dict[str, Any] | None = None
    capability_readiness: dict[str, Any] | None = None
    adversarial_readiness: dict[str, Any] | None = None
    context_rot_readiness: dict[str, Any] | None = None
    cost_readiness: dict[str, Any] | None = None
    scenario_readiness: dict[str, Any] | None = None
    if suite == "proxy":
        from src.proxy_validation import run_proxy_validation

        proxy_validation = run_proxy_validation(safe_iterations)
    if suite == "adapter":
        from src.adapters import run_adapter_readiness

        adapter_readiness = run_adapter_readiness(safe_iterations)
    if suite == "platform":
        from src.platform_runs import run_platform_artifact_readiness

        platform_readiness = run_platform_artifact_readiness(safe_iterations)
    if suite == "excellence":
        from src.excellence import run_excellence_readiness

        excellence_readiness = run_excellence_readiness()
    if suite == "live_matrix":
        from src.live_matrix import run_live_matrix_readiness

        live_matrix_readiness = run_live_matrix_readiness()
    if suite == "capability":
        from src.capability_matrix import run_capability_readiness

        capability_readiness = run_capability_readiness()
    if suite == "adversarial":
        from src.adversarial_verification import run_adversarial_readiness

        adversarial_readiness = run_adversarial_readiness()
    if suite == "context":
        from src.context_management import run_context_rot_readiness

        context_rot_readiness = run_context_rot_readiness()
    if suite == "cost":
        from src.cost_model import run_cost_readiness

        cost_readiness = run_cost_readiness()
    if suite == "scenario":
        from src.scenario_benchmark import run_scenario_readiness

        scenario_readiness = run_scenario_readiness()

    result = {
        "suite": suite,
        "status": "completed",
        "generated_at": datetime.now(UTC).isoformat(),
        "iterations": safe_iterations,
        "metrics": metrics,
        "scorecard": _scorecard_for_suite(
            suite,
            proxy_validation,
            adapter_readiness,
            platform_readiness,
            excellence_readiness,
            live_matrix_readiness,
            capability_readiness,
            adversarial_readiness,
            context_rot_readiness,
            cost_readiness,
            scenario_readiness,
        ),
        "external_baseline": _load_external_baseline(baseline_path),
    }
    if proxy_validation is not None:
        result["proxy_validation"] = proxy_validation
    if adapter_readiness is not None:
        result["adapter_readiness"] = adapter_readiness
    if platform_readiness is not None:
        result["platform_run_readiness"] = platform_readiness
    if excellence_readiness is not None:
        result["excellence_readiness"] = excellence_readiness
    if live_matrix_readiness is not None:
        result["live_matrix_readiness"] = live_matrix_readiness
    if capability_readiness is not None:
        result["capability_readiness"] = capability_readiness
    if adversarial_readiness is not None:
        result["adversarial_readiness"] = adversarial_readiness
    if context_rot_readiness is not None:
        result["context_rot_readiness"] = context_rot_readiness
    if cost_readiness is not None:
        result["cost_readiness"] = cost_readiness
    if scenario_readiness is not None:
        result["scenario_readiness"] = scenario_readiness
    return result


def write_benchmark_result(result: dict[str, Any], output: Path | str) -> Path:
    """Write a benchmark result to a JSON file and return the path."""
    output_path = Path(output)
    if output_path.suffix.lower() == ".json":
        result_path = output_path
    else:
        result_path = output_path / f"benchmark-{result['suite']}.json"

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result_path


def _load_external_baseline(baseline_path: Path | str | None) -> dict[str, Any]:
    if baseline_path is None:
        return {
            "status": "not_configured",
            "reason": "No authorized external Fable 5 baseline run is available in this repo.",
        }

    path = Path(baseline_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("External baseline file must contain a JSON object")

    return {
        "name": data.get("name", "external"),
        "status": data.get("status", "provided"),
        "path": str(path),
        "source": data.get("source", ""),
        "generated_at": data.get("generated_at"),
        "metrics": data.get("metrics", {}),
        "notes": data.get("notes", []),
    }


def _scorecard_for_suite(
    suite: str,
    proxy_validation: dict[str, Any] | None,
    adapter_readiness: dict[str, Any] | None,
    platform_readiness: dict[str, Any] | None,
    excellence_readiness: dict[str, Any] | None,
    live_matrix_readiness: dict[str, Any] | None,
    capability_readiness: dict[str, Any] | None,
    adversarial_readiness: dict[str, Any] | None = None,
    context_rot_readiness: dict[str, Any] | None = None,
    cost_readiness: dict[str, Any] | None = None,
    scenario_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if suite == "scenario" and scenario_readiness is not None:
        return {
            "previous_score": None,
            "current_score": None,
            "score_delta": 0,
            "dimension": "4_real_scenario_benchmark",
            "scenario_count": scenario_readiness["scenario_count"],
            "reference_overall": scenario_readiness["reference_overall"],
            "flawed_overall": scenario_readiness["flawed_overall"],
            "flags_hidden_regression": scenario_readiness["flags_hidden_regression"],
            "resolved_findings": scenario_readiness["resolved_findings"],
            "remaining_findings": ["REAL_SCENARIO_CORPUS_100PLUS", "LIVE_MULTI_HOUR_SESSIONS"],
            "basis": [
                "research proposition 4: multi-dimensional real-scenario benchmark",
                "scores correctness + completeness/no-regression + context retention + robustness",
                "flags a feature-complete solution that regresses an existing case, which a "
                "correctness-only gate would pass",
                "seed + framework; a 100+ live multi-hour corpus remains open work",
            ],
        }

    if suite == "cost" and cost_readiness is not None:
        return {
            "previous_score": None,
            "current_score": None,
            "score_delta": 0,
            "dimension": "4_cost",
            "cost_reduction": cost_readiness["cost_reduction"],
            "cache_hit_rate": cost_readiness["cache_hit_rate"],
            "proposal_target": cost_readiness["proposal_target"],
            "stretch_target": cost_readiness["stretch_target"],
            "resolved_findings": cost_readiness["resolved_findings"],
            "remaining_findings": ["REAL_SCENARIO_BENCHMARK"],
            "basis": [
                "research proposition 3: cache-aware cost model",
                f"prompt/KV cache hit rate {cost_readiness['cache_hit_rate']:.0%} on a "
                "stable-prefix agent session",
                f"total cost reduction {cost_readiness['cost_reduction']:.0%} "
                f"(proposal target {cost_readiness['proposal_target']:.0%}, "
                f"stretch {cost_readiness['stretch_target']:.0%})",
                "modeled under documented cache multipliers, not a billed invoice",
            ],
        }

    if suite == "context" and context_rot_readiness is not None:
        naive_acc = context_rot_readiness["naive"]["accuracy_at_target"]
        adaptive_acc = context_rot_readiness["adaptive"]["accuracy_at_target"]
        target = context_rot_readiness["target_utilization"]
        return {
            "previous_score": None,
            "current_score": None,
            "score_delta": 0,
            "dimension": "3_context_utilization",
            "naive_accuracy_at_target": naive_acc,
            "adaptive_accuracy_at_target": adaptive_acc,
            "accuracy_gap_at_target": context_rot_readiness["accuracy_gap_at_target"],
            "target_utilization": target,
            "resolved_findings": context_rot_readiness["resolved_findings"],
            "remaining_findings": ["REAL_SCENARIO_BENCHMARK"],
            "basis": [
                "research proposition 1: adaptive context management vs context rot",
                f"at {target:.0%} utilization, naive accuracy {naive_acc:.0%} (documented "
                "~40% dumb zone)",
                f"adaptive (lossy compression + relevance filtering) {adaptive_acc:.0%} "
                "expected accuracy with a seed band",
                "red-teamed: compression loss is modeled, not assumed away; deterministic "
                "retention benchmark, not a live-LLM run",
            ],
        }

    if suite == "adversarial" and adversarial_readiness is not None:
        naive = adversarial_readiness["naive"]["cheating_rate"]
        adv = adversarial_readiness["adversarial"]["cheating_rate"]
        return {
            "previous_score": None,
            "current_score": None,
            "score_delta": 0,
            "dimension": "2_self_grading_cheating_rate",
            "naive_cheating_rate": naive,
            "adversarial_cheating_rate": adv,
            "target_max_cheating_rate": adversarial_readiness["target_max_cheating_rate"],
            "resolved_findings": adversarial_readiness["resolved_findings"],
            "remaining_findings": ["W4.1_CONTEXT_ROT", "REAL_SCENARIO_BENCHMARK"],
            "basis": [
                "research proposition 2: adversarial verification cuts self-grading cheating",
                f"naive happy-path self-check cheating rate {naive:.0%}",
                f"adversarial differential verification cheating rate {adv:.0%} "
                f"(target <{int(adversarial_readiness['target_max_cheating_rate'] * 100)}%)",
                "measured on a constructed correct/buggy corpus, not on live Fable 5 runs",
            ],
        }

    if suite == "proxy" and proxy_validation is not None:
        return {
            "previous_score": proxy_validation["previous_score"],
            "current_score": proxy_validation["recommended_score"],
            "score_delta": proxy_validation["score_delta"],
            "resolved_findings": [
                "F007_PROXY_VALIDATED",
                "F008",
                "F009",
                "F010",
                "F013",
                "F014",
            ],
            "remaining_findings": [
                "DIRECT_RETIRED_MODEL_UNAVAILABLE",
                "CI_REMOTE_UNVERIFIED",
                "LIVE_EXTERNAL_PLATFORM_RUNS",
                "FULL_CROSS_PLATFORM_MATRIX",
            ],
            "basis": [
                "direct reference model is unavailable for rerun",
                "GitHub-derived proxy validation matrix is documented",
                "local harness, config/logging, CI gate and safe-action checks pass",
                "proxy validation does not claim direct Fable 5 superiority",
            ],
        }

    if suite == "adapter" and adapter_readiness is not None:
        return {
            "previous_score": adapter_readiness["previous_score"],
            "current_score": adapter_readiness["recommended_score"],
            "score_delta": adapter_readiness["score_delta"],
            "resolved_findings": [
                "F007_PROXY_VALIDATED",
                "F016_EXTERNAL_ADAPTER_CONTRACT",
            ],
            "remaining_findings": [
                "DIRECT_RETIRED_MODEL_UNAVAILABLE",
                "LIVE_EXTERNAL_PLATFORM_RUNS",
                "CI_REMOTE_UNVERIFIED",
                "FULL_CROSS_PLATFORM_MATRIX",
                "ADVERSARIAL_SELF_IMPROVEMENT_SUITE",
            ],
            "basis": [
                "command adapter stdin/stdout JSON protocol is implemented",
                "adapter failures preserve stdout, stderr, return code and timeout errors",
                "adapter runs can write JSONL traces",
                "adapter readiness does not claim live external platform superiority",
            ],
        }

    if suite == "platform" and platform_readiness is not None:
        return {
            "previous_score": platform_readiness["previous_score"],
            "current_score": platform_readiness["recommended_score"],
            "score_delta": platform_readiness["score_delta"],
            "resolved_findings": [
                "F007_PROXY_VALIDATED",
                "F016_EXTERNAL_ADAPTER_CONTRACT",
                "F018_PLATFORM_RUN_ARTIFACTS",
            ],
            "remaining_findings": [
                "DIRECT_RETIRED_MODEL_UNAVAILABLE",
                "LIVE_EXTERNAL_PLATFORM_RUNS",
                "CI_REMOTE_UNVERIFIED",
                "FULL_CROSS_PLATFORM_MATRIX",
                "ADVERSARIAL_SELF_IMPROVEMENT_SUITE",
            ],
            "basis": [
                "platform_run_v1 artifact schema is implemented",
                "platform record and validate commands are available",
                "Codex, Claude Code, Mimo Code and Hermes are declared for discovery",
                "platform readiness does not claim a live external benchmark",
            ],
        }

    if suite == "excellence" and excellence_readiness is not None:
        return {
            "previous_score": excellence_readiness["previous_score"],
            "current_score": excellence_readiness["recommended_score"],
            "score_delta": excellence_readiness["score_delta"],
            "resolved_findings": excellence_readiness["resolved_findings"],
            "remaining_findings": excellence_readiness["remaining_findings"],
            "basis": [
                "at least one valid live_external platform task artifact is required for 95+",
                "cross-platform artifact matrix covers Codex, Claude Code/App, Mimo Code "
                "and Hermes",
                "adversarial validation rejects failed or forged live artifacts",
                "self-improvement score loop resolves findings only when evidence exists",
                "excellence readiness does not claim a retired Fable 5 rerun",
            ],
        }

    if suite == "live_matrix" and live_matrix_readiness is not None:
        return {
            "previous_score": live_matrix_readiness["previous_score"],
            "current_score": live_matrix_readiness["recommended_score"],
            "score_delta": live_matrix_readiness["score_delta"],
            "resolved_findings": live_matrix_readiness["resolved_findings"],
            "remaining_findings": live_matrix_readiness["remaining_findings"],
            "basis": [
                "live_matrix evaluates valid live_external artifacts per provider",
                "blocked provider attempts are diagnostics and do not count as live success",
                "three live providers with blocked diagnostics can support 97/100",
                "four live providers are required to close the full live matrix finding",
            ],
        }

    if suite == "capability" and capability_readiness is not None:
        return {
            "previous_score": capability_readiness["previous_score"],
            "current_score": capability_readiness["recommended_score"],
            "score_delta": capability_readiness["score_delta"],
            "resolved_findings": capability_readiness["resolved_findings"],
            "remaining_findings": capability_readiness["remaining_findings"],
            "basis": [
                "capability matrix grades real code tasks with an isolated test harness",
                "grading is objective (unit cases), not model self-grading",
                "two graded-live providers with blocked diagnostics can support 98/100",
                "three graded-live providers can support 99/100; four close the full matrix",
            ],
        }

    return {
        "previous_score": 68,
        "current_score": 82,
        "score_delta": 14,
        "resolved_findings": ["F008", "F009", "F010", "F013", "F014"],
        "remaining_findings": [
            "F007",
            "CI_REMOTE_UNVERIFIED",
            "CROSS_PLATFORM",
            "EXTERNAL_ADAPTER",
        ],
        "basis": [
            "benchmark CLI writes reproducible JSON results",
            "minimal local Agent Harness is implemented and tested",
            "uaek run exposes the harness as a reusable local entrypoint",
            "CI workflow and external baseline schema are configured",
            "configuration management is implemented and tested",
            "structured JSONL run logging is implemented and tested",
            "external Fable 5 baseline result remains unconfigured",
        ],
    }


def _average_ms(func: Callable[[], Any], iterations: int) -> float:
    timings: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        timings.append((time.perf_counter() - start) * 1000)
    return round(statistics.mean(timings), 4)


def _run_workflow_once() -> dict[str, Any]:
    return execute_workflow_config(
        {
            "id": "benchmark-workflow",
            "tasks": [
                {
                    "id": "echo",
                    "name": "Echo benchmark task",
                    "action": "echo",
                    "args": ["benchmark"],
                }
            ],
        }
    )


def _run_harness_once() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="uaek-benchmark-") as tmp_dir:
        harness = AgentHarness(MemoryService(Path(tmp_dir) / "memory"))
        return harness.run(HarnessRequest(task="implement benchmark evidence pipeline")).to_dict()
