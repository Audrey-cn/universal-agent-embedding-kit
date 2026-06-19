"""Auto-gradable code-task suite for cross-platform capability comparison.

Each task ships a natural-language prompt (sent to an external Agent) and a set
of deterministic assertion cases. A candidate solution is graded objectively by
executing it in an isolated subprocess against the cases — no model self-grading.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapabilityCase:
    """A single deterministic input/output assertion for a task."""

    args: tuple[Any, ...]
    expected: Any


@dataclass(frozen=True)
class CapabilityTask:
    """A code task with a prompt and objective grading cases."""

    task_id: str
    prompt: str
    entrypoint: str
    cases: tuple[CapabilityCase, ...]
    difficulty: str = "easy"


# Difficulty weights make the suite discriminative: passing a hard task is worth
# more than an easy one, so providers that only clear the easy tier rank lower.
DIFFICULTY_WEIGHTS = {"easy": 1, "medium": 2, "hard": 3}


CAPABILITY_TASKS: tuple[CapabilityTask, ...] = (
    CapabilityTask(
        task_id="two_sum",
        prompt=(
            "Output ONLY a Python function definition named two_sum(nums, target) that returns "
            "the indices [i, j] of the two distinct entries in the list nums that add up to "
            "target, with i < j. No prose, no markdown fences, plain code only."
        ),
        entrypoint="two_sum",
        cases=(
            CapabilityCase(args=([2, 7, 11, 15], 9), expected=[0, 1]),
            CapabilityCase(args=([3, 2, 4], 6), expected=[1, 2]),
            CapabilityCase(args=([3, 3], 6), expected=[0, 1]),
        ),
    ),
    CapabilityTask(
        task_id="is_palindrome",
        prompt=(
            "Output ONLY a Python function definition named is_palindrome(s) that returns True "
            "if s is a palindrome considering only alphanumeric characters and ignoring case, "
            "else False. No prose, no markdown fences, plain code only."
        ),
        entrypoint="is_palindrome",
        cases=(
            CapabilityCase(args=("A man, a plan, a canal: Panama",), expected=True),
            CapabilityCase(args=("race a car",), expected=False),
            CapabilityCase(args=(" ",), expected=True),
        ),
    ),
    CapabilityTask(
        task_id="fizzbuzz",
        prompt=(
            "Output ONLY a Python function definition named fizzbuzz(n) that returns the string "
            "'FizzBuzz' if n is divisible by 15, 'Fizz' if divisible by 3, 'Buzz' if divisible "
            "by 5, otherwise the string form of n. No prose, no markdown fences, plain code only."
        ),
        entrypoint="fizzbuzz",
        cases=(
            CapabilityCase(args=(15,), expected="FizzBuzz"),
            CapabilityCase(args=(9,), expected="Fizz"),
            CapabilityCase(args=(10,), expected="Buzz"),
            CapabilityCase(args=(7,), expected="7"),
        ),
    ),
    CapabilityTask(
        task_id="max_subarray",
        prompt=(
            "Output ONLY a Python function definition named max_subarray(nums) that returns the "
            "largest sum of any contiguous non-empty subarray of the integer list nums. "
            "No prose, no markdown fences, plain code only."
        ),
        entrypoint="max_subarray",
        cases=(
            CapabilityCase(args=([-2, 1, -3, 4, -1, 2, 1, -5, 4],), expected=6),
            CapabilityCase(args=([1],), expected=1),
            CapabilityCase(args=([5, 4, -1, 7, 8],), expected=23),
            CapabilityCase(args=([-1, -2, -3],), expected=-1),
        ),
        difficulty="easy",
    ),
    CapabilityTask(
        task_id="roman_to_int",
        prompt=(
            "Output ONLY a Python function definition named roman_to_int(s) that converts a "
            "valid Roman numeral string s (I, V, X, L, C, D, M, including subtractive forms like "
            "IV and IX) to its integer value. No prose, no markdown fences, plain code only."
        ),
        entrypoint="roman_to_int",
        cases=(
            CapabilityCase(args=("III",), expected=3),
            CapabilityCase(args=("IV",), expected=4),
            CapabilityCase(args=("IX",), expected=9),
            CapabilityCase(args=("LVIII",), expected=58),
            CapabilityCase(args=("MCMXCIV",), expected=1994),
        ),
        difficulty="medium",
    ),
    CapabilityTask(
        task_id="valid_parentheses",
        prompt=(
            "Output ONLY a Python function definition named valid_parentheses(s) that returns "
            "True if the string s of brackets '()[]{}' is correctly matched and nested, else "
            "False. An empty string is valid. No prose, no markdown fences, plain code only."
        ),
        entrypoint="valid_parentheses",
        cases=(
            CapabilityCase(args=("()",), expected=True),
            CapabilityCase(args=("()[]{}",), expected=True),
            CapabilityCase(args=("(]",), expected=False),
            CapabilityCase(args=("([)]",), expected=False),
            CapabilityCase(args=("{[]}",), expected=True),
            CapabilityCase(args=("",), expected=True),
            CapabilityCase(args=("(",), expected=False),
        ),
        difficulty="medium",
    ),
    CapabilityTask(
        task_id="longest_unique_substring",
        prompt=(
            "Output ONLY a Python function definition named longest_unique_substring(s) that "
            "returns the length (int) of the longest substring of s without repeating "
            "characters. No prose, no markdown fences, plain code only."
        ),
        entrypoint="longest_unique_substring",
        cases=(
            CapabilityCase(args=("abcabcbb",), expected=3),
            CapabilityCase(args=("bbbbb",), expected=1),
            CapabilityCase(args=("pwwkew",), expected=3),
            CapabilityCase(args=("",), expected=0),
            CapabilityCase(args=("dvdf",), expected=3),
            CapabilityCase(args=("tmmzuxt",), expected=5),
        ),
        difficulty="medium",
    ),
    CapabilityTask(
        task_id="edit_distance",
        prompt=(
            "Output ONLY a Python function definition named edit_distance(a, b) that returns the "
            "Levenshtein edit distance (int) between strings a and b, allowing single-character "
            "insertions, deletions and substitutions. No prose, no markdown fences, plain code "
            "only."
        ),
        entrypoint="edit_distance",
        cases=(
            CapabilityCase(args=("horse", "ros"), expected=3),
            CapabilityCase(args=("intention", "execution"), expected=5),
            CapabilityCase(args=("", "abc"), expected=3),
            CapabilityCase(args=("abc", "abc"), expected=0),
            CapabilityCase(args=("sunday", "saturday"), expected=3),
        ),
        difficulty="hard",
    ),
    CapabilityTask(
        task_id="lru_cache_sim",
        prompt=(
            "Output ONLY a Python function definition named lru_cache_sim(capacity, ops) that "
            "simulates an LRU cache. ops is a list where each item is either ['put', key, value] "
            "or ['get', key]. Return a list with one entry per 'get' op: the cached value, or -1 "
            "if absent. Evict the least-recently-used key when over capacity; both get and put "
            "count as use. No prose, no markdown fences, plain code only."
        ),
        entrypoint="lru_cache_sim",
        cases=(
            CapabilityCase(
                args=(
                    2,
                    [
                        ["put", 1, 1],
                        ["put", 2, 2],
                        ["get", 1],
                        ["put", 3, 3],
                        ["get", 2],
                        ["put", 4, 4],
                        ["get", 1],
                        ["get", 3],
                        ["get", 4],
                    ],
                ),
                expected=[1, -1, -1, 3, 4],
            ),
            CapabilityCase(
                args=(
                    1,
                    [["put", 2, 1], ["get", 2], ["put", 3, 2], ["get", 2], ["get", 3]],
                ),
                expected=[1, -1, 2],
            ),
            CapabilityCase(
                args=(2, [["get", 0]]),
                expected=[-1],
            ),
        ),
        difficulty="hard",
    ),
    CapabilityTask(
        task_id="calculator",
        prompt=(
            "Output ONLY a Python function definition named calculator(expr) that evaluates a "
            "string arithmetic expression containing non-negative integers and the operators "
            "+, -, * (no parentheses, no division), honoring standard operator precedence "
            "(* before + and -) with left-to-right association, ignoring spaces, and returns the "
            "integer result. No prose, no markdown fences, plain code only."
        ),
        entrypoint="calculator",
        cases=(
            CapabilityCase(args=("3+2*2",), expected=7),
            CapabilityCase(args=("1+2*3+4",), expected=11),
            CapabilityCase(args=(" 2*3+5 ",), expected=11),
            CapabilityCase(args=("10-2*3",), expected=4),
            CapabilityCase(args=("100-10-10",), expected=80),
            CapabilityCase(args=("2*2*2*2",), expected=16),
            CapabilityCase(args=("7",), expected=7),
        ),
        difficulty="hard",
    ),
)

_TASKS_BY_ID = {task.task_id: task for task in CAPABILITY_TASKS}

_GRADE_HARNESS = """
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
module = importlib.util.module_from_spec(spec)
results = []
try:
    spec.loader.exec_module(module)
    fn = getattr(module, sys.argv[3])
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"load_error": f"{type(exc).__name__}: {exc}"}))
    sys.exit(0)

with open(sys.argv[2], encoding="utf-8") as handle:
    cases = json.load(handle)

for index, case in enumerate(cases):
    try:
        actual = fn(*case["args"])
        ok = actual == case["expected"]
        results.append({"index": index, "ok": bool(ok), "error": None})
    except Exception as exc:  # noqa: BLE001
        results.append({"index": index, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

print(json.dumps({"results": results}))
"""


def get_task(task_id: str) -> CapabilityTask:
    """Return the capability task with the given id."""
    if task_id not in _TASKS_BY_ID:
        raise KeyError(f"Unknown capability task: {task_id}")
    return _TASKS_BY_ID[task_id]


def extract_code(output: str) -> str:
    """Pull executable Python out of an agent response.

    Handles fenced code blocks and leading/trailing prose. Falls back to the
    text starting at the first import/def/class statement.
    """
    text = output.strip()
    if "```" in text:
        blocks = text.split("```")
        # Odd indices are the fenced contents.
        for block in blocks[1:None:2]:
            body = block
            if "\n" in body:
                first_line, rest = body.split("\n", 1)
                if first_line.strip().lower() in {"python", "py", "python3"}:
                    body = rest
            if any(token in body for token in ("def ", "class ", "import ")):
                return body.strip()

    lines = text.splitlines()
    for start, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(("def ", "class ", "import ", "from ")):
            return "\n".join(lines[start:]).strip()
    return text


def grade_code(task: CapabilityTask, code: str, timeout: float = 20.0) -> dict[str, Any]:
    """Execute candidate code against the task cases in an isolated subprocess."""
    total = len(task.cases)
    if not code.strip():
        return _grade_result(task, passed=0, total=total, error="empty solution", cases=[])

    with tempfile.TemporaryDirectory(prefix="uaek-grade-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        solution_path = tmp_path / "candidate.py"
        cases_path = tmp_path / "cases.json"
        harness_path = tmp_path / "harness.py"
        solution_path.write_text(code, encoding="utf-8")
        cases_payload = [
            {"args": list(case.args), "expected": case.expected} for case in task.cases
        ]
        cases_path.write_text(
            json.dumps(cases_payload),
            encoding="utf-8",
        )
        harness_path.write_text(_GRADE_HARNESS, encoding="utf-8")

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(harness_path),
                    str(solution_path),
                    str(cases_path),
                    task.entrypoint,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _grade_result(
                task, passed=0, total=total, error=f"grading timed out after {timeout:g}s", cases=[]
            )

    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return _grade_result(
            task,
            passed=0,
            total=total,
            error=f"grader produced no JSON (stderr: {completed.stderr.strip()[:200]})",
            cases=[],
        )

    if "load_error" in data:
        return _grade_result(task, passed=0, total=total, error=data["load_error"], cases=[])

    case_results = data.get("results", [])
    passed = sum(1 for item in case_results if item.get("ok"))
    return _grade_result(task, passed=passed, total=total, error=None, cases=case_results)


def _grade_result(
    task: CapabilityTask,
    passed: int,
    total: int,
    error: str | None,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    pass_rate = round(passed / total, 4) if total else 0.0
    return {
        "task_id": task.task_id,
        "entrypoint": task.entrypoint,
        "difficulty": task.difficulty,
        "passed": passed,
        "total": total,
        "pass_rate": pass_rate,
        "status": "pass" if total and passed == total else "fail",
        "cases": cases,
        "error": error,
    }


def compute_capability_score(task_results: list[dict[str, Any]]) -> float:
    """Difficulty-weighted fraction of fully-passed tasks (0..1).

    A hard task fully passed contributes more than an easy one, so the score
    discriminates providers that only clear the easy tier. Falls back to
    weight 1 for any task_result missing a known difficulty.
    """
    total_weight = 0
    earned_weight = 0
    for item in task_results:
        weight = DIFFICULTY_WEIGHTS.get(str(item.get("difficulty", "easy")), 1)
        total_weight += weight
        if item.get("status") == "pass":
            earned_weight += weight
    return round(earned_weight / total_weight, 4) if total_weight else 0.0


def suite_difficulty_summary(
    tasks: tuple[CapabilityTask, ...] = CAPABILITY_TASKS,
) -> dict[str, int]:
    """Count tasks per difficulty tier for the given suite."""
    summary: dict[str, int] = {}
    for task in tasks:
        summary[task.difficulty] = summary.get(task.difficulty, 0) + 1
    return summary


def hardest_tier_passed(task_results: list[dict[str, Any]]) -> str:
    """Return the hardest difficulty tier with at least one fully-passed task."""
    order = ["easy", "medium", "hard"]
    best = ""
    for item in task_results:
        if item.get("status") == "pass":
            tier = str(item.get("difficulty", "easy"))
            if tier in order and order.index(tier) >= (order.index(best) if best else -1):
                best = tier
    return best
