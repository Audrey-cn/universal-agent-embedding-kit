"""Public verification must execute the requested tests at real project paths."""

from pathlib import Path

import pytest

from src.verify import FreshContextVerifier, VerificationType, verify


def test_project_tests_are_not_bypassed_by_a_successful_build(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_failure.py").write_text("def test_failure():\n    assert False\n")
    (tmp_path / "Makefile").write_text("build:\n\t@echo build-ok\n")

    result = verify(tmp_path)

    assert result.verification_type == VerificationType.TEST
    assert result.passed is False
    assert "1 failed" in result.evidence


@pytest.mark.parametrize("layout", ["tests", "root"])
def test_directory_test_target_runs_existing_tests(tmp_path: Path, layout: str) -> None:
    target = tmp_path / "tests" if layout == "tests" else tmp_path
    target.mkdir(exist_ok=True)
    (target / "test_good.py").write_text("def test_good():\n    assert True\n")

    result = verify(target, verification_type=VerificationType.TEST)

    assert result.passed is True, result.evidence
    assert "1 passed" in result.evidence


@pytest.mark.parametrize("target", ["项目 tests/test_good.py", "项目 tests", "."])
def test_fresh_context_resolves_relative_unicode_and_space_paths(
    tmp_path: Path, monkeypatch, target: str
) -> None:
    tests = tmp_path / "项目 tests"
    tests.mkdir()
    (tests / "test_good.py").write_text("def test_good():\n    assert True\n")
    (tmp_path / "criteria.md").write_text("The one real test must pass.\n")
    monkeypatch.chdir(tmp_path)

    result = FreshContextVerifier().verify(Path(target), Path("criteria.md"))

    assert result.passed is True, result.evidence
    assert "1 passed" in result.evidence
