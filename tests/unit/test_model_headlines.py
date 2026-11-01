"""The CI headline command must reject stale context/cost claims too."""

import shutil
from pathlib import Path

import pytest

from scripts.check_headline_consistency import main


@pytest.mark.parametrize("bad_claim", ["context", "cost", "scope"])
def test_headline_command_rejects_stale_model_claims(tmp_path: Path, bad_claim: str) -> None:
    root = Path.cwd()
    for name in [
        "README.md",
        "README.zh.md",
        "VERIFICATION_SCORECARD.md",
        "benchmarks/results/capability-matrix.json",
        "benchmarks/results/benchmark-capability.json",
        "benchmarks/results/benchmark-context.json",
        "benchmarks/results/benchmark-cost.json",
    ]:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    arguments = [
        "--artifact-dir",
        str(root / "benchmarks/results/capability-runs"),
        "--repository-root",
        str(tmp_path),
    ]
    assert main(arguments) == 0
    readme = tmp_path / "README.md"
    text = readme.read_text()
    if bad_claim == "context":
        text = text.replace("**0.85** expected acc.", "**0.90** expected acc.")
    elif bad_claim == "cost":
        text = text.replace("−49% w/ 1h tier", "−63% w/ 1h tier")
    else:
        text = text.replace("warm-only best case;", "general production result;")
    readme.write_text(text)

    result = main(arguments)

    assert result == 1
