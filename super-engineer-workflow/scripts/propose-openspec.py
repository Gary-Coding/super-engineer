#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    demand_path,
    existing_reference_files,
    load_workspace_config,
    openspec_change_dir,
    openspec_change_name,
    openspec_cli_available,
    openspec_writeback_dir,
    read_text,
    run_openspec_cli,
    select_openspec_change,
    update_se_state,
    validate_openspec_change_name,
    workflow_source,
    workspace_root,
    write_active_openspec_change,
    write_json,
    write_text,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSpec-native propose preparation for current workspace.")
    parser.add_argument("change_name", nargs="?", help="OpenSpec change 名称，例如 demand-addition-rate")
    parser.add_argument("--change", dest="change_name_option", help="OpenSpec change 名称，例如 demand-addition-rate")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    args = parser.parse_args()

    workspace = workspace_root(Path(args.workspace).expanduser() if args.workspace else None)
    config = load_workspace_config(workspace)
    if workflow_source(config) != "openspec":
        raise SystemExit("当前 workspace.yml 未启用 OpenSpec 模式，无法执行 propose-openspec。")

    explicit_change_name = args.change_name_option or args.change_name
    if not explicit_change_name:
        raise SystemExit("缺少 OpenSpec change 名称。请使用 /se:propose <change-name> 显式指定。")
    explicit_change_name = validate_openspec_change_name(explicit_change_name)
    config = select_openspec_change(config, explicit_change_name)
    change_name = openspec_change_name(config)
    change_dir = openspec_change_dir(config)
    writeback_dir = openspec_writeback_dir(config)
    demand_file = demand_path(config)
    demand_text = read_text(demand_file) if demand_file else ""
    reference_contexts = [
        {
            "path": item,
            "content": read_text(Path(item)),
        }
        for item in existing_reference_files(config)
    ]

    commands: list[dict] = []
    if openspec_cli_available():
        if not change_dir.exists():
            commands.append(run_openspec_cli(config, ["new", "change", change_name]))
        commands.append(run_openspec_cli(config, ["status", "--change", change_name, "--json"]))
        status_json = commands[-1].get("json") or {}
        artifacts = status_json.get("artifacts", []) if isinstance(status_json, dict) else []
        for artifact in artifacts:
            artifact_id = str(artifact.get("id") or artifact.get("artifact") or artifact.get("name") or "").strip()
            if artifact_id:
                commands.append(run_openspec_cli(config, ["instructions", artifact_id, "--change", change_name, "--json"]))
    else:
        change_dir.mkdir(parents=True, exist_ok=True)
        (change_dir / "specs").mkdir(parents=True, exist_ok=True)
        commands.append(
            {
                "available": False,
                "args": [],
                "returncode": None,
                "stdout": "",
                "stderr": "openspec CLI not found in PATH; created change directory only",
                "json": None,
            }
        )

    active_change_file = write_active_openspec_change(config, change_name)
    payload = {
        "change_name": change_name,
        "change_dir": str(change_dir),
        "active_change_file": str(active_change_file),
        "demand_file": str(demand_file) if demand_file else "",
        "demand_text": demand_text,
        "reference_files": reference_contexts,
        "openspec_cli_available": openspec_cli_available(),
        "commands": commands,
        "next_action": "Use demand_text, reference_files, and OpenSpec instructions to create or update proposal.md, design.md, tasks.md, and specs/.",
    }
    write_json(writeback_dir / "propose-input.json", payload)
    write_text(
        writeback_dir / "propose-input.md",
        "\n".join(
            [
                "# Propose Input",
                "",
                f"- change: {change_name}",
                f"- change_dir: {change_dir}",
                f"- demand_file: {demand_file or ''}",
                f"- openspec_cli_available: {openspec_cli_available()}",
                "",
                "## Demand",
                "",
                demand_text or "未配置或未找到 demand_file。",
                "",
                "## Reference Files",
                "",
                "\n\n".join(
                    [
                        "\n".join(
                            [
                                f"### {item['path']}",
                                "",
                                item["content"] or "文件为空或无法读取。",
                            ]
                        )
                        for item in reference_contexts
                    ]
                )
                or "未配置或未找到 reference_files。",
                "",
            ]
        ),
    )
    update_se_state(
        config,
        phase="proposed",
        last_command="/se:propose",
        artifacts={
            "proposal": str(change_dir / "proposal.md"),
            "design": str(change_dir / "design.md"),
            "tasks": str(change_dir / "tasks.md"),
            "change_dir": str(change_dir),
            "propose_input": str(writeback_dir / "propose-input.json"),
        },
    )
    print(f"change_name={change_name}")
    print(f"change_dir={change_dir}")
    print(f"active_change_file={active_change_file}")
    print(f"demand_file={demand_file or ''}")
    print(f"reference_files={len(reference_contexts)}")
    print(f"openspec_cli_available={str(openspec_cli_available()).lower()}")
    print(f"propose_input={writeback_dir / 'propose-input.json'}")


if __name__ == "__main__":
    main()
