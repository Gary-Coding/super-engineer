---
name: super-engineer-workflow
description: Use this skill when the user wants an engineering workflow in the current workspace. It supports `todo` mode and OpenSpec-bridged mode via `workspace.yml`, reads the configured todo file, reference files, code path, and output directory, reads `~/.super-engineer/skill-config.yml` for skill-level settings such as notifications, creates a new archived session for each workflow run, writes AI data into .super-engineer, writes human-readable markdown reports into the configured output directory, and records total workflow duration.
---

# Super Engineer Workflow

当用户希望把工作空间里的 `todo.md` 变成一个可持续推进、可回看、可协作的工程工作流时，使用这个 skill。

## `/se:*` 专属命令协议

如果用户输入以 `/se:` 开头，必须优先按 [references/se-commands.md](references/se-commands.md) 解释，而不是把它当普通自然语言。

`/se:*` 是用户发给 AI 的工作流指令，不是 shell 命令。AI 必须：

1. 识别命令名和用户补充说明
2. 读取 `<workspace>/workspace.yml`
3. 判断 `workflow_source`、`mode`、当前会话状态和 OpenSpec change 状态
4. 检查命令前置条件
5. 调用本 skill 的内部 workflow 推进阶段
6. 把结果、阻塞项和下一步建议汇报给用户

支持的命令：

- `/se:init`
- `/se:propose <change-name>`
- `/se:bridge`
- `/se:approve`
- `/se:plan`
- `/se:apply`
- `/se:review`
- `/se:verify`
- `/se:archive-check`
- `/se:archive`
- `/se:status`

命令处理硬约束：

- 不要把 `/se:*` 映射为 OpenSpec 官方 `/opsx:*`
- 不要要求用户自己执行底层脚本
- `openspec` 模式下，`/se:bridge` 生成的桥接 todo 必须先经过 `/se:approve` 才能进入交付阶段
- 桥接 todo 的实际路径由 `workspace.yml.todo_file` 决定，不要假设固定文件名；如果用户没有特殊要求，推荐使用 `todo.md`
- `manual` 模式下，计划、实现、审查后按门禁停留
- `auto` 模式下，除非出现硬阻塞，否则连续推进
- `/se:archive` 只能在 `archive_ready=true`、`merge_mode=safe_merge`、`spec_conflicts=[]` 时继续
- 当前置条件不满足时，停止该命令并明确说明缺少什么、应该先执行哪个 `/se:*` 命令
- `/se:propose` 必须显式携带 OpenSpec change 名称，例如 `/se:propose demand-addition-rate`；AI 不得根据需求标题或 `demand_name` 自行推导 change 名称
- `/se:propose <change-name>` 应先执行 `python3 scripts/run-workflow.py propose-openspec <change-name>`，优先使用 OpenSpec CLI 创建 change、读取 status 和 artifact instructions；随后 AI 根据 `propose-input.json` 和 `demand_file` 生成或完善 OpenSpec artifacts

## 先读取这些输入

1. 工作空间配置：`<workspace>/workspace.yml`
2. Skill 配置：`~/.super-engineer/skill-config.yml`
3. `workspace.yml` 中配置的 `workflow_source`
4. `workspace.yml` 中配置的 `todo_file`
5. `workspace.yml` 中配置的 `demand_file`
6. `workspace.yml` 中配置的 `reference_files`
7. `workspace.yml` 中配置的 `code_path`
8. `workspace.yml` 中配置的 `output_dir`
9. 如果 `workflow_source=openspec`，继续读取 `workspace.yml` 中的 `openspec`

这里的 `<workspace>` 就是当前使用这个 skill 的目录。

## 强约束

- 工作空间根目录必须存在 `workspace.yml`
- `todo_file`、`reference_files`、`code_path`、`output_dir` 可以使用相对路径或绝对路径；相对路径按当前工作空间根目录解析
- `demand_file` 是可选原始需求输入，主要给 `/se:propose` 使用；如果配置了，`/se:propose` 必须优先读取它
- `workspace.yml` 支持 `vars` 变量；路径字段可以使用 `${name}` 或 `${vars.name}` 引用变量，例如 `${demand_name}`
- `workflow_source=todo` 时，`todo_file` 是用户维护的真实输入
- `workflow_source=openspec` 时，`todo_file` 是桥接后的执行入口，内容来自 OpenSpec `tasks.md`
- `workflow_source=openspec` 时，OpenSpec change 名称只能由 `/se:propose <change-name>` 显式指定；不得从 `vars.demand_name` 或需求标题推导
- `workspace.yml.verify_commands` 可覆盖自动识别出的验证命令；当存在覆盖命令时，verify 阶段必须优先使用覆盖命令
- 用户真实 Skill 配置位于 `~/.super-engineer/skill-config.yml`
- 如果启用了 `notification.pushplus.ordinary`，其中的 `token` 必须合法
- 如果启用了 `notification.feishu`，必须提供合法的飞书机器人 `webhook_url`
- 如果 `workspace.yml` 缺失，立即停止，并提示用户先补齐配置
- 不允许写回全局配置
- 如果 `code_path` 是多个服务的聚合目录，应优先从 todo 中识别“修改的服务是 xxx”或“修改的服务包括 xxx、yyy”这一类约束，并自动定位一个或多个目标仓库
- 如果 todo 中存在 `# 限制条件` 和 `# 待办` 章节，应把限制条件与真实需求分开解析
- 如果 todo 中存在 `##` 模块标题、`- [ ]` 未完成任务、`- [x]` 已完成任务和编号子要求，应按结构化任务模型解析

## 运行时目录约定

工作空间内只保存给 AI 持续推进流程所需的数据：

- `<workspace>/.super-engineer/current-session.json`
- `<workspace>/.super-engineer/sessions/<session_id>/discovery.json`
- `<workspace>/.super-engineer/sessions/<session_id>/plan.json`
- `<workspace>/.super-engineer/sessions/<session_id>/self-check.json`
- `<workspace>/.super-engineer/sessions/<session_id>/review.json`
- `<workspace>/.super-engineer/sessions/<session_id>/verify.json`
- `<workspace>/.super-engineer/sessions/<session_id>/status.json`

给人看的 Markdown 产物写到 `output_dir` 下，并按会话归档：

- `<output_dir>/<session_id>/discovery.md`
- `<output_dir>/<session_id>/plan.md`
- `<output_dir>/<session_id>/self-check.md`
- `<output_dir>/<session_id>/review.md`
- `<output_dir>/<session_id>/verify.md`

每次新的 `plan` 都必须创建新的 `session_id`，不能覆盖历史会话。

工作流耗时和通知结果写回当前会话的 `status.json`，通知明细写入：

- `<workspace>/.super-engineer/sessions/<session_id>/notification.json`

## 执行模式

先阅读 [references/execution-modes.md](references/execution-modes.md)。

- `manual`：在计划、实现、审查三个检查点等待用户确认
- `auto`：除非阻塞，否则沿工作流自动推进

始终保持 `status.json` 为当前会话的真实状态。

`auto` 模式下的执行纪律：

- 不要在正常推进阶段请求用户批准
- 不要说“批准 plan 后我再继续”
- 如果计划不够精确，应直接去代码里定位，再补充计划并继续
- 只有遇到 [references/workflow.md](references/workflow.md) 中定义的硬阻塞，才允许停下来询问用户
- 如果没有硬阻塞，就继续推进到实现、审查、验证，而不是把决策留在对话里

## 输入模式

`workspace.yml` 用 `workflow_source` 控制输入来源：

- `todo`：沿用当前模式，直接读取 `todo_file`
- `openspec`：从当前 active OpenSpec change 的 `tasks.md` 生成桥接 `todo_file`，并把 `proposal.md`、`design.md`、`specs/` 下的 markdown 自动并入参考上下文

OpenSpec 模式可选显式执行：

- `python3 scripts/run-workflow.py propose-openspec`
- `python3 scripts/run-workflow.py bootstrap-openspec`
- `python3 scripts/run-workflow.py writeback-openspec`
- `python3 scripts/run-workflow.py prepare-archive-openspec`
- `python3 scripts/run-workflow.py archive-openspec`

但正常情况下，`init` 和 `plan` 会自动完成桥接。
`review` 和 `verify` 完成后会自动把执行摘要回写到 `openspec.writeback_dir`。
`archive-openspec` 只在 `prepare-archive-openspec` 产出的 `merge_mode=safe_merge` 时允许自动执行。

`openspec` 模式下，如果用户通过 `/se:*` 使用工作流，推荐阶段顺序是：

1. `/se:propose <change-name>`
2. `/se:bridge`
3. `/se:approve`
4. `/se:plan` 或 `/se:apply`
5. `/se:archive-check`
6. `/se:archive`

`todo` 模式下，如果用户通过 `/se:*` 使用工作流，推荐阶段顺序是：

1. `/se:init`
2. `/se:plan`
3. `/se:apply`
4. `/se:review`
5. `/se:verify`

## 必走工作流

优先使用统一入口 [`scripts/run-workflow.py`](scripts/run-workflow.py)，不要在对话里手工拼工作流状态。

### 1. 初始化上下文

- 读取并校验 `<workspace>/workspace.yml`
- 读取并校验 `~/.super-engineer/skill-config.yml`
- 执行 `python3 scripts/run-workflow.py init`
- 读取 todo 和参考文件
- 检查代码目录，尽量识别语言、构建方式和可安全执行的验证命令

如果 `~/.super-engineer/skill-config.yml` 不存在，初始化阶段必须自动生成该文件，然后立即停止当前工作流，并明确提示用户：

- 已生成的配置文件路径
- 请先完善配置后再重新继续

如果 `todo_file` 指向的文件不存在，初始化阶段必须自动创建一个带示例结构的 `todo.md` 模板，方便用户直接填写。

创建模板后的行为约束：

- 执行 `init` 时：创建模板后停止在初始化阶段，并提示用户先完善 todo
- 执行 `plan` 时：如果检测到 todo 仍然是模板示例内容，必须停止，不允许继续基于模板内容生成计划

参考：

- [references/workflow.md](references/workflow.md)
- [references/project-docs.md](references/project-docs.md)
- [references/java.md](references/java.md)

### 2. 上下文定位

使用 `python3 scripts/run-workflow.py discover`。

这一步会从 todo 中提取服务名、接口名、字段名、类名、表名等关键词，逐仓执行代码定位，写入：

- `discovery.json`
- `discovery.md`

`plan` 命令会自动先执行 discover。通常不需要单独运行，除非 todo 或目标仓库发生变化。

### 3. 生成计划

使用 `python3 scripts/run-workflow.py plan`。

这一步必须：

- 创建新的会话目录
- 更新 `<workspace>/.super-engineer/current-session.json`
- 写入当前会话的 `plan.json`
- 写入当前会话对应输出目录的 `plan.md`
- 初始化当前会话的 `status.json`

`auto` 模式下，计划生成后不能因为“影响文件尚未精确到具体代码位置”而停下来要求批准，应直接继续做代码定位。

todo 解析规则：

- `# 限制条件`：约束信息
- `# 待办` 或 `# 待办事项`：任务入口
- `## 模块标题`：大需求模块
- `- [ ] 任务`：本轮待执行任务
- `- [x] 任务`：已完成任务，不进入本轮计划
- `1.` `2.` 或普通说明行：挂到上一个任务下面作为子要求

如果 todo 中所有任务都已经标记完成，应停止生成新计划，并明确提示当前没有未完成任务。

计划至少要覆盖：

- 需求摘要
- todo 完成进度
- 任务模块与子任务拆解
- 上下文定位证据
- 计划置信度
- 实际命中的目标代码目录
- 实际命中的目标仓库列表
- 关键假设
- 识别到的项目技术栈
- 影响模块
- 影响文件
- 每个任务的验收标准
- 可独立推进的实施切片
- 有序修改步骤
- 测试计划
- 风险
- 未知项

`plan.json` 必须兼容 [assets/plan-schema.json](assets/plan-schema.json)。

### 4. 按计划实施修改

把当前会话的 `plan.json` 作为唯一计划基线，并优先参考 `discovery.json` 中的代码证据。

- 严格围绕计划推进实现
- 如果代码现实与计划冲突，先修正计划再继续
- 用 [`scripts/update-status.py`](scripts/update-status.py) 更新当前会话的 `status.json`
- 如果遇到阻塞，把阻塞原因写入状态，不要在聊天里悄悄跳过
- `auto` 模式下，如果只是需要进一步定位控制器、校验逻辑、调用链或测试入口，这不是阻塞，应直接继续

推荐阶段切换：

- 开始实现前：`python3 scripts/run-workflow.py start-implement`
- 实现完成后：`python3 scripts/run-workflow.py finish-implement`

`finish-implement` 会自动执行实现自查并生成：

- `self-check.json`
- `self-check.md`

自查发现阻塞项时，不进入 review。

`manual` 模式下，实现后要停下来等用户确认。

`auto` 模式下，不要在实现开始前再发起额外确认。

### 5. 审查改动

用真实代码差异对照当前会话计划做审查。

如果当前会话包含多个独立仓库，必须逐仓读取 Git 差异并汇总审查结论。

使用：

- `python3 scripts/run-workflow.py review`
- [references/review-checklist.md](references/review-checklist.md)

输出写到当前会话对应的 `review.md`。

同时写入结构化门禁结果 `review.json`。如果存在 `blocking=true` 的 finding，工作流进入 `blocked`，不得继续执行 verify。

`manual` 模式下，审查后要停下来等用户确认。

`auto` 模式下，review 发现计划需要补充时，应先补计划再继续，不要请求批准。

### 6. 执行验证

使用：

- `python3 scripts/run-workflow.py verify`
- [references/verify-checklist.md](references/verify-checklist.md)

优先使用仓库中识别出来的验证命令，不要凭空猜测。验证结果写到当前会话对应的 `verify.md`，同时收敛 `status.json`。

项目识别应覆盖主流技术栈，包括 Java、Node.js / Vue / React、Go、Python、Rust、.NET、PHP、Ruby、Make / CMake。自动识别不可靠时，优先读取 `workspace.yml.verify_commands`。

同时写入 `verify.json`，记录逐仓命令、退出码、耗时、结果和摘要。验证失败时进入 `blocked`，修复后重新执行 verify。

如果当前会话包含多个独立仓库，必须逐仓执行验证并汇总结果。

`auto` 模式下，verify 前也不要因为“建议先确认”而暂停。

verify 收口时还必须：

- 记录从当前会话开始到 verify 完成的整个工作流耗时
- 把耗时写回 `status.json`
- 如果 `~/.super-engineer/skill-config.yml` 中配置了通知，在工作流完成后自动推送结果通知
- 支持 PushPlus 原生消息和飞书原生 webhook 两条路由独立启停
- 普通消息默认走 `wechat`
- 飞书消息走飞书原生自定义机器人 webhook

## 资源导航

- [references/se-commands.md](references/se-commands.md)：`/se:*` 专属命令协议
- [references/workflow.md](references/workflow.md)：工作空间契约与产物目录规则
- [references/contracts.md](references/contracts.md)：输入输出契约与归档顺序
- [references/execution-modes.md](references/execution-modes.md)：`manual` 与 `auto` 行为
- [references/planning.md](references/planning.md)：上下文定位与计划质量规则
- [references/project-docs.md](references/project-docs.md)：参考文件的使用方式
- [references/java.md](references/java.md)：Java 项目识别与计划提示
- [references/review-checklist.md](references/review-checklist.md)：代码审查核对项
- [references/verify-checklist.md](references/verify-checklist.md)：验证核对项
- [references/platform-openclaw.md](references/platform-openclaw.md)：面向 OpenClaw 的后续接入约束
- [scripts/init-workspace.py](scripts/init-workspace.py)：初始化工作空间基础目录
- [scripts/run-workflow.py](scripts/run-workflow.py)：统一入口
- [scripts/bootstrap-openspec.py](scripts/bootstrap-openspec.py)：OpenSpec `tasks.md` 到桥接 `todo` 的输入适配
- [scripts/writeback-openspec.py](scripts/writeback-openspec.py)：执行摘要回写到 OpenSpec change
- [scripts/prepare-archive-openspec.py](scripts/prepare-archive-openspec.py)：生成归档输入与 merge preview
- [scripts/archive-openspec.py](scripts/archive-openspec.py)：归档 change 并合并 delta specs
- [scripts/generate-smart-plan.py](scripts/generate-smart-plan.py)：生成计划
- [scripts/update-status.py](scripts/update-status.py)：更新状态
- [scripts/generate-review-report.py](scripts/generate-review-report.py)：生成代码审查报告
- [scripts/run-verify-and-report.py](scripts/run-verify-and-report.py)：执行验证并生成报告

## 工作方式

- 产物要短、清晰、稳定，方便 AI 和人同时使用
- 属于工作流状态的信息必须写进 `status.json`，不要只留在聊天上下文里
- 不要覆盖用户写的 todo 内容
- 优先相信仓库现实，其次才是参考文件
- 参考文件是强上下文，但不是不可质疑的真理
