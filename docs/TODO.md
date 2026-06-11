# VidToLevel TODO

Updated: 2026-06-11

This file is the working handoff list. Keep it current before changing phases so
the project can resume without relying on conversation context.

## Active Priority

1. Phase 0 real toolchain smoke test
   - Install or add to `PATH`: COLMAP, Blender, OpenMVS binaries.
   - Run `vidtolevel doctor`.
   - Run a short phone-video pipeline with `--skip-optimize` first.
   - Confirm sparse model opens in `vidtolevel viewer`.

2. Viewer V2 live monitoring
   - Add WebSocket endpoint for job state.
   - Emit pipeline stage events from `process_video` and `add_project_session`.
   - Later, watch COLMAP snapshot folders and stream camera/point diffs.

3. Phase 4 collision upgrade
   - Replace the temporary `ground-slab` with ground/building split.
   - Keep `ground-slab` as a quick smoke-test fallback.

## Main Pipeline Backlog

- Phase 2: parse COLMAP/OpenMVS logs into richer failure reports.
- Phase 2: make reruns more reproducible with explicit command manifests.
- Phase 3: compare session-before/session-after reprojection and observation metrics.
- Phase 3: changed-area-only redensification instead of full project MVS.
- Phase 4: replace temporary `ground-slab` collision with ground/building split.
- Phase 4: add normal baking, texture tiling, and simple delighting.
- Phase 5: add UE5 material preset and level template workflow.
- Phase 6: add robust single-GPU queue locking and job recovery.

## Viewer Backlog

- V1: cached thumbnail generation. Done.
- V1: failure segment explanation panel with counts per reason.
- V2: WebSocket job state and live camera registration.
- V3: dense point downsampling and mesh-to-GLB preview.
- V4: session toggles, session colors, and coverage diff mode.
- V5: view presets, measurement tool, screenshot export, settings persistence.

## Current Known Blockers

- `ffmpeg` is available locally.
- `colmap`, `blender`, and OpenMVS binaries are not available on `PATH`.
- Full video-to-FBX validation is blocked until those external tools are installed.

## Completed Recently

- Viewer V1 point color modes: RGB, reprojection error, observation count, session.
- Viewer V1 path issue highlighting: large camera gaps and weak observations.
- Viewer V1 cached thumbnails: `/thumb` returns 320px cached JPEGs.
