# `/se:archive-check` 与 `/se:archive`

## `/se:archive-check`

用途：检查 OpenSpec change 是否可以安全归档。

前置：`/se:verify` 已通过。

执行：
`python3 scripts/run-workflow.py route-se --command-text "/se:archive-check"`

只有 `archive_ready=true`、`merge_mode=safe_merge` 且无 spec 冲突时，才允许提示 `/se:archive`。

## `/se:archive`

用途：归档当前 OpenSpec change，沉淀长期 specs。

前置：已完成 `/se:archive-check` 且结果为 safe merge。

执行：
`python3 scripts/run-workflow.py route-se --command-text "/se:archive"`

禁止跳过 archive-check 直接归档。
