from __future__ import annotations

from pathlib import Path
from typing import Any

from vidtolevel.core import db
from vidtolevel.viewer.server.colmap_parser import SparseModel


def build_jobs_payload(
    database_path: Path,
    *,
    limit: int = 20,
    event_limit: int = 50,
) -> dict[str, Any]:
    resolved = database_path.resolve()
    jobs = db.list_jobs(resolved, limit=limit) if resolved.exists() else []
    events = db.list_job_events(resolved, limit=event_limit) if resolved.exists() else []
    return {
        "type": "jobs",
        "database": str(resolved),
        "jobs": jobs,
        "events": events,
    }


def sparse_model_signature(sparse_model: Path) -> str:
    parts: list[str] = []
    for name in ("cameras.bin", "images.bin", "points3D.bin", "cameras.txt", "images.txt", "points3D.txt"):
        path = sparse_model / name
        if not path.exists():
            continue
        stat = path.stat()
        parts.append(f"{name}:{stat.st_size}:{stat.st_mtime_ns}")
    return "|".join(parts)


def build_sparse_snapshot_payload(
    *,
    project_id: str,
    sparse_model: Path,
    model: SparseModel,
) -> dict[str, Any]:
    return {
        "type": "sparse_snapshot",
        "project": project_id,
        "sparseModel": str(sparse_model.resolve()),
        "signature": sparse_model_signature(sparse_model),
        "cameraCount": len(model.images),
        "pointCount": len(model.points3d),
    }
