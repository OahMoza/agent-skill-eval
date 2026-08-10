from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from conftest import write_suite

from agent_skill_eval.cli import cli


def test_validate_list_and_run_commands(tmp_path: Path) -> None:
    config = write_suite(tmp_path / "cli")
    runner = CliRunner()
    validated = runner.invoke(cli, ["validate", str(config)])
    assert validated.exit_code == 0
    assert "valid: 1 case" in validated.output
    listed = runner.invoke(cli, ["list-cases", str(config)])
    assert listed.exit_code == 0
    assert "basic\tBasic case\tfunctional_test" in listed.output
    output = tmp_path / "output"
    ran = runner.invoke(cli, ["run", str(config), "--output-dir", str(output)])
    assert ran.exit_code == 0
    assert "PASS\tbasic" in ran.output


def test_unknown_command_has_nonzero_exit_and_help() -> None:
    result = CliRunner().invoke(cli, ["report"])
    assert result.exit_code != 0
    assert "No such command" in result.output
