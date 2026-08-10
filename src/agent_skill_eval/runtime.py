"""Runtime protocol and the local none runtime."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_skill_eval.errors import AgentSkillEvalError, ConfigError
from agent_skill_eval.models import EnvironmentConfig


@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class Runtime(Protocol):
    @property
    def workspace(self) -> Path: ...

    def create(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    def resolve(self, path: str | Path) -> Path: ...
    def upload_file(self, source: Path, target: str) -> None: ...
    def upload_dir(self, source: Path, target: str) -> None: ...
    def download_file(self, source: str, target: Path) -> None: ...
    def exec(
        self,
        argv: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> ExecResult: ...


class NoneRuntime:
    def __init__(self, config: EnvironmentConfig) -> None:
        self.config = config
        self._temp: tempfile.TemporaryDirectory[str] | None = None
        self._workspace: Path | None = None

    @property
    def workspace(self) -> Path:
        if self._workspace is None:
            raise AgentSkillEvalError("runtime has not been created")
        return self._workspace

    def create(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="agent-skill-eval-")
        self._workspace = Path(self._temp.name).resolve()

    def start(self) -> None:
        for step in self.config.setup_steps:
            argv = shlex.split(step.run, posix=os.name != "nt")
            if not argv:
                continue
            result = self.exec(argv)
            if result.exit_code != 0:
                raise ConfigError(f"environment setup step failed: {result.stderr.strip()}")

    def stop(self) -> None:
        return None

    def close(self) -> None:
        if self._temp is not None:
            self._temp.cleanup()
        self._temp = None
        self._workspace = None

    def resolve(self, path: str | Path) -> Path:
        raw = Path(path)
        candidate = raw.resolve() if raw.is_absolute() else (self.workspace / raw).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ConfigError(f"workspace path escapes runtime: {path!s}") from exc
        return candidate

    def upload_file(self, source: Path, target: str) -> None:
        destination = self.resolve(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def upload_dir(self, source: Path, target: str) -> None:
        destination = self.resolve(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True, copy_function=shutil.copy2)

    def download_file(self, source: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.resolve(source), target)

    def exec(
        self,
        argv: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> ExecResult:
        if not argv:
            raise ConfigError("runtime.exec requires a non-empty argv")
        run_cwd = self.workspace if cwd is None else self.resolve(cwd)
        run_env = os.environ.copy()
        run_env.update(self.config.env)
        if env:
            run_env.update(env)
        try:
            completed = subprocess.run(  # noqa: S603 - argv only, never a shell string
                list(argv),
                cwd=run_cwd,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=timeout if timeout > 0 else None,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                stdout=_text(exc.stdout),
                stderr=_text(exc.stderr) or f"process timed out after {timeout}s",
                exit_code=124,
                timed_out=True,
            )
        except OSError as exc:
            return ExecResult(stdout="", stderr=str(exc), exit_code=127)
        return ExecResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )


def _text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
