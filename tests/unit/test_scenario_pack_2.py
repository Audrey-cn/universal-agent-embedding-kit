"""Tests for the second real-scenario pack (the 10→30 corpus expansion).

The pack shipped without dedicated tests; this validates it end to end: every
reference solution passes its own checks, every flawed solution is caught, and
the ScenarioCheck hashability fix (list args normalized to a tuple) holds.
"""

from __future__ import annotations

from src.scenario_benchmark import DIMENSIONS, evaluate_scenario
from src.scenario_pack_2 import FLAWED_PACK_2, REFERENCE_PACK_2, SCENARIO_PACK_2


def test_pack_size_and_categories():
    assert len(SCENARIO_PACK_2) == 20
    categories = {s.category for s in SCENARIO_PACK_2}
    assert len(categories) == 20  # every scenario is its own category
    for s in SCENARIO_PACK_2:
        assert s.scenario_id and s.title and s.category and s.ambiguity
        assert len(s.checks) >= 1
        assert all(c.dimension in DIMENSIONS for c in s.checks)


def test_scenario_check_args_normalized_to_tuple():
    # Regression guard for the mypy fix: list args at call sites are normalized to
    # a tuple in __post_init__ (expected may still be a list, so the instance is
    # not necessarily hashable — and nothing hashes it).
    for s in SCENARIO_PACK_2:
        for c in s.checks:
            assert isinstance(c.args, tuple)


def test_every_reference_solution_scores_full_marks():
    missing = [s.scenario_id for s in SCENARIO_PACK_2 if s.scenario_id not in REFERENCE_PACK_2]
    assert not missing, f"scenarios without a reference solution: {missing}"
    for s in SCENARIO_PACK_2:
        report = evaluate_scenario(s, REFERENCE_PACK_2[s.scenario_id])
        assert report["overall"] == 1.0, f"{s.scenario_id} reference scored {report['overall']}"


def test_every_flawed_solution_is_discriminated():
    for scenario_id, code in FLAWED_PACK_2.items():
        scenario = next(s for s in SCENARIO_PACK_2 if s.scenario_id == scenario_id)
        report = evaluate_scenario(scenario, code)
        assert report["overall"] < 1.0, f"{scenario_id} flawed solution was not caught"
