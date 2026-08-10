"""Case orchestration for the first-stage evaluation vertical slice."""

from __future__ import annotations

import fnmatch
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from agent_skill_eval.agent import Agent, create_agent
from agent_skill_eval.errors import AgentSkillEvalError, ConfigError
from agent_skill_eval.judge import RuleBasedJudge, check_expect
from agent_skill_eval.loader import LoadedSuite
from agent_skill_eval.models import CaseConfig, CaseResult, RunReport
from agent_skill_eval.report import JSONReporter, Reporter
from agent_skill_eval.runtime import NoneRuntime


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


class Evaluator:
    def __init__(
        self, suite: LoadedSuite, output_dir: Path, reporter: Reporter | None = None
    ) -> None:
        self.suite = suite
        self.output_dir = output_dir.resolve()
        self.agent: Agent = create_agent(suite.config.engine)
        self.reporter = reporter or JSONReporter()

    def _prepare_context(self, runtime: NoneRuntime, case: CaseConfig) -> None:
        if case.context.repo_fixture:
            source = (self.suite.skill_dir / case.context.repo_fixture).resolve()
            try:
                source.relative_to(self.suite.skill_dir.resolve())
            except ValueError as exc:
                raise ConfigError(
                    f"context.repo_fixture escapes Skill root: {case.context.repo_fixture!r}"
                ) from exc
            if not source.is_dir():
                raise ConfigError(
                    f"context.repo_fixture does not exist: {case.context.repo_fixture}"
                )
            runtime.upload_dir(source, ".")
        for raw, content in case.context.files.items():
            target = runtime.resolve(raw)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _collect_artifacts(self, runtime: NoneRuntime, case: CaseConfig, suffix: str) -> list[str]:
        collected: list[str] = []
        target_root = self.output_dir / "iteration-1" / case.id / suffix / "outputs" / "workspace"
        for path in runtime.workspace.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(runtime.workspace).as_posix()
            if not any(fnmatch.fnmatch(relative, pattern) for pattern in case.collect_artifacts):
                continue
            destination = target_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            collected.append(relative)
        return collected

    def _run_case(self, case: CaseConfig, variant: str) -> CaseResult:
        started = time.monotonic()
        runtime = NoneRuntime(self.suite.config.environment)
        suffix = variant or "default"
        try:
            runtime.create()
            runtime.start()
            self.agent.install(runtime)
            self.agent.check(runtime)
            self.agent.install_mcp(runtime)
            self._prepare_context(runtime, case)
            if variant != "without_skill":
                for skill in self.suite.config.skills:
                    self.agent.install_skill(runtime, skill, self.suite.skill_dir)
            before = _snapshot(runtime.workspace)
            session = self.agent.run(runtime, case, variant)
            after = _snapshot(runtime.workspace)
            changed = sorted(
                path for path, state in after.items() if path not in before or before[path] != state
            )
            removed = sorted(path for path in before if path not in after)
            session.artifacts["workspace_diff"] = {"changed": changed, "removed": removed}
            session.artifacts["collected_files"] = self._collect_artifacts(runtime, case, suffix)
            expect_ok, expect_assertions = check_expect(
                case.expect, session, runtime.workspace, self.suite.skill_dir
            )
            if expect_ok:
                judge_config = case.judge or self.suite.config.judge
                grading = RuleBasedJudge(judge_config).evaluate(
                    session, runtime.workspace, expect_assertions
                )
            else:
                from agent_skill_eval.models import make_grading

                grading = make_grading(expect_assertions, session.turns)
            status = grading.status
            return CaseResult(
                case_id=case.id,
                title=case.title,
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
                turns=session.turns,
                input_tokens=session.input_tokens,
                output_tokens=session.output_tokens,
                grading=grading,
                configuration=variant,
                prompt=case.input.prompt,
                response=session.final_message,
                transcript=session.transcript,
                artifacts=session.artifacts,
            )
        except AgentSkillEvalError as exc:
            return CaseResult(
                case_id=case.id,
                title=case.title,
                status="ERROR",
                duration_ms=int((time.monotonic() - started) * 1000),
                turns=0,
                error=str(exc),
                configuration=variant,
                prompt=case.input.prompt,
            )
        finally:
            runtime.stop()
            runtime.close()

    def run(self, cases: list[CaseConfig] | None = None) -> RunReport:
        selected = cases or self.suite.cases
        start = datetime.now(UTC)
        self.agent.check_credentials()
        variants = (
            ["with_skill", "without_skill"]
            if self.suite.config.benchmark.enabled
            else ["with_skill"]
        )
        results = [self._run_case(case, variant) for case in selected for variant in variants]
        end = datetime.now(UTC)
        model = self.suite.config.engine.model
        model_name = "/".join(item for item in (model.provider, model.name) if item)
        report = RunReport(
            skill_name=self.suite.skill_dir.name,
            schema_version=self.suite.config.schema_version,
            engine_name=self.suite.config.engine.name,
            model_name=model_name,
            start_time=start,
            end_time=end,
            case_results=results,
            total_tokens=sum(item.input_tokens + item.output_tokens for item in results),
        )
        self.reporter.write(report, self.output_dir)
        return report
