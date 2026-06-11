from __future__ import annotations

from pathlib import Path
from typing import Any

from vidtolevel.core import db


def build_jobs_payload(database_path: Path, *, limit: int = 20) -> dict[str, Any]:
    resolved = database_path.resolve()
    jobs = db.list_jobs(resolved, limit=limit) if resolved.exists() else []
    return {
        "type": "jobs",
        "database": str(resolved),
        "jobs": jobs,
    }
