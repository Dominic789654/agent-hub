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

## 🌐 Project Site

- live site: `https://dominic789654.github.io/agent-hub/`
- landing page: `docs/index.html`
- demo guide: `docs/demo.md`
- demo page: `docs/demo.html`
- recommended agent workflow: `docs/agent-driven-usage.md`
- public launch checklist: `docs/public-launch-checklist.md`
- public release: `https://github.com/Dominic789654/agent-hub/releases/tag/v0.1.0`
- GitHub Pages publish is wired through `.github/workflows/pages.yml`

## 🚦 Current Status

Current status: public-safe OSS MVP.

- ready to share as a local-first, single-operator code-assistant multitask baseline
- suitable for demos, exploration, and extension in local environments
- not yet positioned as a mature hosted platform or stable long-term API surface
- scope is intentionally constrained to queueing, routing, visibility, and handoff

## 🗺️ Near-Term Roadmap

- improve example projects and end-to-end walkthroughs
- add richer screenshots or UI captures for the public site
- tighten public API framing and compatibility expectations
- expand executor and policy examples without turning the repo into a heavy platform

## 🤖 Recommended Usage Pattern

Use `agent-hub` as the multitask board and control plane, not as a replacement for your coding agent.

- keep `agent-hub` responsible for queueing, routing, dependency handling, and visibility
- keep repo-local coding agents responsible for actual implementation work
- register those agents as project-backed local commands, then launch them through `agent-hub`

The current OSS slice is a good fit for workflows where you already use tools like Claude Code, Codex, Kimi Code, or Qwen Code in local repos and want one explicit multitask board in front of them.

See `docs/agent-driven-usage.md` for the recommended setup pattern.

## 🚫 Not A Traditional Task Board

`agent-hub` is not meant to be a generic to-do tracker for arbitrary operator commands.

- the primary unit is a bounded code-assistant task
- the main target is a local repo plus a repo-local coding agent
- the main value is routing, dependency control, retry visibility, and human handoff
- the dashboard is for supervising assistant work, not for replacing the assistant itself

## ✨ What It Does

`agent-hub` currently supports:

- task queueing for code-assistant work with lifecycle state
- dependency edges between tasks
- standalone dispatcher execution
- project-backed actions, task templates, and pipelines for repo-local agents
- task and pipeline run notes / labels
- saved query presets and execution
- human inbox aggregation for manual triage
- dashboard JSON and a thin browser app at `/app`

## 🧱 What It Is Not

This repo is not yet:

- a multi-user SaaS
- a hosted control plane
- an auth-enabled production service
- a generic remote executor framework

Treat it as a strong local MVP for code-assistant orchestration, not a finished platform.

## ⚡ Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## ⏱️ Five-Minute Operator Flow

The intended usage is:

- one background terminal for the board
- one background terminal for the dispatcher
- one assistant terminal where you talk to Codex or Claude Code

**🖥️ Background terminal A**

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json serve --port 8080
```

**🖥️ Background terminal B**

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dispatch
```

**💬 Assistant terminal**

Open Codex or Claude Code in the environment where you want to operate the board, then ask it to submit tasks for you.

Example prompts:

- `Create a Codex task in demo-codex to investigate why the local build script is flaky.`
- `Create a Claude task in demo-claude to review the proposed fix and summarize risks.`
- `If the review is clean, queue the review-then-implement pipeline in demo-codex for "Add a dry-run mode to the deployment helper".`
- `Show me the current human inbox and tell me if any task needs manual routing.`

That is the primary interaction model. The operator mainly talks to the coding assistant, and the assistant uses `agent-hub` to place and inspect work on the board.

Then open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/app`
- `http://127.0.0.1:8080/dashboard`

If you want the lower-level CLI walkthrough, use `docs/demo.md` or `docs/demo.html`. The runnable assistant-board example registry lives at `examples/agent-driven-projects.example.json`.

## 📁 Default Local State

- data dir: `./.agent-hub/`
- database: `./.agent-hub/agent_hub.db`
- projects registry: `./.agent-hub/projects.json`

Overrides:

- `--data-dir`
- `--projects-file`
- `AGENT_HUB_DATA_DIR`
- `AGENT_HUB_PROJECTS_FILE`

## 🧰 Common Board Operations

These are the operations your assistant should usually perform on your behalf.

**🗣️ What You Ask The Assistant**
- `Create a Codex task in demo-codex for this bug report.`
- `Create a Claude review task for the proposed fix.`
- `Queue the review-then-implement pipeline in demo-codex.`
- `Check the human inbox and summarize what needs routing.`
- `Retry the failed Codex task and tell me what changed.`

**⚙️ What The Assistant Uses Under The Hood**
- `python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-codex delegate-task --input "..."`
- `python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-claude delegate-task --input "..."`
- `python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-pipeline demo-codex review-then-implement --input "..."`
- `python -m agent_hub --projects-file examples/agent-driven-projects.example.json list-human-inbox`
- `python -m agent_hub --projects-file examples/agent-driven-projects.example.json retry-task <task-id>`

The CLI remains important, but mostly as the mechanism behind the assistant-facing workflow, not as the primary operator experience.

## 📚 If You Want The Technical Details

- architecture notes: `docs/architecture.md`
- assistant-first workflow: `docs/agent-driven-usage.md`
- runnable board walkthrough: `docs/demo.md`
- browser-friendly demo: `docs/demo.html`
- release / launch checklist: `docs/public-launch-checklist.md`
- public release notes: `docs/release-notes-v0.1.0.md`

## 🧪 Example Project Registries

The repo includes two example registries:

- `examples/agent-driven-projects.example.json` for the recommended code-assistant board pattern
- `examples/projects.example.json` for the lower-level portable sample registry used by tests and scaffold validation

## 📝 Release Notes

Before cutting a public release, run the checklist in:

- `docs/release-checklist.md`
- `docs/oss-repo-prep.md`
- `docs/oss-split-plan.md`
- `docs/license-recommendation.md`
- `docs/public-repo-commands.md`
- `docs/release-notes-v0.1.0.md`

## 🤝 Contributing

See:

- `CONTRIBUTING.md`
- `SECURITY.md`

## 🔒 Safety

- no private infrastructure assumptions
- no secrets in examples
- local state stays under ignored paths such as `./.agent-hub/`
- destructive actions remain explicit
