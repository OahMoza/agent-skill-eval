from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import write_suite

from agent_skill_eval.errors import ConfigError, UnsupportedFeatureError
from agent_skill_eval.loader import load_suite


def test_loads_cases_relative_to_skill_root(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "demo")
    suite = load_suite(path)
    assert suite.skill_dir == tmp_path / "demo"
    assert [case.id for case in suite.cases] == ["basic"]
    assert suite.cases[0].constraints.timeout_seconds == 300


def test_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "demo")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["cases"]["files"].append("evals/cases/duplicate.yaml")
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    duplicate = path.parent / "cases" / "duplicate.yaml"
    duplicate.write_text(
        yaml.safe_dump({"id": "basic", "title": "Duplicate", "input": {"prompt": "x"}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate case id"):
        load_suite(path)


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"environment": {"type": "opensandbox"}}, "environment.type"),
        ({"judge": {"type": "script", "script_path": "judge.py"}}, "judge.type"),
        ({"report": {"formats": ["html"]}}, "report.formats"),
    ],
)
def test_known_deferred_features_are_explicitly_unsupported(
    tmp_path: Path, patch: dict[str, object], message: str
) -> None:
    path = write_suite(tmp_path / message.replace(".", "-"))
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config.update(patch)
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(UnsupportedFeatureError, match=message):
        load_suite(path)


def test_rejects_case_path_escape(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "demo")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["cases"]["files"] = ["../outside.yaml"]
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ConfigError, match="escapes Skill root"):
        load_suite(path)


def test_merges_default_and_case_expect_rules(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "merge")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["cases"]["defaults"] = {"expect": {"must_contain": ["hello"], "exit_code": 0}}
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    case_path = path.parent / "cases/basic.yaml"
    case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    case["expect"] = {"must_contain": ["bug"], "exit_code": 2}
    case_path.write_text(yaml.safe_dump(case), encoding="utf-8")
    loaded = load_suite(path).cases[0]
    assert loaded.expect.must_contain == ["hello", "bug"]
    assert loaded.expect.exit_code == 2
