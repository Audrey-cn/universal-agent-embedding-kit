"""Language-level policy and isolated execution for Python grading candidates."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from src.security.sandbox import SandboxPolicy, SandboxResult, run_bounded_process

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
}

_DANGEROUS_CALLS = {
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "__import__",
    "locals",
    "open",
    "setattr",
    "vars",
}

_PROHIBITED_NODES: tuple[tuple[type[ast.AST], str], ...] = (
    (ast.Import, "imports are not allowed"),
    (ast.ImportFrom, "imports are not allowed"),
    (ast.ClassDef, "class definitions are not allowed"),
    (ast.With, "with statements are not allowed"),
    (ast.AsyncWith, "with statements are not allowed"),
    (ast.Global, "global statements are not allowed"),
    (ast.Nonlocal, "nonlocal statements are not allowed"),
)


def _append_once(diagnostics: list[str], diagnostic: str) -> None:
    if diagnostic not in diagnostics:
        diagnostics.append(diagnostic)


def _identifier(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.keyword):
        return node.arg
    return None


def validate_candidate_code(code: str, entrypoint: str) -> list[str]:
    """Return deterministic policy diagnostics for untrusted candidate source."""
    try:
        tree = ast.parse(code, filename="candidate.py", mode="exec")
    except (SyntaxError, ValueError) as exc:
        return [f"syntax error: {exc}"]

    diagnostics: list[str] = []
    for index, statement in enumerate(tree.body):
        is_docstring = (
            index == 0
            and isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
        if is_docstring:
            continue
        if isinstance(statement, ast.FunctionDef):
            if statement.decorator_list:
                _append_once(diagnostics, "top-level function decorators are not allowed")
            continue
        if isinstance(statement, (ast.Import, ast.ImportFrom, ast.ClassDef)):
            continue
        _append_once(
            diagnostics,
            f"top-level executable statement {type(statement).__name__} is not allowed",
        )

    entrypoint_definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint
    ]
    top_level_entrypoints = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == entrypoint
    ]
    if len(entrypoint_definitions) != 1 or len(top_level_entrypoints) != 1:
        _append_once(
            diagnostics,
            f"entrypoint {entrypoint!r} must be defined exactly once at top level",
        )

    for node in ast.walk(tree):
        for node_type, diagnostic in _PROHIBITED_NODES:
            if isinstance(node, node_type):
                _append_once(diagnostics, diagnostic)

        identifier = _identifier(node)
        if identifier is not None and "__" in identifier:
            _append_once(diagnostics, f"dunder name or attribute {identifier!r} is not allowed")

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
            _append_once(diagnostics, "function decorators are not allowed")

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parameters = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            annotations = [parameter.annotation for parameter in parameters]
            if node.args.vararg is not None:
                annotations.append(node.args.vararg.annotation)
            if node.args.kwarg is not None:
                annotations.append(node.args.kwarg.annotation)
            has_definition_time_expression = (
                bool(node.args.defaults)
                or any(default is not None for default in node.args.kw_defaults)
                or any(annotation is not None for annotation in annotations)
                or node.returns is not None
                or bool(getattr(node, "type_params", ()))
            )
            if has_definition_time_expression:
                _append_once(
                    diagnostics,
                    "definition-time defaults and annotations are not allowed",
                )

        if isinstance(node, ast.Call):
            call_name: str | None = None
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            if call_name in _DANGEROUS_CALLS:
                _append_once(diagnostics, f"dangerous call {call_name!r} is not allowed")

    return diagnostics


def _trusted_harness() -> str:
    return '''
try:
    namespace = {"__builtins__": SAFE_BUILTINS}
    exec(compile(SOURCE_CODE, "candidate.py", "exec"), namespace)
    function = namespace[ENTRYPOINT]
    if not callable(function):
        raise TypeError("candidate entrypoint is not callable")
except Exception as exc:
    print(json.dumps({"load_error": f"{type(exc).__name__}: {exc}"}))
else:
    results = []
    for index, args in enumerate(PAYLOAD["cases"]):
        try:
            value = function(*args)
            json.dumps(value)
            results.append({"index": index, "status": "ok", "value": value})
        except Exception as exc:
            results.append(
                {"index": index, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
            )
    print(json.dumps(results))
'''


def _harness_prelude() -> str:
    builtin_entries = "\n".join(
        f"    {name!r}: {name}," for name in SAFE_BUILTINS
    )
    return f'''import json
import sys

SAFE_BUILTINS = {{
{builtin_entries}
}}

with open(sys.argv[1], encoding="utf-8") as context_handle:
    CONTEXT = json.load(context_handle)
SOURCE_CODE = CONTEXT["code"]
ENTRYPOINT = CONTEXT["entrypoint"]
PAYLOAD = CONTEXT["payload"]
'''


def _failure_result(
    error: str,
    *,
    process_result: SandboxResult | None = None,
) -> SandboxResult:
    if process_result is None:
        return SandboxResult(error=error)
    return SandboxResult(
        stdout=process_result.stdout,
        stderr=process_result.stderr,
        exit_code=process_result.exit_code,
        success=False,
        error=error,
        timed_out=process_result.timed_out,
        output_truncated=process_result.output_truncated,
    )


def run_restricted_harness(
    code: str,
    entrypoint: str,
    harness: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> SandboxResult:
    """Run a repository-owned harness around validated candidate code."""
    diagnostics = validate_candidate_code(code, entrypoint)
    if diagnostics:
        return _failure_result(f"candidate policy rejected: {'; '.join(diagnostics)}")
    return _run_harness(code, entrypoint, harness, payload, timeout=timeout)


def run_restricted_module_harness(
    code: str,
    harness: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> SandboxResult:
    """Run a restricted module harness without requiring a named entrypoint."""
    try:
        tree = ast.parse(code, filename="candidate.py", mode="exec")
    except (SyntaxError, ValueError) as exc:
        return _failure_result(f"candidate policy rejected: syntax error: {exc}")
    validation_entrypoint = next(
        (
            statement.name
            for statement in tree.body
            if isinstance(statement, ast.FunctionDef)
        ),
        "__uaek_missing_entrypoint__",
    )
    diagnostics = [
        diagnostic
        for diagnostic in validate_candidate_code(code, validation_entrypoint)
        if not diagnostic.startswith("top-level executable statement ")
        and not diagnostic.startswith("entrypoint ")
    ]
    if diagnostics:
        return _failure_result(f"candidate policy rejected: {'; '.join(diagnostics)}")
    return _run_harness(code, "", harness, payload, timeout=timeout)


def run_repository_scenario_harness(
    source_id: str,
    entrypoint: str,
    harness: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> SandboxResult:
    """Retrieve and run a fixed repository scenario source by immutable identifier."""
    if type(source_id) is not str or source_id.count(":") != 1:
        return _failure_result("unknown repository scenario source")
    from src import scenario_benchmark

    try:
        code = scenario_benchmark._repository_scenario_source(source_id)
    except KeyError:
        return _failure_result(f"unknown repository scenario source: {source_id!r}")
    return _run_harness(code, entrypoint, harness, payload, timeout=timeout)


def _run_harness(
    code: str,
    entrypoint: str,
    harness: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> SandboxResult:
    """Execute a trusted harness without duplicating process setup."""

    try:
        with tempfile.TemporaryDirectory(prefix="uaek-grade-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            context_path = tmp_path / "context.json"
            harness_path = tmp_path / "harness.py"
            context_path.write_text(
                json.dumps(
                    {"code": code, "entrypoint": entrypoint, "payload": payload}
                ),
                encoding="utf-8",
            )
            harness_path.write_text(_harness_prelude() + harness, encoding="utf-8")
            environment = {
                "HOME": tmp_dir,
                "TMPDIR": tmp_dir,
                "PYTHONHASHSEED": "0",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            }
            process_result = run_bounded_process(
                [sys.executable, str(harness_path), str(context_path)],
                policy=SandboxPolicy(
                    max_runtime_sec=cast(Any, timeout),
                    max_memory_mb=256,
                    max_output_bytes=1024 * 1024,
                ),
                env=environment,
                cwd=tmp_path,
            )
    except Exception as exc:
        return _failure_result(f"grader setup failed: {type(exc).__name__}: {exc}")

    if process_result.timed_out:
        return _failure_result(
            f"grading timed out after {timeout:g}s",
            process_result=process_result,
        )
    if process_result.output_truncated:
        return _failure_result("grader output limit exceeded", process_result=process_result)
    if not process_result.success:
        detail = process_result.error or process_result.stderr.strip()[:200]
        error = f"grader process failed with exit code {process_result.exit_code}"
        if detail:
            error += f": {detail}"
        return _failure_result(error, process_result=process_result)

    try:
        result = json.loads(process_result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return _failure_result(
            f"grader produced invalid JSON: {exc}", process_result=process_result
        )
    process_result.result = result
    return process_result


def _parse_case_results(process_result: SandboxResult) -> list[SandboxResult]:
    try:
        payload = json.loads(process_result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return [
            _failure_result(
                f"grader produced invalid JSON: {exc}",
                process_result=process_result,
            )
        ]

    if isinstance(payload, dict) and isinstance(payload.get("load_error"), str):
        return [_failure_result(payload["load_error"], process_result=process_result)]
    if not isinstance(payload, list):
        return [
            _failure_result(
                f"grader produced invalid JSON result type: {type(payload).__name__}",
                process_result=process_result,
            )
        ]

    case_results: list[SandboxResult] = []
    for item in payload:
        if not isinstance(item, dict):
            return [_failure_result("grader produced invalid JSON case result")]
        if item.get("status") == "ok" and "value" in item:
            case_results.append(
                SandboxResult(
                    stdout=json.dumps(item),
                    exit_code=0,
                    success=True,
                    result=item["value"],
                )
            )
        elif item.get("status") == "error" and isinstance(item.get("error"), str):
            case_results.append(
                SandboxResult(
                    stdout=json.dumps(item),
                    exit_code=0,
                    success=False,
                    error=item["error"],
                )
            )
        else:
            return [_failure_result("grader produced invalid JSON case result")]
    return case_results


def run_candidate_cases(
    code: str,
    entrypoint: str,
    args_list: list[tuple[Any, ...]],
    *,
    timeout: float,
) -> list[SandboxResult]:
    """Validate and run candidate calls in a bounded process and isolated temp home."""
    process_result = run_restricted_harness(
        code,
        entrypoint,
        _trusted_harness(),
        {"cases": args_list},
        timeout=timeout,
    )
    if not process_result.success:
        return [process_result]
    return _parse_case_results(process_result)
