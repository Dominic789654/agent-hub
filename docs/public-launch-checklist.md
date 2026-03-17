# Public Launch Checklist

Use this checklist when the goal is not just "cut a release", but "make the repo understandable and safe to share publicly today".

## 1. Positioning

- [ ] README opening paragraph matches the real scope
- [ ] README explicitly says local-first, single-operator, OSS MVP
- [ ] README explicitly says what the repo is **not**
- [ ] homepage copy matches the same positioning as the README
- [ ] no public copy implies hosted SaaS, multi-tenant, or enterprise guarantees

## 2. Public Entry Points

- [ ] repo homepage is easy to scan in the first screenful
- [ ] README has direct links to the live site, demo page, and release
- [ ] GitHub Pages site is enabled and serving from workflow deploys
- [ ] `docs/index.html` loads and renders correctly
- [ ] `docs/demo.html` loads and renders correctly

## 3. Core Verification

- [ ] `pip install -e .[dev]` works in a fresh virtualenv
- [ ] `pytest` passes
- [ ] `python -m agent_hub --help` works
- [ ] `python -m agent_hub serve --port 8080` starts
- [ ] `python -m agent_hub dispatch` starts
- [ ] `http://127.0.0.1:8080/` renders
- [ ] `http://127.0.0.1:8080/app` renders
- [ ] `http://127.0.0.1:8080/dashboard` returns valid JSON

## 4. Demo Quality

- [ ] `docs/demo.md` matches the actual local flow
- [ ] `docs/demo.html` matches `docs/demo.md`
- [ ] example project registry still boots a usable sample flow
- [ ] task creation, task template, pipeline, human inbox, and saved query flows still work
- [ ] screenshots or diagrams on the homepage still match the implementation shape

## 5. Safety and Hygiene

- [ ] no private infra details remain in committed docs
- [ ] no tracked local state exists under `./.agent-hub/`
- [ ] no secrets, tokens, hostnames, or private repo references remain
- [ ] license, contributing, and security files are present
- [ ] public examples are synthetic and portable

## 6. Release and Site

- [ ] current release tag exists and points at the intended public baseline
- [ ] release notes describe the repo as an OSS MVP, not a finished platform
- [ ] GitHub Pages workflow succeeds on `main`
- [ ] live site is reachable at `https://dominic789654.github.io/agent-hub/`

## 7. Announce-Ready Check

- [ ] one-sentence description is clear
- [ ] one-paragraph description is clear
- [ ] first-time visitor can tell what problem the repo solves in under 30 seconds
- [ ] first-time visitor can find the demo path in under 30 seconds
- [ ] first-time visitor can tell the project boundaries and non-goals in under 30 seconds

## Suggested Launch Sentence

> agent-hub is a local-first control plane for routing and observing agent work across projects, with explicit queue state, dependency-aware dispatch, human handoff, and a thin dashboard.

## Suggested Public Framing

- Share it as an inspectable baseline, not as a finished platform
- Emphasize local-first and single-operator use
- Emphasize explicit queue state, routing, and handoff
- Avoid over-claiming production guarantees
