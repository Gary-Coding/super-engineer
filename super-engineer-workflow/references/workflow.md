# 工作流契约

## 配置文件

工作流会读取两份配置：

- `<workspace>/workspace.yml`
- `~/.super-engineer/skill-config.yml`

`<workspace>` 就是当前使用这个 skill 的目录。

`workspace.yml` 必须包含：

- `version`
- `mode`
- `todo_file`
- `reference_files`
- `code_path`
- `output_dir`

以上路径必须全部使用绝对路径。

`~/.super-engineer/skill-config.yml` 可以包含可选通知：

- `notification.pushplus.token`
- `notification.pushplus.ordinary.enabled`
- `notification.pushplus.ordinary.channel`
- `notification.pushplus.ordinary.template`
- `notification.feishu.enabled`
- `notification.feishu.webhook_url`
- `notification.feishu.secret`

如果 `~/.super-engineer/skill-config.yml` 不存在：

- 首次运行时自动创建
- 创建后当前工作流立即停止
- 用户完善配置后再重新执行

通知规则：

- `ordinary.enabled=true` 时发送普通 PushPlus 消息，默认发给自己
- `feishu.enabled=true` 时通过飞书原生自定义机器人 webhook 发送消息
- `feishu.secret` 可选，仅在机器人开启签名校验时填写
- 两条路由可以同时开启，工作流结束后会分别发送

`code_path` 可以是：

- 单个项目仓库根目录
- 包含多个服务仓库的聚合目录

如果是聚合目录，工作流应优先根据 todo 中的服务名约束自动定位目标仓库。

如果 todo 中明确指定了多个服务，工作流应解析出多个目标仓库，并在后续阶段逐仓执行。

## 运行时目录布局

工作空间内部只保存给 AI 使用的数据：

- `<workspace>/.super-engineer/current-session.json`
- `<workspace>/.super-engineer/sessions/<session_id>/discovery.json`
- `<workspace>/.super-engineer/sessions/<session_id>/plan.json`
- `<workspace>/.super-engineer/sessions/<session_id>/self-check.json`
- `<workspace>/.super-engineer/sessions/<session_id>/review.json`
- `<workspace>/.super-engineer/sessions/<session_id>/verify.json`
- `<workspace>/.super-engineer/sessions/<session_id>/status.json`

给人查看的 Markdown 产物统一写到输出目录：

- `<output_dir>/<session_id>/discovery.md`
- `<output_dir>/<session_id>/plan.md`
- `<output_dir>/<session_id>/self-check.md`
- `<output_dir>/<session_id>/review.md`
- `<output_dir>/<session_id>/verify.md`

会话附加产物：

- `<workspace>/.super-engineer/sessions/<session_id>/notification.json`

## 会话规则

- 每次执行 `plan` 都必须创建新的 `session_id`
- 新会话不能覆盖历史会话目录
- `current-session.json` 只指向当前正在推进的会话
- 后续 `start-implement`、`finish-implement`、`review`、`verify`、`status` 都基于当前会话执行
- `plan` 会自动执行 `discover`，`finish-implement` 会自动执行 `self-check`
- `auto` 模式下，除非进入硬阻塞，否则不能在对话里要求用户批准继续
- 工作流总耗时按当前会话开始到 verify 收口结束的真实墙钟时间计算

## 硬阻塞定义

只有出现以下情况，才允许停止并等待用户：

- 工作空间配置缺失或不合法
- todo 文件缺失，且无法自动创建或内容为空到无法判断需求
- 无法定位目标仓库
- 多仓场景下目标服务不明确
- 必要命令无法执行，且无法自动兜底
- 验证失败到必须人工介入
- 实现自查或 review 发现阻塞级问题
- 发现需求与代码现实严重冲突，继续修改会明显越界

以下情况不属于硬阻塞，必须继续推进：

- 计划还不够精确
- 还需要先去代码里定位具体实现位置
- 想先让用户确认某一步是否继续
- review 过程中发现计划要补充

## 产物规则

- JSON 产物保持稳定、结构化、便于机器读取
- Markdown 产物保持简洁、便于人阅读
- 只要阶段、阻塞、下一步动作发生变化，就更新当前会话的 `status.json`
- 优先通过 `scripts/run-workflow.py` 推进阶段，避免手工拼接状态
- verify 收口后，如果配置了通知，自动发送工作流完成通知，但通知失败不能覆盖真实验证结论
