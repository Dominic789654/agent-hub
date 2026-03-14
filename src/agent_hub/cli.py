from __future__ import annotations

import argparse
import json

from agent_hub import __version__
from agent_hub.config import resolve_settings
from agent_hub.db import Database
from agent_hub.dispatcher import Dispatcher
from agent_hub.models import SUPPORTED_TASK_KINDS
from agent_hub.projects import ProjectRegistry
from agent_hub.repository import RuntimeRepository, TaskRepository
from agent_hub.services.pipelines import PipelineService
from agent_hub.services.task_templates import TaskTemplateService
from agent_hub.web import make_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-hub", description="Local-first agent hub MVP")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="directory used for the local SQLite database",
    )
    parser.add_argument(
        "--projects-file",
        default=None,
        help="path to the JSON project registry (defaults to <data-dir>/projects.json or AGENT_HUB_PROJECTS_FILE)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="run the minimal web surface")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)

    dispatch_parser = subparsers.add_parser("dispatch", help="run the standalone dispatcher")
    dispatch_parser.add_argument("--poll-interval", type=float, default=1.0)

    create_parser = subparsers.add_parser("create-task", help="enqueue a public-safe demo task")
    create_parser.add_argument("title")
    create_parser.add_argument("--kind", default="noop", choices=sorted(SUPPORTED_TASK_KINDS))
    create_parser.add_argument("--payload", default="")
    create_parser.add_argument("--project-id", default=None)
    create_parser.add_argument(
        "--depends-on",
        action="append",
        default=[],
        help="task id dependency; repeat to require multiple predecessor tasks",
    )

    list_parser = subparsers.add_parser("list-tasks", help="list tasks as JSON")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--project-id", default=None)
    list_parser.add_argument("--status", default=None)
    list_parser.add_argument("--kind", default=None)
    list_parser.add_argument("--pipeline-run-id", default=None)

    dashboard_parser = subparsers.add_parser("dashboard", help="print a dashboard snapshot as JSON")
    dashboard_parser.add_argument("--limit", type=int, default=20, help="limit for recent task-like sections")

    list_runs_parser = subparsers.add_parser("list-runs", help="list recent runs as JSON")
    list_runs_parser.add_argument("--limit", type=int, default=20)

    list_human_inbox_parser = subparsers.add_parser("list-human-inbox", help="list tasks needing human attention")
    list_human_inbox_parser.add_argument("--project-id", default=None)
    list_human_inbox_parser.add_argument("--limit", type=int, default=20)

    list_saved_queries_parser = subparsers.add_parser("list-saved-queries", help="list saved filter queries as JSON")
    list_saved_queries_parser.add_argument("--scope", default=None)
    list_saved_queries_parser.add_argument("--limit", type=int, default=20)

    create_saved_query_parser = subparsers.add_parser("create-saved-query", help="create a saved filter query")
    create_saved_query_parser.add_argument("scope", choices=["tasks", "pipeline_runs"])
    create_saved_query_parser.add_argument("name")
    create_saved_query_parser.add_argument("--description", default="")
    create_saved_query_parser.add_argument("--filter", action="append", default=[], help="key=value filter; repeatable")

    apply_saved_query_parser = subparsers.add_parser("apply-saved-query", help="execute a saved query and return matching items")
    apply_saved_query_parser.add_argument("query_id")
    apply_saved_query_parser.add_argument("--limit", type=int, default=20)

    delete_saved_query_parser = subparsers.add_parser("delete-saved-query", help="delete a saved query")
    delete_saved_query_parser.add_argument("query_id")

    cancel_parser = subparsers.add_parser("cancel-task", help="cancel a queued task")
    cancel_parser.add_argument("task_id")

    retry_parser = subparsers.add_parser("retry-task", help="requeue a finished task")
    retry_parser.add_argument("task_id")

    needs_human_parser = subparsers.add_parser("mark-needs-human", help="mark a task for human intervention")
    needs_human_parser.add_argument("task_id")
    needs_human_parser.add_argument("--note", default="")

    add_task_note_parser = subparsers.add_parser("add-task-note", help="attach a note to a task")
    add_task_note_parser.add_argument("task_id")
    add_task_note_parser.add_argument("body")

    add_task_label_parser = subparsers.add_parser("add-task-label", help="attach a label to a task")
    add_task_label_parser.add_argument("task_id")
    add_task_label_parser.add_argument("label")

    remove_task_label_parser = subparsers.add_parser("remove-task-label", help="remove a label from a task")
    remove_task_label_parser.add_argument("task_id")
    remove_task_label_parser.add_argument("label")

    list_projects_parser = subparsers.add_parser("list-projects", help="list registered projects as JSON")
    list_projects_parser.add_argument("--all", action="store_true", help="include disabled projects")

    list_project_actions_parser = subparsers.add_parser(
        "list-project-actions",
        help="list action templates for a registered project as JSON",
    )
    list_project_actions_parser.add_argument("project_id")

    list_project_pipelines_parser = subparsers.add_parser(
        "list-project-pipelines",
        help="list pipeline templates for a registered project as JSON",
    )
    list_project_pipelines_parser.add_argument("project_id")

    list_project_task_templates_parser = subparsers.add_parser(
        "list-project-task-templates",
        help="list task templates for a registered project as JSON",
    )
    list_project_task_templates_parser.add_argument("project_id")

    list_pipeline_runs_parser = subparsers.add_parser(
        "list-pipeline-runs",
        help="list recent instantiated pipeline runs as JSON",
    )
    list_pipeline_runs_parser.add_argument("--limit", type=int, default=20)
    list_pipeline_runs_parser.add_argument("--project-id", default=None)
    list_pipeline_runs_parser.add_argument("--pipeline-id", default=None)

    show_pipeline_run_parser = subparsers.add_parser(
        "show-pipeline-run",
        help="show a pipeline run and its linked tasks as JSON",
    )
    show_pipeline_run_parser.add_argument("pipeline_run_id")

    add_pipeline_run_note_parser = subparsers.add_parser("add-pipeline-run-note", help="attach a note to a pipeline run")
    add_pipeline_run_note_parser.add_argument("pipeline_run_id")
    add_pipeline_run_note_parser.add_argument("body")

    add_pipeline_run_label_parser = subparsers.add_parser("add-pipeline-run-label", help="attach a label to a pipeline run")
    add_pipeline_run_label_parser.add_argument("pipeline_run_id")
    add_pipeline_run_label_parser.add_argument("label")

    remove_pipeline_run_label_parser = subparsers.add_parser("remove-pipeline-run-label", help="remove a label from a pipeline run")
    remove_pipeline_run_label_parser.add_argument("pipeline_run_id")
    remove_pipeline_run_label_parser.add_argument("label")

    cancel_pipeline_run_parser = subparsers.add_parser(
        "cancel-pipeline-run",
        help="cancel queued or blocked tasks inside a pipeline run",
    )
    cancel_pipeline_run_parser.add_argument("pipeline_run_id")

    retry_pipeline_run_parser = subparsers.add_parser(
        "retry-pipeline-run",
        help="requeue non-success terminal tasks inside a pipeline run",
    )
    retry_pipeline_run_parser.add_argument("pipeline_run_id")

    run_pipeline_parser = subparsers.add_parser(
        "run-pipeline",
        help="instantiate a registered project pipeline into queued tasks",
    )
    run_pipeline_parser.add_argument("project_id")
    run_pipeline_parser.add_argument("pipeline_id")
    run_pipeline_parser.add_argument("--input", default="")

    run_task_template_parser = subparsers.add_parser(
        "run-task-template",
        help="instantiate a registered project task template into a queued task",
    )
    run_task_template_parser.add_argument("project_id")
    run_task_template_parser.add_argument("template_id")
    run_task_template_parser.add_argument("--input", default="")
    run_task_template_parser.add_argument("--depends-on", action="append", default=[])

    subparsers.add_parser("status", help="print runtime status as JSON")
    subparsers.add_parser("config", help="print resolved configuration as JSON")
    subparsers.add_parser("version", help="print version")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "version":
        print(__version__)
        return 0

    settings = resolve_settings(data_dir=args.data_dir, projects_file=args.projects_file)
    db = Database(settings.data_dir)
    db.bootstrap()
    task_repository = TaskRepository(db)
    runtime_repository = RuntimeRepository(db)
    project_registry = ProjectRegistry(settings.projects_file)
    project_registry.bootstrap()
    pipeline_service = PipelineService(task_repository=task_repository, project_registry=project_registry)
    task_template_service = TaskTemplateService(task_repository=task_repository, project_registry=project_registry)

    if args.command == "serve":
        server = make_server(args.host, args.port, task_repository, runtime_repository, project_registry, settings)
        print(f"serving agent-hub on http://{args.host}:{args.port} using {db.path}")
        server.serve_forever()
        return 0

    if args.command == "dispatch":
        dispatcher = Dispatcher(
            task_repository=task_repository,
            runtime_repository=runtime_repository,
            project_registry=project_registry,
            poll_interval=args.poll_interval,
        )
        dispatcher.run_forever()
        return 0

    if args.command == "create-task":
        project_id = args.project_id
        if project_id and project_registry.get_project(project_id) is None:
            parser.error(f"unknown project_id: {project_id}")
        if args.kind == "project_command" and not project_id:
            parser.error("project_command tasks require --project-id")
        if args.kind == "project_action":
            if not project_id:
                parser.error("project_action tasks require --project-id")
            if not args.payload:
                parser.error("project_action tasks require --payload with the action id")
            if project_registry.get_project_action(project_id, args.payload) is None:
                parser.error(f"unknown project action: {args.payload}")
        task = task_repository.create_task(
            args.title,
            kind=args.kind,
            payload=args.payload,
            project_id=project_id,
            depends_on=args.depends_on,
        )
        print(json.dumps(task.to_dict(), indent=2))
        return 0

    if args.command == "list-tasks":
        tasks = [
            task.to_dict()
            for task in task_repository.list_tasks(
                limit=args.limit,
                project_id=args.project_id,
                status=args.status,
                kind=args.kind,
                pipeline_run_id=args.pipeline_run_id,
            )
        ]
        print(json.dumps({"tasks": tasks}, indent=2))
        return 0

    if args.command == "dashboard":
        payload = {
            "status": runtime_repository.get_status(task_repository, project_registry).to_dict(),
            "config": settings.to_dict(),
            "recent_tasks": [task.to_dict() for task in task_repository.list_tasks(limit=args.limit)],
            "human_inbox": [item.to_dict() for item in task_repository.list_human_inbox(limit=min(args.limit, 20))],
            "recent_pipeline_runs": [item.to_dict() for item in task_repository.list_pipeline_runs(limit=min(args.limit, 20))],
            "recent_runs": [item.to_dict() for item in task_repository.list_recent_runs(limit=min(args.limit, 20))],
            "saved_queries": [item.to_dict() for item in task_repository.list_saved_queries(limit=min(args.limit, 20))],
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "list-runs":
        runs = [item.to_dict() for item in task_repository.list_recent_runs(limit=args.limit)]
        print(json.dumps({"runs": runs}, indent=2))
        return 0

    if args.command == "list-human-inbox":
        items = [item.to_dict() for item in task_repository.list_human_inbox(limit=args.limit, project_id=args.project_id)]
        print(json.dumps({"items": items}, indent=2))
        return 0

    if args.command == "list-saved-queries":
        queries = [item.to_dict() for item in task_repository.list_saved_queries(scope=args.scope, limit=args.limit)]
        print(json.dumps({"saved_queries": queries}, indent=2))
        return 0

    if args.command == "create-saved-query":
        try:
            query = task_repository.create_saved_query(
                args.scope,
                args.name,
                description=args.description,
                filters=_parse_filter_args(args.filter),
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(query.to_dict(), indent=2))
        return 0

    if args.command == "apply-saved-query":
        try:
            result = task_repository.apply_saved_query(args.query_id, limit=args.limit)
        except KeyError:
            parser.error(f"saved query not found: {args.query_id}")
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "delete-saved-query":
        try:
            task_repository.delete_saved_query(args.query_id)
        except KeyError:
            parser.error(f"saved query not found: {args.query_id}")
        print(json.dumps({"deleted": True, "id": args.query_id}, indent=2))
        return 0

    if args.command == "cancel-task":
        try:
            task = task_repository.cancel_task(args.task_id)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(task.to_dict(), indent=2))
        return 0

    if args.command == "retry-task":
        try:
            task = task_repository.retry_task(args.task_id)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(task.to_dict(), indent=2))
        return 0

    if args.command == "mark-needs-human":
        try:
            task = task_repository.mark_needs_human(args.task_id, note=args.note)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(task.to_dict(), indent=2))
        return 0

    if args.command == "add-task-note":
        try:
            note = task_repository.add_task_note(args.task_id, args.body)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(note.to_dict(), indent=2))
        return 0

    if args.command == "add-task-label":
        try:
            labels = task_repository.add_task_label(args.task_id, args.label)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"task_id": args.task_id, "labels": labels}, indent=2))
        return 0

    if args.command == "remove-task-label":
        try:
            labels = task_repository.remove_task_label(args.task_id, args.label)
        except KeyError:
            parser.error(f"task not found: {args.task_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"task_id": args.task_id, "labels": labels}, indent=2))
        return 0

    if args.command == "status":
        print(json.dumps(runtime_repository.get_status(task_repository, project_registry).to_dict(), indent=2))
        return 0

    if args.command == "list-projects":
        projects = [project.to_dict() for project in project_registry.list_projects(include_disabled=args.all)]
        print(json.dumps({"projects": projects}, indent=2))
        return 0

    if args.command == "list-project-actions":
        if project_registry.get_project(args.project_id) is None:
            parser.error(f"unknown project_id: {args.project_id}")
        actions = [action.to_dict() for action in project_registry.list_project_actions(args.project_id)]
        print(json.dumps({"project_id": args.project_id, "actions": actions}, indent=2))
        return 0

    if args.command == "list-project-pipelines":
        if project_registry.get_project(args.project_id) is None:
            parser.error(f"unknown project_id: {args.project_id}")
        pipelines = [pipeline.to_dict() for pipeline in project_registry.list_project_pipelines(args.project_id)]
        print(json.dumps({"project_id": args.project_id, "pipelines": pipelines}, indent=2))
        return 0

    if args.command == "list-project-task-templates":
        if project_registry.get_project(args.project_id) is None:
            parser.error(f"unknown project_id: {args.project_id}")
        templates = [template.to_dict() for template in project_registry.list_project_task_templates(args.project_id)]
        print(json.dumps({"project_id": args.project_id, "task_templates": templates}, indent=2))
        return 0

    if args.command == "run-pipeline":
        try:
            result = pipeline_service.instantiate(args.project_id, args.pipeline_id, input_value=args.input)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "run-task-template":
        try:
            result = task_template_service.instantiate(
                args.project_id,
                args.template_id,
                input_value=args.input,
                depends_on=args.depends_on,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "list-pipeline-runs":
        runs = [
            item.to_dict()
            for item in task_repository.list_pipeline_runs(
                limit=args.limit,
                project_id=args.project_id,
                pipeline_id=args.pipeline_id,
            )
        ]
        print(json.dumps({"pipeline_runs": runs}, indent=2))
        return 0

    if args.command == "show-pipeline-run":
        detail = task_repository.get_pipeline_run_detail(args.pipeline_run_id)
        if detail is None:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        print(json.dumps(detail.to_dict(), indent=2))
        return 0

    if args.command == "add-pipeline-run-note":
        try:
            note = task_repository.add_pipeline_run_note(args.pipeline_run_id, args.body)
        except KeyError:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(note.to_dict(), indent=2))
        return 0

    if args.command == "add-pipeline-run-label":
        try:
            labels = task_repository.add_pipeline_run_label(args.pipeline_run_id, args.label)
        except KeyError:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"pipeline_run_id": args.pipeline_run_id, "labels": labels}, indent=2))
        return 0

    if args.command == "remove-pipeline-run-label":
        try:
            labels = task_repository.remove_pipeline_run_label(args.pipeline_run_id, args.label)
        except KeyError:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps({"pipeline_run_id": args.pipeline_run_id, "labels": labels}, indent=2))
        return 0

    if args.command == "cancel-pipeline-run":
        try:
            detail = task_repository.cancel_pipeline_run(args.pipeline_run_id)
        except KeyError:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        print(json.dumps(detail.to_dict(), indent=2))
        return 0

    if args.command == "retry-pipeline-run":
        try:
            detail = task_repository.retry_pipeline_run(args.pipeline_run_id)
        except KeyError:
            parser.error(f"pipeline run not found: {args.pipeline_run_id}")
        print(json.dumps(detail.to_dict(), indent=2))
        return 0

    if args.command == "config":
        print(json.dumps(settings.to_dict(), indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _parse_filter_args(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for raw in values:
        item = str(raw).strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"invalid filter expression: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"invalid filter expression: {item}")
        filters[key] = value
    return filters
