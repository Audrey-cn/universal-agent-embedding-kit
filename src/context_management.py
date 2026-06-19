"""Adaptive context management vs context rot — research proposition 1 (P0).

The Fable-5 analysis documents a "dumb zone": with a naive linear context, only
the first ~40% of the window is reliably usable, so as utilization rises the
task-relevant facts get diluted or pushed out and accuracy collapses.

This module measures, on a deterministic needle-in-haystack retrieval scenario,
the *usable utilization ceiling* (highest window-fill fraction at which accuracy
stays >= 0.9) for two context strategies:

* ``naive_context`` — linear context; only the first ``NAIVE_USABLE_FRACTION``
  of the window is reliable.
* ``adaptive_context`` — relevance filtering (drop distractors) + structured
  compression, which extends the reliable zone to ``ADAPTIVE_USABLE_FRACTION``.
  It is bounded by a fidelity floor (a fact cannot be compressed below
  ``FIDELITY_TOKENS`` without being lost), so it tops out at the ~70% target
  rather than claiming a perfect window.

This is a deterministic information-retention benchmark of the context layer,
not a live-LLM run; the ~40% naive threshold is cited from the proposal, and the
adaptive result is computed from the implemented strategy.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIVE_MEASUREMENT_PATH = Path("benchmarks/results/context-live-measurement.json")


def load_live_context_measurement(
    path: Path | str = LIVE_MEASUREMENT_PATH,
) -> dict[str, Any] | None:
    """Load the rung-3 real needle-in-haystack retrieval artifact, if present."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None

WINDOW_TOKENS = 2000
FIDELITY_TOKENS = 40  # tokens needed to faithfully retain one fact (compression floor)
NAIVE_USABLE_FRACTION = 0.40  # documented linear-context "dumb zone" (proposal / Fable-5)
ADAPTIVE_USABLE_FRACTION = 0.70  # target reliable zone via structured context
NEEDLE_FRACTION = 0.8  # share of context items that carry a needed fact
ACCURACY_THRESHOLD = 0.9
SWEEP_LEVELS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
TARGET_UTILIZATION = 0.70

# Red-team hardening: a first version modeled adaptive compression as LOSSLESS
# (every retained needle perfectly answerable), which inflated the ceiling to 90%
# and made it a knife-edge artifact of the ADAPTIVE_USABLE_FRACTION constant. Real
# compression is lossy and relevance filtering is imperfect, so we now model both
# stochastically and report expected accuracy at the target utilization with a
# seed confidence band — not a single deterministic ceiling.
FIDELITY_RECALL = 0.90  # P(a compressed needle is still answerable)
RELEVANCE_RECALL = 0.95  # P(a needle is kept, not misclassified as a distractor)
SEEDS = tuple(range(24))


@dataclass(frozen=True)
class ContextItem:
    item_id: int
    offset: int  # token offset of this item within the linear context
    is_needle: bool
    query_id: int | None


@dataclass(frozen=True)
class ContextScenario:
    utilization: float
    items: tuple[ContextItem, ...]
    query_ids: frozenset[int]


def build_scenario(utilization: float, adversarial_placement: bool = False) -> ContextScenario:
    """Build a needle-in-haystack context filling ``utilization`` of the window.

    With ``adversarial_placement`` the needles are clustered at the END of the
    context (past the naive reliable zone / in the lost-in-the-middle band) —
    a worst case for naive linear context.
    """
    u = max(0.0, min(1.0, float(utilization)))
    content_tokens = round(u * WINDOW_TOKENS)
    num_items = max(1, content_tokens // FIDELITY_TOKENS)
    num_needles = max(1, round(num_items * NEEDLE_FRACTION))

    if adversarial_placement:
        needle_slots = set(range(num_items - num_needles, num_items))
    else:
        # Evenly distribute needle slots across the linear context.
        needle_slots = {(i * num_items) // num_needles for i in range(num_needles)}
    items: list[ContextItem] = []
    next_query = 0
    for index in range(num_items):
        is_needle = index in needle_slots
        query_id = None
        if is_needle:
            query_id = next_query
            next_query += 1
        items.append(ContextItem(index, index * FIDELITY_TOKENS, is_needle, query_id))

    query_ids = frozenset(item.query_id for item in items if item.query_id is not None)
    return ContextScenario(u, tuple(items), query_ids)


def naive_context(scenario: ContextScenario) -> dict[str, Any]:
    """Linear context: only the first NAIVE_USABLE_FRACTION of the window is reliable."""
    reliable_limit = NAIVE_USABLE_FRACTION * WINDOW_TOKENS
    accessible = {
        item.query_id
        for item in scenario.items
        if item.is_needle and item.offset < reliable_limit
    }
    tokens_used = sum(FIDELITY_TOKENS for _ in scenario.items)  # keeps raw context
    return {
        "accessible_query_ids": accessible,
        "tokens_used": tokens_used,
        "needles_retained": len(accessible),
    }


def adaptive_context(scenario: ContextScenario, seed: int | None = None) -> dict[str, Any]:
    """Relevance-filter distractors + lossy structured compression.

    Red-teamed: a needle is only kept if relevance filtering correctly flags it
    (``RELEVANCE_RECALL``) and only answerable if its compression preserved the
    fact (``FIDELITY_RECALL``). With ``seed=None`` it runs deterministically at
    the expected value (no stochastic loss) for the token-efficiency checks; with
    a seed it samples the lossy behavior.
    """
    needles = [item for item in scenario.items if item.is_needle]
    capacity = int(ADAPTIVE_USABLE_FRACTION * WINDOW_TOKENS // FIDELITY_TOKENS)

    if seed is None:
        kept = needles[:capacity]
        accessible = {item.query_id for item in kept}
        return {
            "accessible_query_ids": accessible,
            "tokens_used": len(kept) * FIDELITY_TOKENS,
            "needles_retained": len(kept),
        }

    rng = random.Random(seed)
    kept = [item for item in needles if rng.random() < RELEVANCE_RECALL][:capacity]
    accessible = {item.query_id for item in kept if rng.random() < FIDELITY_RECALL}
    return {
        "accessible_query_ids": accessible,
        "tokens_used": len(kept) * FIDELITY_TOKENS,
        "needles_retained": len(accessible),
    }


def answer_accuracy(selection: dict[str, Any], scenario: ContextScenario) -> float:
    """Fraction of queries whose supporting needle survived into the context."""
    if not scenario.query_ids:
        return 0.0
    answered = selection["accessible_query_ids"] & scenario.query_ids
    return round(len(answered) / len(scenario.query_ids), 4)


_STRATEGIES = {"naive": naive_context, "adaptive": adaptive_context}


def measure_utilization_curve(
    strategy: str, levels: tuple[float, ...] = SWEEP_LEVELS
) -> list[dict[str, Any]]:
    """Accuracy at each utilization level for a strategy."""
    if strategy not in _STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    select = _STRATEGIES[strategy]
    curve: list[dict[str, Any]] = []
    for level in levels:
        scenario = build_scenario(level)
        selection = select(scenario)
        curve.append(
            {
                "utilization": round(level, 4),
                "accuracy": answer_accuracy(selection, scenario),
                "needles_retained": selection["needles_retained"],
                "tokens_used": selection["tokens_used"],
            }
        )
    return curve


def usable_utilization_ceiling(
    curve: list[dict[str, Any]], threshold: float = ACCURACY_THRESHOLD
) -> float:
    """Highest utilization level whose accuracy is still >= threshold."""
    passing = [point["utilization"] for point in curve if point["accuracy"] >= threshold]
    return round(max(passing), 4) if passing else 0.0


def _naive_accuracy_at(utilization: float, adversarial: bool = False) -> float:
    scenario = build_scenario(utilization, adversarial_placement=adversarial)
    return answer_accuracy(naive_context(scenario), scenario)


def expected_adaptive_accuracy(
    utilization: float, adversarial: bool = False
) -> dict[str, float]:
    """Mean/min/max adaptive accuracy over seeds, accounting for lossy compression."""
    scenario = build_scenario(utilization, adversarial_placement=adversarial)
    samples = [
        answer_accuracy(adaptive_context(scenario, seed=seed), scenario) for seed in SEEDS
    ]
    return {
        "mean": round(statistics.mean(samples), 4),
        "min": round(min(samples), 4),
        "max": round(max(samples), 4),
    }


def run_context_rot_readiness() -> dict[str, Any]:
    """Red-teamed dimension-3 readiness.

    A first version modeled adaptive compression as lossless and reported a 90%
    "usable ceiling" that just tracked the ADAPTIVE_USABLE_FRACTION constant. The
    honest metric is the EXPECTED accuracy at the 70% target utilization (with a
    seed confidence band, accounting for ~10% compression loss + ~5% relevance
    misclassification), compared to naive — plus a worst-case adversarial-needle-
    placement check. The single 0.9-threshold ceiling is reported only as a
    sensitivity aside, since it is a knife-edge artifact.
    """
    naive_at_target = _naive_accuracy_at(TARGET_UTILIZATION)
    adaptive_at_target = expected_adaptive_accuracy(TARGET_UTILIZATION)
    gap = round(adaptive_at_target["mean"] - naive_at_target, 4)

    naive_adv = _naive_accuracy_at(TARGET_UTILIZATION, adversarial=True)
    adaptive_adv = expected_adaptive_accuracy(TARGET_UTILIZATION, adversarial=True)

    # Sensitivity: usable ceiling depends heavily on the threshold, so report both.
    naive_curve = measure_utilization_curve("naive")
    adaptive_mean_curve = [
        {"utilization": u, "accuracy": expected_adaptive_accuracy(u)["mean"]}
        for u in SWEEP_LEVELS
    ]
    ceilings = {
        f"threshold_{int(t * 100)}": {
            "naive": usable_utilization_ceiling(naive_curve, t),
            "adaptive": usable_utilization_ceiling(adaptive_mean_curve, t),
        }
        for t in (0.8, 0.9)
    }

    checks = [
        {
            "id": "adaptive_beats_naive_at_target",
            "required": True,
            "status": "pass" if gap >= 0.20 else "fail",
            "evidence": (
                f"at {TARGET_UTILIZATION:.0%} util adaptive {adaptive_at_target['mean']:.0%} "
                f"(band {adaptive_at_target['min']:.0%}-{adaptive_at_target['max']:.0%}) vs naive "
                f"{naive_at_target:.0%} (+{gap:.0%})"
            ),
        },
        {
            "id": "models_compression_and_relevance_loss",
            "required": True,
            "status": "pass" if adaptive_at_target["mean"] < 1.0 else "fail",
            "evidence": (
                f"adaptive accuracy {adaptive_at_target['mean']:.0%} < 100%: lossy compression "
                f"(recall {FIDELITY_RECALL:.0%}) + relevance error ({1 - RELEVANCE_RECALL:.0%}) "
                "are modeled, not assumed away"
            ),
        },
        {
            "id": "robust_under_adversarial_placement",
            "required": True,
            "status": "pass" if adaptive_adv["mean"] > naive_adv + 0.20 else "fail",
            "evidence": (
                f"needles clustered past the dumb zone: adaptive {adaptive_adv['mean']:.0%} vs "
                f"naive {naive_adv:.0%}"
            ),
        },
    ]

    # Rung-3: a real needle-in-haystack probe on a live model, if available. NOTE
    # this validates that real retrieval is tractable at scale; it does NOT prove
    # the adaptive-vs-naive advantage (that comparison lives inside the model).
    live = load_live_context_measurement()
    if live is not None:
        checks.append(
            {
                "id": "live_retrieval_probe",
                "required": False,
                "status": "pass" if float(live.get("recall_rate", 0.0)) >= 0.90 else "fail",
                "evidence": (
                    f"rung-3 real mimo needle-in-haystack: recall {live.get('recall_rate', 0):.0%} "
                    f"({live.get('recalled')}/{live.get('needles')}) over "
                    f"{live.get('context_tokens')} tokens — validates retrieval is tractable, "
                    "not the adaptive advantage"
                ),
            }
        )

    all_pass = all(check["status"] == "pass" for check in checks)

    return {
        "status": "completed" if all_pass else "partial",
        "dimension": "3_context_utilization",
        "target_utilization": TARGET_UTILIZATION,
        "window_tokens": WINDOW_TOKENS,
        "fidelity_recall": FIDELITY_RECALL,
        "relevance_recall": RELEVANCE_RECALL,
        "live_measurement": live,
        "naive": {
            "accuracy_at_target": naive_at_target,
            "accuracy_at_target_adversarial": naive_adv,
        },
        "adaptive": {
            "accuracy_at_target": adaptive_at_target["mean"],
            "accuracy_at_target_band": [adaptive_at_target["min"], adaptive_at_target["max"]],
            "accuracy_at_target_adversarial": adaptive_adv["mean"],
        },
        "accuracy_gap_at_target": gap,
        "usable_ceilings_by_threshold": ceilings,
        "checks": checks,
        "resolved_findings": (
            ["W4.1_CONTEXT_ROT", "F028_ADAPTIVE_CONTEXT_MANAGEMENT"] if all_pass else []
        ),
        "limitations": [
            "Deterministic information-retention benchmark of the context layer, not a live-LLM "
            "comprehension run.",
            "The ~40% naive reliable fraction is the documented Fable-5/LLM dumb-zone, a stated "
            "baseline rather than re-measured.",
            "Compression loss (recall) and relevance-misclassification rates are modeled "
            "parameters; the headline is expected accuracy at the 70% target with a seed band, "
            "not a single deterministic ceiling (which the red-team showed is a threshold "
            "knife-edge).",
        ],
    }
