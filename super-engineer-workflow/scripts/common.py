#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_duration(seconds: float) -> str:
    safe_seconds = max(0.0, float(seconds))
    if safe_seconds < 60:
        return f"{safe_seconds:.2f} 秒"
    total_seconds = int(round(safe_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} 小时")
    if minutes:
        parts.append(f"{minutes} 分")
    if secs or not parts:
        parts.append(f"{secs} 秒")
    return "".join(parts)


def parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped in ("", "null", "~"):
        return ""
    if stripped == "[]":
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        parts: list[str] = []
        current = ""
        quote = ""
        for char in inner:
            if char in ("'", '"'):
                if not quote:
                    quote = char
                elif quote == char:
                    quote = ""
                current += char
                continue
            if char == "," and not quote:
                parts.append(current.strip())
                current = ""
                continue
            current += char
        if current.strip():
            parts.append(current.strip())
        return [parse_scalar(part) for part in parts]
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        return stripped[1:-1]
    return stripped


def _tokenize_yaml(text: str) -> list[tuple[int, str]]:
    tokens: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        tokens.append((indent, raw_line.strip()))
    return tokens


def _parse_yaml_block(tokens: list[tuple[int, str]], index: int, indent: int) -> tuple[int, Any]:
    container: Any = None

    while index < len(tokens):
        current_indent, content = tokens[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"YAML 缩进不合法：{content}")

        if content.startswith("- "):
            if container is None:
                container = []
            if not isinstance(container, list):
                raise ValueError("YAML 不能在同一层混用对象和数组。")
            value_part = content[2:].strip()
            if value_part:
                container.append(parse_scalar(value_part))
                index += 1
                continue
            index, nested = _parse_yaml_block(tokens, index + 1, indent + 2)
            container.append(nested)
            continue

        if container is None:
            container = {}
        if not isinstance(container, dict):
            raise ValueError("YAML 不能在同一层混用数组和对象。")

        key, sep, value_part = content.partition(":")
        if not sep:
            raise ValueError(f"YAML 行缺少冒号：{content}")
        key = key.strip()
        value_part = value_part.strip()
        if value_part:
            container[key] = parse_scalar(value_part)
            index += 1
            continue
        index, nested = _parse_yaml_block(tokens, index + 1, indent + 2)
        container[key] = nested

    if container is None:
        return index, {}
    return index, container


def parse_simple_yaml(text: str) -> dict[str, Any]:
    tokens = _tokenize_yaml(text)
    if not tokens:
        return {}
    _, parsed = _parse_yaml_block(tokens, 0, tokens[0][0])
    if not isinstance(parsed, dict):
        raise ValueError("工作空间配置必须是对象结构。")
    return parsed


def _stringify_workspace_vars(raw_vars: Any) -> dict[str, str]:
    if raw_vars in ("", None):
        return {}
    if not isinstance(raw_vars, dict):
        raise ValueError("workspace.yml 中的 vars 必须是对象。")
    variables: dict[str, str] = {}
    for key, value in raw_vars.items():
        key_text = str(key).strip()
        if not key_text:
            raise ValueError("workspace.yml 中的 vars 不能包含空 key。")
        if isinstance(value, (dict, list)):
            raise ValueError(f"workspace.yml 中的 vars.{key_text} 必须是标量值。")
        variables[key_text] = str(value)
    return variables


def _expand_workspace_value(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name.startswith("vars."):
                name = name[5:]
            if name not in variables:
                raise ValueError(f"workspace.yml 中引用了未定义变量：{match.group(1)}")
            return variables[name]

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}", replace, value)
    if isinstance(value, list):
        return [_expand_workspace_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _expand_workspace_value(item, variables) for key, item in value.items()}
    return value


def expand_workspace_variables(config: dict[str, Any], root: Path) -> dict[str, Any]:
    user_vars = _stringify_workspace_vars(config.get("vars", {}))
    variables = {
        "workspace_root": str(root),
        **user_vars,
    }
    expanded = _expand_workspace_value(config, variables)
    if not isinstance(expanded, dict):
        raise ValueError("工作空间配置必须是对象结构。")
    expanded["vars"] = user_vars
    return expanded


def workspace_root(workspace: Path | None = None) -> Path:
    return (workspace or Path.cwd()).expanduser().resolve()


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def user_skill_config_dir() -> Path:
    return Path.home() / ".super-engineer"


def workspace_config_path(workspace: Path | None = None) -> Path:
    root = workspace_root(workspace)
    workspace_yml = root / "workspace.yml"
    if workspace_yml.exists():
        return workspace_yml
    legacy_config = root / "config.yml"
    if legacy_config.exists():
        return legacy_config
    return workspace_yml


def skill_config_path() -> Path:
    return user_skill_config_dir() / "skill-config.yml"


def skill_config_example_path() -> Path:
    return skill_root() / "config.example.yml"


def default_skill_config() -> dict[str, Any]:
    return {
        "version": 1,
        "notification": {
            "pushplus": {
                "token": "",
                "ordinary": {
                    "enabled": False,
                    "channel": "wechat",
                    "template": "markdown",
                },
            },
            "feishu": {
                "enabled": False,
                "webhook_url": "",
                "secret": "",
            },
        },
    }


def default_skill_config_text() -> str:
    return """version: 1
notification:
  pushplus:
    token: ""
    ordinary:
      enabled: false
      channel: wechat
      template: markdown
  feishu:
    enabled: false
    webhook_url: ""
    secret: ""
"""


def ensure_user_skill_config() -> tuple[Path, bool]:
    config_path = skill_config_path()
    if config_path.exists():
        return config_path, False
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(default_skill_config_text(), encoding="utf-8")
    return config_path, True


def load_skill_config() -> dict[str, Any]:
    config_path, created = ensure_user_skill_config()
    config = default_skill_config()
    if config_path.exists():
        loaded = parse_simple_yaml(config_path.read_text(encoding="utf-8"))
        if loaded:
            config.update(loaded)

    if config.get("version") != 1:
        raise ValueError("~/.super-engineer/skill-config.yml 中的 version 必须为 1。")

    notification = config.get("notification", {})
    if notification in ("", None):
        notification = {}
    if not isinstance(notification, dict):
        raise ValueError("~/.super-engineer/skill-config.yml 中的 notification 必须是对象。")

    pushplus = notification.get("pushplus", {})
    if pushplus in ("", None):
        pushplus = {}
    if not isinstance(pushplus, dict):
        raise ValueError("~/.super-engineer/skill-config.yml 中的 notification.pushplus 必须是对象。")

    pushplus_token = str(pushplus.get("token", "")).strip()
    ordinary_raw = pushplus.get("ordinary", {})
    feishu_raw = notification.get("feishu", {})

    if ordinary_raw in ("", None):
        ordinary_raw = {}
    if feishu_raw in ("", None):
        feishu_raw = {}
    if not isinstance(ordinary_raw, dict):
        raise ValueError("~/.super-engineer/skill-config.yml 中的 notification.pushplus.ordinary 必须是对象。")
    if not isinstance(feishu_raw, dict):
        raise ValueError("~/.super-engineer/skill-config.yml 中的 notification.feishu 必须是对象。")

    ordinary_channel = str(ordinary_raw.get("channel", "wechat")).strip() or "wechat"
    ordinary_template = str(ordinary_raw.get("template", "markdown")).strip() or "markdown"
    ordinary_enabled = bool(ordinary_raw.get("enabled", False))

    feishu_enabled = bool(feishu_raw.get("enabled", False))
    feishu_webhook_url = str(feishu_raw.get("webhook_url", "")).strip()
    feishu_secret = str(feishu_raw.get("secret", "")).strip()

    if not ordinary_channel:
        raise ValueError("~/.super-engineer/skill-config.yml 中的 notification.pushplus.ordinary.channel 不能为空。")
    if ordinary_enabled and not pushplus_token:
        raise ValueError("启用 PushPlus 通知时，~/.super-engineer/skill-config.yml 中的 notification.pushplus.token 不能为空。")
    if feishu_enabled and not feishu_webhook_url:
        raise ValueError("启用飞书通知时，~/.super-engineer/skill-config.yml 中的 notification.feishu.webhook_url 不能为空。")
    if feishu_webhook_url and not feishu_webhook_url.startswith("https://open.feishu.cn/open-apis/bot/v2/hook/"):
        raise ValueError("notification.feishu.webhook_url 必须是飞书自定义机器人的 webhook 地址。")

    config["notification"] = {
        "pushplus": {
            "token": pushplus_token,
            "ordinary": {
                "enabled": ordinary_enabled,
                "channel": ordinary_channel,
                "template": ordinary_template,
            },
        },
        "feishu": {
            "enabled": feishu_enabled,
            "webhook_url": feishu_webhook_url,
            "secret": feishu_secret,
        },
    }
    config["__skill_root"] = str(skill_root())
    config["__skill_config_example_path"] = str(skill_config_example_path())
    config["__skill_config_path"] = str(config_path)
    config["__skill_config_created"] = created
    return config


def load_workspace_config(workspace: Path | None = None) -> dict[str, Any]:
    root = workspace_root(workspace)
    config_path = workspace_config_path(root)
    if not config_path.exists():
        raise FileNotFoundError(f"未找到工作空间配置文件：{config_path}")

    config = expand_workspace_variables(parse_simple_yaml(config_path.read_text(encoding="utf-8")), root)
    config.setdefault("version", 1)
    config.setdefault("mode", "manual")
    config.setdefault("workflow_source", "todo")
    config.setdefault("reference_files", [])

    if config.get("version") != 1:
        raise ValueError("workspace.yml 中的 version 必须为 1。")
    if config.get("mode") not in ("manual", "auto"):
        raise ValueError("workspace.yml 中的 mode 只支持 manual 或 auto。")
    if config.get("workflow_source") not in ("todo", "openspec"):
        raise ValueError("workspace.yml 中的 workflow_source 只支持 todo 或 openspec。")

    todo_file = Path(str(config.get("todo_file", ""))).expanduser()
    if not todo_file.is_absolute():
        raise ValueError("workspace.yml 中的 todo_file 必须是绝对路径。")

    code_path = Path(str(config.get("code_path", ""))).expanduser()
    if not code_path.is_absolute():
        raise ValueError("workspace.yml 中的 code_path 必须是绝对路径。")
    if not code_path.exists():
        raise ValueError(f"workspace.yml 中的 code_path 不存在：{code_path}")

    output_dir = Path(str(config.get("output_dir", ""))).expanduser()
    if not output_dir.is_absolute():
        raise ValueError("workspace.yml 中的 output_dir 必须是绝对路径。")

    reference_files = config.get("reference_files", [])
    if reference_files == {}:
        reference_files = []
    if not isinstance(reference_files, list):
        raise ValueError("workspace.yml 中的 reference_files 必须是数组。")
    normalized_refs: list[str] = []
    for item in reference_files:
        path = Path(str(item)).expanduser()
        if not path.is_absolute():
            raise ValueError("workspace.yml 中的 reference_files 必须全部使用绝对路径。")
        normalized_refs.append(str(path))

    config["todo_file"] = str(todo_file.resolve())
    config["code_path"] = str(code_path.resolve())
    config["output_dir"] = str(output_dir.resolve())
    config["reference_files"] = normalized_refs
    config["workflow_source"] = str(config.get("workflow_source", "todo")).strip() or "todo"

    openspec_raw = config.get("openspec", {})
    if openspec_raw in ("", None):
        openspec_raw = {}
    if not isinstance(openspec_raw, dict):
        raise ValueError("workspace.yml 中的 openspec 必须是对象。")
    openspec: dict[str, Any] = {}
    if config["workflow_source"] == "openspec":
        change_dir = Path(str(openspec_raw.get("change_dir", ""))).expanduser()
        if not change_dir.is_absolute():
            raise ValueError("OpenSpec 模式下，workspace.yml 中的 openspec.change_dir 必须是绝对路径。")
        if not change_dir.exists() or not change_dir.is_dir():
            raise ValueError(f"OpenSpec change_dir 不存在：{change_dir}")
        tasks_file = Path(str(openspec_raw.get("tasks_file", change_dir / "tasks.md"))).expanduser()
        if not tasks_file.is_absolute():
            raise ValueError("OpenSpec 模式下，workspace.yml 中的 openspec.tasks_file 必须是绝对路径。")
        proposal_file = Path(str(openspec_raw.get("proposal_file", change_dir / "proposal.md"))).expanduser()
        design_file = Path(str(openspec_raw.get("design_file", change_dir / "design.md"))).expanduser()
        specs_dir = Path(str(openspec_raw.get("specs_dir", change_dir / "specs"))).expanduser()
        writeback_dir = Path(str(openspec_raw.get("writeback_dir", change_dir / "super-engineer"))).expanduser()
        openspec = {
            "change_dir": str(change_dir.resolve()),
            "tasks_file": str(tasks_file.resolve()),
            "proposal_file": str(proposal_file.resolve()),
            "design_file": str(design_file.resolve()),
            "specs_dir": str(specs_dir.resolve()),
            "writeback_dir": str(writeback_dir.resolve()),
            "change_name": change_dir.name,
        }
    config["openspec"] = openspec

    skill_config = load_skill_config()
    config["notification"] = skill_config.get("notification", {})
    config["__workspace_root"] = str(root)
    config["__config_path"] = str(config_path)
    config["__skill_root"] = str(skill_root())
    config["__skill_config_path"] = str(skill_config_path())
    config["__skill_config_created"] = bool(skill_config.get("__skill_config_created", False))
    config["__skill_config_example_path"] = str(skill_config_example_path())
    return config


def code_root(config: dict[str, Any]) -> Path:
    return Path(str(config["code_path"])).resolve()


def looks_like_project_root(path: Path) -> bool:
    return any(
        (
            (path / ".git").exists(),
            (path / "pom.xml").exists(),
            (path / "mvnw").exists(),
            (path / "build.gradle").exists(),
            (path / "build.gradle.kts").exists(),
            (path / "gradlew").exists(),
            (path / "src" / "main").exists(),
        )
    )


def todo_path(config: dict[str, Any]) -> Path:
    return Path(str(config["todo_file"])).resolve()


def workflow_source(config: dict[str, Any]) -> str:
    return str(config.get("workflow_source", "todo")).strip() or "todo"


def artifacts_dir(config: dict[str, Any]) -> Path:
    return Path(str(config["__workspace_root"])).resolve() / ".super-engineer"


def sessions_dir(config: dict[str, Any]) -> Path:
    return artifacts_dir(config) / "sessions"


def current_session_file(config: dict[str, Any]) -> Path:
    return artifacts_dir(config) / "current-session.json"


def output_dir(config: dict[str, Any]) -> Path:
    return Path(str(config["output_dir"])).resolve()


def session_data_dir(config: dict[str, Any], session_id: str) -> Path:
    return sessions_dir(config) / session_id


def session_report_dir(config: dict[str, Any], session_id: str) -> Path:
    return output_dir(config) / session_id


def _normalize_session_meta(config: dict[str, Any], session_meta: dict[str, Any]) -> dict[str, Any]:
    session_id = str(session_meta.get("session_id", "")).strip()
    if not session_id:
        raise FileNotFoundError("尚未发现当前会话，请先执行 plan 创建新的工作流会话。")
    started_at = (
        str(session_meta.get("started_at", "")).strip()
        or str(session_meta.get("created_at", "")).strip()
        or now_iso()
    )
    return {
        "session_id": session_id,
        "created_at": str(session_meta.get("created_at", "")).strip() or now_iso(),
        "started_at": started_at,
        "workspace": str(workspace_root(Path(str(config["__workspace_root"])))),
        "data_dir": str(session_data_dir(config, session_id)),
        "report_dir": str(session_report_dir(config, session_id)),
    }


def create_session(config: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs(config)
    session_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    started_at = now_iso()
    session_meta = _normalize_session_meta(
        config,
        {
            "session_id": session_id,
            "created_at": started_at,
            "started_at": started_at,
        },
    )
    Path(session_meta["data_dir"]).mkdir(parents=True, exist_ok=True)
    Path(session_meta["report_dir"]).mkdir(parents=True, exist_ok=True)
    write_json(current_session_file(config), session_meta)
    return session_meta


def current_session_meta(config: dict[str, Any]) -> dict[str, Any]:
    session_meta = read_json(current_session_file(config), {})
    normalized = _normalize_session_meta(config, session_meta)
    Path(normalized["data_dir"]).mkdir(parents=True, exist_ok=True)
    Path(normalized["report_dir"]).mkdir(parents=True, exist_ok=True)
    return normalized


def data_artifact_path(config: dict[str, Any], name: str, session_meta: dict[str, Any] | None = None) -> Path:
    meta = _normalize_session_meta(config, session_meta or current_session_meta(config))
    return Path(meta["data_dir"]) / name


def report_artifact_path(config: dict[str, Any], name: str, session_meta: dict[str, Any] | None = None) -> Path:
    meta = _normalize_session_meta(config, session_meta or current_session_meta(config))
    return Path(meta["report_dir"]) / name


def artifact_path(config: dict[str, Any], name: str) -> Path:
    return data_artifact_path(config, name)


def ensure_runtime_dirs(config: dict[str, Any]) -> None:
    artifacts_dir(config).mkdir(parents=True, exist_ok=True)
    sessions_dir(config).mkdir(parents=True, exist_ok=True)
    output_dir(config).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def todo_template() -> str:
    return """# 限制条件
- 修改的服务是 your-service-name

# 待办事项

## 模块一：在这里写大需求模块名称
- [ ] 在这里写主任务 1
1. 在这里写子要求 1
2. 在这里写子要求 2

- [ ] 在这里写主任务 2
1. 在这里写子要求 1
2. 在这里写子要求 2

## 模块二：在这里写第二个大需求模块名称
- [ ] 在这里写主任务 3
- [ ] 在这里写主任务 4

## 验收补充
- [ ] 在这里写需要补充的测试、文档或验证要求
"""


def openspec_change_dir(config: dict[str, Any]) -> Path:
    return Path(str(config.get("openspec", {}).get("change_dir", ""))).resolve()


def openspec_tasks_path(config: dict[str, Any]) -> Path:
    return Path(str(config.get("openspec", {}).get("tasks_file", ""))).resolve()


def openspec_reference_files(config: dict[str, Any]) -> list[str]:
    if workflow_source(config) != "openspec":
        return []
    openspec = config.get("openspec", {})
    files: list[str] = []
    for key in ("proposal_file", "design_file"):
        path_text = str(openspec.get(key, "")).strip()
        if not path_text:
            continue
        path = Path(path_text)
        if path.exists() and path.is_file():
            files.append(str(path.resolve()))
    specs_dir_text = str(openspec.get("specs_dir", "")).strip()
    if specs_dir_text:
        specs_dir = Path(specs_dir_text)
        if specs_dir.exists() and specs_dir.is_dir():
            for path in sorted(specs_dir.rglob("*.md")):
                files.append(str(path.resolve()))
    return unique(files)


def openspec_writeback_dir(config: dict[str, Any]) -> Path:
    return Path(str(config.get("openspec", {}).get("writeback_dir", ""))).resolve()


def openspec_archive_root(config: dict[str, Any]) -> Path:
    return openspec_change_dir(config).parent / "archive"


def openspec_bridge_context_path(config: dict[str, Any]) -> Path:
    return artifacts_dir(config) / "openspec-bridge-context.json"


def transform_openspec_tasks_to_todo(tasks_text: str, change_name: str, change_dir: Path) -> str:
    lines = [
        "# 限制条件",
        f"- 需求来源是 OpenSpec change：{change_name}",
        f"- OpenSpec 变更目录是 {change_dir}",
        "- 优先以 proposal.md、design.md 和 specs/ 下的 delta specs 作为业务边界",
        "",
        "# 待办事项",
        "",
    ]
    has_tasks = False
    for raw_line in tasks_text.splitlines():
        stripped = raw_line.rstrip()
        compact = stripped.strip()
        if not compact:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if compact.startswith("#"):
            heading_text = compact.lstrip("#").strip()
            if heading_text.lower() == "tasks":
                continue
            lines.append(f"## {heading_text}")
            has_tasks = True
            continue
        if compact.startswith("- [") or compact.startswith("* ["):
            lines.append(compact.replace("* [", "- [", 1))
            has_tasks = True
            continue
        if compact.startswith("- ") or compact.startswith("* "):
            lines.append("- [ ] " + normalize_todo_text_item(compact))
            has_tasks = True
            continue
        if re.match(r"^\d+\.\s+", compact):
            lines.append(compact)
            has_tasks = True
            continue
        lines.append("- [ ] " + normalize_todo_text_item(compact))
        has_tasks = True
    if not has_tasks:
        lines.extend(
            [
                "## 默认任务",
                "- [ ] OpenSpec tasks.md 中未识别到可执行任务，请先补充任务项",
            ]
        )
    if lines[-1] != "":
        lines.append("")
    return "\n".join(lines)


def build_openspec_bridge_context(config: dict[str, Any], tasks_text: str) -> dict[str, Any]:
    openspec = config.get("openspec", {})
    proposal_file = Path(str(openspec.get("proposal_file", "")))
    design_file = Path(str(openspec.get("design_file", "")))
    proposal_text = read_text(proposal_file) if proposal_file.exists() else ""
    design_text = read_text(design_file) if design_file.exists() else ""
    specs = openspec_reference_files(config)
    change_dir = openspec_change_dir(config)
    repo_openspec_root = change_dir.parent.parent
    delta_specs_dir = Path(str(openspec.get("specs_dir", ""))).expanduser()
    spec_merge_targets: list[dict[str, Any]] = []
    if delta_specs_dir.exists() and delta_specs_dir.is_dir():
        target_specs_root = repo_openspec_root / "specs"
        for source in sorted(delta_specs_dir.rglob("*.md")):
            relative = source.relative_to(delta_specs_dir)
            target = target_specs_root / relative
            spec_merge_targets.append(
                {
                    "delta_source": str(source.resolve()),
                    "target": str(target.resolve()),
                    "relative_path": str(relative),
                    "target_exists": target.exists(),
                    "target_sha256": file_sha256(target),
                }
            )

    def extract_headings(text: str) -> list[str]:
        headings: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
        return headings[:12]

    compatibility_notes: list[str] = []
    for source_text in (proposal_text, design_text, tasks_text):
        for line in source_text.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if any(keyword in lowered for keyword in ("兼容", "rollback", "回滚", "灰度", "mq", "schema", "contract")):
                compatibility_notes.append(stripped)

    acceptance_criteria: list[str] = []
    for line in tasks_text.splitlines():
        stripped = normalize_todo_text_item(line)
        if stripped and ("test" in stripped.lower() or "验证" in stripped or "验收" in stripped):
            acceptance_criteria.append(stripped)

    return {
        "workflow_source": "openspec",
        "change_name": str(openspec.get("change_name", "")),
        "change_dir": str(openspec_change_dir(config)),
        "tasks_file": str(openspec_tasks_path(config)),
        "proposal_file": str(proposal_file.resolve()) if proposal_file.exists() else "",
        "design_file": str(design_file.resolve()) if design_file.exists() else "",
        "spec_reference_files": specs,
        "proposal_headings": extract_headings(proposal_text),
        "design_headings": extract_headings(design_text),
        "business_constraints": [
            f"需求来源是 OpenSpec change：{openspec.get('change_name', '')}",
            "优先以 proposal.md、design.md 和 specs/ 下的 delta specs 作为业务边界",
        ],
        "acceptance_criteria": unique(acceptance_criteria),
        "compatibility_notes": unique(compatibility_notes),
        "spec_merge_targets": spec_merge_targets,
        "updated_at": now_iso(),
    }


def ensure_workflow_inputs(config: dict[str, Any]) -> dict[str, Any]:
    source = workflow_source(config)
    todo_file = todo_path(config)
    result = {
        "workflow_source": source,
        "todo_path": str(todo_file),
        "todo_created": False,
        "todo_needs_edit": False,
        "bridge_generated": False,
        "bridge_source": "",
    }
    if source == "todo":
        if not todo_file.exists():
            write_text(todo_file, todo_template())
            result["todo_created"] = True
        todo_text = read_text(todo_file)
        result["todo_needs_edit"] = is_todo_template_placeholder(todo_text)
        return result

    tasks_file = openspec_tasks_path(config)
    if not tasks_file.exists():
        raise FileNotFoundError(f"OpenSpec tasks 文件不存在：{tasks_file}")
    tasks_text = read_text(tasks_file)
    bridged_todo = transform_openspec_tasks_to_todo(
        tasks_text,
        str(config.get("openspec", {}).get("change_name", tasks_file.parent.name)),
        openspec_change_dir(config),
    )
    existing = read_text(todo_file)
    if existing != bridged_todo:
        write_text(todo_file, bridged_todo)
        result["bridge_generated"] = True
    result["bridge_source"] = str(tasks_file)
    result["todo_needs_edit"] = is_todo_template_placeholder(bridged_todo)
    bridge_context = build_openspec_bridge_context(config, tasks_text)
    write_json(openspec_bridge_context_path(config), bridge_context)
    return result


def is_todo_template_placeholder(todo_text: str) -> bool:
    normalized = todo_text.strip()
    if not normalized:
        return True
    if normalized == todo_template().strip():
        return True
    markers = [
        "your-service-name",
        "在这里写大需求模块名称",
        "在这里写主任务 1",
        "在这里写需要补充的测试、文档或验证要求",
    ]
    return any(marker in normalized for marker in markers)


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return fallback
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def normalize_todo_text_item(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^\d+\.\s*", "", normalized)
    normalized = re.sub(r"^[-*]\s*", "", normalized)
    normalized = re.sub(r"^\[(?: |x|X)\]\s*", "", normalized)
    return normalized.strip()


def parse_todo_document(todo_text: str) -> dict[str, Any]:
    constraints: list[str] = []
    modules: list[dict[str, Any]] = []
    default_module_title = "未分组需求"
    current_section = "__root__"
    current_module: dict[str, Any] | None = None
    current_task: dict[str, Any] | None = None

    def ensure_module(title: str | None = None) -> dict[str, Any]:
        nonlocal current_module, current_task
        if current_module is not None and title is None:
            return current_module
        module_title = (title or default_module_title).strip() or default_module_title
        if current_module and current_module["title"] == module_title:
            return current_module
        current_module = {
            "id": f"module-{len(modules) + 1}",
            "title": module_title,
            "tasks": [],
        }
        modules.append(current_module)
        current_task = None
        return current_module

    for raw_line in todo_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        heading = re.match(r"^(#+)\s*(.+?)\s*$", stripped)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            lowered = title.lower()
            if level == 1:
                current_task = None
                if is_constraint_section(lowered):
                    current_section = "constraints"
                    current_module = None
                elif is_task_section(lowered):
                    current_section = "tasks"
                    current_module = None
                else:
                    current_section = lowered
                    current_module = None
                continue
            if current_section == "tasks":
                ensure_module(title)
                continue

        if current_section == "constraints":
            normalized = normalize_todo_text_item(stripped)
            if normalized:
                constraints.append(normalized)
            continue

        in_task_area = current_section == "tasks" or current_section == "__root__"
        if not in_task_area:
            continue

        checkbox = re.match(r"^[-*]\s+\[( |x|X)\]\s*(.+)$", stripped)
        if checkbox:
            module = ensure_module()
            completed = checkbox.group(1).lower() == "x"
            title = normalize_todo_text_item(checkbox.group(2))
            current_task = {
                "title": title,
                "details": [],
                "completed": completed,
            }
            module["tasks"].append(current_task)
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            module = ensure_module()
            title = normalize_todo_text_item(bullet.group(1))
            current_task = {
                "title": title,
                "details": [],
                "completed": False,
            }
            module["tasks"].append(current_task)
            continue

        detail = normalize_todo_text_item(stripped)
        if not detail:
            continue
        if current_task is None:
            module = ensure_module()
            current_task = {
                "title": detail,
                "details": [],
                "completed": False,
            }
            module["tasks"].append(current_task)
            continue
        current_task["details"].append(detail)

    normalized_modules: list[dict[str, Any]] = []
    task_index = 1
    for module_index, module in enumerate(modules, start=1):
        normalized_tasks: list[dict[str, Any]] = []
        for task in module.get("tasks", []):
            title = str(task.get("title", "")).strip()
            if not title:
                continue
            details = [str(item).strip() for item in task.get("details", []) if str(item).strip()]
            normalized_tasks.append(
                {
                    "id": f"task-{task_index}",
                    "title": title,
                    "details": details,
                    "completed": bool(task.get("completed", False)),
                }
            )
            task_index += 1
        if normalized_tasks:
            normalized_modules.append(
                {
                    "id": f"module-{module_index}",
                    "title": str(module.get("title", default_module_title)).strip() or default_module_title,
                    "tasks": normalized_tasks,
                }
            )

    pending_modules: list[dict[str, Any]] = []
    completed_modules: list[dict[str, Any]] = []
    for module in normalized_modules:
        pending_tasks = [task for task in module["tasks"] if not task["completed"]]
        completed_tasks = [task for task in module["tasks"] if task["completed"]]
        if pending_tasks:
            pending_modules.append(
                {
                    "id": module["id"],
                    "title": module["title"],
                    "tasks": pending_tasks,
                }
            )
        if completed_tasks:
            completed_modules.append(
                {
                    "id": module["id"],
                    "title": module["title"],
                    "tasks": completed_tasks,
                }
            )

    pending_tasks = [task for module in pending_modules for task in module["tasks"]]
    completed_tasks = [task for module in completed_modules for task in module["tasks"]]
    return {
        "constraints": unique(constraints),
        "modules": pending_modules,
        "completed_modules": completed_modules,
        "tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "stats": {
            "pending_task_count": len(pending_tasks),
            "completed_task_count": len(completed_tasks),
            "total_task_count": len(pending_tasks) + len(completed_tasks),
        },
    }


def parse_task_blocks(todo_text: str) -> list[dict[str, Any]]:
    document = parse_todo_document(todo_text)
    return [
        {
            "id": task["id"],
            "title": task["title"],
            "details": task["details"],
        }
        for task in document["tasks"]
    ]


def parse_task_modules(todo_text: str) -> list[dict[str, Any]]:
    document = parse_todo_document(todo_text)
    return [
        {
            "id": module["id"],
            "title": module["title"],
            "tasks": [
                {
                    "id": task["id"],
                    "title": task["title"],
                    "details": task["details"],
                }
                for task in module["tasks"]
            ],
        }
        for module in document["modules"]
    ]


def todo_progress(todo_text: str) -> dict[str, int]:
    document = parse_todo_document(todo_text)
    return {
        "pending_task_count": int(document["stats"]["pending_task_count"]),
        "completed_task_count": int(document["stats"]["completed_task_count"]),
        "total_task_count": int(document["stats"]["total_task_count"]),
    }


def todo_items(todo_text: str) -> list[str]:
    tasks = parse_task_blocks(todo_text)
    items: list[str] = []
    for task in tasks:
        items.append(task["title"])
        items.extend(task.get("details", []))
    return unique(items)


def parse_todo_sections(todo_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"__root__": []}
    current = "__root__"
    for raw_line in todo_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        heading = re.match(r"^#+\s*(.+?)\s*$", stripped)
        if heading:
            current = heading.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(stripped)
    return sections


def is_task_section(title: str) -> bool:
    return any(keyword in title for keyword in ("待办", "todo", "tasks", "task"))


def is_constraint_section(title: str) -> bool:
    return any(keyword in title for keyword in ("限制条件", "约束", "constraints", "constraint"))


def constraint_items(todo_text: str) -> list[str]:
    return parse_todo_document(todo_text)["constraints"]


def service_hints(todo_text: str) -> list[str]:
    hints: list[str] = []
    candidate_lines = constraint_items(todo_text)
    if not candidate_lines:
        candidate_lines = [line.strip() for line in todo_text.splitlines() if line.strip()]
    patterns = [
        r"(?:修改的服务|目标服务|服务名|服务)\s*(?:是|为|:|：)\s*([A-Za-z0-9._-]+)",
        r"(?:修改的服务|目标服务|服务名|服务)\s*(?:包括|包含|有|涉及)\s*([A-Za-z0-9._,\-、，\s]+)",
        r"(?:仓库|项目)\s*(?:是|为|:|：)\s*([A-Za-z0-9._-]+)",
        r"(?:仓库|项目)\s*(?:包括|包含|有|涉及)\s*([A-Za-z0-9._,\-、，\s]+)",
    ]
    for line in candidate_lines:
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in patterns:
            match = re.search(pattern, stripped, flags=re.IGNORECASE)
            if match:
                raw_value = match.group(1).strip()
                for part in re.split(r"[、，,\s]+", raw_value):
                    normalized = part.strip()
                    if normalized:
                        hints.append(normalized)
    return unique(hints)


def summarize_todo(todo_text: str) -> str:
    tasks = parse_task_blocks(todo_text)
    if not tasks:
        return "请在 todo 文件中补充待办需求。"
    return "；".join(task["title"] for task in tasks[:3])


def extract_todo_keywords(todo_text: str, limit: int = 24) -> list[str]:
    keywords: list[str] = []
    candidates = todo_items(todo_text) + constraint_items(todo_text)
    token_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]{2,}|[\u4e00-\u9fff]{2,}")
    stopwords = {
        "todo",
        "task",
        "tasks",
        "null",
        "true",
        "false",
        "修改",
        "增加",
        "新增",
        "需要",
        "接口",
        "字段",
        "测试",
        "服务",
        "模块",
        "待办",
        "限制条件",
    }
    for candidate in candidates:
        for token in token_pattern.findall(str(candidate)):
            normalized = token.strip("`'\"，。、；：:()（）[]【】")
            if len(normalized) < 2:
                continue
            if normalized.lower() in stopwords or normalized in stopwords:
                continue
            keywords.append(normalized)
    return unique(keywords)[:limit]


def relative_to(path: str | Path, root: Path) -> str:
    candidate = Path(str(path)).resolve()
    try:
        return str(candidate.relative_to(root.resolve()))
    except ValueError:
        return str(candidate)


def existing_reference_files(config: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for item in config.get("reference_files", []):
        path = Path(str(item))
        if path.exists():
            files.append(str(path.resolve()))
    files.extend(openspec_reference_files(config))
    return unique(files)


def find_candidate_codebases(root: Path, max_depth: int = 3) -> list[Path]:
    candidates: list[Path] = []
    if looks_like_project_root(root):
        candidates.append(root.resolve())

    def walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted([child for child in path.iterdir() if child.is_dir()])
        except OSError:
            return
        for child in children:
            if child.name.startswith("."):
                continue
            if looks_like_project_root(child):
                candidates.append(child.resolve())
                continue
            walk(child, depth + 1)

    walk(root, 1)
    ordered: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item.resolve())
        if key not in seen:
            seen.add(key)
            ordered.append(item.resolve())
    return ordered


def _match_score(candidate: Path, hint: str) -> int:
    candidate_name = candidate.name.lower()
    candidate_path = str(candidate).lower()
    normalized_hint = hint.strip().lower()
    if not normalized_hint:
        return 0
    if candidate_name == normalized_hint:
        return 100
    if candidate_name.replace("_", "-") == normalized_hint.replace("_", "-"):
        return 95
    if normalized_hint in candidate_name:
        return 85
    if f"/{normalized_hint}/" in candidate_path:
        return 75
    return 0


def resolve_target_codebases(config: dict[str, Any], todo_text: str | None = None) -> tuple[list[Path], dict[str, Any]]:
    root = code_root(config)
    todo_text = todo_text if todo_text is not None else read_text(todo_path(config))
    hints = service_hints(todo_text)

    if looks_like_project_root(root):
        return [root], {
            "configured_code_path": str(root),
            "resolved_code_paths": [str(root)],
            "service_hints": hints,
            "selection_reason": "code_path 本身就是可识别的项目根目录，按单仓模式处理。",
            "candidate_codebases": [str(root)],
        }

    candidates = find_candidate_codebases(root)
    if not candidates:
        raise ValueError(f"code_path 下未找到可识别的项目目录：{root}")

    matched_candidates: list[Path] = []
    matched_pairs: list[dict[str, str]] = []
    for candidate in candidates:
        local_best_hint = ""
        local_best_score = 0
        for hint in hints:
            score = _match_score(candidate, hint)
            if score > local_best_score:
                local_best_score = score
                local_best_hint = hint
        if local_best_score > 0:
            matched_candidates.append(candidate.resolve())
            matched_pairs.append(
                {
                    "service_hint": local_best_hint,
                    "resolved_code_path": str(candidate.resolve()),
                }
            )

    if matched_candidates:
        return matched_candidates, {
            "configured_code_path": str(root),
            "resolved_code_paths": [str(item.resolve()) for item in matched_candidates],
            "service_hints": hints,
            "matched_services": matched_pairs,
            "selection_reason": "根据 todo 中识别到的服务标识，匹配到一个或多个目标项目目录。",
            "candidate_codebases": [str(item) for item in candidates],
        }

    if len(candidates) == 1:
        return [candidates[0].resolve()], {
            "configured_code_path": str(root),
            "resolved_code_paths": [str(candidates[0].resolve())],
            "service_hints": hints,
            "selection_reason": "code_path 下只发现一个可识别的项目目录，已自动使用该目录。",
            "candidate_codebases": [str(item) for item in candidates],
        }

    candidate_names = ", ".join(item.name for item in candidates[:10])
    raise ValueError(
        "code_path 下发现多个项目目录，但无法根据 todo 判断目标服务。"
        f" 请在 todo 中明确写出服务名，例如“修改的服务是 xxx”。候选目录：{candidate_names}"
    )


def resolve_target_codebase(config: dict[str, Any], todo_text: str | None = None) -> tuple[Path, dict[str, Any]]:
    codebases, resolution = resolve_target_codebases(config, todo_text)
    return codebases[0], resolution


def planned_codebases(config: dict[str, Any], session_meta: dict[str, Any] | None = None) -> list[Path]:
    meta = session_meta or current_session_meta(config)
    plan = read_json(data_artifact_path(config, "plan.json", meta), {})
    paths = plan.get("resolved_code_paths", [])
    if isinstance(paths, list) and paths:
        return [Path(str(item)).resolve() for item in paths if str(item).strip()]
    path = str(plan.get("resolved_code_path", "")).strip()
    if path:
        return [Path(path).resolve()]
    return [code_root(config)]


def planned_codebase(config: dict[str, Any], session_meta: dict[str, Any] | None = None) -> Path:
    return planned_codebases(config, session_meta)[0]


def detect_project(codebase: Path) -> dict[str, str]:
    has_maven = (codebase / "pom.xml").exists() or (codebase / "mvnw").exists()
    has_gradle = (
        (codebase / "build.gradle").exists()
        or (codebase / "build.gradle.kts").exists()
        or (codebase / "gradlew").exists()
    )
    has_java = has_maven or has_gradle or (codebase / "src" / "main" / "java").exists()

    language = "java" if has_java else "unknown"
    build_tool = ""
    test_command = ""
    start_command = ""
    verify_command = ""

    if has_maven:
        build_tool = "maven"
        test_command = "./mvnw test" if (codebase / "mvnw").exists() else "mvn test"
        start_command = "./mvnw spring-boot:run" if (codebase / "mvnw").exists() else "mvn spring-boot:run"
        verify_command = test_command
    elif has_gradle:
        build_tool = "gradle"
        test_command = "./gradlew test" if (codebase / "gradlew").exists() else "gradle test"
        start_command = "./gradlew bootRun" if (codebase / "gradlew").exists() else "gradle bootRun"
        verify_command = test_command

    return {
        "language": language,
        "build_tool": build_tool,
        "test_command": test_command,
        "start_command": start_command,
        "verify_command": verify_command,
    }


def summarize_detected_projects(projects: list[dict[str, str]]) -> dict[str, str]:
    if not projects:
        return {
            "language": "",
            "build_tool": "",
            "test_command": "",
            "start_command": "",
            "verify_command": "",
        }

    def summarize_field(name: str) -> str:
        values = unique([item.get(name, "") for item in projects if item.get(name, "")])
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        return "multiple"

    return {
        "language": summarize_field("language"),
        "build_tool": summarize_field("build_tool"),
        "test_command": summarize_field("test_command"),
        "start_command": summarize_field("start_command"),
        "verify_command": summarize_field("verify_command"),
    }


def default_status(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "session_id": "",
        "data_dir": "",
        "report_dir": "",
        "phase": "context",
        "current_task": "等待开始工作流。",
        "progress": 0,
        "awaiting_confirmation": False,
        "pending_confirmation_for": "",
        "next_action": "读取 todo 文件并生成计划。",
        "completed_tasks": [],
        "blocked_tasks": [],
        "started_at": "",
        "finished_at": "",
        "duration_seconds": 0,
        "notification_status": "pending",
        "notification_message": "",
        "updated_at": now_iso(),
    }


def ensure_status(config: dict[str, Any], session_meta: dict[str, Any], status: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = default_status(config["mode"])
    if status:
        merged.update(status)
    merged["mode"] = config["mode"]
    merged["session_id"] = session_meta["session_id"]
    merged["data_dir"] = session_meta["data_dir"]
    merged["report_dir"] = session_meta["report_dir"]
    merged["started_at"] = (
        str(merged.get("started_at", "")).strip()
        or str(session_meta.get("started_at", "")).strip()
        or str(session_meta.get("created_at", "")).strip()
        or now_iso()
    )
    merged["finished_at"] = str(merged.get("finished_at", "")).strip()
    try:
        merged["duration_seconds"] = float(merged.get("duration_seconds", 0) or 0)
    except (TypeError, ValueError):
        merged["duration_seconds"] = 0.0
    merged["notification_status"] = str(merged.get("notification_status", "pending") or "pending")
    merged["notification_message"] = str(merged.get("notification_message", "") or "")
    return merged


def workflow_duration_seconds(
    session_meta: dict[str, Any],
    status: dict[str, Any] | None = None,
    finished_at: str | None = None,
) -> float:
    start_text = (
        str((status or {}).get("started_at", "")).strip()
        or str(session_meta.get("started_at", "")).strip()
        or str(session_meta.get("created_at", "")).strip()
    )
    end_text = str(finished_at or (status or {}).get("finished_at", "")).strip() or now_iso()
    started = parse_iso_datetime(start_text)
    ended = parse_iso_datetime(end_text)
    if started is None or ended is None:
        return 0.0
    return max(0.0, (ended - started).total_seconds())


def pushplus_config(config: dict[str, Any]) -> dict[str, Any]:
    notification = config.get("notification", {})
    if not isinstance(notification, dict):
        return {
            "token": "",
            "routes": [],
        }
    pushplus = notification.get("pushplus", {})
    if not isinstance(pushplus, dict):
        return {
            "token": "",
            "routes": [],
        }

    ordinary = pushplus.get("ordinary", {})
    if not isinstance(ordinary, dict):
        ordinary = {}
    return {
        "token": str(pushplus.get("token", "")).strip(),
        "routes": [
            {
                "name": "ordinary",
                "enabled": bool(ordinary.get("enabled", False)),
                "channel": str(ordinary.get("channel", "wechat")).strip() or "wechat",
                "template": str(ordinary.get("template", "markdown")).strip() or "markdown",
            },
        ],
    }


def feishu_config(config: dict[str, Any]) -> dict[str, Any]:
    notification = config.get("notification", {})
    if not isinstance(notification, dict):
        return {
            "enabled": False,
            "webhook_url": "",
            "secret": "",
        }
    feishu = notification.get("feishu", {})
    if not isinstance(feishu, dict):
        return {
            "enabled": False,
            "webhook_url": "",
            "secret": "",
        }
    return {
        "enabled": bool(feishu.get("enabled", False)),
        "webhook_url": str(feishu.get("webhook_url", "")).strip(),
        "secret": str(feishu.get("secret", "")).strip(),
    }


def pushplus_api_url() -> str:
    return str(os.environ.get("SUPER_ENGINEER_PUSHPLUS_URL", "https://www.pushplus.plus/send")).strip()


def pushplus_request_url(token: str) -> str:
    base = pushplus_api_url().rstrip("/")
    return f"{base}/{token}" if token else base


def _normalize_pushplus_response(status_code: int, body: str, route: dict[str, Any], sender: str) -> dict[str, Any]:
    try:
        response_payload = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        response_payload = {"raw": body}
    response_code = response_payload.get("code")
    success = status_code == 200 and response_code in (None, 0, 200, "0", "200")
    return {
        "route": route.get("name", ""),
        "channel": route.get("channel", ""),
        "template": route.get("template", ""),
        "sender": sender,
        "status": "sent" if success else "failed",
        "success": success,
        "message": str(response_payload.get("msg") or ("发送成功" if success else "发送失败")),
        "response": response_payload,
    }


def send_pushplus_notification_python(payload: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    request = urllib_request.Request(
        pushplus_api_url(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = getattr(response, "status", 200)
    except urllib_error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        result = _normalize_pushplus_response(error.code, body, route, "python")
        result["message"] = str(result.get("message") or f"PushPlus HTTP {error.code}")
        return result
    except urllib_error.URLError as error:
        return {
            "route": route.get("name", ""),
            "channel": route.get("channel", ""),
            "template": route.get("template", ""),
            "sender": "python",
            "status": "failed",
            "success": False,
            "message": f"PushPlus 请求失败：{error.reason}",
            "response": {},
        }
    return _normalize_pushplus_response(status_code, body, route, "python")


def send_pushplus_notification_curl(payload: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if not curl_path:
        return {
            "route": route.get("name", ""),
            "channel": route.get("channel", ""),
            "template": route.get("template", ""),
            "sender": "curl",
            "status": "failed",
            "success": False,
            "message": "系统中未找到 curl，无法执行回退发送。",
            "response": {},
        }
    result = subprocess.run(
        [
            curl_path,
            "-sS",
            pushplus_api_url(),
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload, ensure_ascii=False),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        return {
            "route": route.get("name", ""),
            "channel": route.get("channel", ""),
            "template": route.get("template", ""),
            "sender": "curl",
            "status": "failed",
            "success": False,
            "message": f"curl 回退发送失败：{result.stderr.strip() or result.stdout.strip() or result.returncode}",
            "response": {},
        }
    return _normalize_pushplus_response(200, result.stdout, route, "curl")


def send_pushplus_notification(pushplus: dict[str, Any], route: dict[str, Any], title: str, content: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token": str(pushplus.get("token", "")).strip(),
        "title": title,
        "content": content,
        "template": route.get("template", "markdown"),
        "channel": route.get("channel", "wechat"),
    }
    python_result = send_pushplus_notification_python(payload, route)
    if python_result.get("success"):
        return python_result
    curl_result = send_pushplus_notification_curl(payload, route)
    if curl_result.get("success"):
        curl_result["message"] = f"{curl_result.get('message', '')}（Python失败后已回退curl成功）"
        curl_result["python_error"] = python_result.get("message", "")
        return curl_result
    curl_result["python_error"] = python_result.get("message", "")
    curl_result["message"] = (
        f"Python发送失败：{python_result.get('message', '')}；"
        f"curl回退也失败：{curl_result.get('message', '')}"
    )
    return curl_result


def _normalize_feishu_response(status_code: int, body: str, sender: str) -> dict[str, Any]:
    try:
        response_payload = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        response_payload = {"raw": body}
    response_code = response_payload.get("code")
    success = status_code == 200 and response_code in (None, 0, "0")
    return {
        "route": "feishu",
        "channel": "webhook",
        "template": "interactive",
        "sender": sender,
        "status": "sent" if success else "failed",
        "success": success,
        "message": str(response_payload.get("msg") or ("success" if success else "发送失败")),
        "response": response_payload,
    }


def feishu_sign(secret: str, timestamp: str) -> str:
    key = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(key, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _workflow_notification_title(session_id: str, overall_result: str) -> str:
    return "super-engineer-workflow任务通知"


def _workflow_notification_status_text(status: dict[str, Any], overall_result: str) -> str:
    current_task = str(status.get("current_task", "") or "暂无").strip()
    next_action = str(status.get("next_action", "") or "工作流已完成，请前往工作区查看。").strip()
    if overall_result == "通过":
        current_task = current_task.replace("✅", "").replace("❌", "").rstrip("。")
        return f"{current_task} ✅。{next_action}"
    current_task = current_task.replace("✅", "").replace("❌", "").rstrip("。")
    return f"{current_task} ❌。{next_action}"


def workflow_notification_fingerprint(
    session_meta: dict[str, Any],
    status: dict[str, Any],
    overall_result: str,
) -> str:
    finished_at = str(status.get("finished_at", "") or "").strip()
    phase = str(status.get("phase", "") or "").strip()
    current_task = str(status.get("current_task", "") or "").strip()
    return "|".join(
        [
            str(session_meta.get("session_id", "")).strip(),
            overall_result.strip(),
            finished_at,
            phase,
            current_task,
        ]
    )


def build_workflow_notification(
    config: dict[str, Any],
    session_meta: dict[str, Any],
    plan: dict[str, Any],
    status: dict[str, Any],
    overall_result: str,
    template: str = "markdown",
) -> tuple[str, str]:
    duration_seconds = workflow_duration_seconds(session_meta, status, status.get("finished_at", ""))
    progress = plan.get("todo_progress", {})
    targets = [str(item.get("name", "")).strip() for item in plan.get("target_codebases", []) if str(item.get("name", "")).strip()]
    target_text = "、".join(targets) if targets else "未识别"
    title = _workflow_notification_title(session_meta["session_id"], overall_result)
    current_task = _workflow_notification_status_text(status, overall_result)
    phase_text = str(status.get("phase", "") or "unknown").strip()
    mode_text = str(config.get("mode", "manual")).strip()
    completed_count = progress.get("completed_task_count", 0)
    total_count = progress.get("total_task_count", 0)
    pending_count = progress.get("pending_task_count", 0)

    if template == "html":
        lines = [
            "<div style=\"font-size:14px;line-height:1.7;\">",
            "<h2 style=\"margin:0 0 8px 0;font-size:16px;\">任务摘要</h2>",
            "<ul style=\"margin:0 0 16px 18px;padding:0;\">",
            f"<li>会话：<code>{session_meta['session_id']}</code></li>",
            f"<li>仓库：{target_text}</li>",
            f"<li>模式：<code>{mode_text}</code></li>",
            f"<li>耗时：{format_duration(duration_seconds)}</li>",
            f"<li>进度：{completed_count}/{total_count} 已完成，剩余 {pending_count}</li>",
            "</ul>",
            "<h2 style=\"margin:0 0 8px 0;font-size:16px;\">任务结果</h2>",
            "<ul style=\"margin:0 0 0 18px;padding:0;\">",
            f"<li>当前阶段：<code>{phase_text}</code></li>",
            f"<li>当前说明：{current_task}</li>",
            f"<li>下一步：{next_action}</li>",
            "</ul>",
            "</div>",
        ]
        return title, "".join(lines)

    if template == "txt":
        lines = [
            "【任务摘要】",
            f"会话：{session_meta['session_id']}",
            f"仓库：{target_text}",
            f"模式：{mode_text}｜耗时：{format_duration(duration_seconds)}",
            f"进度：{completed_count}/{total_count} 已完成，剩余 {pending_count}",
            "",
            "【任务结果】",
            f"阶段：{phase_text}",
            f"说明：{current_task or '暂无'}",
        ]
        return title, "\n".join(lines)

    lines = [
        "## 任务摘要",
        "",
        f"会话：`{session_meta['session_id']}`  ",
        f"仓库：{target_text}  ",
        f"模式：`{mode_text}`｜耗时：{format_duration(duration_seconds)}  ",
        f"进度：{completed_count}/{total_count} 已完成，剩余 {pending_count}",
        "",
        "## 任务结果",
        "",
        f"阶段：`{phase_text}`  ",
        f"说明：{current_task or '暂无'}",
    ]
    return title, "\n".join(lines)


def build_feishu_notification_payload(
    config: dict[str, Any],
    session_meta: dict[str, Any],
    plan: dict[str, Any],
    status: dict[str, Any],
    overall_result: str,
    title: str,
) -> dict[str, Any]:
    duration_seconds = workflow_duration_seconds(session_meta, status, status.get("finished_at", ""))
    progress = plan.get("todo_progress", {})
    targets = [str(item.get("name", "")).strip() for item in plan.get("target_codebases", []) if str(item.get("name", "")).strip()]
    target_text = "、".join(targets) if targets else "未识别"
    current_task = _workflow_notification_status_text(status, overall_result)
    phase_text = str(status.get("phase", "") or "unknown").strip()
    mode_text = str(config.get("mode", "manual")).strip()
    completed_count = progress.get("completed_task_count", 0)
    total_count = progress.get("total_task_count", 0)
    pending_count = progress.get("pending_task_count", 0)
    status_emoji = "✅" if overall_result == "通过" else "❌"
    header_template = "green" if overall_result == "通过" else "red"
    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "config": {
                "update_multi": True,
                "style": {
                    "text_size": {
                        "normal_v2": {
                            "default": "normal",
                            "pc": "normal",
                            "mobile": "heading",
                        }
                    }
                },
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": header_template,
                "padding": "12px 12px 12px 12px",
            },
            "body": {
                "direction": "vertical",
                "padding": "12px 12px 12px 12px",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": (
                            "**任务摘要**\n"
                            f"- 会话：`{session_meta['session_id']}`\n"
                            f"- 仓库：{target_text}\n"
                            f"- 模式：`{mode_text}`\n"
                            f"- 耗时：{format_duration(duration_seconds)}\n"
                            f"- 进度：{completed_count}/{total_count} 已完成，剩余 {pending_count}"
                        ),
                        "text_align": "left",
                        "text_size": "normal_v2",
                    },
                    {
                        "tag": "markdown",
                        "content": (
                            "**任务结果**\n"
                            f"- 阶段：`{phase_text}`\n"
                            f"- 说明：{current_task or '暂无'}"
                        ),
                        "text_align": "left",
                        "text_size": "normal_v2",
                    },
                ],
            },
        },
    }


def send_feishu_notification_python(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib_request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = getattr(response, "status", 200)
    except urllib_error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        result = _normalize_feishu_response(error.code, body, "python")
        result["message"] = str(result.get("message") or f"飞书 HTTP {error.code}")
        return result
    except urllib_error.URLError as error:
        return {
            "route": "feishu",
            "channel": "webhook",
            "template": "interactive",
            "sender": "python",
            "status": "failed",
            "success": False,
            "message": f"飞书 webhook 请求失败：{error.reason}",
            "response": {},
        }
    return _normalize_feishu_response(status_code, body, "python")


def send_feishu_notification_curl(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if not curl_path:
        return {
            "route": "feishu",
            "channel": "webhook",
            "template": "interactive",
            "sender": "curl",
            "status": "failed",
            "success": False,
            "message": "系统中未找到 curl，无法执行飞书回退发送。",
            "response": {},
        }
    result = subprocess.run(
        [
            curl_path,
            "-sS",
            webhook_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload, ensure_ascii=False),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        return {
            "route": "feishu",
            "channel": "webhook",
            "template": "interactive",
            "sender": "curl",
            "status": "failed",
            "success": False,
            "message": f"飞书 curl 回退发送失败：{result.stderr.strip() or result.stdout.strip() or result.returncode}",
            "response": {},
        }
    return _normalize_feishu_response(200, result.stdout, "curl")


def send_feishu_notification(
    feishu: dict[str, Any],
    config: dict[str, Any],
    session_meta: dict[str, Any],
    plan: dict[str, Any],
    status: dict[str, Any],
    overall_result: str,
) -> dict[str, Any]:
    title = _workflow_notification_title(session_meta["session_id"], overall_result)
    payload = build_feishu_notification_payload(config, session_meta, plan, status, overall_result, title)
    secret = str(feishu.get("secret", "")).strip()
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = feishu_sign(secret, timestamp)
    webhook_url = str(feishu.get("webhook_url", "")).strip()
    python_result = send_feishu_notification_python(webhook_url, payload)
    if python_result.get("success"):
        return python_result
    curl_result = send_feishu_notification_curl(webhook_url, payload)
    if curl_result.get("success"):
        curl_result["message"] = f"{curl_result.get('message', '')}（Python失败后已回退curl成功）"
        curl_result["python_error"] = python_result.get("message", "")
        return curl_result
    curl_result["python_error"] = python_result.get("message", "")
    curl_result["message"] = (
        f"Python发送失败：{python_result.get('message', '')}；"
        f"curl回退也失败：{curl_result.get('message', '')}"
    )
    return curl_result


def notify_workflow_result(
    config: dict[str, Any],
    session_meta: dict[str, Any],
    plan: dict[str, Any],
    status: dict[str, Any],
    overall_result: str,
) -> dict[str, Any]:
    notification_path = data_artifact_path(config, "notification.json", session_meta)
    existing_result = read_json(notification_path, {})
    current_fingerprint = workflow_notification_fingerprint(session_meta, status, overall_result)
    if (
        isinstance(existing_result, dict)
        and existing_result.get("status") == "sent"
        and str(existing_result.get("fingerprint", "")).strip() == current_fingerprint
    ):
        deduped_result = dict(existing_result)
        deduped_result["deduplicated"] = True
        deduped_result["message"] = "通知已发送，已跳过重复发送。"
        return deduped_result

    pushplus = pushplus_config(config)
    feishu = feishu_config(config)
    enabled_routes = [item for item in pushplus.get("routes", []) if item.get("enabled")]
    if feishu.get("enabled"):
        enabled_routes.append({"name": "feishu", "channel": "webhook", "template": "interactive"})
    result: dict[str, Any] = {
        "provider": "notification",
        "fingerprint": current_fingerprint,
        "enabled": bool(enabled_routes),
        "status": "skipped",
        "message": "未配置通知。",
        "sent_at": now_iso(),
        "title": "",
        "routes": enabled_routes,
        "results": [],
    }
    if enabled_routes:
        route_results = []
        last_title = ""
        for route in enabled_routes:
            if route.get("name") == "feishu":
                last_title = _workflow_notification_title(session_meta["session_id"], overall_result)
                route_results.append(
                    send_feishu_notification(feishu, config, session_meta, plan, status, overall_result)
                )
                continue
            title, content = build_workflow_notification(
                config,
                session_meta,
                plan,
                status,
                overall_result,
                template=str(route.get("template", "markdown") or "markdown"),
            )
            last_title = title
            route_results.append(send_pushplus_notification(pushplus, route, title, content))
        sent_count = sum(1 for item in route_results if item.get("status") == "sent")
        if sent_count == len(route_results):
            result["status"] = "sent"
        elif sent_count > 0:
            result["status"] = "partial"
        else:
            result["status"] = "failed"
        result["title"] = last_title
        result["message"] = "；".join(
            f"{item.get('route', 'unknown')}:{item.get('message', '')}" for item in route_results
        )
        result["results"] = route_results
        result["sent_at"] = now_iso()
    write_json(notification_path, result)
    return result


def phase_after(stage: str, mode: str) -> tuple[str, bool, str, str]:
    if stage == "plan":
        if mode == "manual":
            return ("wait_confirm_plan", True, "implement", "等待确认后开始按计划修改代码。")
        return ("plan", False, "", "继续进入实现阶段。")
    if stage == "implement":
        if mode == "manual":
            return ("wait_confirm_implement", True, "review", "等待确认后执行代码审查。")
        return ("implement", False, "", "继续进入代码审查阶段。")
    if stage == "review":
        if mode == "manual":
            return ("wait_confirm_review", True, "verify", "等待确认后执行验证。")
        return ("review", False, "", "继续进入验证阶段。")
    return ("done", False, "", "工作流已完成。")


def scan_java_files(codebase: Path) -> list[str]:
    results: list[str] = []
    for pattern in ("src/main/java/**/*.java", "src/test/java/**/*.java"):
        for path in sorted(codebase.glob(pattern)):
            results.append(str(path.resolve()))
    return results


def infer_java_modules(paths: list[str]) -> list[str]:
    modules: list[str] = []
    for absolute_path in paths:
        parts = Path(absolute_path).parts
        if "java" not in parts:
            continue
        java_index = parts.index("java")
        package_parts = list(parts[java_index + 1 : -1])
        if not package_parts:
            continue
        if len(package_parts) >= 2:
            module = f"{package_parts[-2]}-{package_parts[-1]}"
        else:
            module = package_parts[-1]
        if module not in modules:
            modules.append(module)
    return modules
