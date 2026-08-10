from __future__ import annotations

import json
from pathlib import Path

from agent_skill_eval.judge import check_expect, evaluate_rule_based
from agent_skill_eval.models import ExpectConfig, JudgeConfig, Rule, SessionResult, make_grading


def test_expect_failure_matches_go_golden_and_short_circuits(tmp_path: Path) -> None:
    result = SessionResult(exit_code=0, final_message="calculation error", turns=1)
    expect = ExpectConfig(must_contain=["calculation result"], must_not_contain=["error"])
    passed, assertions = check_expect(expect, result, tmp_path, tmp_path)
    assert passed is False
    grading = make_grading(assertions)
    golden_path = (
        Path(__file__).parents[1]
        / "e2e/testdata/expect-short-circuit/fixtures/expected/basic-arithmetic-grading.json"
    )
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert grading.model_dump(mode="json", exclude_none=False) == golden


def test_rule_based_failure_first_and_expect_merge(tmp_path: Path) -> None:
    result = SessionResult(exit_code=0, final_message="unsafe but complete")
    config = JudgeConfig(
        type="rule_based",
        failure=[Rule(output_contains={"all": ["unsafe"]})],
        success=[Rule(output_contains={"all": ["complete"]})],
    )
    grading = evaluate_rule_based(config, result, tmp_path, [])
    assert grading.status == "FAIL"
    assert grading.assertion_results[0].text.startswith("failure:")


def test_rule_based_success_includes_expect_assertions(tmp_path: Path) -> None:
    result = SessionResult(exit_code=0, final_message="hello bug")
    passed, assertions = check_expect(
        ExpectConfig(must_contain=["hello"]), result, tmp_path, tmp_path
    )
    assert passed is True
    grading = evaluate_rule_based(
        JudgeConfig(success=[Rule(output_contains={"all": ["bug"]})]),
        result,
        tmp_path,
        assertions,
    )
    assert grading.status == "PASS"
    assert next(item.text for item in grading.assertion_results) == "expect.must_contain"
