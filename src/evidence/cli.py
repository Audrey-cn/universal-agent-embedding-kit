"""Thin Click adapters for machine-readable UAEK evidence contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from src.evidence.baseline import (
    CURRENT_GRADER_VERSION,
    current_task_set_digest,
    validate_external_baseline,
)
from src.evidence.campaign import (
    aggregate_campaign,
    run_campaign,
    validate_campaign_manifest,
)
from src.evidence.cost import aggregate_cost_evidence, validate_cost_ledger
from src.evidence.session import aggregate_session_evidence, validate_session_artifact


@click.group()
def evidence() -> None:
    """Validate and aggregate UAEK 0.3 evidence artifacts."""


@evidence.group("campaign")
def campaign_group() -> None:
    """Manage multi-sample capability campaigns."""


@campaign_group.command("validate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def campaign_validate(source: str, output: str) -> None:
    """Validate a campaign manifest without executing providers."""

    result = validate_campaign_manifest(source)
    _emit(result, output)
    if not result["valid"]:
        raise click.exceptions.Exit(1)


@campaign_group.command("aggregate")
@click.argument("artifacts", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def campaign_aggregate(artifacts: tuple[str, ...], output: str) -> None:
    """Aggregate campaign artifacts by provider and backend family."""

    _emit(aggregate_campaign(artifacts), output)


@campaign_group.command("run")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Resolve samples without invoking providers.")
@click.option("--output", "-o", type=click.Path(), default="-")
def campaign_run(source: str, dry_run: bool, output: str) -> None:
    """Run or resolve every sample in a campaign manifest."""

    _emit(run_campaign(source, dry_run=dry_run), output)


@evidence.group("cost")
def cost_group() -> None:
    """Manage separated warm, mixed, and cold cost evidence."""


@cost_group.command("validate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def cost_validate(source: str, output: str) -> None:
    result = validate_cost_ledger(source)
    _emit(result, output)
    if not result["valid"]:
        raise click.exceptions.Exit(1)


@cost_group.command("aggregate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def cost_aggregate(source: str, output: str) -> None:
    _emit(aggregate_cost_evidence(source), output)


@evidence.group("session")
def session_group() -> None:
    """Manage deterministic and live session evidence."""


@session_group.command("validate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def session_validate(source: str, output: str) -> None:
    result = validate_session_artifact(source)
    _emit(result, output)
    if not result["valid"]:
        raise click.exceptions.Exit(1)


@session_group.command("aggregate")
@click.argument("artifacts", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def session_aggregate(artifacts: tuple[str, ...], output: str) -> None:
    _emit(aggregate_session_evidence(artifacts), output)


@evidence.group("baseline")
def baseline_group() -> None:
    """Manage comparable external baseline evidence."""


@baseline_group.command("validate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default="-")
def baseline_validate(source: str, output: str) -> None:
    result = validate_external_baseline(
        source,
        expected_task_digest=current_task_set_digest(),
        expected_grader_version=CURRENT_GRADER_VERSION,
    )
    _emit(result, output)
    if result["status"] in {"invalid", "incompatible"}:
        raise click.exceptions.Exit(1)


def _emit(payload: dict[str, Any], output: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output == "-":
        click.echo(serialized, nl=False)
        return
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized, encoding="utf-8")
