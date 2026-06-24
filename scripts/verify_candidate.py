#!/usr/bin/env python
"""Authoritative discrimination gate for a candidate scenario (corpus expansion).

Reads a single candidate-scenario JSON file and runs it through the REAL
``evaluate_scenario`` harness — the same evaluator the benchmark uses — for both
the reference and the flawed solution. Prints a JSON verdict on stdout.

This is the execution-grounded half of "joint verification": red-team agents call
this script rather than re-implementing the scoring logic, so every agent's
numeric verdict comes from the same trusted evaluator. The orchestrator re-runs
the full harness on the merged pack as a final belt-and-suspenders gate.

Candidate JSON shape:
{
  "scenario_id": str, "title": str, "category": str, "ambiguity": str,
  "entrypoint": str,
  "checks": [{"dimension": str, "args": [...], "expected": <any>}, ...],
  "reference_code": str, "flawed_code": str, "flaw_explanation": str
}

Exit code 0 if the candidate PASSES the numeric gate (reference 1.0, flawed <1.0,
no reference load error), 1 otherwise. The verdict JSON is always printed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scenario_benchmark import (  # noqa: E402
    RealScenario,
    ScenarioCheck,
    evaluate_scenario,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: verify_candidate.py <candidate.json>"}))
        return 1
    try:
        data = json.loads(Path(sys.argv[1]).read_text())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"cannot read candidate JSON: {exc}"}))
        return 1

    try:
        entrypoint = data["entrypoint"]
        checks = tuple(
            ScenarioCheck(c["dimension"], entrypoint, c["args"], c["expected"])
            for c in data["checks"]
        )
        scenario = RealScenario(
            scenario_id=data["scenario_id"],
            title=data["title"],
            category=data["category"],
            ambiguity=data["ambiguity"],
            checks=checks,
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"malformed candidate: {exc}"}))
        return 1

    ref = evaluate_scenario(scenario, data["reference_code"])
    flawed = evaluate_scenario(scenario, data["flawed_code"])

    # Illusory flaw: the "flawed" solution actually behaves like the reference, so
    # the corpus would not discriminate it. This is the exact defect that bit pack 2.
    illusory_flaw = flawed["overall"] >= 1.0
    numeric_keep = (
        ref["overall"] == 1.0
        and ref["load_error"] is None
        and flawed["overall"] < 1.0
    )

    verdict = {
        "scenario_id": data["scenario_id"],
        "category": data["category"],
        "entrypoint": entrypoint,
        "ref_overall": ref["overall"],
        "flawed_overall": flawed["overall"],
        "ref_load_error": ref["load_error"],
        "flawed_load_error": flawed["load_error"],
        "ref_dims": ref["dimensions"],
        "flawed_dims": flawed["dimensions"],
        "illusory_flaw": illusory_flaw,
        "numeric_keep": numeric_keep,
        "num_checks": len(checks),
    }
    print(json.dumps(verdict))
    return 0 if numeric_keep else 1


if __name__ == "__main__":
    raise SystemExit(main())
