from __future__ import annotations

import argparse
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from vidtolevel.core.pipeline import ProcessOptions, process_video
from vidtolevel.core.session import SessionOptions, add_project_session
from vidtolevel.server.notify import DiscordNotifier


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v"}


class VideoHandler(FileSystemEventHandler):
    def __init__(
        self,
        runs_dir: Path,
        *,
        project_root: Path | None = None,
        settle_seconds: float = 5.0,
        discord_webhook: str | None = None,
    ) -> None:
        self.runs_dir = runs_dir
        self.project_root = project_root
        self.settle_seconds = settle_seconds
        self.notifier = DiscordNotifier(discord_webhook)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            return
        time.sleep(self.settle_seconds)
        try:
            if self.project_root:
                result = add_project_session(
                    SessionOptions(video_path=path, project_root=self.project_root)
                )
                self.notifier.send(f"VidToLevel watch completed: {result['session_id']}")
            else:
                result = process_video(ProcessOptions(video_path=path, runs_dir=self.runs_dir))
                self.notifier.send(f"VidToLevel watch completed: {result['job_id']}")
        except Exception as exc:
            self.notifier.send(f"VidToLevel watch failed for {path.name}: {exc}")
            raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("watch_dir")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--project")
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--discord-webhook")
    args = parser.parse_args(argv)

    watch_dir = Path(args.watch_dir).resolve()
    handler = VideoHandler(
        Path(args.runs_dir).resolve(),
        project_root=Path(args.project).resolve() if args.project else None,
        settle_seconds=args.settle_seconds,
        discord_webhook=args.discord_webhook,
    )
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
