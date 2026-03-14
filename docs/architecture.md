# Architecture Overview

This repository keeps the scaffold's public-safe shape while landing a minimal working MVP.

## Implemented Slice

The current MVP lives under `src/agent_hub/` and centers on four modules:

- `db.py` bootstraps the local SQLite database
- `repository.py` manages task lifecycle, dependency edges, block propagation, and runtime state
- `dispatcher.py` claims and executes safe built-in task kinds
- `web.py` serves a tiny HTTP surface for health, status, and task listings
- `services/executors.py` routes built-in task kinds, project-backed local command execution, and project action templates
- `services/pipelines.py` instantiates project pipeline templates into queued task graphs

Supporting types live in `models.py`, and `cli.py` wires the slice together for local use.

## Scaffolded Extension Points

The repository still reserves these packages for future growth:

### `src/agent_hub/config/`

Configuration loading, validation, defaults, and environment mapping.

### `src/agent_hub/core/`

Shared domain logic that should stay independent of transports or storage adapters.

### `src/agent_hub/services/`

Optional adapters and orchestration integrations that depend on core logic rather than the other way around.

## Dependency Direction

The implemented MVP currently follows this shape:

```text
cli -> db -> repository <- dispatcher
                      ^
                      └-> web
dispatcher -> services/executors -> projects
```

As the project grows, the intended public-safe dependency flow remains:

```text
config -> core <- services
             ^
           tests
```

## Portability Notes

- use relative or caller-provided data directories
- avoid hard-coded host-specific assumptions
- keep example files synthetic and non-sensitive
- prefer standard library dependencies until a real integration requires more
