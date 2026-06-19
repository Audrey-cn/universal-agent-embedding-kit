# Methodology: evidence strength over impressive numbers

UAEK's benchmarks are designed by the same party that builds the thing being
measured. That is the exact setup where numbers drift from *real* gains to
*vanity* gains. These two practices are how we keep them honest.

## The evidence-strength ladder

A claim can sit at any rung; the rung — not the number's size — determines how
much it is worth. "Pushing a metric to the ceiling" honestly means climbing this
ladder, never turning a constant.

| Rung | Evidence | What it looks like |
|------|----------|--------------------|
| ① | Deterministic local benchmark | a corpus and assumptions you control |
| ② | Stress / adversarial on your own benchmark | bigger, randomized, adversarial inputs; ablations; sensitivity analysis |
| ③ | Real data replaces constructed | real agent outputs, real bugs, real sessions |
| ④ | Live measurement replaces modeling | real model calls, real token bills, real windows |
| ⑤ | External / independent validation | others' data, published baselines, remote CI |

Report the rung next to the number: *"−43% cost reduction (rung 1–2: modeled
under documented cache pricing, red-teamed for TTL)"* tells a reader exactly how
much to trust it and what would strengthen it.

### Smell tests for a rung-1 number pretending to be more

- It hits a round target exactly (50%, 70%, 0%, 100%).
- One constant, if changed, moves the headline 1:1 — arithmetic, not measurement.
- The "bad" baseline is a strawman nobody would ship.
- The corpus's wrong cases were authored to fail the exact check that flags them.
- The metric can be passed without doing the thing it claims to measure.

## Red-team hardening

Before reporting a self-measured number:

1. **State each claim as an attackable target** — *"X claims Y under assumptions Z."*
2. **Spawn independent red-team agents** — one per claim, prompted to *prove the
   number is inflated*, not to confirm it. Do not red-team your own work yourself;
   you share its blind spots.
3. **Triage** — keep attacks that move the headline; drop nitpicks.
4. **Harden** — encode each material attack as a test, then change the code so the
   reported number accounts for it (add the realistic failure mode, model the
   loss, widen the corpus, replace the hollow proxy). The number usually drops.
5. **Scope the limitation** — every hardened number names its residual attack
   surface and the next rung up.

This repo applied exactly this: a red-team round found all four headline numbers
inflated (cost assumed an immortal cache; context modeled lossless compression;
the cheating rate rode a narrow input generator; one benchmark dimension was
hollow). Each was hardened to a number that survives — see
[`../VERIFICATION_SCORECARD.md`](../VERIFICATION_SCORECARD.md) for before/after.

The reusable form of this method is packaged as a standalone `red-team-hardening`
skill.
