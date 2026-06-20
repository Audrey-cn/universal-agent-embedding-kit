"""Tests for the cost model — research proposition 3 (cost / performance).

Models an agentic multi-turn session under Anthropic-style pricing (uncached
input 1.0x, cache write 1.25x, cache read 0.10x, output 5x). The dominant lever
is prompt/KV cache reuse of the stable prefix (system + tools + history): real
agent sessions hit 70-90%+ cache, pushing cost reduction well past the
proposal's conservative -50%.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_baseline_recharges_full_context_each_turn():
    from src.cost_model import baseline_cost, build_agent_workload

    workload = build_agent_workload()
    baseline = baseline_cost(workload)

    # No cache: every input token is charged at full price, none from cache.
    assert baseline["cache_read_tokens"] == 0
    assert baseline["total_cost"] > 0


def test_uaek_caching_achieves_high_hit_rate():
    from src.cost_model import build_agent_workload, uaek_cost

    workload = build_agent_workload()
    uaek = uaek_cost(workload)

    assert uaek["cache_hit_rate"] >= 0.70


def test_fresh_cache_reduction_exceeds_50pct_but_ttl_misses_degrade_it():
    """Red-teamed: caching beats -50% only when fresh; TTL misses degrade it."""
    from src.cost_model import baseline_cost, build_agent_workload, cost_reduction, uaek_cost

    workload = build_agent_workload()
    baseline = baseline_cost(workload)
    fresh = cost_reduction(baseline, uaek_cost(workload, cache_miss_rate=0.0))
    realistic = cost_reduction(baseline, uaek_cost(workload, cache_miss_rate=0.2))

    assert fresh >= 0.50  # fresh cache clears the proposal target
    assert realistic < fresh  # a 20% TTL miss rate measurably degrades it


def test_full_ttl_miss_can_cost_more_than_baseline():
    """At 100% cache miss the prefix is re-written every turn — UAEK costs more."""
    from src.cost_model import baseline_cost, build_agent_workload, cost_reduction, uaek_cost

    workload = build_agent_workload()
    reduction = cost_reduction(baseline_cost(workload), uaek_cost(workload, cache_miss_rate=1.0))

    assert reduction < 0.0


def test_effort_routing_reduces_cost_further():
    from src.cost_model import build_agent_workload, uaek_cost

    workload = build_agent_workload()
    with_effort = uaek_cost(workload, use_effort_routing=True)
    without_effort = uaek_cost(workload, use_effort_routing=False)

    assert with_effort["total_cost"] < without_effort["total_cost"]


def test_long_ttl_stable_prefix_improves_realistic_reduction():
    """Improvement: the 1-hour stable-prefix tier survives TTL misses, raising the number."""
    from src.cost_model import baseline_cost, build_agent_workload, cost_reduction, uaek_cost

    workload = build_agent_workload()
    baseline = baseline_cost(workload)
    five_min = cost_reduction(baseline, uaek_cost(workload, cache_miss_rate=0.2))
    one_hour = cost_reduction(
        baseline, uaek_cost(workload, cache_miss_rate=0.2, long_ttl_stable_prefix=True)
    )

    assert one_hour > five_min  # the improvement is real


def test_run_cost_readiness_reports_honest_improved_number():
    from src.cost_model import run_cost_readiness

    result = run_cost_readiness()

    assert result["dimension"] == "4_cost"
    assert result["cache_hit_rate"] >= 0.70
    # The 1h-tier improvement raises the headline above the 5-min-only number...
    assert result["cost_reduction"] > result["cost_reduction_5min_tier"]
    assert result["ttl_improvement"] > 0
    # ...but is still below the fresh-cache best case, and honestly reported.
    assert result["cost_reduction"] < result["cost_reduction_best_case"]
    assert result["cost_reduction_best_case"] >= 0.50
    # Honest: a genuine +6pt improvement, but still just under target on the default
    # workload — status stays partial rather than gaming a constant to cross the line.
    assert result["status"] == "partial"
    assert result["live_measurement_scope"] == "warm_best_case"
    assert result["cold_path_cost_increase"] > 0
    assert _check_status(result, "best_case_beats_proposal_target") == "pass"
    assert result["effort_routing_contribution"] > 0


def test_cost_reduction_degrades_along_ttl_sweep():
    from src.cost_model import run_cost_readiness

    result = run_cost_readiness()
    sweep = result["ttl_sweep"]
    assert len(sweep) >= 4
    # Fresh cache saves the most; a fully-expired cache saves the least.
    assert sweep[0]["cost_reduction"] > sweep[-1]["cost_reduction"]


def test_rung4_live_measurement_validates_the_model():
    """Rung-4: a real live-session token bill confirms the modeled high cache hit."""
    from src.cost_model import load_live_cost_measurement, run_cost_readiness

    live = load_live_cost_measurement()
    if live is None:
        import pytest

        pytest.skip("no live cost measurement artifact present")

    measured = live["measured"]
    assert measured["real_cache_hit_rate"] >= 0.70  # real measured, not modeled
    assert live["evidence_rung"] == 4
    assert live["red_team_caveats"]  # warm-session / single-provider caveats recorded

    result = run_cost_readiness()
    assert result["live_measurement"] is not None
    assert _check_status(result, "live_measurement_validates_model") == "pass"


def test_benchmark_cost_suite():
    from src.benchmark import run_benchmark

    result = run_benchmark("cost", iterations=1)

    assert result["suite"] == "cost"
    assert "cost_readiness" in result
    assert result["cost_readiness"]["cost_reduction_best_case"] >= 0.50


def test_cli_benchmark_cost_suite(tmp_path: Path):
    output_path = tmp_path / "benchmark-cost.json"

    result = CliRunner().invoke(
        main,
        ["benchmark", "--suite", "cost", "--iterations", "1", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "cost"
    assert "cost_readiness" in payload


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")
