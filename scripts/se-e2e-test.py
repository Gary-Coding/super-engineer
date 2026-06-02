#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_WORKFLOW = REPO_ROOT / "super-engineer-workflow" / "scripts" / "run-workflow.py"
CLI = REPO_ROOT / "bin" / "super-engineer.js"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="se-e2e-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        os.environ["HOME"] = str(home)
        os.environ["USERPROFILE"] = str(home)
        test_templates_cli(root)
        test_openspec_state_and_bridge(root)
        test_todo_auto_session_and_verify_compaction(root)
    print("e2e_test=ok")


def test_templates_cli(root: Path) -> None:
    workspace = root / "template-workspace"
    output = run(["node", str(CLI), "templates"])
    if "openspec-auto" not in output or "todo-auto" not in output:
        raise AssertionError("templates list did not include expected templates")

    show_output = run(["node", str(CLI), "template", "show", "openspec-auto"])
    if "workflow_source: openspec" not in show_output or "mode: auto" not in show_output:
        raise AssertionError("template show returned unexpected content")

    run(
        [
            "node",
            str(CLI),
            "template",
            "copy",
            "todo-auto",
            "--workspace",
            str(workspace),
            "--demand-name",
            "9-e2e-template",
            "--code-path",
            "../code",
        ]
    )
    workspace_yml = read_text(workspace / "workspace.yml")
    if "workflow_source: todo" not in workspace_yml or "9-e2e-template" not in workspace_yml:
        raise AssertionError("template copy did not render workspace.yml")


def test_openspec_state_and_bridge(root: Path) -> None:
    workspace = root / "openspec-workspace"
    code = root / "code" / "demo-service"
    demand_dir = workspace / "superengineer" / "8-demo"
    demand_dir.mkdir(parents=True)
    code.mkdir(parents=True)
    (workspace / "docs").mkdir(parents=True)
    (workspace / "openspec" / "changes").mkdir(parents=True)
    (workspace / "openspec" / "specs").mkdir(parents=True)
    (demand_dir / "需求.md").write_text(
        "# 需求\n\n为 demo-service 增加状态查询接口。\n\n## 验收\n\n- 查询接口返回 ok。\n",
        encoding="utf-8",
    )
    (workspace / "workspace.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "mode: auto",
                "workflow_source: openspec",
                "vars:",
                "  demand_name: 8-demo",
                "demand_file: superengineer/${demand_name}/需求.md",
                "todo_file: superengineer/${demand_name}/todo.md",
                "reference_files: []",
                "code_path: ../code/demo-service",
                "output_dir: superengineer/${demand_name}/output",
                "openspec:",
                "  changes_dir: openspec/changes",
                "",
            ]
        ),
        encoding="utf-8",
    )

    invalid = run(
        [
            sys.executable,
            str(RUN_WORKFLOW),
            "route-se",
            "--workspace",
            str(workspace),
            "--command-text",
            "/se:bridge",
        ],
        check=False,
    )
    if invalid.returncode == 0 or "请先执行 /se:propose" not in invalid.output:
        raise AssertionError("/se:bridge before /se:propose should be rejected")

    env_without_openspec = os.environ.copy()
    env_without_openspec["PATH"] = ""
    propose = run(
        [
            sys.executable,
            str(RUN_WORKFLOW),
            "route-se",
            "--workspace",
            str(workspace),
            "--command-text",
            "/se:propose demo-change",
        ],
        env=env_without_openspec,
    )
    if "final_reply_must=代码未修改。下一步只能执行 /se:bridge。" not in propose:
        raise AssertionError("/se:propose did not print strict next-step constraint")

    change_dir = workspace / "openspec" / "changes" / "demo-change"
    (change_dir / "specs").mkdir(parents=True, exist_ok=True)
    (change_dir / "proposal.md").write_text("# Proposal\n\n增加状态查询接口。\n", encoding="utf-8")
    (change_dir / "design.md").write_text("# Design\n\n目标服务 demo-service。\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] 修改 demo-service controller 增加状态查询接口\n"
        "- [ ] 补充验证，确认接口返回 ok\n",
        encoding="utf-8",
    )

    bridge = run(
        [
            sys.executable,
            str(RUN_WORKFLOW),
            "route-se",
            "--workspace",
            str(workspace),
            "--command-text",
            "/se:bridge",
        ]
    )
    if "bridge_generated=true" not in bridge:
        raise AssertionError("/se:bridge did not generate todo.md")
    todo = read_text(workspace / "superengineer" / "8-demo" / "todo.md")
    if "demo-change" not in todo or "demo-service" not in todo:
        raise AssertionError("bridged todo.md missing expected OpenSpec context")


def test_todo_auto_session_and_verify_compaction(root: Path) -> None:
    workspace = root / "todo-workspace"
    code = root / "todo-code" / "demo-service"
    demand_dir = workspace / "superengineer" / "9-demo"
    demand_dir.mkdir(parents=True)
    code.mkdir(parents=True)
    (workspace / "docs").mkdir(parents=True)
    (code / "verify.py").write_text(
        "print('A' * 13000)\n"
        "import sys\n"
        "print('B' * 13000, file=sys.stderr)\n",
        encoding="utf-8",
    )
    (code / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-service",
                "version": "1.0.0",
                "scripts": {"test": "node -e \"process.exit(0)\""},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    verify_command = f'"{sys.executable}" verify.py'
    (workspace / "workspace.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "mode: auto",
                "workflow_source: todo",
                "vars:",
                "  demand_name: 9-demo",
                "todo_file: superengineer/${demand_name}/todo.md",
                "reference_files: []",
                "code_path: ../todo-code/demo-service",
                "output_dir: superengineer/${demand_name}/output",
                "verify_commands:",
                f"  default: {verify_command}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (demand_dir / "todo.md").write_text(
        "# 限制条件\n"
        "- 修改的服务是 demo-service\n\n"
        "# 待办事项\n\n"
        "- [ ] 增加状态查询接口\n"
        "1. 返回 ok\n\n"
        "## 验收补充\n"
        "- [ ] 执行验证命令\n",
        encoding="utf-8",
    )

    apply_output = run(
        [
            sys.executable,
            str(RUN_WORKFLOW),
            "route-se",
            "--workspace",
            str(workspace),
            "--command-text",
            "/se:apply",
        ]
    )
    if "apply_phase=implementing" not in apply_output:
        raise AssertionError("/se:apply did not enter implementing phase")

    run([sys.executable, str(RUN_WORKFLOW), "finish-implement", "--workspace", str(workspace)])
    session = read_json(workspace / ".super-engineer" / "current-session.json")
    data_dir = Path(session["data_dir"])
    plan_summary = read_json(data_dir / "plan-summary.json")
    verify = read_json(data_dir / "verify.json")
    status = read_json(data_dir / "status.json")
    notification = read_json(data_dir / "notification.json")

    if not plan_summary.get("target_codebases"):
        raise AssertionError("plan-summary.json missing target_codebases")
    if verify.get("result") != "通过":
        raise AssertionError("verify did not pass")
    stdout = verify["sections"][0]["stdout"]
    stderr = verify["sections"][0]["stderr"]
    if "已省略" not in stdout or "已省略" not in stderr:
        raise AssertionError("verify stdout/stderr were not compacted")
    if len(stdout) > 12200 or len(stderr) > 12200:
        raise AssertionError("verify stdout/stderr compaction exceeded expected size")
    if status.get("phase") != "done":
        raise AssertionError("todo auto session did not finish with done status")
    if notification.get("status") != "skipped":
        raise AssertionError("notification should be marked skipped when no provider is configured")


def run(command: list[str], check: bool = True, env: dict[str, str] | None = None):
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check:
        if result.returncode != 0:
            print(result.stdout)
            raise SystemExit(result.returncode)
        return result.stdout
    return CommandResult(result.returncode, result.stdout)


class CommandResult:
    def __init__(self, returncode: int, output: str) -> None:
        self.returncode = returncode
        self.output = output


def read_text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise AssertionError(f"missing file: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise AssertionError(f"json root is not object: {path}")
    return data


if __name__ == "__main__":
    if shutil.which("node") is None:
        raise SystemExit("node is required")
    main()
