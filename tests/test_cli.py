from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agent_hub.cli import main
from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.dispatcher import Dispatcher
from agent_hub.models import RunStatus, TaskStatus
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository


EXAMPLE_PROJECTS_FILE = Path(__file__).resolve().parents[1] / "examples" / "agent-driven-projects.example.json"


class CliTests(unittest.TestCase):
    def test_public_demo_registry_cli_flow_and_dispatch(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"

            delegated_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "run-task-template",
                    "demo-codex",
                    "delegate-task",
                    "--input",
                    "Investigate why the local build script is flaky",
                ],
            ), patch("sys.stdout", delegated_stdout):
                self.assertEqual(main(), 0)
            delegated = json.loads(delegated_stdout.getvalue())

            pipeline_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "run-pipeline",
                    "demo-codex",
                    "review-then-implement",
                    "--input",
                    "Add a dry-run mode",
                ],
            ), patch("sys.stdout", pipeline_stdout):
                self.assertEqual(main(), 0)
            pipeline = json.loads(pipeline_stdout.getvalue())

            human_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "create-task",
                    "Manual review: choose agent",
                    "--kind",
                    "noop",
                    "--project-id",
                    "demo-claude",
                ],
            ), patch("sys.stdout", human_stdout):
                self.assertEqual(main(), 0)
            human_task = json.loads(human_stdout.getvalue())

            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "mark-needs-human",
                    human_task["id"],
                    "--note",
                    "operator chooses owner",
                ],
            ):
                self.assertEqual(main(), 0)

            settings = resolve_settings(data_dir=data_dir, projects_file=EXAMPLE_PROJECTS_FILE)
            db = Database(settings.data_dir)
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            dispatcher = Dispatcher(task_repository=tasks, runtime_repository=runtime, project_registry=projects)

            while True:
                claimed = tasks.claim_next_task()
                if claimed is None:
                    break
                run = tasks.create_run(claimed.id)
                try:
                    dispatcher._process_task(claimed, run.id)
                except Exception as exc:  # pragma: no cover - defensive parity with dispatcher loop
                    tasks.append_run_log(run.id, f"[error] {exc}\n")
                    tasks.finish_run(run.id, status=RunStatus.FAILED)
                    tasks.mark_failed(claimed.id, str(exc))
                else:
                    tasks.finish_run(run.id, status=RunStatus.SUCCEEDED)
                    tasks.mark_succeeded(claimed.id)

            delegated_detail = tasks.get_task_detail(delegated["task"]["id"])
            self.assertIsNotNone(delegated_detail)
            assert delegated_detail is not None
            self.assertEqual(delegated_detail.task.status, TaskStatus.SUCCEEDED)
            self.assertIn("[agent-wrapper] agent=codex", delegated_detail.runs[0].log)
            self.assertIn("simulated assistant run completed", delegated_detail.runs[0].log)

            implement_task_id = next(
                item["id"] for item in pipeline["tasks"] if item["title"] == "Implement reviewed change"
            )
            implement_detail = tasks.get_task_detail(implement_task_id)
            self.assertIsNotNone(implement_detail)
            assert implement_detail is not None
            self.assertEqual(implement_detail.task.status, TaskStatus.SUCCEEDED)
            self.assertIn("[agent-wrapper] agent=codex", implement_detail.runs[0].log)

            inbox_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "list-human-inbox",
                ],
            ), patch("sys.stdout", inbox_stdout):
                self.assertEqual(main(), 0)
            inbox = json.loads(inbox_stdout.getvalue())
            self.assertEqual(len(inbox["items"]), 1)
            self.assertEqual(inbox["items"][0]["task"]["project_id"], "demo-claude")

            dashboard_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "--projects-file",
                    str(EXAMPLE_PROJECTS_FILE),
                    "dashboard",
                    "--limit",
                    "10",
                ],
            ), patch("sys.stdout", dashboard_stdout):
                self.assertEqual(main(), 0)
            dashboard = json.loads(dashboard_stdout.getvalue())
            self.assertEqual(dashboard["status"]["project_count"], 2)
            self.assertEqual(len(dashboard["human_inbox"]), 1)
            self.assertTrue(
                any(item["project_id"] == "demo-codex" for item in dashboard["recent_tasks"]),
            )

    def test_list_runs_and_retry_cancel_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "cli-demo", "--kind", "noop"],
            ), patch("sys.stdout", create_stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            created = json.loads(create_stdout.getvalue())

            cancel_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "cancel-task", created["id"]],
            ), patch("sys.stdout", cancel_stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            cancelled = json.loads(cancel_stdout.getvalue())
            self.assertEqual(cancelled["status"], "cancelled")

            retry_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "retry-task", created["id"]],
            ), patch("sys.stdout", retry_stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            retried = json.loads(retry_stdout.getvalue())
            self.assertEqual(retried["status"], "queued")

    def test_list_runs_command_outputs_recent_run_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "echo-demo", "--kind", "echo", "--payload", "hello"],
            ):
                self.assertEqual(main(), 0)

            from agent_hub.config import resolve_settings
            from agent_hub.db import Database
            from agent_hub.dispatcher import Dispatcher
            from agent_hub.projects import ProjectRegistry
            from agent_hub.repository import RuntimeRepository, TaskRepository

            settings = resolve_settings(data_dir=data_dir)
            db = Database(settings.data_dir)
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            ProjectRegistry(settings.projects_file).bootstrap()
            claimed = tasks.claim_next_task()
            assert claimed is not None
            dispatcher = Dispatcher(task_repository=tasks, runtime_repository=runtime)
            dispatcher._process_task(claimed, tasks.create_run(claimed.id).id)
            tasks.mark_succeeded(claimed.id)

            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-runs", "--limit", "5"],
            ), patch("sys.stdout", stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(len(payload["runs"]), 1)
            self.assertEqual(payload["runs"][0]["task"]["title"], "echo-demo")

    def test_dashboard_command_outputs_snapshot(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "dash-demo", "--kind", "noop", "--project-id", "sample-project"],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)

            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "dashboard", "--limit", "5"],
            ), patch("sys.stdout", stdout):
                self.assertEqual(main(), 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("status", payload)
            self.assertIn("recent_tasks", payload)
            self.assertEqual(len(payload["recent_tasks"]), 1)

    def test_create_project_command_requires_project_id(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stderr = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "bad", "--kind", "project_command"],
            ), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit):
                    main()
            self.assertIn("require --project-id", stderr.getvalue())

    def test_list_project_actions_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-project-actions", "sample-project"],
            ), patch("sys.stdout", stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project_id"], "sample-project")
            self.assertEqual(payload["actions"][0]["id"], "show-status")

    def test_list_project_pipelines_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-project-pipelines", "sample-project"],
            ), patch("sys.stdout", stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project_id"], "sample-project")
            self.assertEqual(payload["pipelines"][0]["id"], "sample-flow")

    def test_list_project_task_templates_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-project-task-templates", "sample-project"],
            ), patch("sys.stdout", stdout):
                exit_code = main()
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project_id"], "sample-project")
            self.assertEqual(payload["task_templates"][0]["id"], "summarize-input")

    def test_create_project_action_requires_known_action(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stderr = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "create-task",
                    "bad-action",
                    "--kind",
                    "project_action",
                    "--project-id",
                    "sample-project",
                    "--payload",
                    "missing",
                ],
            ), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit):
                    main()
            self.assertIn("unknown project action", stderr.getvalue())

    def test_create_task_supports_depends_on(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            first_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "first", "--kind", "noop"],
            ), patch("sys.stdout", first_stdout):
                self.assertEqual(main(), 0)
            first = json.loads(first_stdout.getvalue())

            second_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "create-task",
                    "second",
                    "--kind",
                    "noop",
                    "--depends-on",
                    first["id"],
                ],
            ), patch("sys.stdout", second_stdout):
                self.assertEqual(main(), 0)
            second = json.loads(second_stdout.getvalue())
            self.assertEqual(second["title"], "second")

    def test_mark_needs_human_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "queue-demo", "--kind", "noop"],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)
            created = json.loads(create_stdout.getvalue())

            flagged_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "mark-needs-human", created["id"], "--note", "manual"],
            ), patch("sys.stdout", flagged_stdout):
                self.assertEqual(main(), 0)
            flagged = json.loads(flagged_stdout.getvalue())
            self.assertEqual(flagged["status"], "needs_human")

    def test_run_pipeline_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "run-pipeline",
                    "sample-project",
                    "sample-flow",
                    "--input",
                    "hello",
                ],
            ), patch("sys.stdout", stdout):
                self.assertEqual(main(), 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project_id"], "sample-project")
            self.assertEqual(payload["pipeline_run"]["task_count"], 2)
            self.assertEqual(len(payload["tasks"]), 2)

    def test_run_task_template_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "run-task-template",
                    "sample-project",
                    "summarize-input",
                    "--input",
                    "hello",
                ],
            ), patch("sys.stdout", stdout):
                self.assertEqual(main(), 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["template_id"], "summarize-input")
            self.assertEqual(payload["task"]["kind"], "echo")
            self.assertEqual(payload["labels"], ["template", "summary"])

    def test_list_and_show_pipeline_runs_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "run-pipeline",
                    "sample-project",
                    "sample-flow",
                    "--input",
                    "hello",
                ],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)
            created = json.loads(create_stdout.getvalue())

            list_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-pipeline-runs", "--limit", "5"],
            ), patch("sys.stdout", list_stdout):
                self.assertEqual(main(), 0)
            listed = json.loads(list_stdout.getvalue())
            self.assertEqual(len(listed["pipeline_runs"]), 1)

            show_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "show-pipeline-run", created["pipeline_run"]["id"]],
            ), patch("sys.stdout", show_stdout):
                self.assertEqual(main(), 0)
            detail = json.loads(show_stdout.getvalue())
            self.assertEqual(detail["pipeline_run"]["id"], created["pipeline_run"]["id"])
            self.assertEqual(len(detail["tasks"]), 2)

    def test_cancel_and_retry_pipeline_run_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "run-pipeline",
                    "sample-project",
                    "sample-flow",
                    "--input",
                    "hello",
                ],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)
            created = json.loads(create_stdout.getvalue())
            run_id = created["pipeline_run"]["id"]

            cancel_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "cancel-pipeline-run", run_id],
            ), patch("sys.stdout", cancel_stdout):
                self.assertEqual(main(), 0)
            cancelled = json.loads(cancel_stdout.getvalue())
            self.assertEqual(cancelled["pipeline_run"]["cancelled_count"], 2)

            retry_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "retry-pipeline-run", run_id],
            ), patch("sys.stdout", retry_stdout):
                self.assertEqual(main(), 0)
            retried = json.loads(retry_stdout.getvalue())
            self.assertEqual(retried["pipeline_run"]["queued_count"], 2)

    def test_list_commands_support_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            first_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "first", "--kind", "echo", "--payload", "hi", "--project-id", "sample-project"],
            ), patch("sys.stdout", first_stdout):
                self.assertEqual(main(), 0)
            first = json.loads(first_stdout.getvalue())

            second_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "second", "--kind", "noop", "--project-id", "sample-project"],
            ), patch("sys.stdout", second_stdout):
                self.assertEqual(main(), 0)
            second = json.loads(second_stdout.getvalue())

            from agent_hub.config import resolve_settings
            from agent_hub.db import Database
            from agent_hub.repository import TaskRepository
            settings = resolve_settings(data_dir=data_dir)
            db = Database(settings.data_dir)
            tasks = TaskRepository(db)
            tasks.mark_failed(second["id"], "boom")

            list_tasks_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-tasks", "--project-id", "sample-project", "--status", "failed"],
            ), patch("sys.stdout", list_tasks_stdout):
                self.assertEqual(main(), 0)
            filtered_tasks = json.loads(list_tasks_stdout.getvalue())
            self.assertEqual([item["id"] for item in filtered_tasks["tasks"]], [second["id"]])

            run_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "run-pipeline", "sample-project", "sample-flow", "--input", "hello"],
            ), patch("sys.stdout", run_stdout):
                self.assertEqual(main(), 0)
            created_run = json.loads(run_stdout.getvalue())

            list_runs_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-pipeline-runs", "--project-id", "sample-project", "--pipeline-id", "sample-flow"],
            ), patch("sys.stdout", list_runs_stdout):
                self.assertEqual(main(), 0)
            filtered_runs = json.loads(list_runs_stdout.getvalue())
            self.assertEqual([item["id"] for item in filtered_runs["pipeline_runs"]], [created_run["pipeline_run"]["id"]])

    def test_task_and_pipeline_run_annotation_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            task_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "annotated", "--kind", "noop"],
            ), patch("sys.stdout", task_stdout):
                self.assertEqual(main(), 0)
            task = json.loads(task_stdout.getvalue())

            note_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "add-task-note", task["id"], "manual review"],
            ), patch("sys.stdout", note_stdout):
                self.assertEqual(main(), 0)
            note = json.loads(note_stdout.getvalue())
            self.assertEqual(note["body"], "manual review")

            label_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "add-task-label", task["id"], "important"],
            ), patch("sys.stdout", label_stdout):
                self.assertEqual(main(), 0)
            labels = json.loads(label_stdout.getvalue())
            self.assertEqual(labels["labels"], ["important"])

            run_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "run-pipeline", "sample-project", "sample-flow", "--input", "hello"],
            ), patch("sys.stdout", run_stdout):
                self.assertEqual(main(), 0)
            created_run = json.loads(run_stdout.getvalue())
            run_id = created_run["pipeline_run"]["id"]

            run_label_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "add-pipeline-run-label", run_id, "priority"],
            ), patch("sys.stdout", run_label_stdout):
                self.assertEqual(main(), 0)
            run_labels = json.loads(run_label_stdout.getvalue())
            self.assertEqual(run_labels["labels"], ["priority"])

    def test_saved_query_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            task_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "bad-task", "--kind", "noop", "--project-id", "sample-project"],
            ), patch("sys.stdout", task_stdout):
                self.assertEqual(main(), 0)
            task = json.loads(task_stdout.getvalue())

            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "cancel-task", task["id"]],
            ):
                self.assertEqual(main(), 0)

            from agent_hub.config import resolve_settings
            from agent_hub.db import Database
            from agent_hub.repository import TaskRepository
            settings = resolve_settings(data_dir=data_dir)
            db = Database(settings.data_dir)
            TaskRepository(db).mark_failed(task["id"], "boom")

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "agent-hub",
                    "--data-dir",
                    str(data_dir),
                    "create-saved-query",
                    "tasks",
                    "Failed Tasks",
                    "--description",
                    "focus on failed",
                    "--filter",
                    "project_id=sample-project",
                    "--filter",
                    "status=failed",
                ],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)
            created = json.loads(create_stdout.getvalue())
            self.assertEqual(created["scope"], "tasks")

            list_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-saved-queries", "--scope", "tasks"],
            ), patch("sys.stdout", list_stdout):
                self.assertEqual(main(), 0)
            listed = json.loads(list_stdout.getvalue())
            self.assertEqual(len(listed["saved_queries"]), 1)

            apply_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "apply-saved-query", created["id"], "--limit", "5"],
            ), patch("sys.stdout", apply_stdout):
                self.assertEqual(main(), 0)
            applied = json.loads(apply_stdout.getvalue())
            self.assertEqual(applied["saved_query"]["id"], created["id"])
            self.assertEqual(len(applied["items"]), 1)

            delete_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "delete-saved-query", created["id"]],
            ), patch("sys.stdout", delete_stdout):
                self.assertEqual(main(), 0)
            deleted = json.loads(delete_stdout.getvalue())
            self.assertEqual(deleted["deleted"], True)

    def test_list_human_inbox_command(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)

            create_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "create-task", "needs-help", "--kind", "noop", "--project-id", "sample-project"],
            ), patch("sys.stdout", create_stdout):
                self.assertEqual(main(), 0)
            created = json.loads(create_stdout.getvalue())

            note_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "mark-needs-human", created["id"], "--note", "manual review"],
            ), patch("sys.stdout", note_stdout):
                self.assertEqual(main(), 0)

            list_stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                ["agent-hub", "--data-dir", str(data_dir), "list-human-inbox", "--project-id", "sample-project"],
            ), patch("sys.stdout", list_stdout):
                self.assertEqual(main(), 0)
            payload = json.loads(list_stdout.getvalue())
            self.assertEqual(len(payload["items"]), 1)
            self.assertEqual(payload["items"][0]["task"]["id"], created["id"])


if __name__ == "__main__":
    unittest.main()
