# CLI Quick Reference

This page is the shortest practical reference for the `agent-hub` CLI.

## Start Here

Use the public demo registry first:

```bash
agent-hub version
agent-hub --projects-file examples/agent-driven-projects.example.json list-projects
agent-hub --projects-file examples/agent-driven-projects.example.json list-project-task-templates demo-codex
```

If those commands work, continue with the public demo flow.

## Recommended Public Demo Flow

### Terminal A

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json serve --port 8080
```

### Terminal B

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dispatch
```

### Manual task intake

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-codex delegate-task --input "Investigate why the local build script is flaky"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-pipeline demo-codex review-then-implement --input "Add a dry-run mode"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dashboard
```

## Most Common Commands

```bash
agent-hub --projects-file examples/agent-driven-projects.example.json list-projects
agent-hub --projects-file examples/agent-driven-projects.example.json list-human-inbox
agent-hub --projects-file examples/agent-driven-projects.example.json list-tasks --limit 20
agent-hub --projects-file examples/agent-driven-projects.example.json dashboard
agent-hub --projects-file examples/agent-driven-projects.example.json retry-task <task-id>
agent-hub --projects-file examples/agent-driven-projects.example.json cancel-task <task-id>
```

## Assistant-Driven Usage

The recommended operator experience is still assistant-first:

- you talk to Codex / Claude Code
- the assistant calls `run-task-template`, `run-pipeline`, `list-human-inbox`, and `dashboard`
- `agent-hub` remains the queue, routing, dependency, and visibility layer

## Public Demo Registry vs Bootstrapped Default

There are two different registry paths in the repo:

- `examples/agent-driven-projects.example.json`: canonical public demo path
- `.agent-hub/projects.json`: local bootstrapped default for low-level scaffold use

If you are following public docs, use the checked-in example registry explicitly.

## Advanced Commands

Useful once the basics are working:

```bash
agent-hub --projects-file examples/agent-driven-projects.example.json list-saved-queries
agent-hub --projects-file examples/agent-driven-projects.example.json create-saved-query tasks "Needs Human" --filter status=needs_human
agent-hub --projects-file examples/agent-driven-projects.example.json list-pipeline-runs
agent-hub --projects-file examples/agent-driven-projects.example.json show-pipeline-run <pipeline-run-id>
agent-hub --projects-file examples/agent-driven-projects.example.json mark-needs-human <task-id> --note "manual review required"
```
