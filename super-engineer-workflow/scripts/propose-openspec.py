#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    demand_path,
    load_workspace_config,
    openspec_change_dir,
    openspec_change_name,
    openspec_cli_available,
    openspec_writeback_dir,
    read_text,
    run_openspec_cli,
    workflow_source,
    workspace_root,
    write_json,
    write_text,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSpec-native propose preparation for current workspace.")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    args = parser.parse_args()

    workspace = workspace_root(Path(args.workspace).expanduser() if args.workspace else None)
    config = load_workspace_config(workspace)
    if workflow_source(config) != "openspec":
        raise SystemExit("当前 workspace.yml 未启用 OpenSpec 模式，无法执行 propose-openspec。")

    change_name = openspec_change_name(config)
    change_dir = openspec_change_dir(config)
    writeback_dir = openspec_writeback_dir(config)
    demand_file = demand_path(config)
    demand_text = read_text(demand_file) if demand_file else ""

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

    payload = {
        "change_name": change_name,
        "change_dir": str(change_dir),
        "demand_file": str(demand_file) if demand_file else "",
        "demand_text": demand_text,
        "openspec_cli_available": openspec_cli_available(),
        "commands": commands,
        "next_action": "Use demand_text and OpenSpec instructions to create or update proposal.md, design.md, tasks.md, and specs/.",
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
            ]
        ),
    )
    print(f"change_name={change_name}")
    print(f"change_dir={change_dir}")
    print(f"demand_file={demand_file or ''}")
    print(f"openspec_cli_available={str(openspec_cli_available()).lower()}")
    print(f"propose_input={writeback_dir / 'propose-input.json'}")


if __name__ == "__main__":
    main()
