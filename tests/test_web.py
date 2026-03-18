import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.dispatcher import Dispatcher
from agent_hub.models import RunStatus
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository
from agent_hub.web import AgentHubApp


EXAMPLE_PROJECTS_FILE = Path(__file__).resolve().parents[1] / "examples" / "agent-driven-projects.example.json"


class WebTests(unittest.TestCase):
    def test_health_status_and_tasks_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            tasks.create_task("web-demo", kind="noop", project_id="sample-project")

            app = AgentHubApp(tasks, runtime, projects, settings)
            health = app.handle_get("/healthz")
            status = app.handle_get("/status")
            config = app.handle_get("/config")
            projects_payload = app.handle_get("/projects")
            project_actions = app.handle_get("/projects/sample-project/actions")
            project_pipelines = app.handle_get("/projects/sample-project/pipelines")
            project_task_templates = app.handle_get("/projects/sample-project/task-templates")
            payload = app.handle_get("/tasks?limit=5")
            runs = app.handle_get("/runs?limit=5")
            human_inbox = app.handle_get("/human-inbox?limit=5")
            saved_queries = app.handle_get("/saved-queries?limit=5")
            pipeline_runs = app.handle_get("/pipeline-runs?limit=5")
            dashboard = app.handle_get("/dashboard")
            app_page = app.handle_get("/app")
            html = app.handle_get("/")

            self.assertEqual(health.payload["ok"], True)
            self.assertEqual(status.payload["project_count"], 1)
            self.assertTrue(config.payload["projects_file"].endswith("projects.json"))
            self.assertEqual(len(projects_payload.payload["projects"]), 1)
            self.assertEqual(project_actions.payload["actions"][0]["id"], "show-status")
            self.assertEqual(project_pipelines.payload["pipelines"][0]["id"], "sample-flow")
            self.assertEqual(project_task_templates.payload["task_templates"][0]["id"], "summarize-input")
            self.assertEqual(status.payload["queued_count"], 1)
            self.assertEqual(status.payload["ready_queued_count"], 1)
            self.assertEqual(status.payload["blocked_queued_count"], 0)
            self.assertEqual(status.payload["cancelled_count"], 0)
            self.assertEqual(status.payload["blocked_count"], 0)
            self.assertEqual(status.payload["needs_human_count"], 0)
            self.assertEqual(len(payload.payload["tasks"]), 1)
            self.assertEqual(runs.payload["runs"], [])
            self.assertEqual(human_inbox.payload["items"], [])
            self.assertEqual(saved_queries.payload["saved_queries"], [])
            self.assertEqual(pipeline_runs.payload["pipeline_runs"], [])
            self.assertIn("status", dashboard.payload)
            self.assertIn("recent_tasks", dashboard.payload)
            self.assertIn("Thin client powered by", app_page.payload)
            self.assertIn("fetch(\"/dashboard\"", app_page.payload)
            self.assertEqual(payload.payload["tasks"][0]["project_id"], "sample-project")
            self.assertIn("web-demo", html.payload)
            self.assertIn("sample-project", html.payload)
            self.assertIn("Create task", html.payload)

    def test_task_detail_and_latest_run_log_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("echo-demo", kind="echo", payload="hello")

            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            tasks.append_run_log(run.id, "[echo] hello\n")
            tasks.finish_run(run.id, status=RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)

            app = AgentHubApp(tasks, runtime, projects, settings)
            detail = app.handle_get(f"/tasks/{created.id}")
            latest = app.handle_get(f"/tasks/{created.id}/runs/latest")

            self.assertEqual(detail.status.value, 200)
            self.assertEqual(detail.payload["task"]["id"], created.id)
            self.assertEqual(len(detail.payload["runs"]), 1)
            self.assertEqual(detail.payload["dependency_ids"], [])
            self.assertEqual(latest.payload["task_id"], created.id)
            self.assertIn("[echo] hello", latest.payload["log"])

    def test_task_neighbors_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            first = tasks.create_task("first", kind="noop")
            second = tasks.create_task("second", kind="noop", depends_on=[first.id])
            third = tasks.create_task("third", kind="noop", depends_on=[second.id])

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_get(f"/tasks/{second.id}/neighbors")

            self.assertEqual(response.status.value, 200)
            self.assertEqual([item["id"] for item in response.payload["dependencies"]], [first.id])
            self.assertEqual([item["id"] for item in response.payload["dependents"]], [third.id])

    def test_task_annotation_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("annotated", kind="noop")

            app = AgentHubApp(tasks, runtime, projects, settings)
            note = app.handle_post(f"/tasks/{created.id}/notes", b'{"body":"manual review"}', "application/json")
            label = app.handle_post(f"/tasks/{created.id}/labels", b'{"label":"important"}', "application/json")
            removed = app.handle_post(f"/tasks/{created.id}/labels/remove", b'{"label":"important"}', "application/json")
            detail = app.handle_get(f"/tasks/{created.id}")

            self.assertEqual(note.status.value, 200)
            self.assertEqual(note.payload["body"], "manual review")
            self.assertEqual(label.payload["labels"], ["important"])
            self.assertEqual(removed.payload["labels"], [])
            self.assertEqual(detail.payload["notes"][0]["body"], "manual review")
            self.assertEqual(detail.payload["labels"], [])

    def test_pipeline_run_annotation_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")

            app = AgentHubApp(tasks, runtime, projects, settings)
            note = app.handle_post(
                f"/pipeline-runs/{pipeline_run.id}/notes",
                b'{"body":"track this run"}',
                "application/json",
            )
            label = app.handle_post(
                f"/pipeline-runs/{pipeline_run.id}/labels",
                b'{"label":"priority"}',
                "application/json",
            )
            detail = app.handle_get(f"/pipeline-runs/{pipeline_run.id}")

            self.assertEqual(note.status.value, 200)
            self.assertEqual(label.payload["labels"], ["priority"])
            self.assertEqual(detail.payload["notes"][0]["body"], "track this run")
            self.assertEqual(detail.payload["labels"], ["priority"])

    def test_saved_query_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            failed = tasks.create_task("failed-task", kind="noop", project_id="sample-project")
            tasks.mark_failed(failed.id, "boom")

            app = AgentHubApp(tasks, runtime, projects, settings)
            created = app.handle_post(
                "/saved-queries",
                b'{"scope":"tasks","name":"Failed Tasks","description":"focus","filters":{"project_id":"sample-project","status":"failed"}}',
                "application/json",
            )
            fetched = app.handle_get(f"/saved-queries/{created.payload['id']}")
            listed = app.handle_get("/saved-queries?scope=tasks")
            applied = app.handle_get(f"/saved-queries/{created.payload['id']}/apply?limit=5")
            deleted = app.handle_post(f"/saved-queries/{created.payload['id']}/delete", b"", "application/json")

            self.assertEqual(created.status.value, 201)
            self.assertEqual(fetched.status.value, 200)
            self.assertEqual(fetched.payload["name"], "Failed Tasks")
            self.assertEqual(len(listed.payload["saved_queries"]), 1)
            self.assertEqual(len(applied.payload["items"]), 1)
            self.assertEqual(applied.payload["items"][0]["id"], failed.id)
            self.assertEqual(deleted.payload["deleted"], True)

    def test_human_inbox_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("needs-help", kind="noop", project_id="sample-project")
            tasks.mark_needs_human(created.id, note="manual review")
            tasks.add_task_label(created.id, "priority")
            tasks.add_task_note(created.id, "operator should inspect")

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_get("/human-inbox?project_id=sample-project")

            self.assertEqual(response.status.value, 200)
            self.assertEqual(len(response.payload["items"]), 1)
            self.assertEqual(response.payload["items"][0]["task"]["id"], created.id)
            self.assertEqual(response.payload["items"][0]["labels"], ["priority"])

    def test_create_task_json_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b'{"title":"json-demo","kind":"echo","payload":"hello","project_id":"sample-project"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 201)
            self.assertEqual(response.payload["title"], "json-demo")
            self.assertEqual(response.payload["project_id"], "sample-project")
            self.assertEqual(len(tasks.list_tasks()), 1)

    def test_create_task_with_dependencies_json_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            first = tasks.create_task("first", kind="noop")

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                json.dumps({"title": "second", "kind": "noop", "depends_on": [first.id]}).encode("utf-8"),
                "application/json",
            )

            self.assertEqual(response.status.value, 201)
            detail = tasks.get_task_detail(response.payload["id"])
            assert detail is not None
            self.assertEqual(detail.dependency_ids, [first.id])

    def test_create_task_form_route_redirects_home(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b"title=form-demo&kind=noop&payload=&project_id=",
                "application/x-www-form-urlencoded",
            )

            self.assertEqual(response.status.value, 303)
            self.assertEqual(response.headers["Location"], "/")
            self.assertEqual(tasks.list_tasks()[0].title, "form-demo")

    def test_create_task_rejects_unknown_project(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b'{"title":"bad-project","project_id":"missing"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 400)
            self.assertIn("unknown project_id", response.payload["error"])
            self.assertEqual(tasks.list_tasks(), [])

    def test_create_project_command_requires_project(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b'{"title":"bad-project-command","kind":"project_command"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 400)
            self.assertIn("require project_id", response.payload["error"])

    def test_create_project_action_requires_payload(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b'{"title":"bad-project-action","kind":"project_action","project_id":"sample-project"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 400)
            self.assertIn("require payload", response.payload["error"])

    def test_create_project_action_rejects_unknown_action(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/tasks",
                b'{"title":"bad-project-action","kind":"project_action","project_id":"sample-project","payload":"missing"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 400)
            self.assertIn("unknown project action", response.payload["error"])

    def test_cancel_and_retry_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("queue-demo", kind="noop")

            app = AgentHubApp(tasks, runtime, projects, settings)
            cancelled = app.handle_post(
                f"/tasks/{created.id}/cancel",
                b"",
                "application/json",
            )
            retried = app.handle_post(
                f"/tasks/{created.id}/retry",
                b"",
                "application/json",
            )

            self.assertEqual(cancelled.status.value, 200)
            self.assertEqual(cancelled.payload["status"], "cancelled")
            self.assertEqual(retried.status.value, 200)
            self.assertEqual(retried.payload["status"], "queued")

    def test_mark_needs_human_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("queue-demo", kind="noop")

            app = AgentHubApp(tasks, runtime, projects, settings)
            flagged = app.handle_post(
                f"/tasks/{created.id}/needs-human",
                b'{"note":"manual review"}',
                "application/json",
            )

            self.assertEqual(flagged.status.value, 200)
            self.assertEqual(flagged.payload["status"], "needs_human")
            self.assertEqual(flagged.payload["last_error"], "manual review")

    def test_run_pipeline_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/pipelines",
                b'{"project_id":"sample-project","pipeline_id":"sample-flow","input":"hello"}',
                "application/json",
            )
            detail = app.handle_get(f"/pipeline-runs/{response.payload['pipeline_run']['id']}")

            self.assertEqual(response.status.value, 201)
            self.assertEqual(response.payload["project_id"], "sample-project")
            self.assertEqual(response.payload["pipeline_run"]["task_count"], 2)
            self.assertEqual(len(response.payload["tasks"]), 2)
            self.assertEqual(detail.status.value, 200)
            self.assertEqual(detail.payload["pipeline_run"]["id"], response.payload["pipeline_run"]["id"])
            self.assertEqual(len(detail.payload["tasks"]), 2)

    def test_run_task_template_route(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_post(
                "/task-templates",
                b'{"project_id":"sample-project","template_id":"summarize-input","input":"hello"}',
                "application/json",
            )

            self.assertEqual(response.status.value, 201)
            self.assertEqual(response.payload["template_id"], "summarize-input")
            self.assertEqual(response.payload["task"]["project_id"], "sample-project")
            self.assertEqual(response.payload["labels"], ["template", "summary"])

    def test_cancel_and_retry_pipeline_run_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            app = AgentHubApp(tasks, runtime, projects, settings)

            created = app.handle_post(
                "/pipelines",
                b'{"project_id":"sample-project","pipeline_id":"sample-flow","input":"hello"}',
                "application/json",
            )
            run_id = created.payload["pipeline_run"]["id"]

            cancelled = app.handle_post(
                f"/pipeline-runs/{run_id}/cancel",
                b"",
                "application/json",
            )
            retried = app.handle_post(
                f"/pipeline-runs/{run_id}/retry",
                b"",
                "application/json",
            )

            self.assertEqual(cancelled.status.value, 200)
            self.assertEqual(cancelled.payload["pipeline_run"]["cancelled_count"], 2)
            self.assertEqual(retried.status.value, 200)
            self.assertEqual(retried.payload["pipeline_run"]["queued_count"], 2)

    def test_runs_route_returns_latest_runs(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            created = tasks.create_task("echo-demo", kind="echo", payload="hello")
            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            tasks.append_run_log(run.id, "[echo] hello\n")
            tasks.finish_run(run.id, status=RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)

            app = AgentHubApp(tasks, runtime, projects, settings)
            response = app.handle_get("/runs?limit=5")

            self.assertEqual(response.status.value, 200)
            self.assertEqual(len(response.payload["runs"]), 1)
            self.assertEqual(response.payload["runs"][0]["task"]["id"], created.id)

    def test_tasks_and_pipeline_runs_routes_support_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            first = tasks.create_task("first", kind="echo", project_id="sample-project", pipeline_run_id=pipeline_run.id)
            second = tasks.create_task("second", kind="noop", project_id="sample-project")
            tasks.mark_failed(second.id, "boom")

            app = AgentHubApp(tasks, runtime, projects, settings)
            filtered_tasks = app.handle_get(f"/tasks?project_id=sample-project&status=failed")
            filtered_runs = app.handle_get("/pipeline-runs?project_id=sample-project&pipeline_id=sample-flow")

            self.assertEqual(filtered_tasks.status.value, 200)
            self.assertEqual([item["id"] for item in filtered_tasks.payload["tasks"]], [second.id])
            self.assertEqual(filtered_runs.status.value, 200)
            self.assertEqual([item["id"] for item in filtered_runs.payload["pipeline_runs"]], [pipeline_run.id])

    def test_dispatcher_executes_project_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            settings = resolve_settings(data_dir=data_dir)
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            project_root = settings.projects_file.parent / "workspace" / "demo-project"
            project_root.mkdir(parents=True)
            (project_root / "marker.txt").write_text("marker-ok\n", encoding="utf-8")
            settings.projects_file.write_text(
                """
{
  "version": 1,
  "projects": [
    {
      "id": "demo",
      "name": "Demo",
      "path": "./workspace/demo-project",
      "description": "demo project",
      "tags": ["demo"],
      "executor": {
        "type": "local-command",
        "command": ["python", "-c", "from pathlib import Path; print(Path('marker.txt').read_text().strip())"]
      },
      "enabled": true
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            created = tasks.create_task("project-run", kind="project_command", project_id="demo")

            dispatcher = Dispatcher(task_repository=tasks, runtime_repository=runtime, project_registry=projects)
            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            dispatcher._process_task(claimed, run.id)
            tasks.finish_run(run.id, status=RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)
            detail = tasks.get_task_detail(created.id)

            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertIn("marker-ok", detail.runs[0].log)

    def test_dispatcher_executes_project_action(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            settings = resolve_settings(data_dir=data_dir)
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            project_root = settings.projects_file.parent / "workspace" / "action-project"
            project_root.mkdir(parents=True)
            settings.projects_file.write_text(
                """
{
  "version": 1,
  "projects": [
    {
      "id": "demo",
      "name": "Demo",
      "path": "./workspace/action-project",
      "description": "demo project",
      "tags": ["demo"],
      "executor": {
        "type": "local-command",
        "actions": {
          "check": {
            "name": "Check",
            "description": "sample action",
            "command": ["python", "-c", "print('action={action_id};project={project_id}')"]
          }
        }
      },
      "enabled": true
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            created = tasks.create_task("project-action-run", kind="project_action", project_id="demo", payload="check")

            dispatcher = Dispatcher(task_repository=tasks, runtime_repository=runtime, project_registry=projects)
            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            dispatcher._process_task(claimed, run.id)
            tasks.finish_run(run.id, status=RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)
            detail = tasks.get_task_detail(created.id)

            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertIn("action=check;project=demo", detail.runs[0].log)

    def test_dispatcher_writes_latest_run_log(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            created = tasks.create_task("sleep-demo", kind="sleep", payload="0")

            dispatcher = Dispatcher(task_repository=tasks, runtime_repository=runtime)
            claimed = tasks.claim_next_task()
            assert claimed is not None
            dispatcher._process_task(claimed, tasks.create_run(claimed.id).id)
            detail = tasks.get_task_detail(created.id)

            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertIn("[sleep] seconds=0.0", detail.runs[0].log)

    def test_public_demo_registry_web_routes(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp) / "data", projects_file=EXAMPLE_PROJECTS_FILE)
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            delegated = tasks.create_task(
                "Codex task: flaky build",
                kind="project_command",
                payload="Investigate flaky build",
                project_id="demo-codex",
            )
            manual = tasks.create_task(
                "Manual review: choose agent",
                kind="noop",
                project_id="demo-claude",
            )
            tasks.mark_needs_human(manual.id, note="operator chooses owner")

            app = AgentHubApp(tasks, runtime, projects, settings)
            projects_payload = app.handle_get("/projects")
            actions_payload = app.handle_get("/projects/demo-codex/actions")
            pipelines_payload = app.handle_get("/projects/demo-codex/pipelines")
            templates_payload = app.handle_get("/projects/demo-codex/task-templates")
            dashboard = app.handle_get("/dashboard")
            inbox = app.handle_get("/human-inbox")

            self.assertEqual(projects_payload.status.value, 200)
            self.assertEqual([item["id"] for item in projects_payload.payload["projects"]], ["demo-claude", "demo-codex"])
            self.assertEqual(actions_payload.payload["actions"][0]["id"], "agent-health")
            self.assertEqual(pipelines_payload.payload["pipelines"][0]["id"], "review-then-implement")
            self.assertEqual(templates_payload.payload["task_templates"][0]["id"], "delegate-task")
            self.assertEqual(dashboard.payload["status"]["project_count"], 2)
            self.assertEqual(len(dashboard.payload["human_inbox"]), 1)
            self.assertTrue(any(item["id"] == delegated.id for item in dashboard.payload["recent_tasks"]))
            self.assertEqual(len(inbox.payload["items"]), 1)
            self.assertEqual(inbox.payload["items"][0]["task"]["project_id"], "demo-claude")


if __name__ == "__main__":
    unittest.main()
