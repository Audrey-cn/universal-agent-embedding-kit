"""Tests for auto-graded code-task capability evidence and matrix scoring."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from src.cli import main

CORRECT_TWO_SUM = (
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i, num in enumerate(nums):\n"
    "        if target - num in seen:\n"
    "            return [seen[target - num], i]\n"
    "        seen[num] = i\n"
    "    return []\n"
)

WRONG_TWO_SUM = "def two_sum(nums, target):\n    return [0, 0]\n"


def _task(task_id: str = "two_sum"):
    from src.capability_tasks import get_task

    return get_task(task_id)


def test_grade_code_passes_correct_solution():
    from src.capability_tasks import grade_code

    result = grade_code(_task(), CORRECT_TWO_SUM)

    assert result["status"] == "pass"
    assert result["passed"] == result["total"]
    assert result["pass_rate"] == 1.0
    assert result["error"] is None


def test_grade_code_fails_wrong_solution():
    from src.capability_tasks import grade_code

    result = grade_code(_task(), WRONG_TWO_SUM)

    assert result["status"] == "fail"
    assert result["passed"] < result["total"]
    assert result["pass_rate"] < 1.0


def test_held_out_grading_catches_overfit_lookup():
    """A solution that hardcodes a lookup keyed on the public inputs passes the
    public cases but fails the held-out cases — the exact red-team #2 attack."""
    from src.capability_tasks import get_task, grade_code

    overfit = (
        "def two_sum(nums, target):\n"
        "    table = {(2, 7, 11, 15, 9): [0, 1], (3, 2, 4, 6): [1, 2], (3, 3, 6): [0, 1]}\n"
        "    return table.get(tuple(nums) + (target,), [0, 0])\n"
    )

    overfit_result = grade_code(get_task("two_sum"), overfit)
    correct_result = grade_code(get_task("two_sum"), CORRECT_TWO_SUM)

    assert overfit_result["status"] == "fail"
    assert overfit_result["total"] > len(get_task("two_sum").cases)  # held-out added
    assert correct_result["status"] == "pass"
    assert correct_result["passed"] == correct_result["total"]


def test_held_out_cases_are_deterministic_and_match_public_oracle():
    """Held-out cases are reproducible per task, and each task's reference oracle
    reproduces every public expected value (so the oracle is trustworthy)."""
    from src.capability_tasks import _HELD_OUT_ORACLES, CAPABILITY_TASKS, held_out_cases

    for task in CAPABILITY_TASKS:
        reference, _ = _HELD_OUT_ORACLES[task.task_id]
        for case in task.cases:
            assert reference(*case.args) == case.expected, task.task_id
        assert held_out_cases(task) == held_out_cases(task)  # deterministic
        assert len(held_out_cases(task)) == 16


def test_grade_code_held_out_zero_uses_public_only():
    from src.capability_tasks import get_task, grade_code

    result = grade_code(get_task("two_sum"), CORRECT_TWO_SUM, held_out=0)

    assert result["total"] == len(get_task("two_sum").cases)
    assert result["status"] == "pass"


def test_grade_code_reports_runtime_error_without_crashing():
    from src.capability_tasks import grade_code

    result = grade_code(_task(), "def two_sum(nums, target):\n    raise ValueError('boom')\n")

    assert result["status"] == "fail"
    assert result["passed"] == 0


def test_extract_code_strips_markdown_fences():
    from src.capability_tasks import extract_code

    fenced = "Sure!\n```python\n" + CORRECT_TWO_SUM + "```\nHope this helps."
    extracted = extract_code(fenced)

    assert "two_sum" in extracted
    assert "```" not in extracted
    assert "Hope this helps" not in extracted


def test_capability_artifact_validation_rejects_empty_grade():
    from src.capability_matrix import validate_capability_run_artifact

    artifact = _capability_artifact("mimo_code", tasks_passed=0, suite_pass_rate=0.0)
    validation = validate_capability_run_artifact(artifact)

    assert validation["valid"] is False
    assert validation["is_graded_live"] is False


def test_capability_artifact_validation_accepts_graded_live():
    from src.capability_matrix import validate_capability_run_artifact

    artifact = _capability_artifact("mimo_code", tasks_passed=4, suite_pass_rate=1.0)
    validation = validate_capability_run_artifact(artifact)

    assert validation["valid"] is True
    assert validation["is_graded_live"] is True
    assert validation["tasks_passed"] == 4


def test_capability_artifact_validation_requires_full_suite_pass_for_graded_live():
    """A provider that passes one or most tasks is evidence, but not full graded-live."""
    from src.capability_matrix import validate_capability_run_artifact

    artifact = _capability_artifact("mimo_code", tasks_passed=3, suite_pass_rate=0.75)
    validation = validate_capability_run_artifact(artifact)

    assert validation["valid"] is True
    assert validation["is_graded_live"] is False
    assert validation["tasks_passed"] == 3
    assert validation["tasks_total"] == 4


def test_capability_matrix_scores_98_with_two_graded_and_two_blocked(tmp_path: Path):
    from src.capability_matrix import run_capability_readiness

    for provider in ["mimo_code", "hermes"]:
        _write_json(
            tmp_path / f"{provider}-capability-run.json",
            _capability_artifact(provider, tasks_passed=4, suite_pass_rate=1.0),
        )
    _write_json(
        tmp_path / "codex-capability-run.json",
        _capability_artifact(
            "codex",
            tasks_passed=0,
            suite_pass_rate=0.0,
            status="failed",
            error="Codex usage limit reached",
        ),
    )
    _write_json(
        tmp_path / "claude_code-capability-run.json",
        _capability_artifact(
            "claude_code",
            tasks_passed=0,
            suite_pass_rate=0.0,
            status="failed",
            error="Electron IndexedDB lock prevented headless run",
        ),
    )

    result = run_capability_readiness(tmp_path)

    assert result["status"] == "partial"
    assert result["previous_score"] == 97
    assert result["recommended_score"] == 98
    assert result["metrics"]["graded_live_provider_count"] == 2
    assert result["metrics"]["blocked_provider_count"] == 2
    assert result["metrics"]["missing_provider_count"] == 0
    assert _provider_status(result, "codex")["status"] == "blocked"
    assert _check_status(result, "graded_live_capability_matrix") == "fail"
    assert _check_status(result, "blocked_attempt_diagnostics") == "pass"


def test_partial_run_reports_real_score_not_blocked(tmp_path: Path):
    """A provider that ran the live suite and missed a task is 'partial' with its real
    tasks_passed/capability_score — not relabeled 'blocked, 0.0'. Only genuine
    non-execution (zero passing tasks) is 'blocked'."""
    from src.capability_matrix import run_capability_readiness

    # mimo ran live and passed 3/4 (real partial); hermes failed to run (0 tasks).
    _write_json(
        tmp_path / "mimo_code-capability-run.json",
        _capability_artifact(
            "mimo_code", tasks_passed=3, suite_pass_rate=0.75, capability_score=0.6
        ),
    )
    _write_json(
        tmp_path / "hermes-capability-run.json",
        _capability_artifact(
            "hermes",
            tasks_passed=0,
            suite_pass_rate=0.0,
            status="failed",
            error="hermes backend degraded: no final response",
        ),
    )
    for provider in ["codex", "claude_code"]:
        _write_json(
            tmp_path / f"{provider}-capability-run.json",
            _capability_artifact(provider, tasks_passed=4, suite_pass_rate=1.0),
        )

    result = run_capability_readiness(tmp_path)

    mimo = _provider_status(result, "mimo_code")
    assert mimo["status"] == "partial"
    assert mimo["tasks_passed"] == 3  # real value, not zeroed
    assert mimo["capability_score"] == 0.6  # real score, not 0.0
    assert _provider_status(result, "hermes")["status"] == "blocked"
    assert result["metrics"]["partial_provider_count"] == 1
    assert result["metrics"]["blocked_provider_count"] == 1
    assert result["metrics"]["graded_live_provider_count"] == 2
    # partial providers still count as having produced diagnostics
    assert _check_status(result, "blocked_attempt_diagnostics") == "pass"


def test_capability_matrix_scores_99_with_three_graded(tmp_path: Path):
    from src.capability_matrix import run_capability_readiness

    for provider in ["mimo_code", "hermes", "codex"]:
        _write_json(
            tmp_path / f"{provider}-capability-run.json",
            _capability_artifact(provider, tasks_passed=4, suite_pass_rate=1.0),
        )
    _write_json(
        tmp_path / "claude_code-capability-run.json",
        _capability_artifact(
            "claude_code",
            tasks_passed=0,
            suite_pass_rate=0.0,
            status="failed",
            error="Electron IndexedDB lock prevented headless run",
        ),
    )

    result = run_capability_readiness(tmp_path)

    assert result["recommended_score"] == 99
    assert result["metrics"]["graded_live_provider_count"] == 3
    assert _check_status(result, "blocked_attempt_diagnostics") == "pass"


def test_benchmark_capability_suite_uses_existing_artifacts():
    from src.benchmark import run_benchmark

    result = run_benchmark("capability", iterations=1)

    assert result["suite"] == "capability"
    assert result["scorecard"]["previous_score"] == 97
    assert result["scorecard"]["current_score"] >= 97
    assert "capability_readiness" in result


def test_cli_benchmark_capability_suite(tmp_path: Path):
    output_path = tmp_path / "benchmark-capability.json"

    result = CliRunner().invoke(
        main,
        ["benchmark", "--suite", "capability", "--iterations", "1", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "capability"
    assert "capability_readiness" in payload


def test_cli_capability_run_accepts_provider_home_option(tmp_path: Path, monkeypatch):
    import sys

    runner = CliRunner()
    output_path = tmp_path / "provider-home-capability.json"
    captured = {}
    script = tmp_path / "noop.py"
    script.write_text("print('ok')", encoding="utf-8")
    seed = tmp_path / "seed.txt"
    seed.write_text("model: configured", encoding="utf-8")

    def fake_runner(
        provider,
        base_command,
        output_mode="plain",
        provider_home=None,
        provider_home_seed_paths=(),
        timeout=120.0,
        source="uaek capability run",
    ):
        captured["provider_home"] = provider_home
        captured["provider_home_seed_paths"] = provider_home_seed_paths
        return _capability_artifact(
            provider,
            tasks_passed=1,
            suite_pass_rate=0.25,
            capability_score=0.25,
        )

    def fake_validate(artifact):
        return {
            "valid": True,
            "errors": [],
            "schema": artifact["schema"],
            "provider": artifact["provider"],
            "status": artifact["status"],
            "evidence_level": artifact["evidence_level"],
            "tasks_passed": artifact["metrics"]["tasks_passed"],
            "tasks_total": artifact["metrics"]["tasks_attempted"],
            "suite_pass_rate": artifact["metrics"]["suite_pass_rate"],
            "is_graded_live": True,
        }

    monkeypatch.setattr("src.capability_matrix.run_capability_suite_live", fake_runner)
    monkeypatch.setattr("src.capability_matrix.validate_capability_run_artifact", fake_validate)

    result = runner.invoke(
        main,
        [
            "capability",
            "run",
            "--provider",
            "mimo_code",
            "--command",
            str(Path(sys.executable)),
            "--command",
            str(script),
            "--provider-home",
            str(tmp_path / "provider-home"),
            "--provider-home-seed",
            str(seed),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["provider_home"] == str(tmp_path / "provider-home")
    assert captured["provider_home_seed_paths"] == (str(seed),)
    assert output_path.exists()


def test_cli_capability_batch_runs_manifest_and_writes_matrix(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    artifact_dir = tmp_path / "capability-runs"
    provider_home_root = tmp_path / "provider-homes"
    matrix_output = tmp_path / "capability-matrix.json"
    batch_output = tmp_path / "capability-batch.json"
    seed = tmp_path / "config.yaml"
    seed.write_text("model: configured\n", encoding="utf-8")
    providers = ["codex", "claude_code", "mimo_code", "hermes"]
    manifest = {
        "artifact_dir": str(artifact_dir),
        "provider_home_root": str(provider_home_root),
        "providers": [
            {
                "provider": provider,
                "command": ["fake-agent", provider],
                "output_mode": "plain",
                "provider_home_seed_paths": [str(seed)] if provider == "hermes" else [],
            }
            for provider in providers
        ],
    }
    manifest_path = tmp_path / "capability-manifest.json"
    _write_json(manifest_path, manifest)
    captured: dict[str, dict] = {}

    def fake_runner(
        provider,
        base_command,
        output_mode="plain",
        provider_home=None,
        provider_home_seed_paths=(),
        timeout=120.0,
        source="uaek capability batch",
    ):
        captured[provider] = {
            "command": base_command,
            "provider_home": provider_home,
            "provider_home_seed_paths": provider_home_seed_paths,
            "source": source,
        }
        return _capability_artifact(
            provider,
            tasks_passed=4,
            suite_pass_rate=1.0,
            capability_score=1.0,
        )

    monkeypatch.setattr("src.capability_matrix.run_capability_suite_live", fake_runner)

    result = runner.invoke(
        main,
        [
            "capability",
            "batch",
            str(manifest_path),
            "--output",
            str(batch_output),
            "--matrix-output",
            str(matrix_output),
        ],
    )

    assert result.exit_code == 0
    assert "Capability Batch" in result.output
    for provider in providers:
        assert (artifact_dir / f"{provider}-capability-run.json").exists()
        assert captured[provider]["provider_home"] == str(provider_home_root / provider)
    assert captured["hermes"]["provider_home_seed_paths"] == (str(seed),)
    matrix = json.loads(matrix_output.read_text(encoding="utf-8"))
    assert matrix["recommended_score"] == 100
    assert matrix["metrics"]["graded_live_provider_count"] == 4
    batch = json.loads(batch_output.read_text(encoding="utf-8"))
    assert batch["status"] == "completed"


def test_cli_capability_batch_dry_run_validates_manifest_without_running(
    tmp_path: Path, monkeypatch
):
    runner = CliRunner()
    output_path = tmp_path / "dry-run.json"
    manifest_path = tmp_path / "capability-manifest.json"
    manifest = {
        "artifact_dir": str(tmp_path / "capability-runs"),
        "provider_home_root": str(tmp_path / "provider-homes"),
        "providers": [
            {
                "provider": "codex",
                "command": ["codex", "exec"],
                "provider_home_seed_paths": ["~/missing/auth.json"],
            }
        ],
    }
    _write_json(manifest_path, manifest)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry-run must not execute providers")

    monkeypatch.setattr("src.capability_matrix.run_capability_suite_live", fail_if_called)

    result = runner.invoke(
        main,
        [
            "capability",
            "batch",
            str(manifest_path),
            "--dry-run",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Capability Batch Dry Run" in result.output
    validation = json.loads(output_path.read_text(encoding="utf-8"))
    assert validation["valid"] is True
    assert validation["providers"][0]["provider_home"] == str(tmp_path / "provider-homes/codex")
    assert validation["warnings"]


def test_cli_capability_batch_dry_run_rejects_bad_output_mode(tmp_path: Path):
    runner = CliRunner()
    manifest_path = tmp_path / "bad-capability-manifest.json"
    _write_json(
        manifest_path,
        {
            "providers": [
                {
                    "provider": "codex",
                    "command": ["codex", "exec"],
                    "output_mode": "xml",
                }
            ]
        },
    )

    result = runner.invoke(main, ["capability", "batch", str(manifest_path), "--dry-run"])

    assert result.exit_code == 1
    assert "output_mode unsupported" in result.output


FAKE_PROVIDER = '''
import sys
prompt = sys.argv[-1]
solutions = {
    "two_sum": (
        "def two_sum(nums, target):\\n"
        "    seen = {}\\n"
        "    for i, n in enumerate(nums):\\n"
        "        if target - n in seen:\\n"
        "            return [seen[target - n], i]\\n"
        "        seen[n] = i\\n"
        "    return []\\n"
    ),
    "is_palindrome": (
        "def is_palindrome(s):\\n"
        "    t = ''.join(c.lower() for c in s if c.isalnum())\\n"
        "    return t == t[::-1]\\n"
    ),
    "fizzbuzz": (
        "def fizzbuzz(n):\\n"
        "    if n % 15 == 0: return 'FizzBuzz'\\n"
        "    if n % 3 == 0: return 'Fizz'\\n"
        "    if n % 5 == 0: return 'Buzz'\\n"
        "    return str(n)\\n"
    ),
    "max_subarray": (
        "def max_subarray(nums):\\n"
        "    best = cur = nums[0]\\n"
        "    for x in nums[1:]:\\n"
        "        cur = max(x, cur + x)\\n"
        "        best = max(best, cur)\\n"
        "    return best\\n"
    ),
}
for name, code in solutions.items():
    if name in prompt:
        print("Sure, here you go:\\n```python\\n" + code + "```")
        break
'''


def test_run_capability_suite_live_grades_fake_provider(tmp_path: Path):
    from src.capability_matrix import run_capability_suite_live, validate_capability_run_artifact

    fake = tmp_path / "fake_agent.py"
    fake.write_text(FAKE_PROVIDER, encoding="utf-8")

    artifact = run_capability_suite_live(
        provider="fake",
        base_command=[__import__("sys").executable, str(fake)],
        output_mode="plain",
    )

    # The fake provider solves the original easy tier; the suite has since grown
    # with medium/hard tiers, so assert growth-robust lower bounds rather than a
    # full pass. The point of this test is the end-to-end driver + grading path.
    assert artifact["status"] == "completed"
    assert artifact["metrics"]["tasks_passed"] >= 4
    assert artifact["metrics"]["suite_pass_rate"] > 0
    assert 0.0 < artifact["metrics"]["capability_score"] <= 1.0
    validation = validate_capability_run_artifact(artifact)
    assert validation["valid"] is True
    assert validation["is_graded_live"] is False


def test_run_capability_suite_live_marks_failure_for_silent_provider(tmp_path: Path):
    from src.capability_matrix import run_capability_suite_live

    silent = tmp_path / "silent.py"
    silent.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")

    artifact = run_capability_suite_live(
        provider="silent",
        base_command=[__import__("sys").executable, str(silent)],
        output_mode="plain",
    )

    assert artifact["status"] == "failed"
    assert artifact["metrics"]["tasks_passed"] == 0


def test_decode_output_mimo_jsonl_concatenates_text_parts(tmp_path: Path):
    from src.capability_matrix import run_capability_suite_live

    mimo_like = tmp_path / "mimo_like.py"
    mimo_like.write_text(
        "import sys, json\n"
        "prompt = sys.argv[-1]\n"
        "code = 'def two_sum(nums, target):\\n    seen={}\\n"
        "    for i,n in enumerate(nums):\\n        if target-n in seen:\\n"
        "            return [seen[target-n], i]\\n        seen[n]=i\\n    return []\\n'\n"
        "if 'two_sum' in prompt:\n"
        "    print(json.dumps({'type': 'text', 'part': {'text': code}}))\n",
        encoding="utf-8",
    )

    artifact = run_capability_suite_live(
        provider="mimo_like",
        base_command=[__import__("sys").executable, str(mimo_like)],
        output_mode="mimo_jsonl",
    )

    two_sum = next(item for item in artifact["task_results"] if item["task_id"] == "two_sum")
    assert two_sum["status"] == "pass"


def test_write_capability_run_roundtrip(tmp_path: Path):
    from src.capability_matrix import validate_capability_run_artifact, write_capability_run

    artifact = _capability_artifact("mimo_code", tasks_passed=4, suite_pass_rate=1.0)
    path = write_capability_run(artifact, tmp_path / "out-capability-run.json")
    reloaded = json.loads(path.read_text(encoding="utf-8"))

    assert validate_capability_run_artifact(reloaded)["is_graded_live"] is True


def test_build_run_environment_redirects_provider_home_paths(tmp_path: Path):
    import os

    from src.capability_matrix import _build_run_environment

    provider_home = tmp_path / "isolated-home"
    env = _build_run_environment(str(provider_home))

    expected_home = os.path.abspath(str(provider_home))
    assert env is not None
    assert env["HOME"] == expected_home
    assert env["XDG_CONFIG_HOME"] == expected_home + "/.config"
    assert env["XDG_CACHE_HOME"] == expected_home + "/.cache"
    assert env["XDG_DATA_HOME"] == expected_home + "/.local/share"
    assert (provider_home / ".config").is_dir()
    assert (provider_home / ".cache").is_dir()
    assert (provider_home / ".local" / "share").is_dir()


def test_build_run_environment_copies_explicit_seed_paths(monkeypatch, tmp_path: Path):
    from src.capability_matrix import _build_run_environment

    source_home = tmp_path / "source-home"
    seed_file = source_home / ".hermes" / "config.yaml"
    seed_file.parent.mkdir(parents=True)
    seed_file.write_text("model: configured\n", encoding="utf-8")
    provider_home = tmp_path / "isolated-home"
    monkeypatch.setenv("HOME", str(source_home))

    env = _build_run_environment(str(provider_home), (str(seed_file),))

    assert env is not None
    assert (provider_home / ".hermes" / "config.yaml").read_text(
        encoding="utf-8"
    ) == "model: configured\n"


def test_run_capability_suite_live_passes_provider_home_env_to_subprocess(
    monkeypatch, tmp_path: Path
):
    import os
    import sys

    from src.capability_matrix import run_capability_suite_live
    from src.capability_tasks import get_task

    captured = {}

    def fake_run(command, capture_output, text, timeout, check, env=None):
        captured["env"] = env
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=CORRECT_TWO_SUM,
            stderr="",
        )

    monkeypatch.setattr(
        "src.capability_matrix.grade_code",
        lambda task, code, timeout=20.0: {  # noqa: ARG005
            "task_id": task.task_id,
            "entrypoint": task.entrypoint,
            "difficulty": task.difficulty,
            "passed": 1,
            "total": 1,
            "pass_rate": 1.0,
            "status": "pass",
            "cases": [],
            "error": None,
        },
    )
    monkeypatch.setattr("src.capability_matrix.subprocess.run", fake_run)
    provider_home = tmp_path / "provider_home"

    artifact = run_capability_suite_live(
        provider="fake_provider",
        base_command=[sys.executable, "-c", "print('noop')"],
        output_mode="plain",
        provider_home=str(provider_home),
        tasks=(get_task("two_sum"),),
    )

    assert artifact["status"] == "completed"
    assert artifact["metrics"]["tasks_passed"] == 1
    assert captured["env"] is not None
    assert captured["env"]["HOME"] == os.path.abspath(str(provider_home))
    assert captured["env"]["XDG_CONFIG_HOME"] == os.path.abspath(str(provider_home)) + "/.config"


def test_run_capability_suite_live_uses_default_env_without_provider_home(
    monkeypatch, tmp_path: Path
):
    import sys

    from src.capability_matrix import run_capability_suite_live
    from src.capability_tasks import get_task

    captured = {}

    def fake_run(command, capture_output, text, timeout, check, env=None):
        captured["env"] = env
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=CORRECT_TWO_SUM,
            stderr="",
        )

    monkeypatch.setattr(
        "src.capability_matrix.grade_code",
        lambda task, code, timeout=20.0: {  # noqa: ARG005
            "task_id": task.task_id,
            "entrypoint": task.entrypoint,
            "difficulty": task.difficulty,
            "passed": 1,
            "total": 1,
            "pass_rate": 1.0,
            "status": "pass",
            "cases": [],
            "error": None,
        },
    )
    monkeypatch.setattr("src.capability_matrix.subprocess.run", fake_run)

    artifact = run_capability_suite_live(
        provider="fake_provider",
        base_command=[sys.executable, "-c", "print('noop')"],
        output_mode="plain",
        tasks=(get_task("two_sum"),),
    )

    assert artifact["status"] == "completed"
    assert artifact["metrics"]["tasks_passed"] == 1
    assert captured["env"] is None


def test_run_capability_suite_live_handles_timeout(tmp_path: Path):
    from src.capability_matrix import run_capability_suite_live

    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")

    artifact = run_capability_suite_live(
        provider="slow",
        base_command=[__import__("sys").executable, str(slow)],
        output_mode="plain",
        timeout=0.2,
    )

    assert artifact["status"] == "failed"
    assert any("timed out" in str(item["error"]) for item in artifact["task_results"])


def test_capability_matrix_reports_missing_and_blocked(tmp_path: Path):
    from src.capability_matrix import run_capability_readiness

    # Only one graded-live provider; the rest are missing entirely.
    _write_json(
        tmp_path / "mimo_code-capability-run.json",
        _capability_artifact("mimo_code", tasks_passed=4, suite_pass_rate=1.0),
    )

    result = run_capability_readiness(tmp_path)

    assert result["recommended_score"] == 97
    assert result["status"] == "partial"
    assert result["metrics"]["graded_live_provider_count"] == 1
    assert result["metrics"]["missing_provider_count"] == 3
    assert _provider_status(result, "codex")["status"] == "missing"
    assert _check_status(result, "blocked_attempt_diagnostics") == "fail"


def test_capability_matrix_empty_dir_is_partial(tmp_path: Path):
    from src.capability_matrix import run_capability_readiness

    result = run_capability_readiness(tmp_path / "does-not-exist")

    assert result["status"] == "partial"
    assert result["recommended_score"] == 97
    assert result["metrics"]["capability_artifacts"] == 0


def test_run_capability_suite_live_rejects_empty_command():
    import pytest

    from src.capability_matrix import run_capability_suite_live

    with pytest.raises(ValueError):
        run_capability_suite_live(provider="x", base_command=[], output_mode="plain")


def test_run_capability_suite_live_rejects_seed_without_provider_home(tmp_path: Path):
    import pytest

    from src.capability_matrix import run_capability_suite_live

    seed = tmp_path / "seed.txt"
    seed.write_text("config", encoding="utf-8")

    with pytest.raises(ValueError, match="provider_home"):
        run_capability_suite_live(
            provider="x",
            base_command=["echo"],
            output_mode="plain",
            provider_home_seed_paths=(str(seed),),
        )


def test_decode_output_extracts_text_from_mimo_jsonl():
    from src.capability_matrix import _decode_output

    stdout = "\n".join(
        [
            json.dumps({"type": "step_start", "part": {}}),
            json.dumps({"type": "text", "part": {"text": "def f():"}}),
            json.dumps({"type": "text", "part": {"text": "    return 1"}}),
            "not-json-line",
            json.dumps({"type": "step_finish", "part": {}}),
        ]
    )

    decoded = _decode_output(stdout, "mimo_jsonl")

    assert decoded == "def f():\n    return 1"


def test_run_capability_suite_live_grades_a_fake_plain_provider():
    """A deterministic fake command lets us exercise the live driver end to end."""
    import sys

    from src.capability_matrix import run_capability_suite_live, validate_capability_run_artifact
    from src.capability_tasks import get_task

    # Fake provider: ignores the appended prompt argv and always emits a correct two_sum.
    artifact = run_capability_suite_live(
        provider="fake_agent",
        base_command=[sys.executable, "-c", f"print('''{CORRECT_TWO_SUM}''')"],
        output_mode="plain",
        tasks=(get_task("two_sum"),),
        timeout=30.0,
    )

    assert artifact["schema"] == "capability_run_v1"
    assert artifact["evidence_level"] == "live_external"
    assert artifact["status"] == "completed"
    assert artifact["metrics"]["tasks_passed"] == 1
    assert artifact["task_results"][0]["task_id"] == "two_sum"
    validation = validate_capability_run_artifact(artifact)
    assert validation["is_graded_live"] is True


def test_run_capability_suite_live_records_failed_provider_as_blocked():
    import sys

    from src.capability_matrix import run_capability_suite_live, validate_capability_run_artifact
    from src.capability_tasks import get_task

    # Fake provider exits non-zero with no usable stdout -> blocked diagnostic.
    artifact = run_capability_suite_live(
        provider="broken_agent",
        base_command=[sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"],
        output_mode="plain",
        tasks=(get_task("two_sum"),),
        timeout=30.0,
    )

    assert artifact["status"] == "failed"
    assert artifact["metrics"]["tasks_passed"] == 0
    validation = validate_capability_run_artifact(artifact)
    assert validation["is_graded_live"] is False


def test_run_capability_suite_live_rejects_unknown_output_mode():
    import pytest

    from src.capability_matrix import run_capability_suite_live

    with pytest.raises(ValueError, match="output_mode"):
        run_capability_suite_live("x", ["echo"], output_mode="bogus")


def _check_status(result: dict, check_id: str) -> str:
    for check in result["checks"]:
        if check["id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")


def _provider_status(result: dict, provider: str) -> dict:
    for item in result["provider_statuses"]:
        if item["provider"] == provider:
            return item
    raise AssertionError(f"missing provider {provider}")


def _capability_artifact(
    provider: str,
    tasks_passed: int,
    suite_pass_rate: float,
    status: str = "completed",
    error: str | None = None,
    capability_score: float | None = None,
) -> dict:
    tasks_total = 4
    tiers = ["easy", "easy", "medium", "hard"]
    task_results = []
    for index in range(tasks_total):
        passed = 1 if index < tasks_passed else 0
        task_results.append(
            {
                "task_id": f"task_{index}",
                "difficulty": tiers[index],
                "passed": 3 if passed else 0,
                "total": 3,
                "pass_rate": 1.0 if passed else 0.0,
                "status": "pass" if passed else "fail",
                "code": "def f():\n    return 1\n",
                "error": None if passed else (error or "wrong answer"),
            }
        )
    metrics = {
        "tasks_attempted": tasks_total,
        "tasks_passed": tasks_passed,
        "suite_pass_rate": suite_pass_rate,
        "cases_passed": tasks_passed * 3,
        "cases_total": tasks_total * 3,
    }
    if capability_score is not None:
        metrics["capability_score"] = capability_score
    return {
        "schema": "capability_run_v1",
        "run_id": f"capability-{provider}",
        "provider": provider,
        "task": f"{provider} capability suite",
        "status": status,
        "evidence_level": "live_external",
        "recorded_at": "2026-06-18T00:00:00+00:00",
        "suite": {"task_count": tasks_total},
        "task_results": task_results,
        "metrics": metrics,
        "provenance": {
            "source": f"{provider} live capability suite",
            "command": [provider, "run", "task"],
            "adapter_result_path": f"/tmp/{provider}-capability.json",
        },
        "error": error,
    }


def test_suite_has_difficulty_tiers():
    from src.capability_tasks import CAPABILITY_TASKS, suite_difficulty_summary

    summary = suite_difficulty_summary()

    assert summary.get("easy", 0) >= 1
    assert summary.get("medium", 0) >= 1
    assert summary.get("hard", 0) >= 1
    assert len(CAPABILITY_TASKS) >= 8


def test_grade_hard_task_edit_distance():
    from src.capability_tasks import get_task, grade_code

    correct = (
        "def edit_distance(a, b):\n"
        "    m, n = len(a), len(b)\n"
        "    dp = list(range(n + 1))\n"
        "    for i in range(1, m + 1):\n"
        "        prev = dp[0]\n"
        "        dp[0] = i\n"
        "        for j in range(1, n + 1):\n"
        "            cur = dp[j]\n"
        "            if a[i - 1] == b[j - 1]:\n"
        "                dp[j] = prev\n"
        "            else:\n"
        "                dp[j] = 1 + min(prev, dp[j], dp[j - 1])\n"
        "            prev = cur\n"
        "    return dp[n]\n"
    )
    good = grade_code(get_task("edit_distance"), correct)
    bad = grade_code(get_task("edit_distance"), "def edit_distance(a, b):\n    return 0\n")

    assert good["status"] == "pass"
    assert good["difficulty"] == "hard"
    assert bad["status"] == "fail"


def test_compute_capability_score_weights_hard_more():
    from src.capability_tasks import compute_capability_score

    easy_only = [
        {"difficulty": "easy", "status": "pass"},
        {"difficulty": "hard", "status": "fail"},
    ]
    hard_only = [
        {"difficulty": "easy", "status": "fail"},
        {"difficulty": "hard", "status": "pass"},
    ]

    assert compute_capability_score(hard_only) > compute_capability_score(easy_only)


def test_capability_matrix_ranks_providers_and_reports_spread(tmp_path: Path):
    from src.capability_matrix import run_capability_readiness

    _write_json(
        tmp_path / "mimo_code-capability-run.json",
        _capability_artifact(
            "mimo_code", tasks_passed=4, suite_pass_rate=1.0, capability_score=1.0
        ),
    )
    _write_json(
        tmp_path / "hermes-capability-run.json",
        _capability_artifact("hermes", tasks_passed=4, suite_pass_rate=1.0, capability_score=0.7),
    )
    _write_json(
        tmp_path / "codex-capability-run.json",
        _capability_artifact("codex", tasks_passed=4, suite_pass_rate=1.0, capability_score=0.4),
    )
    _write_json(
        tmp_path / "claude_code-capability-run.json",
        _capability_artifact(
            "claude_code", tasks_passed=0, suite_pass_rate=0.0, status="failed", error="blocked"
        ),
    )

    result = run_capability_readiness(tmp_path)

    assert [item["provider"] for item in result["ranking"]] == ["mimo_code", "hermes", "codex"]
    assert result["metrics"]["capability_score_spread"] == 0.6
    assert result["metrics"]["capability_score_max"] == 1.0
    assert result["metrics"]["capability_score_min"] == 0.4
    assert _check_status(result, "discriminative_task_suite") == "pass"
    assert result["metrics"]["suite_difficulty_tiers"].get("hard", 0) >= 1


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
