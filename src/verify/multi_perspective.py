"""Multi-Perspective Consistency Check Engine — 多视角一致性检查引擎

RESEARCH_PROPOSAL.md 命题2（P0）核心组件：
"多视角一致性检查：同一结果从 3+ 个不同角度验证
（功能正确性、边界情况、安全性、可维护性）"

设计目标：
- 将自评分作弊率从 47-74% 降至 <10%
- 多个独立视角交叉验证，任何一个视角失败即整体失败
- 防止单一视角的盲点导致漏检
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Perspective(Enum):
    """验证视角"""
    CORRECTNESS = "correctness"     # 功能正确性
    BOUNDARY = "boundary"           # 边界情况
    SECURITY = "security"           # 安全性
    MAINTAINABILITY = "maintainability"  # 可维护性
    PERFORMANCE = "performance"     # 性能
    COMPATIBILITY = "compatibility" # 兼容性
    USABILITY = "usability"         # 可用性


@dataclass
class PerspectiveResult:
    """单个视角的验证结果"""
    perspective: Perspective
    passed: bool
    score: float  # 0.0 - 1.0
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class MultiPerspectiveResult:
    """多视角一致性检查结果"""
    artifact_path: Path
    criteria_path: Path | None
    perspectives: list[PerspectiveResult]
    overall_passed: bool
    overall_score: float  # 加权平均分
    consensus_level: str  # "strong" / "moderate" / "weak" / "conflict"
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed_perspectives(self) -> list[PerspectiveResult]:
        return [p for p in self.perspectives if not p.passed]

    @property
    def passed_perspectives(self) -> list[PerspectiveResult]:
        return [p for p in self.perspectives if p.passed]


class MultiPerspectiveChecker:
    """多视角一致性检查器

    整合多个独立视角，对同一产出物进行交叉验证。
    每个视角的检查逻辑是独立的，不共享上下文，防止"共享盲点"。

    使用方式：
        checker = MultiPerspectiveChecker()
        checker.register_perspective(Perspective.CORRECTNESS, my_correctness_fn)
        result = checker.check(artifact_path, criteria_path)
    """

    def __init__(self, strict_mode: bool = True):
        self._checkers: dict[Perspective, Callable] = {}
        self._perspective_weights: dict[Perspective, float] = {
            Perspective.CORRECTNESS: 0.30,
            Perspective.BOUNDARY: 0.25,
            Perspective.SECURITY: 0.20,
            Perspective.MAINTAINABILITY: 0.15,
            Perspective.PERFORMANCE: 0.05,
            Perspective.COMPATIBILITY: 0.03,
            Perspective.USABILITY: 0.02,
        }
        self.strict_mode = strict_mode  # strict=True: 任何视角失败即整体失败

    def register_perspective(
        self,
        perspective: Perspective,
        checker_fn: Callable[[Path, Path | None], PerspectiveResult],
        weight: float | None = None,
    ) -> None:
        """注册一个视角的检查函数"""
        self._checkers[perspective] = checker_fn
        if weight is not None:
            self._perspective_weights[perspective] = weight

    def check(
        self,
        artifact_path: Path,
        criteria_path: Path | None = None,
        perspectives: list[Perspective] | None = None,
    ) -> MultiPerspectiveResult:
        """运行多视角一致性检查

        Args:
            artifact_path: 产出物路径
            criteria_path: 验收标准路径
            perspectives: 要运行的视角列表（默认：所有已注册的视角）

        Returns:
            MultiPerspectiveResult: 多视角检查结果
        """
        import time

        to_check = perspectives or list(self._checkers.keys())
        results: list[PerspectiveResult] = []

        for perspective in to_check:
            if perspective not in self._checkers:
                results.append(PerspectiveResult(
                    perspective=perspective,
                    passed=False,
                    score=0.0,
                    evidence=f"No checker registered for {perspective.value}",
                ))
                continue

            start = time.monotonic()
            try:
                result = self._checkers[perspective](artifact_path, criteria_path)
                result.duration_ms = (time.monotonic() - start) * 1000
                results.append(result)
            except Exception as e:
                results.append(PerspectiveResult(
                    perspective=perspective,
                    passed=False,
                    score=0.0,
                    evidence=f"Checker error: {e}",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))

        # 计算整体结果
        return self._aggregate(results, artifact_path, criteria_path)

    def _aggregate(
        self,
        results: list[PerspectiveResult],
        artifact_path: Path,
        criteria_path: Path | None,
    ) -> MultiPerspectiveResult:
        """聚合多视角结果"""
        if not results:
            return MultiPerspectiveResult(
                artifact_path=artifact_path,
                criteria_path=criteria_path,
                perspectives=[],
                overall_passed=False,
                overall_score=0.0,
                consensus_level="weak",
                summary="No perspectives checked",
            )

        # 加权平均分
        total_weight = 0.0
        weighted_score = 0.0
        for r in results:
            w = self._perspective_weights.get(r.perspective, 0.1)
            total_weight += w
            weighted_score += r.score * w
        overall_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 是否全部通过
        if self.strict_mode:
            overall_passed = all(r.passed for r in results)
        else:
            # 宽松模式：关键视角（正确性+安全性）必须通过
            critical = {Perspective.CORRECTNESS, Perspective.SECURITY}
            critical_results = [r for r in results if r.perspective in critical]
            overall_passed = (
                all(r.passed for r in critical_results) if critical_results
                else sum(1 for r in results if r.passed) >= len(results) * 0.7
            )

        # 一致性级别
        passed_count = sum(1 for r in results if r.passed)
        total = len(results)
        if passed_count == total:
            consensus_level = "strong"
        elif passed_count >= total * 0.75:
            consensus_level = "moderate"
        elif passed_count >= total * 0.5:
            consensus_level = "weak"
        else:
            consensus_level = "conflict"

        # 生成摘要
        failed = [r for r in results if not r.passed]
        summary_parts = [
            f"Multi-perspective check: {passed_count}/{total} passed",
            f"Overall score: {overall_score:.2%}",
            f"Consensus: {consensus_level}",
        ]
        if failed:
            failed_names = [f.perspective.value for f in failed]
            summary_parts.append(f"Failed: {', '.join(failed_names)}")

        return MultiPerspectiveResult(
            artifact_path=artifact_path,
            criteria_path=criteria_path,
            perspectives=results,
            overall_passed=overall_passed,
            overall_score=overall_score,
            consensus_level=consensus_level,
            summary=" | ".join(summary_parts),
            metadata={
                "strict_mode": self.strict_mode,
                "total_perspectives": total,
                "passed_count": passed_count,
                "weights": {k.value: v for k, v in self._perspective_weights.items()},
            },
        )


# --------------------------------------------------------------------------- #
# 内置视角检查函数
# --------------------------------------------------------------------------- #

def _check_correctness(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """功能正确性检查：通过语法/结构分析验证代码基本正确性"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.CORRECTNESS, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0

    # Python 语法检查
    if artifact_path.suffix == ".py":
        try:
            compile(content, str(artifact_path), "exec")
            checks.append({"check": "python_syntax", "passed": True})
        except SyntaxError as e:
            checks.append({"check": "python_syntax", "passed": False, "error": str(e)})
            score -= 0.4

        # 检查是否有明显的运行时错误
        if "import" in content and "ImportError" not in content:
            checks.append({"check": "has_imports", "passed": True})
        if "def " in content or "class " in content:
            checks.append({"check": "has_definitions", "passed": True})

    # 通用检查：文件非空
    if len(content.strip()) == 0:
        checks.append({"check": "non_empty", "passed": False})
        score -= 0.5
    else:
        checks.append({"check": "non_empty", "passed": True})

    passed = score >= 0.5
    return PerspectiveResult(
        perspective=Perspective.CORRECTNESS,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Syntax check: {'PASS' if passed else 'FAIL'}",
        details={"checks": checks},
    )


def _check_boundary(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """边界情况检查：检测代码中的边界处理"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.BOUNDARY, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0
    lines = content.splitlines()

    # 检查空输入处理
    has_empty_check = any(
        kw in content.lower()
        for kw in ["if not", "if len(", "if .* is none", "if .* == \"\"", "if .* == []"]
    )
    checks.append({"check": "empty_input_handling", "passed": has_empty_check})
    if not has_empty_check and len(lines) > 5:
        score -= 0.15

    # 检查边界值处理（min/max/range）
    has_boundary = any(
        kw in content.lower()
        for kw in ["min(", "max(", "range(", "if .* < 0", "if .* <= 0", "if .* > "]
    )
    checks.append({"check": "boundary_value_handling", "passed": has_boundary})
    if not has_boundary and len(lines) > 10:
        score -= 0.1

    # 检查异常处理
    has_exception = any(
        kw in content for kw in ["try:", "except", "raise ", "ValueError", "TypeError"]
    )
    checks.append({"check": "exception_handling", "passed": has_exception})
    if not has_exception and len(lines) > 20:
        score -= 0.1

    passed = score >= 0.6
    return PerspectiveResult(
        perspective=Perspective.BOUNDARY,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Boundary checks: {sum(1 for c in checks if c['passed'])}/{len(checks)} passed",
        details={"checks": checks},
    )


def _check_security(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """安全性检查：检测代码中的安全风险"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.SECURITY, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0

    # 危险模式检测
    dangerous_patterns = {
        "eval(": "Use of eval() is dangerous",
        "exec(": "Use of exec() is dangerous",
        "__import__(": "Dynamic imports are risky",
        "subprocess.call": "Subprocess calls should be sandboxed",
        "os.system(": "Shell execution is dangerous",
        "pickle.loads": "Unsafe deserialization",
        "shell=True": "Shell=True in subprocess is dangerous",
        "password": "Hardcoded password may be present",
        "secret": "Hardcoded secret may be present",
        "token": "Hardcoded token may be present",
    }

    found_dangerous = []
    for pattern, description in dangerous_patterns.items():
        if pattern in content:
            found_dangerous.append({"pattern": pattern, "description": description})
            score -= 0.15

    checks.append({
        "check": "dangerous_patterns",
        "passed": len(found_dangerous) == 0,
        "details": found_dangerous,
    })

    # 检查是否有输入验证
    has_input_validation = any(
        kw in content.lower()
        for kw in ["isinstance(", "assert ", "if not isinstance", ".isdigit(", ".strip()"]
    )
    checks.append({"check": "input_validation", "passed": has_input_validation})
    if not has_input_validation:
        score -= 0.1

    # 检查是否使用了安全的比较方式
    has_safe_compare = "compare_digest" in content or "secrets." in content
    checks.append({"check": "safe_comparison", "passed": has_safe_compare})
    # 不强制扣分，但记录

    passed = score >= 0.5
    return PerspectiveResult(
        perspective=Perspective.SECURITY,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Security: {len(found_dangerous)} dangerous patterns, "
                 f"input_validation={'yes' if has_input_validation else 'no'}",
        details={"checks": checks, "dangerous_found": found_dangerous},
    )


def _check_maintainability(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """可维护性检查：代码质量、文档、结构"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.MAINTAINABILITY, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0
    lines = content.splitlines()

    # 文件长度检查
    if len(lines) > 500:
        checks.append({"check": "file_length", "passed": False, "detail": f"{len(lines)} lines"})
        score -= 0.1
    else:
        checks.append({"check": "file_length", "passed": True})

    # 函数长度检查（粗略：连续缩进行）
    long_blocks = 0
    current_block = 0
    for line in lines:
        if line.startswith((" ", "\t")):
            current_block += 1
        else:
            if current_block > 50:
                long_blocks += 1
            current_block = 0
    checks.append({"check": "long_function_blocks", "passed": long_blocks == 0})
    if long_blocks > 0:
        score -= 0.1 * min(long_blocks, 3)

    # 注释比例检查
    comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
    comment_ratio = comment_lines / max(1, len(lines))
    checks.append({"check": "comment_ratio", "passed": comment_ratio >= 0.05})
    if comment_ratio < 0.05 and len(lines) > 20:
        score -= 0.1

    # 检查是否有 docstring
    has_docstring = '"""' in content or "'''" in content
    checks.append({"check": "has_docstring", "passed": has_docstring})
    if not has_docstring and len(lines) > 10:
        score -= 0.05

    passed = score >= 0.6
    return PerspectiveResult(
        perspective=Perspective.MAINTAINABILITY,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Maintainability: comment_ratio={comment_ratio:.1%}, "
                 f"long_blocks={long_blocks}, lines={len(lines)}",
        details={"checks": checks},
    )


def _check_performance(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """性能检查：检测代码中的性能反模式"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.PERFORMANCE, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0
    lines = content.splitlines()

    # 检测性能反模式
    anti_patterns = {
        "O(n^2)": [
            "for .* in .*:\n.*for .* in",
            "nested.*loop",
            "双重循环",
        ],
        "unbounded_growth": [
            "while True",
            "while 1",
            "while not .*break",
            "无限循环",
        ],
        "large_list_comprehension": [
            "list(",
            ".append(",
        ],
        "repeated_io": [
            "for .* in .*:\n.*open(",
            "for .* in .*:\n.*read(",
            "循环.*读取",
        ],
        "string_concat_in_loop": [
            "s += ",
            "str += ",
            "字符串拼接.*循环",
        ],
        "repeated_regex_compile": [
            "re.compile(",
            "re.match(",
        ],
        "global_variable": [
            "global ",
            "全局变量",
        ],
    }

    found_anti_patterns = []
    for pattern_name, indicators in anti_patterns.items():
        for indicator in indicators:
            if indicator.lower() in content.lower():
                found_anti_patterns.append(pattern_name)
                score -= 0.08
                break

    # 检查是否有 I/O 缓存/批处理
    has_batch_io = any(
        kw in content.lower()
        for kw in ["buffered", "chunk", ".readlines(", "batch", "cursor", "yield"]
    )
    checks.append({"check": "batch_io_handling", "passed": has_batch_io})
    if not has_batch_io and len(lines) > 30:
        score -= 0.05

    # 检查是否使用了高效数据结构
    has_efficient_structures = any(
        kw in content.lower()
        for kw in ["set(", "dict(", "deque", "defaultdict", "counter", "heapq", "bisect"]
    )
    checks.append({"check": "efficient_structures", "passed": has_efficient_structures})

    passed = score >= 0.5
    return PerspectiveResult(
        perspective=Perspective.PERFORMANCE,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Performance: {len(found_anti_patterns)} anti-patterns found"
                 + (f": {', '.join(found_anti_patterns)}" if found_anti_patterns else ""),
        details={"checks": checks, "anti_patterns": found_anti_patterns},
    )


def _check_compatibility(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """兼容性检查：检测跨平台/跨版本兼容性问题"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.COMPATIBILITY, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0

    # 检测平台特定代码
    platform_specific = {
        "os.system": "Shell execution is platform-dependent",
        "subprocess.call": "Subprocess behavior varies across platforms",
        "os.sep": "Path separator is platform-specific",
        "\\\\": "Windows-style path separator in Python",
        "os.path.join": "Manual path joining (use pathlib)",
        "signal.SIGKILL": "SIGKILL not available on Windows",
        "os.fork": "fork() not available on Windows",
        "fcntl": "fcntl module not available on Windows",
        "resource.setrlimit": "resource module varies across platforms",
        "sys.platform": "Platform-specific code path",
        "win32": "Windows-specific API",
        "darwin": "macOS-specific code",
        "linux": "Linux-specific code",
    }

    found_platform = []
    for pattern, desc in platform_specific.items():
        if pattern in content:
            found_platform.append({"pattern": pattern, "description": desc})
            score -= 0.1

    checks.append({
        "check": "platform_specific_code",
        "passed": len(found_platform) == 0,
        "details": found_platform,
    })

    # 检查 Python 版本兼容性
    uses_py310 = "match " in content and "case " in content
    uses_py310_types = "int | " in content or "str | " in content
    has_future = "from __future__ import" in content

    checks.append({"check": "python_version_compat", "passed": True})
    if uses_py310 and not has_future:
        score -= 0.05
    if uses_py310_types and not has_future:
        score -= 0.05

    # 检查是否使用了 pathlib（跨平台路径处理）
    uses_pathlib = "pathlib" in content or "Path(" in content
    checks.append({"check": "uses_pathlib", "passed": uses_pathlib})
    if not uses_pathlib:
        score -= 0.05

    # 检查编码声明
    has_encoding = "encoding=" in content or "utf-8" in content.lower()
    checks.append({"check": "encoding_specified", "passed": has_encoding})

    passed = score >= 0.5
    return PerspectiveResult(
        perspective=Perspective.COMPATIBILITY,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Compatibility: {len(found_platform)} platform-specific patterns, "
                 f"Python 3.10+ features={'yes' if (uses_py310 or uses_py310_types) else 'no'}",
        details={"checks": checks, "platform_specific": found_platform},
    )


def _check_usability(artifact_path: Path, criteria_path: Path | None) -> PerspectiveResult:
    """可用性检查：API 设计、错误信息、文档完整性"""
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except Exception as e:
        return PerspectiveResult(
            perspective=Perspective.USABILITY, passed=False, score=0.0,
            evidence=f"Cannot read: {e}",
        )

    checks = []
    score = 1.0
    lines = content.splitlines()

    # 初始化默认值
    has_docstrings = False
    has_type_annotations = False

    # 检查公共 API 文档
    has_public_api = any(
        kw in content for kw in ["def ", "class "]
    )

    if has_public_api:
        # 检查是否有 docstring
        has_docstrings = '"""' in content or "'''" in content
        checks.append({"check": "has_docstrings", "passed": has_docstrings})
        if not has_docstrings:
            score -= 0.15

        # 检查函数/类的参数文档
        has_param_doc = any(
            kw in content.lower()
            for kw in ["args:", "arguments:", "parameters:", "param ", "returns:", "raises:"]
        )
        checks.append({"check": "parameter_documentation", "passed": has_param_doc})
        if not has_param_doc and len(lines) > 20:
            score -= 0.1

        # 检查类型注解
        has_type_annotations = "-> " in content or ": int" in content or ": str" in content
        checks.append({"check": "type_annotations", "passed": has_type_annotations})
        if not has_type_annotations and len(lines) > 20:
            score -= 0.1

    # 检查错误信息质量
    has_error_messages = any(
        kw in content
        for kw in ["raise .*(", "ValueError(", "TypeError(", "RuntimeError(", "Exception("]
    )
    if has_error_messages:
        # 检查错误信息是否包含描述性文本
        has_descriptive_errors = any(
            kw in content
            for kw in ['raise ValueError("', "raise ValueError('",
                       'raise TypeError("', "raise TypeError('",
                       'raise RuntimeError("', "raise RuntimeError('"]
        )
        checks.append({"check": "descriptive_errors", "passed": has_descriptive_errors})
        if not has_descriptive_errors:
            score -= 0.1

    # 检查命名清晰度
    short_names = 0
    for line in lines:
        stripped = line.strip()
        # 检测单个字母变量名（除 i, j, k 循环变量外）
        if stripped.startswith("def "):
            func_name = stripped.split("(")[0].replace("def ", "")
            if len(func_name) <= 2:
                short_names += 1
    checks.append({"check": "clear_naming", "passed": short_names <= 2})
    if short_names > 2:
        score -= 0.05 * min(short_names - 2, 3)

    # 检查是否有使用示例
    has_examples = "example" in content.lower() or "usage" in content.lower()
    checks.append({"check": "has_examples", "passed": has_examples})

    passed = score >= 0.5
    return PerspectiveResult(
        perspective=Perspective.USABILITY,
        passed=passed,
        score=max(0.0, score),
        evidence=f"Usability: docstrings={'yes' if has_docstrings else 'no'}, "
                 f"type_annotations={'yes' if has_type_annotations else 'no'}, "
                 f"examples={'yes' if has_examples else 'no'}",
        details={"checks": checks},
    )


# --------------------------------------------------------------------------- #
# 工厂函数
# --------------------------------------------------------------------------- #

def create_default_checker(
    strict_mode: bool = True,
    include_all: bool = False,
) -> MultiPerspectiveChecker:
    """创建带有默认视角检查的多视角检查器

    默认视角（RESEARCH_PROPOSAL.md 命题2）：
    - 功能正确性（correctness）
    - 边界情况（boundary）
    - 安全性（security）
    - 可维护性（maintainability）

    可选额外视角（include_all=True）：
    - 性能（performance）
    - 兼容性（compatibility）
    - 可用性（usability）
    """
    checker = MultiPerspectiveChecker(strict_mode=strict_mode)
    checker.register_perspective(Perspective.CORRECTNESS, _check_correctness)
    checker.register_perspective(Perspective.BOUNDARY, _check_boundary)
    checker.register_perspective(Perspective.SECURITY, _check_security)
    checker.register_perspective(Perspective.MAINTAINABILITY, _check_maintainability)

    if include_all:
        checker.register_perspective(Perspective.PERFORMANCE, _check_performance)
        checker.register_perspective(Perspective.COMPATIBILITY, _check_compatibility)
        checker.register_perspective(Perspective.USABILITY, _check_usability)

    return checker


def multi_perspective_verify(
    artifact_path: Path,
    criteria_path: Path | None = None,
    perspectives: list[Perspective] | None = None,
    strict_mode: bool = True,
) -> MultiPerspectiveResult:
    """便捷函数：运行多视角一致性检查

    Args:
        artifact_path: 产出物路径
        criteria_path: 验收标准路径
        perspectives: 要运行的视角（默认：全部四个）
        strict_mode: 严格模式（任何视角失败即整体失败）

    Returns:
        MultiPerspectiveResult: 检查结果
    """
    checker = create_default_checker(strict_mode=strict_mode)
    return checker.check(artifact_path, criteria_path, perspectives)
