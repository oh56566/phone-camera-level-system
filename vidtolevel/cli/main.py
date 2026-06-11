from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from pathlib import Path

from vidtolevel import __version__
from vidtolevel.core import db
from vidtolevel.core.coverage import generate_project_coverage
from vidtolevel.core.pipeline import ProcessOptions, process_video
from vidtolevel.core.project import init_project
from vidtolevel.core.session import SessionOptions, add_project_session
from vidtolevel.core.tools import which


OPENMVS_TOOLS = [
    "InterfaceCOLMAP",
    "DensifyPointCloud",
    "ReconstructMesh",
    "RefineMesh",
    "TextureMesh",
]


def cmd_doctor(_: argparse.Namespace) -> int:
    tools = ["ffmpeg", "colmap", "blender", *OPENMVS_TOOLS]
    ok = True
    for tool in tools:
        resolved = which(tool)
        status = "OK" if resolved else "MISSING"
        print(f"{status:7} {tool:20} {resolved or ''}")
        ok = ok and bool(resolved)
    return 0 if ok else 1


def cmd_process(args: argparse.Namespace) -> int:
    result = process_video(
        ProcessOptions(
            video_path=Path(args.video),
            runs_dir=Path(args.runs_dir),
            fps=args.fps,
            blur_percentile=args.blur_percentile,
            duplicate_threshold=args.duplicate_threshold,
            job_id=args.job_id,
            project=args.project,
            use_gpu=not args.cpu,
            skip_mvs=args.skip_mvs,
            skip_optimize=args.skip_optimize,
            target_faces=args.target_faces,
            collision_mode=args.collision_mode,
            database_path=Path(args.database),
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    database = Path(args.project) / "jobs.sqlite3" if args.project else Path(args.database)
    jobs = db.list_jobs(database, limit=args.limit)
    print(json.dumps(jobs, indent=2, ensure_ascii=False))
    return 0


def cmd_init_project(args: argparse.Namespace) -> int:
    paths = init_project(Path(args.path), name=args.name)
    print(json.dumps({"project": str(paths.root), "metadata": str(paths.metadata)}, indent=2))
    return 0


def cmd_add_session(args: argparse.Namespace) -> int:
    project_root = Path(args.project)
    init_project(project_root)
    result = add_project_session(
        SessionOptions(
            video_path=Path(args.video),
            project_root=project_root,
            fps=args.fps,
            session_id=args.session_id,
            use_gpu=not args.cpu,
            skip_mvs=args.skip_mvs,
            skip_optimize=args.skip_optimize,
            target_faces=args.target_faces,
            collision_mode=args.collision_mode,
            vocab_tree_path=Path(args.vocab_tree) if args.vocab_tree else None,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    stats = generate_project_coverage(
        Path(args.project),
        cell_size=args.cell_size,
        axes=(args.axis_a, args.axis_b),
    )
    print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("vidtolevel.server.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from vidtolevel.server.watcher import main as watcher_main

    watcher_args = [args.watch_dir, "--runs-dir", args.runs_dir, "--settle-seconds", str(args.settle_seconds)]
    if args.project:
        watcher_args.extend(["--project", args.project])
    if args.discord_webhook:
        watcher_args.extend(["--discord-webhook", args.discord_webhook])
    return watcher_main(watcher_args)


def cmd_viewer(args: argparse.Namespace) -> int:
    import uvicorn

    from vidtolevel.viewer.server.api import create_viewer_app

    paths = [Path(path) for path in args.paths]
    app = create_viewer_app(paths)
    project_count = len(app.state.viewer_projects)
    url = f"http://{args.host}:{args.port}"
    print(f"VidToLevel viewer: {url}")
    print(f"Loaded {project_count} reconstruction project(s).")
    if args.open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vidtolevel")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check external tool availability.")
    doctor.set_defaults(func=cmd_doctor)

    process = subparsers.add_parser("process", help="Run video-to-level pipeline.")
    process.add_argument("video", help="Input video path.")
    process.add_argument("--runs-dir", default="runs")
    process.add_argument("--database", default="vidtolevel.sqlite3")
    process.add_argument("--job-id")
    process.add_argument("--project")
    process.add_argument("--fps", type=float, default=2.0)
    process.add_argument("--blur-percentile", type=float, default=15.0)
    process.add_argument("--duplicate-threshold", type=float, default=0.985)
    process.add_argument("--cpu", action="store_true", help="Disable COLMAP GPU extraction/matching.")
    process.add_argument("--skip-mvs", action="store_true")
    process.add_argument("--skip-optimize", action="store_true")
    process.add_argument("--target-faces", type=int, default=500_000)
    process.add_argument("--collision-mode", choices=["ground-slab", "bounds", "none"], default="ground-slab")
    process.set_defaults(func=cmd_process)

    status = subparsers.add_parser("status", help="List recent jobs.")
    status.add_argument("--database", default="vidtolevel.sqlite3")
    status.add_argument("--project")
    status.add_argument("--limit", type=int, default=20)
    status.set_defaults(func=cmd_status)

    init = subparsers.add_parser("init-project", help="Create a persistent project folder.")
    init.add_argument("path")
    init.add_argument("--name")
    init.set_defaults(func=cmd_init_project)

    add_session = subparsers.add_parser("add-session", help="Process a video into a project session folder.")
    add_session.add_argument("video")
    add_session.add_argument("--project", required=True)
    add_session.add_argument("--session-id")
    add_session.add_argument("--fps", type=float, default=2.0)
    add_session.add_argument("--cpu", action="store_true", help="Disable COLMAP GPU extraction/matching.")
    add_session.add_argument("--skip-mvs", action="store_true")
    add_session.add_argument("--skip-optimize", action="store_true")
    add_session.add_argument("--target-faces", type=int, default=500_000)
    add_session.add_argument("--collision-mode", choices=["ground-slab", "bounds", "none"], default="ground-slab")
    add_session.add_argument("--vocab-tree")
    add_session.set_defaults(func=cmd_add_session)

    coverage = subparsers.add_parser("coverage", help="Generate project coverage report.")
    coverage.add_argument("--project", required=True)
    coverage.add_argument("--cell-size", type=float, default=1.0)
    coverage.add_argument("--axis-a", choices=["x", "y", "z"], default="x")
    coverage.add_argument("--axis-b", choices=["x", "y", "z"], default="y")
    coverage.set_defaults(func=cmd_coverage)

    serve = subparsers.add_parser("serve", help="Run the FastAPI job server.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    watch = subparsers.add_parser("watch", help="Watch a folder and process new videos.")
    watch.add_argument("watch_dir")
    watch.add_argument("--runs-dir", default="runs")
    watch.add_argument("--project")
    watch.add_argument("--settle-seconds", type=float, default=5.0)
    watch.add_argument("--discord-webhook")
    watch.set_defaults(func=cmd_watch)

    viewer = subparsers.add_parser("viewer", help="Launch the 3D reconstruction viewer.")
    viewer.add_argument(
        "paths",
        nargs="*",
        default=["runs", "projects"],
        help="Run folder, COLMAP sparse model folder, or parent directory to scan.",
    )
    viewer.add_argument("--host", default="127.0.0.1")
    viewer.add_argument("--port", type=int, default=8765)
    viewer.add_argument("--log-level", default="info")
    viewer.add_argument("--no-open", dest="open_browser", action="store_false")
    viewer.set_defaults(func=cmd_viewer, open_browser=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
