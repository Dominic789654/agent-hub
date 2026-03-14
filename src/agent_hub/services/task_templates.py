from __future__ import annotations

from dataclasses import dataclass

from agent_hub.models import ProjectTaskTemplateRecord, Task
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import TaskRepository


@dataclass(slots=True)
class TaskTemplateInstantiationResult:
    project_id: str
    template_id: str
    input_value: str
    task: Task
    labels: list[str]

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "template_id": self.template_id,
            "input": self.input_value,
            "task": self.task.to_dict(),
            "labels": list(self.labels),
        }


@dataclass(slots=True)
class TaskTemplateService:
    task_repository: TaskRepository
    project_registry: ProjectRegistry

    def instantiate(
        self,
        project_id: str,
        template_id: str,
        *,
        input_value: str = "",
        depends_on: list[str] | None = None,
    ) -> TaskTemplateInstantiationResult:
        project = self.project_registry.get_project(project_id)
        if project is None:
            raise ValueError(f"unknown project_id: {project_id}")
        template = self.project_registry.get_project_task_template(project_id, template_id)
        if template is None:
            raise ValueError(f"unknown project task template: {template_id}")

        self._validate_template(project_id, template)
        task = self.task_repository.create_task(
            title=self._render_value(template.title, project_id=project_id, template_id=template_id, input_value=input_value),
            kind=template.kind,
            payload=self._render_value(template.payload, project_id=project_id, template_id=template_id, input_value=input_value),
            project_id=project_id,
            depends_on=depends_on,
        )
        labels: list[str] = []
        for label in template.labels:
            labels = self.task_repository.add_task_label(task.id, label)
        return TaskTemplateInstantiationResult(
            project_id=project_id,
            template_id=template_id,
            input_value=input_value,
            task=task,
            labels=labels,
        )

    def _validate_template(self, project_id: str, template: ProjectTaskTemplateRecord) -> None:
        if template.kind == "project_action" and self.project_registry.get_project_action(project_id, template.payload) is None:
            raise ValueError(f"unknown project action: {template.payload}")

    @staticmethod
    def _render_value(raw: str, *, project_id: str, template_id: str, input_value: str) -> str:
        return raw.replace("{project_id}", project_id).replace("{template_id}", template_id).replace("{input}", input_value)
