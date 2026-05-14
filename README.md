# super-engineer

`super-engineer` 是一个面向存量系统交付场景的 AI 工程工作流项目。

它解决的不是“让 AI 帮我写几段代码”，而是“让 AI 参与需求分析、计划、实现、自查、审查、验证和归档，并留下稳定产物”。

适用场景：

- 中大型存量系统
- 多服务或多仓库工程
- 需要计划、审查、验证门禁
- 希望把一次需求交付沉淀成可回看、可追踪、可归档的过程
- 希望与 OpenSpec 结合，建立长期规格治理能力

## 项目目标

这个项目希望把真实工程交付中的几个关键环节结构化下来：

- 需求输入
- 上下文定位
- 变更计划
- 代码实现
- 实现自查
- 代码审查
- 自动化验证
- OpenSpec 回写与归档准备

最终目标是把“聊天上下文里的临时过程”变成“文件系统里的长期工程资产”。

## 当前能力

当前版本已经支持：

- `discover -> plan -> implement -> self-check -> review -> verify` 执行流
- `manual` 与 `auto` 两种执行模式
- 单仓和多仓目录自动识别
- 会话级产物归档到 `.super-engineer/sessions/<session_id>/`
- 面向人的 Markdown 报告输出到 `output_dir`
- `todo` 模式
- `openspec` 模式
- OpenSpec `tasks.md -> todo` 桥接
- OpenSpec 执行摘要回写
- OpenSpec 归档前检查与安全归档
- PushPlus / Feishu 通知

## 仓库结构

```text
super-engineer/
├── README.md
├── docs/
└── super-engineer-workflow/
    ├── SKILL.md
    ├── agents/
    ├── assets/
    ├── references/
    └── scripts/
```

## 工作流模式

当前支持两种输入模式。

### 1. `todo` 模式

直接使用用户维护的 `todo.md` 作为执行入口。

适合：

- 需求局部
- 主要目标是工程交付
- 不要求长期规格治理

### 2. `openspec` 模式

使用 OpenSpec change 作为上游输入。

工作流会：

- 读取 `tasks.md`
- 生成桥接后的执行 `todo`
- 自动纳入 `proposal.md`、`design.md`、`specs/*.md` 上下文
- 把执行结果写回 OpenSpec change
- 生成归档输入
- 在安全条件满足时执行 archive

## 安装

本仓库提供 skill 源码，安装方式是把 `super-engineer-workflow/` 复制到本地 skill 目录。

常见安装位置：

- Codex：`~/.codex/skills/super-engineer-workflow`
- Claude：`~/.claude/skills/super-engineer-workflow`

## 工作空间配置

每个业务工作空间都需要有 `workspace.yml`。

最小 `todo` 模式示例：

```yaml
version: 1
mode: manual
workflow_source: todo
todo_file: /absolute/path/to/workspace/todo.md
reference_files: []
code_path: /absolute/path/to/code
output_dir: /absolute/path/to/output
```

最小 `openspec` 模式示例：

```yaml
version: 1
mode: manual
workflow_source: openspec
todo_file: /absolute/path/to/workspace/todo.generated.md
reference_files: []
code_path: /absolute/path/to/code
output_dir: /absolute/path/to/output
openspec:
  change_dir: /absolute/path/to/openspec/changes/add-phone-filter
```

skill 自身配置位于：

```text
~/.super-engineer/skill-config.yml
```

如果该文件不存在，首次执行 `init` 时会自动生成默认配置并暂停流程，等待你补全。

## 核心命令

统一入口：

```bash
python3 scripts/run-workflow.py <command> --workspace /abs/path/to/workspace
```

常用命令：

- `init`
- `discover`
- `plan`
- `start-implement`
- `finish-implement`
- `review`
- `verify`
- `status`

OpenSpec 相关命令：

- `bootstrap-openspec`
- `writeback-openspec`
- `prepare-archive-openspec`
- `archive-openspec`

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

`prepare-archive-openspec` 会基于计划阶段记录的 spec baseline 做冲突检测。  
只有 `merge_mode=safe_merge` 时，才允许自动执行 `archive-openspec`。

## OpenSpec 集成方式

当前推荐分层是：

```text
OpenSpec change
-> 桥接为 workflow 输入
-> super-engineer 执行交付流程
-> 回写执行摘要
-> 准备归档
-> archive change 并同步 delta specs
```

这个分层的目标很明确：

- OpenSpec 负责长期规格演进
- `super-engineer` 负责代码侧交付执行

## 文档入口

建议从这里开始：

- [super-engineer-workflow/SKILL.md](super-engineer-workflow/SKILL.md)
- [super-engineer-workflow/references/workflow.md](super-engineer-workflow/references/workflow.md)
- [super-engineer-workflow/references/contracts.md](super-engineer-workflow/references/contracts.md)
- [super-engineer-workflow/references/planning.md](super-engineer-workflow/references/planning.md)
- [docs/中文使用手册.md](docs/中文使用手册.md)

## 当前状态

当前状态可以概括为：

- 执行流已经可用
- OpenSpec 输入桥接已经可用
- OpenSpec 执行摘要回写已经可用
- 归档前检查和安全归档已经可用
- 团队级长期规格治理仍然依赖流程纪律和评审约束

## 路线图

后续优先方向：

- 将 archive 从文件级覆盖提升到语义级 merge
- 增强 release / rollout / rollback 元数据
- 增强多仓协作模式文档
- 补充更完整的团队协作手册

## 许可证

当前仓库还没有单独的 LICENSE 文件。  
如果准备公开发布，建议补充正式许可证。
