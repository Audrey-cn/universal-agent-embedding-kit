"""UAEK CLI — 命令行接口"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="uaek")
def main():
    """UAEK — Universal Agent Enhancement Kit"""
    pass


@main.command()
@click.argument("artifact_path", type=click.Path(exists=True))
@click.option("--criteria", "-c", type=click.Path(exists=True), help="验收标准路径")
@click.option(
    "--type",
    "-t",
    "verification_type",
    type=click.Choice(["test", "build", "lint", "render", "diff", "adversarial"]),
    help="验证类型",
)
def verify(artifact_path: str, criteria: str | None, verification_type: str | None):
    """运行验证"""
    from src.verify import VerificationType
    from src.verify import verify as run_verify

    artifact = Path(artifact_path)
    criteria_path = Path(criteria) if criteria else None

    vtype = None
    if verification_type:
        vtype = VerificationType(verification_type)

    console.print(f"[bold]验证 {artifact}...[/bold]")
    result = run_verify(artifact, criteria_path, vtype)

    if result.passed:
        console.print(f"[green]✅ {result}[/green]")
    else:
        console.print(f"[red]❌ {result}[/red]")

    console.print(f"\n[dim]证据:[/dim]\n{result.evidence[:500]}")
    sys.exit(0 if result.passed else 1)


@main.command()
@click.argument("task_description")
@click.option("--files", "-f", type=int, help="涉及文件数")
@click.option("--deps", "-d", type=int, help="依赖深度")
@click.option("--ambiguity", "-a", type=float, help="模糊度 0.0-1.0")
@click.option("--reversibility", "-r", type=float, help="可逆度 0.0-1.0")
@click.option("--language", "-l", type=click.Choice(["zh", "en"]), default="en", help="语言")
def effort(
    task_description: str,
    files: int | None,
    deps: int | None,
    ambiguity: float | None,
    reversibility: float | None,
    language: str,
):
    """分类 Effort 级别"""
    from src.effort import classify

    result = classify(
        task_description,
        file_count=files,
        dependency_depth=deps,
        ambiguity=ambiguity,
        reversibility=reversibility,
    )

    # 创建结果表格
    table = Table(title="Effort 分类结果")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")

    table.add_row("Effort 级别", result.level.value)
    table.add_row("置信度", f"{result.confidence:.0%}")
    table.add_row("调度短语", result.dispatch_phrase)
    table.add_row("验证深度", result.verification_depth)
    table.add_row("分类理由", result.reasoning)

    console.print(table)

    # 显示详细指标
    console.print("\n[dim]详细指标:[/dim]")
    for key, value in result.metrics.items():
        console.print(f"  {key}: {value}")


@main.command("run")
@click.argument("task_description")
@click.option(
    "--memory-store",
    type=click.Path(),
    default=None,
    help="Harness 记忆存储目录",
)
@click.option("--memory-layer", type=click.Choice(["l1", "l2", "l3"]), default=None)
@click.option("--tag", "tags", multiple=True, help="Harness 结果标签，可重复")
@click.option("--output", "-o", type=click.Path(), help="输出 JSON 文件")
@click.option("--config", "config_path", type=click.Path(exists=True), help="UAEK 配置文件")
@click.option("--log-file", type=click.Path(), help="结构化 JSONL 日志文件")
def run(
    task_description: str,
    memory_store: str | None,
    memory_layer: str | None,
    tags: tuple[str, ...],
    output: str | None,
    config_path: str | None,
    log_file: str | None,
):
    """通过本地 Agent Harness 运行一个任务"""
    from src.config import load_config
    from src.harness import AgentHarness, HarnessRequest
    from src.logger import JsonlLogger
    from src.memory import MemoryService

    config = load_config(Path(config_path) if config_path else None)
    resolved_memory_store = memory_store or config.memory.storage_path
    resolved_memory_layer = memory_layer or config.memory.default_layer
    resolved_log_file = log_file or config.logging.file_path

    harness = AgentHarness(MemoryService(Path(resolved_memory_store)))
    request = HarnessRequest(
        task=task_description,
        memory_layer=resolved_memory_layer,
        tags=list(tags) or ["harness"],
    )
    payload = harness.run(request).to_dict()
    logged_path = JsonlLogger(resolved_log_file, enabled=config.logging.enabled).record(
        "harness_run",
        {
            "task": payload["task"],
            "success": payload["success"],
            "score": payload["report"]["score"],
            "memory_entry_id": payload["memory"]["entry_id"],
            "memory_layer": payload["memory"]["layer"],
            "workflow_id": payload["workflow"]["workflow_id"],
        },
    )

    table = Table(title="Harness Run")
    table.add_column("Stage", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Task", payload["task"])
    table.add_row("Success", str(payload["success"]))
    table.add_row("Effort", payload["effort"]["level"])
    table.add_row("Workflow", payload["workflow"]["workflow_id"])
    table.add_row("Verification", str(payload["verification"]["passed"]))
    table.add_row("Score", str(payload["report"]["score"]))
    table.add_row("Memory", payload["memory"]["entry_id"])
    console.print(table)

    if output:
        output_path = _write_json(payload, Path(output))
        console.print(f"[green]written[/green] {output_path}")
    if logged_path:
        console.print(f"[green]logged[/green] {logged_path}")

    sys.exit(0 if payload["success"] else 1)


@main.group()
def memory():
    """管理跨会话记忆"""
    pass


@memory.command("add")
@click.argument("content")
@click.option("--store", type=click.Path(), default=".uaek/memory", help="记忆存储目录")
@click.option("--layer", type=click.Choice(["l1", "l2", "l3"]), default="l1", help="记忆层")
@click.option("--importance", type=float, default=0.5, help="重要性 0.0-1.0")
@click.option("--tag", "tags", multiple=True, help="标签，可重复")
def memory_add(content: str, store: str, layer: str, importance: float, tags: tuple[str, ...]):
    """添加记忆"""
    from src.memory import MemoryService

    service = MemoryService(Path(store))
    entry = service.add(content, layer=layer, importance=importance, tags=list(tags))
    service.persist()
    console.print(f"[green]added[/green] {entry['id']} layer={entry['layer']} {entry['content']}")


@memory.command("query")
@click.argument("query")
@click.option("--store", type=click.Path(), default=".uaek/memory", help="记忆存储目录")
@click.option("--layer", type=click.Choice(["l1", "l2", "l3"]), help="记忆层")
@click.option("--tag", "tags", multiple=True, help="标签过滤，可重复")
@click.option("--min-importance", type=float, default=0.0, help="最小重要性")
@click.option("--limit", type=int, default=10, help="返回数量")
def memory_query(
    query: str,
    store: str,
    layer: str | None,
    tags: tuple[str, ...],
    min_importance: float,
    limit: int,
):
    """查询记忆"""
    from src.memory import MemoryService

    service = MemoryService(Path(store))
    result = service.query(
        query,
        layer=layer,
        tags=list(tags),
        min_importance=min_importance,
        limit=limit,
    )
    table = Table(title=f"Memory Query: {query}")
    table.add_column("ID", style="cyan")
    table.add_column("Layer", style="green")
    table.add_column("Importance")
    table.add_column("Content")
    for entry in result["results"]:
        table.add_row(
            entry["id"],
            entry["layer"],
            f"{entry['importance']:.2f}",
            entry["content"],
        )
    console.print(table)
    console.print(f"[dim]total: {result['total']}[/dim]")


@memory.command("compress")
@click.option("--store", type=click.Path(), default=".uaek/memory", help="记忆存储目录")
@click.option("--layer", type=click.Choice(["l1", "l2", "l3"]), help="记忆层")
@click.option("--target-ratio", type=float, default=0.5, help="目标保留比例")
def memory_compress(store: str, layer: str | None, target_ratio: float):
    """压缩记忆"""
    from src.memory import MemoryService

    service = MemoryService(Path(store))
    result = service.compress(layer=layer, target_ratio=target_ratio)
    service.persist()
    console.print(
        f"[green]{result['status']}[/green] before={result['before']} after={result['after']}"
    )


@memory.command("restore")
@click.option("--store", type=click.Path(), default=".uaek/memory", help="记忆存储目录")
def memory_restore(store: str):
    """恢复并显示记忆统计"""
    from src.memory import MemoryService

    service = MemoryService(Path(store))
    result = service.restore()
    console.print(f"[green]{result['status']}[/green] {result['storage_path']}")
    console.print(result["layers"])


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="工作流配置文件")
def workflow(config: str | None):
    """运行工作流"""
    from src.workflow import execute_workflow_config, load_workflow_config

    if not config:
        console.print("[red]需要 --config 指定工作流配置文件[/red]")
        sys.exit(2)

    result = execute_workflow_config(load_workflow_config(Path(config)))
    console.print(f"[bold]Workflow:[/bold] {result['workflow_id']}")
    table = Table(title="Workflow Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Result")
    for task in result["tasks"]:
        table.add_row(task["id"], task["status"], _stringify(task["result"]))
    console.print(table)
    console.print(f"[dim]duration: {result['duration']:.4f}s[/dim]")
    sys.exit(0 if result["success"] else 1)


@main.group(invoke_without_command=True)
@click.option("--skills-dir", type=click.Path(exists=True), default="skills", help="技能目录")
@click.pass_context
def skill(ctx: click.Context, skills_dir: str):
    """加载并执行技能"""
    if ctx.invoked_subcommand is not None:
        return
    _list_skills(skills_dir)


@skill.command("list")
@click.option("--skills-dir", type=click.Path(exists=True), default="skills", help="技能目录")
def skill_list(skills_dir: str):
    """列出技能"""
    _list_skills(skills_dir)


@skill.command("run")
@click.argument("name")
@click.option("--input", "input_path", "-i", type=click.Path(exists=True), help="输入文件")
@click.option("--skills-dir", type=click.Path(exists=True), default="skills", help="技能目录")
def skill_run(name: str, input_path: str | None, skills_dir: str):
    """执行技能"""
    _run_skill(name, input_path=input_path, skills_dir=skills_dir)


@main.group()
def adapter():
    """运行外部 Agent Adapter"""
    pass


@adapter.command("run")
@click.argument("task_description")
@click.option("--provider", default="command-agent", help="外部 Agent provider 名称")
@click.option("--command", "command", multiple=True, required=True, help="命令 token，可重复")
@click.option("--context", default="{}", help="JSON 对象形式的上下文")
@click.option("--metadata", default="{}", help="JSON 对象形式的元数据")
@click.option("--timeout", type=float, default=60.0, help="命令超时秒数")
@click.option("--output", "-o", type=click.Path(), help="输出 JSON 文件")
@click.option("--trace", type=click.Path(), help="Adapter JSONL trace 文件")
def adapter_run(
    task_description: str,
    provider: str,
    command: tuple[str, ...],
    context: str,
    metadata: str,
    timeout: float,
    output: str | None,
    trace: str | None,
):
    """通过命令式外部 Agent Adapter 运行一个任务"""
    from src.adapters import AdapterRequest, CommandAgentAdapter

    try:
        context_data = _parse_json_object(context, "context")
        metadata_data = _parse_json_object(metadata, "metadata")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    result = CommandAgentAdapter(
        list(command),
        provider=provider,
        timeout_seconds=timeout,
        trace_path=Path(trace) if trace else None,
    ).run(
        AdapterRequest(
            task=task_description,
            context=context_data,
            metadata=metadata_data,
        )
    )
    payload = result.to_dict()

    table = Table(title="Adapter Run")
    table.add_column("Stage", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Provider", payload["provider"])
    table.add_row("Success", str(payload["success"]))
    table.add_row("Trace ID", payload["trace_id"])
    table.add_row("Return Code", str(payload["return_code"]))
    table.add_row("Output", payload["output"])
    if payload["error"]:
        table.add_row("Error", payload["error"])
    console.print(table)

    if output:
        output_path = _write_json(payload, Path(output))
        console.print(f"[green]written[/green] {output_path}")
    if trace:
        console.print(f"[green]traced[/green] {trace}")

    sys.exit(0 if payload["success"] else 1)


@main.group()
def platform():
    """记录和校验外部平台运行证据"""
    pass


@platform.command("discover")
@click.option("--output", "-o", type=click.Path(), help="输出平台发现 JSON 文件")
def platform_discover(output: str | None):
    """发现本机可用的外部 Agent 平台入口"""
    from src.platform_runs import discover_platforms

    payload = {"platforms": discover_platforms()}
    table = Table(title="Platform Discovery")
    table.add_column("Provider", style="cyan")
    table.add_column("Available", style="green")
    table.add_column("Command")
    for item in payload["platforms"]:
        table.add_row(item["provider"], str(item["available"]), item["command_path"])
    console.print(table)

    if output:
        output_path = _write_json(payload, Path(output))
        console.print(f"[green]written[/green] {output_path}")


@platform.command("record")
@click.option("--adapter-result", type=click.Path(exists=True), required=True)
@click.option("--provider", required=True, help="平台 provider 名称")
@click.option(
    "--evidence-level",
    type=click.Choice(["contract", "local_command", "live_external"]),
    required=True,
)
@click.option("--source", default="uaek adapter run", help="证据来源说明")
@click.option("--command", "command", multiple=True, help="实际运行命令 token，可重复")
@click.option("--output", "-o", type=click.Path(), required=True, help="输出 artifact JSON")
def platform_record(
    adapter_result: str,
    provider: str,
    evidence_level: str,
    source: str,
    command: tuple[str, ...],
    output: str,
):
    """把 adapter result 包装为 platform_run_v1 artifact"""
    from src.platform_runs import record_platform_run, validate_platform_run_artifact

    artifact = record_platform_run(
        adapter_result_path=Path(adapter_result),
        provider=provider,
        evidence_level=evidence_level,
        output_path=Path(output),
        source=source,
        command=list(command),
    )
    validation = validate_platform_run_artifact(artifact)

    table = Table(title="Platform Run")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Provider", artifact["provider"])
    table.add_row("Task", artifact["task"])
    table.add_row("Status", artifact["status"])
    table.add_row("Evidence", artifact["evidence_level"])
    table.add_row("Valid", str(validation["valid"]))
    console.print(table)
    console.print(f"[green]written[/green] {output}")

    sys.exit(0 if validation["valid"] else 1)


@platform.command("validate")
@click.argument("artifact_path", type=click.Path(exists=True))
def platform_validate(artifact_path: str):
    """校验 platform_run_v1 artifact"""
    from src.platform_runs import validate_platform_run_artifact

    validation = validate_platform_run_artifact(Path(artifact_path))
    table = Table(title="Platform Run Validation")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Valid", str(validation["valid"]))
    table.add_row("Provider", str(validation["provider"]))
    table.add_row("Evidence", str(validation["evidence_level"]))
    table.add_row("Live external", str(validation["is_live_external"]))
    if validation["errors"]:
        table.add_row("Errors", "; ".join(validation["errors"]))
    console.print(table)

    sys.exit(0 if validation["valid"] else 1)


@main.group()
def capability():
    """运行并校验可自动评分的真实代码任务能力证据"""
    pass


@capability.command("run")
@click.option("--provider", required=True, help="平台 provider 名称")
@click.option("--command", "command", multiple=True, required=True, help="基础命令 token，可重复")
@click.option(
    "--output-mode",
    type=click.Choice(["plain", "mimo_jsonl"]),
    default="plain",
    help="provider stdout 解码方式",
)
@click.option(
    "--provider-home",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="可选隔离 HOME 目录；用于有写入权限问题的 provider（写入日志/数据库）",
)
@click.option(
    "--provider-home-seed",
    "provider_home_seed_paths",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    help="显式复制到隔离 HOME 的配置文件/目录；HOME 下路径会保留相对布局",
)
@click.option("--timeout", type=float, default=120.0, help="单任务超时秒数")
@click.option(
    "--output", "-o", type=click.Path(), required=True, help="输出 capability artifact JSON"
)
def capability_run(
    provider: str,
    command: tuple[str, ...],
    output_mode: str,
    provider_home: Path | None,
    provider_home_seed_paths: tuple[Path, ...],
    timeout: float,
    output: str,
):
    """驱动 provider 跑完整代码任务套件并客观评分"""
    from src.capability_matrix import (
        run_capability_suite_live,
        validate_capability_run_artifact,
        write_capability_run,
    )

    artifact = run_capability_suite_live(
        provider=provider,
        base_command=list(command),
        output_mode=output_mode,
        timeout=timeout,
        provider_home=str(provider_home) if provider_home is not None else None,
        provider_home_seed_paths=tuple(str(path) for path in provider_home_seed_paths),
    )
    write_capability_run(artifact, Path(output))
    validation = validate_capability_run_artifact(artifact)

    table = Table(title="Capability Run")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Provider", artifact["provider"])
    table.add_row("Status", artifact["status"])
    metrics = artifact["metrics"]
    table.add_row("Tasks passed", f"{metrics['tasks_passed']}/{metrics['tasks_attempted']}")
    table.add_row("Suite pass rate", str(metrics["suite_pass_rate"]))
    table.add_row("Graded live", str(validation["is_graded_live"]))
    if validation["errors"]:
        table.add_row("Errors", "; ".join(validation["errors"]))
    console.print(table)
    console.print(f"[green]written[/green] {output}")

    sys.exit(0 if validation["is_graded_live"] else 1)


@capability.command("batch")
@click.argument("manifest_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", type=click.Path(path_type=Path), help="artifact 输出目录")
@click.option("--timeout", type=float, default=None, help="覆盖 manifest 默认单任务超时秒数")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="可选 batch summary JSON")
@click.option("--matrix-output", type=click.Path(path_type=Path), help="可选 matrix JSON")
@click.option("--dry-run", is_flag=True, help="仅校验 manifest，不启动 provider")
def capability_batch(
    manifest_path: Path,
    output_dir: Path | None,
    timeout: float | None,
    output: Path | None,
    matrix_output: Path | None,
    dry_run: bool,
):
    """按 JSON manifest 批量复跑 capability provider 矩阵"""
    from src.capability_matrix import run_capability_manifest, validate_capability_manifest

    if dry_run:
        validation = validate_capability_manifest(
            manifest_path=manifest_path,
            output_dir=output_dir,
            timeout=timeout,
        )
        table = Table(title="Capability Batch Dry Run")
        table.add_column("Provider", style="cyan")
        table.add_column("Output mode", style="green")
        table.add_column("Command tokens")
        table.add_column("Seed paths")
        for item in validation["providers"]:
            table.add_row(
                item["provider"],
                item["output_mode"],
                str(len(item["command"])),
                str(len(item["provider_home_seed_paths"])),
            )
        console.print(table)
        if validation["errors"]:
            console.print("[red]Errors:[/red] " + "; ".join(validation["errors"]))
        if validation["warnings"]:
            console.print("[yellow]Warnings:[/yellow] " + "; ".join(validation["warnings"]))
        if output:
            output_path = _write_json(validation, output)
            console.print(f"[green]written[/green] {output_path}")
        sys.exit(0 if validation["valid"] else 1)

    result = run_capability_manifest(
        manifest_path=manifest_path,
        output_dir=output_dir,
        timeout=timeout,
    )

    table = Table(title="Capability Batch")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Tasks passed")
    table.add_column("Graded live")
    for item in result["runs"]:
        metrics = item["metrics"]
        validation = item["validation"]
        table.add_row(
            item["provider"],
            item["status"],
            f"{metrics['tasks_passed']}/{metrics['tasks_attempted']}",
            str(validation["is_graded_live"]),
        )
    console.print(table)
    console.print(
        f"[bold]Matrix score:[/bold] {result['matrix']['recommended_score']} "
        f"({result['matrix']['status']})"
    )

    if output:
        output_path = _write_json(result, output)
        console.print(f"[green]written[/green] {output_path}")
    if matrix_output:
        matrix_path = _write_json(result["matrix"], matrix_output)
        console.print(f"[green]written[/green] {matrix_path}")

    sys.exit(0 if result["status"] == "completed" else 1)


@capability.command("validate")
@click.argument("artifact_path", type=click.Path(exists=True))
def capability_validate(artifact_path: str):
    """校验 capability_run_v1 artifact"""
    from src.capability_matrix import validate_capability_run_artifact

    validation = validate_capability_run_artifact(Path(artifact_path))
    table = Table(title="Capability Run Validation")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Valid", str(validation["valid"]))
    table.add_row("Provider", str(validation["provider"]))
    table.add_row("Graded live", str(validation["is_graded_live"]))
    table.add_row("Tasks passed", str(validation["tasks_passed"]))
    if validation["errors"]:
        table.add_row("Errors", "; ".join(validation["errors"]))
    console.print(table)

    sys.exit(0 if validation["valid"] else 1)


@capability.command("matrix")
@click.option("--artifact-dir", type=click.Path(), default=None, help="capability artifact 目录")
@click.option("--output", "-o", type=click.Path(), help="可选输出 JSON 文件")
def capability_matrix(artifact_dir: str | None, output: str | None):
    """聚合全平台能力矩阵并给出推荐分数"""
    from src.capability_matrix import DEFAULT_CAPABILITY_RUN_DIR, run_capability_readiness

    target_dir = Path(artifact_dir) if artifact_dir else DEFAULT_CAPABILITY_RUN_DIR
    result = run_capability_readiness(target_dir)
    table = Table(title="Capability Matrix")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Tasks passed")
    table.add_column("Pass rate")
    for item in result["provider_statuses"]:
        table.add_row(
            item["provider"],
            item["status"],
            f"{item['tasks_passed']}/{item['tasks_total']}",
            str(item["suite_pass_rate"]),
        )
    console.print(table)
    console.print(
        f"[bold]Recommended score:[/bold] {result['recommended_score']} ({result['status']})"
    )

    if output:
        output_path = _write_json(result, Path(output))
        console.print(f"[green]written[/green] {output_path}")


@main.command()
@click.option(
    "--suite",
    "-s",
    type=click.Choice(
        [
            "quick",
            "proxy",
            "adapter",
            "platform",
            "excellence",
            "live_matrix",
            "capability",
            "adversarial",
            "context",
            "cost",
            "scenario",
            "fable5",
            "cross_platform",
        ]
    ),
    default="quick",
    help="基准测试套件",
)
@click.option("--iterations", "-n", type=int, default=5, help="每项本地测量迭代次数")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="benchmarks/results",
    help="输出目录或 JSON 文件",
)
@click.option("--baseline", type=click.Path(exists=True), help="外部 baseline JSON 文件")
def benchmark(suite: str, iterations: int, output: str, baseline: str | None):
    """运行基准测试"""
    from src.benchmark import run_benchmark, write_benchmark_result

    result = run_benchmark(
        suite=suite,
        iterations=iterations,
        baseline_path=Path(baseline) if baseline else None,
    )
    output_path = write_benchmark_result(result, Path(output))

    table = Table(title="Benchmark Result")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for name, value in result["metrics"].items():
        table.add_row(name, f"{value:.4f}ms")
    if result["scorecard"].get("current_score") is not None:
        table.add_row("Score", str(result["scorecard"]["current_score"]))
        table.add_row("Delta", f"+{result['scorecard']['score_delta']}")
    table.add_row("External baseline", result["external_baseline"]["status"])
    if "adversarial_readiness" in result:
        adv = result["adversarial_readiness"]
        table.add_row(
            "Cheating rate (naive→adv)",
            f"{adv['naive']['cheating_rate']:.0%} → {adv['adversarial']['cheating_rate']:.0%}",
        )
    if "context_rot_readiness" in result:
        ctx = result["context_rot_readiness"]
        table.add_row(
            "Accuracy @70% util (naive→adaptive)",
            f"{ctx['naive']['accuracy_at_target']:.0%} → "
            f"{ctx['adaptive']['accuracy_at_target']:.0%}",
        )
    if "cost_readiness" in result:
        cst = result["cost_readiness"]
        table.add_row(
            "Cost reduction (cache hit)",
            f"-{cst['cost_reduction']:.0%} (hit {cst['cache_hit_rate']:.0%})",
        )
    if "scenario_readiness" in result:
        scn = result["scenario_readiness"]
        table.add_row(
            "Scenario eval (ref vs regressing)",
            f"{scn['reference_overall']:.0%} vs {scn['flawed_overall']:.0%}",
        )
    if "proxy_validation" in result:
        table.add_row("Proxy validation", result["proxy_validation"]["status"])
    if "adapter_readiness" in result:
        table.add_row("Adapter readiness", result["adapter_readiness"]["status"])
    if "platform_run_readiness" in result:
        table.add_row("Platform readiness", result["platform_run_readiness"]["status"])
    if "excellence_readiness" in result:
        table.add_row("Excellence readiness", result["excellence_readiness"]["status"])
    if "live_matrix_readiness" in result:
        table.add_row("Live matrix readiness", result["live_matrix_readiness"]["status"])
    if "capability_readiness" in result:
        table.add_row("Capability readiness", result["capability_readiness"]["status"])
    console.print(table)
    console.print(f"[green]written[/green] {output_path}")



@main.command()
@click.option("--iterations", "-n", type=int, default=2, help="迭代次数")
@click.option(
    "--output", "-o", type=click.Path(), default="benchmarks/results", help="输出目录或 JSON 文件"
)
@click.option("--baseline", type=click.Path(exists=True), help="外部 baseline JSON 文件")
def audit(iterations: int, output: str, baseline: str | None):
    """运行全量审计：聚合所有 benchmark suite 为统一报告"""
    from src.benchmark import run_audit

    result = run_audit(
        iterations=iterations,
        baseline_path=Path(baseline) if baseline else None,
    )

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output == "-":
        # "-" means stdout (machine / pipe use): emit pure JSON, skip the human
        # table. Previously this fell through to ``Path("-") / "audit.json"`` and
        # created a stray directory literally named "-".
        click.echo(payload, nl=False)
        return
    output_path = Path(output)
    if output_path.suffix.lower() == ".json":
        audit_path = output_path
    else:
        audit_path = output_path / "audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(payload, encoding="utf-8")

    # Print summary table
    table = Table(title="UAEK Audit Report")
    table.add_column("Dimension", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Key Result", style="yellow")

    props = result["propositions"]

    def _fmt_pct(v: Any) -> str:
        if v is None:
            return "—"
        return f"{v:.0%}"

    def _fmt_neg_pct(v: Any) -> str:
        if v is None:
            return "—"
        return f"−{v:.0%}"

    p1 = props["p1_context_utilization"]["key_result"]
    table.add_row(
        "P1 上下文利用率",
        props["p1_context_utilization"]["status"],
        f"adaptive {_fmt_pct(p1['adaptive_accuracy'])} @ {_fmt_pct(p1['target_utilization'])} util"
        if p1["adaptive_accuracy"] is not None
        else "—",
    )
    p2 = props["p2_self_grading_cheating"]["key_result"]
    table.add_row(
        "P2 自评分作弊率",
        props["p2_self_grading_cheating"]["status"],
        (
            f"naive {_fmt_pct(p2['naive_cheating_rate'])} "
            f"→ adv {_fmt_pct(p2['adversarial_cheating_rate'])}"
        )
        if p2["adversarial_cheating_rate"] is not None
        else "—",
    )
    p3 = props["p3_cost_optimization"]["key_result"]
    table.add_row(
        "P3 成本优化",
        props["p3_cost_optimization"]["status"],
        (
            f"model {_fmt_neg_pct(p3['model_cost_reduction'])}, "
            f"live {_fmt_neg_pct(p3['live_measured_reduction'])}"
        )
        if p3["model_cost_reduction"] is not None
        else "—",
    )
    p4 = props["p4_real_scenario_benchmark"]["key_result"]
    table.add_row(
        "P4 真实场景基准",
        props["p4_real_scenario_benchmark"]["status"],
        f"{p4['scenario_count'] or '—'} scenarios, ref {_fmt_pct(p4['reference_overall'])}"
        if p4["reference_overall"] is not None
        else "—",
    )
    cap_key = props["p5_cross_platform_verification"]["key_result"]
    table.add_row(
        "P5 跨平台验证",
        props["p5_cross_platform_verification"]["status"],
        f"{cap_key.get('graded_live_count', '—')}/{cap_key.get('total_tasks', '—')} graded-live"
        if cap_key.get("graded_live_count") is not None
        else "—",
    )
    table.add_section()
    gates = result["gates"]
    table.add_row(
        "所有命题完成",
        "✓" if props["all_propositions_complete"] else "✗",
        "",
    )
    table.add_row(
        "证据档案",
        f"{gates['benchmark_evidence_count']} suites",
        f"errors: {len(result['errors'])}",
    )
    ci_url = gates.get("ci_remote_run_url")
    ci_detail = (
        f"✓ {ci_url}" if gates["ci_remote_verified"] and ci_url
        else "✓ detected" if gates["ci_remote_verified"]
        else "配置完成，待远端运行"
    )
    table.add_row(
        "CI 远端验证",
        "✓" if gates["ci_remote_verified"] else "✗",
        ci_detail,
    )
    table.add_row(
        "外部 Baseline",
        "✗" if not gates["external_baseline_available"] else "✓",
        "Fable 5 已退役，无可复跑 baseline",
    )
    console.print(table)
    console.print(f"[green]written[/green] {audit_path}")


def _list_skills(skills_dir: str):
    from src.skills import SkillService

    service = SkillService([Path(skills_dir)])
    table = Table(title="Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Path")
    for metadata in service.list_skills():
        table.add_row(metadata["name"], metadata["description"], metadata["path"])
    console.print(table)


def _run_skill(name: str, input_path: str | None, skills_dir: str):
    from src.skills import SkillService

    context: dict[str, Any] = {}
    if input_path:
        context["input"] = Path(input_path).read_text(encoding="utf-8")
    service = SkillService([Path(skills_dir)])
    result = service.run(name, context)
    console.print(f"[bold]Skill:[/bold] {result['name']}")
    console.print(result["output"][:2000], markup=False)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(value)


def _write_json(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _parse_json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


if __name__ == "__main__":
    main()
