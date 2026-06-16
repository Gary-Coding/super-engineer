# Changelog

## 0.1.7

- 拆分 `/se:*` 协议到 `references/commands/*`，AI 按命令读取最小协议上下文，降低固定 token 消耗。
- 增加 `route-check` JSON 预检入口，统一返回命令、阶段、允许状态和阻塞原因。
- OpenSpec bridge 记录 `tasks.md` hash；后续 plan/apply 发现 tasks 变化会拒绝继续并要求重新 bridge。
- 增强 `se doctor --fix`，可同步 skill 并补齐工作区 `.claude/commands/se/*` 快捷命令。
- 初始化完成提示改为推荐流程，明确 propose -> bridge -> 审核 todo -> apply。

## 0.1.6

- 修复计划生成失败或中断后重复 `/se:apply` 会创建多个空 session/output 目录的问题。

## 0.1.5

- 修复重复执行 `/se:plan` 会创建多个 session 的问题：计划阶段复用当前 session，交付中重复 plan 会被拒绝。
- 增加 E2E 测试，覆盖模板 CLI、OpenSpec 状态机与桥接、todo auto 会话、verify 长日志截断。
- 增加 `se templates`、`se template show`、`se template copy`，支持复制内置 `workspace.yml` 模板。
- 增加 OpenSpec、todo、Java 微服务、前端、多仓库等工作区模板。
- 增加模板使用指南，并在 README 和快速初始化文档中补充模板入口。

## 0.1.4

- Review 阶段优先读取 `plan-summary.json`，仅在缺失时回退到 `plan.json`。
- Self-check、verify、OpenSpec writeback 阶段优先读取轻量计划摘要，减少重复加载完整计划。
- Review 阶段默认压缩过长 diff 摘要，避免对话和报告带入大量无效上下文。
- Verify 阶段增加命令输出压缩工具，为长日志截断和摘要化提供统一入口。

## 0.1.3

- 压缩 `SKILL.md` 为轻量入口，详细规则改为按需读取 references，降低每次 `/se:*` 固定上下文消耗。
- 快捷命令模板改为极简形式，减少 Claude / Codex slash command 触发时的重复提示词。
- `/se:propose` 不再把 `reference_files` 全文复制进 `propose-input.json` / `propose-input.md`，改为路径、sha256、标题和摘要片段。
- 大型 Markdown 参考文档自动摘要，保留按需读取全文能力。
- OpenSpec bridge context 增加 proposal/design 摘要片段，避免后续阶段重复读取全文。
- `plan` 阶段新增 `plan-summary.json`，供后续阶段优先读取轻量计划摘要。
- 收紧脚本最终回复约束文案，默认输出更 compact。

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
