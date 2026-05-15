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
    require_se_state,
    report_artifact_path,
    recover_se_state_from_artifacts,
    se_state_path,
    todo_path,
    update_se_state,
    validate_se_state,
    workflow_source,
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
    config = load_workspace_config(workspace)
    recover_se_state_from_artifacts(config)
    try:
        status, _ = load_status(workspace)
    except FileNotFoundError:
        print("尚未创建当前会话，请先执行 plan。")
        status = {}
    if not status:
        print("尚未生成 status.json，请先执行 plan。")
    else:
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
    state = read_json(se_state_path(config), {})
    if state:
        print(f"se_phase={state.get('phase', '')}")
        print(f"se_allowed_next={','.join(str(item) for item in state.get('allowed_next', []))}")


def command_validate_state(workspace: Path | None, command: str | None) -> None:
    if not command:
        raise SystemExit("缺少要校验的命令，例如 validate-state plan。")
    config = load_workspace_config(workspace)
    result = validate_se_state(config, command)
    print(f"valid={str(bool(result.get('valid'))).lower()}")
    print(f"phase={result.get('phase', '')}")
    print(f"allowed_next={','.join(str(item) for item in result.get('allowed_next', []))}")
    for error in result.get("errors", []):
        print(f"error={error}")
    if not result.get("valid"):
        raise SystemExit(1)


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


def command_bootstrap_openspec(workspace: Path | None) -> None:
    require_se_state(load_workspace_config(workspace), "bootstrap-openspec")
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("bootstrap-openspec.py", args)


def command_propose_openspec(workspace: Path | None, change_name: str | None = None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    if change_name:
        args.append(change_name)
    run_python("propose-openspec.py", args)


def command_writeback_openspec(workspace: Path | None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("writeback-openspec.py", args)


def command_prepare_archive_openspec(workspace: Path | None) -> None:
    require_se_state(load_workspace_config(workspace), "prepare-archive-openspec")
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("prepare-archive-openspec.py", args)


def command_archive_openspec(workspace: Path | None) -> None:
    require_se_state(load_workspace_config(workspace), "archive-openspec")
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("archive-openspec.py", args)


def command_plan(workspace: Path | None) -> None:
    config = load_workspace_config(workspace)
    require_se_state(config, "plan")
    command_init(workspace)
    config = load_workspace_config(workspace)
    create_session(config)
    command_discover(workspace)
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-smart-plan.py", args)
    update_se_state(
        config,
        phase="planned",
        last_command="/se:plan",
        artifacts={
            "todo": str(todo_path(config)),
            "plan_json": str(data_artifact_path(config, "plan.json")),
            "plan_md": str(report_artifact_path(config, "plan.md")),
        },
    )


def command_discover(workspace: Path | None) -> None:
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-discovery.py", args)


def command_start_implement(workspace: Path | None) -> None:
    config = load_workspace_config(workspace)
    require_se_state(config, "start-implement")
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
    update_se_state(config, phase="implementing", last_command="/se:apply")


def command_finish_implement(workspace: Path | None) -> None:
    config = load_workspace_config(workspace)
    require_se_state(config, "finish-implement")
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-self-check.py", args)
    update_se_state(
        config,
        phase="self_checked",
        last_command="/se:apply",
        artifacts={
            "self_check_json": str(data_artifact_path(config, "self-check.json")),
            "self_check_md": str(report_artifact_path(config, "self-check.md")),
        },
    )
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
    config = load_workspace_config(workspace)
    require_se_state(config, "review")
    args = ["--workspace", str(workspace)] if workspace else []
    run_python("generate-review-report.py", args)
    update_se_state(
        config,
        phase="reviewed",
        last_command="/se:review",
        artifacts={
            "review_json": str(data_artifact_path(config, "review.json")),
            "review_md": str(report_artifact_path(config, "review.md")),
        },
    )
    if workflow_source(config) == "openspec":
        run_python("writeback-openspec.py", args)


def command_verify(workspace: Path | None, timeout_seconds: int, force: bool = False) -> None:
    config = load_workspace_config(workspace)
    require_se_state(config, "verify")
    args = ["--timeout-seconds", str(timeout_seconds)]
    if force:
        args.append("--force")
    if workspace:
        args.extend(["--workspace", str(workspace)])
    run_python("run-verify-and-report.py", args)
    verify_result = read_json(data_artifact_path(config, "verify.json"), {})
    result_text = str(verify_result.get("result", "")).strip()
    update_se_state(
        config,
        phase="verified" if result_text == "通过" else "blocked",
        last_command="/se:verify",
        artifacts={
            "verify_json": str(data_artifact_path(config, "verify.json")),
            "verify_md": str(report_artifact_path(config, "verify.md")),
            "notification_json": str(data_artifact_path(config, "notification.json")),
        },
        blocked_reason="" if result_text == "通过" else result_text or "验证未通过",
    )
    if workflow_source(config) == "openspec":
        run_python("writeback-openspec.py", ["--workspace", str(workspace)] if workspace else [])


def main() -> None:
    parser = argparse.ArgumentParser(description="super-engineer 统一工作流入口。")
    parser.add_argument("command", choices=["init", "propose-openspec", "bootstrap-openspec", "writeback-openspec", "prepare-archive-openspec", "archive-openspec", "discover", "plan", "start-implement", "finish-implement", "self-check", "review", "verify", "status", "next", "validate-state"])
    parser.add_argument("change_name", nargs="?", help="配合 propose-openspec 或 validate-state 使用。")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--force", action="store_true", help="配合 verify 使用，强制重跑验证并覆盖结果。")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser() if args.workspace else None

    if args.command == "init":
        command_init(workspace)
    elif args.command == "propose-openspec":
        command_propose_openspec(workspace, args.change_name)
    elif args.command == "bootstrap-openspec":
        command_bootstrap_openspec(workspace)
    elif args.command == "writeback-openspec":
        command_writeback_openspec(workspace)
    elif args.command == "prepare-archive-openspec":
        command_prepare_archive_openspec(workspace)
    elif args.command == "archive-openspec":
        command_archive_openspec(workspace)
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
    elif args.command == "validate-state":
        command_validate_state(workspace, args.change_name)


if __name__ == "__main__":
    main()
