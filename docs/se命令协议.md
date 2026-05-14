# `se` 命令协议

`se` 是 `super-engineer` 的专属命令前缀。

它的定位不是 shell 命令，而是用户发给 AI 的工作流指令。  
AI 收到这些指令后，再根据当前工作空间、当前模式和当前阶段，调用内部 workflow。

## 1. 设计原则

- 不复用 OpenSpec 官方 `/opsx:*`
- `se` 只表达 `super-engineer` 的工作流意图
- 用户只面向阶段说话，不需要关心底层脚本
- `openspec` 模式下，桥接 todo 是桥接产物，不是规格源头
- 桥接 todo 的实际路径由 `workspace.yml.todo_file` 决定，推荐继续使用 `todo.md`

## 2. 阶段模型

推荐把整个流程分成三段：

1. 规格阶段
2. 交付阶段
3. 归档阶段

典型状态流转：

```text
draft
-> spec_ready
-> todo_generated
-> todo_approved
-> implementing
-> reviewing
-> verifying
-> archive_ready
-> archived
```

如果出现阻塞，则进入：

```text
blocked
```

## 3. 命令列表

### `/se:init`

作用：

- 检查 `workspace.yml`
- 检查 `~/.super-engineer/skill-config.yml`
- 初始化工作流运行目录

适用模式：

- `todo`
- `openspec`

典型提示词：

```text
/se:init
使用当前工作空间，检查 workspace 是否可用，并告诉我缺哪些配置。
```

### `/se:propose`

作用：

- 为当前需求生成或完善 OpenSpec change
- 产出或更新 `proposal.md`、`design.md`、`tasks.md`
- 优先读取 `workspace.yml.demand_file` 作为原始需求输入

适用模式：

- `openspec`

典型提示词：

```text
/se:propose
请根据当前 workspace 的 demand_file 生成或完善 OpenSpec change。
```

### `/se:bridge`

作用：

- 读取当前 OpenSpec change
- 把 `tasks.md` 转成桥接 todo
- 输出待审核执行清单

适用模式：

- `openspec`

前置条件：

- 当前 change 已存在 `tasks.md`

典型提示词：

```text
/se:bridge
针对当前 OpenSpec change 生成桥接 todo，并总结待审核项。
```

### `/se:approve`

作用：

- 表达用户已审核当前桥接 todo
- 允许工作流进入交付阶段

适用模式：

- `openspec`

前置条件：

- 当前桥接 todo 已经人工审核

典型提示词：

```text
/se:approve
我已审核当前桥接 todo，可以进入交付阶段。
```

### `/se:plan`

作用：

- 创建新的交付会话
- 生成 `plan.json` 和 `plan.md`
- 给出影响范围、验收标准和主要风险

适用模式：

- `todo`
- `openspec`

前置条件：

- `todo` 模式：`todo.md` 已存在
- `openspec` 模式：推荐在 `/se:approve` 之后执行

典型提示词：

```text
/se:plan
使用当前工作空间。
基于当前交付输入生成计划，先不要改代码。
```

### `/se:apply`

作用：

- 启动交付阶段
- 执行实现、自查、审查、验证
- `openspec` 模式下自动回写执行摘要

适用模式：

- `todo`
- `openspec`

前置条件：

- `todo` 模式：`todo.md` 已存在
- `openspec` 模式：当前桥接 todo 已审核通过

典型提示词：

```text
/se:apply
使用当前工作空间。
如果没有硬阻塞，继续推进当前交付阶段。
```

### `/se:review`

作用：

- 对当前代码改动做审查
- 给出 gate、blocking findings、warning findings

适用模式：

- `todo`
- `openspec`

典型提示词：

```text
/se:review
继续当前工作空间，对当前改动做代码审查。
```

### `/se:verify`

作用：

- 执行验证
- 汇总每个仓库的验证结果
- 判断当前 workflow 是 `done` 还是 `blocked`

适用模式：

- `todo`
- `openspec`

典型提示词：

```text
/se:verify
继续当前工作空间，执行验证并汇报结果。
```

### `/se:archive-check`

作用：

- 检查当前 OpenSpec change 是否满足归档条件
- 输出 `archive_ready`、`merge_mode`、`blockers`、`spec_conflicts`

适用模式：

- `openspec`

前置条件：

- 当前 change 已完成交付并已有执行摘要

典型提示词：

```text
/se:archive-check
检查当前 OpenSpec change 是否满足归档条件。
```

### `/se:archive`

作用：

- 在满足安全条件时执行归档
- 同步 delta specs
- 移动当前 change 到 archive 目录

适用模式：

- `openspec`

前置条件：

- `archive_ready=true`
- `merge_mode=safe_merge`
- `spec_conflicts` 为空

典型提示词：

```text
/se:archive
仅在当前 change 满足安全归档条件时继续归档。
```

### `/se:status`

作用：

- 查看当前阶段
- 查看当前 session
- 查看阻塞项和下一步建议

适用模式：

- `todo`
- `openspec`

典型提示词：

```text
/se:status
告诉我当前工作流处在哪个阶段，还有哪些阻塞项。
```

## 4. 两种模式下怎么理解命令

### `todo` 模式

`todo` 模式通常从这里开始：

- `/se:init`
- `/se:plan`
- `/se:apply`

如果是 `auto`，通常直接 `/se:apply`。  
如果是 `manual`，通常先 `/se:plan`，再逐步 `/se:apply`、`/se:review`、`/se:verify`。

### `openspec` 模式

`openspec` 模式通常从这里开始：

- `/se:propose`
- `/se:bridge`
- `/se:approve`
- `/se:plan` 或 `/se:apply`
- `/se:archive-check`
- `/se:archive`

核心区别是：

- `todo` 模式的输入是用户直接维护的 `todo.md`
- `openspec` 模式的输入先是 OpenSpec change，再桥接成桥接 todo

## 5. 推荐使用约束

- `openspec` 模式下，不建议跳过 `/se:bridge`
- `openspec` 模式下，不建议跳过桥接 todo 的人工审核
- `manual` 模式下，建议在 `/se:plan` 之后先看计划再进入实现
- `auto` 模式下，只有出现硬阻塞才应该停下
- 归档前一定先做 `/se:archive-check`

## 6. 一个完整例子

下面是一条比较完整的 `openspec + auto` 使用链路：

```text
/se:propose
请根据当前 workspace 的 demand_file 生成或完善 OpenSpec change。
```

```text
/se:bridge
针对当前 OpenSpec change 生成桥接 todo，并总结待审核项。
```

```text
/se:approve
我已审核当前桥接 todo，可以进入交付阶段。
```

```text
/se:apply
使用当前工作空间。
当前模式是 openspec + auto。
如果没有硬阻塞，自动推进到 verify。
verify 通过后继续检查归档条件，但只有结果为 safe_merge 时才继续归档。
```

```text
/se:status
告诉我当前交付是否完成，是否已经进入归档阶段。
```
