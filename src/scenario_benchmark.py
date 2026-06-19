"""Real-scenario benchmark — research proposition 4.

Self-contained coding tasks ("write two_sum") do not reflect real sessions:
multi-step dependencies, ambiguous requirements, and — the part single pass/fail
checks miss entirely — *not breaking existing behavior* while adding a feature.

This suite scores a solution across several dimensions (correctness,
completeness/no-regression, context retention, robustness). Its headline result
is discriminative: a solution that ships the requested feature (correctness
1.0) but regresses an existing case is caught here, where a correctness-only
gate would pass it.

Scope is honest: this is a small *seed* of scenarios with a deterministic
auto-grader, the framework for real-scenario evaluation — not yet the proposal's
100+ live multi-hour sessions. The graders are black-box, so "context
retention" is checked via cross-call consistency rather than introspection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DIMENSIONS = ("correctness", "completeness", "context_retention", "robustness")
LIVE_MEASUREMENT_PATH = Path("benchmarks/results/scenario-live-measurement.json")


def load_live_scenario_measurement(
    path: Path | str = LIVE_MEASUREMENT_PATH,
) -> dict[str, Any] | None:
    """Load the rung-3 real-agent scenario measurement artifact, if present."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class ScenarioCheck:
    dimension: str
    entrypoint: str
    args: tuple[Any, ...]
    expected: Any


class ReuseProbe:
    """A genuine dependency-reuse test (red-team hardening).

    Black-box equality checks can't tell whether ``caller`` actually reused
    ``dependency`` or just reimplemented it inline. This probe REPLACES the
    dependency in the solution's namespace with a valid-but-different
    implementation and asserts ``caller``'s output CHANGES accordingly. Genuine
    reuse tracks the swap; an inline reimplementation does not.
    """

    def __init__(self, caller: str, dependency: str, swapped_code: str, probe_input: Any):
        self.caller = caller
        self.dependency = dependency
        self.swapped_code = swapped_code
        self.probe_input = probe_input


@dataclass(frozen=True)
class RealScenario:
    scenario_id: str
    title: str
    category: str
    ambiguity: str
    checks: tuple[ScenarioCheck, ...]
    reuse_probe: ReuseProbe | None = None


SCENARIOS: tuple[RealScenario, ...] = (
    RealScenario(
        scenario_id="discount_feature",
        title="Add a HALF discount code without breaking SAVE10",
        category="feature-add-with-regression-risk",
        ambiguity="Unknown codes are unspecified; assume no discount (return full price).",
        checks=(
            ScenarioCheck("correctness", "discount", (100, "HALF"), 50.0),
            ScenarioCheck("correctness", "discount", (200, "HALF"), 100.0),
            ScenarioCheck("completeness", "discount", (100, "SAVE10"), 90.0),
            ScenarioCheck("completeness", "discount", (50, "SAVE10"), 45.0),
            ScenarioCheck("robustness", "discount", (100, "UNKNOWN"), 100),
            ScenarioCheck("robustness", "discount", (0, "HALF"), 0.0),
        ),
    ),
    RealScenario(
        scenario_id="running_total",
        title="Two-step: parse amounts, then a running total that reuses the parse",
        category="multi-step-dependency",
        ambiguity="Blank entries between commas are unspecified; assume they are skipped.",
        checks=(
            ScenarioCheck("correctness", "running_total", ("1,2,3",), [1, 3, 6]),
            ScenarioCheck("correctness", "running_total", ("5",), [5]),
            ScenarioCheck("completeness", "running_total", ("",), []),
            ScenarioCheck("robustness", "running_total", ("-1,1",), [-1, 0]),
        ),
        # Genuine reuse test: swap parse_amounts for a valid variant that doubles
        # each amount. Real reuse makes running_total's output change; an inline
        # reimplementation ignores the swap and is flagged as non-reuse.
        reuse_probe=ReuseProbe(
            caller="running_total",
            dependency="parse_amounts",
            swapped_code=(
                "def parse_amounts(s):\n"
                "    if not s.strip():\n        return []\n"
                "    return [2 * int(x) for x in s.split(',') if x.strip() != '']\n"
            ),
            probe_input="3,4",
        ),
    ),
)

_SCENARIOS_BY_ID = {scenario.scenario_id: scenario for scenario in SCENARIOS}

REFERENCE_SOLUTIONS: dict[str, str] = {
    "discount_feature": (
        "def discount(price, code):\n"
        "    if code == 'SAVE10':\n"
        "        return price * 0.9\n"
        "    if code == 'HALF':\n"
        "        return price * 0.5\n"
        "    return price\n"
    ),
    "running_total": (
        "def parse_amounts(s):\n"
        "    if not s.strip():\n"
        "        return []\n"
        "    return [int(x) for x in s.split(',') if x.strip() != '']\n"
        "def running_total(s):\n"
        "    out, total = [], 0\n"
        "    for amount in parse_amounts(s):\n"
        "        total += amount\n"
        "        out.append(total)\n"
        "    return out\n"
    ),
}

# Per-scenario flawed solutions (de-circularized: one per scenario, each a
# different real failure mode).
FLAWED_SOLUTIONS: dict[str, str] = {
    # Ships the requested HALF feature but regresses SAVE10.
    "discount_feature": (
        "def discount(price, code):\n"
        "    if code == 'HALF':\n"
        "        return price * 0.5\n"
        "    return price\n"
    ),
    # Passes every black-box output check but REIMPLEMENTS parsing inline instead
    # of reusing parse_amounts — caught only by the reuse probe.
    "running_total": (
        "def parse_amounts(s):\n"
        "    if not s.strip():\n        return []\n"
        "    return [int(x) for x in s.split(',') if x.strip() != '']\n"
        "def running_total(s):\n"
        "    parts = [int(x) for x in s.split(',') if x.strip() != ''] if s.strip() else []\n"
        "    out, total = [], 0\n"
        "    for amount in parts:\n"
        "        total += amount\n        out.append(total)\n"
        "    return out\n"
    ),
}


def get_scenario(scenario_id: str) -> RealScenario:
    if scenario_id not in _SCENARIOS_BY_ID:
        raise KeyError(f"unknown scenario: {scenario_id}")
    return _SCENARIOS_BY_ID[scenario_id]


def _reuse_detected(namespace: dict[str, Any], probe: ReuseProbe) -> bool:
    """True iff swapping the dependency changes the caller's output (genuine reuse)."""
    caller = namespace.get(probe.caller)
    if not callable(caller):
        return False
    try:
        baseline = caller(probe.probe_input)
    except Exception:  # noqa: BLE001
        return False
    # Swap the dependency in-place with a valid-but-different implementation.
    exec(compile(probe.swapped_code, "<reuse-probe>", "exec"), namespace)  # noqa: S102
    swapped_caller = namespace.get(probe.caller)
    if not callable(swapped_caller):
        return False
    try:
        swapped = swapped_caller(probe.probe_input)
    except Exception:  # noqa: BLE001
        return False
    return bool(swapped != baseline)


def evaluate_scenario(scenario: RealScenario, code: str) -> dict[str, Any]:
    """Score a solution across the scenario's dimensions."""
    namespace: dict[str, Any] = {}
    load_error: str | None = None
    try:
        exec(compile(code, f"<{scenario.scenario_id}>", "exec"), namespace)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        load_error = f"{type(exc).__name__}: {exc}"

    per_dimension_pass: dict[str, int] = {}
    per_dimension_total: dict[str, int] = {}
    for check in scenario.checks:
        per_dimension_total[check.dimension] = per_dimension_total.get(check.dimension, 0) + 1
        passed = False
        if load_error is None:
            fn = namespace.get(check.entrypoint)
            if callable(fn):
                try:
                    passed = fn(*check.args) == check.expected
                except Exception:  # noqa: BLE001
                    passed = False
        if passed:
            per_dimension_pass[check.dimension] = per_dimension_pass.get(check.dimension, 0) + 1

    # Genuine context_retention: the reuse probe (swap the dependency, require the
    # caller's output to track it). An inline reimplementation fails this.
    if scenario.reuse_probe is not None:
        per_dimension_total["context_retention"] = per_dimension_total.get(
            "context_retention", 0
        ) + 1
        if load_error is None and _reuse_detected(namespace, scenario.reuse_probe):
            per_dimension_pass["context_retention"] = per_dimension_pass.get(
                "context_retention", 0
            ) + 1

    dimensions = {
        dim: round(per_dimension_pass.get(dim, 0) / total, 4)
        for dim, total in per_dimension_total.items()
    }
    total_checks = sum(per_dimension_total.values())
    total_passed = sum(per_dimension_pass.values())
    return {
        "scenario_id": scenario.scenario_id,
        "category": scenario.category,
        "dimensions": dimensions,
        "overall": round(total_passed / total_checks, 4) if total_checks else 0.0,
        "checks_passed": total_passed,
        "checks_total": total_checks,
        "load_error": load_error,
    }


def run_scenario_readiness() -> dict[str, Any]:
    """Demonstrate multi-dimensional discrimination on the seed scenarios."""
    reference_reports = {
        scenario.scenario_id: evaluate_scenario(scenario, REFERENCE_SOLUTIONS[scenario.scenario_id])
        for scenario in SCENARIOS
    }
    reference_overall = round(
        sum(r["overall"] for r in reference_reports.values()) / len(reference_reports), 4
    )

    # Red-teamed: TWO independent flawed solutions (de-circularized), each a
    # different real failure mode caught by a different dimension.
    regression = evaluate_scenario(
        get_scenario("discount_feature"), FLAWED_SOLUTIONS["discount_feature"]
    )
    nonreuse = evaluate_scenario(
        get_scenario("running_total"), FLAWED_SOLUTIONS["running_total"]
    )
    flawed_overall = regression["overall"]

    # The regression is "hidden" from a correctness-only gate.
    flags_hidden_regression = (
        regression["dimensions"].get("correctness") == 1.0
        and regression["dimensions"].get("completeness", 1.0) < 1.0
    )
    # The non-reuse solution passes every black-box output check but fails the
    # genuine reuse probe — proving context_retention is no longer hollow.
    catches_nonreuse = (
        nonreuse["dimensions"].get("correctness") == 1.0
        and nonreuse["dimensions"].get("context_retention", 1.0) < 1.0
    )

    categories = sorted({scenario.category for scenario in SCENARIOS})
    dimensions_covered = sorted(
        {check.dimension for scenario in SCENARIOS for check in scenario.checks}
        | ({"context_retention"} if any(s.reuse_probe for s in SCENARIOS) else set())
    )

    checks = [
        {
            "id": "reference_full_marks",
            "required": True,
            "status": "pass" if reference_overall == 1.0 else "fail",
            "evidence": f"reference solutions score {reference_overall:.0%} overall",
        },
        {
            "id": "multidimensional_discrimination",
            "required": True,
            "status": (
                "pass" if flawed_overall < reference_overall and flags_hidden_regression else "fail"
            ),
            "evidence": (
                f"feature-complete but regressing solution scores correctness "
                f"{regression['dimensions'].get('correctness', 0):.0%} but completeness "
                f"{regression['dimensions'].get('completeness', 0):.0%} (overall "
                f"{flawed_overall:.0%})"
            ),
        },
        {
            "id": "context_retention_requires_real_reuse",
            "required": True,
            "status": "pass" if catches_nonreuse else "fail",
            "evidence": (
                "a solution that passes all black-box output checks but reimplements the "
                "dependency inline is caught by the reuse probe (context_retention "
                f"{nonreuse['dimensions'].get('context_retention', 1.0):.0%})"
            ),
        },
    ]

    # Rung-3: real agent solutions scored by the same rubric, if available.
    live = load_live_scenario_measurement()
    if live is not None:
        live_runs = live.get("runs", [])
        all_scored = bool(live_runs) and all(r.get("overall") is not None for r in live_runs)
        checks.append(
            {
                "id": "real_agent_solutions_scored_live",
                "required": False,
                "status": "pass" if all_scored else "fail",
                "evidence": (
                    f"rung-3: {len(live_runs)} real agent solutions scored multi-dimensionally "
                    f"(reuse probe verified on live code: "
                    f"{live.get('context_retention_verified_on_real_code')})"
                ),
            }
        )

    all_pass = all(check["status"] == "pass" for check in checks)

    return {
        "status": "completed" if all_pass else "partial",
        "dimension": "4_real_scenario_benchmark",
        "scenario_count": len(SCENARIOS),
        "flawed_solution_count": len(FLAWED_SOLUTIONS),
        "live_measurement": live,
        "categories": categories,
        "dimensions_covered": dimensions_covered,
        "reference_overall": reference_overall,
        "flawed_overall": flawed_overall,
        "flawed_report": regression,
        "nonreuse_report": nonreuse,
        "flags_hidden_regression": flags_hidden_regression,
        "catches_nonreuse": catches_nonreuse,
        "checks": checks,
        "resolved_findings": (
            ["W2.3_BENCHMARK_REALISM", "F030_MULTIDIMENSIONAL_SCENARIO_BENCHMARK"]
            if all_pass
            else []
        ),
        "limitations": [
            "Seed of scenarios with a deterministic auto-grader — the framework for "
            "real-scenario evaluation, not yet the proposal's 100+ live multi-hour sessions.",
            "Red-team hardened: context_retention now uses a dependency-SWAP reuse probe (proven "
            "to catch an inline reimplementation that passes every black-box check); each "
            "scenario has its own flawed solution so discrimination is no longer a single "
            "circular foil.",
            "Ambiguity is still encoded as a documented assumption per scenario; it does not yet "
            "test an agent's clarifying-question behavior on UNdocumented ambiguity.",
            "Framework is ready to drive live providers via the capability adapter; expanding "
            "to a real 100+ scenario corpus is open work.",
        ],
    }
