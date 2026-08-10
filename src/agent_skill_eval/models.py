"""Typed domain models shared by loaders, agents, judges, and reporters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupStep(StrictModel):
    run: str


class EnvironmentConfig(StrictModel):
    type: str = "none"
    workspace_mount: str = "/workspace"
    env: dict[str, str] = Field(default_factory=dict)
    setup_steps: list[SetupStep] = Field(default_factory=list)
    image: str = ""
    sandbox_template: str = ""
    use_server_proxy: bool = False
    ready_timeout_seconds: int = 0
    sandbox_timeout_seconds: int = 0
    entrypoint: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    kwargs: dict[str, str] = Field(default_factory=dict)
    network_policy: str = ""
    allowed_egress: list[str] = Field(default_factory=list)


class MCPServer(StrictModel):
    name: str
    mode: str
    transport: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    endpoint: str = ""
    config_ref: str = ""


class MCPConfig(StrictModel):
    servers: list[MCPServer] = Field(default_factory=list)


class SkillRef(StrictModel):
    source: str
    path: str = ""
    target: str = ""
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class ModelConfig(StrictModel):
    provider: str = ""
    name: str = ""
    base_url: str = ""
    params: dict[str, str] = Field(default_factory=dict)


class CustomLocalConfig(StrictModel):
    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str = ""
    input_file: str = ""
    output_file: str = ""


class CustomEngineConfig(StrictModel):
    transport: str
    timeout_seconds: int = 0
    response_format: str = "session_result"
    env: dict[str, str] = Field(default_factory=dict)
    kwargs: dict[str, str] = Field(default_factory=dict)
    local: CustomLocalConfig | None = None
    http: dict[str, Any] | None = None


class EngineConfig(StrictModel):
    name: str
    version: str = ""
    entry: str = ""
    model: ModelConfig = Field(default_factory=ModelConfig)
    kwargs: dict[str, str] = Field(default_factory=dict)
    custom: CustomEngineConfig | None = None


class FileContainsCheck(StrictModel):
    path: str
    content: str


class ExpectConfig(StrictModel):
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    files_exist: list[str] = Field(default_factory=list)
    files_not_exist: list[str] = Field(default_factory=list)
    golden_file: str = ""
    file_contains: list[FileContainsCheck] = Field(default_factory=list)


class CaseDefaults(StrictModel):
    timeout_seconds: int = 300
    max_turns: int = 10
    collect_artifacts: list[str] = Field(default_factory=list)
    expect: ExpectConfig = Field(default_factory=ExpectConfig)


class RetryPolicy(StrictModel):
    max_retries: int = 0
    retry_on: list[str] = Field(default_factory=list)


class CasesConfig(StrictModel):
    files: list[str]
    defaults: CaseDefaults = Field(default_factory=CaseDefaults)
    parallelism: int = 1
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class Rule(StrictModel):
    output_contains: dict[str, list[str]] | None = None
    exit_code: int | None = None
    tool_called: dict[str, Any] | None = None
    files_exist: list[str] = Field(default_factory=list)
    files_not_exist: list[str] = Field(default_factory=list)
    turn_response_contains: dict[str, Any] | None = None
    turn_response_not_contains: dict[str, Any] | None = None
    tool_called_in_turn: dict[str, Any] | None = None
    tool_not_called_in_turn: dict[str, Any] | None = None


class JudgeConfig(StrictModel):
    type: str = "rule_based"
    script_path: str = ""
    model: str = ""
    criteria: list[str] = Field(default_factory=list)
    skills: list[SkillRef] = Field(default_factory=list)
    context: dict[str, Any] | None = None
    pass_threshold: float | None = None
    timeout_seconds: int | None = None
    success: list[Rule] = Field(default_factory=list)
    failure: list[Rule] = Field(default_factory=list)


class InputConfig(StrictModel):
    prompt: str = ""
    turns: list[dict[str, Any]] = Field(default_factory=list)


class GitContext(StrictModel):
    init: bool = False
    checkout: str = ""
    apply_diff: str = ""
    remotes: list[dict[str, str]] = Field(default_factory=list)


class ContextConfig(StrictModel):
    repo_fixture: str = ""
    git: GitContext | None = None
    files: dict[str, str] = Field(default_factory=dict)


class Constraints(StrictModel):
    timeout_seconds: int = 0
    max_turns: int = 0


class CaseConfig(StrictModel):
    id: str
    title: str
    description: str = ""
    tag: str = ""
    input: InputConfig
    context: ContextConfig = Field(default_factory=ContextConfig)
    constraints: Constraints = Field(default_factory=Constraints)
    expect: ExpectConfig = Field(default_factory=ExpectConfig)
    judge: JudgeConfig | None = None
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    collect_artifacts: list[str] = Field(default_factory=list)
    source_file: str = Field(default="", exclude=True)


class BenchmarkConfig(StrictModel):
    enabled: bool = False


class ReportConfig(StrictModel):
    formats: list[str] = Field(default_factory=lambda: ["json"])
    artifacts: list[str] = Field(default_factory=list)


class EvalConfig(StrictModel):
    schema_version: str
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    skills: list[SkillRef] = Field(default_factory=list)
    engine: EngineConfig
    cases: CasesConfig
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    benchmark: BenchmarkConfig = Field(default_factory=BenchmarkConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)


class SessionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    engine: str = ""
    model: str = ""
    session_id: str = ""
    exit_code: int
    duration_ms: int = 0
    turns: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    final_message: str = ""
    stderr: str = ""
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class AssertionResult(StrictModel):
    text: str
    passed: bool
    evidence: str


class ResultSummary(StrictModel):
    passed: int
    failed: int
    total: int
    pass_rate: float


class GradingResult(StrictModel):
    status: Literal["PASS", "FAIL", "SKIP"]
    skip_reason: str | None = None
    turns_executed: int = 1
    turns_total: int = 1
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    summary: ResultSummary


class CaseResult(StrictModel):
    case_id: str
    title: str
    status: Literal["PASS", "FAIL", "ERROR", "SKIP"]
    duration_ms: int
    turns: int
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    grading: GradingResult | None = None
    configuration: str = ""
    prompt: str = ""
    response: str = ""
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class RunReport(StrictModel):
    product: str = "agent-skill-eval"
    skill_name: str
    schema_version: str
    engine_name: str
    model_name: str
    start_time: datetime
    end_time: datetime
    case_results: list[CaseResult]
    total_tokens: int = 0


def make_grading(assertions: list[AssertionResult], turns: int = 1) -> GradingResult:
    passed = sum(item.passed for item in assertions)
    total = len(assertions)
    failed = total - passed
    status: Literal["PASS", "FAIL"] = "PASS" if failed == 0 else "FAIL"
    return GradingResult(
        status=status,
        turns_executed=turns,
        turns_total=turns,
        assertion_results=assertions,
        summary=ResultSummary(
            passed=passed,
            failed=failed,
            total=total,
            pass_rate=passed / total if total else 1.0,
        ),
    )
