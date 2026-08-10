"""Agent protocol plus deterministic fake and custom-local adapters."""

from __future__ import annotations

import json
import os
import re
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from agent_skill_eval.errors import AgentExecutionError, ConfigError
from agent_skill_eval.models import CaseConfig, EngineConfig, SessionResult, SkillRef
from agent_skill_eval.runtime import Runtime


class Agent(Protocol):
    def install(self, runtime: Runtime) -> None: ...
    def check(self, runtime: Runtime) -> None: ...
    def check_credentials(self) -> None: ...
    def install_skill(self, runtime: Runtime, skill: SkillRef, skill_dir: Path) -> None: ...
    def install_mcp(self, runtime: Runtime) -> None: ...
    def run(self, runtime: Runtime, case: CaseConfig, variant: str) -> SessionResult: ...


class SessionResumer(Protocol):
    def run_turn(
        self, runtime: Runtime, case: CaseConfig, message: str, session_id: str
    ) -> SessionResult: ...


class BaseAgent:
    def __init__(self, config: EngineConfig) -> None:
        self.config = config

    def install(self, runtime: Runtime) -> None:
        del runtime

    def check(self, runtime: Runtime) -> None:
        del runtime

    def check_credentials(self) -> None:
        return None

    def install_skill(self, runtime: Runtime, skill: SkillRef, skill_dir: Path) -> None:
        if skill.source != "local_path":
            raise ConfigError(f"unsupported skill source: {skill.source!r}")
        source = (skill_dir / (skill.path or ".")).resolve()
        try:
            source.relative_to(skill_dir.resolve())
        except ValueError as exc:
            raise ConfigError(f"skill path escapes Skill root: {skill.path!r}") from exc
        if not source.exists():
            raise ConfigError(f"skill path does not exist: {skill.path!r}")
        target = skill.target or source.name or "skill"
        includes = skill.include or ["**/*"]
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            included = any(_matches(relative, pattern) for pattern in includes)
            excluded = any(_matches(relative, pattern) for pattern in skill.exclude)
            if included and not excluded:
                runtime.upload_file(path, f".agent-skills/{target}/{relative}")

    def install_mcp(self, runtime: Runtime) -> None:
        del runtime


class FakeAgent(BaseAgent):
    def run(self, runtime: Runtime, case: CaseConfig, variant: str) -> SessionResult:
        del runtime, variant
        started = time.monotonic()
        response = self.config.kwargs.get("response", case.input.prompt)
        return SessionResult(
            engine="fake",
            model="fake/deterministic",
            exit_code=int(self.config.kwargs.get("exit_code", "0")),
            duration_ms=int((time.monotonic() - started) * 1000),
            turns=1,
            final_message=response,
            transcript=[
                {"role": "user", "content": case.input.prompt},
                {"role": "assistant", "content": response},
            ],
        )


_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")


class CustomLocalAgent(BaseAgent):
    def _render(self, value: str, variables: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in variables:
                return variables[key]
            if key in os.environ:
                return os.environ[key]
            raise ConfigError(f"unknown custom engine template variable: ${{{key}}}")

        return _PLACEHOLDER.sub(replace, value)

    @staticmethod
    def _mask(value: str, secrets: list[str]) -> str:
        masked = value
        for secret in secrets:
            if secret:
                masked = masked.replace(secret, "[REDACTED]")
        return masked

    def run(self, runtime: Runtime, case: CaseConfig, variant: str) -> SessionResult:
        custom = self.config.custom
        if custom is None or custom.local is None:
            raise ConfigError("engine.custom.local is required")
        local = custom.local
        input_path = runtime.resolve(local.input_file or "inputs/messages.json")
        output_path = runtime.resolve(local.output_file or "outputs/session-result.json")
        timeout = custom.timeout_seconds or case.constraints.timeout_seconds
        model = "/".join(
            item for item in (self.config.model.provider, self.config.model.name) if item
        )
        kwargs = dict(custom.kwargs)
        session_input: dict[str, Any] = {
            "case_id": case.id,
            "variant": variant,
            "workspace": str(runtime.workspace),
            "model": model,
            "kwargs": kwargs,
            "messages": [{"role": "user", "content": case.input.prompt}],
            "max_turns": case.constraints.max_turns,
            "timeout_seconds": timeout,
        }
        input_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.unlink(missing_ok=True)
        input_path.write_text(json.dumps(session_input, ensure_ascii=False), encoding="utf-8")
        variables = {
            "workspace": str(runtime.workspace),
            "prompt": case.input.prompt,
            "input_file": str(input_path),
            "output_file": str(output_path),
            "model": model,
            "model_provider": self.config.model.provider,
            "model_name": self.config.model.name,
            "case_id": case.id,
            "variant": variant,
            "max_turns": str(case.constraints.max_turns),
            "timeout_seconds": str(timeout),
            **{f"kwargs.{key}": value for key, value in kwargs.items()},
        }
        argv = [self._render(local.command, variables)]
        argv.extend(self._render(item, variables) for item in local.args)
        rendered_env = {key: self._render(value, variables) for key, value in custom.env.items()}
        cwd = self._render(local.cwd, variables) if local.cwd else None
        started = time.monotonic()
        result = runtime.exec(argv, cwd=cwd, env=rendered_env, timeout=timeout)
        duration_ms = int((time.monotonic() - started) * 1000)
        secrets = [
            value
            for key, value in rendered_env.items()
            if any(marker in key.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
        ]
        stderr = self._mask(result.stderr, secrets)
        if result.timed_out:
            raise AgentExecutionError(f"custom local agent timed out after {timeout}s")
        if result.exit_code != 0:
            raise AgentExecutionError(
                f"custom local agent exited {result.exit_code}: {stderr.strip()}"
            )
        if custom.response_format == "text":
            final = result.stdout
            return SessionResult(
                engine=self.config.name,
                model=model,
                exit_code=0,
                duration_ms=duration_ms,
                turns=1,
                final_message=final,
                stderr=stderr,
                transcript=[
                    {"role": "user", "content": case.input.prompt},
                    {"role": "assistant", "content": final},
                ],
                artifacts={
                    "generated_files": [input_path.relative_to(runtime.workspace).as_posix()]
                },
            )
        raw = output_path.read_text(encoding="utf-8") if output_path.is_file() else result.stdout
        if not raw.strip():
            raise AgentExecutionError("custom local agent returned no SessionResult JSON")
        try:
            parsed = SessionResult.model_validate_json(raw)
        except ValidationError as exc:
            raise AgentExecutionError(
                f"custom local agent returned invalid SessionResult: {exc}"
            ) from exc
        parsed.duration_ms = parsed.duration_ms or duration_ms
        parsed.engine = parsed.engine or self.config.name
        parsed.model = parsed.model or model
        parsed.stderr = self._mask(parsed.stderr or stderr, secrets)
        if not parsed.transcript:
            parsed.transcript = [
                {"role": "user", "content": case.input.prompt},
                {"role": "assistant", "content": parsed.final_message},
            ]
        generated = parsed.artifacts.setdefault("generated_files", [])
        generated.append(input_path.relative_to(runtime.workspace).as_posix())
        if output_path.is_file():
            generated.append(output_path.relative_to(runtime.workspace).as_posix())
        if parsed.exit_code != 0:
            raise AgentExecutionError(
                f"custom local agent result reported exit {parsed.exit_code}: {parsed.stderr}"
            )
        return parsed


def create_agent(config: EngineConfig) -> Agent:
    if config.name == "fake" and config.custom is None:
        return FakeAgent(config)
    if config.custom is not None and config.custom.transport == "local":
        return CustomLocalAgent(config)
    raise ConfigError(f"unsupported engine: {config.name!r}")


def _matches(path: str, pattern: str) -> bool:
    return fnmatch(path, pattern) or (
        pattern.startswith("**/") and fnmatch(path, pattern.removeprefix("**/"))
    )
