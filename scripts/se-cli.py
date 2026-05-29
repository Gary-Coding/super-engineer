#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "super-engineer-workflow"
PACKAGE_JSON = REPO_ROOT / "package.json"


def main() -> None:
    if len(sys.argv) == 1:
        run_setup([])
        return
    if sys.argv[1] in ("init", "setup"):
        run_setup(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(
        prog="se",
        description="Super Engineer workflow CLI.",
    )
    parser.add_argument("--version", action="store_true", help="显示版本号。")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="交互式安装 skill 并初始化工作区。")
    subparsers.add_parser("setup", help="init 的别名。")

    install_parser = subparsers.add_parser("install", help="安装 skill 到 Codex / Claude。")
    install_parser.add_argument("--target", choices=["codex", "claude", "both"], default="both")
    install_parser.add_argument("--force", action="store_true", help="安装前删除旧 skill 目录。")

    sync_parser = subparsers.add_parser("sync", help="重新同步 skill 到 Codex / Claude。")
    sync_parser.add_argument("--target", choices=["codex", "claude", "both"], default="both")

    doctor_parser = subparsers.add_parser("doctor", help="检查本机环境和工作区配置。")
    doctor_parser.add_argument("--workspace", default=".", help="工作区目录，默认当前目录。")
    doctor_parser.add_argument("--json", action="store_true", help="输出 JSON。")

    migrate_parser = subparsers.add_parser("migrate", help="补齐旧工作区缺失的 workspace.yml 配置项。")
    migrate_parser.add_argument("--workspace", default=".", help="工作区目录，默认当前目录。")
    migrate_parser.add_argument("--dry-run", action="store_true", help="只展示计划，不写入文件。")

    subparsers.add_parser("version", help="显示版本号。")

    args = parser.parse_args()
    if args.version or args.command == "version":
        print(package_version())
        return
    if args.command == "install":
        install_targets(args.target, force=args.force)
        return
    if args.command == "sync":
        install_targets(args.target, force=True)
        return
    if args.command == "doctor":
        exit_code = doctor(Path(args.workspace).expanduser().resolve(), output_json=args.json)
        raise SystemExit(exit_code)
    if args.command == "migrate":
        exit_code = migrate(Path(args.workspace).expanduser().resolve(), dry_run=args.dry_run)
        raise SystemExit(exit_code)

    parser.print_help()


def package_version() -> str:
    if not PACKAGE_JSON.exists():
        return "0.0.0"
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    return str(data.get("version", "0.0.0"))


def run_setup(args: list[str]) -> None:
    script = REPO_ROOT / "scripts" / "se-setup.py"
    result = subprocess.run([sys.executable, str(script), *args], check=False)
    raise SystemExit(result.returncode)


def install_targets(target: str, force: bool) -> None:
    targets = []
    if target in ("codex", "both"):
        targets.append(skill_target("codex"))
    if target in ("claude", "both"):
        targets.append(skill_target("claude"))
    for item in targets:
        install_skill(item, force=force)


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
    shutil.copytree(
        SKILL_DIR,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    print(f"✓ 已同步 skill: {target}")


def doctor(workspace: Path, output_json: bool) -> int:
    checks: list[dict[str, str]] = []
    add_check(checks, "python", "ok", sys.version.split()[0])
    add_check(checks, "skill_source", "ok" if SKILL_DIR.exists() else "fail", str(SKILL_DIR))
    add_check(checks, "codex_skill", "ok" if skill_target("codex").exists() else "warn", str(skill_target("codex")))
    add_check(checks, "claude_skill", "ok" if skill_target("claude").exists() else "warn", str(skill_target("claude")))
    add_check(checks, "openspec_cli", "ok" if shutil.which("openspec") else "warn", shutil.which("openspec") or "未安装")
    add_check(checks, "workspace", "ok" if workspace.exists() else "fail", str(workspace))

    workspace_yml = workspace / "workspace.yml"
    add_check(checks, "workspace_yml", "ok" if workspace_yml.exists() else "fail", str(workspace_yml))
    if workspace_yml.exists():
        try:
            config = read_workspace_yaml(workspace_yml)
        except ValueError as exc:
            add_check(checks, "workspace_yml.parse", "fail", str(exc))
        else:
            add_check(checks, "workspace_yml.parse", "ok", "解析成功")
            validate_workspace(checks, workspace, config)

    if output_json:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    else:
        print("Super Engineer doctor")
        for check in checks:
            mark = {"ok": "✓", "warn": "!", "fail": "✗"}[check["status"]]
            print(f"{mark} {check['name']}: {check['message']}")

    return 1 if any(item["status"] == "fail" for item in checks) else 0


def add_check(checks: list[dict[str, str]], name: str, status: str, message: str) -> None:
    checks.append({"name": name, "status": status, "message": message})


def read_workspace_yaml(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError("workspace.yml 顶层必须是对象")
        return loaded

    common_path = SKILL_DIR / "scripts" / "common.py"
    spec = importlib.util.spec_from_file_location("se_common_for_cli", common_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载 YAML 解析器：{common_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loaded = module.parse_simple_yaml(text)
    if not isinstance(loaded, dict):
        raise ValueError("workspace.yml 顶层必须是对象")
    return loaded


def config_get(config: dict[str, object], key: str, default: object = None) -> object:
    current: object = config
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def config_str(config: dict[str, object], key: str, default: str = "") -> str:
    value = config_get(config, key, default)
    if value is None:
        return default
    return str(value)


def validate_workspace(checks: list[dict[str, str]], workspace: Path, config: dict[str, object]) -> None:
    for key in ("workflow_source", "mode", "code_path", "output_dir"):
        value = config_str(config, key)
        add_check(checks, f"config.{key}", "ok" if value else "fail", value or "缺失")

    version = config_get(config, "version")
    add_check(checks, "config.version", "ok" if version == 1 else "fail", str(version or "缺失"))

    references = config_get(config, "reference_files")
    add_check(checks, "config.reference_files", "ok" if isinstance(references, list) else "fail", "list" if isinstance(references, list) else "缺失或非数组")

    source = config_str(config, "workflow_source")
    if source not in ("openspec", "todo"):
        add_check(checks, "config.workflow_source.value", "fail", source or "缺失")

    mode = config_str(config, "mode")
    if mode not in ("auto", "manual"):
        add_check(checks, "config.mode.value", "fail", mode or "缺失")

    code_path = config_str(config, "code_path")
    if code_path:
        resolved = resolve_workspace_path(workspace, code_path)
        add_check(checks, "code_path.exists", "ok" if resolved.exists() else "warn", str(resolved))

    demand_file = config_str(config, "demand_file")
    if source == "openspec":
        add_check(checks, "config.demand_file", "ok" if demand_file else "fail", demand_file or "缺失")
        if demand_file:
            resolved = resolve_workspace_path(workspace, expand_vars(demand_file, config))
            add_check(checks, "demand_file.exists", "ok" if resolved.exists() else "warn", str(resolved))
        changes_dir = config_str(config, "openspec.changes_dir", "openspec/changes")
        resolved_changes = resolve_workspace_path(workspace, changes_dir)
        add_check(checks, "openspec.changes_dir", "ok" if resolved_changes.exists() else "warn", str(resolved_changes))

    todo_file = config_str(config, "todo_file")
    add_check(checks, "config.todo_file", "ok" if todo_file else "fail", todo_file or "缺失")
    if todo_file:
        resolved = resolve_workspace_path(workspace, expand_vars(todo_file, config))
        status = "ok" if resolved.exists() else ("warn" if source == "openspec" else "fail")
        add_check(checks, "todo_file.exists", status, str(resolved))


def expand_vars(value: str, config: dict[str, object]) -> str:
    demand_name = config_str(config, "vars.demand_name")
    return value.replace("${demand_name}", demand_name)


def resolve_workspace_path(workspace: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (workspace / path).resolve()


def migrate(workspace: Path, dry_run: bool) -> int:
    workspace_yml = workspace / "workspace.yml"
    if not workspace_yml.exists():
        print(f"✗ workspace.yml 不存在：{workspace_yml}")
        return 1

    try:
        config = read_workspace_yaml(workspace_yml)
    except ValueError as exc:
        print(f"✗ workspace.yml 无法解析：{exc}")
        return 1

    additions = default_missing_lines(config)
    if not additions:
        print("✓ workspace.yml 已是当前版本，无需迁移。")
        return 0

    print("将补齐以下配置：")
    for line in additions:
        print(f"  {line}")

    if dry_run:
        return 0

    with workspace_yml.open("a", encoding="utf-8") as handle:
        handle.write("\n# Added by super-engineer migrate\n")
        for line in additions:
            handle.write(f"{line}\n")
    print(f"✓ 已迁移：{workspace_yml}")
    return 0


def default_missing_lines(config: dict[str, object]) -> list[str]:
    additions: list[str] = []
    if config_get(config, "version") is None:
        additions.append("version: 1")
    if not config_str(config, "mode"):
        additions.append("mode: manual")
    if not config_str(config, "workflow_source"):
        additions.append("workflow_source: todo")
    if config_get(config, "reference_files") is None:
        additions.extend(["reference_files:", "  - docs/项目介绍.md"])
    if not config_str(config, "code_path"):
        additions.append("code_path: ../your-project")
    if not config_str(config, "output_dir"):
        additions.append("output_dir: output")
    return additions


if __name__ == "__main__":
    main()
