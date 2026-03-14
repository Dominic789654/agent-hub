from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


SUPPORTED_TASK_KINDS = {"noop", "echo", "sleep", "project_command", "project_action"}


@dataclass(slots=True)
class Task:
    id: str
    title: str
    project_id: str | None
    pipeline_run_id: str | None
    kind: str
    payload: str
    status: TaskStatus
    attempt_count: int
    last_error: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class RuntimeStatus:
    dispatcher_state: str
    heartbeat_at: str | None
    last_task_id: str | None
    note: str | None
    project_count: int
    queued_count: int
    ready_queued_count: int
    blocked_queued_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    blocked_count: int
    needs_human_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProjectRecord:
    id: str
    name: str
    path: str
    description: str
    tags: list[str]
    executor: dict[str, Any] | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProjectActionRecord:
    id: str
    name: str
    description: str
    command: list[str]
    executor_type: str = "local-command"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProjectPipelineStepRecord:
    id: str
    title: str
    kind: str
    payload: str = ""
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProjectPipelineRecord:
    id: str
    name: str
    description: str
    steps: list[ProjectPipelineStepRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(slots=True)
class ProjectTaskTemplateRecord:
    id: str
    name: str
    description: str
    title: str
    kind: str
    payload: str = ""
    labels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineRun:
    id: str
    project_id: str
    pipeline_id: str
    input_value: str
    created_at: str
    updated_at: str
    task_count: int
    queued_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    blocked_count: int
    needs_human_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "pipeline_id": self.pipeline_id,
            "input": self.input_value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "task_count": self.task_count,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "blocked_count": self.blocked_count,
            "needs_human_count": self.needs_human_count,
        }


@dataclass(slots=True)
class TaskRun:
    id: int
    task_id: str
    status: RunStatus
    log: str
    created_at: str
    updated_at: str
    started_at: str
    finished_at: str | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class TaskDetail:
    task: Task
    runs: list[TaskRun]
    dependency_ids: list[str] = field(default_factory=list)
    unresolved_dependency_ids: list[str] = field(default_factory=list)
    dependent_ids: list[str] = field(default_factory=list)
    incomplete_dependent_ids: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    notes: list["NoteRecord"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
            "dependency_ids": list(self.dependency_ids),
            "unresolved_dependency_ids": list(self.unresolved_dependency_ids),
            "dependent_ids": list(self.dependent_ids),
            "incomplete_dependent_ids": list(self.incomplete_dependent_ids),
            "labels": list(self.labels),
            "notes": [note.to_dict() for note in self.notes],
        }


@dataclass(slots=True)
class RecentRun:
    run: TaskRun
    task: Task

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "task": self.task.to_dict(),
        }


@dataclass(slots=True)
class PipelineRunDetail:
    pipeline_run: PipelineRun
    tasks: list[Task]
    labels: list[str] = field(default_factory=list)
    notes: list["NoteRecord"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_run": self.pipeline_run.to_dict(),
            "tasks": [task.to_dict() for task in self.tasks],
            "labels": list(self.labels),
            "notes": [note.to_dict() for note in self.notes],
        }


@dataclass(slots=True)
class TaskNeighbors:
    task: Task
    dependencies: list[Task] = field(default_factory=list)
    dependents: list[Task] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "dependencies": [task.to_dict() for task in self.dependencies],
            "dependents": [task.to_dict() for task in self.dependents],
        }


@dataclass(slots=True)
class NoteRecord:
    id: int
    body: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SavedQueryRecord:
    id: str
    scope: str
    name: str
    description: str
    filters: dict[str, str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HumanInboxItem:
    task: Task
    reason: str
    labels: list[str] = field(default_factory=list)
    latest_note: NoteRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "reason": self.reason,
            "labels": list(self.labels),
            "latest_note": self.latest_note.to_dict() if self.latest_note is not None else None,
        }


@dataclass(slots=True)
class SavedQueryExecutionResult:
    saved_query: SavedQueryRecord
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "saved_query": self.saved_query.to_dict(),
            "items": list(self.items),
        }


@dataclass(slots=True)
class DashboardSnapshot:
    status: RuntimeStatus
    config: dict[str, Any]
    recent_tasks: list[Task] = field(default_factory=list)
    human_inbox: list[HumanInboxItem] = field(default_factory=list)
    recent_pipeline_runs: list[PipelineRun] = field(default_factory=list)
    recent_runs: list[RecentRun] = field(default_factory=list)
    saved_queries: list[SavedQueryRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.to_dict(),
            "config": dict(self.config),
            "recent_tasks": [task.to_dict() for task in self.recent_tasks],
            "human_inbox": [item.to_dict() for item in self.human_inbox],
            "recent_pipeline_runs": [item.to_dict() for item in self.recent_pipeline_runs],
            "recent_runs": [item.to_dict() for item in self.recent_runs],
            "saved_queries": [item.to_dict() for item in self.saved_queries],
        }
