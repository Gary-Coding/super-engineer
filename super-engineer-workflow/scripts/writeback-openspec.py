#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    current_session_meta,
    data_artifact_path,
    format_duration,
    load_workspace_config,
    now_iso,
    openspec_change_dir,
    openspec_writeback_dir,
    read_json,
    report_artifact_path,
    workflow_source,
    workspace_root,
    write_json,
    write_text,
)


def summarize_review(review: dict) -> list[str]:
    findings = review.get("findings", [])
    if not findings:
        return ["暂无 review finding。"]
    lines: list[str] = []
    for item in findings[:8]:
        lines.append(f"[{item.get('severity', 'info')}] {item.get('title', '')}：{item.get('detail', '')}")
    return lines


def summarize_verify(verify: dict) -> list[str]:
    sections = verify.get("sections", [])
    if not sections:
        return ["暂无 verify 明细。"]
    lines: list[str] = []
    for section in sections[:8]:
        lines.append(
            f"{section.get('name', 'unknown')}：{section.get('result', '')}，退出码 {section.get('exit_code', '')}，耗时 {section.get('duration', 0):.2f} 秒"
        )
    return lines


def summarize_acceptance(plan: dict, verify: dict) -> list[dict[str, object]]:
    verify_result = str(verify.get("result", "missing"))
    status = "passed" if verify_result == "通过" else "pending"
    items: list[dict[str, object]] = []
    for criterion in plan.get("acceptance_criteria", []):
        checks = [str(item) for item in criterion.get("checks", [])]
        items.append(
            {
                "task_title": str(criterion.get("task_title", "")),
                "status": status,
                "checks": checks,
            }
        )
    return items


def infer_spec_impacts(plan: dict, bridge_context: dict) -> list[str]:
    impacts = [str(item) for item in bridge_context.get("spec_reference_files", []) if str(item).strip()]
    if impacts:
        return impacts
    return [str(item.get("path", "")) for item in plan.get("target_codebases", []) if str(item.get("path", "")).strip()]


def residual_risks(plan: dict, review: dict, verify: dict) -> list[str]:
    risks = [str(item) for item in plan.get("risks", []) if str(item).strip()]
    for finding in review.get("findings", []):
        if str(finding.get("severity", "")) in ("warning", "blocker"):
            risks.append(str(finding.get("detail", "")))
    if verify.get("result") not in ("通过", "", None):
        risks.append(f"验证结果未通过：{verify.get('result')}")
    return risks[:12]


def build_markdown(payload: dict) -> str:
    lines = [
        "# Super Engineer Execution Summary",
        "",
        "## Change",
        f"- change: {payload.get('change_name', '')}",
        f"- change_dir: {payload.get('change_dir', '')}",
        f"- session_id: {payload.get('session_id', '')}",
        f"- updated_at: {payload.get('updated_at', '')}",
        "",
        "## Plan",
        f"- requirement_summary: {payload.get('plan', {}).get('requirement_summary', '')}",
        f"- confidence: {payload.get('plan', {}).get('confidence', '')}",
        "",
        "## Repositories",
    ]
    repos = payload.get("plan", {}).get("target_codebases", [])
    if repos:
        for repo in repos:
            lines.append(f"- {repo.get('name', '')}: {repo.get('path', '')}")
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "## Review",
        f"- result: {payload.get('review', {}).get('result', 'missing')}",
    ])
    lines.extend(f"- {item}" for item in payload.get("review_summary", []))
    lines.extend([
        "",
        "## Verify",
        f"- result: {payload.get('verify', {}).get('result', 'missing')}",
    ])
    lines.extend(f"- {item}" for item in payload.get("verify_summary", []))
    lines.extend([
        "",
        "## Links",
        f"- plan.md: {payload.get('reports', {}).get('plan_md', '')}",
        f"- review.md: {payload.get('reports', {}).get('review_md', '')}",
        f"- verify.md: {payload.get('reports', {}).get('verify_md', '')}",
    ])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="把当前会话执行结果回写到 OpenSpec change 目录。")
    parser.add_argument("--workspace", help="工作空间路径，默认读取当前目录")
    args = parser.parse_args()

    workspace = workspace_root(Path(args.workspace).expanduser() if args.workspace else None)
    config = load_workspace_config(workspace)
    if workflow_source(config) != "openspec":
        raise SystemExit("当前 workspace.yml 未启用 OpenSpec 模式，无需执行 writeback-openspec。")

    session_meta = current_session_meta(config)
    plan = read_json(data_artifact_path(config, "plan.json", session_meta), {})
    review = read_json(data_artifact_path(config, "review.json", session_meta), {})
    verify = read_json(data_artifact_path(config, "verify.json", session_meta), {})
    status = read_json(data_artifact_path(config, "status.json", session_meta), {})
    plan_bridge_context = plan.get("bridge_context", {})
    archive_ready = bool(
        review.get("result") == "passed"
        and verify.get("result") == "通过"
        and str(status.get("phase", "")).strip() == "done"
    )
    archive_blockers: list[str] = []
    if review.get("result") != "passed":
        archive_blockers.append("review 未通过")
    if verify.get("result") != "通过":
        archive_blockers.append("verify 未通过")
    if str(status.get("phase", "")).strip() != "done":
        archive_blockers.append(f"当前状态不是 done：{status.get('phase', '')}")

    payload = {
        "change_name": str(config.get("openspec", {}).get("change_name", "")),
        "change_dir": str(openspec_change_dir(config)),
        "session_id": session_meta["session_id"],
        "updated_at": now_iso(),
        "status": {
            "phase": status.get("phase", ""),
            "progress": status.get("progress", 0),
            "current_task": status.get("current_task", ""),
            "duration": format_duration(float(status.get("duration_seconds", 0) or 0)),
        },
        "archive_ready": archive_ready,
        "archive_blockers": archive_blockers,
        "plan": {
            "requirement_summary": plan.get("requirement_summary", ""),
            "confidence": plan.get("confidence", ""),
            "target_codebases": plan.get("target_codebases", []),
            "impacted_files": plan.get("impacted_files", []),
            "acceptance_criteria": plan.get("acceptance_criteria", []),
        },
        "bridge_context": plan_bridge_context,
        "review": {
            "result": review.get("result", "missing"),
            "findings": review.get("findings", []),
        },
        "verify": {
            "result": verify.get("result", "missing"),
            "sections": verify.get("sections", []),
        },
        "acceptance_result": summarize_acceptance(plan, verify),
        "spec_impacts": infer_spec_impacts(plan, plan_bridge_context),
        "residual_risks": residual_risks(plan, review, verify),
        "manual_decisions": [],
        "review_summary": summarize_review(review),
        "verify_summary": summarize_verify(verify),
        "reports": {
            "plan_md": str(report_artifact_path(config, "plan.md", session_meta)),
            "review_md": str(report_artifact_path(config, "review.md", session_meta)),
            "verify_md": str(report_artifact_path(config, "verify.md", session_meta)),
        },
    }

    output_dir = openspec_writeback_dir(config)
    write_json(output_dir / "execution-summary.json", payload)
    write_text(output_dir / "execution-summary.md", build_markdown(payload))
    print(f"writeback_dir={output_dir}")
    print(f"change_dir={openspec_change_dir(config)}")


if __name__ == "__main__":
    main()
