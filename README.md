# VidToLevel

VidToLevel turns phone video into UE5-oriented scan assets through a local
photogrammetry pipeline:

1. Extract and filter frames with FFmpeg/OpenCV.
2. Run COLMAP SfM.
3. Run OpenMVS densification, meshing, and texturing.
4. Optionally run Blender headless optimization/export.
5. Import the FBX/OBJ result into Unreal Engine.

This repository is the initial implementation scaffold for the MVP described in
the project plan. The external photogrammetry tools are intentionally called as
separate binaries so that GPU/CUDA builds can be swapped without changing Python
code.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

vidtolevel doctor
vidtolevel process /path/to/video.mp4 --fps 2
vidtolevel viewer runs
```

Expected external binaries:

- `ffmpeg`
- `colmap`
- OpenMVS binaries: `InterfaceCOLMAP`, `DensifyPointCloud`,
  `ReconstructMesh`, `RefineMesh`, `TextureMesh`
- `blender` for the optional optimization step

## Repository Layout

```text
vidtolevel/
  cli/                  # process, add-session, status, coverage, doctor
  core/                 # frame processing, tool wrappers, checkpoints, DB
  optimize/             # Blender headless script
  server/               # FastAPI queue, watcher, notifications
  unreal/               # UE editor import script
docs/
  SHOOTING_GUIDE.md
projects/
```

## MVP Command

```bash
vidtolevel process samples/test.mp4 --fps 2 --target-faces 500000
```

The command creates a timestamped run directory under `runs/`, records stage
checkpoints, stores job metadata in SQLite, and writes logs for each external
tool invocation.

By default, Blender export includes a `UCX_` ground-slab collision mesh for
initial walk tests. Use `--collision-mode bounds` for a single blocking proxy or
`--collision-mode none` when collision will be authored manually in UE5.

## Project Sessions

Use project sessions when scanning the same space repeatedly:

```bash
vidtolevel init-project projects/my_neighborhood
vidtolevel add-session /path/to/pass_001.mp4 --project projects/my_neighborhood --fps 2
vidtolevel add-session /path/to/pass_002.mp4 --project projects/my_neighborhood --fps 2
vidtolevel coverage --project projects/my_neighborhood --cell-size 1
```

Project sessions keep a shared COLMAP database in `projects/<name>/database.db`,
stage accepted frames into `projects/<name>/images/<session_id>/`, and update
the active sparse model at `projects/<name>/sparse/0`.

## Operations

```bash
# Process new videos dropped into a folder.
vidtolevel watch /path/to/upload_folder --project projects/my_neighborhood

# Run the job API.
vidtolevel serve --host 127.0.0.1 --port 8080

# Inspect sparse reconstructions in a browser.
vidtolevel viewer runs projects
```

Every run writes a `summary.json`, a Markdown quality report, and per-tool logs.
If a stage fails, rerun the same command with the same `--job-id` or
`--session-id` to resume from the last completed checkpoint.

The viewer is self-contained: Three.js and OrbitControls are served from
`vidtolevel/viewer/web/vendor/`, so sparse reconstruction inspection does not
depend on an external CDN.

## Current Toolchain Status

`vidtolevel doctor` reports which external binaries are available. The Python
package is usable before the photogrammetry tools are installed, but full
reconstruction requires COLMAP, OpenMVS, and Blender on `PATH`.


## Reconstruction Viewer

```bash
vidtolevel viewer runs/20260101_120000_scan
```

The viewer starts a FastAPI server at `http://127.0.0.1:8765`, opens a browser,
and renders the COLMAP sparse model from a VidToLevel run folder or a direct
`colmap/sparse/0` model folder. The first version shows sparse RGB points,
camera frustums, the capture path, timeline scrubbing, and basic reconstruction
metrics.
