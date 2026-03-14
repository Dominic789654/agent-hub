from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import TaskRepository
from agent_hub.services.task_templates import TaskTemplateService


class TaskTemplateServiceTests(unittest.TestCase):
    def test_instantiate_task_template_creates_labeled_task(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = resolve_settings(data_dir=Path(tmp))
            db = Database(settings.data_dir)
            db.bootstrap()
            tasks = TaskRepository(db)
            projects = ProjectRegistry(settings.projects_file)
            projects.bootstrap()
            service = TaskTemplateService(task_repository=tasks, project_registry=projects)

            result = service.instantiate("sample-project", "summarize-input", input_value="hello world")

            self.assertEqual(result.project_id, "sample-project")
            self.assertEqual(result.template_id, "summarize-input")
            self.assertEqual(result.task.project_id, "sample-project")
            self.assertEqual(result.task.kind, "echo")
            self.assertIn("hello world", result.task.title)
            self.assertEqual(result.labels, ["template", "summary"])


if __name__ == "__main__":
    unittest.main()
