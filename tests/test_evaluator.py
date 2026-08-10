from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import write_suite

from agent_skill_eval.evaluator import Evaluator
from agent_skill_eval.loader import load_suite


def test_fake_agent_end_to_end_writes_reports(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "skill")
    output = tmp_path / "results"
    report = Evaluator(load_suite(path), output).run()
    assert report.case_results[0].status == "PASS"
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result["product"] == "agent-skill-eval"
    assert result["case_results"][0]["transcript"]
    grading = json.loads(
        (output / "iteration-1/basic/with_skill/grading.json").read_text(encoding="utf-8")
    )
    assert grading["summary"]["pass_rate"] == 1.0
    assert len(grading["expectations"]) == 2
    assert (output / "iteration-1/basic/with_skill/outputs/response.md").is_file()


def test_custom_local_agent_uses_structured_files(tmp_path: Path) -> None:
    root = tmp_path / "custom"
    script = root / "agent.py"
    root.mkdir(parents=True)
    script.write_text(
        """import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
result = {'exit_code': 0, 'turns': 1, 'final_message': 'handled ' + payload['case_id']}
pathlib.Path(sys.argv[2]).write_text(json.dumps(result), encoding='utf-8')
""",
        encoding="utf-8",
    )
    engine = {
        "name": "local-fixture",
        "custom": {
            "transport": "local",
            "response_format": "session_result",
            "local": {
                "command": sys.executable,
                "args": [str(script), "${input_file}", "${output_file}"],
            },
        },
    }
    case = {
        "id": "basic",
        "title": "Custom",
        "input": {"prompt": "ping"},
        "expect": {"must_contain": ["handled basic"]},
    }
    path = write_suite(root, engine=engine, case=case, judge={"type": "rule_based"})
    report = Evaluator(load_suite(path), tmp_path / "custom-results").run()
    assert report.case_results[0].status == "PASS"
    assert "inputs/messages.json" in report.case_results[0].artifacts["generated_files"]


def test_benchmark_emits_with_and_without_skill_variants(tmp_path: Path) -> None:
    path = write_suite(tmp_path / "benchmark")
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "benchmark:\n  enabled: true\n", encoding="utf-8")
    report = Evaluator(load_suite(path), tmp_path / "benchmark-results").run()
    assert [item.configuration for item in report.case_results] == [
        "with_skill",
        "without_skill",
    ]


@pytest.mark.parametrize(
    ("script_body", "custom_options", "expected"),
    [
        ("print('not-json')", {}, "invalid SessionResult"),
        (
            "import os, sys; print(os.environ['API_TOKEN'], file=sys.stderr); sys.exit(7)",
            {"env": {"API_TOKEN": "super-secret"}},
            "exited 7: [REDACTED]",
        ),
        (
            "import time; time.sleep(2)",
            {"timeout_seconds": 1},
            "timed out after 1s",
        ),
    ],
)
def test_custom_local_agent_reports_stable_redacted_errors(
    tmp_path: Path,
    script_body: str,
    custom_options: dict[str, object],
    expected: str,
) -> None:
    root = tmp_path / expected.replace(" ", "-").replace(":", "")
    root.mkdir(parents=True)
    script = root / "agent.py"
    script.write_text(script_body, encoding="utf-8")
    custom = {
        "transport": "local",
        "response_format": "session_result",
        "local": {"command": sys.executable, "args": [str(script)]},
        **custom_options,
    }
    path = write_suite(root, engine={"name": "broken-local", "custom": custom})
    result = Evaluator(load_suite(path), tmp_path / "errors").run().case_results[0]
    assert result.status == "ERROR"
    assert expected in result.error
    assert "super-secret" not in result.error
