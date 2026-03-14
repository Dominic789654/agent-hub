# Demo Guide

This guide is for a quick local walkthrough of the current OSS MVP.

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 2. Start the Web Surface

```bash
python -m agent_hub serve --port 8080
```

Open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/app`
- `http://127.0.0.1:8080/dashboard`

## 3. Start the Dispatcher

In a second terminal:

```bash
python -m agent_hub dispatch
```

## 4. Queue Example Work

In a third terminal:

```bash
python -m agent_hub create-task "hello world" --kind echo --payload "hi"
python -m agent_hub run-task-template sample-project summarize-input --input "review this operator note"
python -m agent_hub run-pipeline sample-project sample-flow --input "demo"
```

## 5. Exercise Human Handoff

```bash
TASK_ID=$(python -m agent_hub create-task "manual review" --kind noop | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
)
python -m agent_hub mark-needs-human "$TASK_ID" --note "manual review required"
python -m agent_hub add-task-label "$TASK_ID" priority
python -m agent_hub add-task-note "$TASK_ID" "operator should inspect context"
python -m agent_hub list-human-inbox
```

## 6. Exercise Saved Queries

```bash
python -m agent_hub create-saved-query tasks "Needs Human" --filter status=needs_human
python -m agent_hub list-saved-queries
```

Use the returned query id:

```bash
python -m agent_hub apply-saved-query <query-id>
```

## 7. Confirm Dashboard Snapshot

```bash
python -m agent_hub dashboard
curl -s http://127.0.0.1:8080/dashboard | sed -n '1,80p'
```

## Expected Result

By the end of the demo you should see:

- tasks moving through the queue
- the browser app rendering current state
- a populated human inbox
- a saved query returning matching results
