from __future__ import annotations

from pathlib import Path

import pytest

from src.progressive_quality import ProgressiveQuality, QualityTier
from src.verify.diff_runner import DiffRunner
from src.verify.formal_verify import FormalVerificationStatus, FormalVerifier, LightweightSolver
from src.verify.incremental import DependencyGraph, IncrementalVerifier
from src.verify.multi_perspective import (
    MultiPerspectiveChecker,
    Perspective,
    PerspectiveResult,
)
from src.verify.property_test import (
    InputGenerator,
    PropertyTester,
    PropertyType,
    Shrinker,
    property_test_verify,
)


def test_diff_runner_returns_failure_for_incompatible_json_shapes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    criteria = tmp_path / "criteria.json"
    artifact.write_text('["name"]', encoding="utf-8")
    criteria.write_text('{"name": "uaek"}', encoding="utf-8")

    result = DiffRunner().run(artifact, criteria)

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert "object" in result.evidence.lower()


def test_diff_runner_reports_json_coverage_and_text_requirements(tmp_path: Path) -> None:
    artifact_json = tmp_path / "actual.json"
    criteria_json = tmp_path / "expected.json"
    artifact_json.write_text('{"name": "uaek", "extra": true}', encoding="utf-8")
    criteria_json.write_text('{"name": "uaek"}', encoding="utf-8")
    assert DiffRunner().run(artifact_json, criteria_json).passed is True

    artifact_text = tmp_path / "actual.md"
    criteria_text = tmp_path / "expected.md"
    artifact_text.write_text("# Runtime\nsecure MCP workflow", encoding="utf-8")
    criteria_text.write_text("# Runtime\n- [ ] secure MCP workflow", encoding="utf-8")
    result = DiffRunner().run(artifact_text, criteria_text)
    assert result.passed is True
    assert "checks" in result.evidence


def test_incremental_verifier_detects_real_file_changes_and_persists_cache(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    verifier = IncrementalVerifier(tmp_path)

    assert verifier.has_changed(source) is True
    first = verifier.update_fingerprint(source)
    assert verifier.has_changed(source) is False
    source.write_text("VALUE = 2\n", encoding="utf-8")

    assert verifier.detect_changes([source]) == {"module.py"}
    reloaded = IncrementalVerifier(tmp_path)
    assert reloaded.get_fingerprint(source).hash == first.hash  # type: ignore[union-attr]
    reloaded.clear_cache()
    assert reloaded.stats()["total_tracked"] == 0


def test_dependency_graph_propagates_transitive_impact_and_round_trips() -> None:
    graph = DependencyGraph()
    graph.add_dependency("api.py", "service.py")
    graph.add_dependency("service.py", "model.py")

    assert graph.affected_by({"model.py"}) == {"model.py", "service.py", "api.py"}
    restored = DependencyGraph.from_dict(graph.to_dict())
    assert restored.affected_by({"model.py"}) == {"model.py", "service.py", "api.py"}


def test_lightweight_formal_verifier_returns_counterexample_for_false_invariant() -> None:
    verifier = FormalVerifier(use_z3=False)

    valid = verifier.verify_invariant("x >= 0", {"x": range(0, 3)})
    invalid = verifier.verify_invariant("x > 0", {"x": range(0, 3)})

    assert valid.passed is True
    assert valid.status is FormalVerificationStatus.UNSAT
    assert invalid.passed is False
    assert invalid.counterexample == {"x": 0}


def test_lightweight_solver_rejects_unsafe_expressions() -> None:
    solver = LightweightSolver()
    solver.declare_int("x", range(2))

    with pytest.raises(ValueError, match="Unsupported constraint node"):
        solver.add_constraint("__import__('os').getcwd()")


def test_property_tester_finds_and_shrinks_non_idempotent_input() -> None:
    result = PropertyTester(trials=5, seed=1).test_idempotent(
        lambda value: value + 1,
        input_gen=lambda: 8,
    )

    assert result.passed is False
    assert result.counterexample == 8
    assert abs(result.shrunk_counterexample) < 8
    assert Shrinker().shrink([1, 2, 3], lambda values: len(values) < 1) == [1]


def test_input_generator_is_reproducible_for_a_fixed_seed() -> None:
    left = InputGenerator(seed=42)
    right = InputGenerator(seed=42)

    assert [left.random_int() for _ in range(5)] == [right.random_int() for _ in range(5)]
    assert left.random_choice(["a"]) == "a"
    assert isinstance(left.random_dict(lambda: "k", lambda: 1), dict)


def test_property_verify_rejects_parent_environment_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A policy regression would mutate the parent before property checks run."""
    artifact = tmp_path / "candidate.py"
    artifact.write_text(
        "import os\n"
        "os.environ['UAEK_PROPERTY_SENTINEL'] = 'changed'\n"
        "def normalize(value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UAEK_PROPERTY_SENTINEL", "unchanged")

    result = property_test_verify(
        artifact,
        "normalize",
        property_type=PropertyType.IDEMPOTENT,
        trials=3,
        seed=1,
    )

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert "policy rejected" in result.evidence.lower()
    assert "imports" in result.evidence.lower()
    assert __import__("os").environ["UAEK_PROPERTY_SENTINEL"] == "unchanged"


def test_property_verify_preserves_verification_result_contract(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.py"
    artifact.write_text(
        "def increment(value):\n"
        "    return value + 1\n",
        encoding="utf-8",
    )

    result = property_test_verify(
        artifact,
        "increment",
        property_type=PropertyType.IDEMPOTENT,
        trials=3,
        seed=1,
    )

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert result.evidence == "Property tests: 0/1 passed"
    assert result.notes == "Failed: ['idempotent']"
    assert result.artifact_path == artifact


def test_property_verify_preserves_missing_function_contract(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.py"
    artifact.write_text("def other(value):\n    return value\n", encoding="utf-8")

    result = property_test_verify(artifact, "target", trials=1)

    assert result.passed is False
    assert result.verdict == "INDETERMINATE"
    assert result.evidence == f"Function 'target' not found in {artifact}"
    assert result.notes == "Available: ['other']"


def test_property_verify_preserves_non_callable_contract(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.py"
    artifact.write_text("target = 1\n", encoding="utf-8")

    result = property_test_verify(artifact, "target", trials=1)

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert result.evidence == "'target' is not callable"
    assert result.notes == ""


def test_property_verify_preserves_syntax_error_contract(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.py"
    artifact.write_text("def target(:\n    pass\n", encoding="utf-8")

    result = property_test_verify(artifact, "target", trials=1)

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert result.evidence.startswith("Cannot compile code: ")
    assert "invalid syntax" in result.evidence
    assert result.notes == result.evidence.replace(
        "Cannot compile code: ", "Compile error: ", 1
    )


def test_property_verify_preserves_load_error_contract(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.py"
    artifact.write_text(
        "raise ValueError('boom')\n"
        "def target(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    result = property_test_verify(artifact, "target", trials=1)

    assert result.passed is False
    assert result.verdict == "FAIL"
    assert result.evidence == "Cannot compile code: boom"
    assert result.notes == "Compile error: boom"


def test_multi_perspective_checker_uses_weights_and_strict_consensus(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.py"
    artifact.write_text("VALUE = 1\n", encoding="utf-8")
    checker = MultiPerspectiveChecker(strict_mode=True)
    checker.register_perspective(
        Perspective.CORRECTNESS,
        lambda _artifact, _criteria: PerspectiveResult(
            Perspective.CORRECTNESS, True, 1.0, "correct"
        ),
        weight=3.0,
    )
    checker.register_perspective(
        Perspective.SECURITY,
        lambda _artifact, _criteria: PerspectiveResult(
            Perspective.SECURITY, False, 0.0, "unsafe"
        ),
        weight=1.0,
    )

    result = checker.check(artifact)

    assert result.overall_passed is False
    assert result.overall_score == pytest.approx(0.75)
    assert result.consensus_level == "weak"


def test_progressive_quality_stops_after_a_failing_fast_hook(tmp_path: Path) -> None:
    artifact = tmp_path / "valid.py"
    artifact.write_text("VALUE = 1\n", encoding="utf-8")
    verifier = ProgressiveQuality(
        stop_on_fail=True,
        tier_hooks={QualityTier.FAST: lambda _artifact, _criteria: False},
    )

    result = verifier.verify(artifact)

    assert result.overall_passed is False
    assert result.tiers_completed == [QualityTier.FAST]
    assert result.final_tier is QualityTier.FAST
    assert "FAST tier failed" in result.recommendation
