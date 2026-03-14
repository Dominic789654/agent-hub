from __future__ import annotations

import signal
from dataclasses import dataclass
from threading import Event

from agent_hub.models import RunStatus, Task
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository
from agent_hub.services.executors import TaskExecutorRegistry


@dataclass(slots=True)
class Dispatcher:
    task_repository: TaskRepository
    runtime_repository: RuntimeRepository
    project_registry: ProjectRegistry | None = None
    poll_interval: float = 1.0
    sleep_cap_seconds: float = 30.0

    def run_forever(self) -> None:
        stop_event = Event()

        def _stop(_signum: int, _frame: object) -> None:
            stop_event.set()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        self.runtime_repository.heartbeat("idle", note="dispatcher started")

        while not stop_event.is_set():
            task = self.task_repository.claim_next_task()
            if task is None:
                self.runtime_repository.heartbeat("idle", note="waiting for queued tasks")
                stop_event.wait(self.poll_interval)
                continue

            self.runtime_repository.heartbeat(
                "running", note=f"processing {task.kind}", last_task_id=task.id
            )
            run = self.task_repository.create_run(task.id)
            self.task_repository.append_run_log(run.id, f"[start] kind={task.kind} payload={task.payload!r}\n")
            try:
                self._process_task(task, run.id)
            except Exception as exc:
                self.task_repository.append_run_log(run.id, f"[error] {exc}\n")
                self.task_repository.finish_run(run.id, RunStatus.FAILED)
                self.task_repository.mark_failed(task.id, str(exc))
                self.runtime_repository.heartbeat(
                    "idle", note=f"task failed: {task.id}", last_task_id=task.id
                )
            else:
                self.task_repository.append_run_log(run.id, "[done] task completed successfully\n")
                self.task_repository.finish_run(run.id, RunStatus.SUCCEEDED)
                self.task_repository.mark_succeeded(task.id)
                self.runtime_repository.heartbeat(
                    "idle", note=f"task finished: {task.id}", last_task_id=task.id
                )

        self.runtime_repository.heartbeat("stopped", note="dispatcher stopped")

    def _process_task(self, task: Task, run_id: int) -> None:
        executor_registry = TaskExecutorRegistry(
            project_registry=self.project_registry,
            sleep_cap_seconds=self.sleep_cap_seconds,
        )
        executor_registry.execute(
            task,
            append_log=lambda message: self.task_repository.append_run_log(run_id, message),
        )
