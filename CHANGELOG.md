# Changelog

## 0.1.2

- `se init` 在 `openspec` 模式下默认尝试执行 `openspec init . --tools codex,claude`。
- `se init` 自动生成工作区 `.claude/commands/se/*` 快捷命令。
- 当初始化时选择安装 Codex skill，同步生成 `~/.codex/prompts/se-*.md` 快捷提示。
- 增加 `--skip-openspec-init` 和 `--skip-commands` 以便高级用户跳过对应步骤。

## 0.1.1

- 调整 README 项目定位：适用于新系统开发和存量系统迭代，强调存量系统长期需求迭代优势更明显。
- 调整 npm 包描述，避免将适用场景限定为存量系统。

## 0.1.0

- 增加 `se` / `super-engineer` npm CLI 入口。
- 增加交互式初始化向导。
- 增加 `se doctor`、`se install`、`se sync`、`se version`。
- 增加 npm 打包白名单和临时产物排除规则。
- 增加 OpenSpec + todo 桥接工作流文档。
