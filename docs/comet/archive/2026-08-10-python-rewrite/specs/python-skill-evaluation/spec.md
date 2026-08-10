# Python Agent Skill 评测能力

## 状态

本规格已经用户确认并进入 Build。品牌、兼容策略、第一阶段范围、迁移方式、宿主平台和 Python 版本均已确定。

## 目标

`agent-skill-eval` 应以 Python 提供可独立安装和维护的 Agent Skill 评测能力。用户可以通过声明式配置定义评测环境、Agent、Case 和 Judge，执行后获得可审计的结果、证据和报告。

## 产品标识

- 项目与报告品牌：`agent-skill-eval`
- Python distribution：`agent-skill-eval`
- Python import package：`agent_skill_eval`
- CLI 可执行命令：`agent-skill-eval`
- 第一阶段新增标识使用 `AGENT_SKILL_EVAL` / `agent-skill-eval` 前缀，不注册 `skill-up` CLI 别名，避免与并存的 Go CLI 冲突；旧用户配置和凭据前缀兼容不属于第一阶段。

## 核心行为

1. 系统应从 Skill 根目录发现评测配置，并加载评测级配置与 Case 配置。
2. 系统应在执行前完成 schema、路径、Agent、Runtime 和 Judge 配置验证。
3. 系统应通过 Agent 协议封装凭据检查、安装、Skill/MCP 安装、单轮执行和可选会话恢复。
4. 系统应通过 Runtime 协议封装生命周期、命令执行、环境变量和文件上传下载。
5. Evaluator 应为每个 Case 准备独立工作区，安装 fixture/MCP/Skill，运行 Agent，收集 transcript、artifact 和 workspace diff。
6. `expect` 应作为确定性前置检查；失败时不得继续产生可能掩盖失败的 Judge 通过结果。
7. 第一阶段 Judge 支持 `rule_based`，并为 `script` 与 `agent_judge` 保留可插拔边界；后二者在第一阶段收到配置时必须明确报告 unsupported。
8. 启用基线时，系统应区分 `with_skill` 与 `without_skill`，并生成可比较结果。
9. 系统应生成稳定的机器可读结果，并根据确认的兼容范围生成其他报告。
10. CLI 应返回适合本地和 CI 使用的退出码，并避免泄露凭据。

## 第一阶段垂直切片

第一阶段必须形成以下可运行闭环：

1. 建立可安装的 Python 项目、独立 CLI 入口和类型化领域模型。
2. 兼容加载并验证第一阶段涉及字段的 `v1alpha1` `eval.yaml` 与 Case YAML；已知但尚未实现的能力必须给出明确的 unsupported 错误。
3. 提供 `validate`、`list-cases` 和 `run` 核心命令语义。
4. 提供本机 `none` Runtime，支持隔离工作目录、环境变量、进程执行和文件传输所需的最小契约。
5. 提供无网络 Fake Agent 以及基于显式进程契约的 Custom Local Agent，使核心链路可测试并可连接自定义 Agent。
6. 支持 fixture/上下文准备、单轮 Agent 执行、transcript 与 artifact 元数据收集。
7. 支持默认/Case 级 `expect` 合并与确定性短路。
8. 支持 `rule_based` Judge 的第一阶段规则集合，并输出 assertion evidence。
9. 输出兼容的 `result.json` 和每 Case `grading.json`；以黄金样例验证字段、状态和退出码。
10. 提供不依赖网络和真实凭据的单元测试与端到端测试。

第一阶段不提供 `report`、`import`、`debug` 和用户配置 `init` 命令；调用未提供的命令应由 CLI 返回非零退出码和清晰帮助。`validate` 验证完整套件，`run` 只执行筛选后的 Case 并对尚未实现的配置给出明确错误。

第一阶段明确延后：内置 Claude Code/Codex/Qoder/Qwen Agent、Docker、OpenSandbox、真实 MCP provision、多轮会话、`script` Judge、`agent_judge`、HTML、JUnit 以及完整 Anthropic benchmark。延后能力不得被静默忽略；配置触及时必须报告可识别的 unsupported 错误。

## 迁移拓扑

- 第一阶段使用 Go/Python 并存的渐进迁移方式。
- 现有 Go 源码、`go.mod`、测试、CI 和用户入口不得在本 change 中删除或削弱。
- Python 实现使用 `src/agent_skill_eval` 布局、独立 Python 测试目录和 `pyproject.toml` 工具链。
- Go 实现及其 fixtures/golden outputs 作为外部行为 oracle；Python 对已实现能力建立黄金样例或差分测试。
- Python 文档应明确其第一阶段能力和延后项，不能让用户误认为已经完整替代 Go。
- Python 达到后续确认的兼容门槛后，再通过独立 change 执行 Python-only 切换和 Go 清理。
- 只有第一阶段 Python 核心切片完成并通过验证后，才将可发布的干净快照导出为独立 Git 仓库；不得提前把当前 Go 快照或中间 Comet 产物发布为初始版本。导出不复用当前 worktree 的 Git 元数据；目标远端为 `git@gitlab.dc.servyou-it.com:nsp/agent-skill-eval.git`，默认分支为 `master`，首个提交信息为 `Initial commit`。
- 新仓库不保留上游 Git 提交历史，但必须保留 Apache-2.0 许可证及适用归属声明。

## 平台支持

- 第一阶段正式支持 Windows 与 Linux。
- Windows 与 Linux 都必须运行配置、Runtime、Evaluator、Judge、报告和 CLI 的 Python 自动化测试。
- 平台相关进程、路径、权限和 shell 行为应封装在明确边界内，不得散落到领域逻辑。
- macOS 应避免被主动破坏，但第一阶段不承诺 CI、验收证据或问题修复时限。

## Python 运行与工具链

- `requires-python` 为 `>=3.11,<4`。
- 环境创建、依赖解析和锁文件由 `uv` 管理；项目仍应符合标准 `pyproject.toml` 安装方式。
- CI 至少验证 Python 3.11 和 3.13，并覆盖 Windows 与 Linux；可增加中间版本但不作为最低验收要求。
- 格式化、lint、静态类型检查和测试命令必须可由本地与 CI 使用同一配置重复执行。

## 扩展边界

- Agent、Runtime、Judge、Reporter 应使用 Python Protocol/ABC 或等价的显式契约。
- 领域数据使用具备运行时验证和静态类型支持的模型。
- CLI 只负责解析输入、组装依赖和展示结果，不承载评测业务规则。

## 兼容性

- Python 项目应兼容现有 `v1alpha1` YAML schema、默认值、路径解析和合并语义；任何阶段性缺口必须明确报错，不能静默改变含义。
- Python 项目应保持现有核心命令概念、参数语义和成功/失败退出码；可执行命令使用独立品牌名 `agent-skill-eval`。
- `result.json`、Anthropic `grading.json` / benchmark 等确认保留的机器契约应能通过黄金样例或差分测试证明兼容。
- Python 内部模块、类型和扩展接口不需要兼容 Go 源码或 `pkg/*` API。
- 重写采用分阶段交付；第一阶段范围以“第一阶段垂直切片”为准，后续阶段不得破坏已确认的外部契约。

## 安全与归属

- 凭据只能从确认的安全来源解析，任何日志和报告必须脱敏。
- 外部命令参数必须通过安全的进程参数或平台引用函数传递。
- 项目采用 `agent-skill-eval` 独立名称和描述，不暗示属于原项目维护者；保留 Apache-2.0 要求的许可和归属信息。

## 验收方向

1. 给定兼容的 Skill 目录、`eval.yaml` 和 Case YAML，`agent-skill-eval validate` 成功并报告 Case 数量；无效 schema、重复 ID 和非法路径返回非零退出码及字段级错误。
2. `agent-skill-eval list-cases` 按配置顺序输出 Case ID、标题和标签。
3. `agent-skill-eval run` 使用 Fake Agent 在临时 `none` Runtime 中完成单轮 Case，执行 `expect` 和 `rule_based`，写出兼容状态与断言证据。
4. Custom Local Agent 通过结构化 `SessionInput` / `SessionResult` 文件或标准输出完成一次执行；超时、非零退出和无效 JSON 产生稳定错误结果且不泄露环境凭据。
5. `expect` 失败时短路 Judge；`expect` 通过时其断言与 rule-based 断言合并为最终 grading。
6. `result.json` 和 Case `grading.json` 与选定 Go fixtures 的字段、状态、路径布局和数值语义通过黄金样例或差分测试。
7. 配置内出现延后能力时，命令明确指出具体 unsupported 字段/能力，不能忽略后继续运行。
8. Windows 与 Linux、Python 3.11 与 3.13 的无网络测试矩阵通过。
