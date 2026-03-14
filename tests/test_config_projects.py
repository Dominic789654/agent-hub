from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_hub.config import resolve_settings
from agent_hub.projects import ProjectRegistry


class ConfigProjectsTests(unittest.TestCase):
    def test_resolve_settings_defaults_projects_file_under_data_dir(self) -> None:
        settings = resolve_settings(data_dir=Path("/tmp/agent-hub-test"))
        self.assertEqual(settings.db_path, Path("/tmp/agent-hub-test/agent_hub.db"))
        self.assertEqual(settings.projects_file, Path("/tmp/agent-hub-test/projects.json"))

    def test_project_registry_bootstrap_and_filtering(self) -> None:
        with TemporaryDirectory() as tmp:
            projects_file = Path(tmp) / "projects.json"
            registry = ProjectRegistry(projects_file)
            registry.bootstrap()

            bootstrapped = registry.list_projects()
            self.assertEqual(len(bootstrapped), 1)
            self.assertEqual(bootstrapped[0].id, "sample-project")
            self.assertEqual(bootstrapped[0].executor["type"], "local-command")
            self.assertEqual(registry.list_project_actions("sample-project")[0].id, "show-status")
            self.assertEqual(registry.list_project_task_templates("sample-project")[0].id, "summarize-input")
            self.assertEqual(registry.list_project_pipelines("sample-project")[0].id, "sample-flow")

            projects_file.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "projects": [
                            {
                                "id": "alpha",
                                "name": "Alpha",
                                "path": "./alpha",
                                "description": "enabled",
                                "tags": ["demo"],
                                "enabled": True,
                            },
                            {
                                "id": "beta",
                                "name": "Beta",
                                "path": "./beta",
                                "description": "disabled",
                                "tags": [],
                                "enabled": False,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            enabled = registry.list_projects()
            all_projects = registry.list_projects(include_disabled=True)

            self.assertEqual([item.id for item in enabled], ["alpha"])
            self.assertEqual([item.id for item in all_projects], ["alpha", "beta"])
            self.assertEqual(registry.enabled_count(), 1)
            self.assertEqual(registry.get_project("beta").name, "Beta")
            self.assertEqual(registry.resolve_project_path(registry.get_project("alpha")), (projects_file.parent / "alpha").resolve())


if __name__ == "__main__":
    unittest.main()
