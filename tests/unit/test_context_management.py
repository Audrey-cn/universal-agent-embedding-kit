"""Tests for adaptive context management vs context rot (proposition 1 / P0).

Models the "dumb zone": with naive linear context only the first ~40% of the
window is reliably usable, so as utilization rises the task-relevant facts get
diluted/pushed out and accuracy collapses. UAEK's adaptive strategy (relevance
filtering + structured compression, bounded by a fidelity floor) keeps the
needed facts accessible up to ~70% utilization.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_naive_degrades_past_dumb_zone():
    from src.context_management import answer_accuracy, build_scenario, naive_context

    scenario = build_scenario(utilization=0.7)
    accessible = naive_context(scenario)
    accuracy = answer_accuracy(accessible, scenario)

    assert accuracy < 0.9  # past ~40% utilization the naive context has rotted


def test_adaptive_beats_naive_at_target_but_loss_is_modeled():
    """Red-teamed: adaptive holds far above naive at 70% util, but NOT a perfect 1.0."""
    from src.context_management import expected_adaptive_accuracy

    adaptive = expected_adaptive_accuracy(0.7)

    assert adaptive["mean"] >= 0.80  # holds well above naive's ~0.57
    assert adaptive["mean"] < 1.0  # lossy compression + relevance error are modeled
    assert adaptive["min"] < adaptive["max"]  # there is a real seed band


def test_adaptive_uses_fewer_tokens_while_retaining_needles():
    """The mechanism: filtering distractors + compression keeps signal cheaper."""
    from src.context_management import adaptive_context, build_scenario, naive_context

    scenario = build_scenario(utilization=0.6)
    naive = naive_context(scenario)
    adaptive = adaptive_context(scenario)

    assert adaptive["tokens_used"] < naive["tokens_used"]
    assert adaptive["needles_retained"] >= naive["needles_retained"]


def test_adaptive_robust_under_adversarial_needle_placement():
    from src.context_management import _naive_accuracy_at, expected_adaptive_accuracy

    naive_adv = _naive_accuracy_at(0.7, adversarial=True)
    adaptive_adv = expected_adaptive_accuracy(0.7, adversarial=True)

    # Clustering needles past the dumb zone hurts naive; adaptive reorders by relevance.
    assert adaptive_adv["mean"] > naive_adv + 0.2


def test_usable_ceiling_is_threshold_sensitive_knife_edge():
    """Red-team finding: the 0.9-threshold ceiling is a knife-edge, not a robust metric."""
    from src.context_management import run_context_rot_readiness

    ceilings = run_context_rot_readiness()["usable_ceilings_by_threshold"]
    # At threshold 0.8 adaptive >> naive; at 0.9 the modeled loss collapses it — proof the
    # single-ceiling claim was an artifact, which is why we report accuracy-at-target instead.
    assert ceilings["threshold_80"]["adaptive"] > ceilings["threshold_80"]["naive"]
    assert ceilings["threshold_90"]["adaptive"] < ceilings["threshold_80"]["adaptive"]


def test_answer_accuracy_is_fraction_of_retained_needles():
    from src.context_management import answer_accuracy, build_scenario

    scenario = build_scenario(utilization=0.5)
    # An empty accessible set answers nothing.
    empty = {"accessible_query_ids": set(), "tokens_used": 0, "needles_retained": 0}
    assert answer_accuracy(empty, scenario) == 0.0


def test_run_context_rot_readiness_fills_dimension_three():
    from src.context_management import run_context_rot_readiness

    result = run_context_rot_readiness()

    assert result["dimension"] == "3_context_utilization"
    assert result["target_utilization"] == 0.70
    assert result["naive"]["accuracy_at_target"] < 0.7
    assert result["adaptive"]["accuracy_at_target"] >= 0.80
    assert result["accuracy_gap_at_target"] >= 0.20
    assert result["status"] == "completed"
    assert _check_status(result, "adaptive_beats_naive_at_target") == "pass"
    assert _check_status(result, "models_compression_and_relevance_loss") == "pass"
    assert _check_status(result, "robust_under_adversarial_placement") == "pass"


def test_rung3_live_retrieval_probe_is_honestly_scoped():
    """Rung-3: a real needle-in-haystack probe validates retrieval, not the adaptive advantage."""
    from src.context_management import load_live_context_measurement, run_context_rot_readiness

    live = load_live_context_measurement()
    if live is None:
        import pytest

        pytest.skip("no live context measurement artifact present")

    assert live["evidence_rung"] == 3
    assert 0.0 <= live["recall_rate"] <= 1.0
    # The caveat must state this does not prove the adaptive advantage.
    assert any("not" in c.lower() and "adaptive" in c.lower() for c in live["red_team_caveats"])

    result = run_context_rot_readiness()
    assert result["live_measurement"] is not None


def test_benchmark_context_suite():
    from src.benchmark import run_benchmark

    result = run_benchmark("context", iterations=1)

    assert result["suite"] == "context"
    assert "context_rot_readiness" in result
    assert result["context_rot_readiness"]["adaptive"]["accuracy_at_target"] >= 0.80


def test_cli_benchmark_context_suite(tmp_path: Path):
    output_path = tmp_path / "benchmark-context.json"

    result = CliRunner().invoke(
        main,
        ["benchmark", "--suite", "context", "--iterations", "1", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "context"
    assert "context_rot_readiness" in payload


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")
