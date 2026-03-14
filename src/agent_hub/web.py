from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from string import Template
from urllib.parse import parse_qs, urlparse

from agent_hub.config import Settings
from agent_hub.models import DashboardSnapshot, SUPPORTED_TASK_KINDS
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository
from agent_hub.services.pipelines import PipelineService
from agent_hub.services.task_templates import TaskTemplateService

HTML_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>agent-hub</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; }
      h1 { margin-bottom: 0.5rem; }
      a { color: #0969da; text-decoration: none; }
      a:hover { text-decoration: underline; }
      .summary { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin: 1.5rem 0; }
      .card { border: 1px solid #d0d7de; border-radius: 8px; padding: 0.9rem; background: #f6f8fa; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border-bottom: 1px solid #d8dee4; text-align: left; padding: 0.6rem; vertical-align: top; }
      code { white-space: nowrap; }
      .muted { color: #57606a; }
      ul { padding-left: 1.2rem; }
    </style>
  </head>
  <body>
    <h1>agent-hub</h1>
    <p class="muted">Local-first public-safe MVP surface for dispatcher status and tasks.</p>
    <p><a href="/app">Open dashboard app</a> · <a href="/dashboard">View dashboard JSON</a></p>
    <div class="summary">
      <div class="card"><strong>Dispatcher</strong><br>${dispatcher_state}</div>
      <div class="card"><strong>Heartbeat</strong><br>${heartbeat_at}</div>
      <div class="card"><strong>Queued</strong><br>${queued_count}</div>
      <div class="card"><strong>Ready</strong><br>${ready_queued_count}</div>
      <div class="card"><strong>Blocked Queue</strong><br>${blocked_queued_count}</div>
      <div class="card"><strong>Running</strong><br>${running_count}</div>
      <div class="card"><strong>Succeeded</strong><br>${succeeded_count}</div>
      <div class="card"><strong>Failed</strong><br>${failed_count}</div>
      <div class="card"><strong>Cancelled</strong><br>${cancelled_count}</div>
      <div class="card"><strong>Blocked Tasks</strong><br>${blocked_count}</div>
      <div class="card"><strong>Needs Human</strong><br>${needs_human_count}</div>
      <div class="card"><strong>Human Inbox</strong><br>${human_inbox_count}</div>
      <div class="card"><strong>Projects</strong><br>${project_count}</div>
      <div class="card"><strong>Pipeline Runs</strong><br>${pipeline_run_count}</div>
    </div>
    <p><strong>Note:</strong> ${note}</p>
    <h2>Configuration</h2>
    <ul>
      <li><strong>Data dir:</strong> <code>${data_dir}</code></li>
      <li><strong>Projects file:</strong> <code>${projects_file}</code></li>
    </ul>
    <h2>Projects</h2>
    <ul>
      ${project_rows}
    </ul>
    <h2>Create Task</h2>
    <form method="post" action="/tasks">
      <p>
        <label>Title<br><input type="text" name="title" required style="width: min(32rem, 100%);"></label>
      </p>
      <p>
        <label>Project<br>
          <select name="project_id">
            ${project_options}
          </select>
        </label>
      </p>
      <p>
        <label>Kind<br>
          <select name="kind">
            ${kind_options}
          </select>
        </label>
      </p>
      <p>
        <label>Payload<br><textarea name="payload" rows="3" style="width: min(40rem, 100%);"></textarea></label>
      </p>
      <p>
        <label>Depends On<br><input type="text" name="depends_on" placeholder="comma-separated task ids" style="width: min(40rem, 100%);"></label>
      </p>
      <p><button type="submit">Create task</button></p>
    </form>
    <h2>Human Inbox</h2>
    <table>
      <thead>
        <tr>
          <th>Project</th>
          <th>Task</th>
          <th>Status</th>
          <th>Reason</th>
          <th>Labels</th>
          <th>Latest Note</th>
        </tr>
      </thead>
      <tbody>
        ${human_inbox_rows}
      </tbody>
    </table>
    <h2>Tasks</h2>
    <table>
      <thead>
        <tr>
          <th>Project</th>
          <th>Pipeline Run</th>
          <th>Title</th>
          <th>Kind</th>
          <th>Status</th>
          <th>Attempts</th>
          <th>Updated</th>
          <th>Actions</th>
          <th>ID</th>
        </tr>
      </thead>
      <tbody>
        ${task_rows}
      </tbody>
    </table>
    <h2>Recent Pipeline Runs</h2>
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Project</th>
          <th>Pipeline</th>
          <th>Input</th>
          <th>Progress</th>
          <th>Updated</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${pipeline_run_rows}
      </tbody>
    </table>
    <h2>Recent Runs</h2>
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Task</th>
          <th>Status</th>
          <th>Started</th>
          <th>Finished</th>
        </tr>
      </thead>
      <tbody>
        ${run_rows}
      </tbody>
    </table>
  </body>
</html>
"""
)

APP_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>agent-hub dashboard</title>
    <style>
      :root { color-scheme: light dark; }
      body { font-family: system-ui, sans-serif; margin: 0; background: #f6f8fa; color: #24292f; }
      .page { max-width: 1200px; margin: 0 auto; padding: 1.25rem; }
      .topbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: 1rem; }
      .summary { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); margin: 1rem 0 1.5rem; }
      .card, .panel { border: 1px solid #d0d7de; border-radius: 10px; background: #ffffff; }
      .card { padding: 0.9rem; }
      .card strong { display: block; margin-bottom: 0.35rem; font-size: 0.9rem; color: #57606a; }
      .grid { display: grid; gap: 1rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .panel h2 { margin: 0; padding: 0.9rem 1rem; border-bottom: 1px solid #d8dee4; font-size: 1rem; }
      .panel .body { padding: 0.5rem 1rem 1rem; overflow: auto; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border-bottom: 1px solid #d8dee4; text-align: left; padding: 0.55rem 0.45rem; vertical-align: top; font-size: 0.92rem; }
      code { white-space: nowrap; }
      .muted { color: #57606a; }
      .pill { display: inline-block; border-radius: 999px; padding: 0.12rem 0.45rem; margin: 0 0.25rem 0.25rem 0; background: #ddf4ff; color: #0969da; font-size: 0.82rem; }
      .status { font-weight: 600; }
      .ok { color: #1a7f37; }
      .warn { color: #9a6700; }
      .bad { color: #cf222e; }
      a { color: #0969da; text-decoration: none; }
      a:hover { text-decoration: underline; }
      @media (max-width: 920px) { .grid { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="page">
      <div class="topbar">
        <div>
          <h1 style="margin:0;">agent-hub dashboard</h1>
          <div class="muted">Thin client powered by <code>/dashboard</code></div>
        </div>
        <div class="muted">
          <a href="/">Classic view</a> · <a href="/dashboard">JSON</a> ·
          <span id="refresh-state">loading…</span>
        </div>
      </div>
      <div class="summary" id="summary"></div>
      <div class="grid">
        <section class="panel">
          <h2>Human Inbox</h2>
          <div class="body"><table><thead><tr><th>Project</th><th>Task</th><th>Status</th><th>Reason</th><th>Labels</th></tr></thead><tbody id="human-inbox"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Saved Queries</h2>
          <div class="body"><table><thead><tr><th>Scope</th><th>Name</th><th>Filters</th></tr></thead><tbody id="saved-queries"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Recent Tasks</h2>
          <div class="body"><table><thead><tr><th>Project</th><th>Title</th><th>Status</th><th>Kind</th><th>Updated</th></tr></thead><tbody id="recent-tasks"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Pipeline Runs</h2>
          <div class="body"><table><thead><tr><th>Project</th><th>Pipeline</th><th>Progress</th><th>Updated</th></tr></thead><tbody id="pipeline-runs"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Recent Runs</h2>
          <div class="body"><table><thead><tr><th>Task</th><th>Status</th><th>Started</th><th>Finished</th></tr></thead><tbody id="recent-runs"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Configuration</h2>
          <div class="body"><table><tbody id="config"></tbody></table></div>
        </section>
      </div>
    </div>
    <script>
      const refreshState = document.getElementById("refresh-state");
      const esc = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
      const statusClass = (value) => {
        if (["succeeded", "idle", "running"].includes(value)) return "ok";
        if (["blocked", "needs_human", "cancelled"].includes(value)) return "warn";
        return "bad";
      };
      const setRows = (id, rows, colspan, empty) => {
        document.getElementById(id).innerHTML = rows.length ? rows.join("") : `<tr><td colspan="${colspan}" class="muted">${esc(empty)}</td></tr>`;
      };
      const render = (data) => {
        const s = data.status;
        document.getElementById("summary").innerHTML = [
          ["Dispatcher", s.dispatcher_state],
          ["Heartbeat", s.heartbeat_at || "never"],
          ["Queued", s.queued_count],
          ["Running", s.running_count],
          ["Failed", s.failed_count],
          ["Needs Human", s.needs_human_count],
          ["Blocked", s.blocked_count],
          ["Human Inbox", data.human_inbox.length],
          ["Pipeline Runs", data.recent_pipeline_runs.length],
          ["Saved Queries", data.saved_queries.length],
        ].map(([label, value]) => `<div class="card"><strong>${esc(label)}</strong><div class="status ${statusClass(String(value).toLowerCase())}">${esc(value)}</div></div>`).join("");

        setRows("human-inbox", data.human_inbox.map((item) =>
          `<tr>
            <td><code>${esc(item.task.project_id || "-")}</code></td>
            <td><a href="/tasks/${esc(item.task.id)}">${esc(item.task.title)}</a></td>
            <td class="status ${statusClass(item.task.status)}">${esc(item.task.status)}</td>
            <td>${esc(item.reason)}</td>
            <td>${(item.labels || []).map((label) => `<span class="pill">${esc(label)}</span>`).join("") || '<span class="muted">-</span>'}</td>
          </tr>`
        ), 5, "Human inbox is empty.");

        setRows("saved-queries", data.saved_queries.map((item) =>
          `<tr>
            <td><code>${esc(item.scope)}</code></td>
            <td><a href="/saved-queries/${esc(item.id)}/apply">${esc(item.name)}</a></td>
            <td><code>${esc(JSON.stringify(item.filters))}</code></td>
          </tr>`
        ), 3, "No saved queries yet.");

        setRows("recent-tasks", data.recent_tasks.map((task) =>
          `<tr>
            <td><code>${esc(task.project_id || "-")}</code></td>
            <td><a href="/tasks/${esc(task.id)}">${esc(task.title)}</a></td>
            <td class="status ${statusClass(task.status)}">${esc(task.status)}</td>
            <td><code>${esc(task.kind)}</code></td>
            <td>${esc(task.updated_at)}</td>
          </tr>`
        ), 5, "No tasks yet.");

        setRows("pipeline-runs", data.recent_pipeline_runs.map((item) => {
          const completed = item.succeeded_count + item.failed_count + item.cancelled_count + item.blocked_count + item.needs_human_count;
          return `<tr>
            <td><code>${esc(item.project_id)}</code></td>
            <td><a href="/pipeline-runs/${esc(item.id)}">${esc(item.pipeline_id)}</a></td>
            <td>${completed}/${item.task_count}</td>
            <td>${esc(item.updated_at)}</td>
          </tr>`;
        }), 4, "No pipeline runs yet.");

        setRows("recent-runs", data.recent_runs.map((item) =>
          `<tr>
            <td><a href="/tasks/${esc(item.task.id)}">${esc(item.task.title)}</a></td>
            <td class="status ${statusClass(item.run.status)}">${esc(item.run.status)}</td>
            <td>${esc(item.run.started_at)}</td>
            <td>${esc(item.run.finished_at || "-")}</td>
          </tr>`
        ), 4, "No runs yet.");

        document.getElementById("config").innerHTML = [
          ["Data Dir", data.config.data_dir],
          ["Projects File", data.config.projects_file],
          ["Database", data.config.db_path],
        ].map(([label, value]) => `<tr><th>${esc(label)}</th><td><code>${esc(value)}</code></td></tr>`).join("");
      };
      const load = async () => {
        refreshState.textContent = "refreshing…";
        try {
          const response = await fetch("/dashboard", { cache: "no-store" });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          render(await response.json());
          refreshState.textContent = `updated ${new Date().toLocaleTimeString()}`;
        } catch (error) {
          refreshState.textContent = `error: ${error}`;
        }
      };
      load();
      setInterval(load, 5000);
    </script>
  </body>
</html>
"""


class AgentHubHandler(BaseHTTPRequestHandler):
    task_repository: TaskRepository
    runtime_repository: RuntimeRepository
    project_registry: ProjectRegistry
    settings: Settings

    def do_GET(self) -> None:
        app = AgentHubApp(self.task_repository, self.runtime_repository, self.project_registry, self.settings)
        response = app.handle_get(self.path)
        if response.content_type.startswith("application/json"):
            self._write_json(response.status, response.payload, response.headers)
            return
        self._write_html(response.status, str(response.payload), response.headers)

    def do_POST(self) -> None:
        app = AgentHubApp(self.task_repository, self.runtime_repository, self.project_registry, self.settings)
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        content_type = self.headers.get("Content-Type", "")
        body = self.rfile.read(content_length)
        response = app.handle_post(self.path, body, content_type)
        if response.content_type.startswith("application/json"):
            self._write_json(response.status, response.payload, response.headers)
            return
        self._write_html(response.status, str(response.payload), response.headers)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _render_index(self) -> str:
        app = AgentHubApp(self.task_repository, self.runtime_repository, self.project_registry, self.settings)
        response = app.handle_get("/")
        return str(response.payload)

    def _write_json(self, status: HTTPStatus, payload: object, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, status: HTTPStatus, body: str, headers: dict[str, str] | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def make_server(
    host: str,
    port: int,
    task_repository: TaskRepository,
    runtime_repository: RuntimeRepository,
    project_registry: ProjectRegistry,
    settings: Settings,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredAgentHubHandler",
        (AgentHubHandler,),
        {
            "task_repository": task_repository,
            "runtime_repository": runtime_repository,
            "project_registry": project_registry,
            "settings": settings,
        },
    )
    return ThreadingHTTPServer((host, port), handler)


class AgentHubResponse:
    def __init__(
        self,
        status: HTTPStatus,
        content_type: str,
        payload: object,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.content_type = content_type
        self.payload = payload
        self.headers = headers or {}


class AgentHubApp:
    def __init__(
        self,
        task_repository: TaskRepository,
        runtime_repository: RuntimeRepository,
        project_registry: ProjectRegistry,
        settings: Settings,
    ) -> None:
        self.task_repository = task_repository
        self.runtime_repository = runtime_repository
        self.project_registry = project_registry
        self.settings = settings
        self.pipeline_service = PipelineService(task_repository=task_repository, project_registry=project_registry)
        self.task_template_service = TaskTemplateService(task_repository=task_repository, project_registry=project_registry)

    def handle_get(self, path: str) -> AgentHubResponse:
        parsed = urlparse(path)
        if parsed.path == "/healthz":
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"ok": True})
        if parsed.path == "/status":
            status = self.runtime_repository.get_status(self.task_repository, self.project_registry)
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", status.to_dict())
        if parsed.path == "/dashboard":
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", self._build_dashboard().to_dict())
        if parsed.path == "/app":
            return AgentHubResponse(HTTPStatus.OK, "text/html; charset=utf-8", self._render_app())
        if parsed.path == "/config":
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", self.settings.to_dict())
        if parsed.path == "/projects":
            projects = [project.to_dict() for project in self.project_registry.list_projects()]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"projects": projects})
        if parsed.path.startswith("/projects/") and parsed.path.endswith("/actions"):
            project_id = parsed.path.removeprefix("/projects/")[: -len("/actions")].strip("/")
            if not project_id or self.project_registry.get_project(project_id) is None:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "project not found"})
            actions = [action.to_dict() for action in self.project_registry.list_project_actions(project_id)]
            return AgentHubResponse(
                HTTPStatus.OK,
                "application/json; charset=utf-8",
                {"project_id": project_id, "actions": actions},
            )
        if parsed.path.startswith("/projects/") and parsed.path.endswith("/pipelines"):
            project_id = parsed.path.removeprefix("/projects/")[: -len("/pipelines")].strip("/")
            if not project_id or self.project_registry.get_project(project_id) is None:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "project not found"})
            pipelines = [pipeline.to_dict() for pipeline in self.project_registry.list_project_pipelines(project_id)]
            return AgentHubResponse(
                HTTPStatus.OK,
                "application/json; charset=utf-8",
                {"project_id": project_id, "pipelines": pipelines},
            )
        if parsed.path.startswith("/projects/") and parsed.path.endswith("/task-templates"):
            project_id = parsed.path.removeprefix("/projects/")[: -len("/task-templates")].strip("/")
            if not project_id or self.project_registry.get_project(project_id) is None:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "project not found"})
            templates = [template.to_dict() for template in self.project_registry.list_project_task_templates(project_id)]
            return AgentHubResponse(
                HTTPStatus.OK,
                "application/json; charset=utf-8",
                {"project_id": project_id, "task_templates": templates},
            )
        if parsed.path == "/tasks":
            query = parse_qs(parsed.query)
            limit = _coerce_limit(query.get("limit", ["100"])[0])
            project_id = _coerce_optional_query(query, "project_id")
            status = _coerce_optional_query(query, "status")
            kind = _coerce_optional_query(query, "kind")
            pipeline_run_id = _coerce_optional_query(query, "pipeline_run_id")
            tasks = [
                task.to_dict()
                for task in self.task_repository.list_tasks(
                    limit=limit,
                    project_id=project_id,
                    status=status,
                    kind=kind,
                    pipeline_run_id=pipeline_run_id,
                )
            ]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"tasks": tasks})
        if parsed.path == "/runs":
            query = parse_qs(parsed.query)
            limit = _coerce_limit(query.get("limit", ["20"])[0])
            runs = [item.to_dict() for item in self.task_repository.list_recent_runs(limit=limit)]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"runs": runs})
        if parsed.path == "/human-inbox":
            query = parse_qs(parsed.query)
            limit = _coerce_limit(query.get("limit", ["20"])[0])
            project_id = _coerce_optional_query(query, "project_id")
            items = [item.to_dict() for item in self.task_repository.list_human_inbox(limit=limit, project_id=project_id)]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"items": items})
        if parsed.path == "/saved-queries":
            query = parse_qs(parsed.query)
            limit = _coerce_limit(query.get("limit", ["20"])[0])
            scope = _coerce_optional_query(query, "scope")
            queries = [item.to_dict() for item in self.task_repository.list_saved_queries(scope=scope, limit=limit)]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"saved_queries": queries})
        if parsed.path.startswith("/saved-queries/"):
            if parsed.path.endswith("/apply"):
                query_id = parsed.path.removeprefix("/saved-queries/")[: -len("/apply")].strip("/")
                if not query_id:
                    return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
                query = parse_qs(parsed.query)
                limit = _coerce_limit(query.get("limit", ["20"])[0])
                try:
                    result = self.task_repository.apply_saved_query(query_id, limit=limit)
                except KeyError:
                    return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "saved query not found"})
                return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", result.to_dict())
            query_id = parsed.path.removeprefix("/saved-queries/").strip("/")
            if not query_id:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
            query = self.task_repository.get_saved_query(query_id)
            if query is None:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "saved query not found"})
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", query.to_dict())
        if parsed.path == "/pipeline-runs":
            query = parse_qs(parsed.query)
            limit = _coerce_limit(query.get("limit", ["20"])[0])
            project_id = _coerce_optional_query(query, "project_id")
            pipeline_id = _coerce_optional_query(query, "pipeline_id")
            runs = [
                item.to_dict()
                for item in self.task_repository.list_pipeline_runs(
                    limit=limit,
                    project_id=project_id,
                    pipeline_id=pipeline_id,
                )
            ]
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"pipeline_runs": runs})
        if parsed.path.startswith("/pipeline-runs/"):
            pipeline_run_id = parsed.path.removeprefix("/pipeline-runs/").strip("/")
            if not pipeline_run_id:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
            detail = self.task_repository.get_pipeline_run_detail(pipeline_run_id)
            if detail is None:
                return AgentHubResponse(
                    HTTPStatus.NOT_FOUND,
                    "application/json; charset=utf-8",
                    {"error": "pipeline run not found"},
                )
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", detail.to_dict())
        if parsed.path.startswith("/tasks/"):
            return self._handle_task_detail(parsed.path)
        if parsed.path == "/":
            return AgentHubResponse(HTTPStatus.OK, "text/html; charset=utf-8", self._render_index())
        return AgentHubResponse(
            HTTPStatus.NOT_FOUND,
            "application/json; charset=utf-8",
            {"error": "not found"},
        )

    def handle_post(self, path: str, body: bytes, content_type: str) -> AgentHubResponse:
        parsed = urlparse(path)
        if parsed.path == "/tasks":
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type == "application/json":
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return AgentHubResponse(
                        HTTPStatus.BAD_REQUEST,
                        "application/json; charset=utf-8",
                        {"error": "invalid json body"},
                    )
                return self._create_task_response(payload, redirect=False)

            if media_type == "application/x-www-form-urlencoded":
                form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
                payload = {key: values[0] if values else "" for key, values in form.items()}
                return self._create_task_response(payload, redirect=True)

            return AgentHubResponse(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "application/json; charset=utf-8",
                {"error": "unsupported content type"},
            )

        if parsed.path == "/pipelines":
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                return AgentHubResponse(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "application/json; charset=utf-8",
                    {"error": "unsupported content type"},
                )
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "invalid json body"},
                )
            if not isinstance(payload, dict):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "request body must be an object"},
                )
            project_id = str(payload.get("project_id", "")).strip()
            pipeline_id = str(payload.get("pipeline_id", "")).strip()
            input_value = str(payload.get("input", ""))
            if not project_id or not pipeline_id:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "project_id and pipeline_id are required"},
                )
            try:
                result = self.pipeline_service.instantiate(project_id, pipeline_id, input_value=input_value)
            except ValueError as exc:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": str(exc)},
                )
            return AgentHubResponse(HTTPStatus.CREATED, "application/json; charset=utf-8", result.to_dict())

        if parsed.path == "/task-templates":
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                return AgentHubResponse(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "application/json; charset=utf-8",
                    {"error": "unsupported content type"},
                )
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "invalid json body"},
                )
            if not isinstance(payload, dict):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "request body must be an object"},
                )
            project_id = str(payload.get("project_id", "")).strip()
            template_id = str(payload.get("template_id", "")).strip()
            input_value = str(payload.get("input", ""))
            depends_on = _coerce_dependency_ids(payload.get("depends_on", []))
            if not project_id or not template_id:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "project_id and template_id are required"},
                )
            try:
                result = self.task_template_service.instantiate(
                    project_id,
                    template_id,
                    input_value=input_value,
                    depends_on=depends_on,
                )
            except ValueError as exc:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": str(exc)},
                )
            return AgentHubResponse(HTTPStatus.CREATED, "application/json; charset=utf-8", result.to_dict())

        if parsed.path == "/saved-queries":
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                return AgentHubResponse(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "application/json; charset=utf-8",
                    {"error": "unsupported content type"},
                )
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "invalid json body"},
                )
            if not isinstance(payload, dict):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "request body must be an object"},
                )
            scope = str(payload.get("scope", "")).strip()
            name = str(payload.get("name", "")).strip()
            description = str(payload.get("description", ""))
            raw_filters = payload.get("filters", {})
            if not isinstance(raw_filters, dict):
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "filters must be an object"},
                )
            try:
                query = self.task_repository.create_saved_query(
                    scope,
                    name,
                    description=description,
                    filters={str(key): str(value) for key, value in raw_filters.items()},
                )
            except ValueError as exc:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": str(exc)},
                )
            return AgentHubResponse(HTTPStatus.CREATED, "application/json; charset=utf-8", query.to_dict())

        if parsed.path.startswith("/saved-queries/") and parsed.path.endswith("/delete"):
            query_id = parsed.path.removeprefix("/saved-queries/")[: -len("/delete")].strip("/")
            if not query_id:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
            try:
                self.task_repository.delete_saved_query(query_id)
            except KeyError:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "saved query not found"})
            return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", {"deleted": True, "id": query_id})

        if parsed.path.startswith("/pipeline-runs/"):
            suffix = parsed.path.removeprefix("/pipeline-runs/").strip("/")
            if suffix.endswith("/retry"):
                pipeline_run_id = suffix[: -len("/retry")].strip("/")
                return self._handle_pipeline_run_action(pipeline_run_id, action="retry", content_type=content_type)
            if suffix.endswith("/cancel"):
                pipeline_run_id = suffix[: -len("/cancel")].strip("/")
                return self._handle_pipeline_run_action(pipeline_run_id, action="cancel", content_type=content_type)
            if suffix.endswith("/notes"):
                pipeline_run_id = suffix[: -len("/notes")].strip("/")
                return self._handle_pipeline_run_annotation(pipeline_run_id, action="add_note", body=body, content_type=content_type)
            if suffix.endswith("/labels"):
                pipeline_run_id = suffix[: -len("/labels")].strip("/")
                return self._handle_pipeline_run_annotation(pipeline_run_id, action="add_label", body=body, content_type=content_type)
            if suffix.endswith("/labels/remove"):
                pipeline_run_id = suffix[: -len("/labels/remove")].strip("/")
                return self._handle_pipeline_run_annotation(pipeline_run_id, action="remove_label", body=body, content_type=content_type)

        if parsed.path.startswith("/tasks/"):
            suffix = parsed.path.removeprefix("/tasks/").strip("/")
            if suffix.endswith("/retry"):
                task_id = suffix[: -len("/retry")].strip("/")
                return self._handle_task_action(task_id, action="retry", body=body, content_type=content_type)
            if suffix.endswith("/cancel"):
                task_id = suffix[: -len("/cancel")].strip("/")
                return self._handle_task_action(task_id, action="cancel", body=body, content_type=content_type)
            if suffix.endswith("/needs-human"):
                task_id = suffix[: -len("/needs-human")].strip("/")
                return self._handle_task_action(task_id, action="needs_human", body=body, content_type=content_type)
            if suffix.endswith("/notes"):
                task_id = suffix[: -len("/notes")].strip("/")
                return self._handle_task_annotation(task_id, action="add_note", body=body, content_type=content_type)
            if suffix.endswith("/labels"):
                task_id = suffix[: -len("/labels")].strip("/")
                return self._handle_task_annotation(task_id, action="add_label", body=body, content_type=content_type)
            if suffix.endswith("/labels/remove"):
                task_id = suffix[: -len("/labels/remove")].strip("/")
                return self._handle_task_annotation(task_id, action="remove_label", body=body, content_type=content_type)

        return AgentHubResponse(
            HTTPStatus.NOT_FOUND,
            "application/json; charset=utf-8",
            {"error": "not found"},
        )

    def _handle_pipeline_run_action(self, pipeline_run_id: str, action: str, content_type: str) -> AgentHubResponse:
        if not pipeline_run_id:
            return AgentHubResponse(
                HTTPStatus.NOT_FOUND,
                "application/json; charset=utf-8",
                {"error": "not found"},
            )
        media_type = content_type.split(";", 1)[0].strip().lower()
        wants_redirect = media_type == "application/x-www-form-urlencoded"
        try:
            if action == "retry":
                detail = self.task_repository.retry_pipeline_run(pipeline_run_id)
            elif action == "cancel":
                detail = self.task_repository.cancel_pipeline_run(pipeline_run_id)
            else:
                return AgentHubResponse(
                    HTTPStatus.NOT_FOUND,
                    "application/json; charset=utf-8",
                    {"error": "not found"},
                )
        except KeyError:
            return AgentHubResponse(
                HTTPStatus.NOT_FOUND,
                "application/json; charset=utf-8",
                {"error": "pipeline run not found"},
            )
        if wants_redirect:
            return AgentHubResponse(
                HTTPStatus.SEE_OTHER,
                "text/html; charset=utf-8",
                "",
                headers={"Location": "/"},
            )
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", detail.to_dict())

    def _handle_task_annotation(self, task_id: str, action: str, body: bytes, content_type: str) -> AgentHubResponse:
        if not task_id:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
        payload, wants_redirect, error = _decode_body_payload(body, content_type)
        if error is not None:
            return error
        try:
            if action == "add_note":
                note = self.task_repository.add_task_note(task_id, str(payload.get("body", "")))
                result: object = note.to_dict()
            elif action == "add_label":
                labels = self.task_repository.add_task_label(task_id, str(payload.get("label", "")))
                result = {"task_id": task_id, "labels": labels}
            elif action == "remove_label":
                labels = self.task_repository.remove_task_label(task_id, str(payload.get("label", "")))
                result = {"task_id": task_id, "labels": labels}
            else:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
        except KeyError:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "task not found"})
        except ValueError as exc:
            return AgentHubResponse(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", {"error": str(exc)})
        if wants_redirect:
            return AgentHubResponse(HTTPStatus.SEE_OTHER, "text/html; charset=utf-8", "", headers={"Location": f"/tasks/{task_id}"})
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", result)

    def _handle_pipeline_run_annotation(self, pipeline_run_id: str, action: str, body: bytes, content_type: str) -> AgentHubResponse:
        if not pipeline_run_id:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
        payload, wants_redirect, error = _decode_body_payload(body, content_type)
        if error is not None:
            return error
        try:
            if action == "add_note":
                note = self.task_repository.add_pipeline_run_note(pipeline_run_id, str(payload.get("body", "")))
                result: object = note.to_dict()
            elif action == "add_label":
                labels = self.task_repository.add_pipeline_run_label(pipeline_run_id, str(payload.get("label", "")))
                result = {"pipeline_run_id": pipeline_run_id, "labels": labels}
            elif action == "remove_label":
                labels = self.task_repository.remove_pipeline_run_label(pipeline_run_id, str(payload.get("label", "")))
                result = {"pipeline_run_id": pipeline_run_id, "labels": labels}
            else:
                return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
        except KeyError:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "pipeline run not found"})
        except ValueError as exc:
            return AgentHubResponse(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", {"error": str(exc)})
        if wants_redirect:
            return AgentHubResponse(HTTPStatus.SEE_OTHER, "text/html; charset=utf-8", "", headers={"Location": f"/pipeline-runs/{pipeline_run_id}"})
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", result)

    def _handle_task_action(self, task_id: str, action: str, body: bytes, content_type: str) -> AgentHubResponse:
        if not task_id:
            return AgentHubResponse(
                HTTPStatus.NOT_FOUND,
                "application/json; charset=utf-8",
                {"error": "not found"},
            )
        media_type = content_type.split(";", 1)[0].strip().lower()
        wants_redirect = media_type == "application/x-www-form-urlencoded"
        try:
            if action == "retry":
                task = self.task_repository.retry_task(task_id)
            elif action == "cancel":
                task = self.task_repository.cancel_task(task_id)
            elif action == "needs_human":
                note = ""
                if media_type == "application/json" and body:
                    try:
                        payload = json.loads(body.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return AgentHubResponse(
                            HTTPStatus.BAD_REQUEST,
                            "application/json; charset=utf-8",
                            {"error": "invalid json body"},
                        )
                    if isinstance(payload, dict):
                        note = str(payload.get("note", ""))
                task = self.task_repository.mark_needs_human(task_id, note=note)
            else:
                return AgentHubResponse(
                    HTTPStatus.NOT_FOUND,
                    "application/json; charset=utf-8",
                    {"error": "not found"},
                )
        except KeyError:
            return AgentHubResponse(
                HTTPStatus.NOT_FOUND,
                "application/json; charset=utf-8",
                {"error": "task not found"},
            )
        except ValueError as exc:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": str(exc)},
            )
        if wants_redirect:
            return AgentHubResponse(
                HTTPStatus.SEE_OTHER,
                "text/html; charset=utf-8",
                "",
                headers={"Location": "/"},
            )
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", task.to_dict())

    def _render_index(self) -> str:
        dashboard = self._build_dashboard()
        status = dashboard.status
        projects = self.project_registry.list_projects()
        human_inbox = dashboard.human_inbox
        tasks = dashboard.recent_tasks
        pipeline_runs = dashboard.recent_pipeline_runs
        recent_runs = dashboard.recent_runs
        human_inbox_rows = "".join(
            (
                "<tr>"
                f"<td><code>{_escape(item.task.project_id or '-')}</code></td>"
                f"<td><a href=\"/tasks/{_escape(item.task.id)}\">{_escape(item.task.title)}</a></td>"
                f"<td>{_escape(item.task.status.value)}</td>"
                f"<td>{_escape(item.reason)}</td>"
                f"<td>{_escape(', '.join(item.labels) or '-')}</td>"
                f"<td>{_escape(item.latest_note.body if item.latest_note is not None else '-')}</td>"
                "</tr>"
            )
            for item in human_inbox
        ) or '<tr><td colspan="6" class="muted">Human inbox is empty.</td></tr>'
        rows = "".join(
            (
                "<tr>"
                f"<td><code>{_escape(task.project_id or '-')}</code></td>"
                f"<td>{self._render_pipeline_run_link(task.pipeline_run_id)}</td>"
                f"<td><a href=\"/tasks/{_escape(task.id)}\">{_escape(task.title)}</a></td>"
                f"<td><code>{_escape(task.kind)}</code></td>"
                f"<td>{_escape(task.status.value)}</td>"
                f"<td>{task.attempt_count}</td>"
                f"<td>{_escape(task.updated_at)}</td>"
                f"<td>{self._render_task_actions(task)}</td>"
                f"<td><code><a href=\"/tasks/{_escape(task.id)}\">{_escape(task.id)}</a></code></td>"
                "</tr>"
            )
            for task in tasks
        ) or '<tr><td colspan="9" class="muted">No tasks yet.</td></tr>'
        pipeline_run_rows = "".join(
            (
                "<tr>"
                f"<td><code><a href=\"/pipeline-runs/{_escape(item.id)}\">{_escape(item.id)}</a></code></td>"
                f"<td><code>{_escape(item.project_id)}</code></td>"
                f"<td><code>{_escape(item.pipeline_id)}</code></td>"
                f"<td>{_escape(item.input_value or '-')}</td>"
                f"<td>{_escape(self._render_pipeline_progress(item))}</td>"
                f"<td>{_escape(item.updated_at)}</td>"
                f"<td>{self._render_pipeline_run_actions(item)}</td>"
                "</tr>"
            )
            for item in pipeline_runs
        ) or '<tr><td colspan="7" class="muted">No pipeline runs yet.</td></tr>'
        run_rows = "".join(
            (
                "<tr>"
                f"<td><code><a href=\"/tasks/{_escape(item.task.id)}/runs/latest\">#{item.run.id}</a></code></td>"
                f"<td><a href=\"/tasks/{_escape(item.task.id)}\">{_escape(item.task.title)}</a></td>"
                f"<td>{_escape(item.run.status.value)}</td>"
                f"<td>{_escape(item.run.started_at)}</td>"
                f"<td>{_escape(item.run.finished_at or '-')}</td>"
                "</tr>"
            )
            for item in recent_runs
        ) or '<tr><td colspan="5" class="muted">No runs yet.</td></tr>'
        project_rows = "".join(
            f"<li><code>{_escape(project.id)}</code> — {_escape(project.name)} <span class=\"muted\">({_escape(project.path)})</span></li>"
            for project in projects
        ) or '<li class="muted">No enabled projects registered.</li>'
        project_options = "".join(
            f'<option value="{_escape(project.id)}">{_escape(project.name)} ({_escape(project.id)})</option>'
            for project in projects
        )
        project_options = f'<option value="">No project</option>{project_options}'
        kind_options = "".join(
            f'<option value="{_escape(kind)}">{_escape(kind)}</option>'
            for kind in sorted(SUPPORTED_TASK_KINDS)
        )
        return HTML_TEMPLATE.substitute(
            dispatcher_state=_escape(status.dispatcher_state),
            heartbeat_at=_escape(status.heartbeat_at or "never"),
            project_count=status.project_count,
            queued_count=status.queued_count,
            ready_queued_count=status.ready_queued_count,
            blocked_queued_count=status.blocked_queued_count,
            running_count=status.running_count,
            succeeded_count=status.succeeded_count,
            failed_count=status.failed_count,
            cancelled_count=status.cancelled_count,
            blocked_count=status.blocked_count,
            needs_human_count=status.needs_human_count,
            human_inbox_count=self.task_repository.count_human_inbox(),
            note=_escape(status.note or "none"),
            data_dir=_escape(str(self.settings.data_dir)),
            projects_file=_escape(str(self.settings.projects_file)),
            pipeline_run_count=self.task_repository.count_pipeline_runs(),
            project_rows=project_rows,
            project_options=project_options,
            kind_options=kind_options,
            human_inbox_rows=human_inbox_rows,
            task_rows=rows,
            pipeline_run_rows=pipeline_run_rows,
            run_rows=run_rows,
        )

    def _build_dashboard(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            status=self.runtime_repository.get_status(self.task_repository, self.project_registry),
            config=self.settings.to_dict(),
            recent_tasks=self.task_repository.list_tasks(limit=20),
            human_inbox=self.task_repository.list_human_inbox(limit=10),
            recent_pipeline_runs=self.task_repository.list_pipeline_runs(limit=10),
            recent_runs=self.task_repository.list_recent_runs(limit=10),
            saved_queries=self.task_repository.list_saved_queries(limit=10),
        )

    @staticmethod
    def _render_app() -> str:
        return APP_TEMPLATE

    @staticmethod
    def _render_pipeline_run_link(pipeline_run_id: str | None) -> str:
        if not pipeline_run_id:
            return '<span class="muted">-</span>'
        escaped = _escape(pipeline_run_id)
        return f'<code><a href="/pipeline-runs/{escaped}">{escaped}</a></code>'

    @staticmethod
    def _render_pipeline_progress(pipeline_run: object) -> str:
        item = pipeline_run
        completed = getattr(item, "succeeded_count") + getattr(item, "failed_count") + getattr(item, "cancelled_count") + getattr(item, "blocked_count") + getattr(item, "needs_human_count")
        return f"{completed}/{getattr(item, 'task_count')} done; queued={getattr(item, 'queued_count')}; running={getattr(item, 'running_count')}"

    @staticmethod
    def _render_pipeline_run_actions(pipeline_run: object) -> str:
        run_id = getattr(pipeline_run, "id")
        queued_count = getattr(pipeline_run, "queued_count")
        blocked_count = getattr(pipeline_run, "blocked_count")
        needs_human_count = getattr(pipeline_run, "needs_human_count")
        failed_count = getattr(pipeline_run, "failed_count")
        cancelled_count = getattr(pipeline_run, "cancelled_count")
        actions: list[str] = []
        if queued_count or blocked_count or needs_human_count:
            actions.append(
                f'<form method="post" action="/pipeline-runs/{_escape(run_id)}/cancel">'
                '<button type="submit">Cancel run</button>'
                "</form>"
            )
        if failed_count or cancelled_count or blocked_count or needs_human_count:
            actions.append(
                f'<form method="post" action="/pipeline-runs/{_escape(run_id)}/retry">'
                '<button type="submit">Retry run</button>'
                "</form>"
            )
        return " ".join(actions) if actions else '<span class="muted">-</span>'

    def _create_task_response(self, payload: object, *, redirect: bool) -> AgentHubResponse:
        if not isinstance(payload, dict):
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": "request body must be an object"},
            )

        raw_title = str(payload.get("title", "")).strip()
        raw_kind = str(payload.get("kind", "noop")).strip() or "noop"
        raw_payload = str(payload.get("payload", ""))
        raw_project_id = str(payload.get("project_id", "")).strip()
        raw_depends_on = payload.get("depends_on", [])
        project_id = raw_project_id or None
        dependency_ids = _coerce_dependency_ids(raw_depends_on)

        if not raw_title:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": "title is required"},
            )
        if raw_kind == "project_command" and not project_id:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": "project_command tasks require project_id"},
            )
        if raw_kind == "project_action":
            if not project_id:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "project_action tasks require project_id"},
                )
            if not raw_payload:
                return AgentHubResponse(
                    HTTPStatus.BAD_REQUEST,
                    "application/json; charset=utf-8",
                    {"error": "project_action tasks require payload with the action id"},
                )
        if project_id and self.project_registry.get_project(project_id) is None:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": f"unknown project_id: {project_id}"},
            )
        if raw_kind == "project_action" and project_id and self.project_registry.get_project_action(project_id, raw_payload) is None:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": f"unknown project action: {raw_payload}"},
            )

        try:
            task = self.task_repository.create_task(
                title=raw_title,
                kind=raw_kind,
                payload=raw_payload,
                project_id=project_id,
                depends_on=dependency_ids,
            )
        except ValueError as exc:
            return AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": str(exc)},
            )

        if redirect:
            return AgentHubResponse(
                HTTPStatus.SEE_OTHER,
                "text/html; charset=utf-8",
                "",
                headers={"Location": "/"},
            )
        return AgentHubResponse(HTTPStatus.CREATED, "application/json; charset=utf-8", task.to_dict())

    def _handle_task_detail(self, path: str) -> AgentHubResponse:
        suffix = path.removeprefix("/tasks/")
        if suffix.endswith("/runs/latest"):
            task_id = suffix[: -len("/runs/latest")].strip("/")
            return self._handle_latest_run(task_id)
        if suffix.endswith("/neighbors"):
            task_id = suffix[: -len("/neighbors")].strip("/")
            return self._handle_task_neighbors(task_id)

        task_id = suffix.strip("/")
        if not task_id:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "not found"})
        detail = self.task_repository.get_task_detail(task_id)
        if detail is None:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "task not found"})
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", detail.to_dict())

    def _handle_latest_run(self, task_id: str) -> AgentHubResponse:
        detail = self.task_repository.get_task_detail(task_id)
        if detail is None:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "task not found"})
        if not detail.runs:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "run not found"})
        latest = detail.runs[0]
        return AgentHubResponse(
            HTTPStatus.OK,
            "application/json; charset=utf-8",
            {"task_id": task_id, "run": latest.to_dict(), "log": latest.log},
        )

    def _handle_task_neighbors(self, task_id: str) -> AgentHubResponse:
        neighbors = self.task_repository.get_task_neighbors(task_id)
        if neighbors is None:
            return AgentHubResponse(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", {"error": "task not found"})
        return AgentHubResponse(HTTPStatus.OK, "application/json; charset=utf-8", neighbors.to_dict())

    def _render_task_actions(self, task: object) -> str:
        task_id = getattr(task, "id")
        status = getattr(task, "status").value
        cancel_form = (
            f'<form method="post" action="/tasks/{_escape(task_id)}/cancel">'
            '<button type="submit">Cancel</button>'
            "</form>"
        )
        retry_form = (
            f'<form method="post" action="/tasks/{_escape(task_id)}/retry">'
            '<button type="submit">Retry</button>'
            "</form>"
        )
        needs_human_form = (
            f'<form method="post" action="/tasks/{_escape(task_id)}/needs-human">'
            '<button type="submit">Needs human</button>'
            "</form>"
        )
        if status == "queued":
            return f"{cancel_form} {needs_human_form}"
        if status in {"failed", "succeeded", "cancelled"}:
            return f"{retry_form} {needs_human_form}"
        if status == "blocked":
            return retry_form
        if status == "needs_human":
            return retry_form
        return '<span class="muted">-</span>'


def _coerce_limit(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        return 100
    return max(1, min(value, 500))


def _coerce_dependency_ids(raw: object) -> list[str]:
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        values = raw.split(",")
    elif raw is None:
        values = []
    else:
        values = [str(raw)]
    dependency_ids: list[str] = []
    for item in values:
        task_id = str(item).strip()
        if task_id and task_id not in dependency_ids:
            dependency_ids.append(task_id)
    return dependency_ids


def _coerce_optional_query(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key, [])
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


def _decode_body_payload(body: bytes, content_type: str) -> tuple[dict[str, str], bool, AgentHubResponse | None]:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}, False, AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": "invalid json body"},
            )
        if not isinstance(payload, dict):
            return {}, False, AgentHubResponse(
                HTTPStatus.BAD_REQUEST,
                "application/json; charset=utf-8",
                {"error": "request body must be an object"},
            )
        return {str(key): str(value) for key, value in payload.items()}, False, None
    if media_type == "application/x-www-form-urlencoded":
        form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        return {key: values[0] if values else "" for key, values in form.items()}, True, None
    return {}, False, AgentHubResponse(
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        "application/json; charset=utf-8",
        {"error": "unsupported content type"},
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
