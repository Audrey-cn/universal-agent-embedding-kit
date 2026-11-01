# Local hooks policy

This repository's local `core.hooksPath` may point here. No executable Git hooks
are installed by the project. The directory being present does not enforce a gate.

The required checks are the documented ruff, formatting, mypy, pytest/coverage and
headline-consistency commands in CI and `scripts/setup.sh --verify`. Optional
pre-commit setup remains explicit; it is not installed or enabled automatically.

Do not stage unrelated work or use a hook to make implicit commits. Local checks
and configured CI jobs are separate evidence; only a completed run proves a gate.
