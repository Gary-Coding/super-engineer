#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "super-engineer-workflow"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="安装 super-engineer skill，并初始化业务工作区。"
    )
    parser.add_argument("--workspace", help="业务工作区目录，默认使用当前目录。")
    parser.add_argument("--code-path", help="代码目录，写入 workspace.yml。默认：../code")
    parser.add_argument("--demand-name", help="需求目录名。默认：1-your-demand")
    parser.add_argument("--source", choices=["todo", "openspec"], help="输入模式。默认：openspec")
    parser.add_argument("--mode", choices=["manual", "auto"], help="执行模式。默认：auto")
    parser.add_argument(
        "--install",
        choices=["none", "codex", "claude", "both"],
        help="安装 skill 到本机目录。默认：none",
    )
    parser.add_argument("--force-skill", action="store_true", help="安装 skill 时先删除已有目录。")
    parser.add_argument("--openspec-init", action="store_true", help="如果安装了 openspec CLI，尝试执行 openspec init。openspec 模式默认启用。")
    parser.add_argument("--skip-openspec-init", action="store_true", help="openspec 模式下也跳过 openspec init。")
    parser.add_argument("--skip-commands", action="store_true", help="跳过生成 Claude / Codex 快捷命令。")
    parser.add_argument("--yes", action="store_true", help="非交互模式，全部使用参数或默认值。")
    args = parser.parse_args()

    if should_prompt(args):
        args = prompt_args(args)

    install = args.install or "none"
    source = args.source or "openspec"
    mode = args.mode or "auto"
    demand_name = args.demand_name or "1-your-demand"
    code_path = args.code_path or "../code"
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else Path.cwd().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    if install in ("codex", "both"):
        install_skill(skill_target("codex"), args.force_skill)
    if install in ("claude", "both"):
        install_skill(skill_target("claude"), args.force_skill)

    ensure_global_skill_config()
    init_workspace(
        workspace=workspace,
        code_path=code_path,
        demand_name=demand_name,
        source=source,
        mode=mode,
        openspec_init=should_init_openspec(source, args.openspec_init, args.skip_openspec_init),
        install_target=install,
        skip_commands=args.skip_commands,
    )
    print_summary(workspace, demand_name, source, mode)


def should_prompt(args: argparse.Namespace) -> bool:
    if args.yes:
        return False
    provided = any(
        [
            args.workspace,
            args.code_path,
            args.demand_name,
            args.source,
            args.mode,
            args.install,
            args.force_skill,
            args.openspec_init,
            args.skip_openspec_init,
            args.skip_commands,
        ]
    )
    return not provided and sys.stdin.isatty()


def prompt_args(args: argparse.Namespace) -> argparse.Namespace:
    print("Super Engineer 初始化向导")
    print("该向导会逐步完成：环境检查、skill 安装、工作区结构初始化、workspace.yml 生成。")
    print("按 Enter 使用默认值。")
    print("")
    print("Step 1/7 环境检查")
    print(f"  Python: {sys.executable}")
    print(f"  Skill:  {SKILL_DIR}")
    print(f"  OpenSpec CLI: {'已安装' if shutil.which('openspec') else '未检测到'}")
    print("")
    print("Step 2/7 选择本机 skill 安装目标")
    args.install = prompt_choice(
        "安装 skill 到哪里",
        choices=["both", "codex", "claude", "none"],
        default="both",
        labels={
            "both": "Codex 和 Claude",
            "codex": "仅 Codex",
            "claude": "仅 Claude",
            "none": "暂不安装",
        },
    )
    args.force_skill = prompt_bool("如果 skill 已存在，是否覆盖安装", default=False)
    print("")
    print("Step 3/7 选择业务工作区")
    args.workspace = prompt_text("业务工作区目录", default=str(Path.cwd()))
    print("")
    print("Step 4/7 配置代码目录和当前需求")
    args.code_path = prompt_text("代码目录 code_path", default="../code")
    args.demand_name = prompt_text("当前需求目录名", default="1-your-demand")
    print("")
    print("Step 5/7 选择工作流模式")
    args.source = prompt_choice(
        "输入模式",
        choices=["openspec", "todo"],
        default="openspec",
        labels={
            "openspec": "OpenSpec + todo 桥接",
            "todo": "直接读取 todo.md",
        },
    )
    args.mode = prompt_choice(
        "执行模式",
        choices=["auto", "manual"],
        default="auto",
        labels={
            "auto": "自动推进到验证",
            "manual": "关键阶段等待人工确认",
        },
    )
    print("")
    print("Step 6/7 OpenSpec 初始化与快捷命令")
    args.openspec_init = prompt_bool("是否尝试执行 openspec init", default=True)
    args.skip_openspec_init = not args.openspec_init
    args.skip_commands = not prompt_bool("是否生成 Claude / Codex 快捷命令", default=True)
    print("")
    print("Step 7/7 执行前确认")
    print(f"  install:       {args.install}")
    print(f"  force_skill:   {args.force_skill}")
    print(f"  workspace:     {Path(args.workspace).expanduser()}")
    print(f"  code_path:     {args.code_path}")
    print(f"  demand_name:   {args.demand_name}")
    print(f"  source:        {args.source}")
    print(f"  mode:          {args.mode}")
    print(f"  openspec_init: {args.openspec_init}")
    print(f"  skip_commands: {args.skip_commands}")
    if not prompt_bool("确认开始初始化", default=True):
        raise SystemExit("已取消初始化。")
    print("")
    return args


def prompt_text(title: str, default: str) -> str:
    value = input(f"{title} [{default}]: ").strip()
    return value or default


def prompt_bool(title: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{title} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "true", "1", "是")


def prompt_choice(title: str, choices: list[str], default: str, labels: dict[str, str]) -> str:
    print(title)
    for index, choice in enumerate(choices, start=1):
        marker = " 默认" if choice == default else ""
        print(f"  {index}. {labels.get(choice, choice)} ({choice}){marker}")
    while True:
        value = input(f"请选择 [默认 {default}]: ").strip()
        if not value:
            return default
        if value in choices:
            return value
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value) - 1]
        print("输入无效，请重新选择。")


def skill_target(kind: str) -> Path:
    if kind == "codex":
        base = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    elif kind == "claude":
        base = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
    else:
        raise ValueError(kind)
    return base / "skills" / "super-engineer-workflow"


def install_skill(target: Path, force: bool) -> None:
    if not SKILL_DIR.exists():
        raise SystemExit(f"skill 目录不存在：{SKILL_DIR}")
    if target.exists() and force:
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_DIR, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"installed_skill={target}")


def ensure_global_skill_config() -> None:
    config_dir = Path("~/.super-engineer").expanduser()
    config_file = config_dir / "skill-config.yml"
    if config_file.exists():
        print(f"skill_config=exists:{config_file}")
        return
    config_dir.mkdir(parents=True, exist_ok=True)
    source = SKILL_DIR / "assets" / "config.example.yml"
    if source.exists():
        shutil.copyfile(source, config_file)
    else:
        config_file.write_text("version: 1\nnotification: {}\n", encoding="utf-8")
    print(f"skill_config=created:{config_file}")


def init_workspace(
    workspace: Path,
    code_path: str,
    demand_name: str,
    source: str,
    mode: str,
    openspec_init: bool,
    install_target: str,
    skip_commands: bool,
) -> None:
    (workspace / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
    (workspace / "openspec" / "specs").mkdir(parents=True, exist_ok=True)
    demand_dir = workspace / "superengineer" / demand_name
    demand_dir.mkdir(parents=True, exist_ok=True)

    demand_file = demand_dir / "需求.md"
    if not demand_file.exists():
        demand_file.write_text(
            "# 需求说明\n\n"
            "## 背景\n\n"
            "请在这里描述业务背景。\n\n"
            "## 目标\n\n"
            "请在这里描述本次需求目标。\n\n"
            "## 验收标准\n\n"
            "- [ ] 补充验收标准。\n",
            encoding="utf-8",
        )

    workspace_yml = workspace / "workspace.yml"
    if not workspace_yml.exists():
        workspace_yml.write_text(
            build_workspace_yml(
                code_path=code_path,
                demand_name=demand_name,
                source=source,
                mode=mode,
            ),
            encoding="utf-8",
        )
        print(f"workspace_yml=created:{workspace_yml}")
    else:
        print(f"workspace_yml=exists:{workspace_yml}")

    if openspec_init:
        try_init_openspec(workspace)
    if not skip_commands:
        install_workspace_commands(workspace)
        if install_target in ("codex", "both"):
            install_codex_prompts()


def should_init_openspec(source: str, openspec_init: bool, skip_openspec_init: bool) -> bool:
    if skip_openspec_init:
        return False
    return source == "openspec" or openspec_init


def build_workspace_yml(code_path: str, demand_name: str, source: str, mode: str) -> str:
    if source == "todo":
        return (
            "version: 1\n"
            f"mode: {mode}\n"
            "workflow_source: todo\n"
            "vars:\n"
            f"  demand_name: {demand_name}\n"
            "todo_file: superengineer/${demand_name}/todo.md\n"
            "reference_files:\n"
            "  - docs/需求分析与实现指南.md\n"
            f"code_path: {code_path}\n"
            "output_dir: superengineer/${demand_name}/output\n"
        )
    return (
        "version: 1\n"
        f"mode: {mode}\n"
        "workflow_source: openspec\n"
        "vars:\n"
        f"  demand_name: {demand_name}\n"
        "demand_file: superengineer/${demand_name}/需求.md\n"
        "todo_file: superengineer/${demand_name}/todo.md\n"
        "reference_files:\n"
        "  - docs/需求分析与实现指南.md\n"
        f"code_path: {code_path}\n"
        "output_dir: superengineer/${demand_name}/output\n"
        "openspec:\n"
        "  changes_dir: openspec/changes\n"
    )


def try_init_openspec(workspace: Path) -> None:
    if not shutil.which("openspec"):
        print("openspec_init=skipped:openspec CLI not found")
        return
    if openspec_initialized(workspace):
        print("openspec_init=skipped:already initialized")
        return
    result = subprocess.run(
        ["openspec", "init", ".", "--tools", "codex,claude"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout.strip())
    print(f"openspec_init={'ok' if result.returncode == 0 else 'failed'}")


def openspec_initialized(workspace: Path) -> bool:
    markers = [
        workspace / "openspec" / "config.yaml",
        workspace / ".claude" / "commands" / "opsx" / "propose.md",
        workspace / ".codex" / "skills" / "openspec-propose" / "SKILL.md",
    ]
    return any(path.exists() for path in markers)


SE_COMMANDS: dict[str, str] = {
    "propose.md": """---
description: Super Engineer：生成或完善 OpenSpec change
argument-hint: <change-name>
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

本命令接收到的 OpenSpec change 名称参数是：`$ARGUMENTS`。

如果 `$ARGUMENTS` 为空，先不要执行 `/se:propose`，请直接询问用户：

```text
请提供 OpenSpec change 名称，例如：demand-to-venus-api。
```

如果 `$ARGUMENTS` 不为空，请执行：

```text
python3 ~/.claude/skills/super-engineer-workflow/scripts/run-workflow.py route-se --command-text "/se:propose $ARGUMENTS"
```

请根据当前 workspace 的 demand_file 生成或完善 OpenSpec change。
本命令只能生成或完善 OpenSpec change 文档，严禁执行 /se:bridge，严禁生成或修改 todo.md。
不要改代码。
过程中请使用中文。
""",
    "propose-fix.md": """---
description: Super Engineer：需求补充后修正当前 OpenSpec change
argument-hint: <change-name>
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

本命令接收到的 OpenSpec change 名称参数是：`$ARGUMENTS`。

如果 `$ARGUMENTS` 为空，先不要执行 `/se:propose`，请直接询问用户：

```text
请提供要修正的 OpenSpec change 名称，例如：demand-to-venus-api。
```

如果 `$ARGUMENTS` 不为空，请执行：

```text
/se:propose $ARGUMENTS
```

当前需求有补充，请基于修改后的 demand_file 修正当前 OpenSpec change。
不要创建新的 change。
不要改代码。
过程中请使用中文。
""",
    "bridge.md": """---
description: Super Engineer：生成桥接 todo
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

请执行：

```text
python3 ~/.claude/skills/super-engineer-workflow/scripts/run-workflow.py route-se --command-text "/se:bridge"
```

针对当前 OpenSpec change 生成桥接 todo，并总结待审核项。
不要改代码，不要进入实现。
过程中请使用中文。
""",
    "plan.md": """---
description: Super Engineer：只生成实施计划
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

/se:plan

基于已审核的 todo.md 生成计划。
先不要改代码，只总结目标仓库、影响范围、验收标准和主要风险。
过程中请使用中文。
""",
    "apply.md": """---
description: Super Engineer：审核 todo 后进入交付阶段
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

/se:apply

我已审核当前桥接 todo，可以进入交付阶段。
使用当前工作空间。
如果没有硬阻塞，自动推进到实现、自查、审查和验证。
过程中请使用中文。
""",
    "archive-check.md": """---
description: Super Engineer：检查 OpenSpec 归档条件
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

/se:archive-check

检查当前 OpenSpec change 是否满足归档条件。
过程中请使用中文。
""",
    "archive.md": """---
description: Super Engineer：归档 OpenSpec change
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

/se:archive

仅在 archive_ready=true、merge_mode=safe_merge、spec_conflicts 为空时执行归档。
过程中请使用中文。
""",
    "status.md": """---
description: Super Engineer：查看当前工作流状态
---

请使用 super-engineer-workflow skill 处理下面的 /se:* 工作流命令。

/se:status

请检查当前工作流状态，并说明当前阶段、允许的下一步和阻塞项。
过程中请使用中文。
""",
}


def install_workspace_commands(workspace: Path) -> None:
    command_dir = workspace / ".claude" / "commands" / "se"
    command_dir.mkdir(parents=True, exist_ok=True)
    for name, content in SE_COMMANDS.items():
        (command_dir / name).write_text(content, encoding="utf-8")
    print(f"claude_commands=created:{command_dir}")


def install_codex_prompts() -> None:
    prompt_dir = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for name, content in SE_COMMANDS.items():
        codex_name = f"se-{name}"
        codex_content = content.replace("~/.claude/skills/", "~/.codex/skills/")
        (prompt_dir / codex_name).write_text(codex_content, encoding="utf-8")
    print(f"codex_prompts=created:{prompt_dir}")


def print_summary(workspace: Path, demand_name: str, source: str, mode: str) -> None:
    print("")
    print("初始化完成。")
    print(f"workspace={workspace}")
    print(f"demand_dir={workspace / 'superengineer' / demand_name}")
    print(f"workflow_source={source}")
    print(f"mode={mode}")
    print("")
    if source == "openspec":
        print("下一步提示词：")
        print(f"/se:propose <change-name>")
        print("请根据当前 workspace 的 demand_file 生成或完善 OpenSpec change。")
        print("不要改代码。过程中请使用中文。")
    else:
        print("下一步提示词：")
        print("/se:apply")
        print("请根据当前 workspace 的 todo_file 推进交付工作流。过程中请使用中文。")


if __name__ == "__main__":
    main()
