# agent-hub

[![Live Site](https://img.shields.io/badge/site-live-78A8FF)](https://dominic789654.github.io/agent-hub/)
[![Release](https://img.shields.io/badge/release-v0.1.0-7EF0C4)](https://github.com/Dominic789654/agent-hub/releases/tag/v0.1.0)
[![License](https://img.shields.io/badge/license-Apache--2.0-C0B0FF)](./LICENSE)

Local-first multitask board for routing and observing code-assistant work across projects.

Quick links: [Live Site](https://dominic789654.github.io/agent-hub/) · [Demo Page](https://dominic789654.github.io/agent-hub/demo.html) · [Repository](https://github.com/Dominic789654/agent-hub) · [First Release](https://github.com/Dominic789654/agent-hub/releases/tag/v0.1.0)

This OSS repo is the portable, public-safe slice of the broader idea:

- queue code-assistant tasks in SQLite
- route work into repo-local code agents through project-backed commands
- model dependencies, retries, blocking, and human handoff
- expose a small HTTP surface and a thin browser dashboard for multitask visibility

The codebase stays intentionally small and uses the Python standard library only.

## Project Site

- live site: `https://dominic789654.github.io/agent-hub/`
- landing page: `docs/index.html`
- demo guide: `docs/demo.md`
- demo page: `docs/demo.html`
- recommended agent workflow: `docs/agent-driven-usage.md`
- public launch checklist: `docs/public-launch-checklist.md`
- public release: `https://github.com/Dominic789654/agent-hub/releases/tag/v0.1.0`
- GitHub Pages publish is wired through `.github/workflows/pages.yml`

## Current Status

Current status: public-safe OSS MVP.

- ready to share as a local-first, single-operator code-assistant multitask baseline
- suitable for demos, exploration, and extension in local environments
- not yet positioned as a mature hosted platform or stable long-term API surface
- scope is intentionally constrained to queueing, routing, visibility, and handoff

## Near-Term Roadmap

- improve example projects and end-to-end walkthroughs
- add richer screenshots or UI captures for the public site
- tighten public API framing and compatibility expectations
- expand executor and policy examples without turning the repo into a heavy platform

## Recommended Usage Pattern

Use `agent-hub` as the multitask board and control plane, not as a replacement for your coding agent.

- keep `agent-hub` responsible for queueing, routing, dependency handling, and visibility
- keep repo-local coding agents responsible for actual implementation work
- register those agents as project-backed local commands, then launch them through `agent-hub`

The current OSS slice is a good fit for workflows where you already use tools like Claude Code, Codex, Kimi Code, or Qwen Code in local repos and want one explicit multitask board in front of them.

See `docs/agent-driven-usage.md` for the recommended setup pattern.

## Not A Traditional Task Board

`agent-hub` is not meant to be a generic to-do tracker for arbitrary operator commands.

- the primary unit is a bounded code-assistant task
- the main target is a local repo plus a repo-local coding agent
- the main value is routing, dependency control, retry visibility, and human handoff
- the dashboard is for supervising assistant work, not for replacing the assistant itself

## What It Does

`agent-hub` currently supports:

- task queueing for code-assistant work with lifecycle state
- dependency edges between tasks
- standalone dispatcher execution
- project-backed actions, task templates, and pipelines for repo-local agents
- task and pipeline run notes / labels
- saved query presets and execution
- human inbox aggregation for manual triage
- dashboard JSON and a thin browser app at `/app`

## What It Is Not

This repo is not yet:

- a multi-user SaaS
- a hosted control plane
- an auth-enabled production service
- a generic remote executor framework

Treat it as a strong local MVP for code-assistant orchestration, not a finished platform.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Five-Minute Demo

Terminal A:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json serve --port 8080
```

Terminal B:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dispatch
```

Terminal C:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-codex delegate-task --input "Investigate why the local build script is flaky"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-claude delegate-task --input "Review the proposed fix and summarize risks"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-pipeline demo-codex review-then-implement --input "Add a dry-run mode to the deployment helper"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json list-human-inbox
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dashboard
```

Then open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/app`
- `http://127.0.0.1:8080/dashboard`

More guided steps live in `docs/demo.md`, and the browser-friendly version lives in `docs/demo.html`. The runnable assistant-board example registry lives at `examples/agent-driven-projects.example.json`.

## Default Local State

- data dir: `./.agent-hub/`
- database: `./.agent-hub/agent_hub.db`
- projects registry: `./.agent-hub/projects.json`

Overrides:

- `--data-dir`
- `--projects-file`
- `AGENT_HUB_DATA_DIR`
- `AGENT_HUB_PROJECTS_FILE`

## Core Concepts

**Tasks**
- unit of queued work
- may target a `project_id`
- may depend on predecessor task ids

**Project Actions**
- reusable named command templates under `executor.actions`
- executed via `project_action` tasks

**Task Templates**
- reusable intake templates under `executor.task_templates`
- instantiate a single queued task

**Pipelines**
- reusable multi-step graphs under `executor.pipelines`
- instantiate multiple tasks plus dependency edges

**Human Inbox**
- derived view over `failed`, `blocked`, and `needs_human` tasks
- enriched with labels and latest note

**Saved Queries**
- persisted filter presets for `tasks` and `pipeline_runs`
- can be executed later through CLI or HTTP

## Main Commands

**Setup / Runtime**
- `python -m agent_hub serve --port 8080`
- `python -m agent_hub dispatch`
- `python -m agent_hub dashboard`
- `python -m agent_hub status`
- `python -m agent_hub config`

**Task Queue**
- `python -m agent_hub create-task "hello" --kind echo --payload hi`
- `python -m agent_hub list-tasks --project-id sample-project --status failed`
- `python -m agent_hub retry-task <task-id>`
- `python -m agent_hub cancel-task <task-id>`
- `python -m agent_hub mark-needs-human <task-id> --note "manual review required"`

**Project Routing**
- `python -m agent_hub list-projects`
- `python -m agent_hub list-project-actions sample-project`
- `python -m agent_hub list-project-task-templates sample-project`
- `python -m agent_hub list-project-pipelines sample-project`
- `python -m agent_hub run-task-template sample-project summarize-input --input "hello"`
- `python -m agent_hub run-pipeline sample-project sample-flow --input "hello"`

**Annotations**
- `python -m agent_hub add-task-note <task-id> "manual review required"`
- `python -m agent_hub add-task-label <task-id> important`
- `python -m agent_hub remove-task-label <task-id> important`
- `python -m agent_hub add-pipeline-run-note <pipeline-run-id> "watch this run"`
- `python -m agent_hub add-pipeline-run-label <pipeline-run-id> priority`
- `python -m agent_hub remove-pipeline-run-label <pipeline-run-id> priority`

**Inbox / Queries**
- `python -m agent_hub list-human-inbox --project-id sample-project`
- `python -m agent_hub create-saved-query tasks "Failed Tasks" --filter project_id=sample-project --filter status=failed`
- `python -m agent_hub list-saved-queries --scope tasks`
- `python -m agent_hub apply-saved-query <query-id>`
- `python -m agent_hub delete-saved-query <query-id>`

## HTTP Surface

**Dashboard / Status**
- `GET /healthz`
- `GET /app`
- `GET /dashboard`
- `GET /status`
- `GET /config`

**Projects**
- `GET /projects`
- `GET /projects/<project_id>/actions`
- `GET /projects/<project_id>/task-templates`
- `GET /projects/<project_id>/pipelines`

**Tasks**
- `GET /tasks?limit=20&project_id=<id>&status=<status>&kind=<kind>&pipeline_run_id=<id>`
- `GET /tasks/<task_id>`
- `GET /tasks/<task_id>/neighbors`
- `GET /tasks/<task_id>/runs/latest`
- `POST /tasks`
- `POST /tasks/<task_id>/retry`
- `POST /tasks/<task_id>/cancel`
- `POST /tasks/<task_id>/needs-human`
- `POST /tasks/<task_id>/notes`
- `POST /tasks/<task_id>/labels`
- `POST /tasks/<task_id>/labels/remove`

**Runs / Inbox**
- `GET /runs?limit=20`
- `GET /human-inbox?limit=20&project_id=<id>`

**Pipelines**
- `GET /pipeline-runs?limit=20&project_id=<id>&pipeline_id=<id>`
- `GET /pipeline-runs/<pipeline_run_id>`
- `POST /pipelines`
- `POST /pipeline-runs/<pipeline_run_id>/retry`
- `POST /pipeline-runs/<pipeline_run_id>/cancel`
- `POST /pipeline-runs/<pipeline_run_id>/notes`
- `POST /pipeline-runs/<pipeline_run_id>/labels`
- `POST /pipeline-runs/<pipeline_run_id>/labels/remove`

**Saved Queries**
- `GET /saved-queries?limit=20&scope=<tasks|pipeline_runs>`
- `GET /saved-queries/<query_id>`
- `GET /saved-queries/<query_id>/apply?limit=20`
- `POST /saved-queries`
- `POST /saved-queries/<query_id>/delete`

**Task Template Intake**
- `POST /task-templates`

## Example Project Registry

The repo bootstraps a local example project that includes:

- one project action
- one task template
- one pipeline

See:

- `examples/projects.example.json`

## Release Notes

Before cutting a public release, run the checklist in:

- `docs/release-checklist.md`
- `docs/oss-repo-prep.md`
- `docs/oss-split-plan.md`
- `docs/license-recommendation.md`
- `docs/public-repo-commands.md`
- `docs/release-notes-v0.1.0.md`

## Contributing

See:

- `CONTRIBUTING.md`
- `SECURITY.md`

## Safety

- no private infrastructure assumptions
- no secrets in examples
- local state stays under ignored paths such as `./.agent-hub/`
- destructive actions remain explicit

## Repository Layout

```text
.
├── docs/
│   ├── architecture.md
│   ├── demo.md
│   ├── handoff-notes.md
│   ├── license-recommendation.md
│   ├── oss-repo-prep.md
│   ├── oss-split-plan.md
│   ├── release-notes-v0.1.0.md
│   ├── release-checklist.md
│   └── safety.md
├── examples/
│   ├── env.example
│   └── projects.example.json
├── src/
│   └── agent_hub/
├── tests/
└── pyproject.toml
```
