# `se` 命令协议

`/se:*` 是用户发给 AI 的工作流指令，不是 shell 命令，也不是 OpenSpec `/opsx:*`。

用户只需要输入命令；AI 会根据当前 `workspace.yml`、状态机和 skill 协议调用底层脚本。

## 命令顺序

### todo 模式

```text
/se:init
-> /se:plan 或 /se:apply
-> /se:review
-> /se:verify
```

`todo + auto` 通常可以直接从 `/se:apply` 开始。

### OpenSpec 模式

```text
/se:propose <change-name>
-> /se:bridge
-> 人工审核 todo.md
-> /se:apply
-> /se:archive-check
-> /se:archive
```

`/se:propose` 后禁止直接 `/se:apply`；必须先 `/se:bridge`。

## 命令表

| 命令 | 作用 | 下一步 |
| --- | --- | --- |
| `/se:init` | 初始化或检查工作区 | todo 模式可 `/se:apply`，OpenSpec 模式可 `/se:propose <change-name>` |
| `/se:propose <change-name>` | 生成或修正 OpenSpec change，不改代码 | `/se:bridge` |
| `/se:bridge` | 将 `tasks.md` 桥接为待审核 `todo.md` | 审核后 `/se:apply` |
| `/se:plan` | 只生成实施计划，不改代码 | `/se:apply` |
| `/se:apply` | 进入交付，实现、自查，并在 auto 模式继续 review/verify | 失败则修复后重跑，通过后看状态 |
| `/se:review` | 单独执行代码审查 | `/se:verify` 或 `/se:apply` 修复 |
| `/se:verify` | 执行验证并由脚本发送通知 | OpenSpec 模式下一步 `/se:archive-check` |
| `/se:archive-check` | 检查 OpenSpec 是否可安全归档 | safe_merge 后 `/se:archive` |
| `/se:archive` | 归档 OpenSpec change 和相关 specs | 完成 |
| `/se:status` | 查看当前状态和阻塞项 | 按 allowed_next 继续 |

## 最短提示词

OpenSpec 模式：

```text
/se:propose add-user-phone-filter
```

```text
/se:bridge
```

审核 `todo.md` 后：

```text
/se:apply
```

todo 模式：

```text
/se:apply
```

## 约束

- `workspace.yml` 是用户维护的契约，AI 禁止修改。
- 状态、报告、通知必须由脚本生成。
- 飞书/PushPlus 通知只能由 verify 脚本发送。
- OpenSpec `tasks.md` 在 bridge 后发生变化时，必须重新 `/se:bridge`。
- 归档前必须先 `/se:archive-check`。

AI 内部执行协议以 `super-engineer-workflow/references/commands/` 下的命令分片为准。
