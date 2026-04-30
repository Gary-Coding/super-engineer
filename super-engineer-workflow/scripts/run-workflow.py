#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import (
    create_session,
    current_session_meta,
    data_artifact_path,
    ensure_status,
    load_workspace_config,
    now_iso,
    planned_codebases,
    planned_codebase,
    read_json,
    write_json,
    workspace_root,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def run_python(script_name: str, extra_args: list[str]) -> None:
    script_path = SCRIPT_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path), *extra_args],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_status(workspace: Path | None) -> tuple[dict, Path]:
    config = load_workspace_config(workspace)
    session_meta = current_session_meta(config)
    status_path = data_artifact_path(config, "status.json", session_meta)
    status = ensure_status(config, session_meta, read_json(status_path, {}))
    return status, status_path


def update_status_for_implement(workspace: Path | None, current_task: str, next_action: str, phase: str, progress: int, completed_task: str | None = None) -> None:
    config = load_workspace_config(workspace)
    session_meta = current_session_meta(config)
    status_path = data_artifact_path(config, "status.json", session_meta)
    status = ensure_status(config, session_meta, read_json(status_path, {}))
    completed_tasks = status.get("completed_tasks", [])
    if completed_task and completed_task not in completed_tasks:
        completed_tasks = completed_tasks + [completed_task]
    status.update(
        {
            "phase": phase,
            "current_task": current_task,
            "progress": progress,
            "awaiting_confirmation": phase.startswith("wait_confirm_"),
            "pending_confirmation_for": "review" if phase == "wait_confirm_implement" else "",
            "next_action": next_action,
            "completed_tasks": completed_tasks,
            "blocked_tasks": status.get("blocked_tasks", []),
            "started_at": status.get("started_at") or session_meta.get("started_at", ""),
            "updated_at": now_iso(),
        }
    )
    write_json(status_path, status)


def command_status(workspace: Path | None) -> None:
    try:
        status, _ = load_status(workspace)
    except FileNotFoundError:
        print("尚未创建当前会话，请先执行 plan。")
        return
    if not status:
        print("尚未生成 status.json，请先执行 plan。")
        return
    for key in (
        "session_id",
        "mode",
        "phase",
        "current_task",
        "progress",
        "awaiting_confirmation",
        "pending_confirmation_for",
        "next_action",
        "started_at",
        "finished_at",
        "duration_seconds",
        "notification_status",
        "notification_message",
        ):
        print(f"{key}={status.get(key, '')}")


def command_next(workspace: Path | None, timeout_seconds: int) -> None:
    config = load_workspace_config(workspace)
    session_meta = current_session_meta(config)
    status = read_json(data_artifact_path(config, "status.json", session_meta), {})
    phase = status.get("phase", "")

    if phase in ("wait_confirm_plan", "plan"):
        command_start_implement(workspace)
        return
    if phase == "implement":
        command_finish_implement(workspace)
        return
    if phase == "self_check":
        command_review(workspace)
        return
    if phase in ("wait_confirm_implement", "review"):
        command_review(workspace)
        return
    if phase == "wait_confirm_review":
        command_verify(workspace, timeout_seconds)
        return
    print(f"当前阶段无需 next：{phase}")


def command_init(workspace: Path | None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("init-workspace.py", args)


def command_plan(workspace: Path | None) -> None:
    command_init(workspace)
    config = load_workspace_config(workspace)
    create_session(config)
    command_discover(workspace)
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-smart-plan.py", args)


def command_discover(workspace: Path | None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-discovery.py", args)


def command_start_implement(workspace: Path | None) -> None:
    config = load_workspace_config(workspace)
    session_meta = current_session_meta(config)
    codebases = planned_codebases(config, session_meta)
    codebase = planned_codebase(config, session_meta)
    if len(codebases) == 1:
        current_task = f"正在实现代码修改：{codebase}"
    else:
        current_task = "正在实现多仓库代码修改：" + "、".join(str(item) for item in codebases)
    update_status_for_implement(
        workspace,
        current_task=current_task,
        next_action="按 plan.json 完成代码修改，完成后执行 finish-implement。",
        phase="implement",
        progress=45,
    )


def command_finish_implement(workspace: Path | None) -> None:
    config = load_workspace_config(workspace)
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-self-check.py", args)
    if config["mode"] == "manual":
        update_status_for_implement(
            workspace,
            current_task="实现阶段已完成。",
            next_action="等待确认后执行代码审查。",
            phase="wait_confirm_implement",
            progress=60,
            completed_task="已完成代码实现",
        )
        return

    update_status_for_implement(
        workspace,
        current_task="实现阶段已完成。",
        next_action="继续执行代码审查和验证。",
        phase="review",
        progress=60,
        completed_task="已完成代码实现",
    )
    command_review(workspace)
    command_verify(workspace, 300)


def command_review(workspace: Path | None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-review-report.py", args)


def command_verify(workspace: Path | None, timeout_seconds: int, force: bool = False) -> None:
    args = ["--timeout-seconds", str(timeout_seconds)]
    if force:
        args.append("--force")
    if workspace:
        args.extend(["--workspace", str(workspace)])
    run_python("run-verify-and-report.py", args)


def main() -> None:
    parser = argparse.ArgumentParser(description="super-engineer 统一工作流入口。")
    parser.add_argument("command", choices=["init", "discover", "plan", "start-implement", "finish-implement", "self-check", "review", "verify", "status", "next"])
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--force", action="store_true", help="配合 verify 使用，强制重跑验证并覆盖结果。")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser() if args.workspace else None

    if args.command == "init":
        command_init(workspace)
    elif args.command == "discover":
        command_discover(workspace)
    elif args.command == "plan":
        command_plan(workspace)
    elif args.command == "start-implement":
        command_start_implement(workspace)
    elif args.command == "finish-implement":
        command_finish_implement(workspace)
    elif args.command == "self-check":
        run_python("generate-self-check.py", ["--workspace", str(workspace)] if workspace else [])
    elif args.command == "review":
        command_review(workspace)
    elif args.command == "verify":
        command_verify(workspace, args.timeout_seconds, args.force)
    elif args.command == "status":
        command_status(workspace)
    elif args.command == "next":
        command_next(workspace, args.timeout_seconds)


if __name__ == "__main__":
    main()
