# `/se:*` 专属命令协议

`/se:*` 是 `super-engineer-workflow` 的专属命令前缀。

它不是 shell 命令，也不是 OpenSpec 官方 `/opsx:*` 命令。用户输入 `/se:*` 时，AI 必须把它理解为当前 skill 的阶段指令，并按本文件执行。

## 通用处理规则

收到 `/se:*` 后必须先做这些事：

1. 读取 `<workspace>/workspace.yml`
2. 读取 `~/.super-engineer/skill-config.yml`
3. 判断 `workflow_source` 是 `todo` 还是 `openspec`
4. 判断 `mode` 是 `manual` 还是 `auto`
5. 读取当前 `.super-engineer/current-session.json` 和当前 session 的 `status.json`，如果存在
6. 如果是 `openspec` 模式，读取 `openspec.change_dir` 下的 `proposal.md`、`design.md`、`tasks.md`、`specs/` 和 `super-engineer/` 目录
7. 如果配置了 `demand_file`，读取它作为原始需求输入
8. 检查当前命令的前置条件
9. 前置条件不满足时停止，并告诉用户应该先执行哪个 `/se:*` 命令

`/se:*` 命令不得要求用户自己运行底层脚本。底层脚本只能由 AI 在 skill 内部调用。

## 状态模型

推荐状态流转：

```text
draft
-> spec_ready
-> todo_generated
-> todo_approved
-> planned
-> implementing
-> self_checked
-> reviewed
-> verified
-> archive_ready
-> archived
```

阻塞状态：

```text
blocked
```

## OpenSpec 审核标记

`openspec` 模式下，桥接 todo 是桥接产物，必须被审核后才能进入交付。

桥接 todo 的实际路径由 `workspace.yml.todo_file` 决定。不要假设固定文件名；如果用户没有特殊要求，推荐继续使用 `todo.md`。

当用户执行 `/se:approve` 时，AI 应写入审核标记：

```text
<workspace>/.super-engineer/openspec-todo-approval.json
```

建议结构：

```json
{
  "approved": true,
  "approved_at": "ISO-8601 datetime",
  "todo_file": "todo.md",
  "change_dir": "../openspec/changes/<change>",
  "source": "/se:approve"
}
```

`/se:plan` 和 `/se:apply` 在 `workflow_source=openspec` 时必须检查该标记。没有审核标记时，停止并提示先执行 `/se:bridge` 和 `/se:approve`。

## 命令定义

### `/se:init`

用途：

- 校验工作空间
- 初始化 `.super-engineer/`
- 确认配置是否完整

适用模式：

- `todo`
- `openspec`

内部动作：

- 执行 `python3 scripts/run-workflow.py init`

完成后汇报：

- workspace 是否可用
- 缺失配置
- 下一步建议命令

### `/se:propose`

用途：

- 为需求生成或完善 OpenSpec change
- 产出 `proposal.md`、`design.md`、`tasks.md`

适用模式：

- `openspec`

前置条件：

- `workspace.yml` 中 `workflow_source=openspec`
- 已配置 `openspec.change_dir`
- 优先读取 `workspace.yml.demand_file`
- 如果没有 `demand_file`，则使用用户提供的需求描述，或 change 目录已有上下文

内部动作：

- 执行 `python3 scripts/run-workflow.py propose-openspec`
- 优先使用 OpenSpec CLI 创建 change、读取 status 和 artifact instructions
- 读取 `propose-input.json`
- 读取 `demand_file` 或用户输入的需求描述，以及现有 OpenSpec 文件
- 创建或更新 `proposal.md`
- 创建或更新 `design.md`
- 创建或更新 `tasks.md`
- 不进入代码实现

完成后汇报：

- change 目录
- 已生成或更新的文件
- 任务摘要
- 是否可以进入 `/se:bridge`

如果 `workflow_source=todo`，停止并说明 `/se:propose` 只适用于 `openspec` 模式。

### `/se:bridge`

用途：

- 把 OpenSpec `tasks.md` 转成桥接 todo
- 生成待审核执行清单

适用模式：

- `openspec`

前置条件：

- `workspace.yml` 中 `workflow_source=openspec`
- `openspec.change_dir` 存在
- `tasks.md` 存在且包含可执行任务

内部动作：

- 执行 `python3 scripts/run-workflow.py bootstrap-openspec`
- 读取 OpenSpec CLI status 和 apply instructions，并写入 bridge context
- 读取生成后的 `todo_file`
- 汇总待审核项
- 不自动进入实现

完成后汇报：

- 桥接 todo 路径
- 进入本轮交付的任务
- 关键约束
- 不清楚或需要人工确认的点
- 下一步建议 `/se:approve`

### `/se:approve`

用途：

- 记录用户已审核桥接 todo
- 允许 OpenSpec 交付阶段开始

适用模式：

- `openspec`

前置条件：

- 桥接 todo 已存在
- 用户明确表示已审核通过

内部动作：

- 写入 `<workspace>/.super-engineer/openspec-todo-approval.json`
- 状态进入 `todo_approved`

完成后汇报：

- 已审核的 todo 路径
- 下一步建议 `/se:plan` 或 `/se:apply`

如果用户没有明确审核通过，不能替用户执行 `/se:approve`。

### `/se:plan`

用途：

- 生成交付计划
- 不直接改代码

适用模式：

- `todo`
- `openspec`

前置条件：

- `todo` 模式：`todo_file` 存在且不是空模板
- `openspec` 模式：已完成 `/se:bridge` 和 `/se:approve`

内部动作：

- 执行 `python3 scripts/run-workflow.py plan`

完成后汇报：

- 目标仓库
- 影响范围
- 验收标准
- 风险
- 下一步建议

`manual` 模式下，生成计划后停下。  
`auto` 模式下，如果用户明确要求“只做计划”，也必须停下。

### `/se:apply`

用途：

- 启动或继续交付阶段
- 实现代码并完成自查、审查、验证

适用模式：

- `todo`
- `openspec`

前置条件：

- `todo` 模式：`todo_file` 存在且不是空模板
- `openspec` 模式：已完成 `/se:bridge` 和 `/se:approve`

内部动作：

- 如果没有当前 session，先执行 `python3 scripts/run-workflow.py plan`
- 执行 `python3 scripts/run-workflow.py start-implement`
- 按当前 `plan.json` 实现代码
- 执行 `python3 scripts/run-workflow.py finish-implement`
- 根据 `mode` 判断是否继续

`manual` 模式：

- 实现和自查后停下，等待用户后续 `/se:review`

`auto` 模式：

- 如果 self-check 无阻塞，继续执行 review
- 如果 review 无阻塞，继续执行 verify
- 如果 `workflow_source=openspec` 且 verify 通过，继续执行 `/se:archive-check` 的检查逻辑
- 只有归档检查结果为 `safe_merge` 时才允许继续归档；如果没有用户明确要求自动归档，只汇报归档状态

完成后汇报：

- 修改文件
- self-check 结果
- review gate
- verify 结果
- residual risks
- OpenSpec 回写状态

### `/se:review`

用途：

- 审查当前代码改动

适用模式：

- `todo`
- `openspec`

前置条件：

- 当前 session 存在
- 已有代码改动或实现阶段已完成

内部动作：

- 执行 `python3 scripts/run-workflow.py review`

完成后汇报：

- gate 结果
- blocking findings
- warning findings
- 测试覆盖风险
- `openspec` 模式下的 execution-summary 回写状态

### `/se:verify`

用途：

- 执行验证并收口当前交付

适用模式：

- `todo`
- `openspec`

前置条件：

- 当前 session 存在
- review 未阻塞

内部动作：

- 执行 `python3 scripts/run-workflow.py verify`

完成后汇报：

- 总体结果
- 每个仓库的验证结果
- workflow 是 `done` 还是 `blocked`
- residual risks

### `/se:archive-check`

用途：

- 检查当前 OpenSpec change 是否满足归档条件

适用模式：

- `openspec`

前置条件：

- `workflow_source=openspec`
- verify 已通过
- execution-summary 已存在

内部动作：

- 执行 `python3 scripts/run-workflow.py prepare-archive-openspec`
- 结合 OpenSpec CLI status / archive instructions 与 super-engineer 安全检查结果

完成后汇报：

- `archive_ready`
- `merge_mode`
- `blockers`
- `spec_conflicts`
- 是否允许继续 `/se:archive`

如果 `merge_mode=manual_merge_required`，停止并说明需要人工处理的 spec 冲突。

### `/se:archive`

用途：

- 安全归档 OpenSpec change

适用模式：

- `openspec`

前置条件：

- 已完成 `/se:archive-check`
- `archive_ready=true`
- `merge_mode=safe_merge`
- `spec_conflicts=[]`

内部动作：

- 执行 `python3 scripts/run-workflow.py archive-openspec`

完成后汇报：

- 同步了哪些 spec 文件
- change 被归档到哪里
- archive-result 路径

前置条件不满足时，停止并提示先执行 `/se:archive-check` 或处理冲突。

### `/se:status`

用途：

- 查看当前工作流状态

适用模式：

- `todo`
- `openspec`

内部动作：

- 执行 `python3 scripts/run-workflow.py status`
- 读取当前 session `status.json`
- 如果是 `openspec` 模式，同时检查 bridge、approval、execution-summary、archive-input 状态

完成后汇报：

- 当前阶段
- 当前 session
- 是否 blocked
- 下一步建议命令

## 模式差异

`todo + auto`：

- 通常可以直接从 `/se:apply` 开始
- 没有硬阻塞时自动推进到 verify

`todo + manual`：

- 先 `/se:plan`
- 用户确认后 `/se:apply`
- 再按需要 `/se:review`、`/se:verify`

`openspec + auto`：

- 必须先 `/se:propose` 或已有 OpenSpec change
- 然后 `/se:bridge`
- 人审后 `/se:approve`
- 再 `/se:apply`
- verify 通过后做 `/se:archive-check`

`openspec + manual`：

- 前半段同 `openspec + auto`
- `/se:approve` 后先 `/se:plan`
- 用户确认后 `/se:apply`
- 再 `/se:review`、`/se:verify`、`/se:archive-check`、`/se:archive`

## 失败反馈格式

命令无法继续时，按这个结构回复：

```text
当前命令：/se:<command>
当前模式：<workflow_source> + <mode>
阻塞原因：<具体原因>
缺失前置条件：<缺失项>
建议下一步：<建议执行的 /se:* 命令或人工处理动作>
```
