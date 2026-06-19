"""Tests for adversarial (differential) verification and cheating-rate measurement.

Research proposition 2 (P0): cut self-grading "cheating rate" (a wrong solution
accepted as correct) from the Fable-5 baseline of 47-74% to <10% by replacing
naive happy-path self-checks with execution-grounded adversarial verification.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main

# A subtly wrong is_palindrome: forgets to strip non-alphanumeric characters.
# It still passes the trivial happy-path example "aba" but fails real cases.
BUGGY_PALINDROME_EDGE = (
    "def is_palindrome(s):\n"
    "    t = s.lower()\n"
    "    return t == t[::-1]\n"
)

# A blatantly wrong is_palindrome that fails even the happy-path example.
BUGGY_PALINDROME_OBVIOUS = "def is_palindrome(s):\n    return False\n"

CORRECT_PALINDROME = (
    "def is_palindrome(s):\n"
    "    t = ''.join(c.lower() for c in s if c.isalnum())\n"
    "    return t == t[::-1]\n"
)


def test_reference_solutions_pass_objective_grader():
    """The verifier's own oracle must itself be correct."""
    from src.adversarial_verification import REFERENCE_SOLUTIONS
    from src.capability_tasks import get_task, grade_code

    for task_id, code in REFERENCE_SOLUTIONS.items():
        result = grade_code(get_task(task_id), code)
        assert result["status"] == "pass", f"reference for {task_id} is not correct"


def test_adversarial_verifier_accepts_correct_solution():
    from src.adversarial_verification import adversarial_verify

    verdict = adversarial_verify("is_palindrome", CORRECT_PALINDROME, trials=200, seed=0)

    assert verdict["accepted"] is True
    assert verdict["counterexample"] is None


def test_adversarial_verifier_rejects_edge_case_bug_with_counterexample():
    from src.adversarial_verification import adversarial_verify

    verdict = adversarial_verify("is_palindrome", BUGGY_PALINDROME_EDGE, trials=200, seed=0)

    assert verdict["accepted"] is False
    assert verdict["counterexample"] is not None


def test_naive_verifier_misses_edge_case_bug_that_adversarial_catches():
    """The crux: a happy-path-passing bug fools naive but not adversarial."""
    from src.adversarial_verification import adversarial_verify, naive_verify

    assert naive_verify("is_palindrome", BUGGY_PALINDROME_EDGE) is True
    assert adversarial_verify("is_palindrome", BUGGY_PALINDROME_EDGE, seed=0)["accepted"] is False


def test_naive_verifier_rejects_obvious_bug():
    from src.adversarial_verification import naive_verify

    assert naive_verify("is_palindrome", BUGGY_PALINDROME_OBVIOUS) is False


def test_measure_cheating_rate_counts_false_accepts():
    from src.adversarial_verification import CandidateSolution, measure_cheating_rate

    samples = [
        CandidateSolution("is_palindrome", "correct", CORRECT_PALINDROME, is_correct=True),
        CandidateSolution("is_palindrome", "edge-bug", BUGGY_PALINDROME_EDGE, is_correct=False),
        CandidateSolution(
            "is_palindrome", "obvious-bug", BUGGY_PALINDROME_OBVIOUS, is_correct=False
        ),
    ]

    # A verifier that accepts everything has cheating_rate 1.0 (both wrong accepted).
    report = measure_cheating_rate(samples, verifier=lambda task_id, code: True)

    assert report["wrong"] == 2
    assert report["accepted_wrong"] == 2
    assert report["cheating_rate"] == 1.0


def test_run_adversarial_readiness_drives_cheating_below_10pct():
    from src.adversarial_verification import run_adversarial_readiness

    result = run_adversarial_readiness()

    assert result["naive"]["cheating_rate"] >= 0.3
    assert result["adversarial"]["cheating_rate"] <= 0.10
    assert result["adversarial"]["cheating_rate"] < result["naive"]["cheating_rate"]
    assert result["adversarial"]["false_reject_rate"] == 0.0
    assert result["status"] == "completed"
    assert _check_status(result, "cheating_rate_below_10pct") == "pass"
    assert result["target_max_cheating_rate"] == 0.10


def test_hardened_generator_catches_red_team_magic_value_escapes():
    """Red-teamed: widened generators reject magic-value escapes that fooled the narrow box."""
    from src.adversarial_verification import RED_TEAM_ESCAPES, adversarial_verify

    assert len(RED_TEAM_ESCAPES) >= 3
    for escape in RED_TEAM_ESCAPES:
        verdict = adversarial_verify(escape.task_id, escape.code, trials=500, seed=0)
        assert verdict["accepted"] is False, f"{escape.label} escaped the hardened verifier"


def test_readiness_reports_red_team_escapes_caught_and_scoping():
    from src.adversarial_verification import run_adversarial_readiness

    result = run_adversarial_readiness()

    assert result["red_team_escapes_caught"] == result["red_team_escapes"]
    assert _check_status(result, "catches_red_team_escapes") == "pass"
    # The claim must be scoped, not stated as impossibility.
    assert any("white-box" in lim for lim in result["limitations"])


def test_rung3_real_agent_outputs_confirm_verifier():
    """Rung-3: on REAL mimo-generated buggy code, adversarial still catches what naive misses."""
    from src.adversarial_verification import (
        load_live_cheating_measurement,
        run_adversarial_readiness,
    )

    live = load_live_cheating_measurement()
    if live is None:
        import pytest

        pytest.skip("no live cheating measurement artifact present")

    assert live["evidence_rung"] == 3
    assert live["real_wrong"] >= 1
    # On the real agent errors, adversarial false-accept stays at/under target.
    assert live["adversarial_cheating_rate"] <= 0.10
    assert live["naive_cheating_rate"] > live["adversarial_cheating_rate"]

    result = run_adversarial_readiness()
    assert result["live_measurement"] is not None
    assert _check_status(result, "real_agent_outputs_confirm_verifier") == "pass"


def test_benchmark_adversarial_suite():
    from src.benchmark import run_benchmark

    result = run_benchmark("adversarial", iterations=1)

    assert result["suite"] == "adversarial"
    assert "adversarial_readiness" in result
    assert result["adversarial_readiness"]["adversarial"]["cheating_rate"] <= 0.10


def test_cli_benchmark_adversarial_suite(tmp_path: Path):
    output_path = tmp_path / "benchmark-adversarial.json"

    result = CliRunner().invoke(
        main,
        ["benchmark", "--suite", "adversarial", "--iterations", "1", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "adversarial"
    assert "adversarial_readiness" in payload


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")
