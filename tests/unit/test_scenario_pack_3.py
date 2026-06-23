"""Tests for the third real-scenario pack (the 30→40 corpus expansion).

Same discrimination discipline as packs 1 and 2: every reference solution passes
its own checks, every flawed solution is caught by a boundary check, and list args
are normalized to a tuple.
"""

from __future__ import annotations

from src.scenario_benchmark import DIMENSIONS, evaluate_scenario
from src.scenario_pack_3 import FLAWED_PACK_3, REFERENCE_PACK_3, SCENARIO_PACK_3


def test_pack_size_and_categories():
    assert len(SCENARIO_PACK_3) == 10
    categories = {s.category for s in SCENARIO_PACK_3}
    assert len(categories) == 10  # every scenario is its own category
    for s in SCENARIO_PACK_3:
        assert s.scenario_id and s.title and s.category and s.ambiguity
        assert len(s.checks) >= 1
        assert all(c.dimension in DIMENSIONS for c in s.checks)


def test_scenario_check_args_normalized_to_tuple():
    for s in SCENARIO_PACK_3:
        for c in s.checks:
            assert isinstance(c.args, tuple)


def test_every_reference_solution_scores_full_marks():
    missing = [s.scenario_id for s in SCENARIO_PACK_3 if s.scenario_id not in REFERENCE_PACK_3]
    assert not missing, f"scenarios without a reference solution: {missing}"
    for s in SCENARIO_PACK_3:
        report = evaluate_scenario(s, REFERENCE_PACK_3[s.scenario_id])
        assert report["overall"] == 1.0, f"{s.scenario_id} reference scored {report['overall']}"


def test_every_flawed_solution_is_discriminated():
    for scenario_id, code in FLAWED_PACK_3.items():
        scenario = next(s for s in SCENARIO_PACK_3 if s.scenario_id == scenario_id)
        report = evaluate_scenario(scenario, code)
        assert report["overall"] < 1.0, f"{scenario_id} flawed solution was not caught"
