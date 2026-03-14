from __future__ import annotations

import json
from pathlib import Path

from agent_hub.models import (
    ProjectActionRecord,
    ProjectPipelineRecord,
    ProjectPipelineStepRecord,
    ProjectRecord,
    ProjectTaskTemplateRecord,
)


DEFAULT_PROJECTS_PAYLOAD = {
    "version": 1,
    "projects": [
        {
            "id": "sample-project",
            "name": "Sample Project",
            "path": "./workspace/sample-project",
            "description": "Portable example project entry for local development.",
            "tags": ["example", "local"],
            "executor": {
                "type": "local-command",
                "command": ["python", "-c", "print('sample-project executor')"],
                "actions": {
                    "show-status": {
                        "name": "Show Status",
                        "description": "Print a sample status line from the project action template.",
                        "command": ["python", "-c", "print('sample-project action: ok')"],
                    }
                },
                "task_templates": {
                    "summarize-input": {
                        "name": "Summarize Input",
                        "description": "Create a portable echo task from free-form operator input.",
                        "title": "Summarize: {input}",
                        "kind": "echo",
                        "payload": "summary request={input}",
                        "labels": ["template", "summary"],
                    }
                },
                "pipelines": {
                    "sample-flow": {
                        "name": "Sample Flow",
                        "description": "Two-step sample pipeline using project actions.",
                        "steps": [
                            {
                                "id": "status",
                                "title": "Show sample status",
                                "kind": "project_action",
                                "payload": "show-status",
                            },
                            {
                                "id": "echo",
                                "title": "Echo pipeline input",
                                "kind": "echo",
                                "payload": "pipeline input={input}",
                                "depends_on": ["status"],
                            },
                        ],
                    }
                },
            },
            "enabled": True,
        }
    ],
}


class ProjectRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()

    def bootstrap(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(DEFAULT_PROJECTS_PAYLOAD, indent=2), encoding="utf-8")

    def list_projects(self, *, include_disabled: bool = False) -> list[ProjectRecord]:
        payload = self._load_payload()
        projects: list[ProjectRecord] = []
        for item in payload.get("projects", []):
            if not isinstance(item, dict):
                continue
            project = ProjectRecord(
                id=str(item.get("id", "")).strip(),
                name=str(item.get("name", "")).strip(),
                path=str(item.get("path", "")).strip(),
                description=str(item.get("description", "")).strip(),
                tags=[str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                executor=item.get("executor") if isinstance(item.get("executor"), dict) else None,
                enabled=bool(item.get("enabled", True)),
            )
            if not project.id or not project.name or not project.path:
                continue
            if include_disabled or project.enabled:
                projects.append(project)
        return sorted(projects, key=lambda item: item.id)

    def get_project(self, project_id: str) -> ProjectRecord | None:
        needle = project_id.strip()
        if not needle:
            return None
        for project in self.list_projects(include_disabled=True):
            if project.id == needle:
                return project
        return None

    def enabled_count(self) -> int:
        return len(self.list_projects())

    def resolve_project_path(self, project: ProjectRecord) -> Path:
        project_path = Path(project.path).expanduser()
        if project_path.is_absolute():
            return project_path
        return (self.path.parent / project_path).resolve()

    def list_project_actions(self, project_id: str) -> list[ProjectActionRecord]:
        project = self.get_project(project_id)
        if project is None:
            return []
        executor = project.executor or {}
        actions = executor.get("actions", {})
        if not isinstance(actions, dict):
            return []
        records: list[ProjectActionRecord] = []
        default_type = str(executor.get("type", "local-command"))
        for action_id, item in actions.items():
            if not isinstance(action_id, str) or not isinstance(item, dict):
                continue
            raw_command = item.get("command")
            if not isinstance(raw_command, list) or not raw_command or not all(isinstance(token, str) for token in raw_command):
                continue
            records.append(
                ProjectActionRecord(
                    id=action_id.strip(),
                    name=str(item.get("name") or action_id).strip(),
                    description=str(item.get("description", "")).strip(),
                    command=list(raw_command),
                    executor_type=str(item.get("type") or default_type),
                )
            )
        return sorted((record for record in records if record.id), key=lambda item: item.id)

    def get_project_action(self, project_id: str, action_id: str) -> ProjectActionRecord | None:
        needle = action_id.strip()
        if not needle:
            return None
        for action in self.list_project_actions(project_id):
            if action.id == needle:
                return action
        return None

    def list_project_pipelines(self, project_id: str) -> list[ProjectPipelineRecord]:
        project = self.get_project(project_id)
        if project is None:
            return []
        executor = project.executor or {}
        raw_pipelines = executor.get("pipelines", {})
        if not isinstance(raw_pipelines, dict):
            return []
        pipelines: list[ProjectPipelineRecord] = []
        for pipeline_id, item in raw_pipelines.items():
            if not isinstance(pipeline_id, str) or not isinstance(item, dict):
                continue
            raw_steps = item.get("steps")
            if not isinstance(raw_steps, list) or not raw_steps:
                continue
            steps: list[ProjectPipelineStepRecord] = []
            for step_item in raw_steps:
                if not isinstance(step_item, dict):
                    continue
                step_id = str(step_item.get("id", "")).strip()
                title = str(step_item.get("title", "")).strip()
                kind = str(step_item.get("kind", "")).strip()
                if not step_id or not title or not kind:
                    continue
                depends_on = [
                    str(dep).strip()
                    for dep in step_item.get("depends_on", [])
                    if str(dep).strip()
                ] if isinstance(step_item.get("depends_on", []), list) else []
                steps.append(
                    ProjectPipelineStepRecord(
                        id=step_id,
                        title=title,
                        kind=kind,
                        payload=str(step_item.get("payload", "")),
                        depends_on=depends_on,
                    )
                )
            if not steps:
                continue
            pipelines.append(
                ProjectPipelineRecord(
                    id=pipeline_id.strip(),
                    name=str(item.get("name") or pipeline_id).strip(),
                    description=str(item.get("description", "")).strip(),
                    steps=steps,
                )
            )
        return sorted((pipeline for pipeline in pipelines if pipeline.id), key=lambda item: item.id)

    def get_project_pipeline(self, project_id: str, pipeline_id: str) -> ProjectPipelineRecord | None:
        needle = pipeline_id.strip()
        if not needle:
            return None
        for pipeline in self.list_project_pipelines(project_id):
            if pipeline.id == needle:
                return pipeline
        return None

    def list_project_task_templates(self, project_id: str) -> list[ProjectTaskTemplateRecord]:
        project = self.get_project(project_id)
        if project is None:
            return []
        executor = project.executor or {}
        raw_templates = executor.get("task_templates", {})
        if not isinstance(raw_templates, dict):
            return []
        templates: list[ProjectTaskTemplateRecord] = []
        for template_id, item in raw_templates.items():
            if not isinstance(template_id, str) or not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            kind = str(item.get("kind", "")).strip()
            if not title or not kind:
                continue
            labels = [
                str(label).strip()
                for label in item.get("labels", [])
                if str(label).strip()
            ] if isinstance(item.get("labels", []), list) else []
            templates.append(
                ProjectTaskTemplateRecord(
                    id=template_id.strip(),
                    name=str(item.get("name") or template_id).strip(),
                    description=str(item.get("description", "")).strip(),
                    title=title,
                    kind=kind,
                    payload=str(item.get("payload", "")),
                    labels=labels,
                )
            )
        return sorted((template for template in templates if template.id), key=lambda item: item.id)

    def get_project_task_template(self, project_id: str, template_id: str) -> ProjectTaskTemplateRecord | None:
        needle = template_id.strip()
        if not needle:
            return None
        for template in self.list_project_task_templates(project_id):
            if template.id == needle:
                return template
        return None

    def _load_payload(self) -> dict:
        self.bootstrap()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("projects file must contain a JSON object")
        return raw
