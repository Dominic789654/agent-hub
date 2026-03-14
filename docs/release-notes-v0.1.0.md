# Release Notes — v0.1.0

`v0.1.0` is the first public OSS baseline for `agent-hub`.

This release packages the current local-first MVP into a form that is easier to run, review, and extend.

## Positioning

This release is:

- experimental
- local-first
- single-operator oriented
- meant as an extensible OSS foundation

This release is not:

- a hosted control plane
- a secure multi-user system
- a finished product

## Highlights

### Task Queue Core

- SQLite-backed task storage
- task lifecycle management
- dependency-aware scheduling
- retry and cancellation behavior
- block propagation and human handoff states

### Project Routing

- project-backed actions
- task templates
- pipeline templates
- pipeline run tracking

### Human Review Surface

- task and pipeline notes
- task and pipeline labels
- human inbox aggregation
- saved query presets plus execution

### Operator Visibility

- JSON dashboard snapshot at `/dashboard`
- thin browser dashboard at `/app`
- classic HTML control page at `/`

## Included Documentation

- updated `README.md`
- demo walkthrough in `docs/demo.md`
- release checklist in `docs/release-checklist.md`
- handoff notes in `docs/handoff-notes.md`
- OSS split and repo prep guidance

## Recommended Demo Flow

1. start `serve`
2. start `dispatch`
3. queue one task template
4. queue one pipeline
5. mark a task `needs_human`
6. view `/app`
7. create and apply a saved query

## Known Gaps

Still intentionally missing:

- auth
- multi-user permissions
- hosted execution model
- background supervision layer
- import/export UX
- richer browser interactions

## Upgrade / Install Notes

Fresh install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m agent_hub serve --port 8080
```
