from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime

from agent_hub.db import Database
from agent_hub.models import (
    HumanInboxItem,
    NoteRecord,
    PipelineRun,
    PipelineRunDetail,
    RecentRun,
    RunStatus,
    RuntimeStatus,
    SavedQueryExecutionResult,
    SUPPORTED_TASK_KINDS,
    SavedQueryRecord,
    Task,
    TaskDetail,
    TaskNeighbors,
    TaskRun,
    TaskStatus,
)
from agent_hub.projects import ProjectRegistry


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


SAVED_QUERY_ALLOWED_FILTERS = {
    "tasks": {"project_id", "status", "kind", "pipeline_run_id"},
    "pipeline_runs": {"project_id", "pipeline_id"},
}


class TaskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_task(
        self,
        title: str,
        kind: str = "noop",
        payload: str = "",
        project_id: str | None = None,
        depends_on: list[str] | None = None,
        pipeline_run_id: str | None = None,
    ) -> Task:
        if kind not in SUPPORTED_TASK_KINDS:
            raise ValueError(f"unsupported task kind: {kind}")
        dependency_ids = self._normalize_dependency_ids(depends_on)
        now = utc_now()
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            project_id=project_id,
            pipeline_run_id=pipeline_run_id,
            kind=kind,
            payload=payload,
            status=TaskStatus.QUEUED,
            attempt_count=0,
            last_error=None,
            created_at=now,
            updated_at=now,
            started_at=None,
            finished_at=None,
        )
        with closing(self.db.connect()) as connection:
            if dependency_ids:
                missing = self._find_missing_dependencies(connection, dependency_ids)
                if missing:
                    raise ValueError(f"unknown dependency task ids: {', '.join(missing)}")
            connection.execute(
                """
                INSERT INTO tasks(
                    id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                    created_at, updated_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.project_id,
                    task.pipeline_run_id,
                    task.kind,
                    task.payload,
                    task.status.value,
                    task.attempt_count,
                    task.last_error,
                    task.created_at,
                    task.updated_at,
                    task.started_at,
                    task.finished_at,
                ),
            )
            for dependency_id in dependency_ids:
                connection.execute(
                    """
                    INSERT INTO task_dependencies(task_id, depends_on_task_id)
                    VALUES (?, ?)
                    """,
                    (task.id, dependency_id),
                )
            connection.commit()
        return task

    def list_tasks(
        self,
        limit: int = 100,
        *,
        project_id: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        pipeline_run_id: str | None = None,
    ) -> list[Task]:
        query_limit = max(1, min(limit, 500))
        filters: list[str] = []
        params: list[object] = []
        if project_id:
            filters.append("project_id = ?")
            params.append(project_id)
        if status:
            filters.append("status = ?")
            params.append(status)
        if kind:
            filters.append("kind = ?")
            params.append(kind)
        if pipeline_run_id:
            filters.append("pipeline_run_id = ?")
            params.append(pipeline_run_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks
                {where_clause}
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (*params, query_limit),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def list_human_inbox(self, limit: int = 100, *, project_id: str | None = None) -> list[HumanInboxItem]:
        query_limit = max(1, min(limit, 500))
        actionable_statuses = (
            TaskStatus.NEEDS_HUMAN.value,
            TaskStatus.FAILED.value,
            TaskStatus.BLOCKED.value,
        )
        filters = [f"status IN ({', '.join('?' for _ in actionable_statuses)})"]
        params: list[object] = [*actionable_statuses]
        if project_id:
            filters.append("project_id = ?")
            params.append(project_id)
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks
                WHERE {' AND '.join(filters)}
                ORDER BY datetime(updated_at) DESC, id DESC
                LIMIT ?
                """,
                (*params, query_limit),
            ).fetchall()
        items: list[HumanInboxItem] = []
        for row in rows:
            task = self._row_to_task(row)
            notes = self.list_task_notes(task.id)
            items.append(
                HumanInboxItem(
                    task=task,
                    reason=task.last_error or task.status.value,
                    labels=self.list_task_labels(task.id),
                    latest_note=notes[0] if notes else None,
                )
            )
        return items

    def count_human_inbox(self, *, project_id: str | None = None) -> int:
        actionable_statuses = (
            TaskStatus.NEEDS_HUMAN.value,
            TaskStatus.FAILED.value,
            TaskStatus.BLOCKED.value,
        )
        filters = [f"status IN ({', '.join('?' for _ in actionable_statuses)})"]
        params: list[object] = [*actionable_statuses]
        if project_id:
            filters.append("project_id = ?")
            params.append(project_id)
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM tasks WHERE {' AND '.join(filters)}",
                params,
            ).fetchone()
        return int(row["count"] or 0)

    def get_task(self, task_id: str) -> Task | None:
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                """
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row is not None else None

    def get_task_detail(self, task_id: str) -> TaskDetail | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, task_id, status, log, created_at, updated_at, started_at, finished_at
                FROM runs
                WHERE task_id = ?
                ORDER BY id DESC
                """,
                (task_id,),
            ).fetchall()
            dependency_rows = connection.execute(
                """
                SELECT td.depends_on_task_id AS dependency_id, dep.status AS dependency_status
                FROM task_dependencies td
                INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                WHERE td.task_id = ?
                ORDER BY td.depends_on_task_id
                """,
                (task_id,),
            ).fetchall()
            dependent_rows = connection.execute(
                """
                SELECT td.task_id AS dependent_id, child.status AS dependent_status
                FROM task_dependencies td
                INNER JOIN tasks child ON child.id = td.task_id
                WHERE td.depends_on_task_id = ?
                ORDER BY td.task_id
                """,
                (task_id,),
            ).fetchall()
            label_rows = connection.execute(
                """
                SELECT label
                FROM task_labels
                WHERE task_id = ?
                ORDER BY rowid ASC
                """,
                (task_id,),
            ).fetchall()
            note_rows = connection.execute(
                """
                SELECT id, body, created_at, updated_at
                FROM task_notes
                WHERE task_id = ?
                ORDER BY id DESC
                """,
                (task_id,),
            ).fetchall()
        dependency_ids = [str(row["dependency_id"]) for row in dependency_rows]
        unresolved_dependency_ids = [
            str(row["dependency_id"])
            for row in dependency_rows
            if str(row["dependency_status"]) != TaskStatus.SUCCEEDED.value
        ]
        dependent_ids = [str(row["dependent_id"]) for row in dependent_rows]
        incomplete_dependent_ids = [
            str(row["dependent_id"])
            for row in dependent_rows
            if str(row["dependent_status"]) != TaskStatus.SUCCEEDED.value
        ]
        return TaskDetail(
            task=task,
            runs=[self._row_to_run(row) for row in rows],
            dependency_ids=dependency_ids,
            unresolved_dependency_ids=unresolved_dependency_ids,
            dependent_ids=dependent_ids,
            incomplete_dependent_ids=incomplete_dependent_ids,
            labels=[str(row["label"]) for row in label_rows],
            notes=[self._row_to_note(row) for row in note_rows],
        )

    def get_task_neighbors(self, task_id: str) -> TaskNeighbors | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        with closing(self.db.connect()) as connection:
            dependency_rows = connection.execute(
                """
                SELECT dep.id, dep.title, dep.project_id, dep.pipeline_run_id, dep.kind, dep.payload, dep.status,
                       dep.attempt_count, dep.last_error, dep.created_at, dep.updated_at, dep.started_at, dep.finished_at
                FROM task_dependencies td
                INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                WHERE td.task_id = ?
                ORDER BY dep.id
                """,
                (task_id,),
            ).fetchall()
            dependent_rows = connection.execute(
                """
                SELECT child.id, child.title, child.project_id, child.pipeline_run_id, child.kind, child.payload, child.status,
                       child.attempt_count, child.last_error, child.created_at, child.updated_at, child.started_at, child.finished_at
                FROM task_dependencies td
                INNER JOIN tasks child ON child.id = td.task_id
                WHERE td.depends_on_task_id = ?
                ORDER BY child.id
                """,
                (task_id,),
            ).fetchall()
        return TaskNeighbors(
            task=task,
            dependencies=[self._row_to_task(row) for row in dependency_rows],
            dependents=[self._row_to_task(row) for row in dependent_rows],
        )

    def list_recent_runs(self, limit: int = 20) -> list[RecentRun]:
        query_limit = max(1, min(limit, 200))
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    r.id AS run_id,
                    r.task_id AS run_task_id,
                    r.status AS run_status,
                    r.log AS run_log,
                    r.created_at AS run_created_at,
                    r.updated_at AS run_updated_at,
                    r.started_at AS run_started_at,
                    r.finished_at AS run_finished_at,
                    t.id AS task_id,
                    t.title AS task_title,
                    t.project_id AS task_project_id,
                    t.pipeline_run_id AS task_pipeline_run_id,
                    t.kind AS task_kind,
                    t.payload AS task_payload,
                    t.status AS task_status,
                    t.attempt_count AS task_attempt_count,
                    t.last_error AS task_last_error,
                    t.created_at AS task_created_at,
                    t.updated_at AS task_updated_at,
                    t.started_at AS task_started_at,
                    t.finished_at AS task_finished_at
                FROM runs r
                INNER JOIN tasks t ON t.id = r.task_id
                ORDER BY r.id DESC
                LIMIT ?
                """,
                (query_limit,),
            ).fetchall()
        recent_runs: list[RecentRun] = []
        for row in rows:
            recent_runs.append(
                RecentRun(
                    run=TaskRun(
                        id=int(row["run_id"]),
                        task_id=str(row["run_task_id"]),
                        status=RunStatus(str(row["run_status"])),
                        log=str(row["run_log"]),
                        created_at=str(row["run_created_at"]),
                        updated_at=str(row["run_updated_at"]),
                        started_at=str(row["run_started_at"]),
                        finished_at=row["run_finished_at"],
                    ),
                    task=Task(
                        id=str(row["task_id"]),
                        title=str(row["task_title"]),
                        project_id=row["task_project_id"],
                        pipeline_run_id=row["task_pipeline_run_id"],
                        kind=str(row["task_kind"]),
                        payload=str(row["task_payload"]),
                        status=TaskStatus(str(row["task_status"])),
                        attempt_count=int(row["task_attempt_count"]),
                        last_error=row["task_last_error"],
                        created_at=str(row["task_created_at"]),
                        updated_at=str(row["task_updated_at"]),
                        started_at=row["task_started_at"],
                        finished_at=row["task_finished_at"],
                    ),
                )
            )
        return recent_runs

    def claim_next_task(self) -> Task | None:
        with closing(self.db.connect()) as connection:
            connection.isolation_level = None
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks t
                WHERE status = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM task_dependencies td
                      INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                      WHERE td.task_id = t.id
                        AND dep.status <> ?
                  )
                ORDER BY datetime(created_at) ASC
                LIMIT 1
                """,
                (TaskStatus.QUEUED.value, TaskStatus.SUCCEEDED.value),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None

            task = self._row_to_task(row)
            now = utc_now()
            claimed = replace(
                task,
                status=TaskStatus.RUNNING,
                attempt_count=task.attempt_count + 1,
                started_at=now,
                updated_at=now,
                last_error=None,
            )
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, attempt_count = ?, started_at = ?, updated_at = ?, last_error = ?
                WHERE id = ? AND status = ?
                """,
                (
                    claimed.status.value,
                    claimed.attempt_count,
                    claimed.started_at,
                    claimed.updated_at,
                    claimed.last_error,
                    claimed.id,
                    TaskStatus.QUEUED.value,
                ),
            )
            if connection.total_changes == 0:
                connection.execute("ROLLBACK")
                return None
            connection.execute("COMMIT")
            return claimed

    def mark_succeeded(self, task_id: str) -> Task:
        task = self._mark_final(task_id=task_id, status=TaskStatus.SUCCEEDED, last_error=None)
        self._release_ready_blocked_dependents()
        return task

    def mark_failed(self, task_id: str, error_message: str) -> Task:
        task = self._mark_final(task_id=task_id, status=TaskStatus.FAILED, last_error=error_message)
        self._propagate_blocked_descendants(task_id, reason=f"blocked by failed dependency: {task_id}")
        return task

    def cancel_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        if task.status is not TaskStatus.QUEUED:
            raise ValueError("only queued tasks can be cancelled")
        cancelled = self._mark_final(task_id=task_id, status=TaskStatus.CANCELLED, last_error=None)
        self._propagate_blocked_descendants(task_id, reason=f"blocked by cancelled dependency: {task_id}")
        return cancelled

    def mark_needs_human(self, task_id: str, note: str | None = None) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        if task.status == TaskStatus.RUNNING:
            raise ValueError("running tasks cannot be marked needs_human")
        message = note.strip() if note else "marked for human intervention"
        flagged = self._mark_final(task_id=task_id, status=TaskStatus.NEEDS_HUMAN, last_error=message)
        self._propagate_blocked_descendants(task_id, reason=f"blocked by needs_human dependency: {task_id}")
        return flagged

    def retry_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        if task.status not in {
            TaskStatus.FAILED,
            TaskStatus.SUCCEEDED,
            TaskStatus.CANCELLED,
            TaskStatus.BLOCKED,
            TaskStatus.NEEDS_HUMAN,
        }:
            raise ValueError("only finished tasks can be retried")
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, last_error = NULL, updated_at = ?, started_at = NULL, finished_at = NULL
                WHERE id = ?
                """,
                (TaskStatus.QUEUED.value, now, task_id),
            )
            row = connection.execute(
                """
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            connection.commit()
        self._release_ready_blocked_dependents()
        assert row is not None
        return self._row_to_task(row)

    def _mark_final(self, task_id: str, status: TaskStatus, last_error: str | None) -> Task:
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, last_error = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (status.value, last_error, now, now, task_id),
            )
            row = connection.execute(
                """
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            connection.commit()
        if row is None:
            raise KeyError(f"task not found: {task_id}")
        return self._row_to_task(row)

    def counts_by_status(self) -> dict[str, int]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status").fetchall()
        counts = {status.value: 0 for status in TaskStatus}
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts

    def count_queued_readiness(self) -> tuple[int, int]:
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(
                        CASE
                            WHEN t.status = :queued
                             AND NOT EXISTS (
                                 SELECT 1
                                 FROM task_dependencies td
                                 INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                                 WHERE td.task_id = t.id
                                   AND dep.status <> :succeeded
                             )
                            THEN 1 ELSE 0
                        END
                    ) AS ready_count,
                    SUM(
                        CASE
                            WHEN t.status = :queued
                             AND EXISTS (
                                 SELECT 1
                                 FROM task_dependencies td
                                 INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                                 WHERE td.task_id = t.id
                                   AND dep.status <> :succeeded
                             )
                            THEN 1 ELSE 0
                        END
                    ) AS blocked_count
                FROM tasks t
                """,
                {
                    "queued": TaskStatus.QUEUED.value,
                    "succeeded": TaskStatus.SUCCEEDED.value,
                },
            ).fetchone()
        return int(row["ready_count"] or 0), int(row["blocked_count"] or 0)

    def list_dependencies(self, task_id: str) -> list[str]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT depends_on_task_id
                FROM task_dependencies
                WHERE task_id = ?
                ORDER BY depends_on_task_id
                """,
                (task_id,),
            ).fetchall()
        return [str(row["depends_on_task_id"]) for row in rows]

    def create_run(self, task_id: str) -> TaskRun:
        now = utc_now()
        with closing(self.db.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs(task_id, status, log, created_at, updated_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, RunStatus.RUNNING.value, "", now, now, now, None),
            )
            row = connection.execute(
                """
                SELECT id, task_id, status, log, created_at, updated_at, started_at, finished_at
                FROM runs
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._row_to_run(row)

    def create_pipeline_run(self, project_id: str, pipeline_id: str, input_value: str = "") -> PipelineRun:
        pipeline_run_id = str(uuid.uuid4())
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs(id, project_id, pipeline_id, input_value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (pipeline_run_id, project_id, pipeline_id, input_value, now, now),
            )
            connection.commit()
        created = self.get_pipeline_run(pipeline_run_id)
        assert created is not None
        return created

    def get_pipeline_run(self, pipeline_run_id: str) -> PipelineRun | None:
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM (" + self._pipeline_run_select() + ") WHERE id = ?",
                (pipeline_run_id,),
            ).fetchone()
        return self._row_to_pipeline_run(row) if row is not None else None

    def list_pipeline_runs(
        self,
        limit: int = 20,
        *,
        project_id: str | None = None,
        pipeline_id: str | None = None,
    ) -> list[PipelineRun]:
        query_limit = max(1, min(limit, 200))
        filters: list[str] = []
        params: list[object] = []
        if project_id:
            filters.append("project_id = ?")
            params.append(project_id)
        if pipeline_id:
            filters.append("pipeline_id = ?")
            params.append(pipeline_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM (" + self._pipeline_run_select() + f") {where_clause} ORDER BY datetime(created_at) DESC LIMIT ?",
                (*params, query_limit),
            ).fetchall()
        return [self._row_to_pipeline_run(row) for row in rows]

    def get_pipeline_run_detail(self, pipeline_run_id: str) -> PipelineRunDetail | None:
        pipeline_run = self.get_pipeline_run(pipeline_run_id)
        if pipeline_run is None:
            return None
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, title, project_id, pipeline_run_id, kind, payload, status, attempt_count, last_error,
                       created_at, updated_at, started_at, finished_at
                FROM tasks
                WHERE pipeline_run_id = ?
                ORDER BY rowid ASC
                """,
                (pipeline_run_id,),
            ).fetchall()
        return PipelineRunDetail(
            pipeline_run=pipeline_run,
            tasks=[self._row_to_task(row) for row in rows],
            labels=self.list_pipeline_run_labels(pipeline_run_id),
            notes=self.list_pipeline_run_notes(pipeline_run_id),
        )

    def count_pipeline_runs(self) -> int:
        with closing(self.db.connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM pipeline_runs").fetchone()
        return int(row["count"] or 0)

    def add_task_note(self, task_id: str, body: str) -> NoteRecord:
        if self.get_task(task_id) is None:
            raise KeyError(f"task not found: {task_id}")
        text = body.strip()
        if not text:
            raise ValueError("note body is required")
        now = utc_now()
        with closing(self.db.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO task_notes(task_id, body, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, text, now, now),
            )
            row = connection.execute(
                """
                SELECT id, body, created_at, updated_at
                FROM task_notes
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._row_to_note(row)

    def list_task_notes(self, task_id: str) -> list[NoteRecord]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, body, created_at, updated_at
                FROM task_notes
                WHERE task_id = ?
                ORDER BY id DESC
                """,
                (task_id,),
            ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def add_task_label(self, task_id: str, label: str) -> list[str]:
        if self.get_task(task_id) is None:
            raise KeyError(f"task not found: {task_id}")
        normalized = label.strip()
        if not normalized:
            raise ValueError("label is required")
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                INSERT INTO task_labels(task_id, label, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id, label) DO NOTHING
                """,
                (task_id, normalized, now),
            )
            connection.commit()
        return self.list_task_labels(task_id)

    def remove_task_label(self, task_id: str, label: str) -> list[str]:
        if self.get_task(task_id) is None:
            raise KeyError(f"task not found: {task_id}")
        normalized = label.strip()
        if not normalized:
            raise ValueError("label is required")
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                DELETE FROM task_labels
                WHERE task_id = ? AND label = ?
                """,
                (task_id, normalized),
            )
            connection.commit()
        return self.list_task_labels(task_id)

    def list_task_labels(self, task_id: str) -> list[str]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT label
                FROM task_labels
                WHERE task_id = ?
                ORDER BY rowid ASC
                """,
                (task_id,),
            ).fetchall()
        return [str(row["label"]) for row in rows]

    def add_pipeline_run_note(self, pipeline_run_id: str, body: str) -> NoteRecord:
        if self.get_pipeline_run(pipeline_run_id) is None:
            raise KeyError(f"pipeline run not found: {pipeline_run_id}")
        text = body.strip()
        if not text:
            raise ValueError("note body is required")
        now = utc_now()
        with closing(self.db.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO pipeline_run_notes(pipeline_run_id, body, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (pipeline_run_id, text, now, now),
            )
            row = connection.execute(
                """
                SELECT id, body, created_at, updated_at
                FROM pipeline_run_notes
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._row_to_note(row)

    def list_pipeline_run_notes(self, pipeline_run_id: str) -> list[NoteRecord]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, body, created_at, updated_at
                FROM pipeline_run_notes
                WHERE pipeline_run_id = ?
                ORDER BY id DESC
                """,
                (pipeline_run_id,),
            ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def add_pipeline_run_label(self, pipeline_run_id: str, label: str) -> list[str]:
        if self.get_pipeline_run(pipeline_run_id) is None:
            raise KeyError(f"pipeline run not found: {pipeline_run_id}")
        normalized = label.strip()
        if not normalized:
            raise ValueError("label is required")
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_run_labels(pipeline_run_id, label, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(pipeline_run_id, label) DO NOTHING
                """,
                (pipeline_run_id, normalized, now),
            )
            connection.commit()
        return self.list_pipeline_run_labels(pipeline_run_id)

    def remove_pipeline_run_label(self, pipeline_run_id: str, label: str) -> list[str]:
        if self.get_pipeline_run(pipeline_run_id) is None:
            raise KeyError(f"pipeline run not found: {pipeline_run_id}")
        normalized = label.strip()
        if not normalized:
            raise ValueError("label is required")
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                DELETE FROM pipeline_run_labels
                WHERE pipeline_run_id = ? AND label = ?
                """,
                (pipeline_run_id, normalized),
            )
            connection.commit()
        return self.list_pipeline_run_labels(pipeline_run_id)

    def list_pipeline_run_labels(self, pipeline_run_id: str) -> list[str]:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT label
                FROM pipeline_run_labels
                WHERE pipeline_run_id = ?
                ORDER BY rowid ASC
                """,
                (pipeline_run_id,),
            ).fetchall()
        return [str(row["label"]) for row in rows]

    def create_saved_query(
        self,
        scope: str,
        name: str,
        *,
        description: str = "",
        filters: dict[str, str] | None = None,
    ) -> SavedQueryRecord:
        normalized_scope = scope.strip()
        normalized_name = name.strip()
        if normalized_scope not in SAVED_QUERY_ALLOWED_FILTERS:
            raise ValueError(f"unsupported saved query scope: {scope}")
        if not normalized_name:
            raise ValueError("saved query name is required")
        normalized_filters = self._normalize_saved_query_filters(normalized_scope, filters or {})
        query_id = str(uuid.uuid4())
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                INSERT INTO saved_queries(id, scope, name, description, filters_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (query_id, normalized_scope, normalized_name, description.strip(), json.dumps(normalized_filters, sort_keys=True), now, now),
            )
            row = connection.execute(
                """
                SELECT id, scope, name, description, filters_json, created_at, updated_at
                FROM saved_queries
                WHERE id = ?
                """,
                (query_id,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._row_to_saved_query(row)

    def list_saved_queries(self, scope: str | None = None, limit: int = 100) -> list[SavedQueryRecord]:
        query_limit = max(1, min(limit, 500))
        with closing(self.db.connect()) as connection:
            if scope:
                rows = connection.execute(
                    """
                    SELECT id, scope, name, description, filters_json, created_at, updated_at
                    FROM saved_queries
                    WHERE scope = ?
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    """,
                    (scope, query_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, scope, name, description, filters_json, created_at, updated_at
                    FROM saved_queries
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    """,
                    (query_limit,),
                ).fetchall()
        return [self._row_to_saved_query(row) for row in rows]

    def get_saved_query(self, query_id: str) -> SavedQueryRecord | None:
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                """
                SELECT id, scope, name, description, filters_json, created_at, updated_at
                FROM saved_queries
                WHERE id = ?
                """,
                (query_id,),
            ).fetchone()
        return self._row_to_saved_query(row) if row is not None else None

    def delete_saved_query(self, query_id: str) -> None:
        with closing(self.db.connect()) as connection:
            connection.execute("DELETE FROM saved_queries WHERE id = ?", (query_id,))
            changed = connection.total_changes
            connection.commit()
        if changed == 0:
            raise KeyError(f"saved query not found: {query_id}")

    def apply_saved_query(self, query_id: str, limit: int = 100) -> SavedQueryExecutionResult:
        saved_query = self.get_saved_query(query_id)
        if saved_query is None:
            raise KeyError(f"saved query not found: {query_id}")
        if saved_query.scope == "tasks":
            items = [
                task.to_dict()
                for task in self.list_tasks(
                    limit=limit,
                    project_id=saved_query.filters.get("project_id"),
                    status=saved_query.filters.get("status"),
                    kind=saved_query.filters.get("kind"),
                    pipeline_run_id=saved_query.filters.get("pipeline_run_id"),
                )
            ]
        elif saved_query.scope == "pipeline_runs":
            items = [
                item.to_dict()
                for item in self.list_pipeline_runs(
                    limit=limit,
                    project_id=saved_query.filters.get("project_id"),
                    pipeline_id=saved_query.filters.get("pipeline_id"),
                )
            ]
        else:
            raise ValueError(f"unsupported saved query scope: {saved_query.scope}")
        return SavedQueryExecutionResult(saved_query=saved_query, items=items)

    def retry_pipeline_run(self, pipeline_run_id: str) -> PipelineRunDetail:
        detail = self.get_pipeline_run_detail(pipeline_run_id)
        if detail is None:
            raise KeyError(f"pipeline run not found: {pipeline_run_id}")
        retryable_statuses = {
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.NEEDS_HUMAN.value,
        }
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                f"""
                UPDATE tasks
                SET status = ?, last_error = NULL, updated_at = ?, started_at = NULL, finished_at = NULL
                WHERE pipeline_run_id = ?
                  AND status IN ({", ".join("?" for _ in retryable_statuses)})
                """,
                (TaskStatus.QUEUED.value, now, pipeline_run_id, *sorted(retryable_statuses)),
            )
            connection.commit()
        refreshed = self.get_pipeline_run_detail(pipeline_run_id)
        assert refreshed is not None
        return refreshed

    def cancel_pipeline_run(self, pipeline_run_id: str) -> PipelineRunDetail:
        detail = self.get_pipeline_run_detail(pipeline_run_id)
        if detail is None:
            raise KeyError(f"pipeline run not found: {pipeline_run_id}")
        cancellable_statuses = {
            TaskStatus.QUEUED.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.NEEDS_HUMAN.value,
        }
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                f"""
                UPDATE tasks
                SET status = ?, last_error = ?, updated_at = ?, started_at = NULL, finished_at = ?
                WHERE pipeline_run_id = ?
                  AND status IN ({", ".join("?" for _ in cancellable_statuses)})
                """,
                (
                    TaskStatus.CANCELLED.value,
                    "cancelled by pipeline run",
                    now,
                    now,
                    pipeline_run_id,
                    *sorted(cancellable_statuses),
                ),
            )
            connection.commit()
        refreshed = self.get_pipeline_run_detail(pipeline_run_id)
        assert refreshed is not None
        return refreshed

    def append_run_log(self, run_id: int, message: str) -> TaskRun:
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                UPDATE runs
                SET log = log || ?, updated_at = ?
                WHERE id = ?
                """,
                (message, now, run_id),
            )
            row = connection.execute(
                """
                SELECT id, task_id, status, log, created_at, updated_at, started_at, finished_at
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            connection.commit()
        if row is None:
            raise KeyError(f"run not found: {run_id}")
        return self._row_to_run(row)

    def finish_run(self, run_id: int, status: RunStatus) -> TaskRun:
        now = utc_now()
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (status.value, now, now, run_id),
            )
            row = connection.execute(
                """
                SELECT id, task_id, status, log, created_at, updated_at, started_at, finished_at
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            connection.commit()
        if row is None:
            raise KeyError(f"run not found: {run_id}")
        return self._row_to_run(row)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=str(row["id"]),
            title=str(row["title"]),
            project_id=row["project_id"],
            pipeline_run_id=row["pipeline_run_id"],
            kind=str(row["kind"]),
            payload=str(row["payload"]),
            status=TaskStatus(str(row["status"])),
            attempt_count=int(row["attempt_count"]),
            last_error=row["last_error"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    @staticmethod
    def _pipeline_run_select() -> str:
        return """
            SELECT
                pr.id,
                pr.project_id,
                pr.pipeline_id,
                pr.input_value,
                pr.created_at,
                COALESCE(MAX(t.updated_at), pr.updated_at) AS updated_at,
                COUNT(t.id) AS task_count,
                SUM(CASE WHEN t.status = 'queued' THEN 1 ELSE 0 END) AS queued_count,
                SUM(CASE WHEN t.status = 'running' THEN 1 ELSE 0 END) AS running_count,
                SUM(CASE WHEN t.status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded_count,
                SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN t.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
                SUM(CASE WHEN t.status = 'blocked' THEN 1 ELSE 0 END) AS blocked_count,
                SUM(CASE WHEN t.status = 'needs_human' THEN 1 ELSE 0 END) AS needs_human_count
            FROM pipeline_runs pr
            LEFT JOIN tasks t ON t.pipeline_run_id = pr.id
            GROUP BY pr.id, pr.project_id, pr.pipeline_id, pr.input_value, pr.created_at, pr.updated_at
        """

    @staticmethod
    def _row_to_pipeline_run(row: sqlite3.Row) -> PipelineRun:
        return PipelineRun(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            pipeline_id=str(row["pipeline_id"]),
            input_value=str(row["input_value"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            task_count=int(row["task_count"] or 0),
            queued_count=int(row["queued_count"] or 0),
            running_count=int(row["running_count"] or 0),
            succeeded_count=int(row["succeeded_count"] or 0),
            failed_count=int(row["failed_count"] or 0),
            cancelled_count=int(row["cancelled_count"] or 0),
            blocked_count=int(row["blocked_count"] or 0),
            needs_human_count=int(row["needs_human_count"] or 0),
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> TaskRun:
        return TaskRun(
            id=int(row["id"]),
            task_id=str(row["task_id"]),
            status=RunStatus(str(row["status"])),
            log=str(row["log"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            started_at=str(row["started_at"]),
            finished_at=row["finished_at"],
        )

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> NoteRecord:
        return NoteRecord(
            id=int(row["id"]),
            body=str(row["body"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_saved_query(row: sqlite3.Row) -> SavedQueryRecord:
        raw_filters = json.loads(str(row["filters_json"]))
        filters = {str(key): str(value) for key, value in raw_filters.items()} if isinstance(raw_filters, dict) else {}
        return SavedQueryRecord(
            id=str(row["id"]),
            scope=str(row["scope"]),
            name=str(row["name"]),
            description=str(row["description"]),
            filters=filters,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _normalize_saved_query_filters(scope: str, filters: dict[str, str]) -> dict[str, str]:
        allowed = SAVED_QUERY_ALLOWED_FILTERS[scope]
        normalized: dict[str, str] = {}
        for raw_key, raw_value in filters.items():
            key = str(raw_key).strip()
            value = str(raw_value).strip()
            if not key or not value:
                continue
            if key not in allowed:
                raise ValueError(f"unsupported filter for {scope}: {key}")
            normalized[key] = value
        return normalized

    def _propagate_blocked_descendants(self, task_id: str, reason: str) -> None:
        with closing(self.db.connect()) as connection:
            pending = [task_id]
            seen = {task_id}
            while pending:
                current = pending.pop(0)
                rows = connection.execute(
                    """
                    SELECT t.id
                    FROM task_dependencies td
                    INNER JOIN tasks t ON t.id = td.task_id
                    WHERE td.depends_on_task_id = ?
                      AND t.status IN (?, ?)
                    """,
                    (current, TaskStatus.QUEUED.value, TaskStatus.BLOCKED.value),
                ).fetchall()
                child_ids = [str(row["id"]) for row in rows]
                for child_id in child_ids:
                    connection.execute(
                        """
                        UPDATE tasks
                        SET status = ?, last_error = ?, updated_at = ?, started_at = NULL, finished_at = ?
                        WHERE id = ?
                        """,
                        (TaskStatus.BLOCKED.value, reason, utc_now(), utc_now(), child_id),
                    )
                    if child_id not in seen:
                        seen.add(child_id)
                        pending.append(child_id)
            connection.commit()

    def _release_ready_blocked_dependents(self) -> None:
        with closing(self.db.connect()) as connection:
            rows = connection.execute(
                """
                SELECT t.id
                FROM tasks t
                WHERE t.status = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM task_dependencies td
                      INNER JOIN tasks dep ON dep.id = td.depends_on_task_id
                      WHERE td.task_id = t.id
                        AND dep.status <> ?
                  )
                """,
                (TaskStatus.BLOCKED.value, TaskStatus.SUCCEEDED.value),
            ).fetchall()
            task_ids = [str(row["id"]) for row in rows]
            now = utc_now()
            for task_id in task_ids:
                connection.execute(
                    """
                    UPDATE tasks
                    SET status = ?, last_error = NULL, updated_at = ?, started_at = NULL, finished_at = NULL
                    WHERE id = ?
                    """,
                    (TaskStatus.QUEUED.value, now, task_id),
                )
            connection.commit()

    @staticmethod
    def _normalize_dependency_ids(depends_on: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for raw in depends_on or []:
            task_id = str(raw).strip()
            if task_id and task_id not in normalized:
                normalized.append(task_id)
        return normalized

    @staticmethod
    def _find_missing_dependencies(connection: sqlite3.Connection, dependency_ids: list[str]) -> list[str]:
        if not dependency_ids:
            return []
        placeholders = ", ".join("?" for _ in dependency_ids)
        rows = connection.execute(
            f"SELECT id FROM tasks WHERE id IN ({placeholders})",
            dependency_ids,
        ).fetchall()
        existing = {str(row["id"]) for row in rows}
        return [task_id for task_id in dependency_ids if task_id not in existing]


class RuntimeRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def heartbeat(self, state: str, note: str | None = None, last_task_id: str | None = None) -> None:
        with closing(self.db.connect()) as connection:
            connection.execute(
                """
                UPDATE runtime_state
                SET dispatcher_state = ?, heartbeat_at = ?, note = ?, last_task_id = ?
                WHERE singleton = 1
                """,
                (state, utc_now(), note, last_task_id),
            )
            connection.commit()

    def get_status(self, task_repository: TaskRepository, project_registry: ProjectRegistry | None = None) -> RuntimeStatus:
        counts = task_repository.counts_by_status()
        ready_queued_count, blocked_queued_count = task_repository.count_queued_readiness()
        with closing(self.db.connect()) as connection:
            row = connection.execute(
                """
                SELECT dispatcher_state, heartbeat_at, last_task_id, note
                FROM runtime_state
                WHERE singleton = 1
                """
            ).fetchone()
        return RuntimeStatus(
            dispatcher_state=str(row["dispatcher_state"]),
            heartbeat_at=row["heartbeat_at"],
            last_task_id=row["last_task_id"],
            note=row["note"],
            project_count=project_registry.enabled_count() if project_registry else 0,
            queued_count=counts[TaskStatus.QUEUED.value],
            ready_queued_count=ready_queued_count,
            blocked_queued_count=blocked_queued_count,
            running_count=counts[TaskStatus.RUNNING.value],
            succeeded_count=counts[TaskStatus.SUCCEEDED.value],
            failed_count=counts[TaskStatus.FAILED.value],
            cancelled_count=counts[TaskStatus.CANCELLED.value],
            blocked_count=counts[TaskStatus.BLOCKED.value],
            needs_human_count=counts[TaskStatus.NEEDS_HUMAN.value],
        )
