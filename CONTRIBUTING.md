# Contributing to UAEK

Thanks for your interest. UAEK is small and opinionated, and the one thing that
makes it worth existing is its **honesty discipline**. Contributions are welcome
as long as they keep that discipline intact.

## The one non-negotiable rule

> **Every metric you add or change must ship with its rung on the evidence ladder
> and an honest caveat.**

The evidence-strength ladder (see [`docs/methodology.md`](docs/methodology.md)):

| Rung | Strength | Means |
|:----:|----------|-------|
| ① | weakest | deterministic local benchmark |
| ② | | stress / adversarial test |
| ③ | | measured on real data |
| ④ | | live measurement against a real provider |
| ⑤ | strongest | external / third-party validation |

"Improving" a metric means **climbing the ladder** — collecting stronger evidence —
**never turning a knob** to make a local number look better. A number that goes
*down* after a red-team pass is a success, not a regression.

## Development setup

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
bash scripts/setup.sh        # .venv + install + ruff + mypy + pytest
```

## Before opening a PR

All gates must be green:

```bash
ruff check src api mcp tests
mypy src api mcp
pytest -q
```

- Add or update tests for any behavior change.
- If you touch a benchmark or a reported number, update
  [`VERIFICATION_SCORECARD.md`](VERIFICATION_SCORECARD.md) with the new value, its
  rung, and how it was measured.
- Keep claims in `README.md` / `README.zh.md` in sync, and never inflate them.

## Reporting bugs / ideas

Open an issue. For anything security-related, follow [`SECURITY.md`](SECURITY.md)
instead of filing a public issue.

## License

By contributing you agree your contributions are licensed under the
[MIT License](LICENSE).
