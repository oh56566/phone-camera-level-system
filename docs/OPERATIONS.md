# Operations Workflow

## Single Video MVP

1. Record a short 4K test clip using `docs/SHOOTING_GUIDE.md`.
2. Run `vidtolevel doctor`.
3. Run `vidtolevel process clip.mp4 --fps 2`.
4. Open the generated quality report under `runs/<job_id>/output/quality_report.md`.
5. Import the optimized FBX from `runs/<job_id>/output/` into UE5, or run the
   Unreal script in `vidtolevel/unreal/import_scan.py`.

## Incremental Project

1. Create a project with `vidtolevel init-project projects/<name>`.
2. Add each capture pass with `vidtolevel add-session clip.mp4 --project projects/<name>`.
3. Use `vidtolevel status --project projects/<name>` to see session jobs.
4. Use `vidtolevel coverage --project projects/<name>` after sparse
   reconstruction to write `coverage.csv`, `coverage.svg`, and `coverage.json`.
5. Use `vidtolevel viewer projects/<name>` to inspect sparse points and camera
   placement.

The viewer serves its JavaScript runtime locally, including Three.js, so it can
be used on an offline scan workstation after the Python package is installed.

## Watch Folder

```bash
vidtolevel watch /path/to/upload_folder --project projects/<name>
```

The watcher waits for newly created `.mp4`, `.mov`, or `.m4v` files, then runs
the project session pipeline. Add `--discord-webhook <url>` to receive completion
or failure messages.

## Job API

```bash
vidtolevel serve --host 127.0.0.1 --port 8080
```

Endpoints:

- `GET /health`
- `POST /jobs`
- `GET /jobs?database=vidtolevel.sqlite3`
- `GET /jobs/{job_id}?database=vidtolevel.sqlite3`

Use `project_root` in the `POST /jobs` payload to add a video as an incremental
project session.
