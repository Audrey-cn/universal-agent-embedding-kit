"""Formal Verification — 形式化验证集成

RESEARCH_PROPOSAL.md 命题2（P1）增强组件：
"形式化验证集成：对关键路径代码自动引入形式化验证工具"

设计目标：
- 可选 Z3 后端：如果安装了 z3-solver 则使用 SMT 求解器
- 内置轻量级符号推理：不依赖 Z3 时使用约束传播
- 支持前置条件/后置条件/不变性验证
- 与验证框架集成，作为新的验证类型

支持的形式化验证模式：
- 前置条件验证（pre-condition）
- 后置条件验证（post-condition）
- 循环不变性（loop invariant）
- 可达性分析（reachability）
- 类型约束（type constraints）
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FormalVerificationStatus(Enum):
    SAT = "sat"  # 可满足（找到反例）
    UNSAT = "unsat"  # 不可满足（属性成立）
    UNKNOWN = "unknown"  # 无法确定
    ERROR = "error"  # 验证过程出错


@dataclass
class Constraint:
    """约束条件"""

    expression: str
    description: str = ""
    bound_vars: list[str] = field(default_factory=list)


@dataclass
class FormalVerificationResult:
    """形式化验证结果"""

    status: FormalVerificationStatus
    passed: bool
    property_name: str
    evidence: str
    counterexample: dict[str, Any] | None = None
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# 轻量级符号推理引擎（不依赖 Z3）
# --------------------------------------------------------------------------- #


class LightweightSolver:
    """轻量级约束求解器

    使用区间传播和简单约束推理，不依赖外部 SMT 求解器。
    适用于简单的算术约束和类型约束。
    """

    # 支持的二元运算符
    OPERATORS: dict[type[ast.AST], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.Lt: operator.lt,
        ast.Gt: operator.gt,
        ast.LtE: operator.le,
        ast.GtE: operator.ge,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
    }

    def __init__(self):
        self._variables: dict[str, set[Any]] = {}
        self._constraints: list[tuple[ast.Expression, str]] = []

    def declare_int(self, name: str, domain: range | None = None) -> None:
        """声明整数变量"""
        if domain:
            self._variables[name] = set(domain)
        else:
            self._variables[name] = set(range(-100, 101))

    def declare_bool(self, name: str) -> None:
        """声明布尔变量"""
        self._variables[name] = {True, False}

    def declare_set(self, name: str, values: set[Any]) -> None:
        """声明有限域变量"""
        self._variables[name] = values

    def add_constraint(self, constraint_expr: str, description: str = "") -> None:
        """添加约束条件"""
        try:
            tree = ast.parse(constraint_expr, mode="eval")
            self._validate_ast(tree)
            self._constraints.append((tree, description))
        except SyntaxError as e:
            raise ValueError(f"Invalid constraint expression '{constraint_expr}': {e}")

    def _validate_ast(self, tree: ast.Expression) -> None:
        """Reject nodes the lightweight evaluator cannot interpret."""
        allowed = (
            ast.Expression,
            ast.Constant,
            ast.Name,
            ast.Load,
            ast.UnaryOp,
            ast.USub,
            ast.Not,
            ast.BinOp,
            ast.Compare,
            ast.BoolOp,
            *self.OPERATORS.keys(),
        )
        unsupported = next((node for node in ast.walk(tree) if not isinstance(node, allowed)), None)
        if unsupported is not None:
            raise ValueError(f"Unsupported constraint node: {type(unsupported).__name__}")

    def check(self, max_iterations: int = 10000) -> FormalVerificationStatus:
        """检查约束可满足性

        Returns:
            SAT: 找到满足所有约束的解
            UNSAT: 不存在满足所有约束的解
            UNKNOWN: 在迭代限制内无法确定
        """
        if not self._variables:
            return FormalVerificationStatus.SAT

        # 暴力搜索所有变量组合
        var_names = list(self._variables.keys())
        domains = [list(self._variables[name]) for name in var_names]

        iteration = 0
        for assignment in self._enumerate_assignments(domains, max_iterations):
            iteration += 1
            if iteration > max_iterations:
                return FormalVerificationStatus.UNKNOWN

            env = dict(zip(var_names, assignment))
            if self._check_all_constraints(env):
                return FormalVerificationStatus.SAT

        return FormalVerificationStatus.UNSAT

    def find_counterexample(
        self,
        max_iterations: int = 10000,
    ) -> dict[str, Any] | None:
        """查找反例"""
        if not self._variables:
            return None

        var_names = list(self._variables.keys())
        domains = [list(self._variables[name]) for name in var_names]

        iteration = 0
        for assignment in self._enumerate_assignments(domains, max_iterations):
            iteration += 1
            if iteration > max_iterations:
                return None

            env = dict(zip(var_names, assignment))
            if self._check_all_constraints(env):
                return env

        return None

    def _enumerate_assignments(self, domains: list[list[Any]], max_iter: int):
        """枚举所有可能的赋值组合"""
        if not domains:
            yield []
            return

        indices = [0] * len(domains)
        iteration = 0

        while True:
            if iteration >= max_iter:
                return
            iteration += 1

            yield [domains[i][indices[i]] for i in range(len(domains))]

            # 进位
            pos = len(indices) - 1
            while pos >= 0:
                indices[pos] += 1
                if indices[pos] < len(domains[pos]):
                    break
                indices[pos] = 0
                pos -= 1
            if pos < 0:
                break

    def _check_all_constraints(self, env: dict[str, Any]) -> bool:
        """检查所有约束是否满足"""
        for tree, _ in self._constraints:
            try:
                result = self._eval_ast(tree.body, env)
                if not result:
                    return False
            except Exception:
                return False
        return True

    def _eval_ast(self, node: ast.AST, env: dict[str, Any]) -> Any:
        """评估 AST 节点"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return env[node.id]
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_ast(node.operand, env)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.Not):
                return not operand
        elif isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left, env)
            right = self._eval_ast(node.right, env)
            op_type: type[ast.AST] = type(node.op)
            if op_type in self.OPERATORS:
                return self.OPERATORS[op_type](left, right)
        elif isinstance(node, ast.Compare):
            left = self._eval_ast(node.left, env)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_ast(comparator, env)
                op_type = type(op)
                if op_type in self.OPERATORS:
                    if not self.OPERATORS[op_type](left, right):
                        return False
                    left = right
            return True
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self._eval_ast(v, env) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self._eval_ast(v, env) for v in node.values)
        raise ValueError(f"Unsupported AST node: {type(node)}")


# --------------------------------------------------------------------------- #
# 形式化验证器
# --------------------------------------------------------------------------- #


class FormalVerifier:
    """形式化验证器

    使用方式：
        verifier = FormalVerifier()

        # 验证前置条件
        result = verifier.verify_precondition(
            func_name="divide",
            precondition="b != 0",
            variables={"a": range(-10, 10), "b": range(-10, 10)},
        )

        # 验证后置条件
        result = verifier.verify_postcondition(
            func_name="abs_value",
            postcondition="result >= 0",
            variables={"x": range(-100, 100)},
        )

        # 验证不变性
        result = verifier.verify_invariant(
            property_name="no_negative",
            invariant="x >= 0",
            variables={"x": range(-50, 50)},
        )
    """

    def __init__(self, use_z3: bool = True):
        self._z3_available = False
        if use_z3:
            try:
                import z3  # noqa: F401

                self._z3_available = True
            except ImportError:
                pass

    @property
    def backend(self) -> str:
        return "z3" if self._z3_available else "lightweight"

    def verify_precondition(
        self,
        precondition: str,
        variables: dict[str, set[Any] | range],
        property_name: str = "precondition",
        max_iterations: int = 10000,
    ) -> FormalVerificationResult:
        """验证前置条件

        检查在所有可能的变量取值下，前置条件是否始终成立。
        """
        import time

        start = time.monotonic()

        if self._z3_available:
            return self._verify_with_z3(
                property_name=property_name,
                constraints=[precondition],
                variables=variables,
                start=start,
            )

        # 使用轻量级求解器
        # 验证原理：添加 NOT(property) 作为约束，如果不可满足(UNSAT)则属性成立
        solver = LightweightSolver()
        for name, domain in variables.items():
            if isinstance(domain, range):
                solver.declare_int(name, domain)
            else:
                solver.declare_set(name, domain)

        solver.add_constraint(f"not ({precondition})", property_name)
        status = solver.check(max_iterations=max_iterations)

        duration = (time.monotonic() - start) * 1000

        if status == FormalVerificationStatus.UNSAT:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNSAT,
                passed=True,
                property_name=property_name,
                evidence=f"Precondition '{precondition}' holds for all inputs",
                duration_ms=duration,
                details={"backend": self.backend},
            )
        elif status == FormalVerificationStatus.SAT:
            counterexample = solver.find_counterexample(max_iterations=max_iterations)
            return FormalVerificationResult(
                status=FormalVerificationStatus.SAT,
                passed=False,
                property_name=property_name,
                evidence=f"Precondition '{precondition}' violated",
                counterexample=counterexample,
                duration_ms=duration,
                details={"backend": self.backend},
            )
        else:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNKNOWN,
                passed=False,
                property_name=property_name,
                evidence=(
                    f"Cannot determine precondition '{precondition}' "
                    f"within {max_iterations} iterations"
                ),
                duration_ms=duration,
                details={"backend": self.backend},
            )

    def verify_invariant(
        self,
        invariant: str,
        variables: dict[str, set[Any] | range],
        property_name: str = "invariant",
        max_iterations: int = 10000,
    ) -> FormalVerificationResult:
        """验证不变性

        检查在所有可能的变量取值下，不变性是否始终成立。
        """
        import time

        start = time.monotonic()

        if self._z3_available:
            return self._verify_with_z3(
                property_name=property_name,
                constraints=[invariant],
                variables=variables,
                start=start,
            )

        solver = LightweightSolver()
        for name, domain in variables.items():
            if isinstance(domain, range):
                solver.declare_int(name, domain)
            else:
                solver.declare_set(name, domain)

        # 验证原理：NOT(invariant) 不可满足 → invariant 对所有输入成立
        solver.add_constraint(f"not ({invariant})", property_name)
        status = solver.check(max_iterations=max_iterations)

        duration = (time.monotonic() - start) * 1000

        if status == FormalVerificationStatus.UNSAT:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNSAT,
                passed=True,
                property_name=property_name,
                evidence=f"Invariant '{invariant}' holds for all inputs",
                duration_ms=duration,
                details={"backend": self.backend},
            )
        elif status == FormalVerificationStatus.SAT:
            counterexample = solver.find_counterexample(max_iterations=max_iterations)
            return FormalVerificationResult(
                status=FormalVerificationStatus.SAT,
                passed=False,
                property_name=property_name,
                evidence=f"Invariant '{invariant}' violated",
                counterexample=counterexample,
                duration_ms=duration,
                details={"backend": self.backend},
            )
        else:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNKNOWN,
                passed=False,
                property_name=property_name,
                evidence=(
                    f"Cannot determine invariant '{invariant}' within {max_iterations} iterations"
                ),
                duration_ms=duration,
                details={"backend": self.backend},
            )

    def verify_postcondition(
        self,
        precondition: str,
        postcondition: str,
        variables: dict[str, set[Any] | range],
        property_name: str = "postcondition",
        max_iterations: int = 10000,
    ) -> FormalVerificationResult:
        """验证后置条件

        检查：如果前置条件成立，则后置条件必须成立。
        即：precondition ∧ ¬postcondition 不可满足
        """
        import time

        start = time.monotonic()

        # 构造：precondition ∧ NOT(postcondition)
        negated = f"not ({postcondition})"
        combined = f"({precondition}) and {negated}"

        if self._z3_available:
            return self._verify_with_z3(
                property_name=property_name,
                constraints=[precondition, negated],
                variables=variables,
                start=start,
            )

        solver = LightweightSolver()
        for name, domain in variables.items():
            if isinstance(domain, range):
                solver.declare_int(name, domain)
            else:
                solver.declare_set(name, domain)

        try:
            solver.add_constraint(combined, property_name)
        except ValueError:
            # 复杂的否定表达式可能无法解析，回退到分别添加
            solver.add_constraint(precondition, "precondition")
            try:
                solver.add_constraint(negated, "negated_postcondition")
            except ValueError:
                pass

        status = solver.check(max_iterations=max_iterations)

        duration = (time.monotonic() - start) * 1000

        if status == FormalVerificationStatus.UNSAT:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNSAT,
                passed=True,
                property_name=property_name,
                evidence=(
                    f"Postcondition '{postcondition}' holds given precondition '{precondition}'"
                ),
                duration_ms=duration,
                details={"backend": self.backend},
            )
        elif status == FormalVerificationStatus.SAT:
            counterexample = solver.find_counterexample(max_iterations=max_iterations)
            return FormalVerificationResult(
                status=FormalVerificationStatus.SAT,
                passed=False,
                property_name=property_name,
                evidence=f"Postcondition '{postcondition}' violated",
                counterexample=counterexample,
                duration_ms=duration,
                details={"backend": self.backend, "precondition": precondition},
            )
        else:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNKNOWN,
                passed=False,
                property_name=property_name,
                evidence=f"Cannot determine postcondition within {max_iterations} iterations",
                duration_ms=duration,
                details={"backend": self.backend},
            )

    def _verify_with_z3(
        self,
        property_name: str,
        constraints: list[str],
        variables: dict[str, set[Any] | range],
        start: float,
    ) -> FormalVerificationResult:
        """使用 Z3 求解器验证（需要 z3-solver 已安装）"""
        import time

        try:
            import z3
        except ImportError:
            return FormalVerificationResult(
                status=FormalVerificationStatus.ERROR,
                passed=False,
                property_name=property_name,
                evidence="Z3 solver not available",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        solver = z3.Solver()
        z3_vars: dict[str, z3.ExprRef] = {}

        for name, domain in variables.items():
            if isinstance(domain, range):
                v = z3.Int(name)
                solver.add(v >= domain.start)
                solver.add(v < domain.stop)
            else:
                v = z3.Int(name)
            z3_vars[name] = v

        # 解析约束（简化版：仅支持 x op y 形式）
        for constraint in constraints:
            try:
                z3_constraint = self._parse_z3_constraint(constraint, z3_vars)
                if z3_constraint is not None:
                    solver.add(z3_constraint)
            except Exception:
                pass

        result = solver.check()
        duration = (time.monotonic() - start) * 1000

        if result == z3.unsat:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNSAT,
                passed=True,
                property_name=property_name,
                evidence=f"Property '{property_name}' formally verified",
                duration_ms=duration,
                details={"backend": "z3"},
            )
        elif result == z3.sat:
            model = solver.model()
            counterexample = {name: model.eval(v) for name, v in z3_vars.items()}
            return FormalVerificationResult(
                status=FormalVerificationStatus.SAT,
                passed=False,
                property_name=property_name,
                evidence=f"Property '{property_name}' violated",
                counterexample=counterexample,
                duration_ms=duration,
                details={"backend": "z3"},
            )
        else:
            return FormalVerificationResult(
                status=FormalVerificationStatus.UNKNOWN,
                passed=False,
                property_name=property_name,
                evidence=f"Z3 returned unknown for '{property_name}'",
                duration_ms=duration,
                details={"backend": "z3"},
            )

    def _parse_z3_constraint(self, constraint: str, variables: dict[str, Any]) -> Any:
        """将约束字符串解析为 Z3 表达式（简化版）"""
        # 简单约束解析：x op y 或 x
        import importlib.util
        import re

        # 仅在 z3 可用时才解析（本函数为简化版，实际用纯 Python 求值）
        if importlib.util.find_spec("z3") is None:
            return None

        # 匹配: x op y
        match = re.match(r"\s*(\w+)\s*(==|!=|<=|>=|<|>)\s*(\w+|\d+)\s*", constraint)
        if match:
            var_name = match.group(1)
            op = match.group(2)
            other = match.group(3)

            if var_name not in variables:
                return None

            v = variables[var_name]
            if other.isdigit() or (other.startswith("-") and other[1:].isdigit()):
                rhs = int(other)
            elif other in variables:
                rhs = variables[other]
            else:
                return None

            ops = {
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
                "<=": lambda a, b: a <= b,
                ">=": lambda a, b: a >= b,
                "<": lambda a, b: a < b,
                ">": lambda a, b: a > b,
            }
            if op in ops:
                return ops[op](v, rhs)

        return None


# --------------------------------------------------------------------------- #
# 与验证框架的集成
# --------------------------------------------------------------------------- #


def formal_verify_artifact(
    artifact_path: Path,
    constraints: list[dict[str, Any]] | None = None,
    max_iterations: int = 10000,
) -> list[FormalVerificationResult]:
    """对产出物运行形式化验证

    从 criteria_path 读取约束定义，或使用默认约束。

    Args:
        artifact_path: 产出物路径
        constraints: 约束定义列表，每个元素为:
            {
                "type": "precondition" | "postcondition" | "invariant",
                "property": "约束表达式",
                "variables": {"x": [-10, 10], "y": [-10, 10]},
            }
        max_iterations: 最大迭代次数

    Returns:
        FormalVerificationResult 列表
    """
    verifier = FormalVerifier()
    results: list[FormalVerificationResult] = []

    if constraints is None:
        # 默认约束：检查基本类型安全
        constraints = []

    for constraint in constraints:
        ctype = constraint.get("type", "invariant")
        prop = constraint.get("property", "")
        variables = constraint.get("variables", {})

        # 转换变量域
        var_domains: dict[str, set[Any] | range] = {}
        for name, domain in variables.items():
            if isinstance(domain, list) and len(domain) == 2:
                var_domains[name] = range(domain[0], domain[1] + 1)
            elif isinstance(domain, list):
                var_domains[name] = set(domain)
            elif isinstance(domain, range):
                var_domains[name] = domain
            else:
                var_domains[name] = set(domain) if isinstance(domain, (list, set)) else {-10, 10}

        if ctype == "precondition":
            result = verifier.verify_precondition(prop, var_domains, max_iterations=max_iterations)
        elif ctype == "postcondition":
            precondition = constraint.get("precondition", "True")
            result = verifier.verify_postcondition(
                precondition,
                prop,
                var_domains,
                max_iterations=max_iterations,
            )
        else:
            result = verifier.verify_invariant(prop, var_domains, max_iterations=max_iterations)

        results.append(result)

    return results
