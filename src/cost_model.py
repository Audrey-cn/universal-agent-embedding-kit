"""Cost model — research proposition 3 (cost / performance).

Models an agentic multi-turn session under Anthropic-style token pricing and
shows that the cost/performance trade-off Fable 5 paid (slower, ~2x cost) is
recoverable — and then some — mainly through prompt/KV cache reuse of the stable
prefix (system prompt + tool definitions + conversation history).

Pricing multipliers (relative to base input price = 1.0), matching documented
Anthropic prompt-caching economics:
* uncached input  : 1.00x
* cache write      : 1.25x  (one-time, when a token first enters the cached prefix)
* cache read       : 0.10x  (every subsequent turn the token is reused)
* output           : 5.00x

Real agent loops reuse a large stable prefix every turn, so cache hit rates of
70-90%+ are typical — which is why the achievable cost reduction is well past the
proposal's conservative -50% target.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIVE_MEASUREMENT_PATH = Path("benchmarks/results/cost-live-measurement.json")

INPUT_PRICE = 1.00
CACHE_WRITE_MULT = 1.25  # 5-minute cache write premium
CACHE_WRITE_1H_MULT = 2.00  # 1-hour cache write premium (Anthropic extended TTL)
CACHE_READ_MULT = 0.10
OUTPUT_MULT = 5.00
# Effort routing: simple turns are routed to a cheaper/low-effort path, trimming
# output compute. Documented as a routing factor, not a free lunch.
EFFORT_OUTPUT_FACTOR = {"simple": 0.30, "complex": 1.00}

PROPOSAL_TARGET = 0.50  # the original RESEARCH_PROPOSAL cost-reduction target
STRETCH_TARGET = 0.70  # raised target justified by observed 70-90% cache hit rates
# Realistic fraction of turns whose cached prefix expires past the 5-min TTL
# (human-paced / tool-heavy agent turns). Used for the honest headline number.
REALISTIC_MISS_RATE = 0.20


@dataclass(frozen=True)
class AgentTurn:
    new_input_tokens: int
    output_tokens: int
    complexity: str  # "simple" | "complex"


@dataclass(frozen=True)
class AgentWorkload:
    stable_prefix_tokens: int
    turns: tuple[AgentTurn, ...]


def build_agent_workload(
    stable_prefix_tokens: int = 4000,
    num_turns: int = 10,
    new_input_tokens: int = 250,
    output_tokens: int = 450,
) -> AgentWorkload:
    """A representative agent session: large stable prefix, many turns.

    Alternates simple/complex turns so effort routing has something to trim.
    """
    turns = tuple(
        AgentTurn(
            new_input_tokens=new_input_tokens,
            output_tokens=output_tokens,
            complexity="simple" if index % 2 == 0 else "complex",
        )
        for index in range(num_turns)
    )
    return AgentWorkload(stable_prefix_tokens=stable_prefix_tokens, turns=turns)


def baseline_cost(workload: AgentWorkload) -> dict[str, Any]:
    """No caching, full effort: the entire context is re-charged every turn."""
    context = workload.stable_prefix_tokens
    input_cost = 0.0
    output_cost = 0.0
    total_input_tokens = 0
    for turn in workload.turns:
        context_for_turn = context + turn.new_input_tokens
        input_cost += context_for_turn * INPUT_PRICE
        output_cost += turn.output_tokens * OUTPUT_MULT * INPUT_PRICE
        total_input_tokens += context_for_turn
        context += turn.new_input_tokens + turn.output_tokens
    return {
        "input_cost": round(input_cost, 2),
        "output_cost": round(output_cost, 2),
        "total_cost": round(input_cost + output_cost, 2),
        "total_input_tokens": total_input_tokens,
        "cache_read_tokens": 0,
        "cache_hit_rate": 0.0,
    }


def uaek_cost(
    workload: AgentWorkload,
    use_effort_routing: bool = True,
    cache_miss_rate: float = 0.0,
    long_ttl_stable_prefix: bool = False,
) -> dict[str, Any]:
    """Prompt caching + effort routing, with a TTL-expiry miss model.

    A token is written to the cache once (1.25x) when it first enters the
    context, then read (0.10x) on every later turn — UNLESS the cache has
    expired (Anthropic's default prompt-cache TTL is 5 minutes). On an expired
    turn the whole live prefix must be re-written at 1.25x instead of read at
    0.10x. ``cache_miss_rate`` is the fraction of turns whose prefix expired
    (e.g. human-paced or tool-heavy turns crossing the TTL); misses are spread
    evenly across the session.
    """
    miss_rate = max(0.0, min(1.0, float(cache_miss_rate)))
    cached_tokens = 0  # tokens already in the cached prefix at the start of a turn
    input_cost = 0.0
    write_cost = 0.0
    output_cost = 0.0
    cache_read_tokens = 0
    cache_miss_tokens = 0
    total_input_tokens = 0
    miss_accumulator = 0.0

    # The stable prefix (system + tools) is written once up front. Improvement:
    # put it on the 1-hour cache tier so it survives the gaps that expire the
    # 5-minute rolling history — at a higher one-time write premium.
    stable = workload.stable_prefix_tokens
    stable_write_mult = CACHE_WRITE_1H_MULT if long_ttl_stable_prefix else CACHE_WRITE_MULT
    write_cost += stable * stable_write_mult * INPUT_PRICE
    cached_tokens += stable

    for turn in workload.turns:
        # Decide if this turn's cached prefix has expired (spread evenly).
        miss_accumulator += miss_rate
        expired = miss_accumulator >= 1.0
        if expired:
            miss_accumulator -= 1.0
            if long_ttl_stable_prefix:
                # Only the 5-min rolling history expired; the 1-hour stable prefix
                # survives and is still read at 0.10x.
                rolling = cached_tokens - stable
                input_cost += stable * CACHE_READ_MULT * INPUT_PRICE
                input_cost += rolling * CACHE_WRITE_MULT * INPUT_PRICE
                cache_read_tokens += stable
                cache_miss_tokens += rolling
            else:
                # TTL expiry: the whole live prefix must be re-written, not read.
                input_cost += cached_tokens * CACHE_WRITE_MULT * INPUT_PRICE
                cache_miss_tokens += cached_tokens
        else:
            input_cost += cached_tokens * CACHE_READ_MULT * INPUT_PRICE
            cache_read_tokens += cached_tokens
        total_input_tokens += cached_tokens + turn.new_input_tokens
        # New input enters context this turn: write once for future reuse.
        write_cost += turn.new_input_tokens * CACHE_WRITE_MULT * INPUT_PRICE
        # Output, possibly routed to a cheaper path for simple turns.
        factor = EFFORT_OUTPUT_FACTOR[turn.complexity] if use_effort_routing else 1.0
        output_cost += turn.output_tokens * OUTPUT_MULT * INPUT_PRICE * factor
        # Both new input and output become part of the cached prefix next turn.
        cached_tokens += turn.new_input_tokens + turn.output_tokens
        write_cost += turn.output_tokens * CACHE_WRITE_MULT * INPUT_PRICE

    total_cost = input_cost + write_cost + output_cost
    hit_rate = (
        round(cache_read_tokens / total_input_tokens, 4) if total_input_tokens else 0.0
    )
    return {
        "input_cost": round(input_cost, 2),
        "write_cost": round(write_cost, 2),
        "output_cost": round(output_cost, 2),
        "total_cost": round(total_cost, 2),
        "total_input_tokens": total_input_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_hit_rate": hit_rate,
        "cache_miss_rate": round(miss_rate, 4),
    }


def load_live_cost_measurement(path: Path | str = LIVE_MEASUREMENT_PATH) -> dict[str, Any] | None:
    """Load the rung-4 real token-bill measurement artifact if present (else None).

    This is real measured token accounting from a live multi-turn model session —
    the cache hit rate and token counts are MEASURED, not modeled. It is the
    evidence-ladder upgrade over the deterministic cost model.
    """
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def cost_reduction(baseline: dict[str, Any], uaek: dict[str, Any]) -> float:
    """Fraction of total cost saved by the UAEK strategy."""
    baseline_total = float(baseline["total_cost"])
    if baseline_total <= 0:
        return 0.0
    return round(1.0 - float(uaek["total_cost"]) / baseline_total, 4)


def run_cost_readiness() -> dict[str, Any]:
    """Red-teamed cost readiness: TTL-aware, range-reported, effort separated.

    A first version claimed a flat -63% by assuming the cache never expires. The
    red-team showed Anthropic's 5-min TTL means human-paced / tool-heavy turns
    miss the cache and re-write the prefix at 1.25x, collapsing the headline. So
    the honest headline is the reduction at a REALISTIC miss rate, reported with
    the full best-case→worst-case range, and with the cache-only saving split
    from the (unverified-quality) effort-routing saving.
    """
    workload = build_agent_workload()
    baseline = baseline_cost(workload)

    best_case = uaek_cost(workload, cache_miss_rate=0.0)
    realistic = uaek_cost(workload, cache_miss_rate=REALISTIC_MISS_RATE)
    cache_only = uaek_cost(workload, use_effort_routing=False, cache_miss_rate=REALISTIC_MISS_RATE)
    # Improvement: stable prefix on the 1-hour cache tier survives TTL misses.
    improved = uaek_cost(
        workload, cache_miss_rate=REALISTIC_MISS_RATE, long_ttl_stable_prefix=True
    )

    best_case_reduction = cost_reduction(baseline, best_case)
    realistic_reduction = cost_reduction(baseline, realistic)
    improved_reduction = cost_reduction(baseline, improved)
    cache_only_reduction = cost_reduction(baseline, cache_only)
    effort_contribution = round(realistic_reduction - cache_only_reduction, 4)

    # Rung-4: real measured token bill from a live model session, if available.
    live = load_live_cost_measurement()

    # TTL sensitivity sweep — the headline number's dependence on cache freshness.
    ttl_sweep = [
        {
            "cache_miss_rate": miss,
            "cost_reduction": cost_reduction(baseline, uaek_cost(workload, cache_miss_rate=miss)),
        }
        for miss in (0.0, 0.1, 0.2, 0.3, 0.5, 1.0)
    ]

    checks = [
        {
            "id": "best_case_beats_proposal_target",
            "required": True,
            "status": "pass" if best_case_reduction >= PROPOSAL_TARGET else "fail",
            "evidence": (
                f"fresh-cache reduction {best_case_reduction:.0%} >= "
                f"proposal target {PROPOSAL_TARGET:.0%}"
            ),
        },
        {
            "id": "ttl_sensitivity_disclosed",
            "required": True,
            "status": "pass",
            "evidence": (
                f"reduction ranges {ttl_sweep[-1]['cost_reduction']:.0%} (100% miss) to "
                f"{ttl_sweep[0]['cost_reduction']:.0%} (fresh) across the TTL sweep"
            ),
        },
        {
            "id": "improved_robust_to_realistic_ttl_misses",
            "required": True,
            "status": "pass" if improved_reduction >= PROPOSAL_TARGET else "fail",
            "evidence": (
                f"1-hour stable-prefix tier at {REALISTIC_MISS_RATE:.0%} TTL miss: reduction "
                f"{improved_reduction:.0%} (vs {realistic_reduction:.0%} on 5-min tier) "
                f"target {PROPOSAL_TARGET:.0%}"
            ),
        },
    ]
    if live is not None:
        real_hit = float(live.get("measured", {}).get("real_cache_hit_rate", 0.0))
        real_red = float(live.get("measured", {}).get("real_cost_reduction", 0.0))
        checks.append(
            {
                "id": "live_measurement_validates_model",
                "required": False,
                "status": "pass" if real_hit >= 0.70 else "fail",
                "evidence": (
                    f"rung-4 live mimo session: MEASURED cache hit {real_hit:.0%}, "
                    f"cost reduction {real_red:.0%} (warm session — real analog of best case)"
                ),
            }
        )
    required_pass = all(c["status"] == "pass" for c in checks if c["required"])

    return {
        # Improved: the 1-hour stable-prefix tier makes the realistic number robust.
        "status": "completed" if required_pass else "partial",
        "dimension": "4_cost",
        "proposal_target": PROPOSAL_TARGET,
        "stretch_target": STRETCH_TARGET,
        "realistic_miss_rate": REALISTIC_MISS_RATE,
        # Headline is the IMPROVED realistic number (1-hour stable-prefix tier).
        "cost_reduction": improved_reduction,
        "cost_reduction_5min_tier": realistic_reduction,
        "cost_reduction_best_case": best_case_reduction,
        "cost_reduction_cache_only": cache_only_reduction,
        "ttl_improvement": round(improved_reduction - realistic_reduction, 4),
        "effort_routing_contribution": effort_contribution,
        "cache_hit_rate": best_case["cache_hit_rate"],
        "ttl_sweep": ttl_sweep,
        "live_measurement": live,
        "baseline": baseline,
        "uaek": improved,
        "pricing": {
            "input": INPUT_PRICE,
            "cache_write": CACHE_WRITE_MULT,
            "cache_read": CACHE_READ_MULT,
            "output": OUTPUT_MULT,
        },
        "checks": checks,
        "resolved_findings": (
            ["W7_COST_PERFORMANCE", "F029_CACHE_AWARE_COST_MODEL"] if required_pass else []
        ),
        "limitations": [
            "Modeled cost under documented Anthropic-style cache multipliers, not a billed "
            "invoice; absolute savings depend on workload shape.",
            "Headline is the IMPROVED number: the stable system+tools prefix is put on the "
            "1-hour cache tier (2x write premium) so it survives the gaps that expire the 5-min "
            "rolling history. This makes the 20%-miss reduction robust; the 5-min-only number "
            "(cost_reduction_5min_tier) and the full TTL sweep are reported for comparison. A "
            "session gap beyond 1 hour still expires even the stable prefix.",
            "The baseline caches nothing; a baseline that already caches the static system+tools "
            "prefix would narrow the delta. Cache-only vs +effort are reported separately so the "
            "unverified 'simple turns are cheaper without quality loss' assumption is auditable.",
            "Anthropic allows only ~4 cache breakpoints; perfect per-turn incremental caching is "
            "an upper bound, so the modeled hit rate is optimistic.",
        ],
    }
