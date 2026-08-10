# agent-skill-eval Python preview

`agent-skill-eval` is the independently branded Python implementation being
developed alongside the existing Go CLI. The first release is a deliberately
small local vertical slice; it is not yet a complete replacement for `skill-up`.

## Install and verify

Python 3.11 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --dev
uv run agent-skill-eval --help
uv run agent-skill-eval validate examples/python-basic/evals/eval.yaml
uv run agent-skill-eval run examples/python-basic/evals/eval.yaml --output-dir .tmp/python-results
```

The same checks used by CI are:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
```

## First-stage support

- `v1alpha1` `eval.yaml` and `cases/*.yaml`, resolved from the directory that
  contains `SKILL.md`.
- `validate`, `list-cases`, and `run`.
- The local `none` runtime.
- A deterministic `fake` agent and structured custom local agents.
- Deterministic `expect` checks followed by a `rule_based` judge.
- `result.json` and per-case Anthropic-compatible `grading.json`.
- Optional `with_skill` / `without_skill` baseline variants.

Known but deferred features fail with an explicit `unsupported` error. These
include built-in Codex/Claude/Qoder/Qwen agents, HTTP custom agents,
OpenSandbox/Docker, MCP provisioning, multi-turn sessions, script and agent
judges, HTML/JUnit reports, and the broader benchmark/report command family.

## Custom local agent contract

The adapter writes a JSON `SessionInput` containing `case_id`, `variant`,
`workspace`, `model`, `messages`, `max_turns`, and `timeout_seconds`. Commands
receive paths using `${input_file}` and `${output_file}` placeholders. They
return a `SessionResult` JSON through the output file or stdout:

```json
{
  "exit_code": 0,
  "turns": 1,
  "final_message": "completed",
  "artifacts": {"generated_files": ["result.txt"]}
}
```

Commands are launched as an argument vector without a shell. Credentials must
be supplied through the custom agent environment and are redacted from surfaced
stderr; do not interpolate secrets into command arguments.

