"""Load and validate v1alpha1 evaluation suites."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agent_skill_eval.errors import ConfigError, UnsupportedFeatureError
from agent_skill_eval.models import CaseConfig, EvalConfig, ExpectConfig, JudgeConfig


@dataclass(frozen=True)
class LoadedSuite:
    config: EvalConfig
    cases: list[CaseConfig]
    eval_path: Path
    skill_dir: Path


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: document must be a YAML mapping")
    return value


def _skill_dir(eval_path: Path) -> Path:
    for parent in (eval_path.parent, *eval_path.parents):
        if (parent / "SKILL.md").is_file():
            return parent
    if eval_path.parent.name == "evals":
        return eval_path.parent.parent
    return eval_path.parent


def _inside(root: Path, raw: str, label: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ConfigError(f"{label}: path escapes Skill root: {raw!r}") from exc
    return candidate


def _merge_expect(defaults: ExpectConfig, case: ExpectConfig) -> ExpectConfig:
    return ExpectConfig(
        must_contain=[*defaults.must_contain, *case.must_contain],
        must_not_contain=[*defaults.must_not_contain, *case.must_not_contain],
        exit_code=case.exit_code if case.exit_code is not None else defaults.exit_code,
        files_exist=[*defaults.files_exist, *case.files_exist],
        files_not_exist=[*defaults.files_not_exist, *case.files_not_exist],
        golden_file=case.golden_file or defaults.golden_file,
        file_contains=[*defaults.file_contains, *case.file_contains],
    )


def _validate_supported(config: EvalConfig, cases: list[CaseConfig]) -> None:
    unsupported: list[str] = []
    if config.environment.type != "none":
        unsupported.append(f"environment.type={config.environment.type!r}")
    environment_only = (
        config.environment.image,
        config.environment.sandbox_template,
        config.environment.use_server_proxy,
        config.environment.ready_timeout_seconds,
        config.environment.sandbox_timeout_seconds,
        config.environment.entrypoint,
        config.environment.metadata,
        config.environment.kwargs,
        config.environment.network_policy,
        config.environment.allowed_egress,
    )
    if any(environment_only):
        unsupported.append("environment sandbox/network options")
    if config.mcp.servers or any(case.mcp.servers for case in cases):
        unsupported.append("mcp.servers")
    if config.cases.parallelism != 1:
        unsupported.append("cases.parallelism (only 1 is supported)")
    if config.cases.retry_policy.max_retries:
        unsupported.append("cases.retry_policy")
    if any(fmt not in {"json", "grading"} for fmt in config.report.formats):
        unsupported.append("report.formats (only json/grading are supported)")
    if config.engine.custom is None and config.engine.name != "fake":
        unsupported.append(
            f"engine.name={config.engine.name!r} (use fake or a custom local engine)"
        )
    if config.engine.custom is not None:
        custom = config.engine.custom
        if custom.transport != "local" or custom.local is None:
            unsupported.append("engine.custom.transport (only local is supported)")
        if custom.http is not None:
            unsupported.append("engine.custom.http")
    judges: list[JudgeConfig] = [config.judge]
    judges.extend(case.judge for case in cases if case.judge is not None)
    for judge in judges:
        if judge.type not in {"", "rule_based"}:
            unsupported.append(f"judge.type={judge.type!r}")
        if any(
            (
                judge.script_path,
                judge.model,
                judge.criteria,
                judge.skills,
                judge.context,
                judge.pass_threshold is not None,
                judge.timeout_seconds is not None,
            )
        ):
            unsupported.append("judge agent/script options")
        for rule in [*judge.success, *judge.failure]:
            if any(
                (
                    rule.tool_called,
                    rule.turn_response_contains,
                    rule.turn_response_not_contains,
                    rule.tool_called_in_turn,
                    rule.tool_not_called_in_turn,
                )
            ):
                unsupported.append("rule_based tool/per-turn assertions")
    if any(case.input.turns for case in cases):
        unsupported.append("input.turns (multi-turn sessions are deferred)")
    if any(case.context.git is not None for case in cases):
        unsupported.append("context.git")
    if unsupported:
        rendered = ", ".join(dict.fromkeys(unsupported))
        raise UnsupportedFeatureError(f"unsupported in agent-skill-eval 0.1: {rendered}")


def load_suite(path: str | Path) -> LoadedSuite:
    eval_path = Path(path).resolve()
    if not eval_path.is_file():
        raise ConfigError(f"evaluation config does not exist: {eval_path}")
    try:
        config = EvalConfig.model_validate(_yaml(eval_path))
    except ValidationError as exc:
        raise ConfigError(f"{eval_path}: {exc}") from exc
    if config.schema_version != "v1alpha1":
        raise ConfigError(f"schema_version: expected 'v1alpha1', got {config.schema_version!r}")
    skill_dir = _skill_dir(eval_path)
    for skill in config.skills:
        if skill.source != "local_path":
            raise UnsupportedFeatureError(
                f"unsupported in agent-skill-eval 0.1: skill.source={skill.source!r}"
            )
        source = _inside(skill_dir, skill.path or ".", "skills.path")
        if not source.is_dir():
            raise ConfigError(f"skills.path: directory does not exist: {skill.path!r}")
    cases: list[CaseConfig] = []
    seen: dict[str, str] = {}
    for raw in config.cases.files:
        case_path = _inside(skill_dir, raw, "cases.files")
        if not case_path.is_file():
            raise ConfigError(f"cases.files: file does not exist: {raw}")
        try:
            case = CaseConfig.model_validate(_yaml(case_path))
        except ValidationError as exc:
            raise ConfigError(f"{case_path}: {exc}") from exc
        if case.id in seen:
            raise ConfigError(f"duplicate case id {case.id!r} in {seen[case.id]!r} and {raw!r}")
        seen[case.id] = raw
        case.source_file = raw
        case.expect = _merge_expect(config.cases.defaults.expect, case.expect)
        if case.constraints.timeout_seconds <= 0:
            case.constraints.timeout_seconds = config.cases.defaults.timeout_seconds
        if case.constraints.max_turns <= 0:
            case.constraints.max_turns = config.cases.defaults.max_turns
        case.collect_artifacts = list(
            dict.fromkeys([*config.cases.defaults.collect_artifacts, *case.collect_artifacts])
        )
        if not case.input.prompt.strip():
            raise ConfigError(f"{raw}: input.prompt is required for a single-turn case")
        cases.append(case)
    if not cases:
        raise ConfigError("cases.files must load at least one case")
    _validate_supported(config, cases)
    return LoadedSuite(config=config, cases=cases, eval_path=eval_path, skill_dir=skill_dir)
