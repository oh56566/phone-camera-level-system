from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    database: Path
    images: Path
    sparse: Path
    sparse_versions: Path
    sessions: Path
    meshes: Path
    coverage: Path
    reports: Path
    metadata: Path


def project_paths(root: Path) -> ProjectPaths:
    return ProjectPaths(
        root=root,
        database=root / "database.db",
        images=root / "images",
        sparse=root / "sparse",
        sparse_versions=root / "sparse_versions",
        sessions=root / "sessions",
        meshes=root / "meshes",
        coverage=root / "coverage",
        reports=root / "reports",
        metadata=root / "project.json",
    )


def init_project(root: Path, *, name: str | None = None) -> ProjectPaths:
    paths = project_paths(root)
    for directory in [
        paths.root,
        paths.images,
        paths.sparse,
        paths.sparse_versions,
        paths.sessions,
        paths.meshes,
        paths.coverage,
        paths.reports,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    if not paths.metadata.exists():
        payload: dict[str, Any] = {
            "name": name or root.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "scale_factor": None,
            "sessions": [],
        }
        paths.metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return paths


def load_metadata(root: Path) -> dict[str, Any]:
    paths = init_project(root)
    return json.loads(paths.metadata.read_text(encoding="utf-8"))


def save_metadata(root: Path, metadata: dict[str, Any]) -> None:
    paths = init_project(root)
    paths.metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def active_sparse_model(root: Path) -> Path | None:
    paths = init_project(root)
    model = paths.sparse / "0"
    return model if model.exists() else None


def append_session(
    root: Path,
    session_id: str,
    video_path: Path,
    stats: dict[str, Any],
    *,
    status: str = "done",
) -> None:
    metadata = load_metadata(root)
    sessions = metadata.setdefault("sessions", [])
    sessions[:] = [session for session in sessions if session.get("id") != session_id]
    metadata.setdefault("sessions", []).append(
        {
            "id": session_id,
            "video_path": str(video_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "stats": stats,
        }
    )
    save_metadata(root, metadata)
