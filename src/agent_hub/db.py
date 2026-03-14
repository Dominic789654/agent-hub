from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class Database:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "agent_hub.db"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def bootstrap(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    project_id TEXT,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
                ON tasks(status, created_at);

                CREATE TABLE IF NOT EXISTS runtime_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    dispatcher_state TEXT NOT NULL,
                    heartbeat_at TEXT,
                    last_task_id TEXT,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    log TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_runs_task_created_at
                ON runs(task_id, created_at);

                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL,
                    depends_on_task_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, depends_on_task_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    CHECK(task_id <> depends_on_task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_task_dependencies_lookup
                ON task_dependencies(task_id, depends_on_task_id);

                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    pipeline_id TEXT NOT NULL,
                    input_value TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at
                ON pipeline_runs(created_at);

                CREATE TABLE IF NOT EXISTS task_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_task_notes_task_created_at
                ON task_notes(task_id, created_at);

                CREATE TABLE IF NOT EXISTS task_labels (
                    task_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, label),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_task_labels_task
                ON task_labels(task_id, created_at);

                CREATE TABLE IF NOT EXISTS pipeline_run_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_run_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pipeline_run_notes_created_at
                ON pipeline_run_notes(pipeline_run_id, created_at);

                CREATE TABLE IF NOT EXISTS pipeline_run_labels (
                    pipeline_run_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(pipeline_run_id, label)
                );

                CREATE INDEX IF NOT EXISTS idx_pipeline_run_labels_created_at
                ON pipeline_run_labels(pipeline_run_id, created_at);

                CREATE TABLE IF NOT EXISTS saved_queries (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    filters_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_saved_queries_scope_created_at
                ON saved_queries(scope, created_at);
                """
            )
            connection.execute(
                """
                INSERT INTO runtime_state(singleton, dispatcher_state, heartbeat_at, last_task_id, note)
                VALUES (1, 'stopped', NULL, NULL, 'dispatcher has not started')
                ON CONFLICT(singleton) DO NOTHING
                """
            )
            self._ensure_column(connection, "tasks", "project_id", "TEXT")
            self._ensure_column(connection, "tasks", "pipeline_run_id", "TEXT")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_pipeline_run_id
                ON tasks(pipeline_run_id, created_at)
                """
            )
            connection.commit()

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column in columns:
            return
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
