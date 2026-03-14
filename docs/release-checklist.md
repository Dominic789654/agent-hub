# Release Checklist

Use this checklist before cutting a public OSS release.

## Install / Packaging

- [ ] `pip install -e .[dev]` works in a fresh virtualenv
- [ ] `python -m agent_hub version` works
- [ ] `python -m agent_hub --help` renders without errors

## Core Runtime

- [ ] `python -m agent_hub serve --port 8080` starts
- [ ] `python -m agent_hub dispatch` starts
- [ ] `GET /healthz` returns `{"ok": true}`
- [ ] `GET /dashboard` returns a valid snapshot
- [ ] `GET /app` renders the thin browser dashboard

## Demo Flow

- [ ] `create-task` works
- [ ] `run-task-template` works
- [ ] `run-pipeline` works
- [ ] task notes / labels work
- [ ] pipeline run notes / labels work
- [ ] human inbox shows actionable tasks
- [ ] saved query create / list / apply / delete works

## Quality Gates

- [ ] `python -m pytest -q`
- [ ] `python -m compileall src/agent_hub tests`

## Repo Hygiene

- [ ] README matches current commands and routes
- [ ] `docs/demo.md` matches the actual startup path
- [ ] `examples/projects.example.json` still boots a usable sample project
- [ ] no local state files under `./.agent-hub/` are tracked
- [ ] no private infra details or secrets are present

## Release Framing

- [ ] document current scope as local MVP, not full platform
- [ ] call out missing auth / multi-user / hosted execution
- [ ] choose license before publishing broadly
