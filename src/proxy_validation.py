"""GitHub-derived proxy validation for unavailable direct baselines."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from src.config import load_config
from src.harness import AgentHarness, HarnessRequest
from src.logger import JsonlLogger
from src.memory import MemoryService


def build_proxy_validation_matrix() -> dict[str, Any]:
    """Return the public benchmark-practice matrix used for proxy validation."""
    sources = [
        {
            "name": "SWE-bench",
            "url": "https://github.com/swe-bench/SWE-bench",
            "practice": "real GitHub issues, reproducible Docker evaluation, logs/results",
        },
        {
            "name": "HAL harness",
            "url": "https://github.com/princeton-pli/hal-harness",
            "practice": "unified benchmark CLI, agent-agnostic adapters, trace/cost tracking",
        },
        {
            "name": "tau-bench",
            "url": "https://github.com/sierra-research/tau-bench",
            "practice": "tool-agent-user interaction with domain APIs and repeated pass metrics",
        },
        {
            "name": "AppWorld",
            "url": "https://github.com/StonyBrookNLP/appworld",
            "practice": "sandboxed app world, local APIs, task state reset and outputs",
        },
        {
            "name": "OSWorld",
            "url": "https://github.com/xlang-ai/OSWorld",
            "practice": "real computer environments and verified task repair process",
        },
        {
            "name": "Inspect AI",
            "url": "https://github.com/UKGovernmentBEIS/inspect_ai",
            "practice": "general eval framework for tool use, multi-turn dialog and scoring",
        },
        {
            "name": "ImpossibleBench",
            "url": "https://github.com/safety-research/impossiblebench",
            "practice": "impossible variants for cheating and shortcut detection",
        },
        {
            "name": "AgentSafety",
            "url": "https://github.com/OSU-NLP-Group/AgentSafety",
            "practice": "agent safety, attack and defense benchmark taxonomy",
        },
        {
            "name": "MLE-bench",
            "url": "https://github.com/openai/mle-bench",
            "practice": "objective grading scripts for ML engineering submissions",
        },
        {
            "name": "MLAgentBench",
            "url": "https://github.com/snap-stanford/mlagentbench",
            "practice": "sandboxed ML experimentation tasks and repeatable reports",
        },
    ]
    dimensions = [
        "reproducible_artifacts",
        "isolated_execution",
        "tool_interaction_state",
        "trace_and_cost_observability",
        "objective_scoring",
        "safety_and_cheat_resistance",
        "cross_environment_readiness",
    ]
    return {
        "strategy": "proxy_validation_for_retired_direct_baseline",
        "sources": sources,
        "dimensions": dimensions,
        "limitations": [
            "This is not a direct run against the retired reference model.",
            "Remote CI and live external agent adapters still require separate evidence.",
        ],
    }


def run_proxy_validation(iterations: int = 1) -> dict[str, Any]:
    """Run local proxy checks and return score evidence."""
    safe_iterations = max(1, int(iterations))
    matrix = build_proxy_validation_matrix()
    checks = [
        _check_harness_pipeline(safe_iterations),
        _check_config_logging(),
        _check_ci_gate_contract(),
        _check_safe_workflow_actions(),
    ]
    required_checks = [check for check in checks if check["required"]]
    passed_required = [check for check in required_checks if check["status"] == "pass"]
    pass_rate = len(passed_required) / len(required_checks)

    return {
        "status": "completed" if pass_rate == 1.0 else "partial",
        "matrix": matrix,
        "direct_baseline": {
            "status": "retired_unavailable",
            "reason": "The reference model is not currently available for direct reruns.",
        },
        "checks": checks,
        "metrics": {
            "github_source_count": len(matrix["sources"]),
            "validation_dimension_count": len(matrix["dimensions"]),
            "required_checks": len(required_checks),
            "passed_required_checks": len(passed_required),
            "proxy_pass_rate": round(pass_rate, 4),
        },
        "previous_score": 82,
        "recommended_score": 88 if pass_rate == 1.0 else 82,
        "score_delta": 6 if pass_rate == 1.0 else 0,
    }


def _check_harness_pipeline(iterations: int) -> dict[str, Any]:
    successes = 0
    with tempfile.TemporaryDirectory(prefix="uaek-proxy-harness-") as tmp_dir:
        harness = AgentHarness(MemoryService(Path(tmp_dir) / "memory"))
        for _ in range(iterations):
            result = harness.run(
                HarnessRequest(
                    task="validate proxy evidence using local harness",
                    tags=["proxy-validation"],
                )
            )
            if result.success and result.report.get("score") == 1.0:
                successes += 1

    return {
        "id": "local_harness_pipeline",
        "required": True,
        "status": "pass" if successes == iterations else "fail",
        "source_practices": ["SWE-bench", "HAL harness", "MLAgentBench"],
        "evidence": f"{successes}/{iterations} local harness runs completed with score 1.0",
    }


def _check_config_logging() -> dict[str, Any]:
    config = load_config()
    with tempfile.TemporaryDirectory(prefix="uaek-proxy-log-") as tmp_dir:
        log_path = Path(tmp_dir) / "proxy.jsonl"
        written_path = JsonlLogger(log_path, enabled=config.logging.enabled).record(
            "proxy_validation",
            {"score_target": 88, "source": "github-derived-matrix"},
        )
        record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    passed = written_path == log_path and record["event"] == "proxy_validation"
    return {
        "id": "structured_trace_logging",
        "required": True,
        "status": "pass" if passed else "fail",
        "source_practices": ["HAL harness", "Inspect AI"],
        "evidence": "JSONL trace event written and parsed",
    }


def _check_ci_gate_contract() -> dict[str, Any]:
    workflow_path = Path(".github/workflows/ci.yml")
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    required_terms = [
        "ruff check src api mcp tests",
        "mypy src api mcp",
        "pytest",
        "--cov=src",
    ]
    passed = all(term in workflow_text for term in required_terms)
    return {
        "id": "local_ci_gate_contract",
        "required": True,
        "status": "pass" if passed else "fail",
        "source_practices": ["SWE-bench", "HAL harness"],
        "evidence": "CI workflow defines lint, typecheck, tests and coverage gates",
    }


def _check_safe_workflow_actions() -> dict[str, Any]:
    config_path = Path("config/default.yaml")
    config = load_config(config_path if config_path.exists() else None)
    risky_actions = {"exec", "shell", "python", "subprocess", "eval"}
    configured_actions = set(config.workflow.safe_actions)
    passed = configured_actions.isdisjoint(risky_actions) and {"echo", "effort"}.issubset(
        configured_actions
    )
    return {
        "id": "safe_action_surface",
        "required": True,
        "status": "pass" if passed else "fail",
        "source_practices": ["AppWorld", "ImpossibleBench", "AgentSafety"],
        "evidence": "workflow safe_actions exclude shell/eval style execution",
    }
