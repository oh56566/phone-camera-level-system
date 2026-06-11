from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from vidtolevel.core import db
from vidtolevel.core.pipeline import ProcessOptions, process_video
from vidtolevel.core.session import SessionOptions, add_project_session
from vidtolevel.server.notify import DiscordNotifier


app = FastAPI(title="VidToLevel API", version="0.1.0")


class ProcessRequest(BaseModel):
    video_path: str = Field(..., description="Local path to the uploaded video.")
    project: str | None = None
    project_root: str | None = Field(
        None,
        description="When set, process the video as an incremental project session.",
    )
    fps: float = 2.0
    skip_mvs: bool = False
    skip_optimize: bool = False
    target_faces: int = 500_000
    discord_webhook: str | None = None


def run_job(request: ProcessRequest) -> None:
    notifier = DiscordNotifier(request.discord_webhook)
    try:
        if request.project_root:
            result = add_project_session(
                SessionOptions(
                    video_path=Path(request.video_path),
                    project_root=Path(request.project_root),
                    fps=request.fps,
                    skip_mvs=request.skip_mvs,
                    skip_optimize=request.skip_optimize,
                    target_faces=request.target_faces,
                )
            )
            job_name = result["session_id"]
        else:
            result = process_video(
                ProcessOptions(
                    video_path=Path(request.video_path),
                    project=request.project,
                    fps=request.fps,
                    skip_mvs=request.skip_mvs,
                    skip_optimize=request.skip_optimize,
                    target_faces=request.target_faces,
                )
            )
            job_name = result["job_id"]
        notifier.send(f"VidToLevel completed: {job_name}")
    except Exception as exc:
        notifier.send(f"VidToLevel failed: {exc}")
        raise


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
def create_job(request: ProcessRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(run_job, request)
    return {"status": "queued", "video_path": request.video_path}


@app.get("/jobs")
def list_jobs(
    database: str = Query("vidtolevel.sqlite3"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict[str, object]]:
    return db.list_jobs(Path(database), limit=limit)


@app.get("/jobs/{job_id}")
def get_job(job_id: str, database: str = Query("vidtolevel.sqlite3")) -> dict[str, object]:
    job = db.get_job(Path(database), job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job
