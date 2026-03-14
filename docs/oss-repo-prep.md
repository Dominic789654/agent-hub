# OSS Repo Preparation

This document tracks what should be true before moving this branch into a dedicated public repository.

## Must-Have

- stable README
- demo instructions that actually run
- release checklist
- contribution guide
- security reporting guidance
- issue / PR templates
- explicit statement of current scope and non-goals

## Still Missing Before Broad Release

- final license decision
- repository description / topics
- screenshots or GIF for `/app`
- first public changelog or release notes
- example of a clean fresh install from scratch

Supporting docs now exist for:

- split strategy: `docs/oss-split-plan.md`
- license choice: `docs/license-recommendation.md`
- first release notes: `docs/release-notes-v0.1.0.md`

## Suggested Public Repo Description

Local-first agent task hub with SQLite queueing, dependency-aware dispatch, project task templates, pipelines, human inbox, and a thin dashboard.

## Suggested Initial Topics

- agents
- automation
- sqlite
- orchestration
- local-first
- python

## First Public Release Framing

Recommend positioning the first release as:

- experimental
- local-first
- single-operator oriented
- extensible OSS foundation

Do not position it as:

- production-grade hosted control plane
- multi-user secure platform
- enterprise workflow manager
