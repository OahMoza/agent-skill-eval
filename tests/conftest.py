from __future__ import annotations

from pathlib import Path

import yaml


def write_suite(
    root: Path,
    *,
    engine: dict[str, object] | None = None,
    case: dict[str, object] | None = None,
    judge: dict[str, object] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("---\nname: fixture\n---\n", encoding="utf-8")
    evals = root / "evals"
    cases = evals / "cases"
    cases.mkdir(parents=True)
    config = {
        "schema_version": "v1alpha1",
        "environment": {"type": "none"},
        "engine": engine or {"name": "fake", "kwargs": {"response": "hello bug"}},
        "cases": {"files": ["evals/cases/basic.yaml"]},
        "judge": judge
        or {
            "type": "rule_based",
            "success": [{"output_contains": {"all": ["hello", "bug"]}}],
        },
        "report": {"formats": ["json"]},
    }
    case_config = case or {
        "id": "basic",
        "title": "Basic case",
        "tag": "functional_test",
        "input": {"prompt": "say hello"},
        "expect": {"must_contain": ["hello"]},
    }
    (evals / "eval.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (cases / "basic.yaml").write_text(yaml.safe_dump(case_config), encoding="utf-8")
    return evals / "eval.yaml"
