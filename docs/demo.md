# Demo Guide

This guide is for a quick local walkthrough of `agent-hub` as a **code-assistant multitask board**.

The intended usage is:

- run the board in the background
- open Codex or Claude Code in another terminal
- ask the assistant to place and inspect tasks for you through `agent-hub`

The goal is not to teach operators to type a long sequence of board commands by hand. The goal is to show how the assistant-first workflow is supposed to feel.

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
bash -n examples/demo-agent-repo/scripts/run_agent_task.sh
```

## 2. Start the Web Surface With the Agent-Driven Example

Use the example projects registry that models repo-agent pairs:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json serve --port 8080
```

Open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/app`
- `http://127.0.0.1:8080/dashboard`

## 3. Start the Dispatcher

In a second terminal:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dispatch
```

## 4. Open Your Assistant Terminal

Open Codex or Claude Code in another terminal in the same environment.

Then ask it to use the board for you.

Example prompts:

- `Create a Codex task in demo-codex to investigate why the local build script is flaky and summarize the likely root cause.`
- `Create a Claude task in demo-claude to review the proposed fix and call out operator-facing risks.`
- `Queue the review-then-implement pipeline in demo-codex for "Add a dry-run mode to the deployment helper".`

Under the hood, the assistant will call commands like:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-codex delegate-task --input "Investigate why the local build script is flaky and summarize the likely root cause"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-claude delegate-task --input "Review the proposed fix and call out any operator-facing risks"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-pipeline demo-codex review-then-implement --input "Add a dry-run mode to the deployment helper"
```

This demo uses wrapper scripts under `examples/demo-agent-repo/scripts/` as a stand-in for real tools like Claude Code, Codex, Kimi Code, or Qwen Code.

## 5. Ask The Assistant To Inspect Handoff

You can also ask the assistant to inspect the board and report back:

- `Show me the human inbox and explain which task needs manual routing.`
- `If anything failed, tell me whether I should retry it or mark it for manual review.`

Under the hood, those checks map to commands like:

```bash
TASK_ID=$(python -m agent_hub --projects-file examples/agent-driven-projects.example.json create-task "Manual review: choose agent" --kind noop | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
)
python -m agent_hub --projects-file examples/agent-driven-projects.example.json mark-needs-human "$TASK_ID" --note "operator must decide whether Codex or Claude should own this task"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json add-task-label "$TASK_ID" routing
python -m agent_hub --projects-file examples/agent-driven-projects.example.json add-task-note "$TASK_ID" "ambiguous ownership; human should choose executor"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json list-human-inbox
```

## 6. Ask The Assistant For Saved Views

Once the board has useful slices, the assistant can use saved queries to answer questions like:

- `Show only Codex-owned tasks.`
- `Show only tasks that need manual review.`

The underlying commands look like:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json create-saved-query tasks "Needs Human" --filter status=needs_human
python -m agent_hub --projects-file examples/agent-driven-projects.example.json create-saved-query tasks "Codex Tasks" --filter project_id=demo-codex
python -m agent_hub --projects-file examples/agent-driven-projects.example.json list-saved-queries
```

Use the returned query id:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json apply-saved-query <query-id>
```

## 7. Confirm The Board View

At any point, the assistant or operator can inspect the board state directly:

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dashboard
curl -s http://127.0.0.1:8080/dashboard | sed -n '1,80p'
```

## Expected Result

By the end of the demo you should see:

- multiple assistant-task records moving through one queue
- separate repo-agent pairs visible as different `project_id`s
- a pipeline showing serial assistant work
- a populated human inbox for ambiguous or manual-review cases
- saved queries that slice the board by assistant or handoff state

More importantly, you should be able to imagine the normal operating mode:

- you talk to Codex or Claude Code
- the assistant submits tasks into `agent-hub`
- the board becomes the shared visibility layer for many code-assistant tasks
