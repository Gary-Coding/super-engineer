# super-engineer

`super-engineer` 是一个面向工程交付场景的 AI 工作流项目。

它的目标不是单纯“和 AI 聊天写代码”，而是把真实项目中的需求分析、计划生成、代码修改、代码审查、验证测试这些步骤，沉淀成一个可追踪、可归档、可回看的工作流能力。

当前仓库优先实现的是 Skill：

- `super-engineer-workflow`

后续会继续扩展可视化插件与多 Agent 适配能力。

## 项目背景

在中大型项目里，单纯依赖 Chat 式对话驱动 AI Agent，通常会遇到这些问题：

- 对话上下文容易被冲刷，计划难以长期保留
- AI 的执行过程不透明，用户很难知道当前进度
- 需求、实现、审查、验证之间缺少稳定的中间产物
- 多轮协作后，很难回看某一次任务到底做了什么

`super-engineer` 想解决的，就是把这些本来散落在对话里的“工程过程”，转成结构化、持久化的工作流产物。

## 当前能力

当前版本已经支持以下能力：

- 以工作空间中的 `workspace.yml` 作为业务配置入口
- 以 `~/.super-engineer/skill-config.yml` 作为 Skill 自身配置入口
- 从用户维护的 `todo.md` 中提取本轮需求
- 读取多个参考文件作为项目上下文
- 面向当前代码目录生成计划
- 自动识别单仓库或聚合目录下的多个独立仓库
- 通过统一入口脚本推进 `plan -> implement -> review -> verify`
- 支持 `manual` 和 `auto` 两种工作流模式
- 每次新会话自动归档，历史数据不会被覆盖
- 给 AI 使用的数据与给人查看的 Markdown 报告分离存储
- 记录整个工作流总耗时
- 支持在工作流完成后推送 PushPlus 通知

## 当前目录

```text
super-engineer/
├── README.md
└── super-engineer-workflow/
    ├── SKILL.md
    ├── agents/
    ├── assets/
    ├── references/
    └── scripts/
```

## 工作空间设计

这个项目采用“Skill 与工作空间分离”的设计。

Skill 本身只提供规则、脚本和参考资料。真实业务项目的输入输出，全部放在用户自己的工作空间里。

工作空间根目录必须存在 `workspace.yml`：

```yaml
version: 1
mode: manual
todo_file: /absolute/path/to/your-workspace/todo.md
reference_files:
  - /absolute/path/to/your-project/docs/项目介绍.md
  - /absolute/path/to/your-project/docs/开发规范.md
code_path: /absolute/path/to/your-project
output_dir: /absolute/path/to/your-output
```

真实生效的 Skill 配置放在：

```text
~/.super-engineer/skill-config.yml
```

首次运行时如果文件不存在，Skill 会自动生成一份默认配置，默认都关闭：

```yaml
version: 1
notification:
  pushplus:
    token: ""
    ordinary:
      enabled: false
      channel: wechat
      template: markdown
  feishu:
    enabled: false
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook"
    secret: ""
```

需要注意：

- 首次自动生成 `~/.super-engineer/skill-config.yml` 后，当前工作流会主动暂停
- Skill 会提示生成位置
- 你完善配置后，再重新执行工作流即可

配置说明：

- `mode`
  - `manual`：计划、实现、审查后暂停，等待用户确认
  - `auto`：在未阻塞时自动推进整个工作流
- `todo_file`：本轮需求待办文件
- `reference_files`：项目介绍、架构设计、业务规则、开发规范等参考文件
- `code_path`：实际需要分析和修改的代码目录
  - 可以直接指向单个仓库根目录
  - 也可以指向多个服务聚合目录，此时建议在 `todo.md` 中明确写出“修改的服务是 xxx”或“修改的服务包括 xxx、yyy”
- `output_dir`：给人查看的 Markdown 产物输出目录

`~/.super-engineer/skill-config.yml` 说明：

- `notification.pushplus.token`：PushPlus token
- `notification.pushplus.ordinary.enabled`：是否启用普通 PushPlus 消息，默认关闭
- `notification.pushplus.ordinary.channel`：普通消息渠道，默认 `wechat`
- `notification.pushplus.ordinary.template`：普通消息模板，建议用 `markdown`
- `notification.feishu.enabled`：是否启用飞书原生机器人消息，默认关闭
- `notification.feishu.webhook_url`：飞书自定义机器人 webhook 地址
- `notification.feishu.secret`：飞书机器人签名秘钥，可选；只有开启签名校验时才需要填写

所有路径都必须是绝对路径。

如果没有参考文件，也可以写成：

```yaml
reference_files: []
```

## 运行时产物

工作空间内只保存 AI 需要持续读取的数据：

```text
<workspace>/.super-engineer/current-session.json
<workspace>/.super-engineer/sessions/<session_id>/plan.json
<workspace>/.super-engineer/sessions/<session_id>/status.json
<workspace>/.super-engineer/sessions/<session_id>/notification.json
```

给人查看的报告输出到 `output_dir`：

```text
<output_dir>/<session_id>/plan.md
<output_dir>/<session_id>/review.md
<output_dir>/<session_id>/verify.md
```

每次新的 `plan` 都会生成新的 `session_id`，历史会话会完整保留。

其中：

- `status.json` 会记录工作流开始时间、结束时间、总耗时和通知状态
- `notification.json` 会记录本次通知发送结果，包含 PushPlus 普通消息和飞书原生 webhook 各自的发送状态

## todo.md 推荐写法

当前版本最稳定、最推荐的写法，是扁平的一级待办列表：

```md
# 待办

- 用户列表接口增加按手机号精确筛选
- 补齐 service 和 controller 层测试
```

这也是当前最适合自动生成计划的格式。

如果某个需求点比较复杂，也可以继续补充详细描述，推荐这样写：

```md
# 待办

- 用户列表接口增加按手机号精确筛选
  详细说明：
  1. 仅支持管理员角色使用
  2. 前端为空时不传该参数
  3. 后端需要兼容旧参数
  4. 需要补充 controller 和 service 层测试

- 补齐 service 和 controller 层测试
```

如果 `code_path` 是一个包含多个服务仓库的聚合目录，推荐在 `todo.md` 中显式写出目标服务：

```md
# 限制条件

- 修改的服务是 item-core-facde-server

# 待办

- 用户列表接口增加按手机号精确筛选
- 补齐 service 和 controller 层测试
```

如果一个需求会同时修改多个独立仓库，可以这样写：

```md
# 限制条件

- 修改的服务包括 item-core-facde-server、order-center-server

# 待办

- 同步调整两个服务的接口返回文案
- 补齐对应测试
```

当前版本也支持“主需求 + 子要求”结构：

```md
# 限制条件
- 修改的服务是 item-core-facade-server

# 待办
- 主需求1
1. 子要求1
2. 子要求2

- 主需求2
1. 子要求1
2. 子要求2
```

在这个结构里：

- `- 主需求` 会被解析为任务主项
- 紧跟其后的 `1.` `2.` 或普通说明行，会自动挂到这个主项下面
- `plan.json` 中会写入结构化的 `task_breakdown`
- `plan.md` 中会显示“任务拆解”

如果你的需求比较复杂，推荐使用“限制条件 + 大模块 + 勾选任务 + 子要求”的结构：

```md
# 限制条件
- 修改的服务是 item-core-facade-server

# 待办事项

## 保存草稿、新建自采品
- [ ] 表 ic_franchisee_self_sku_audit 增加字段 black_gold_price decimal (10, 2) null comment '加盟商自建品黑金价'，给出 DDL 语句
- [ ] /saveToDraftBox 接口入参增加 blackGoldPrice，数据落 ic_franchisee_self_sku_audit
- [ ] /bpmCallBackFranchiseeSkuAudit 审核通过之后流程
1. 黑金价需要插入加盟商自采品关系表 ic_franchisee_self_sku
2. 如果 isNew，插入之后需要发一个黑金价变更 mq

## 添加自采品到门店
- [ ] /addSelfSkuToStore 接口入参增加 blackGoldPrice，数据落 ic_franchisee_self_sku_audit
- [ ] buildAuditFormDataFields 映射字段需要考虑新增字段
```

在这个结构里：

- `##` 会被解析为大模块
- `- [ ]` 会被当成未完成任务，进入本轮工作流
- `- [x]` 会被当成已完成任务，不进入本轮工作流
- 紧跟在任务后面的 `1.` `2.` 或普通说明，会挂到这个任务下面
- 每次新一轮执行时，只会读取未完成任务
- 人工复核后，你可以手动把已完成项改成 `- [x]`，把未完成或完成不佳的项保留为 `- [ ]`

需要注意的是：

- 当前版本会优先把 `# 待办` 章节作为真实需求，把 `# 限制条件` 章节作为约束条件
- 当前版本已经可以读取这些补充文本作为需求上下文
- 当前版本已经支持 `## 模块`、`- [ ]`、`- [x]` 和子要求组合格式
- 当前版本每次只会针对未完成任务生成计划；如果 todo 全部标记完成，plan 会直接停止
- 当前版本已经支持根据 todo 中的服务名，从聚合代码目录里自动定位目标仓库
- 当前版本已经支持一次会话同时命中多个独立仓库，并逐仓执行 review 与 verify
- 但还没有把 `todo.md` 真正解析成“严格的树形层级结构”
- 所以如果想要最稳定的计划结果，优先还是建议一级待办尽量清晰明确

后续版本会继续增强复杂需求结构的表达能力。

## 快速开始

### 1. 准备工作空间

创建一个独立工作空间目录，并放入：

- `workspace.yml`
- `todo.md`

同时准备好：

- 真实业务代码目录
- 项目参考文档
- Markdown 输出目录

如果 `workspace.yml` 中指定的 `todo_file` 还不存在，执行 `init` 或 `plan` 时会自动创建一个带示例结构的 `todo.md` 模板。

需要注意：

- 执行 `init` 时，模板创建后不会继续生成计划，只会提示你先完善 todo
- 执行 `plan` 时，如果检测到当前 todo 仍然是模板示例内容，会直接停止，并提示你先补全真实需求

### 2. 安装 Skill

当前使用方式是把 `super-engineer-workflow` 安装到支持 Skill 的 Agent 环境中。

以 Claude 本地目录为例：

```text
~/.claude/skills/super-engineer-workflow
```

### 3. 执行工作流

优先使用统一入口脚本：

```bash
python3 scripts/run-workflow.py init
python3 scripts/run-workflow.py plan
python3 scripts/run-workflow.py start-implement
python3 scripts/run-workflow.py finish-implement
python3 scripts/run-workflow.py review
python3 scripts/run-workflow.py verify
```

也可以通过：

```bash
python3 scripts/run-workflow.py next
```

根据当前状态推进到下一阶段。

## 当前适用范围

当前版本优先面向：

- Java 项目
- 本地工作空间驱动的工程流程
- 希望保留中间产物和历史会话的 AI 协作场景

虽然项目设计上已经考虑了未来多语言、多 Agent 和 OpenClaw 等场景，但当前实现重点仍然是 Java 工作流的第一版闭环。

## 设计原则

- 工作空间是唯一运行上下文，不依赖全局配置
- 真实代码目录和 Skill 目录分离
- AI 数据与人类可读报告分离
- 每轮任务必须归档，不能覆盖历史
- 工作流状态必须落盘，而不是只存在于聊天记录里

## 适配规划

后续会继续沿这些方向扩展：

- 更强的 `todo.md` 结构化表达能力
- 支持更多语言和工程栈
- 更完整的计划更新与回滚机制
- VS Code 插件和可视化白板能力
- 面向 OpenClaw 等自主 Agent 的接入适配
- 更标准的开源发布与安装体验

## 当前状态

当前仓库处于早期可用版本阶段，重点是先把 Skill 主链路打通：

- 配置驱动
- 计划生成
- 审查报告
- 验证报告
- 会话归档

如果你希望把这个项目用于真实业务项目，建议先在一个小型或中等复杂度的 Java 项目上试跑，再逐步扩展到更复杂的生产场景。

## License

当前仓库暂未补充正式 License。

如果后续准备在 GitHub 开源，建议尽快补齐：

- `LICENSE`
- 发布说明
- 贡献指南
- Issue / PR 模板
