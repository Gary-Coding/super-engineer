# super-engineer

`super-engineer` 是一个面向存量系统交付场景的 AI 工程工作流项目。

它的目标不是让 AI 零散地写代码，而是让 AI 围绕一次真实需求，按稳定阶段推进：

- 需求理解
- 计划生成
- 代码实现
- 实现自查
- 代码审查
- 自动化验证
- OpenSpec 回写与归档

## 适用场景

- 中大型存量系统
- 多服务或多仓库工程
- 需要计划、审查、验证门禁
- 希望沉淀可回看、可追踪、可归档的交付过程
- 希望把 OpenSpec 和代码交付流程接起来

## 当前能力

当前版本已经支持：

- `discover -> plan -> implement -> self-check -> review -> verify` 执行流
- `manual` 与 `auto` 两种执行模式
- `todo` 与 `openspec` 两种输入模式
- OpenSpec `tasks.md -> todo_file` 桥接
- OpenSpec 执行摘要回写
- 归档前检查与安全归档
- 会话级 JSON / Markdown 产物归档
- PushPlus / Feishu 通知

## 工作流分层

推荐把整个流程理解成三个阶段：

1. 规格阶段
   - OpenSpec change 产出 `proposal.md`、`design.md`、`tasks.md`
2. 交付阶段
   - `todo.md` 或 桥接 todo 进入实现工作流
3. 归档阶段
   - 回写执行摘要，检查归档条件，满足条件后归档

在 `openspec` 模式下，桥接 todo 是规格到交付之间的桥接产物。  
桥接 todo 的实际文件路径由 `workspace.yml` 中的 `todo_file` 决定，推荐继续使用 `todo.md`。  
它应该先被审核，再进入自动实现阶段。

## `se` 专属命令

这个项目建议用户通过一组发给 AI 的专属命令来使用工作流，而不是直接接触底层脚本。

推荐命令：

- `/se:init`
- `/se:propose`
- `/se:bridge`
- `/se:approve`
- `/se:plan`
- `/se:apply`
- `/se:review`
- `/se:verify`
- `/se:archive-check`
- `/se:archive`
- `/se:status`

这些命令的定位是：

- 它们是发给 AI 的工作流指令
- 不是给用户自己执行的 shell 命令
- AI 收到命令后，再根据当前 `workspace.yml` 和工作流状态决定内部执行什么

完整协议见：

- [docs/se命令协议.md](/Users/muke/Documents/personal/codex/super-engineer/docs/se命令协议.md)

## 用户如何开始

先准备工作空间，再把命令发给 AI。

一个真实需求示例：

> 经销商用户列表接口增加手机号精确筛选，要求兼容旧查询行为，并补齐 controller / service 层测试。

`todo` 模式常见起点：

```text
/se:apply
使用当前工作空间。
需求是：经销商用户列表接口增加手机号精确筛选，要求兼容旧查询行为，并补齐 controller / service 层测试。
当前模式是 todo + auto。
如果 workspace 未初始化，先初始化；如果没有硬阻塞，直接推进到实现、自查、审查和验证。
```

`openspec` 模式常见起点：

```text
/se:propose
需求是：经销商用户列表接口增加手机号精确筛选，要求兼容旧查询行为，并补齐 controller / service 层测试。
```

然后：

```text
/se:bridge
针对当前 OpenSpec change 生成交付阶段的桥接 todo，并总结待审核项。
```

人工确认后：

```text
/se:approve
我已审核当前桥接 todo，可以进入交付阶段。
```

再启动自动交付：

```text
/se:apply
使用当前工作空间，当前模式是 openspec + auto。
如果没有硬阻塞，自动推进到 verify；verify 通过后继续检查归档条件。
```

## 工作空间配置

每个业务工作空间都需要有 `workspace.yml`。

最小 `todo` 模式示例：

```yaml
version: 1
mode: manual
workflow_source: todo
todo_file: todo.md
reference_files: []
code_path: ../../../code
output_dir: output
```

最小 `openspec` 模式示例：

```yaml
version: 1
mode: manual
workflow_source: openspec
todo_file: ${demand_name}/todo.md
reference_files: []
code_path: ../../../code
output_dir: ${demand_name}/output
openspec:
  change_dir: ../openspec/changes/${demand_name}
```

如果同一个工作空间经常切换需求，可以用 `vars` 避免重复修改路径：

```yaml
version: 1
mode: auto
workflow_source: openspec
vars:
  demand_name: 7-deamnd-addition-rate
todo_file: ${demand_name}/todo.md
reference_files:
  - ${demand_name}/需求.md
code_path: ../../../code
output_dir: ${demand_name}/output
openspec:
  change_dir: ../openspec/changes/${demand_name}
```

skill 自身配置位于：

```text
~/.super-engineer/skill-config.yml
```

如果该文件不存在，首次初始化时会自动生成默认配置并暂停流程，等待补全。

## 运行时产物

给机器读取的会话产物：

```text
<workspace>/.super-engineer/current-session.json
<workspace>/.super-engineer/sessions/<session_id>/discovery.json
<workspace>/.super-engineer/sessions/<session_id>/plan.json
<workspace>/.super-engineer/sessions/<session_id>/self-check.json
<workspace>/.super-engineer/sessions/<session_id>/review.json
<workspace>/.super-engineer/sessions/<session_id>/verify.json
<workspace>/.super-engineer/sessions/<session_id>/status.json
```

给人查看的报告：

```text
<output_dir>/<session_id>/discovery.md
<output_dir>/<session_id>/plan.md
<output_dir>/<session_id>/self-check.md
<output_dir>/<session_id>/review.md
<output_dir>/<session_id>/verify.md
```

OpenSpec 模式额外产物：

```text
<workspace>/.super-engineer/openspec-bridge-context.json
<change_dir>/super-engineer/execution-summary.json
<change_dir>/super-engineer/archive-input.json
<change_dir>/super-engineer/archive-result.json
```

## 文档入口

- [docs/se命令协议.md](/Users/muke/Documents/personal/codex/super-engineer/docs/se命令协议.md)
- [docs/中文使用手册.md](/Users/muke/Documents/personal/codex/super-engineer/docs/中文使用手册.md)
- [super-engineer-workflow/SKILL.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/SKILL.md)
- [super-engineer-workflow/references/workflow.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/references/workflow.md)
- [super-engineer-workflow/references/contracts.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/references/contracts.md)

## 许可证

本项目使用 [MIT License](/Users/muke/Documents/personal/codex/super-engineer/LICENSE)。
