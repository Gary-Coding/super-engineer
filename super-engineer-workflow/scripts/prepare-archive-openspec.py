#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    file_sha256,
    load_workspace_config,
    openspec_change_dir,
    openspec_writeback_dir,
    read_json,
    workflow_source,
    workspace_root,
    write_json,
    write_text,
)


def detect_spec_conflicts(summary: dict) -> list[dict[str, object]]:
    bridge_context = summary.get("bridge_context", {})
    conflicts: list[dict[str, object]] = []
    for item in bridge_context.get("spec_merge_targets", []):
        target = Path(str(item.get("target", "")))
        baseline = str(item.get("target_sha256", ""))
        current = file_sha256(target)
        target_exists = bool(item.get("target_exists", False))
        if not target_exists and target.exists():
            conflicts.append(
                {
                    "relative_path": str(item.get("relative_path", "")),
                    "reason": "计划阶段目标 spec 不存在，但归档前已出现同路径文件",
                    "target": str(target),
                }
            )
        elif target_exists and baseline and current and baseline != current:
            conflicts.append(
                {
                    "relative_path": str(item.get("relative_path", "")),
                    "reason": "目标 spec 自计划阶段以来已发生变化",
                    "target": str(target),
                }
            )
    return conflicts


def build_markdown(payload: dict) -> str:
    blockers = payload.get("blockers", [])
    lines = [
        "# Archive Input",
        "",
        "## Summary",
        f"- change: {payload.get('change_name', '')}",
        f"- archive_ready: {payload.get('archive_ready', False)}",
        "",
        "## Blockers",
    ]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "## Spec Impacts",
    ])
    impacts = payload.get("spec_impacts", [])
    if impacts:
        lines.extend(f"- {item}" for item in impacts)
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "## Acceptance",
    ])
    acceptance = payload.get("acceptance_result", [])
    if acceptance:
        lines.extend(f"- {item.get('task_title', '')}: {item.get('status', '')}" for item in acceptance)
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "## Merge Mode",
        f"- {payload.get('merge_mode', '')}",
        "",
        "## Conflicts",
    ])
    conflicts = payload.get("spec_conflicts", [])
    if conflicts:
        lines.extend(f"- {item.get('relative_path', '')}: {item.get('reason', '')}" for item in conflicts)
    else:
        lines.append("- 暂无")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="根据 OpenSpec 回写结果生成 archive 输入。")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    args = parser.parse_args()

    workspace = workspace_root(Path(args.workspace).expanduser() if args.workspace else None)
    config = load_workspace_config(workspace)
    if workflow_source(config) != "openspec":
        raise SystemExit("当前 workspace.yml 未启用 OpenSpec 模式，无需执行 prepare-archive-openspec。")

    writeback_dir = openspec_writeback_dir(config)
    summary = read_json(writeback_dir / "execution-summary.json", {})
    if not summary:
        raise SystemExit(f"未找到 execution-summary.json：{writeback_dir / 'execution-summary.json'}")

    blockers = list(summary.get("archive_blockers", []))
    acceptance_result = summary.get("acceptance_result", [])
    if any(item.get("status") != "passed" for item in acceptance_result):
        blockers.append("存在未通过的验收项")
    spec_conflicts = detect_spec_conflicts(summary)
    if spec_conflicts:
        blockers.append("存在 spec merge 冲突，请先人工处理")
    merge_mode = "safe_merge" if not spec_conflicts else "manual_merge_required"

    payload = {
        "change_name": summary.get("change_name", ""),
        "change_dir": str(openspec_change_dir(config)),
        "archive_ready": not blockers and bool(summary.get("archive_ready")),
        "blockers": blockers,
        "review_result": summary.get("review", {}).get("result", ""),
        "verify_result": summary.get("verify", {}).get("result", ""),
        "spec_impacts": summary.get("spec_impacts", []),
        "spec_conflicts": spec_conflicts,
        "merge_mode": merge_mode,
        "acceptance_result": acceptance_result,
        "residual_risks": summary.get("residual_risks", []),
        "reports": summary.get("reports", {}),
    }
    write_json(writeback_dir / "archive-input.json", payload)
    write_text(writeback_dir / "merge-preview.md", build_markdown(payload))
    print(f"archive_ready={str(payload['archive_ready']).lower()}")
    print(f"writeback_dir={writeback_dir}")


if __name__ == "__main__":
    main()
