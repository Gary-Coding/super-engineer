# super-engineer

`super-engineer` is a workflow-oriented skill package for AI-assisted software delivery in brownfield systems.

It is designed for teams that do not just want "AI writes code", but want a repeatable execution flow with:

- structured planning
- implementation checkpoints
- review and verify gates
- durable session artifacts
- optional OpenSpec integration for spec-governed changes

## Why

In medium and large codebases, chat-only agent workflows usually fail in predictable ways:

- requirements get lost in long conversations
- plans are implicit and not reusable
- implementation evidence is hard to audit
- code review and verification are loosely coupled
- the next change starts without a stable baseline

`super-engineer` addresses that by turning engineering work into a file-backed workflow.

## Features

- `discover -> plan -> implement -> self-check -> review -> verify` execution flow
- session-based artifacts under `.super-engineer/sessions/<session_id>/`
- human-readable reports in a configurable `output_dir`
- `manual` and `auto` execution modes
- multi-repo / aggregated codebase targeting
- OpenSpec bridge mode via `workspace.yml`
- OpenSpec execution writeback and archive preparation
- PushPlus and Feishu notifications

## Repository Layout

```text
super-engineer/
├── README.md
└── super-engineer-workflow/
    ├── SKILL.md
    ├── agents/
    ├── assets/
    ├── references/
    └── scripts/
```

## Workflow Modes

The skill supports two input modes.

### 1. `todo` mode

Use a user-maintained `todo.md` as the direct execution input.

This is the default mode and is the lightest setup.

### 2. `openspec` mode

Use an OpenSpec change as upstream input.

The workflow will:

- read `tasks.md`
- generate a bridged execution `todo`
- include `proposal.md`, `design.md`, and `specs/*.md` as context
- write execution results back to the OpenSpec change
- prepare archive inputs for long-term spec sync

## Installation

This repository contains the skill source. Install it by copying `super-engineer-workflow/` into a local skill directory.

Common locations:

- Codex: `~/.codex/skills/super-engineer-workflow`
- Claude: `~/.claude/skills/super-engineer-workflow`

## Workspace Setup

Each business workspace must include `workspace.yml`.

Minimal `todo` mode example:

```yaml
version: 1
mode: manual
workflow_source: todo
todo_file: /absolute/path/to/workspace/todo.md
reference_files: []
code_path: /absolute/path/to/code
output_dir: /absolute/path/to/output
```

Minimal `openspec` mode example:

```yaml
version: 1
mode: manual
workflow_source: openspec
todo_file: /absolute/path/to/workspace/todo.generated.md
reference_files: []
code_path: /absolute/path/to/code
output_dir: /absolute/path/to/output
openspec:
  change_dir: /absolute/path/to/openspec/changes/add-phone-filter
```

Skill-level configuration lives at:

```text
~/.super-engineer/skill-config.yml
```

If the file does not exist, the workflow creates a default config and stops so it can be completed explicitly.

## Core Commands

Main entrypoint:

```bash
python3 scripts/run-workflow.py <command> --workspace /abs/path/to/workspace
```

Common commands:

- `init`
- `discover`
- `plan`
- `start-implement`
- `finish-implement`
- `review`
- `verify`
- `status`

OpenSpec bridge commands:

- `bootstrap-openspec`
- `writeback-openspec`
- `prepare-archive-openspec`
- `archive-openspec`

## Runtime Artifacts

Machine-readable session artifacts:

```text
<workspace>/.super-engineer/current-session.json
<workspace>/.super-engineer/sessions/<session_id>/discovery.json
<workspace>/.super-engineer/sessions/<session_id>/plan.json
<workspace>/.super-engineer/sessions/<session_id>/self-check.json
<workspace>/.super-engineer/sessions/<session_id>/review.json
<workspace>/.super-engineer/sessions/<session_id>/verify.json
<workspace>/.super-engineer/sessions/<session_id>/status.json
```

Human-readable reports:

```text
<output_dir>/<session_id>/discovery.md
<output_dir>/<session_id>/plan.md
<output_dir>/<session_id>/self-check.md
<output_dir>/<session_id>/review.md
<output_dir>/<session_id>/verify.md
```

OpenSpec mode adds:

```text
<workspace>/.super-engineer/openspec-bridge-context.json
<change_dir>/super-engineer/execution-summary.json
<change_dir>/super-engineer/archive-input.json
<change_dir>/super-engineer/archive-result.json
```

`prepare-archive-openspec` performs baseline-aware conflict detection before archive. Automatic archive is allowed only when `merge_mode` is `safe_merge`.

## OpenSpec Integration Model

The intended layering is:

```text
OpenSpec change
-> bridge into workflow input
-> super-engineer execution flow
-> writeback execution summary
-> prepare archive
-> archive change and sync delta specs
```

This separation keeps:

- OpenSpec responsible for long-term spec evolution
- `super-engineer` responsible for code-facing delivery execution

## Documentation

Start here:

- [super-engineer-workflow/SKILL.md](super-engineer-workflow/SKILL.md)
- [super-engineer-workflow/references/workflow.md](super-engineer-workflow/references/workflow.md)
- [super-engineer-workflow/references/contracts.md](super-engineer-workflow/references/contracts.md)
- [super-engineer-workflow/references/planning.md](super-engineer-workflow/references/planning.md)
- [docs/中文使用手册.md](docs/中文使用手册.md)

## Status

Current state:

- execution workflow is usable
- OpenSpec bridge input is implemented
- OpenSpec writeback is implemented
- archive preparation and archive commands are implemented with baseline-aware safe-merge checks
- long-term spec governance still requires team process discipline

## Roadmap

- richer spec merge semantics than file copy for archive
- optional policy rules for when OpenSpec mode is required
- better release / rollout metadata integration
- clearer multi-repo collaboration patterns

## License

No license file is included yet. Add one before public distribution.
