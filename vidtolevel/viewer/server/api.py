from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from vidtolevel.viewer.server.colmap_parser import SparseModel, model_bounds, read_sparse_model
from vidtolevel.viewer.server.converter import (
    POINT_BINARY_MIME,
    POINT_BINARY_STRIDE,
    POINT_COLOR_MODES,
    find_first_sparse_model,
    find_images_dir,
    pack_points_binary,
)
from vidtolevel.viewer.server.coverage import compute_topdown_coverage
from vidtolevel.viewer.server.diagnostics import annotate_camera_path, summarize_camera_path
from vidtolevel.viewer.server.live import (
    build_jobs_payload,
    build_sparse_snapshot_payload,
    sparse_snapshot_state,
    sparse_model_signature,
)
from vidtolevel.viewer.server.thumbnails import build_cached_thumbnail


@dataclass(frozen=True)
class ViewerProject:
    id: str
    name: str
    root: Path
    sparse_model: Path
    images_dir: Path | None


def create_viewer_app(paths: list[Path] | None = None) -> FastAPI:
    projects = discover_projects(paths or [Path("runs")])
    app = FastAPI(title="VidToLevel Viewer", version="0.1.0")
    app.state.viewer_projects = projects

    web_root = Path(__file__).resolve().parents[1] / "web"
    app.mount("/assets", StaticFiles(directory=web_root), name="viewer-assets")

    @app.get("/", response_class=HTMLResponse)
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, str]]:
        return [
            {
                "id": project.id,
                "name": project.name,
                "root": str(project.root),
                "sparseModel": str(project.sparse_model),
                "imagesDir": str(project.images_dir) if project.images_dir else "",
            }
            for project in projects.values()
        ]

    @app.get("/api/{project_id}/status")
    def status(project_id: str) -> dict[str, object]:
        project = _project_or_404(projects, project_id)
        model = _load_project_model(project)
        camera_payload = annotate_camera_path(_camera_payload(project, model))
        checkpoint = project.root / "checkpoint.json"
        summary = project.root / "output" / "summary.json"
        return {
            "project": project.id,
            "modelSignature": sparse_model_signature(project.sparse_model),
            "cameraCount": len(model.images),
            "pointCount": len(model.points3d),
            "bounds": model_bounds(model.points3d, model.images),
            "diagnostics": summarize_camera_path(camera_payload),
            "checkpoint": str(checkpoint) if checkpoint.exists() else "",
            "summary": str(summary) if summary.exists() else "",
        }

    @app.get("/api/{project_id}/cameras")
    def cameras(project_id: str) -> dict[str, object]:
        project = _project_or_404(projects, project_id)
        model = _load_project_model(project)
        payload = _camera_payload(project, model)
        return {"project": project.id, "cameras": annotate_camera_path(payload)}

    @app.get("/api/{project_id}/points")
    def points(
        project_id: str,
        limit: Annotated[int | None, Query(ge=1, le=5_000_000)] = None,
        color_mode: Annotated[str, Query(pattern="^(rgb|error|track|session)$")] = "rgb",
    ) -> Response:
        project = _project_or_404(projects, project_id)
        model = _load_project_model(project)
        if color_mode not in POINT_COLOR_MODES:
            raise HTTPException(status_code=400, detail=f"Unsupported color mode: {color_mode}")
        data, count = pack_points_binary(
            model.points3d.values(),
            limit=limit,
            color_mode=color_mode,
            images=model.images,
        )
        return Response(
            content=data,
            media_type=POINT_BINARY_MIME,
            headers={
                "X-VidToLevel-Point-Count": str(count),
                "X-VidToLevel-Point-Stride": str(POINT_BINARY_STRIDE),
                "X-VidToLevel-Color-Mode": color_mode,
            },
        )

    @app.get("/api/{project_id}/coverage")
    def coverage(
        project_id: str,
        cell_size: Annotated[float, Query(gt=0.01, le=10.0)] = 0.5,
    ) -> dict[str, object]:
        project = _project_or_404(projects, project_id)
        model = _load_project_model(project)
        return compute_topdown_coverage(list(model.points3d.values()), cell_size=cell_size)

    @app.get("/api/{project_id}/thumb/{image_name:path}")
    def thumbnail(project_id: str, image_name: str) -> FileResponse:
        project = _project_or_404(projects, project_id)
        if project.images_dir is None:
            raise HTTPException(status_code=404, detail="Image directory not found.")
        image_path = (project.images_dir / image_name).resolve()
        if project.images_dir.resolve() not in image_path.parents:
            raise HTTPException(status_code=400, detail="Invalid image path.")
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found.")
        try:
            thumbnail_path = build_cached_thumbnail(
                project_root=project.root,
                source_path=image_path,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FileResponse(thumbnail_path, media_type="image/jpeg")

    @app.websocket("/ws/jobs")
    async def jobs_socket(
        websocket: WebSocket,
        database: str = "vidtolevel.sqlite3",
        limit: int = 20,
        event_limit: int = 50,
        interval: float = 2.0,
    ) -> None:
        await websocket.accept()
        last_payload = ""
        poll_interval = max(0.5, min(interval, 10.0))
        try:
            while True:
                payload = build_jobs_payload(
                    Path(database),
                    limit=max(1, min(limit, 200)),
                    event_limit=max(1, min(event_limit, 500)),
                )
                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if serialized != last_payload:
                    await websocket.send_text(serialized)
                    last_payload = serialized
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=poll_interval)
                except TimeoutError:
                    continue
        except (WebSocketDisconnect, asyncio.CancelledError):
            return

    @app.websocket("/ws/{project_id}")
    async def project_socket(
        websocket: WebSocket,
        project_id: str,
        interval: float = 2.0,
    ) -> None:
        project = _project_or_404(projects, project_id)
        await websocket.accept()
        last_payload = ""
        previous_state = None
        poll_interval = max(0.5, min(interval, 10.0))
        try:
            while True:
                try:
                    model = _load_project_model(project)
                    current_state = sparse_snapshot_state(project.sparse_model, model)
                    if previous_state is None or current_state.signature != previous_state.signature:
                        payload = build_sparse_snapshot_payload(
                            project_id=project.id,
                            sparse_model=project.sparse_model,
                            model=model,
                            previous_state=previous_state,
                        )
                        previous_state = current_state
                    else:
                        payload = None
                except Exception as exc:
                    payload = {
                        "type": "sparse_snapshot_error",
                        "project": project.id,
                        "message": str(exc),
                    }
                if payload is not None:
                    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    if serialized != last_payload:
                        await websocket.send_text(serialized)
                        last_payload = serialized
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=poll_interval)
                except TimeoutError:
                    continue
        except (WebSocketDisconnect, asyncio.CancelledError):
            return

    return app


def discover_projects(paths: list[Path]) -> dict[str, ViewerProject]:
    projects: dict[str, ViewerProject] = {}
    for raw_path in paths:
        root = raw_path.resolve()
        candidates = [root]
        if root.exists() and root.is_dir() and not find_first_sparse_model(root):
            candidates.extend(sorted(path for path in root.iterdir() if path.is_dir()))

        for candidate in candidates:
            sparse_model = find_first_sparse_model(candidate)
            if sparse_model is None:
                continue
            project_id = _unique_id(_slug(candidate.name or sparse_model.name), projects)
            projects[project_id] = ViewerProject(
                id=project_id,
                name=candidate.name or sparse_model.name,
                root=candidate,
                sparse_model=sparse_model,
                images_dir=find_images_dir(candidate, sparse_model),
            )
    return projects


def _project_or_404(projects: dict[str, ViewerProject], project_id: str) -> ViewerProject:
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown viewer project: {project_id}")
    return project


def _camera_payload(project: ViewerProject, model: SparseModel) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for image in sorted(model.images.values(), key=lambda item: item.name):
        camera = model.cameras.get(image.camera_id)
        if camera is None:
            continue
        image_path = project.images_dir / image.name if project.images_dir else None
        thumbnail_url = (
            f"/api/{project.id}/thumb/{quote(image.name)}"
            if image_path is not None and image_path.exists()
            else ""
        )
        fov_x, fov_y = camera.fov
        payload.append(
            {
                "id": image.image_id,
                "name": image.name,
                "cameraId": image.camera_id,
                "model": camera.model_name,
                "width": camera.width,
                "height": camera.height,
                "fovX": fov_x,
                "fovY": fov_y,
                "position": [float(value) for value in image.center],
                "rotationCameraToWorld": [
                    float(value) for value in image.rotation_camera_to_world.reshape(-1)
                ],
                "registeredPointCount": image.registered_point_count,
                "thumbnailUrl": thumbnail_url,
            }
        )
    return payload


def _load_project_model(project: ViewerProject) -> SparseModel:
    return _load_model(str(project.sparse_model), sparse_model_signature(project.sparse_model))


@lru_cache(maxsize=16)
def _load_model(sparse_model: str, signature: str) -> SparseModel:
    return read_sparse_model(Path(sparse_model))


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return slug or "project"


def _unique_id(base: str, projects: dict[str, ViewerProject]) -> str:
    if base not in projects:
        return base
    index = 2
    while f"{base}-{index}" in projects:
        index += 1
    return f"{base}-{index}"
