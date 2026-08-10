# Outcome

以现有 skill-up 的产品能力和行为为参考，构建由用户独立维护、以 Python 实现的 Agent Skill 评测项目 `agent-skill-eval`。最终项目应具备自主品牌、Python 工程结构、可测试的扩展边界，并能在真实 Agent 评测工作流中使用。

# Scope

- 将现有产品拆解为 Python 领域模块：配置加载与验证、Agent Engine 适配、Runtime 隔离、Case 执行编排、Judge、报告与 CLI。
- 建立 Python 包、命令行入口、自动化测试、示例配置和用户文档。
- 使用 distribution `agent-skill-eval`、import package `agent_skill_eval`、CLI 命令 `agent-skill-eval`，报告中的产品标识同步使用 `agent-skill-eval`。
- 第一阶段采用 Go/Python 并存：保留现有 Go 实现、Go 测试和 Go CI 作为行为基准，在仓库中新增独立的 Python `src/agent_skill_eval` 实现、Python 测试和 Python 工具链。
- 第一阶段正式支持 Windows 与 Linux，并在两个平台运行 Python 自动化测试；macOS 保持可移植设计，但不作为第一阶段验证和发布门槛。
- 兼容现有 `v1alpha1` `eval.yaml`、`cases/*.yaml`、核心 CLI 语义、退出码和机器可读报告契约，使已有评测资产可以迁移和差分验证。
- 第一阶段交付本地核心垂直切片：Python 包与 CLI、配置加载/验证、`none` Runtime、Custom/Fake Agent、`expect`、`rule_based` Judge、JSON/grading 报告和端到端测试。
- 在独立 worktree `E:\WorkSpace\github\skill-up\.worktrees\python-rewrite` 和分支 `comet/python-rewrite` 中完成，不混入主工作区现有未提交内容。
- 验证后的独立项目目标为 GitLab `git@gitlab.dc.servyou-it.com:nsp/agent-skill-eval.git`，默认分支 `master`，以新的 `Initial commit` 开始而不携带上游 Git 提交历史。

# Non-goals

- 不逐行翻译 Go 源码或机械复制其内部结构。
- 不保留 Go 的 `pkg/skillup` / `pkg/transcript` 二进制或源码级 API。
- 在推送时点确认且 GitLab SSH 可访问前，不向目标远端发布；不宣称与原项目官方有关联。
- 不删除或覆盖主工作区中的 Go 项目和用户未提交内容。
- 第一阶段不实现内置 Claude Code/Codex/Qoder/Qwen Agent、Docker/OpenSandbox、真实 MCP、多轮会话、`script`/`agent_judge`、HTML/JUnit 和完整 benchmark；这些作为后续兼容阶段。
- 第一阶段不删除 Go 源码、`go.mod`、Go 测试、Go CI 或现有 Go 文档入口；最终 Python-only 切换在达到足够兼容度后通过后续 change 完成。

# Acceptance examples

- Python CLI 能发现并加载一个 Skill 的评测配置，验证 Case，并给出稳定、可读的错误。
- 一个测试 Case 能在隔离 Runtime 中调用 Agent，执行确定性 `expect` 检查和配置的 Judge，并生成结构化结果。
- 支持至少一个真实 Agent 适配器和一个可用于测试的自定义/假 Agent 适配器。
- 结果包含 Case 状态、证据、transcript、artifact 元数据，并能生成用户确认范围内的报告格式。
- 自动化测试覆盖配置、执行、判分和报告的主链路；公开示例可在无真实 API key 的情况下验证核心流程。

# Constraints and invariants

- Python 实现必须形成清晰的依赖方向：CLI 组装，领域逻辑不依赖 CLI；Agent、Runtime、Judge 通过协议/接口扩展。
- 凭据不得写入仓库、日志或报告；继续遵守 CLI 参数、环境变量和凭据文件的显式优先级。
- 外部命令和用户输入必须安全引用，不能拼接成可注入的 shell 命令。
- 作为 Apache-2.0 项目的衍生实现时，必须保留适用的许可证和归属声明，同时使用独立品牌避免官方关联暗示。
- 行为范围、兼容边界和迁移策略在 Shape 确认前不得进入实现。

# Decisions

- 使用 Python 重构，并将成果作为用户独立维护的项目。
- 采用独立 Git worktree；change 分支为 `comet/python-rewrite`，目标分支为 `main`。
- 使用现有 Go 项目作为行为事实和验收参考，而不是进行逐行转译。
- 采用兼容优先、分阶段重写：保留现有配置和外部行为契约，使用独立品牌与全新 Python 内部架构；不追求 Go 源码/API 兼容。
- 第一阶段采用核心垂直切片，不进行一次性全功能重写；完成稳定闭环后再扩展真实 Agent、远程 Runtime 和其他报告能力。
- 新项目名称确认为 `agent-skill-eval`；Python distribution 为 `agent-skill-eval`，import package 为 `agent_skill_eval`，CLI 为 `agent-skill-eval`。
- 第一阶段采用 Go/Python 并存的渐进迁移；Go 保持可构建、可测试并作为差分 oracle，Python 核心闭环独立新增，不在本 change 删除 Go。
- 第一阶段宿主平台范围为 Windows 与 Linux；macOS 不纳入首阶段正式支持矩阵。
- 最低运行版本为 Python 3.11；开发与 CI 至少验证 Python 3.11 和 3.13，环境与锁文件由 `uv` 管理。
- 最终独立仓库使用 GitLab `nsp/agent-skill-eval`、默认分支 `master` 和新的单提交历史；许可证与归属信息不因清除 Git 历史而删除。
- 等第一阶段 Python 核心切片完成并通过验证后，再导出干净快照创建 GitLab 仓库的 `Initial commit`；当前 Go 快照和中间 Comet 产物不提前发布为初始版本。

# Open questions

无。

# Verification expectations

- 使用 Python 单元测试和端到端测试验证配置 → 执行 → Judge → 报告链路。
- 对确认保留的 Go 行为建立契约/黄金样例，并对 Go 与 Python 输出进行差分验证。
- 执行格式化、静态类型检查、安全检查和测试覆盖率检查。
- 在 Windows 本机验证基础 CLI；涉及 POSIX Agent/Runtime 的路径根据最终平台范围在 WSL2 或 Linux CI 验证。
