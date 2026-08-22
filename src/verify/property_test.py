"""Property-Based Testing — 基于属性的测试引擎

RESEARCH_PROPOSAL.md 命题2（P1）增强组件：
"Property-Based Testing：随机生成输入，验证不变性属性"

设计目标：
- 自动生成随机输入，测试代码在各种边界条件下的行为
- 验证不变性属性（idempotency, commutativity, round-trip 等）
- 与验证框架集成，作为 VERIFICATION_TYPE 的一种
- 缩小搜索：失败时自动缩小到最小反例
"""

from __future__ import annotations

import operator
import random
import string
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from src.security.python_policy import run_restricted_module_harness

from .interface import VerificationResult, VerificationType


class PropertyType(Enum):
    """属性类型"""

    IDEMPOTENT = "idempotent"  # f(f(x)) == f(x)
    COMMUTATIVE = "commutative"  # f(a, b) == f(b, a)
    ROUND_TRIP = "round_trip"  # decode(encode(x)) == x
    INVARIANT = "invariant"  # 自定义不变性
    SYMMETRIC = "symmetric"  # f(a, b) == f(b, a)
    MONOTONIC = "monotonic"  # a <= b → f(a) <= f(b)
    NO_CRASH = "no_crash"  # 不会崩溃
    ASSOCIATIVE = "associative"  # f(a, f(b, c)) == f(f(a, b), c)


@dataclass
class PropertyTestResult:
    """单个属性测试的运行结果"""

    property_type: PropertyType
    passed: bool
    total_trials: int
    failed_trial: int | None  # 第几次试验失败
    counterexample: Any | None  # 反例
    shrunk_counterexample: Any | None  # 缩小后的最小反例
    duration_ms: float
    evidence: str


@dataclass
class PropertyTestSuiteResult:
    """属性测试套件结果"""

    artifact_path: Path
    function_name: str
    results: list[PropertyTestResult]
    overall_passed: bool
    total_trials: int
    total_duration_ms: float
    summary: str


class InputGenerator:
    """随机输入生成器

    支持多种类型的随机输入生成：
    - int: 整数（正/负/零/边界）
    - float: 浮点数
    - str: 字符串（空/短/长/特殊字符）
    - list: 列表（空/单元素/多元素）
    - dict: 字典
    - bool: 布尔值
    - None: None
    """

    # 边界值（优先尝试）
    EDGE_INTEGERS = [0, 1, -1, 2, -2, 10, -10, 100, -100, 2**31 - 1, -(2**31)]
    EDGE_STRINGS = ["", " ", "a", "ab", "abc", "x" * 100, "x" * 1000, "\\n", "\\t", "null"]
    EDGE_FLOATS = [0.0, 1.0, -1.0, 0.5, -0.5, float("inf"), float("-inf")]

    def __init__(self, seed: int | None = None):
        self._random = random.Random(seed)

    def random_int(self, min_val: int = -1000, max_val: int = 1000) -> int:
        """生成随机整数（20% 概率返回边界值）"""
        if self._random.random() < 0.2:
            return self._random.choice(self.EDGE_INTEGERS)
        return self._random.randint(min_val, max_val)

    def random_float(self) -> float:
        """生成随机浮点数"""
        if self._random.random() < 0.2:
            return self._random.choice(self.EDGE_FLOATS)
        return self._random.uniform(-1000.0, 1000.0)

    def random_string(self, max_len: int = 50) -> str:
        """生成随机字符串"""
        if self._random.random() < 0.2:
            return self._random.choice(self.EDGE_STRINGS)
        length = self._random.randint(0, max_len)
        return "".join(self._random.choices(string.printable, k=length))

    def random_list(self, elem_gen: Callable[[], Any], max_len: int = 20) -> list[Any]:
        """生成随机列表"""
        length = self._random.randint(0, max_len)
        return [elem_gen() for _ in range(length)]

    def random_dict(
        self, key_gen: Callable[[], str], val_gen: Callable[[], Any], max_len: int = 10
    ) -> dict[str, Any]:
        """生成随机字典"""
        length = self._random.randint(0, max_len)
        return {key_gen(): val_gen() for _ in range(length)}

    def random_bool(self) -> bool:
        return self._random.choice([True, False])

    def random_choice(self, choices: list[Any]) -> Any:
        return self._random.choice(choices)


class Shrinker:
    """反例缩小器

    当发现反例时，尝试缩小到最小反例以便调试。
    策略：
    - 整数：逐步向 0 靠近
    - 字符串：逐步缩短
    - 列表：逐步移除元素
    """

    def shrink(self, counterexample: Any, property_fn: Callable[..., bool]) -> Any:
        """缩小反例"""
        if isinstance(counterexample, int):
            return self._shrink_int(counterexample, property_fn)
        elif isinstance(counterexample, str):
            return self._shrink_str(counterexample, property_fn)
        elif isinstance(counterexample, list):
            return self._shrink_list(counterexample, property_fn)
        return counterexample

    def _shrink_int(self, value: int, property_fn: Callable[..., bool]) -> int:
        if value == 0:
            return 0
        direction = -1 if value > 0 else 1
        step = abs(value) // 2
        current = value
        while step > 0:
            candidate = current + direction * step
            if not property_fn(candidate):
                current = candidate
            step //= 2
        return current

    def _shrink_str(self, value: str, property_fn: Callable[..., bool]) -> str:
        current = value
        # 尝试移除后半部分
        while len(current) > 0:
            candidate = current[: len(current) // 2]
            if not property_fn(candidate):
                current = candidate
            else:
                break
        return current

    def _shrink_list(self, value: list[Any], property_fn: Callable[..., bool]) -> list[Any]:
        current = list(value)
        # 尝试移除后半部分元素
        while len(current) > 0:
            candidate = current[: len(current) // 2]
            if not property_fn(candidate):
                current = candidate
            else:
                break
        return current


class PropertyTester:
    """属性测试器

    使用方式：
        tester = PropertyTester(trials=200, seed=42)

        # 测试幂等性
        result = tester.test_idempotent(my_func, input_generator)

        # 测试自定义属性
        result = tester.test_property(
            "my_property",
            lambda x: x == x,  # 属性函数
            input_generator,
        )
    """

    def __init__(self, trials: int = 200, seed: int | None = None, max_shrink_steps: int = 50):
        self.trials = trials
        self.seed = seed
        self.max_shrink_steps = max_shrink_steps
        self.generator = InputGenerator(seed=seed)
        self.shrinker = Shrinker()

    def test_idempotent(
        self,
        func: Callable[[Any], Any],
        input_gen: Callable[[], Any] | None = None,
        eq_check: Callable[[Any, Any], bool] | None = None,
    ) -> PropertyTestResult:
        """测试幂等性：f(f(x)) == f(x)"""
        if input_gen is None:
            input_gen = self.generator.random_int
        if eq_check is None:
            eq_check = operator.eq

        start = time.monotonic()
        for trial in range(self.trials):
            x = input_gen()
            try:
                fx = func(x)
                ffx = func(fx)
                if not eq_check(ffx, fx):
                    shrunk = self.shrinker.shrink(
                        x,
                        lambda v: self._safe_check(func, eq_check, v),
                    )
                    return PropertyTestResult(
                        property_type=PropertyType.IDEMPOTENT,
                        passed=False,
                        total_trials=trial + 1,
                        failed_trial=trial + 1,
                        counterexample=x,
                        shrunk_counterexample=shrunk,
                        duration_ms=(time.monotonic() - start) * 1000,
                        evidence=f"f(f(x)) != f(x) for x={x}, f(x)={fx}, f(f(x))={ffx}",
                    )
            except Exception as e:
                return PropertyTestResult(
                    property_type=PropertyType.IDEMPOTENT,
                    passed=False,
                    total_trials=trial + 1,
                    failed_trial=trial + 1,
                    counterexample=x,
                    shrunk_counterexample=None,
                    duration_ms=(time.monotonic() - start) * 1000,
                    evidence=f"Exception at trial {trial + 1}: {e}",
                )

        return PropertyTestResult(
            property_type=PropertyType.IDEMPOTENT,
            passed=True,
            total_trials=self.trials,
            failed_trial=None,
            counterexample=None,
            shrunk_counterexample=None,
            duration_ms=(time.monotonic() - start) * 1000,
            evidence=f"Passed {self.trials} trials",
        )

    def test_round_trip(
        self,
        encode: Callable[[Any], Any],
        decode: Callable[[Any], Any],
        input_gen: Callable[[], Any] | None = None,
        eq_check: Callable[[Any, Any], bool] | None = None,
    ) -> PropertyTestResult:
        """测试往返属性：decode(encode(x)) == x"""
        if input_gen is None:
            input_gen = self.generator.random_int
        if eq_check is None:
            eq_check = operator.eq

        start = time.monotonic()
        for trial in range(self.trials):
            x = input_gen()
            try:
                encoded = encode(x)
                decoded = decode(encoded)
                if not eq_check(decoded, x):
                    return PropertyTestResult(
                        property_type=PropertyType.ROUND_TRIP,
                        passed=False,
                        total_trials=trial + 1,
                        failed_trial=trial + 1,
                        counterexample=x,
                        shrunk_counterexample=None,
                        duration_ms=(time.monotonic() - start) * 1000,
                        evidence=f"decode(encode(x)) != x for x={x}, "
                        f"encoded={encoded}, decoded={decoded}",
                    )
            except Exception as e:
                return PropertyTestResult(
                    property_type=PropertyType.ROUND_TRIP,
                    passed=False,
                    total_trials=trial + 1,
                    failed_trial=trial + 1,
                    counterexample=x,
                    shrunk_counterexample=None,
                    duration_ms=(time.monotonic() - start) * 1000,
                    evidence=f"Exception at trial {trial + 1}: {e}",
                )

        return PropertyTestResult(
            property_type=PropertyType.ROUND_TRIP,
            passed=True,
            total_trials=self.trials,
            failed_trial=None,
            counterexample=None,
            shrunk_counterexample=None,
            duration_ms=(time.monotonic() - start) * 1000,
            evidence=f"Passed {self.trials} trials",
        )

    def test_commutative(
        self,
        func: Callable[[Any, Any], Any],
        gen_a: Callable[[], Any] | None = None,
        gen_b: Callable[[], Any] | None = None,
        eq_check: Callable[[Any, Any], bool] | None = None,
    ) -> PropertyTestResult:
        """测试交换律：f(a, b) == f(b, a)"""
        if gen_a is None:
            gen_a = self.generator.random_int
        if gen_b is None:
            gen_b = gen_a
        if eq_check is None:
            eq_check = operator.eq

        start = time.monotonic()
        for trial in range(self.trials):
            a = gen_a()
            b = gen_b()
            try:
                fab = func(a, b)
                fba = func(b, a)
                if not eq_check(fab, fba):
                    return PropertyTestResult(
                        property_type=PropertyType.COMMUTATIVE,
                        passed=False,
                        total_trials=trial + 1,
                        failed_trial=trial + 1,
                        counterexample=(a, b),
                        shrunk_counterexample=None,
                        duration_ms=(time.monotonic() - start) * 1000,
                        evidence=f"f(a, b) != f(b, a) for a={a}, b={b}, f(a,b)={fab}, f(b,a)={fba}",
                    )
            except Exception as e:
                return PropertyTestResult(
                    property_type=PropertyType.COMMUTATIVE,
                    passed=False,
                    total_trials=trial + 1,
                    failed_trial=trial + 1,
                    counterexample=(a, b),
                    shrunk_counterexample=None,
                    duration_ms=(time.monotonic() - start) * 1000,
                    evidence=f"Exception at trial {trial + 1}: {e}",
                )

        return PropertyTestResult(
            property_type=PropertyType.COMMUTATIVE,
            passed=True,
            total_trials=self.trials,
            failed_trial=None,
            counterexample=None,
            shrunk_counterexample=None,
            duration_ms=(time.monotonic() - start) * 1000,
            evidence=f"Passed {self.trials} trials",
        )

    def test_no_crash(
        self,
        func: Callable[..., Any],
        input_gen: Callable[[], Any] | None = None,
    ) -> PropertyTestResult:
        """测试不会崩溃属性"""
        if input_gen is None:
            input_gen = self.generator.random_int

        start = time.monotonic()
        for trial in range(self.trials):
            x = input_gen()
            try:
                func(x)
            except Exception as e:
                return PropertyTestResult(
                    property_type=PropertyType.NO_CRASH,
                    passed=False,
                    total_trials=trial + 1,
                    failed_trial=trial + 1,
                    counterexample=x,
                    shrunk_counterexample=None,
                    duration_ms=(time.monotonic() - start) * 1000,
                    evidence=f"Crash at trial {trial + 1} with input {x}: {e}",
                )

        return PropertyTestResult(
            property_type=PropertyType.NO_CRASH,
            passed=True,
            total_trials=self.trials,
            failed_trial=None,
            counterexample=None,
            shrunk_counterexample=None,
            duration_ms=(time.monotonic() - start) * 1000,
            evidence=f"Passed {self.trials} trials (no crashes)",
        )

    def test_custom_property(
        self,
        property_name: str,
        property_fn: Callable[..., bool],
        input_gen: Callable[[], Any] | None = None,
        arity: int = 1,
    ) -> PropertyTestResult:
        """测试自定义属性"""
        if input_gen is None:
            input_gen = self.generator.random_int

        start = time.monotonic()
        for trial in range(self.trials):
            inputs = [input_gen() for _ in range(arity)]
            try:
                if not property_fn(*inputs):
                    return PropertyTestResult(
                        property_type=PropertyType.INVARIANT,
                        passed=False,
                        total_trials=trial + 1,
                        failed_trial=trial + 1,
                        counterexample=inputs if arity > 1 else inputs[0],
                        shrunk_counterexample=None,
                        duration_ms=(time.monotonic() - start) * 1000,
                        evidence=f"Property '{property_name}' failed at trial {trial + 1} "
                        f"with inputs {inputs}",
                    )
            except Exception as e:
                return PropertyTestResult(
                    property_type=PropertyType.INVARIANT,
                    passed=False,
                    total_trials=trial + 1,
                    failed_trial=trial + 1,
                    counterexample=inputs if arity > 1 else inputs[0],
                    shrunk_counterexample=None,
                    duration_ms=(time.monotonic() - start) * 1000,
                    evidence=(
                        f"Property '{property_name}' threw exception at trial {trial + 1}: {e}"
                    ),
                )

        return PropertyTestResult(
            property_type=PropertyType.INVARIANT,
            passed=True,
            total_trials=self.trials,
            failed_trial=None,
            counterexample=None,
            shrunk_counterexample=None,
            duration_ms=(time.monotonic() - start) * 1000,
            evidence=f"Property '{property_name}' passed {self.trials} trials",
        )

    def _safe_check(
        self,
        func: Callable[..., Any],
        eq_check: Callable[[Any, Any], bool],
        x: Any,
    ) -> bool:
        """安全地检查属性（不抛出异常）"""
        try:
            fx = func(x)
            ffx = func(fx)
            return eq_check(ffx, fx)
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# 与验证框架的集成
# --------------------------------------------------------------------------- #

_PROPERTY_HARNESS = """
from src.verify.property_test import PropertyTester, PropertyType

def safe_counterexample(value):
    if value is None or type(value) in (bool, int, float, str):
        return repr(value)[:1000]
    if type(value) in (list, tuple, dict, set):
        return repr(value)[:1000]
    return f"<{type(value).__name__}>"

try:
    namespace = {"__builtins__": SAFE_BUILTINS}
    exec(compile(SOURCE_CODE, "candidate.py", "exec"), namespace)
except Exception as exc:
    print(json.dumps({"load_error": str(exc)}))
else:
    function_name = PAYLOAD["func_name"]
    if function_name not in namespace:
        available = [name for name in namespace if callable(namespace[name])]
        print(json.dumps({"status": "missing", "available": available}))
    elif not callable(namespace[function_name]):
        print(json.dumps({"status": "not_callable"}))
    else:
        function = namespace[function_name]
        tester = PropertyTester(trials=PAYLOAD["trials"], seed=PAYLOAD["seed"])
        results = []
        for requested_type in PAYLOAD["property_types"]:
            if requested_type == PropertyType.IDEMPOTENT.value:
                result = tester.test_idempotent(function)
            elif requested_type == PropertyType.NO_CRASH.value:
                result = tester.test_no_crash(function)
            else:
                continue
            results.append({
                "passed": result.passed,
                "property_type": result.property_type.value,
                "total_trials": result.total_trials,
                "failed_trial": result.failed_trial,
                "counterexample": safe_counterexample(result.counterexample),
                "shrunk_counterexample": safe_counterexample(result.shrunk_counterexample),
            })
        print(json.dumps({"results": results}))
"""


def property_test_verify(
    artifact_path: Path,
    func_name: str,
    property_type: PropertyType | None = None,
    trials: int = 200,
    seed: int = 0,
) -> VerificationResult:
    """从 Python 文件中提取函数并运行属性测试

    集成到验证框架中，作为新的验证类型。
    """
    try:
        code = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Cannot read artifact: {e}",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
            notes=f"Artifact read error: {e}",
        )

    try:
        compile(code, str(artifact_path), "exec")
    except Exception as e:
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Cannot compile code: {e}",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
            notes=f"Compile error: {e}",
        )

    property_types = []
    if property_type is None or property_type == PropertyType.IDEMPOTENT:
        property_types.append(PropertyType.IDEMPOTENT.value)
    if property_type is None or property_type == PropertyType.NO_CRASH:
        property_types.append(PropertyType.NO_CRASH.value)
    process_result = run_restricted_module_harness(
        code,
        _PROPERTY_HARNESS,
        {
            "func_name": func_name,
            "property_types": property_types,
            "trials": trials,
            "seed": seed,
        },
        timeout=5.0,
    )
    if not process_result.success:
        diagnostic = process_result.error or "unknown grader failure"
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Property test policy rejected or execution failed: {diagnostic}",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
            notes=diagnostic,
        )

    payload = process_result.result if isinstance(process_result.result, dict) else {}
    load_error = payload.get("load_error")
    if isinstance(load_error, str):
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"Cannot compile code: {load_error}",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
            notes=f"Compile error: {load_error}",
        )

    status = payload.get("status")
    if status == "missing":
        available = payload.get("available", [])
        return VerificationResult(
            passed=False,
            verdict="INDETERMINATE",
            evidence=f"Function '{func_name}' not found in {artifact_path}",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
            notes=f"Available: {available}",
        )
    if status == "not_callable":
        return VerificationResult(
            passed=False,
            verdict="FAIL",
            evidence=f"'{func_name}' is not callable",
            verification_type=VerificationType.TEST,
            artifact_path=artifact_path,
        )

    raw_results = payload.get("results", [])
    results = raw_results if isinstance(raw_results, list) else []
    all_passed = all(
        isinstance(result, dict) and result.get("passed") is True for result in results
    )
    failed = [
        result
        for result in results
        if isinstance(result, dict) and result.get("passed") is not True
    ]
    passed_count = sum(
        1 for result in results if isinstance(result, dict) and result.get("passed") is True
    )

    return VerificationResult(
        passed=all_passed,
        verdict="PASS" if all_passed else "FAIL",
        evidence=f"Property tests: {passed_count}/{len(results)} passed",
        verification_type=VerificationType.TEST,
        artifact_path=artifact_path,
        notes=(
            f"Failed: {[result.get('property_type') for result in failed]}"
            if failed
            else "All passed"
        ),
    )
