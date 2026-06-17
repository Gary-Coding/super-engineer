# SpecTrace 重构实施方案

本文档用于指导 AI 将当前 `super-engineer-workflow` 重构为新的开源品牌项目 **SpecTrace**。

重构目标不是简单改名，而是将现有 skill 收敛为 **SpecTrace RD**，同时为未来的需求梳理阶段和测试阶段预留清晰扩展边界。

## 1. 品牌与定位

项目品牌：

```text
SpecTrace
```

项目副标题：

```text
Structured AI Delivery Workflow
```

一句话定位：

```text
SpecTrace turns requirements and specs into traceable AI-delivered software changes.
```

中文定位：

```text
SpecTrace 把需求和规格转化为可追踪的 AI 软件交付变更。
```

当前阶段先实现：

```text
SpecTrace RD
```

当前 RD 定位：

```text
SpecTrace RD turns requirements and specs into traceable AI-delivered software changes through planning, implementation, review, verification, handoff, and archive checks.
```

## 2. 三阶段 Skill 命名

SpecTrace 是一个 suite，不是单个大 skill。

未来完整形态：

```text
SpecTrace Suite
├── SpecTrace PM
├── SpecTrace RD
└── SpecTrace QA
```

| 阶段 | Skill 名称 | 作用 | 当前状态 |
| --- | --- | --- | --- |
| 产品需求阶段 | `SpecTrace PM` | 需求梳理、澄清、业务规则、验收标准、可选生成 OpenSpec 前置材料 | 预留 |
| 研发交付阶段 | `SpecTrace RD` | 计划、实现、自查、审查、验证、交付报告、OpenSpec 回写和归档检查 | 当前实现 |
| 测试阶段 | `SpecTrace QA` | 测试计划、测试用例、测试执行、缺陷反馈、回归清单、测试报告 | 预留 |

命名说明：

- `PM` = Product Manager / 产品经理。
- `RD` = Research & Development / 研发工程师。
- `QA` = Quality Assurance / 质量保证工程师。

这三个缩写贴近企业真实协作角色，同时保持统一品牌前缀。

## 3. 新项目组织

推荐新开仓库：

```text
spectrace/
```

推荐一个仓库承载三个 skill，而不是拆成三个项目。

```text
spectrace/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── package.json
├── bin/
│   └── spectrace.js
├── skills/
│   ├── spectrace-pm/
│   │   └── SKILL.md
│   ├── spectrace-rd/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/
│   └── spectrace-qa/
│       └── SKILL.md
├── scripts/
│   ├── spectrace-cli.py
│   ├── se-to-st-migrate.py
│   └── shared/
├── templates/
│   └── workspaces/
└── docs/
```

当前重构优先级：

1. 完成 `spectrace-rd`。
2. 预留 `spectrace-pm` 和 `spectrace-qa` 的最小 `SKILL.md`。
3. 共享 workspace 协议先设计好，但 PM / QA 逻辑不展开实现。

## 4. 包名、CLI 与命令前缀

推荐 npm 包名：

```text
@gary-coding/spectrace
```

推荐 CLI：

```bash
spectrace
```

推荐短别名：

```bash
st
```

推荐 AI 命令前缀：

```text
/st:*
```

当前 `/se:*` 不在新项目中长期保留。可以提供一次性迁移脚本或迁移文档，但不要在新项目中继续维护 `/se:*` 双协议入口。

## 5. 三阶段命令规划

### 5.1 SpecTrace PM，预留

```text
/st:intake
/st:clarify
/st:spec
/st:acceptance
```

| 命令 | 作用 |
| --- | --- |
| `/st:intake` | 读取原始需求、会议记录、飞书文档，生成需求草稿 |
| `/st:clarify` | 找出需求不清晰点，生成澄清问题 |
| `/st:spec` | 生成结构化需求规格，可选生成 OpenSpec 前置材料 |
| `/st:acceptance` | 生成验收标准和业务规则清单 |

### 5.2 SpecTrace RD，当前实现

```text
/st:propose <change-name>
/st:bridge
/st:plan
/st:apply
/st:review
/st:verify
/st:archive-check
/st:archive
/st:status
```

| 命令 | 作用 |
| --- | --- |
| `/st:propose <change-name>` | 生成或修正 OpenSpec change，不改代码 |
| `/st:bridge` | 将 OpenSpec `tasks.md` 桥接为待审核 `todo.md` |
| `/st:plan` | 只生成实施计划，不改代码 |
| `/st:apply` | 进入开发交付，推进实现、自查、review、verify |
| `/st:review` | 单独执行代码审查 |
| `/st:verify` | 执行验证并由脚本发送通知 |
| `/st:archive-check` | 检查 OpenSpec 是否满足安全归档条件 |
| `/st:archive` | 执行 OpenSpec 归档 |
| `/st:status` | 查看当前需求和阶段状态 |

### 5.3 SpecTrace QA，预留

```text
/st:test-plan
/st:test-cases
/st:test-execute
/st:defect
/st:regression
/st:test-report
```

| 命令 | 作用 |
| --- | --- |
| `/st:test-plan` | 根据需求、验收标准和交付报告生成测试计划 |
| `/st:test-cases` | 生成测试用例 |
| `/st:test-execute` | 记录测试执行结果 |
| `/st:defect` | 根据测试失败生成缺陷反馈 |
| `/st:regression` | 生成回归测试清单 |
| `/st:test-report` | 生成测试验收报告 |

## 6. Workspace 协议

SpecTrace 应该从一开始支持团队多需求并行。

核心原则：

```text
需求级隔离 + Git 分支隔离 + 状态目录隔离 + 显式 demand 参数
```

推荐工作区：

```text
spectrace-workspace/
├── workspace.yml
├── demands/
│   └── <demand-name>/
│       ├── demand.yml
│       ├── state.json
│       ├── requirements/
│       │   ├── raw.md
│       │   ├── requirement.md
│       │   ├── business-rules.md
│       │   └── acceptance.md
│       ├── delivery/
│       │   ├── todo.md
│       │   ├── plan-summary.json
│       │   ├── review.json
│       │   ├── verify.json
│       │   ├── execution-summary.json
│       │   ├── task-mapping.json
│       │   ├── handoff.md
│       │   └── output/
│       └── qa/
│           ├── test-plan.md
│           ├── test-cases.md
│           ├── defect-list.md
│           ├── regression-checklist.md
│           └── test-report.md
├── openspec/
│   ├── changes/
│   └── specs/
└── .spectrace/
    ├── workspace-index.json
    ├── sessions/
    └── locks/
```

`workspace.yml` 示例：

```yaml
version: 1
project: spectrace

workspace:
  demands_dir: demands
  openspec_dir: openspec
  default_workflow_source: openspec
  default_delivery_mode: auto

paths:
  code_path: ../code

integrations:
  openspec: true
  feishu: false
  pushplus: false

commands:
  prefix: /st
```

每个需求独立 `demand.yml`：

```yaml
demand_name: add-phone-filter
change_name: add-phone-filter
title: 用户列表增加手机号精确筛选

workflow_source: openspec
delivery_mode: auto

paths:
  raw_requirement: requirements/raw.md
  requirement: requirements/requirement.md
  acceptance: requirements/acceptance.md
  delivery_todo: delivery/todo.md
  delivery_output: delivery/output
  qa_plan: qa/test-plan.md
  qa_report: qa/test-report.md

code_repositories:
  - name: user-service
    path: ../../code/user-service
    branch: feature/add-phone-filter
```

## 7. 多需求并行设计

当前 `super-engineer` 的单需求设计需要重构。

不再使用全局：

```text
.super-engineer/current-session.json
.super-engineer/se-state.json
vars.demand_name
```

改为需求级：

```text
demands/<demand-name>/.spectrace/current-session.json
demands/<demand-name>/.spectrace/state.json
demands/<demand-name>/delivery/todo.md
demands/<demand-name>/delivery/output/
```

所有 AI 命令必须能显式指定 demand：

```text
/st:apply add-phone-filter
/st:test-plan add-price-rule
```

如果工作区存在多个 active demand，而命令没有指定 demand，脚本必须拒绝并提示用户选择：

```text
检测到多个进行中的需求，请指定：
/st:apply <demand-name>
```

## 8. Git-first 团队共享

SpecTrace 面向企业和团队时，推荐使用 Git 仓库共享工作区。

不要把 SpecTrace 产物放进业务代码仓库，推荐单独仓库：

```text
spectrace-workspace.git
```

业务代码仍在各自仓库：

```text
user-service.git
admin-web.git
```

推荐分支策略：

```text
main
└── demand/add-phone-filter
```

每个需求一个分支。三阶段产物都提交到该需求分支，QA 通过后合并到 `main`。

SpecTrace CLI 需要提供 Git 辅助命令：

```bash
spectrace demand new add-phone-filter
spectrace demand list
spectrace status add-phone-filter
spectrace git summary add-phone-filter
spectrace git stage add-phone-filter --stage delivery
```

默认不要自动 commit。CLI 只给出建议提交文件和建议 commit message。

## 9. 当前代码迁移映射

| 当前路径 / 名称 | 新路径 / 名称 |
| --- | --- |
| `super-engineer-workflow/` | `skills/spectrace-rd/` |
| `super-engineer-workflow/SKILL.md` | `skills/spectrace-rd/SKILL.md` |
| `/se:*` | `/st:*` |
| `se` CLI | `spectrace` CLI，短别名 `st` |
| `.super-engineer/` | `.spectrace/` |
| `superengineer/<demand>` | `demands/<demand>` |
| `workspace.yml.vars.demand_name` | `demands/<demand>/demand.yml` |
| `todo_file` | `demands/<demand>/delivery/todo.md` |
| `output_dir` | `demands/<demand>/delivery/output` |

迁移时不要保留双协议入口。新项目只实现 `/st:*`。

## 10. RD 阶段必须保留的能力

以下能力来自当前 skill，迁移后必须保留：

- `todo` / `openspec` 双输入模式
- OpenSpec CLI 集成
- OpenSpec `tasks.md -> todo.md` bridge
- bridge 后 `tasks.md` hash 校验
- `route-check` JSON 预检
- `route-se --json` 摘要输出，迁移后改名为 `route-st --json`
- workflow lock
- `discovery-summary.json`
- `plan-summary.json`
- `review.json`
- `verify.json`
- `notification.json`
- `execution-summary.json`
- `task-mapping.json`
- OpenSpec hash drift 检查
- archive-check / archive
- 多语言 adapter
- Feishu / PushPlus 通知
- E2E / smoke / pack check

## 11. Relationship with OpenSpec

新项目 README 必须增加声明：

```md
## Relationship with OpenSpec

SpecTrace integrates with the OpenSpec CLI and OpenSpec workspace structure.
It is not affiliated with, endorsed by, or maintained by the OpenSpec project.

OpenSpec is an open-source project licensed under the MIT License:
https://github.com/Fission-AI/OpenSpec
```

不要使用 OpenSpec 官方 `/opsx:*` 作为 SpecTrace 命令。

不要暗示 SpecTrace 是 OpenSpec 官方扩展。

## 12. 新 README 首屏

新项目 README 首屏只保留：

1. 它是什么
2. 适合谁
3. 三步开始
4. 一个最小示例

示例：

```md
# SpecTrace

Structured AI Delivery Workflow

SpecTrace turns requirements and specs into traceable AI-delivered software changes.

## Start

npm install -g @gary-coding/spectrace
spectrace init
spectrace sync --target both

Then ask your AI agent:

/st:propose add-phone-filter
/st:bridge
/st:apply
```

## 13. 最小验收标准

重构完成后必须通过：

```bash
npm run check
npm run e2e
npm run smoke
npm run pack:check
```

并额外确认：

- npm 包名为 `@gary-coding/spectrace`。
- CLI 支持 `spectrace version` 和 `st version`。
- skill 名称为 `spectrace-rd`。
- 新项目不包含 `super-engineer-workflow` 字样。
- 新项目不包含 `/se:*` 协议入口。
- 新项目不包含 `.super-engineer` 运行目录。
- 新项目默认使用 `.spectrace`。
- README 不包含作者本机绝对路径。
- README 明确说明与 OpenSpec 的关系。
- E2E 覆盖至少一个 `openspec + auto` RD 流程。
- E2E 覆盖多个 demand 并行时无参命令被拒绝。

## 14. 分阶段实施建议

### 阶段 1：品牌和目录重构

- 新建 `spectrace` 仓库。
- 迁移当前核心代码到 `skills/spectrace-rd/`。
- 改包名、CLI、skill 名和 README。
- `/se:*` 全部替换为 `/st:*`。

### 阶段 2：需求级隔离

- 引入 `demands/<demand>/demand.yml`。
- 状态文件迁移到 `demands/<demand>/.spectrace/`。
- 所有命令支持 `<demand-name>` 参数。
- 多 active demand 时，无参命令必须拒绝。

### 阶段 3：Git-first 协作

- 增加 `spectrace demand new/list/status`。
- 增加 `spectrace git summary/stage`。
- 文档明确一个需求一个 Git 分支。

### 阶段 4：预留 PM / QA

- 增加 `skills/spectrace-pm/SKILL.md`。
- 增加 `skills/spectrace-qa/SKILL.md`。
- 暂不实现复杂逻辑，只声明阶段边界、输入输出和未来命令。

## 15. 重构原则

- 不做大而全单 skill。
- 不保留 `/se:*` 双入口。
- 不保留 `.super-engineer` 双运行目录。
- 不把需求交付产物放入业务代码仓库。
- 不复制 OpenSpec 源码或长文档。
- 不让 AI 猜当前 demand。
- 所有状态和报告必须由脚本生成。
- 所有阶段产物必须可被 Git 追踪。

