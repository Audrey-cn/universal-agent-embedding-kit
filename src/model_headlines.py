"""Keep current modeled claims distinct from historical and live best-case evidence."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

START = "<!-- current-model-headlines:start -->"
END = "<!-- current-model-headlines:end -->"


def _evidence(root: Path) -> tuple[dict, dict]:
    results = root / "benchmarks/results"
    context = json.loads((results / "benchmark-context.json").read_text())["context_rot_readiness"]
    cost = json.loads((results / "benchmark-cost.json").read_text())["cost_readiness"]
    return context, cost


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("modeled headline evidence must contain finite numbers")
    return float(value)


def render_model_headlines(root: Path) -> str:
    context, cost = _evidence(root)
    accuracy = _number(context["adaptive"]["accuracy_at_target"])
    utilization = _number(context["target_utilization"])
    reduction = _number(cost["cost_reduction"])
    misses = _number(cost["realistic_miss_rate"])
    return "\n".join(
        [
            START,
            "| 当前建模指标 | 归档证据口径 | 状态 |",
            "|---|---|---|",
            f"| Context accuracy | {accuracy:.4f} expected accuracy @ {utilization:.0%} "
            f"utilization; modeled | {context['status']} |",
            f"| Cost reduction | {reduction:.2%}; 1h cache tier, {misses:.0%} TTL miss; "
            f"modeled | {cost['status']} |",
            "",
            "来源：[context](benchmarks/results/benchmark-context.json)、[cost](benchmarks/results/benchmark-cost.json)。",
            "warm-only live 抽检是 best case；这里未重新运行模型，不将其推广为通用生产收益。",
            END,
        ]
    )


def validate_model_headlines(root: Path) -> list[str]:
    """Validate the generated summary and the two active README headline rows."""
    errors: list[str] = []
    try:
        expected = render_model_headlines(root)
        context, cost = _evidence(root)
        scorecard = (root / "VERIFICATION_SCORECARD.md").read_text()
        block = scorecard.partition(START)[2].partition(END)[0]
        if START not in scorecard or END not in scorecard or START + block + END != expected:
            errors.append(
                "VERIFICATION_SCORECARD.md: current modeled summary differs from evidence"
            )
        accuracy = _number(context["adaptive"]["accuracy_at_target"])
        utilization = _number(context["target_utilization"])
        naive = _number(context["naive"]["accuracy_at_target"])
        short = _number(cost["cost_reduction_5min_tier"])
        long = _number(cost["cost_reduction"])
        cold = _number(cost["cold_path_cost_increase"])
        live = cost["live_measurement"]["measured"]
        saving = _number(live["real_cost_reduction"])
        hit = _number(live["real_cache_hit_rate"])
        for (
            name,
            context_label,
            cost_label,
            context_claim,
            context_scope,
            cost_claim,
            cold_scope,
        ) in [
            (
                "README.md",
                "| Context utilization |",
                "| Cost reduction |",
                f"adaptive **{accuracy:.2f}** expected acc. "
                f"@{utilization:.0%} util vs naive {naive:.2f}",
                "validates retrieval, not the adaptive advantage live",
                f"modeled −{short:.0%} (−{long:.0%} w/ 1h tier); "
                f"warm live spot-check **−{saving:.0%}, {hit:.0%} hit**",
                f"warm-only best case; a fully-cold session is modeled "
                f"**{cold:.0%} more expensive** than baseline",
            ),
            (
                "README.zh.md",
                "| 上下文利用率 |",
                "| 成本降低 |",
                f"自适应 **{accuracy:.2f}** 期望准确率 "
                f"@{utilization:.0%} 利用率 vs naive {naive:.2f}",
                "验证的是检索,不是自适应优势的 live 证明",
                f"建模 −{short:.0%}(1h 档 −{long:.0%});"
                f"warm live 抽检 **−{saving:.0%},命中 {hit:.0%}**",
                f"warm-only best case;全冷会话建模结果比 baseline **贵 {cold:.0%}**",
            ),
        ]:
            lines = (root / name).read_text().splitlines()
            crows = [line for line in lines if line.startswith(context_label)]
            krows = [line for line in lines if line.startswith(cost_label)]
            # Check the claim's unit and scope together; matching numbers alone
            # would accept an expected accuracy relabeled as live utilization.
            if len(crows) != 1 or not (context_claim in crows[0] and context_scope in crows[0]):
                errors.append(f"{name}: stale context accuracy/utilization headline")
            if len(krows) != 1 or not (
                cost_claim in krows[0]
                and re.search(r"\b" + re.escape(str(cost["status"])) + r"\b", krows[0])
                and cold_scope in krows[0]
            ):
                errors.append(f"{name}: stale cost headline or missing best-case scope")
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        errors.append(f"modeled headline evidence unavailable: {exc}")
    return errors
