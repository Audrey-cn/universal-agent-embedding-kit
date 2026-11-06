# Fable 5 status correction

Earlier wording incorrectly described Claude Fable 5 as retired. The official lifecycle is **Active (legacy)**: Fable 5 was released on 2026-06-09, temporarily paused for U.S. export-control compliance on 2026-06-12, and restored globally on 2026-07-01. Fable 5.1 has succeeded it, and Fable 5 will not be retired before 2027-06-09.

Official sources: [Redeploying Fable 5](https://www.anthropic.com/news/redeploying-fable-5) and the [Fable 5 model overview](https://platform.claude.com/docs/en/models/fable-5/overview).

This repository has not rerun a direct Fable 5 baseline. Historical JSON result archives under `benchmarks/results/` remain unchanged. Legacy serialized compatibility identifiers such as `retired_unavailable` and `DIRECT_RETIRED_MODEL_UNAVAILABLE` are retained where external consumers may depend on them; current proxy output adds `current_status = legacy_not_rerun`.
