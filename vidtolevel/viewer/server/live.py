from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vidtolevel.core import db
from vidtolevel.viewer.server.colmap_parser import SparseModel


@dataclass(frozen=True)
class SparseSnapshotState:
    signature: str
    camera_ids: frozenset[int]
    point_ids: frozenset[int]

    @property
    def camera_count(self) -> int:
        return len(self.camera_ids)

    @property
    def point_count(self) -> int:
        return len(self.point_ids)


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


def sparse_snapshot_state(sparse_model: Path, model: SparseModel) -> SparseSnapshotState:
    return SparseSnapshotState(
        signature=sparse_model_signature(sparse_model),
        camera_ids=frozenset(model.images),
        point_ids=frozenset(model.points3d),
    )


def build_sparse_snapshot_payload(
    *,
    project_id: str,
    sparse_model: Path,
    model: SparseModel,
    previous_state: SparseSnapshotState | None = None,
) -> dict[str, Any]:
    current_state = sparse_snapshot_state(sparse_model, model)
    return {
        "type": "sparse_snapshot",
        "project": project_id,
        "sparseModel": str(sparse_model.resolve()),
        "signature": current_state.signature,
        "cameraCount": current_state.camera_count,
        "pointCount": current_state.point_count,
        "diff": sparse_snapshot_diff(previous_state, current_state),
    }


def sparse_snapshot_diff(
    previous: SparseSnapshotState | None,
    current: SparseSnapshotState,
    *,
    sample_limit: int = 50,
) -> dict[str, Any]:
    if previous is None:
        return {
            "initial": True,
            "cameraCountDelta": 0,
            "pointCountDelta": 0,
            "addedCameraIds": [],
            "removedCameraIds": [],
            "addedPointCount": 0,
            "removedPointCount": 0,
            "addedPointIdsSample": [],
            "removedPointIdsSample": [],
        }

    added_cameras = sorted(current.camera_ids - previous.camera_ids)
    removed_cameras = sorted(previous.camera_ids - current.camera_ids)
    added_points = sorted(current.point_ids - previous.point_ids)
    removed_points = sorted(previous.point_ids - current.point_ids)
    return {
        "initial": False,
        "cameraCountDelta": current.camera_count - previous.camera_count,
        "pointCountDelta": current.point_count - previous.point_count,
        "addedCameraIds": added_cameras,
        "removedCameraIds": removed_cameras,
        "addedPointCount": len(added_points),
        "removedPointCount": len(removed_points),
        "addedPointIdsSample": added_points[:sample_limit],
        "removedPointIdsSample": removed_points[:sample_limit],
    }
