from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_skill_eval.errors import ConfigError
from agent_skill_eval.models import EnvironmentConfig
from agent_skill_eval.runtime import NoneRuntime


def test_none_runtime_executes_argv_and_confines_paths() -> None:
    runtime = NoneRuntime(EnvironmentConfig())
    runtime.create()
    try:
        result = runtime.exec([sys.executable, "-c", "print('ok')"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "ok"
        with pytest.raises(ConfigError, match="escapes runtime"):
            runtime.resolve("../outside")
    finally:
        runtime.close()


def test_none_runtime_transfers_files(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    runtime = NoneRuntime(EnvironmentConfig())
    runtime.create()
    try:
        runtime.upload_file(source, "nested/target.txt")
        destination = tmp_path / "downloaded.txt"
        runtime.download_file("nested/target.txt", destination)
        assert destination.read_text(encoding="utf-8") == "payload"
    finally:
        runtime.close()
