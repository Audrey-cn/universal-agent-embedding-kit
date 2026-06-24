"""Auto-gradable code-task suite for cross-platform capability comparison.

Each task ships a natural-language prompt (sent to an external Agent) and a set
of deterministic assertion cases. A candidate solution is graded objectively by
executing it in an isolated subprocess against the cases — no model self-grading.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
from collections import OrderedDict
from collections.abc import Callable
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


# --------------------------------------------------------------------------- #
# Held-out / metamorphic grading
#
# The fixed ``cases`` above are a small public set; a solution that hardcodes a
# lookup keyed on those exact inputs would pass them while being non-general.
# For each task we keep a trusted reference oracle plus an input sampler. At
# grade time we draw deterministic-but-prompt-unseen inputs, compute the
# expected output with the reference (in the trusted parent process), and grade
# the candidate against them too. A hardcoded lookup fails the held-out inputs.
# Seeds are fixed per task so the suite stays reproducible; the inputs are never
# shown to the provider, so they still test generalization beyond the prompt.
# --------------------------------------------------------------------------- #
HELD_OUT_COUNT = 16


def _int_to_roman(n: int) -> str:
    table = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
        (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    out: list[str] = []
    for value, symbol in table:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)


def _ref_two_sum(nums: list[int], target: int) -> list[int]:
    seen: dict[int, int] = {}
    for i, num in enumerate(nums):
        if target - num in seen:
            return [seen[target - num], i]
        seen[num] = i
    return []


def _ref_is_palindrome(s: str) -> bool:
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]


def _ref_fizzbuzz(n: int) -> str:
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)


def _ref_max_subarray(nums: list[int]) -> int:
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best


def _ref_roman_to_int(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = vals[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def _ref_valid_parentheses(s: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


def _ref_longest_unique_substring(s: str) -> int:
    last: dict[str, int] = {}
    start = 0
    best = 0
    for i, ch in enumerate(s):
        if ch in last and last[ch] >= start:
            start = last[ch] + 1
        last[ch] = i
        best = max(best, i - start + 1)
    return best


def _ref_edit_distance(a: str, b: str) -> int:
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return dp[n]


def _ref_lru_cache_sim(capacity: int, ops: list[list[Any]]) -> list[int]:
    cache: OrderedDict[Any, Any] = OrderedDict()
    out: list[int] = []
    for op in ops:
        if op[0] == "put":
            _, key, value = op
            if key in cache:
                cache.move_to_end(key)
            cache[key] = value
            if len(cache) > capacity:
                cache.popitem(last=False)
        else:
            _, key = op
            if key in cache:
                cache.move_to_end(key)
                out.append(cache[key])
            else:
                out.append(-1)
    return out


def _ref_calculator(expr: str) -> int:
    s = expr.replace(" ", "")
    stack: list[int] = []
    num = 0
    op = "+"
    for i, ch in enumerate(s):
        if ch.isdigit():
            num = num * 10 + int(ch)
        if ch in "+-*" or i == len(s) - 1:
            if op == "+":
                stack.append(num)
            elif op == "-":
                stack.append(-num)
            elif op == "*":
                stack.append(stack.pop() * num)
            op = ch
            num = 0
    return sum(stack)


def _sample_two_sum(rng: random.Random) -> tuple[Any, ...]:
    # Powers of 3 give every pair a distinct sum, so the target identifies a
    # unique pair and the candidate's indices must match the reference's.
    k = rng.randint(4, 8)
    values = [3**i for i in range(k)]
    rng.shuffle(values)
    i, j = sorted(rng.sample(range(k), 2))
    return (values, values[i] + values[j])


def _sample_is_palindrome(rng: random.Random) -> tuple[Any, ...]:
    alpha = "abcABC123 ,:!"
    if rng.random() < 0.5:
        half = [rng.choice(alpha) for _ in range(rng.randint(1, 6))]
        return ("".join(half + half[::-1]),)
    return ("".join(rng.choice(alpha) for _ in range(rng.randint(1, 12))),)


def _sample_fizzbuzz(rng: random.Random) -> tuple[Any, ...]:
    return (rng.randint(1, 10000),)


def _sample_max_subarray(rng: random.Random) -> tuple[Any, ...]:
    return ([rng.randint(-20, 20) for _ in range(rng.randint(1, 12))],)


def _sample_roman_to_int(rng: random.Random) -> tuple[Any, ...]:
    return (_int_to_roman(rng.randint(1, 3999)),)


def _sample_valid_parentheses(rng: random.Random) -> tuple[Any, ...]:
    return ("".join(rng.choice("()[]{}") for _ in range(rng.randint(0, 12))),)


def _sample_longest_unique_substring(rng: random.Random) -> tuple[Any, ...]:
    return ("".join(rng.choice("abcd") for _ in range(rng.randint(0, 15))),)


def _sample_edit_distance(rng: random.Random) -> tuple[Any, ...]:
    def word() -> str:
        return "".join(rng.choice("abc") for _ in range(rng.randint(0, 7)))

    return (word(), word())


def _sample_lru_cache_sim(rng: random.Random) -> tuple[Any, ...]:
    cap = rng.randint(1, 3)
    ops: list[list[Any]] = []
    for _ in range(rng.randint(3, 12)):
        if rng.random() < 0.5:
            ops.append(["put", rng.randint(0, 4), rng.randint(0, 9)])
        else:
            ops.append(["get", rng.randint(0, 4)])
    return (cap, ops)


def _sample_calculator(rng: random.Random) -> tuple[Any, ...]:
    parts = [str(rng.randint(0, 20))]
    for _ in range(rng.randint(1, 5)):
        parts.append(rng.choice("+-*"))
        parts.append(str(rng.randint(0, 20)))
    return ("".join(parts),)


# task_id -> (reference oracle, input sampler)
_Reference = Callable[..., Any]
_Sampler = Callable[[random.Random], tuple[Any, ...]]
_HELD_OUT_ORACLES: dict[str, tuple[_Reference, _Sampler]] = {
    "two_sum": (_ref_two_sum, _sample_two_sum),
    "is_palindrome": (_ref_is_palindrome, _sample_is_palindrome),
    "fizzbuzz": (_ref_fizzbuzz, _sample_fizzbuzz),
    "max_subarray": (_ref_max_subarray, _sample_max_subarray),
    "roman_to_int": (_ref_roman_to_int, _sample_roman_to_int),
    "valid_parentheses": (_ref_valid_parentheses, _sample_valid_parentheses),
    "longest_unique_substring": (_ref_longest_unique_substring, _sample_longest_unique_substring),
    "edit_distance": (_ref_edit_distance, _sample_edit_distance),
    "lru_cache_sim": (_ref_lru_cache_sim, _sample_lru_cache_sim),
    "calculator": (_ref_calculator, _sample_calculator),
}


def held_out_cases(task: CapabilityTask, count: int = HELD_OUT_COUNT) -> tuple[CapabilityCase, ...]:
    """Deterministic prompt-unseen cases drawn from the task's reference oracle.

    Returns an empty tuple for tasks with no registered oracle (e.g. ad-hoc test
    fixtures). Seeded per task id so the suite is reproducible.
    """
    oracle = _HELD_OUT_ORACLES.get(task.task_id)
    if oracle is None or count <= 0:
        return ()
    reference, sampler = oracle
    rng = random.Random(f"uaek-held-out:{task.task_id}")
    cases: list[CapabilityCase] = []
    for _ in range(count):
        args = sampler(rng)
        cases.append(CapabilityCase(args=tuple(args), expected=reference(*args)))
    return tuple(cases)


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


def grade_code(
    task: CapabilityTask, code: str, timeout: float = 20.0, held_out: int = HELD_OUT_COUNT
) -> dict[str, Any]:
    """Execute candidate code against public + held-out cases in a subprocess.

    Grading spans the fixed public ``cases`` plus ``held_out`` deterministic
    prompt-unseen cases from the task's reference oracle, so a solution that
    overfits a lookup to the public inputs fails. Pass ``held_out=0`` to grade
    against only the public cases (legacy behaviour).
    """
    all_cases = task.cases + held_out_cases(task, held_out)
    total = len(all_cases)
    if not code.strip():
        return _grade_result(task, passed=0, total=total, error="empty solution", cases=[])

    with tempfile.TemporaryDirectory(prefix="uaek-grade-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        solution_path = tmp_path / "candidate.py"
        cases_path = tmp_path / "cases.json"
        harness_path = tmp_path / "harness.py"
        solution_path.write_text(code, encoding="utf-8")
        cases_payload = [
            {"args": list(case.args), "expected": case.expected} for case in all_cases
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
