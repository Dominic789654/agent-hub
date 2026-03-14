# Public Repo Commands

Use these commands when moving this OSS tree into a dedicated public repository.

## Recommended Flow

Assumptions:

- the new public repo already exists and is empty
- the chosen repo name is `agent-hub`
- you want a clean public baseline instead of exposing all intermediate history

## 1. Create a Clean Export Directory

```bash
mkdir -p /tmp/agent-hub-public
rsync -a --delete \
  --exclude '.git' \
  --exclude '.agent-hub' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  /tmp/agent-hub-oss-task-control/ /tmp/agent-hub-public/
```

## 2. Initialize the Public Repository

```bash
cd /tmp/agent-hub-public
git init
git checkout -b main
git add .
git commit -m "feat: initial public agent-hub MVP"
```

## 3. Connect the Public Remote

```bash
git remote add origin <PUBLIC_REPO_URL>
git push -u origin main
```

## 4. Tag the First Release

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 5. Publish the Release

Use the contents of:

- `docs/release-notes-v0.1.0.md`

## Optional Checks Before Push

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m pytest -q
python -m compileall src/agent_hub tests
```

## Suggested GitHub Metadata

Repository name:

- `agent-hub`

Description:

- `Local-first agent task hub with SQLite queueing, dependency-aware dispatch, task templates, pipelines, human inbox, saved queries, and a thin dashboard.`

Topics:

- `agents`
- `automation`
- `sqlite`
- `orchestration`
- `local-first`
- `python`
