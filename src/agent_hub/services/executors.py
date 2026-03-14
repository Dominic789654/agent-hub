from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_hub.models import ProjectActionRecord, ProjectRecord, Task
from agent_hub.projects import ProjectRegistry


LogWriter = Callable[[str], None]


@dataclass(slots=True)
class TaskExecutorRegistry:
    project_registry: ProjectRegistry | None = None
    sleep_cap_seconds: float = 30.0

    def execute(self, task: Task, append_log: LogWriter) -> None:
        if task.kind == "noop":
            append_log("[noop] no work performed\n")
            return
        if task.kind == "echo":
            append_log(f"[echo] {task.payload}\n")
            return
        if task.kind == "sleep":
            seconds = float(task.payload or "0")
            if seconds < 0:
                raise ValueError("sleep task payload must be non-negative seconds")
            append_log(f"[sleep] seconds={seconds}\n")
            time.sleep(min(seconds, self.sleep_cap_seconds))
            return
        if task.kind == "project_command":
            self._execute_project_command(task, append_log)
            return
        if task.kind == "project_action":
            self._execute_project_action(task, append_log)
            return
        raise ValueError(f"unsupported task kind: {task.kind}")

    def _execute_project_command(self, task: Task, append_log: LogWriter) -> None:
        project = self._require_project(task, "project_command")
        executor = project.executor or {}
        executor_type = str(executor.get("type", ""))
        raw_command = executor.get("command")
        if executor_type != "local-command":
            raise ValueError("project executor type must be local-command")
        if not isinstance(raw_command, list) or not raw_command or not all(isinstance(item, str) for item in raw_command):
            raise ValueError("project executor command must be a non-empty string list")
        self._run_local_command(
            task=task,
            project=project,
            append_log=append_log,
            raw_command=list(raw_command),
            log_prefix="project_command",
        )

    def _execute_project_action(self, task: Task, append_log: LogWriter) -> None:
        project = self._require_project(task, "project_action")
        action = self.project_registry.get_project_action(project.id, task.payload) if self.project_registry else None
        if action is None:
            raise ValueError(f"unknown project action: {task.payload}")
        if action.executor_type != "local-command":
            raise ValueError("project action executor type must be local-command")
        self._run_local_command(
            task=task,
            project=project,
            append_log=append_log,
            raw_command=action.command,
            log_prefix=f"project_action:{action.id}",
            action=action,
        )

    def _require_project(self, task: Task, kind: str) -> ProjectRecord:
        if self.project_registry is None:
            raise ValueError(f"project registry is required for {kind} tasks")
        if not task.project_id:
            raise ValueError(f"{kind} tasks require project_id")
        project = self.project_registry.get_project(task.project_id)
        if project is None:
            raise ValueError(f"unknown project_id: {task.project_id}")
        return project

    def _run_local_command(
        self,
        task: Task,
        project: ProjectRecord,
        append_log: LogWriter,
        raw_command: list[str],
        log_prefix: str,
        action: ProjectActionRecord | None = None,
    ) -> None:
        assert self.project_registry is not None
        cwd = self.project_registry.resolve_project_path(project)
        command = [self._render_token(token, task, project, cwd, action) for token in raw_command]
        append_log(f"[{log_prefix}] project={project.id} cwd={cwd}\n")
        if action is not None:
            append_log(f"[{log_prefix}] action={action.id}\n")
        append_log(f"[{log_prefix}] command={command!r}\n")
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.stdout:
            append_log(f"[stdout]\n{completed.stdout}")
            if not completed.stdout.endswith("\n"):
                append_log("\n")
        if completed.stderr:
            append_log(f"[stderr]\n{completed.stderr}")
            if not completed.stderr.endswith("\n"):
                append_log("\n")
        append_log(f"[exit] code={completed.returncode}\n")
        if completed.returncode != 0:
            raise RuntimeError(f"project command exited with code {completed.returncode}")

    @staticmethod
    def _render_token(
        token: str,
        task: Task,
        project: ProjectRecord,
        cwd: Path,
        action: ProjectActionRecord | None = None,
    ) -> str:
        rendered = (
            token.replace("{payload}", task.payload)
            .replace("{project_id}", project.id)
            .replace("{project_path}", str(cwd))
            .replace("{task_id}", task.id)
        )
        if action is not None:
            rendered = rendered.replace("{action_id}", action.id).replace("{action_name}", action.name)
        return rendered
