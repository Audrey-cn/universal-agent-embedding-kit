"""The same numbers cannot silently change their unit, scope, or direction."""

import shutil
from pathlib import Path

import pytest

from scripts.check_headline_consistency import main


@pytest.mark.parametrize(
    "name,before,after",
    [
        ("README.md", "expected acc. @70% util", "live accuracy @70% accuracy"),
        ("README.md", "modeled −43%", "production −43%"),
        ("README.md", "22% more expensive", "22% cheaper"),
        (
            "README.md",
            "validates retrieval, not the adaptive advantage live",
            "proves the adaptive advantage live",
        ),
        ("README.md", "warm live spot-check", "general production saving"),
        ("README.zh.md", "期望准确率 @70% 利用率", "实测准确率 @70% 准确率"),
        ("README.zh.md", "建模 −43%", "生产 −43%"),
        ("README.zh.md", "贵 22%", "便宜 22%"),
        ("README.zh.md", "验证的是检索,不是自适应优势的 live 证明", "是自适应优势的 live 证明"),
    ],
)
def test_scope_direction_units(tmp_path: Path, name: str, before: str, after: str):
    root = Path.cwd()
    for rel in [
        "README.md",
        "README.zh.md",
        "VERIFICATION_SCORECARD.md",
        "benchmarks/results/capability-matrix.json",
        "benchmarks/results/benchmark-capability.json",
        "benchmarks/results/benchmark-context.json",
        "benchmarks/results/benchmark-cost.json",
    ]:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
    arguments = [
        "--artifact-dir",
        str(root / "benchmarks/results/capability-runs"),
        "--repository-root",
        str(tmp_path),
    ]
    assert main(arguments) == 0
    target = tmp_path / name
    text = target.read_text()
    assert before in text
    target.write_text(text.replace(before, after))
    assert main(arguments) == 1
