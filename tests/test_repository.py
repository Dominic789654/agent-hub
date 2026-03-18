from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.models import RunStatus
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository


class RepositoryTests(unittest.TestCase):
    def test_task_lifecycle_and_status_counts(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            created = tasks.create_task("demo", kind="echo", payload="hello", project_id="sample-project")
            claimed = tasks.claim_next_task()

            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(claimed.id, created.id)
            self.assertEqual(claimed.attempt_count, 1)
            self.assertEqual(claimed.project_id, "sample-project")

            tasks.mark_succeeded(claimed.id)
            status = runtime.get_status(tasks, projects)

            self.assertEqual(status.succeeded_count, 1)
            self.assertEqual(status.queued_count, 0)
            self.assertEqual(status.dispatcher_state, "stopped")
            self.assertEqual(status.project_count, 1)

    def test_task_detail_includes_runs_and_logs(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            created = tasks.create_task("detail-demo", kind="echo", payload="hello")
            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            tasks.append_run_log(run.id, "[echo] hello\n")
            tasks.finish_run(run.id, RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)

            detail = tasks.get_task_detail(created.id)

            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.task.id, created.id)
            self.assertEqual(len(detail.runs), 1)
            self.assertEqual(detail.runs[0].status, RunStatus.SUCCEEDED)
            self.assertIn("[echo] hello", detail.runs[0].log)

    def test_cancel_and_retry_task(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            runtime = RuntimeRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            created = tasks.create_task("demo", kind="noop", project_id="sample-project")
            cancelled = tasks.cancel_task(created.id)
            retried = tasks.retry_task(created.id)
            status = runtime.get_status(tasks, projects)

            self.assertEqual(cancelled.status.value, "cancelled")
            self.assertEqual(retried.status.value, "queued")
            self.assertEqual(status.queued_count, 1)
            self.assertEqual(status.cancelled_count, 0)

    def test_list_recent_runs_returns_joined_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            task = tasks.create_task("runs-demo", kind="echo", payload="hello")
            claimed = tasks.claim_next_task()
            assert claimed is not None
            run = tasks.create_run(claimed.id)
            tasks.append_run_log(run.id, "hello\n")
            tasks.finish_run(run.id, RunStatus.SUCCEEDED)
            tasks.mark_succeeded(claimed.id)

            rows = tasks.list_recent_runs(limit=5)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].task.id, task.id)
            self.assertEqual(rows[0].run.task_id, task.id)

    def test_claim_next_task_waits_for_succeeded_dependencies(self) -> None:
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

            claimed_first = tasks.claim_next_task()
            self.assertIsNotNone(claimed_first)
            assert claimed_first is not None
            self.assertEqual(claimed_first.id, first.id)
            self.assertIsNone(tasks.claim_next_task())

            tasks.mark_succeeded(first.id)
            claimed_second = tasks.claim_next_task()
            self.assertIsNotNone(claimed_second)
            assert claimed_second is not None
            self.assertEqual(claimed_second.id, second.id)

            status = runtime.get_status(tasks, projects)
            self.assertEqual(status.ready_queued_count, 0)
            self.assertEqual(status.blocked_queued_count, 0)

    def test_task_detail_reports_dependencies(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            first = tasks.create_task("first", kind="noop")
            second = tasks.create_task("second", kind="noop", depends_on=[first.id])

            detail = tasks.get_task_detail(second.id)

            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.dependency_ids, [first.id])
            self.assertEqual(detail.unresolved_dependency_ids, [first.id])
            self.assertEqual(detail.dependent_ids, [])
            self.assertEqual(detail.incomplete_dependent_ids, [])

            first_detail = tasks.get_task_detail(first.id)
            self.assertIsNotNone(first_detail)
            assert first_detail is not None
            self.assertEqual(first_detail.dependent_ids, [second.id])
            self.assertEqual(first_detail.incomplete_dependent_ids, [second.id])

    def test_get_task_neighbors_returns_dependency_and_dependent_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            first = tasks.create_task("first", kind="noop")
            second = tasks.create_task("second", kind="noop", depends_on=[first.id])
            third = tasks.create_task("third", kind="noop", depends_on=[second.id])

            middle = tasks.get_task_neighbors(second.id)
            self.assertIsNotNone(middle)
            assert middle is not None
            self.assertEqual([task.id for task in middle.dependencies], [first.id])
            self.assertEqual([task.id for task in middle.dependents], [third.id])

    def test_task_notes_and_labels_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            created = tasks.create_task("annotated", kind="noop")
            note = tasks.add_task_note(created.id, "needs operator review")
            labels = tasks.add_task_label(created.id, "uat")
            labels = tasks.add_task_label(created.id, "important")
            labels = tasks.remove_task_label(created.id, "uat")
            detail = tasks.get_task_detail(created.id)

            self.assertEqual(note.body, "needs operator review")
            self.assertEqual(labels, ["important"])
            assert detail is not None
            self.assertEqual(detail.labels, ["important"])
            self.assertEqual(detail.notes[0].body, "needs operator review")

    def test_pipeline_run_notes_and_labels_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            note = tasks.add_pipeline_run_note(pipeline_run.id, "watch latency")
            labels = tasks.add_pipeline_run_label(pipeline_run.id, "priority")
            labels = tasks.remove_pipeline_run_label(pipeline_run.id, "priority")
            detail = tasks.get_pipeline_run_detail(pipeline_run.id)

            self.assertEqual(note.body, "watch latency")
            self.assertEqual(labels, [])
            assert detail is not None
            self.assertEqual(detail.notes[0].body, "watch latency")
            self.assertEqual(detail.labels, [])

    def test_saved_queries_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)
            failed = tasks.create_task("failed", kind="noop", project_id="sample-project")
            tasks.mark_failed(failed.id, "boom")

            created = tasks.create_saved_query(
                "tasks",
                "Failed Sample Tasks",
                description="focus on failed tasks",
                filters={"project_id": "sample-project", "status": "failed"},
            )
            fetched = tasks.get_saved_query(created.id)
            listed = tasks.list_saved_queries(scope="tasks")
            applied = tasks.apply_saved_query(created.id)

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.filters["status"], "failed")
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].id, created.id)
            self.assertEqual(len(applied.items), 1)
            self.assertEqual(applied.items[0]["id"], failed.id)

            tasks.delete_saved_query(created.id)
            self.assertEqual(tasks.list_saved_queries(scope="tasks"), [])

    def test_list_human_inbox_returns_actionable_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            failed = tasks.create_task("failed", kind="noop", project_id="sample-project")
            blocked_parent = tasks.create_task("parent", kind="noop", project_id="sample-project")
            blocked_child = tasks.create_task("blocked", kind="noop", project_id="sample-project", depends_on=[blocked_parent.id])
            needs_human = tasks.create_task("human", kind="noop", project_id="other-project")
            tasks.mark_failed(failed.id, "boom")
            tasks.mark_failed(blocked_parent.id, "upstream broke")
            tasks.mark_needs_human(needs_human.id, note="manual check")
            tasks.add_task_note(needs_human.id, "needs operator reply")
            tasks.add_task_label(needs_human.id, "priority")

            inbox = tasks.list_human_inbox(limit=10)
            sample_inbox = tasks.list_human_inbox(limit=10, project_id="sample-project")

            self.assertEqual({item.task.id for item in inbox}, {failed.id, blocked_child.id, needs_human.id, blocked_parent.id})
            self.assertEqual({item.task.id for item in sample_inbox}, {failed.id, blocked_child.id, blocked_parent.id})
            human_item = next(item for item in inbox if item.task.id == needs_human.id)
            self.assertEqual(human_item.labels, ["priority"])
            self.assertEqual(human_item.latest_note.body, "needs operator reply")  # type: ignore[union-attr]

    def test_failed_task_blocks_descendants_until_retried_and_succeeded(self) -> None:
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

            tasks.mark_failed(first.id, "boom")
            blocked = tasks.get_task(second.id)
            assert blocked is not None
            self.assertEqual(blocked.status.value, "blocked")

            tasks.retry_task(first.id)
            tasks.mark_succeeded(first.id)
            released = tasks.get_task(second.id)
            assert released is not None
            self.assertEqual(released.status.value, "queued")

            status = runtime.get_status(tasks, projects)
            self.assertEqual(status.blocked_count, 0)
            self.assertEqual(status.needs_human_count, 0)

    def test_mark_needs_human_blocks_descendants(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Database(Path(tmp))
            db.bootstrap()
            tasks = TaskRepository(db)

            first = tasks.create_task("first", kind="noop")
            second = tasks.create_task("second", kind="noop", depends_on=[first.id])

            flagged = tasks.mark_needs_human(first.id, note="manual check")
            blocked = tasks.get_task(second.id)
            assert blocked is not None
            self.assertEqual(flagged.status.value, "needs_human")
            self.assertEqual(blocked.status.value, "blocked")

    def test_pipeline_run_detail_links_instantiated_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            first = tasks.create_task(
                "first",
                kind="noop",
                project_id="sample-project",
                pipeline_run_id=pipeline_run.id,
            )
            second = tasks.create_task(
                "second",
                kind="noop",
                project_id="sample-project",
                pipeline_run_id=pipeline_run.id,
                depends_on=[first.id],
            )

            listed = tasks.list_pipeline_runs(limit=5)
            detail = tasks.get_pipeline_run_detail(pipeline_run.id)

            self.assertEqual(tasks.count_pipeline_runs(), 1)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].task_count, 2)
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.pipeline_run.id, pipeline_run.id)
            self.assertEqual([task.id for task in detail.tasks], [first.id, second.id])

    def test_cancel_pipeline_run_cancels_incomplete_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            first = tasks.create_task("first", kind="noop", project_id="sample-project", pipeline_run_id=pipeline_run.id)
            second = tasks.create_task(
                "second",
                kind="noop",
                project_id="sample-project",
                pipeline_run_id=pipeline_run.id,
                depends_on=[first.id],
            )

            tasks.mark_succeeded(first.id)
            cancelled = tasks.cancel_pipeline_run(pipeline_run.id)

            self.assertEqual(cancelled.pipeline_run.cancelled_count, 1)
            self.assertEqual(tasks.get_task(first.id).status.value, "succeeded")  # type: ignore[union-attr]
            self.assertEqual(tasks.get_task(second.id).status.value, "cancelled")  # type: ignore[union-attr]

    def test_retry_pipeline_run_requeues_non_success_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            first = tasks.create_task("first", kind="noop", project_id="sample-project", pipeline_run_id=pipeline_run.id)
            second = tasks.create_task(
                "second",
                kind="noop",
                project_id="sample-project",
                pipeline_run_id=pipeline_run.id,
                depends_on=[first.id],
            )

            tasks.mark_failed(first.id, "boom")
            retried = tasks.retry_pipeline_run(pipeline_run.id)

            self.assertEqual(retried.pipeline_run.queued_count, 2)
            self.assertEqual(tasks.get_task(first.id).status.value, "queued")  # type: ignore[union-attr]
            self.assertEqual(tasks.get_task(second.id).status.value, "queued")  # type: ignore[union-attr]

    def test_list_tasks_supports_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)

            pipeline_run = tasks.create_pipeline_run("sample-project", "sample-flow", "hello")
            first = tasks.create_task("first", kind="echo", project_id="sample-project", pipeline_run_id=pipeline_run.id)
            second = tasks.create_task("second", kind="noop", project_id="sample-project")
            tasks.create_task("third", kind="noop", project_id="other-project")
            tasks.mark_succeeded(first.id)
            tasks.mark_failed(second.id, "boom")

            self.assertEqual({item.id for item in tasks.list_tasks(project_id="sample-project")}, {second.id, first.id})
            self.assertEqual([item.id for item in tasks.list_tasks(status="failed")], [second.id])
            self.assertEqual([item.id for item in tasks.list_tasks(kind="echo")], [first.id])
            self.assertEqual([item.id for item in tasks.list_tasks(pipeline_run_id=pipeline_run.id)], [first.id])
            self.assertEqual(len(tasks.list_tasks(project_id="other-project")), 1)
            self.assertEqual(tasks.list_tasks(project_id="missing"), [])

    def test_list_pipeline_runs_supports_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)

            first = tasks.create_pipeline_run("sample-project", "sample-flow", "a")
            second = tasks.create_pipeline_run("sample-project", "other-flow", "b")
            third = tasks.create_pipeline_run("other-project", "sample-flow", "c")

            self.assertEqual({item.id for item in tasks.list_pipeline_runs(project_id="sample-project")}, {second.id, first.id})
            self.assertEqual({item.id for item in tasks.list_pipeline_runs(pipeline_id="sample-flow")}, {third.id, first.id})
            self.assertEqual([item.id for item in tasks.list_pipeline_runs(project_id="sample-project", pipeline_id="other-flow")], [second.id])


if __name__ == "__main__":
    unittest.main()
