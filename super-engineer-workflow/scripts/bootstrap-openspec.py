#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ensure_workflow_inputs, load_workspace_config, todo_path, update_se_state, workflow_source, workspace_root


def main() -> None:
    parser = argparse.ArgumentParser(description="根据 OpenSpec change/tasks 生成桥接 todo 文件。")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    args = parser.parse_args()

    workspace = workspace_root(Path(args.workspace).expanduser() if args.workspace else None)
    config = load_workspace_config(workspace)
    if workflow_source(config) != "openspec":
        raise SystemExit("当前 workspace.yml 未启用 OpenSpec 模式，无需执行 bootstrap-openspec。")
    result = ensure_workflow_inputs(config, allow_bridge_write=True)
    update_se_state(
        config,
        phase="bridged",
        last_command="/se:bridge",
        artifacts={
            "todo": str(todo_path(config)),
            "bridge_source": str(result.get("bridge_source", "")),
        },
    )
    print(f"workflow_source={result.get('workflow_source', '')}")
    print(f"todo={todo_path(config)}")
    print(f"bridge_generated={'true' if result.get('bridge_generated') else 'false'}")
    print(f"bridge_source={result.get('bridge_source', '')}")


if __name__ == "__main__":
    main()
