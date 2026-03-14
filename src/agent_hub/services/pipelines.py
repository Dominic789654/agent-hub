from __future__ import annotations

from dataclasses import dataclass

from agent_hub.models import PipelineRun, ProjectPipelineRecord, Task
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import TaskRepository


@dataclass(slots=True)
class PipelineInstantiationResult:
    pipeline_run: PipelineRun
    project_id: str
    pipeline_id: str
    input_value: str
    tasks: list[Task]

    def to_dict(self) -> dict:
        return {
            "pipeline_run": self.pipeline_run.to_dict(),
            "project_id": self.project_id,
            "pipeline_id": self.pipeline_id,
            "input": self.input_value,
            "tasks": [task.to_dict() for task in self.tasks],
        }


@dataclass(slots=True)
class PipelineService:
    task_repository: TaskRepository
    project_registry: ProjectRegistry

    def instantiate(self, project_id: str, pipeline_id: str, *, input_value: str = "") -> PipelineInstantiationResult:
        project = self.project_registry.get_project(project_id)
        if project is None:
            raise ValueError(f"unknown project_id: {project_id}")
        pipeline = self.project_registry.get_project_pipeline(project_id, pipeline_id)
        if pipeline is None:
            raise ValueError(f"unknown project pipeline: {pipeline_id}")

        self._validate_pipeline(pipeline)
        pipeline_run = self.task_repository.create_pipeline_run(project_id, pipeline_id, input_value)
        created_by_step: dict[str, Task] = {}
        created_tasks: list[Task] = []
        for step in pipeline.steps:
            depends_on = [created_by_step[step_id].id for step_id in step.depends_on]
            task = self.task_repository.create_task(
                title=self._render_value(step.title, project_id=project_id, pipeline_id=pipeline_id, step_id=step.id, input_value=input_value),
                kind=step.kind,
                payload=self._render_value(step.payload, project_id=project_id, pipeline_id=pipeline_id, step_id=step.id, input_value=input_value),
                project_id=project_id,
                depends_on=depends_on,
                pipeline_run_id=pipeline_run.id,
            )
            created_by_step[step.id] = task
            created_tasks.append(task)
        refreshed_pipeline_run = self.task_repository.get_pipeline_run(pipeline_run.id)
        assert refreshed_pipeline_run is not None
        return PipelineInstantiationResult(
            pipeline_run=refreshed_pipeline_run,
            project_id=project_id,
            pipeline_id=pipeline_id,
            input_value=input_value,
            tasks=created_tasks,
        )

    @staticmethod
    def _validate_pipeline(pipeline: ProjectPipelineRecord) -> None:
        seen: set[str] = set()
        for step in pipeline.steps:
            if step.id in seen:
                raise ValueError(f"duplicate pipeline step id: {step.id}")
            seen.add(step.id)
        for step in pipeline.steps:
            for dependency_id in step.depends_on:
                if dependency_id not in seen:
                    raise ValueError(f"unknown pipeline dependency step id: {dependency_id}")

    @staticmethod
    def _render_value(raw: str, *, project_id: str, pipeline_id: str, step_id: str, input_value: str) -> str:
        return (
            raw.replace("{project_id}", project_id)
            .replace("{pipeline_id}", pipeline_id)
            .replace("{step_id}", step_id)
            .replace("{input}", input_value)
        )
