from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import TaskRepository
from agent_hub.services.pipelines import PipelineService


class PipelineServiceTests(unittest.TestCase):
    def test_instantiate_pipeline_creates_task_graph(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            service = PipelineService(task_repository=tasks, project_registry=projects)

            result = service.instantiate("sample-project", "sample-flow", input_value="hello")

            self.assertEqual(result.project_id, "sample-project")
            self.assertEqual(result.pipeline_run.project_id, "sample-project")
            self.assertEqual(len(result.tasks), 2)
            first, second = result.tasks
            self.assertEqual(first.pipeline_run_id, result.pipeline_run.id)
            self.assertEqual(second.pipeline_run_id, result.pipeline_run.id)
            self.assertEqual(first.kind, "project_action")
            self.assertEqual(second.kind, "echo")
            self.assertIn("hello", second.payload)
            detail = tasks.get_task_detail(second.id)
            assert detail is not None
            self.assertEqual(detail.dependency_ids, [first.id])


if __name__ == "__main__":
    unittest.main()
