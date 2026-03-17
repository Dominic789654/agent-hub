# Recommended Agent-Driven Usage

This document describes the usage pattern that best matches the current OSS slice of `agent-hub`.

The short version:

- use `agent-hub` as the control plane
- use your existing coding agents as repo-local executors
- let `agent-hub` queue, route, sequence, and expose the work

This is the most honest framing of the public MVP. `agent-hub` does not try to replace Claude Code, Codex, Kimi Code, or Qwen Code. It gives you one explicit queue and routing layer in front of them.

## Recommended Topology

Use three layers:

1. **Operator layer**
   - one human interface
   - natural-language requests
   - review and triage through dashboard / inbox / notes

2. **Control-plane layer**
   - `agent-hub serve`
   - `agent-hub dispatch`
   - task queue, dependencies, saved views, human handoff

3. **Executor layer**
   - repo-local agent wrappers
   - one wrapper per agent, or one wrapper per repo-agent pair
   - examples: Claude Code, Codex, Kimi Code, Qwen Code

## Why This Pattern Works

It maps directly onto the current implementation:

- `project_command` runs a project-level local command
- `task_templates` turn free-form input into bounded queued tasks
- `pipelines` let you sequence steps when one task must wait for another
- the dashboard and human inbox make failures and ambiguity visible

This means the clean public story is:

> `agent-hub` decides what should run, in what order, against which repo.  
> Your code agent decides how to do the actual work inside that repo.

## Recommended Setup

### 1. Keep the control plane in its own terminal

Terminal A:

```bash
python -m agent_hub serve --port 8080
```

Terminal B:

```bash
python -m agent_hub dispatch
```

### 2. Keep agent entrypoints inside each target repo

In each repo, create small wrapper scripts such as:

- `scripts/run_codex_task.sh`
- `scripts/run_claude_task.sh`
- `scripts/run_kimi_task.sh`
- `scripts/run_qwen_task.sh`

These wrappers should do whatever is natural for your local environment:

- call the agent CLI directly
- attach to `tmux`
- write prompts into a watched file
- invoke a repo-local automation script

The important point is not the exact vendor command. The important point is that `agent-hub` launches a stable local entrypoint that you control.

### 3. Register repo-agent pairs as projects

The current OSS model is simplest when each repo-agent combination is its own `project_id`.

Example:

```json
{
  "version": 1,
  "projects": [
    {
      "id": "trading-codex",
      "name": "Trading Repo via Codex",
      "path": "../unified-agent-trading",
      "description": "Run bounded tasks in the trading repo through Codex.",
      "tags": ["trading", "codex"],
      "executor": {
        "type": "local-command",
        "command": ["bash", "-lc", "./scripts/run_codex_task.sh '{task_id}' '{payload}'"],
        "task_templates": {
          "delegate-task": {
            "name": "Delegate Task",
            "description": "Send a free-form implementation request to Codex.",
            "title": "Codex task: {input}",
            "kind": "project_command",
            "payload": "{input}",
            "labels": ["agent", "codex"]
          }
        }
      },
      "enabled": true
    },
    {
      "id": "trading-claude",
      "name": "Trading Repo via Claude Code",
      "path": "../unified-agent-trading",
      "description": "Run bounded tasks in the trading repo through Claude Code.",
      "tags": ["trading", "claude"],
      "executor": {
        "type": "local-command",
        "command": ["bash", "-lc", "./scripts/run_claude_task.sh '{task_id}' '{payload}'"],
        "task_templates": {
          "delegate-task": {
            "name": "Delegate Task",
            "description": "Send a free-form implementation request to Claude Code.",
            "title": "Claude task: {input}",
            "kind": "project_command",
            "payload": "{input}",
            "labels": ["agent", "claude"]
          }
        }
      },
      "enabled": true
    }
  ]
}
```

This model is repetitive, but it is explicit and works well with the current public MVP.

## How to Launch Work

Once registered, use `task_templates` as the main intake path.

Example:

```bash
python -m agent_hub run-task-template trading-codex delegate-task --input "Investigate why PR 46 fails and prepare a fix plan"
python -m agent_hub run-task-template trading-claude delegate-task --input "Review the proposed fix and summarize risks"
```

This gives you:

- a queued record
- project routing
- run logs
- retry / cancel controls
- visibility in `/dashboard` and `/app`

## How to Handle Serial and Parallel Work

For serial work:

- create dependencies explicitly
- or define a pipeline that encodes the sequence

For parallel work:

- queue independent tasks against different `project_id`s
- let the dispatcher claim them independently

This is where `agent-hub` adds leverage: not by being the agent, but by giving one place to reason about order, visibility, and handoff.

## Good Public Defaults

For the public OSS version, the most robust recommendation is:

- keep wrappers repo-local
- keep prompts bounded
- keep each task tied to one repo and one agent
- use `needs_human` instead of infinite retry loops
- surface failures through inbox and notes rather than hiding them

## What This Public Repo Does Not Yet Do

The current OSS MVP does **not** yet provide:

- first-class built-in integrations for each vendor agent
- per-action free-form input on project actions
- a full multi-agent orchestration DSL
- hosted remote scheduling or auth-heavy production controls

So the right public message is:

> Bring your own local code agent.  
> Use `agent-hub` to queue, route, sequence, observe, and intervene.

## Suggested Public Sentence

> If you already use Claude Code, Codex, Kimi Code, or Qwen Code in local repos, `agent-hub` gives you one explicit control plane in front of them.
