# OSS Split Plan

This document describes how to move the current branch into a dedicated public repository with minimal confusion and minimal history cleanup risk.

## Recommended Strategy

Use a **fresh public repository** and import the current tree as a clean initial public baseline.

Recommended approach:

1. create a new empty public repo
2. copy the current working tree into that repo
3. keep the first public commit small and coherent
4. publish later incremental commits only after the repo exists

This is safer than exposing the entire development history by default.

## Why a Fresh Public Repo

Benefits:

- simpler story for outside contributors
- avoids leaking private naming or workflow residue through old history
- cleaner first release notes
- easier license and metadata setup

Tradeoff:

- you lose some granular commit history in the first public snapshot

For this project, that tradeoff is worth it.

## Recommended History Policy

### Option A — Recommended

Create a clean public baseline with:

- one initial import commit
- one docs / governance commit
- one optional release-tag commit

Use this if the public repo should feel intentionally curated.

### Option B — Acceptable

Push the existing OSS branch history if you want early contributors to see how the MVP evolved.

Use this only if you are comfortable with the current commit narrative becoming public.

## Suggested Public Repo Contents

Include:

- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/`
- `examples/`
- `src/`
- `tests/`
- `.github/` templates
- `pyproject.toml`

Before publishing, also add:

- final `LICENSE`
- repository description
- repository topics

## Suggested Split Steps

```bash
# in a fresh directory
git init
git remote add origin <new-public-repo-url>

# copy the current OSS tree into the repo
# then:
git add .
git commit -m "feat: initial public agent-hub MVP"

# optional
git add LICENSE
git commit -m "docs: add license and public repo metadata"

git tag v0.1.0
git push -u origin main --tags
```

## Public Repo Description

Recommended description:

> Local-first agent task hub with SQLite queueing, dependency-aware dispatch, project task templates, pipelines, human inbox, saved queries, and a thin dashboard.

## Suggested Topics

- agents
- automation
- sqlite
- orchestration
- local-first
- python

## First Public Scope

Publicly frame `v0.1.0` as:

- experimental
- local-first
- single-operator oriented
- extensible OSS foundation

Do not frame it as:

- production hosted control plane
- secure multi-user platform
- enterprise workflow manager
