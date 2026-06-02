# super-engineer

`super-engineer` 是一个面向需求驱动开发的软件工程工作流 skill，适用于新系统开发和存量系统迭代。

它的目标不是让 AI 零散地写代码，而是让 AI 围绕一次真实需求，按稳定阶段推进：

- 需求理解
- 计划生成
- 代码实现
- 实现自查
- 代码审查
- 自动化验证
- OpenSpec 回写与归档

## 适用场景

- 新系统从 0 到 1 的需求交付
- 中大型存量系统的长期需求迭代
- 多服务或多仓库工程
- 需要计划、审查、验证门禁
- 希望沉淀可回看、可追踪、可归档的交付过程
- 希望把 OpenSpec 和代码交付流程接起来

相比快速原型或一次性 demo，它更适合需要规格、计划、实现、自查、审查、验证、归档闭环的工程场景。相比从零开始的新项目，它在存量系统、多服务、多仓库、长期需求迭代场景下优势更明显。

## 当前能力

当前版本已经支持：

- `discover -> plan -> implement -> self-check -> review -> verify` 执行流
- `manual` 与 `auto` 两种执行模式
- `todo` 与 `openspec` 两种输入模式
- OpenSpec `tasks.md -> todo_file` 桥接
- `/se:propose <change-name>` 优先使用 OpenSpec CLI 创建指定 change、读取 status 和 artifact instructions
- OpenSpec 模式使用 `.super-engineer/se-state.json` 状态机约束阶段跳转
- `/se:*` 命令可由统一路由入口解析，脚本负责校验阶段与允许命令
- OpenSpec 执行摘要回写
- OpenSpec task -> todo -> evidence 映射回写
- 归档前检查与安全归档
- 会话级 JSON / Markdown 产物归档
- 基于 `adapters/*.yml` 的主流语言项目识别与验证命令推断：Java、Node.js / Vue / React、Go、Python，并保留 Rust、.NET、PHP、Ruby、Make / CMake 兜底识别
- `workspace.yml.verify_commands` 覆盖默认验证命令
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

OpenSpec 模式下，脚本会维护 `.super-engineer/se-state.json`。
`/se:propose` 后只允许 `/se:bridge`，`/se:bridge` 后才允许审核后 `/se:apply`，非法跨阶段命令会被脚本拒绝。

标准工作流产物由脚本写入，AI 不应手工伪造 `.super-engineer` 状态文件、`verify.json`、`notification.json` 或 output 下的标准报告。飞书通知只以 `notification.json` 中由 `run-workflow.py verify` 生成的记录为准。

## `se` 专属命令

这个项目建议用户通过一组发给 AI 的专属命令来使用工作流，而不是直接接触底层脚本。

推荐命令：

- `/se:init`
- `/se:propose <change-name>`
- `/se:bridge`
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

如果通过 npm 使用，推荐入口是：

```bash
npx super-engineer-workflow init
```

也可以全局安装后使用：

```bash
npm install -g super-engineer-workflow
se init
```

常用 CLI 命令：

```bash
se init      # 交互式安装 skill 并初始化工作区
se doctor    # 检查本机环境和 workspace.yml
se templates # 查看内置 workspace.yml 模板
se install   # 安装 skill 到 Codex / Claude
se sync      # 强制同步最新 skill 到 Codex / Claude
se migrate   # 补齐旧工作区缺失配置
se version   # 查看版本
```

模板入口：

```bash
se templates
se template show openspec-auto
se template copy openspec-auto --workspace /path/to/ai-workspace --demand-name 13-your-demand --code-path ../code
```

模板说明见 [docs/模板使用指南.md](/Users/muke/Documents/personal/codex/super-engineer/docs/模板使用指南.md)。

本地源码开发时，也可以直接使用引导脚本。默认是一步一步的交互式向导：

```bash
python3 scripts/se-setup.py
```

脚本会依次完成环境检查、安装目标选择、工作区选择、代码目录配置、需求目录配置、工作流模式选择、OpenSpec 初始化确认、快捷命令生成，并在执行前展示摘要。最终会创建 `workspace.yml`、`openspec/`、`superengineer/<demand_name>/需求.md`、`.claude/commands/se/*`，并可选安装 skill 到 Codex / Claude 本机目录。

当选择 `openspec` 模式时，`se init` 默认会尝试在工作区根目录执行 `openspec init . --tools codex,claude`。如果本机未安装 OpenSpec CLI，会跳过并给出提示；如果你希望跳过该步骤，可以使用 `--skip-openspec-init`。

如果需要非交互初始化：

```bash
python3 scripts/se-setup.py \
  --yes \
  --install both \
  --workspace /path/to/ai-workspace \
  --code-path ../code \
  --demand-name 1-your-demand \
  --source openspec \
  --mode auto
```

npm 包入口由 `package.json` 的 `bin` 字段提供，`super-engineer` 和 `se` 都会转发到同一个 CLI。

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
/se:propose add-phone-filter
请根据当前 workspace 的 demand_file 生成或完善 OpenSpec change。
```

然后：

```text
/se:bridge
针对当前 OpenSpec change 生成交付阶段的桥接 todo，并总结待审核项。
```

人工确认后：

```text
/se:apply
使用当前工作空间，当前模式是 openspec + auto。
我已审核当前桥接 todo，可以进入交付阶段。
如果没有硬阻塞，自动推进到 verify；verify 通过后继续检查归档条件。
如果结果为 safe_merge，下一步再执行 /se:archive。
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

如果自动识别出的验证命令不适合当前项目，可以在 `workspace.yml` 中覆盖：

```yaml
verify_commands:
  default: pnpm test && pnpm build
  frontend-app: pnpm test && pnpm build
  user-service: go test ./...
```

最小 `openspec` 模式示例：

```yaml
version: 1
mode: manual
workflow_source: openspec
vars:
  demand_name: add-phone-filter
demand_file: superengineer/${demand_name}/需求.md
todo_file: superengineer/${demand_name}/todo.md
reference_files: []
code_path: ../../../code
output_dir: superengineer/${demand_name}/output
openspec:
  changes_dir: ../openspec/changes
```

`demand_file` 可以是本地 Markdown，也可以是飞书/Lark 云文档 URL。使用云文档时需要先安装并授权官方 CLI：

```bash
npx @larksuite/cli@latest install
lark-cli config init --new
lark-cli auth login --recommend
```

如果同一个工作空间经常切换需求，可以用 `vars` 避免重复修改路径：

```yaml
version: 1
mode: auto
workflow_source: openspec
vars:
  demand_name: 7-deamnd-addition-rate
demand_file: superengineer/${demand_name}/需求.md
todo_file: superengineer/${demand_name}/todo.md
reference_files:
  - ../docs/需求分析与实现指南.md
code_path: ../../../code
output_dir: superengineer/${demand_name}/output
openspec:
  changes_dir: ../openspec/changes
```

OpenSpec change 名称不从 `demand_name` 推导。请在 `/se:propose <change-name>` 后显式指定，例如 `/se:propose demand-addition-rate`。后续 `/se:bridge`、`/se:apply` 会使用 propose 阶段记录的当前 change。

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
- [docs/项目架构与设计说明.md](/Users/muke/Documents/personal/codex/super-engineer/docs/项目架构与设计说明.md)
- [super-engineer-workflow/SKILL.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/SKILL.md)
- [super-engineer-workflow/references/workflow.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/references/workflow.md)
- [super-engineer-workflow/references/contracts.md](/Users/muke/Documents/personal/codex/super-engineer/super-engineer-workflow/references/contracts.md)

## 许可证

本项目使用 [MIT License](/Users/muke/Documents/personal/codex/super-engineer/LICENSE)。
