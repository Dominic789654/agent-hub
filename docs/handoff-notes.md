# Handoff Notes

This repo now has a coherent local MVP surface.

## Stable Capabilities

- local SQLite task store
- task lifecycle and dependency graph
- dispatcher with safe built-in executors
- project actions
- task templates
- pipelines
- task / pipeline notes and labels
- human inbox
- saved queries plus execution
- dashboard JSON plus thin browser app

## Current Positioning

Recommended positioning for OSS:

- local-first
- single-operator oriented
- public-safe reference control plane
- suitable for demos, experiments, and further extension

Avoid positioning it as:

- multi-tenant SaaS
- production orchestration platform
- secure hosted execution layer

## Strong Demo Paths

Best features to demonstrate:

1. `run-task-template`
2. `run-pipeline`
3. `mark-needs-human`
4. `list-human-inbox`
5. `create-saved-query` + `apply-saved-query`
6. `/app`

## Likely Next Product Steps

If development continues, the highest-value next steps are:

1. better browser UX around `/app`
2. import / export for saved queries and project presets
3. explicit review queue actions in the UI
4. auth / multi-user decisions, if the scope expands
5. packaging / release polish

## Things Intentionally Not Solved Yet

- auth
- user accounts
- background process supervision
- remote worker pools
- multi-project policy engine
- rich front-end interactions
