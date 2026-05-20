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
6. 如果是 `openspec` 模式，读取当前 active OpenSpec change 下的 `proposal.md`、`design.md`、`tasks.md`、`specs/` 和 `super-engineer/` 目录
7. 如果配置了 `demand_file`，读取它作为原始需求输入
8. 如果配置了 `reference_files`，读取真实存在的参考文件作为需求、设计和计划上下文
9. 检查当前命令的前置条件
10. 前置条件不满足时停止，并告诉用户应该先执行哪个 `/se:*` 命令

`/se:*` 命令不得要求用户自己运行底层脚本。底层脚本只能由 AI 在 skill 内部调用。

`openspec` 模式下，OpenSpec change 名称必须由 `/se:propose <change-name>` 显式指定。AI 不得根据需求标题、需求文件名或 `vars.demand_name` 自行推导 change 名称。

`workspace.yml` 是用户维护的工作空间契约。AI 只能读取和校验，禁止自动编辑、重写或格式化。如果配置需要调整，AI 必须停止并说明需要用户修改的字段。

桥接脚本支持相对路径、绝对路径、`${demand_name}` / `${vars.demand_name}` 变量和 `openspec.changes_dir`。AI 禁止因为缺少 active change 就要求用户把路径改成绝对路径，或要求用户显式新增 `openspec.change_dir`。缺少 active change 时，正确下一步是 `/se:propose <change-name>`。

## 状态产物写入硬约束

AI 禁止直接创建、修改或伪造以下标准工作流产物：

- `<workspace>/.super-engineer/current-session.json`
- `<workspace>/.super-engineer/sessions/<session_id>/status.json`
- `<workspace>/.super-engineer/sessions/<session_id>/plan.json`
- `<workspace>/.super-engineer/sessions/<session_id>/review.json`
- `<workspace>/.super-engineer/sessions/<session_id>/verify.json`
- `<workspace>/.super-engineer/sessions/<session_id>/notification.json`
- `<output_dir>/<session_id>/discovery.md`
- `<output_dir>/<session_id>/plan.md`
- `<output_dir>/<session_id>/self-check.md`
- `<output_dir>/<session_id>/review.md`
- `<output_dir>/<session_id>/verify.md`

这些文件只能由本 skill 的标准脚本生成或更新。AI 可以修改业务代码、OpenSpec 规格、todo 文件和用户明确要求编辑的普通文档，但不能手工补写工作流状态产物。

如果发现 session 已经被手工污染，例如只有 `status.json`，没有 `plan.json`、`review.json`、`verify.json`、`notification.json` 或 output Markdown，AI 必须停止手工补文件，改为：

1. 重新执行 `/se:plan` 创建标准 session；或
2. 在已有标准 session 上执行 `/se:review`、`/se:verify` 恢复后续标准产物。

禁止通过手工写 `notification_status=sent`、手工写 `phase=done`、手工拼飞书卡片来宣称工作流完成。

## 下一步提示硬约束

AI 每次完成 `/se:*` 命令后，只能提示当前阶段允许的下一步，不能为了“方便”跳过门禁。

“提示下一步”和“执行下一步”必须严格区分：

- 提示下一步：只在回复里告诉用户下一条建议命令
- 执行下一步：调用脚本、修改状态、生成计划、实现代码、审查或验证

除非用户当前消息明确请求该命令，否则 AI 只能提示下一步，不能执行下一步。

`auto` 模式只影响 `/se:apply` 内部从实现到验证的连续推进，不允许让 `/se:propose`、`/se:bridge` 自动串到 `/se:apply`。

如果脚本输出了 `final_reply_must`，或者输出了 `se_reply_constraint_begin` / `se_reply_constraint_end` 包裹的约束，AI 最终回复必须以该约束为准。禁止在最终回复中追加任何与 `allowed_next` 冲突的 `/se:*` 命令。

`openspec` 模式允许的阶段流转：

```text
/se:propose <change-name>
-> /se:bridge
-> 人工审核 todo.md
-> /se:apply
-> /se:review
-> /se:verify
-> /se:archive-check
-> /se:archive
```

硬性禁止：

- `/se:propose` 完成后禁止提示 `/se:apply`
- `/se:propose` 完成回复中禁止出现“确认无误后执行 `/se:apply`”“通过 `/se:apply` 进入实现阶段”等跨阶段提示
- `/se:bridge` 完成后必须提示先人工审核 todo，审核通过后发送 `/se:apply`
- `/se:apply` 之前必须已完成 `/se:bridge`，并由用户在对话中明确表示 todo 已审核通过或直接在审核后发送 `/se:apply`
- `/se:apply` 必须通过标准脚本序列推进，禁止手工写 `status.json` 或手工补 output 文档后宣称完成
- `/se:verify` 通过前禁止提示 `/se:archive-check`
- `/se:archive-check` 未得到 `archive_ready=true` 且 `merge_mode=safe_merge` 前禁止提示 `/se:archive`
- 工作流完成通知必须通过 `python3 scripts/run-workflow.py verify` 发送，禁止 AI 直接调用飞书 webhook，禁止 AI 手工拼接飞书卡片 JSON
- 启用飞书时，只有 `notification.json` 中存在 `source=run-workflow.py verify`、fingerprint 匹配、`route=feishu`、`template=interactive`、`status=sent` 的结果，才算飞书通知成功

`todo` 模式允许的阶段流转：

```text
/se:init
-> /se:plan 或 /se:apply
-> /se:review
-> /se:verify
```

如果用户要求跳过上述顺序，AI 必须停止并说明缺失的前置条件。

命令完成后的停止规则：

| 命令 | 完成后是否必须停止 | 允许的下一步提示 | 禁止自动执行 |
| --- | --- | --- | --- |
| `/se:init` | 是 | `/se:propose <change-name>`、`/se:plan` 或 `/se:apply` | 后续所有命令 |
| `/se:propose <change-name>` | 是 | `/se:bridge` | `/se:plan`、`/se:apply`、代码实现 |
| `/se:bridge` | 是 | 人工审核 todo 后 `/se:apply` | 自动执行 `/se:plan`、`/se:apply` |
| `/se:plan` | 是 | `/se:apply` | 代码实现、review、verify |
| `/se:archive-check` | 是 | 满足 safe_merge 时 `/se:archive` | `/se:archive` |

## 状态模型

OpenSpec 模式使用 `<workspace>/.super-engineer/se-state.json` 作为脚本状态机。AI 只能读取该文件，不能手工编辑。

状态流转：

```text
draft
-> proposed
-> bridged
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

实际脚本阶段：

```text
draft
-> proposed        allowed_next=[/se:bridge]
-> bridged         allowed_next=[/se:apply, /se:plan]
-> planned         allowed_next=[/se:apply]
-> implementing
-> self_checked    allowed_next=[/se:review]
-> reviewed        allowed_next=[/se:verify, /se:apply]
-> verified        allowed_next=[/se:archive-check]
-> archive_ready   allowed_next=[/se:archive]
-> archived
```

执行 `/se:bridge`、`/se:plan`、`/se:apply`、`/se:verify`、`/se:archive-check`、`/se:archive` 前，脚本必须校验当前 `phase` 和 `allowed_next`。校验失败时停止，不能靠 AI 口头判断继续。

## OpenSpec 桥接审核

`openspec` 模式下，桥接 todo 是桥接产物，必须被人工审核后才能进入交付。

桥接 todo 的实际路径由 `workspace.yml.todo_file` 决定。不要假设固定文件名；如果用户没有特殊要求，推荐继续使用 `todo.md`。

审核动作不再通过单独命令记录。用户审核 `todo.md` 后，直接发送 `/se:apply` 即表示确认该桥接 todo 可以进入交付。

AI 在 `/se:bridge` 完成后必须停止，只能提示用户审核 `todo.md`；不能自动进入 `/se:apply`。

`openspec` 模式下，只有显式执行 `/se:bridge` 才允许从 `tasks.md` 重写 `todo.md`。后续 `/se:plan` 或 `/se:apply` 触发的初始化只能校验已有 `todo.md` 和刷新桥接上下文，不能覆盖人工审核或补充过的 todo。

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
- 下一步建议命令：`todo` 模式建议 `/se:plan` 或 `/se:apply`；`openspec` 模式建议 `/se:propose <change-name>` 或 `/se:bridge`，取决于是否已有 active change 和 `tasks.md`

### `/se:propose`

用途：

- 为需求生成或完善 OpenSpec change
- 产出 `proposal.md`、`design.md`、`tasks.md`

适用模式：

- `openspec`

前置条件：

- `workspace.yml` 中 `workflow_source=openspec`
- 用户已在 `/se:propose` 后显式指定 change 名称
- 优先读取 `workspace.yml.demand_file`
- `demand_file` 可以是本地 Markdown 路径，也可以是飞书/Lark 云文档 URL
- 当 `demand_file` 是飞书/Lark 云文档 URL 时，必须由脚本调用官方 `lark-cli docs +fetch` 读取并转换为 Markdown；AI 禁止手工复制云文档正文
- 如果本机没有安装 `lark-cli`，必须停止并提示用户安装：`npx @larksuite/cli@latest install`，随后执行 `lark-cli config init --new` 和 `lark-cli auth login --recommend`
- 如果没有 `demand_file`，则使用用户提供的需求描述，或 change 目录已有上下文

内部动作：

- 执行 `python3 scripts/run-workflow.py route-se --command-text "/se:propose <change-name>"`
- 优先使用 OpenSpec CLI 创建 change、读取 status 和 artifact instructions
- 读取 `propose-input.json`
- 读取 `demand_file` 或用户输入的需求描述
- 读取 `reference_files` 中真实存在的参考文件，并作为生成 OpenSpec 产物的上下文
- 读取现有 OpenSpec 文件
- 创建或更新 `proposal.md`
- 创建或更新 `design.md`
- 创建或更新 `tasks.md`
- 不进入代码实现
- 禁止调用 `bootstrap-openspec.py` 或 `run-workflow.py bootstrap-openspec`
- 禁止创建或修改 `workspace.yml.todo_file` 指向的桥接 todo
- 完成后 `se-state.phase` 必须停留在 `proposed`

完成后汇报：

- change 目录
- 已生成或更新的文件
- 任务摘要
- 下一步只能提示：`/se:bridge`

完成后推荐固定收口句：

```text
代码暂未修改。下一步请执行 /se:bridge，把当前 OpenSpec tasks.md 桥接为待审核 todo.md。
```

完成后禁止提示：

- `/se:apply`
- `/se:plan`
- 任何代码实现动作
- “确认无误后通过 /se:apply 进入实现阶段”这类跨过 `/se:bridge` 的表达

如果发现需求有遗漏，应继续停留在 `/se:propose <change-name>` 阶段，补充当前 change，不进入 `/se:bridge`。

如果 `workflow_source=todo`，停止并说明 `/se:propose` 只适用于 `openspec` 模式。

### `/se:bridge`

用途：

- 把 OpenSpec `tasks.md` 转成桥接 todo
- 生成待审核执行清单

适用模式：

- `openspec`

前置条件：

- `workspace.yml` 中 `workflow_source=openspec`
- 已通过 `/se:propose <change-name>` 记录当前 active change，或 `workspace.yml.openspec.change_dir` 指向明确 change
- `tasks.md` 存在且包含可执行任务
- 当前阶段是 `proposed` 或尚未进入交付的 `bridged`；如果已进入 `planned`、`implementing`、`reviewed`、`verified` 等交付阶段，不允许直接重写桥接 todo

重复桥接规则：

- 如果 `/se:bridge` 后人工审核发现 todo 或需求有偏差，应先通过 `/se:propose <change-name>` 修正当前 OpenSpec change
- 修正后的 `tasks.md` 生成完成后，可以再次执行 `/se:bridge` 重建待审核 todo
- 禁止 AI 手工把 `tasks.md` 内容同步到 `todo.md`；必须通过 `/se:bridge` 脚本生成

内部动作：

- 执行 `python3 scripts/run-workflow.py route-se --command-text "/se:bridge"`，或由受控入口调用 `python3 scripts/run-workflow.py bootstrap-openspec --explicit-se-bridge`
- 读取 OpenSpec CLI status 和 apply instructions，并写入 bridge context
- 读取生成后的 `todo_file`
- 汇总待审核项
- 不自动进入实现

完成后汇报：

- 桥接 todo 路径
- 进入本轮交付的任务
- 关键约束
- 不清楚或需要人工确认的点
- 下一步只能提示“人工审核 todo.md，审核通过后执行 `/se:apply`”

完成后禁止提示：

- `/se:plan`
- `/se:review`
- `/se:verify`

### `/se:plan`

用途：

- 生成交付计划
- 不直接改代码

适用模式：

- `todo`
- `openspec`

前置条件：

- `todo` 模式：`todo_file` 存在且不是空模板
- `openspec` 模式：已完成 `/se:bridge`，且用户已审核桥接 `todo.md`

内部动作：

- 执行 `python3 scripts/run-workflow.py plan`

完成后汇报：

- 目标仓库
- 影响范围
- 验收标准
- 风险
- 下一步建议：`manual` 模式提示用户确认后 `/se:apply`；`auto` 模式如果用户只要求计划，只能停在计划阶段

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
- `openspec` 模式：已完成 `/se:bridge`，且用户已审核桥接 `todo.md`

内部动作：

- 如果没有当前 session，先执行 `python3 scripts/run-workflow.py plan`
- 执行 `python3 scripts/run-workflow.py start-implement`
- 按当前 `plan.json` 实现代码
- 执行 `python3 scripts/run-workflow.py finish-implement`
- 根据 `mode` 判断是否继续

执行约束：

- `plan`、`start-implement`、`finish-implement`、`review`、`verify` 的状态推进必须由 `python3 scripts/run-workflow.py ...` 完成
- 每个阶段执行前必须通过 `se-state.json` 状态校验；`/se:propose` 后直接进入 `/se:apply` 必须被脚本拒绝
- `todo` 模式下也必须通过当前 session 的 `status.json`、`todo-state.json` 和标准产物来源校验，不能复用旧需求 session
- `todo` 模式的状态不能写入 OpenSpec 专用 `se-state.json`
- `todo` 模式下如果 `current-session.json` 指向旧 `output_dir`，`/se:apply` 必须重新创建标准 session
- AI 只能在 `start-implement` 和 `finish-implement` 之间修改业务代码
- AI 不得直接写 `.super-engineer` 下的状态 JSON
- AI 不得直接写 output 下的标准 Markdown 报告
- AI 不得直接调用飞书 webhook 或手工拼接飞书通知；通知只能在后续 `python3 scripts/run-workflow.py verify` 中由脚本发送
- 如果当前 session 不是标准脚本创建的，或者缺少 `plan.json`，必须重新执行 `python3 scripts/run-workflow.py plan` 创建标准 session
- 如果当前 session 的 `plan.json`、`self-check.json`、`review.json`、`verify.json` 缺少对应 `source=run-workflow.py ...`，必须视为非标准产物并停止

`manual` 模式：

- 实现和自查后停下，等待用户后续 `/se:review`

`auto` 模式：

- 如果 self-check 无阻塞，继续执行 review
- 如果 review 无阻塞，继续执行 verify
- 如果 `workflow_source=openspec` 且 verify 通过，继续执行 `/se:archive-check` 的检查逻辑
- 只有归档检查结果为 `safe_merge` 时才允许提示 `/se:archive`；默认只汇报归档状态，不自动执行归档

完成后汇报：

- 修改文件
- self-check 结果
- review gate
- verify 结果
- residual risks
- OpenSpec 回写状态

如果 `workflow_source=openspec` 且 verify 通过，下一步只能提示 `/se:archive-check`。只有 `/se:archive-check` 已满足 `safe_merge` 时，才允许提示 `/se:archive`。

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

如果 review 通过，下一步提示 `/se:verify`。如果存在 blocking finding，下一步提示 `/se:apply` 修复 blocking finding，不能提示 `/se:verify`。

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
- 由 verify 脚本统一执行通知发送
- 写入 `verify.json`
- 写入 `notification.json`

完成后汇报：

- 总体结果
- 每个仓库的验证结果
- workflow 是 `done` 还是 `blocked`
- `notification.json` 中的通知结果；启用飞书时必须汇报飞书 route 是否为 `sent`
- residual risks

如果验证通过且是 `openspec` 模式，下一步只能提示 `/se:archive-check`。如果验证失败，下一步提示 `/se:apply` 修复或人工处理，不能提示 `/se:archive-check`。

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

只有 `archive_ready=true`、`merge_mode=safe_merge`、`spec_conflicts=[]` 时，下一步才允许提示 `/se:archive`。否则只能提示人工处理 blockers 或 spec 冲突。

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
- 如果是 `openspec` 模式，同时检查 bridge、execution-summary、archive-input 状态

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
- 人工审核 `todo.md`
- 审核通过后 `/se:apply`
- verify 通过后做 `/se:archive-check`

`openspec + manual`：

- 前半段同 `openspec + auto`
- 人工审核 `todo.md` 后先 `/se:plan`
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
