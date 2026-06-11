from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vidtolevel.core import db
from vidtolevel.core.checkpoint import Checkpoint
from vidtolevel.core.frames import extract_frames, filter_frames
from vidtolevel.core.mvs import run_openmvs
from vidtolevel.core.optimizer import run_blender_optimize
from vidtolevel.core.pipeline import make_job_id
from vidtolevel.core.project import active_sparse_model, append_session, init_project
from vidtolevel.core.report import write_quality_report
from vidtolevel.core.sfm import register_incremental_session, run_new_reconstruction
from vidtolevel.core.tools import require_tool


@dataclass(frozen=True)
class SessionOptions:
    video_path: Path
    project_root: Path
    fps: float = 2.0
    blur_percentile: float = 15.0
    duplicate_threshold: float = 0.985
    session_id: str | None = None
    use_gpu: bool = True
    skip_mvs: bool = False
    skip_optimize: bool = False
    target_faces: int = 500_000
    collision_mode: str = "ground-slab"
    vocab_tree_path: Path | None = None
    mapper_snapshot_frames_freq: int = 25


@dataclass(frozen=True)
class SessionLayout:
    root: Path
    input_video: Path
    logs: Path
    extracted_frames: Path
    accepted_frames: Path
    rejected_frames: Path
    image_list: Path
    mvs_output: Path
    output: Path
    snapshots: Path
    checkpoint: Path
    report: Path


def make_session_layout(project_root: Path, session_id: str) -> SessionLayout:
    root = project_root / "sessions" / session_id
    return SessionLayout(
        root=root,
        input_video=root / "input" / "source.mp4",
        logs=root / "logs",
        extracted_frames=root / "frames" / "extracted",
        accepted_frames=root / "frames" / "accepted",
        rejected_frames=root / "frames" / "rejected",
        image_list=root / "image_list.txt",
        mvs_output=project_root / "meshes" / session_id / "openmvs",
        output=project_root / "meshes" / session_id / "output",
        snapshots=root / "snapshots",
        checkpoint=root / "checkpoint.json",
        report=project_root / "reports" / f"{session_id}_quality.md",
    )


def _stage_project_images(
    accepted_frames: Path,
    project_images: Path,
    session_id: str,
    image_list: Path,
) -> list[str]:
    session_images = project_images / session_id
    session_images.mkdir(parents=True, exist_ok=True)
    relative_names: list[str] = []
    for index, frame in enumerate(sorted(accepted_frames.glob("*.jpg")), start=1):
        relative_name = f"{session_id}/{index:06d}.jpg"
        shutil.copy2(frame, project_images / relative_name)
        relative_names.append(relative_name)
    image_list.write_text("\n".join(relative_names) + "\n", encoding="utf-8")
    return relative_names


def _replace_active_sparse(project_root: Path, new_model: Path, version_dir: Path) -> None:
    paths = init_project(project_root)
    if version_dir.exists():
        shutil.rmtree(version_dir)
    shutil.copytree(new_model, version_dir)

    active = paths.sparse / "0"
    if new_model.resolve() == active.resolve():
        return
    if active.exists():
        shutil.rmtree(active)
    shutil.copytree(new_model, active)


def _stage_stats(checkpoint: Checkpoint) -> dict[str, Any]:
    return {
        stage: {key: value for key, value in payload.items() if key != "status"}
        for stage, payload in checkpoint.stages.items()
    }


def _emit_event(
    database_path: Path,
    job_id: str,
    stage: str,
    event: str,
    message: str | None = None,
    **payload: Any,
) -> None:
    db.add_job_event(
        database_path,
        job_id=job_id,
        stage=stage,
        event=event,
        message=message,
        payload=payload,
    )


def add_project_session(options: SessionOptions) -> dict[str, Any]:
    video_path = options.video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    paths = init_project(options.project_root.resolve())
    session_id = options.session_id or make_job_id(video_path)
    layout = make_session_layout(paths.root, session_id)
    for directory in [layout.root, layout.logs, layout.output]:
        directory.mkdir(parents=True, exist_ok=True)

    jobs_db = paths.root / "jobs.sqlite3"
    db.create_job(
        jobs_db,
        job_id=session_id,
        project=paths.root.name,
        video_path=video_path,
        work_dir=layout.root,
    )
    _emit_event(
        jobs_db,
        session_id,
        "job",
        "queued",
        "session queued",
        video_path=str(video_path),
        work_dir=str(layout.root),
    )
    checkpoint = Checkpoint.load(layout.checkpoint)

    try:
        db.update_job(jobs_db, job_id=session_id, status="running", message="copy input")
        if not checkpoint.done("input"):
            _emit_event(jobs_db, session_id, "input", "started", "copy input")
            checkpoint.start("input", source=str(video_path))
            layout.input_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video_path, layout.input_video)
            checkpoint.finish("input", copied_to=str(layout.input_video))
            _emit_event(
                jobs_db,
                session_id,
                "input",
                "done",
                "input copied",
                copied_to=str(layout.input_video),
            )

        if not checkpoint.done("frames"):
            db.update_job(jobs_db, job_id=session_id, status="running", message="extract frames")
            _emit_event(
                jobs_db,
                session_id,
                "frames",
                "started",
                "extract frames",
                fps=options.fps,
            )
            checkpoint.start("frames", fps=options.fps)
            extracted_count = extract_frames(
                layout.input_video,
                layout.extracted_frames,
                fps=options.fps,
                ffmpeg=require_tool("ffmpeg"),
                log_path=layout.logs / "ffmpeg_extract_frames.log",
            )
            frame_stats = filter_frames(
                layout.extracted_frames,
                layout.accepted_frames,
                layout.rejected_frames,
                blur_percentile=options.blur_percentile,
                duplicate_threshold=options.duplicate_threshold,
            )
            relative_images = _stage_project_images(
                layout.accepted_frames,
                paths.images,
                session_id,
                layout.image_list,
            )
            frame_payload = frame_stats.to_dict()
            checkpoint.finish(
                "frames",
                staged_project_images=len(relative_images),
                image_list=str(layout.image_list),
                **frame_payload,
            )
            _emit_event(
                jobs_db,
                session_id,
                "frames",
                "done",
                "frames staged",
                staged_project_images=len(relative_images),
                image_list=str(layout.image_list),
                **frame_payload,
            )

        if not checkpoint.done("sfm"):
            db.update_job(jobs_db, job_id=session_id, status="running", message="run project colmap")
            existing_model = active_sparse_model(paths.root)
            _emit_event(
                jobs_db,
                session_id,
                "sfm",
                "started",
                "run project colmap",
                mode="incremental" if existing_model else "new",
                use_gpu=options.use_gpu,
            )
            checkpoint.start("sfm")
            if existing_model is None:
                sfm_stats = run_new_reconstruction(
                    colmap=require_tool("colmap"),
                    images_dir=paths.images,
                    database_path=paths.database,
                    sparse_dir=paths.sparse,
                    log_dir=layout.logs,
                    use_gpu=options.use_gpu,
                    image_list_path=layout.image_list,
                    mapper_snapshot_path=layout.snapshots / "sfm",
                    mapper_snapshot_frames_freq=options.mapper_snapshot_frames_freq,
                )
                sparse_model = Path(sfm_stats.sparse_model) if sfm_stats.sparse_model else None
                if sparse_model:
                    _replace_active_sparse(
                        paths.root,
                        sparse_model,
                        paths.sparse_versions / session_id,
                    )
            else:
                session_model = layout.root / "sparse_registered"
                sfm_stats = register_incremental_session(
                    colmap=require_tool("colmap"),
                    images_dir=paths.images,
                    database_path=paths.database,
                    existing_sparse_model=existing_model,
                    output_sparse_model=session_model,
                    log_dir=layout.logs,
                    vocab_tree_path=options.vocab_tree_path,
                    use_gpu=options.use_gpu,
                    image_list_path=layout.image_list,
                )
                _replace_active_sparse(paths.root, session_model, paths.sparse_versions / session_id)
            checkpoint.finish("sfm", **sfm_stats.to_dict())
            _emit_event(
                jobs_db,
                session_id,
                "sfm",
                "done",
                "project colmap completed",
                **sfm_stats.to_dict(),
            )

        textured_mesh: Path | None = None
        if not options.skip_mvs and not checkpoint.done("mvs"):
            db.update_job(jobs_db, job_id=session_id, status="running", message="run project openmvs")
            _emit_event(jobs_db, session_id, "mvs", "started", "run project openmvs")
            checkpoint.start("mvs")
            mvs_stats = run_openmvs(
                colmap=require_tool("colmap"),
                interface_colmap=require_tool("InterfaceCOLMAP"),
                densify_point_cloud=require_tool("DensifyPointCloud"),
                reconstruct_mesh=require_tool("ReconstructMesh"),
                refine_mesh=require_tool("RefineMesh"),
                texture_mesh=require_tool("TextureMesh"),
                colmap_workspace=paths.root,
                image_folder=paths.images,
                output_dir=layout.mvs_output,
                log_dir=layout.logs,
            )
            textured_mesh = Path(mvs_stats.textured_mesh_path)
            checkpoint.finish("mvs", **mvs_stats.to_dict())
            _emit_event(
                jobs_db,
                session_id,
                "mvs",
                "done",
                "project openmvs completed",
                **mvs_stats.to_dict(),
            )
        elif checkpoint.done("mvs"):
            textured = checkpoint.stages["mvs"].get("textured_mesh_path")
            textured_mesh = Path(textured) if textured else None
        elif options.skip_mvs:
            _emit_event(jobs_db, session_id, "mvs", "skipped", "openmvs skipped")

        if (
            not options.skip_optimize
            and textured_mesh is not None
            and not checkpoint.done("optimize")
        ):
            db.update_job(jobs_db, job_id=session_id, status="running", message="run blender")
            _emit_event(
                jobs_db,
                session_id,
                "optimize",
                "started",
                "run blender",
                collision_mode=options.collision_mode,
                target_faces=options.target_faces,
            )
            checkpoint.start("optimize")
            output_fbx = layout.output / f"{session_id}.fbx"
            optimize_stats = run_blender_optimize(
                blender=require_tool("blender"),
                input_mesh=textured_mesh,
                output_fbx=output_fbx,
                log_dir=layout.logs,
                target_faces=options.target_faces,
                collision_mode=options.collision_mode,
            )
            checkpoint.finish("optimize", **optimize_stats.to_dict())
            _emit_event(
                jobs_db,
                session_id,
                "optimize",
                "done",
                "blender optimization completed",
                **optimize_stats.to_dict(),
            )
        elif options.skip_optimize:
            _emit_event(jobs_db, session_id, "optimize", "skipped", "optimization skipped")

        stats = _stage_stats(checkpoint)
        summary_path = layout.output / "summary.json"
        summary_path.write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")
        write_quality_report(
            report_path=layout.report,
            title=f"VidToLevel Session Quality: {session_id}",
            stats=stats,
            work_dir=layout.root,
        )
        append_session(paths.root, session_id, video_path, stats, status="done")
        db.update_job(jobs_db, job_id=session_id, status="done", message="completed", stats=stats)
        _emit_event(jobs_db, session_id, "job", "done", "completed")
        return {
            "session_id": session_id,
            "project": str(paths.root),
            "work_dir": str(layout.root),
            "report": str(layout.report),
            "stats": stats,
        }
    except Exception as exc:
        stats = _stage_stats(checkpoint)
        append_session(paths.root, session_id, video_path, stats, status="failed")
        db.update_job(jobs_db, job_id=session_id, status="failed", message=str(exc), stats=stats)
        _emit_event(jobs_db, session_id, "job", "failed", str(exc))
        raise
