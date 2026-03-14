from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_DATA_DIR = Path(".agent-hub")


@dataclass(slots=True)
class Settings:
    data_dir: Path
    db_path: Path
    projects_file: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": str(self.data_dir),
            "db_path": str(self.db_path),
            "projects_file": str(self.projects_file),
        }


def resolve_settings(*, data_dir: str | Path | None = None, projects_file: str | Path | None = None) -> Settings:
    resolved_data_dir = Path(data_dir or os.environ.get("AGENT_HUB_DATA_DIR") or DEFAULT_DATA_DIR).expanduser()
    resolved_projects_file = Path(
        projects_file or os.environ.get("AGENT_HUB_PROJECTS_FILE") or (resolved_data_dir / "projects.json")
    ).expanduser()
    return Settings(
        data_dir=resolved_data_dir,
        db_path=resolved_data_dir / "agent_hub.db",
        projects_file=resolved_projects_file,
    )


__all__ = ["DEFAULT_DATA_DIR", "Settings", "resolve_settings"]
