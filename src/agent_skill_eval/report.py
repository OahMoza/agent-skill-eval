"""Stable JSON and Anthropic-compatible grading report writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from agent_skill_eval.judge import grading_to_anthropic
from agent_skill_eval.models import CaseResult, RunReport


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_reports(report: RunReport, output_dir: Path) -> None:
    _write(output_dir / "result.json", report.model_dump(mode="json", exclude_none=True))
    for result in report.case_results:
        if result.grading is None:
            continue
        suffix = result.configuration or "with_skill"
        case_dir = output_dir / "iteration-1" / result.case_id / suffix
        _write(case_dir / "grading.json", grading_to_anthropic(result.grading))
        _write(
            case_dir / "eval_metadata.json",
            {
                "eval_name": result.case_id,
                "prompt": result.prompt,
                "assertions": [item.text for item in result.grading.assertion_results],
            },
        )
        outputs = case_dir / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "response.md").write_text(result.response, encoding="utf-8")
        _write(outputs / "transcript.json", result.transcript)


class Reporter(Protocol):
    def write(self, report: RunReport, output_dir: Path) -> None: ...


class JSONReporter:
    def write(self, report: RunReport, output_dir: Path) -> None:
        write_reports(report, output_dir)


def primary_results(results: list[CaseResult]) -> list[CaseResult]:
    by_id: dict[str, CaseResult] = {}
    order: list[str] = []
    for result in results:
        if result.case_id not in by_id:
            order.append(result.case_id)
        current = by_id.get(result.case_id)
        if result.configuration == "with_skill":
            by_id[result.case_id] = result
        elif current is None or current.configuration == "without_skill":
            by_id[result.case_id] = result
    return [by_id[case_id] for case_id in order]
