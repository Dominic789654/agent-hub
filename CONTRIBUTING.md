# Contributing to agent-hub

Thanks for contributing.

This repo currently targets a small, local-first control plane. Please keep contributions aligned with that scope.

## Before You Start

- read `README.md`
- read `docs/architecture.md`
- read `docs/safety.md`
- prefer small, reviewable changes

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Validation

Run these before opening a PR:

```bash
python -m pytest -q
python -m compileall src/agent_hub tests
```

If you change docs-only files, say so clearly in the PR.

## Contribution Rules

- keep the project local-first
- avoid private or host-specific assumptions
- do not add secrets, credentials, or internal endpoints
- prefer standard library solutions unless an external dependency is clearly justified
- keep new features narrow and composable
- add tests for behavior changes
- update README or docs when user-facing behavior changes

## Scope Guidance

Good contributions:

- queue and dependency behavior
- dispatcher correctness
- dashboard and web UX improvements
- docs and examples
- test coverage
- small extensibility improvements

Out-of-scope changes unless discussed first:

- hosted SaaS assumptions
- multi-tenant auth systems
- opaque vendor-specific integrations
- large framework migrations

## Pull Requests

Please include:

- what changed
- why it changed
- how you validated it
- any follow-up work or known limitations

If the PR changes routes or commands, include concrete examples.
