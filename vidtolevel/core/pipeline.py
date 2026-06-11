from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from vidtolevel.core import db
from vidtolevel.core.checkpoint import Checkpoint
from vidtolevel.core.frames import extract_frames, filter_frames
from vidtolevel.core.mvs import run_openmvs
from vidtolevel.core.optimizer import run_blender_optimize
from vidtolevel.core.report import write_quality_report
from vidtolevel.core.sfm import run_new_reconstruction
from vidtolevel.core.tools import require_tool


@dataclass(frozen=True)
class ProcessOptions:
    video_path: Path
    runs_dir: Path = Path("runs")
    fps: float = 2.0
    blur_percentile: float = 15.0
    duplicate_threshold: float = 0.985
    job_id: str | None = None
    project: str | None = None
    use_gpu: bool = True
    skip_mvs: bool = False
    skip_optimize: bool = False
    target_faces: int = 500_000
    collision_mode: str = "ground-slab"
    database_path: Path = Path("vidtolevel.sqlite3")


@dataclass(frozen=True)
class RunLayout:
    root: Path
    input_video: Path
    logs: Path
    extracted_frames: Path
    accepted_images: Path
    rejected_frames: Path
    colmap_workspace: Path
    colmap_database: Path
    sparse: Path
    openmvs: Path
    output: Path
    checkpoint: Path


def make_job_id(video_path: Path) -> str:
    stem = video_path.stem.replace(" ", "_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{stem}"


def make_layout(runs_dir: Path, job_id: str) -> RunLayout:
    root = runs_dir / job_id
    colmap_workspace = root / "colmap"
    return RunLayout(
        root=root,
        input_video=root / "input" / "source.mp4",
        logs=root / "logs",
        extracted_frames=root / "frames" / "extracted",
        accepted_images=colmap_workspace / "images",
        rejected_frames=root / "frames" / "rejected",
        colmap_workspace=colmap_workspace,
        colmap_database=colmap_workspace / "database.db",
        sparse=colmap_workspace / "sparse",
        openmvs=root / "openmvs",
        output=root / "output",
        checkpoint=root / "checkpoint.json",
    )


def _stage_stats(checkpoint: Checkpoint) -> dict[str, Any]:
    return {
        stage: {key: value for key, value in payload.items() if key not in {"status"}}
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


def process_video(options: ProcessOptions) -> dict[str, Any]:
    video_path = options.video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    job_id = options.job_id or make_job_id(video_path)
    layout = make_layout(options.runs_dir.resolve(), job_id)
    layout.root.mkdir(parents=True, exist_ok=True)
    layout.logs.mkdir(parents=True, exist_ok=True)
    layout.output.mkdir(parents=True, exist_ok=True)

    db.create_job(
        options.database_path,
        job_id=job_id,
        project=options.project,
        video_path=video_path,
        work_dir=layout.root,
    )
    _emit_event(
        options.database_path,
        job_id,
        "job",
        "queued",
        "job queued",
        video_path=str(video_path),
        work_dir=str(layout.root),
    )
    checkpoint = Checkpoint.load(layout.checkpoint)

    try:
        db.update_job(options.database_path, job_id=job_id, status="running", message="copy input")
        if not checkpoint.done("input"):
            _emit_event(options.database_path, job_id, "input", "started", "copy input")
            checkpoint.start("input", source=str(video_path))
            layout.input_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video_path, layout.input_video)
            checkpoint.finish("input", copied_to=str(layout.input_video))
            _emit_event(
                options.database_path,
                job_id,
                "input",
                "done",
                "input copied",
                copied_to=str(layout.input_video),
            )

        if not checkpoint.done("frames"):
            db.update_job(options.database_path, job_id=job_id, status="running", message="extract frames")
            _emit_event(
                options.database_path,
                job_id,
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
                log_path=layout.logs / "ffmpeg_extract_frames.log",
            )
            frame_stats = filter_frames(
                layout.extracted_frames,
                layout.accepted_images,
                layout.rejected_frames,
                blur_percentile=options.blur_percentile,
                duplicate_threshold=options.duplicate_threshold,
            )
            checkpoint.finish(
                "frames",
                extracted_count=extracted_count,
                **frame_stats.to_dict(),
            )
            _emit_event(
                options.database_path,
                job_id,
                "frames",
                "done",
                "frames filtered",
                extracted_count=extracted_count,
                **frame_stats.to_dict(),
            )

        if not checkpoint.done("sfm"):
            db.update_job(options.database_path, job_id=job_id, status="running", message="run colmap")
            _emit_event(
                options.database_path,
                job_id,
                "sfm",
                "started",
                "run colmap",
                use_gpu=options.use_gpu,
            )
            checkpoint.start("sfm")
            sfm_stats = run_new_reconstruction(
                colmap=require_tool("colmap"),
                images_dir=layout.accepted_images,
                database_path=layout.colmap_database,
                sparse_dir=layout.sparse,
                log_dir=layout.logs,
                use_gpu=options.use_gpu,
            )
            checkpoint.finish("sfm", **sfm_stats.to_dict())
            _emit_event(
                options.database_path,
                job_id,
                "sfm",
                "done",
                "colmap completed",
                **sfm_stats.to_dict(),
            )
            if sfm_stats.registered_ratio is not None and sfm_stats.registered_ratio < 0.6:
                checkpoint.fail(
                    "quality_gate",
                    "Registered image ratio is below 60%. Check blur, overlap, and texture richness.",
                    registered_ratio=sfm_stats.registered_ratio,
                )
                _emit_event(
                    options.database_path,
                    job_id,
                    "quality_gate",
                    "failed",
                    "registered image ratio below 60%",
                    registered_ratio=sfm_stats.registered_ratio,
                )

        textured_mesh: Path | None = None
        if not options.skip_mvs and not checkpoint.done("mvs"):
            db.update_job(options.database_path, job_id=job_id, status="running", message="run openmvs")
            _emit_event(options.database_path, job_id, "mvs", "started", "run openmvs")
            checkpoint.start("mvs")
            mvs_stats = run_openmvs(
                interface_colmap=require_tool("InterfaceCOLMAP"),
                densify_point_cloud=require_tool("DensifyPointCloud"),
                reconstruct_mesh=require_tool("ReconstructMesh"),
                refine_mesh=require_tool("RefineMesh"),
                texture_mesh=require_tool("TextureMesh"),
                colmap_workspace=layout.colmap_workspace,
                output_dir=layout.openmvs,
                log_dir=layout.logs,
            )
            textured_mesh = Path(mvs_stats.textured_mesh_path)
            checkpoint.finish("mvs", **mvs_stats.to_dict())
            _emit_event(
                options.database_path,
                job_id,
                "mvs",
                "done",
                "openmvs completed",
                **mvs_stats.to_dict(),
            )
        elif checkpoint.done("mvs"):
            textured = checkpoint.stages["mvs"].get("textured_mesh_path")
            textured_mesh = Path(textured) if textured else None
        elif options.skip_mvs:
            _emit_event(options.database_path, job_id, "mvs", "skipped", "openmvs skipped")

        if (
            not options.skip_optimize
            and textured_mesh is not None
            and not checkpoint.done("optimize")
        ):
            db.update_job(options.database_path, job_id=job_id, status="running", message="run blender")
            _emit_event(
                options.database_path,
                job_id,
                "optimize",
                "started",
                "run blender",
                collision_mode=options.collision_mode,
                target_faces=options.target_faces,
            )
            checkpoint.start("optimize")
            output_fbx = layout.output / f"{job_id}.fbx"
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
                options.database_path,
                job_id,
                "optimize",
                "done",
                "blender optimization completed",
                **optimize_stats.to_dict(),
            )
        elif options.skip_optimize:
            _emit_event(options.database_path, job_id, "optimize", "skipped", "optimization skipped")

        final_stats = _stage_stats(checkpoint)
        summary_path = layout.output / "summary.json"
        summary_path.write_text(json.dumps(final_stats, indent=2, sort_keys=True), encoding="utf-8")
        report_path = layout.output / "quality_report.md"
        write_quality_report(
            report_path=report_path,
            title=f"VidToLevel Quality: {job_id}",
            stats=final_stats,
            work_dir=layout.root,
        )
        db.update_job(
            options.database_path,
            job_id=job_id,
            status="done",
            message="completed",
            stats=final_stats,
        )
        _emit_event(options.database_path, job_id, "job", "done", "completed")
        return {
            "job_id": job_id,
            "work_dir": str(layout.root),
            "report": str(report_path),
            "stats": final_stats,
        }
    except Exception as exc:
        db.update_job(options.database_path, job_id=job_id, status="failed", message=str(exc))
        _emit_event(options.database_path, job_id, "job", "failed", str(exc))
        raise
