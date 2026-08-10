"""Command-line interface for agent-skill-eval."""

from __future__ import annotations

from pathlib import Path

import click

from agent_skill_eval.errors import AgentSkillEvalError
from agent_skill_eval.evaluator import Evaluator
from agent_skill_eval.loader import load_suite
from agent_skill_eval.report import primary_results


def _fail(message: str) -> None:
    click.echo(f"error: {message}", err=True)
    raise click.exceptions.Exit(2)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="agent-skill-eval")
def cli() -> None:
    """Evaluate Agent Skills from declarative v1alpha1 suites."""


@cli.command()
@click.argument("config", type=click.Path(path_type=Path, dir_okay=False))
def validate(config: Path) -> None:
    """Validate an eval.yaml and all referenced cases."""
    try:
        suite = load_suite(config)
    except AgentSkillEvalError as exc:
        _fail(str(exc))
    click.echo(f"valid: {len(suite.cases)} case(s), schema {suite.config.schema_version}")


@cli.command("list-cases")
@click.argument("config", type=click.Path(path_type=Path, dir_okay=False))
@click.option("--tag", help="Only list cases with this tag.")
def list_cases(config: Path, tag: str | None) -> None:
    """List case IDs, titles, and tags in configuration order."""
    try:
        suite = load_suite(config)
    except AgentSkillEvalError as exc:
        _fail(str(exc))
    for case in suite.cases:
        if tag and case.tag != tag:
            continue
        click.echo(f"{case.id}\t{case.title}\t{case.tag}")


@cli.command()
@click.argument("config", type=click.Path(path_type=Path, dir_okay=False))
@click.option("--case", "case_ids", multiple=True, help="Run only the selected case ID.")
@click.option("--tag", help="Run only cases with this tag.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default="agent-skill-eval-results",
    show_default=True,
)
def run(config: Path, case_ids: tuple[str, ...], tag: str | None, output_dir: Path) -> None:
    """Run selected cases and write result.json plus per-case grading.json."""
    try:
        suite = load_suite(config)
        requested = set(case_ids)
        known = {case.id for case in suite.cases}
        missing = sorted(requested - known)
        if missing:
            _fail(f"unknown case id(s): {', '.join(missing)}")
        cases = [
            case
            for case in suite.cases
            if (not requested or case.id in requested) and (not tag or case.tag == tag)
        ]
        if not cases:
            _fail("case filters matched no cases")
        report = Evaluator(suite, output_dir).run(cases)
    except AgentSkillEvalError as exc:
        _fail(str(exc))
    primary = primary_results(report.case_results)
    for result in primary:
        click.echo(f"{result.status}\t{result.case_id}\t{result.duration_ms}ms")
    click.echo(f"report: {(output_dir / 'result.json').resolve()}")
    if any(result.status in {"FAIL", "ERROR"} for result in primary):
        raise click.exceptions.Exit(1)


def main() -> None:
    cli(prog_name="agent-skill-eval")
