"""Deterministic expect checks and the first-stage rule-based judge."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from agent_skill_eval.errors import ConfigError, UnsupportedFeatureError
from agent_skill_eval.models import (
    AssertionResult,
    ExpectConfig,
    GradingResult,
    JudgeConfig,
    Rule,
    SessionResult,
    make_grading,
)


def _safe(root: Path, raw: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ConfigError(f"path escapes workspace: {raw!r}") from exc
    return candidate


def check_expect(
    expect: ExpectConfig, result: SessionResult, workspace: Path, skill_dir: Path
) -> tuple[bool, list[AssertionResult]]:
    groups: list[tuple[str, list[str]]] = []
    if expect.must_contain:
        groups.append(
            (
                "must_contain",
                [
                    f'output does not contain "{item}"'
                    for item in expect.must_contain
                    if item not in result.final_message
                ],
            )
        )
    if expect.must_not_contain:
        groups.append(
            (
                "must_not_contain",
                [
                    f'output contains forbidden keyword "{item}"'
                    for item in expect.must_not_contain
                    if item in result.final_message
                ],
            )
        )
    if expect.exit_code is not None:
        failures = (
            []
            if result.exit_code == expect.exit_code
            else [f"expected exit_code {expect.exit_code}, got {result.exit_code}"]
        )
        groups.append(("exit_code", failures))
    if expect.files_exist:
        groups.append(
            (
                "files_exist",
                [
                    f'expected file "{item}" does not exist'
                    for item in expect.files_exist
                    if not _safe(workspace, item).exists()
                ],
            )
        )
    if expect.files_not_exist:
        groups.append(
            (
                "files_not_exist",
                [
                    f'file "{item}" should not exist but does'
                    for item in expect.files_not_exist
                    if _safe(workspace, item).exists()
                ],
            )
        )
    if expect.golden_file:
        golden = _safe(skill_dir, expect.golden_file)
        if not golden.is_file():
            failures = [f'cannot read golden file "{expect.golden_file}"']
        else:
            expected = golden.read_text(encoding="utf-8").strip()
            failures = (
                []
                if expected == result.final_message.strip()
                else [f'output does not match golden file "{expect.golden_file}"']
            )
        groups.append(("golden_file", failures))
    if expect.file_contains:
        failures = []
        for check in expect.file_contains:
            path = _safe(workspace, check.path)
            if not path.is_file():
                failures.append(f'cannot read file "{check.path}"')
            elif check.content not in path.read_text(encoding="utf-8"):
                failures.append(f'file "{check.path}" does not contain "{check.content}"')
        groups.append(("file_contains", failures))
    assertions = [
        AssertionResult(
            text=f"expect.{name}",
            passed=not failures,
            evidence="all checks passed" if not failures else "; ".join(failures),
        )
        for name, failures in groups
    ]
    return all(item.passed for item in assertions), assertions


def _rule(rule: Rule, result: SessionResult, workspace: Path) -> AssertionResult:
    populated = [
        name
        for name in (
            "output_contains",
            "exit_code",
            "tool_called",
            "files_exist",
            "files_not_exist",
            "turn_response_contains",
            "turn_response_not_contains",
            "tool_called_in_turn",
            "tool_not_called_in_turn",
        )
        if getattr(rule, name) not in (None, [], {})
    ]
    if len(populated) != 1:
        return AssertionResult(
            text="unknown_rule", passed=False, evidence="exactly one rule field is required"
        )
    name = populated[0]
    if name == "output_contains":
        config = rule.output_contains or {}
        all_values = config.get("all", [])
        any_values = config.get("any", [])
        not_values = config.get("not", [])
        missing = [item for item in all_values if item not in result.final_message]
        forbidden = [item for item in not_values if item in result.final_message]
        any_ok = not any_values or any(item in result.final_message for item in any_values)
        passed = not missing and not forbidden and any_ok
        evidence = "all output_contains checks passed"
        if missing:
            evidence = f"output does not contain required keywords: {missing}"
        elif forbidden:
            evidence = f"output contains forbidden keywords: {forbidden}"
        elif not any_ok:
            evidence = f"output does not contain any of {any_values}"
        return AssertionResult(text=f"output_contains:{config}", passed=passed, evidence=evidence)
    if name == "exit_code":
        passed = result.exit_code == rule.exit_code
        return AssertionResult(
            text=f"exit_code: {rule.exit_code}",
            passed=passed,
            evidence=(
                f"exit_code is {result.exit_code} as expected"
                if passed
                else f"expected exit_code {rule.exit_code}, got {result.exit_code}"
            ),
        )
    if name in {"files_exist", "files_not_exist"}:
        paths = getattr(rule, name)
        exists = [_safe(workspace, item).exists() for item in paths]
        passed = all(exists) if name == "files_exist" else not any(exists)
        return AssertionResult(
            text=f"{name}: {paths}",
            passed=passed,
            evidence="file checks passed" if passed else "file checks failed",
        )
    raise UnsupportedFeatureError(f"unsupported rule_based assertion: {name}")


def evaluate_rule_based(
    config: JudgeConfig,
    result: SessionResult,
    workspace: Path,
    expect_assertions: list[AssertionResult],
) -> GradingResult:
    assertions = list(expect_assertions)
    for failure in config.failure:
        evaluated = _rule(failure, result, workspace)
        if evaluated.passed:
            assertions.append(
                AssertionResult(
                    text=f"failure: {evaluated.text}",
                    passed=False,
                    evidence=f"failure rule matched: {evaluated.evidence}",
                )
            )
            return make_grading(assertions, result.turns)
    assertions.extend(_rule(rule, result, workspace) for rule in config.success)
    return make_grading(assertions, result.turns)


class Judge(Protocol):
    def evaluate(
        self,
        result: SessionResult,
        workspace: Path,
        expect_assertions: list[AssertionResult],
    ) -> GradingResult: ...


class RuleBasedJudge:
    def __init__(self, config: JudgeConfig) -> None:
        self.config = config

    def evaluate(
        self,
        result: SessionResult,
        workspace: Path,
        expect_assertions: list[AssertionResult],
    ) -> GradingResult:
        return evaluate_rule_based(self.config, result, workspace, expect_assertions)


def grading_to_anthropic(grading: GradingResult) -> dict[str, Any]:
    return {
        "expectations": [item.model_dump() for item in grading.assertion_results],
        "summary": grading.summary.model_dump(),
    }
