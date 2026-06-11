# VidToLevel TODO

Updated: 2026-06-11

This file is the working handoff list. Keep it current before changing phases so
the project can resume without relying on conversation context.

## Active Priority

1. Phase 0 real toolchain smoke test
   - Done locally: FFmpeg, COLMAP, Blender, and OpenMVS are discoverable by `vidtolevel doctor`.
   - Done on Windows RTX 4070 Super: COLMAP 4.1 dev CUDA build runs GPU feature extraction and matching.
   - Done on Windows RTX 4070 Super: synthetic video sparse smoke registers 24/24 frames and opens in `vidtolevel viewer`.
   - Run a short real phone-video pipeline with `--skip-optimize` first once a sample `.mp4` is available.
   - Resolve Windows OpenMVS v2.4.0 binary launch failure before full MVS smoke; both CPU and CUDA release binaries currently exit 1 with empty logs.

2. Viewer V2 live monitoring
   - Done: add WebSocket endpoint for job state backed by SQLite polling.
   - Done: viewer status bar shows live job state and reconnects automatically.
   - Done: watch sparse model signatures via project WebSocket and refresh viewer data when snapshots change.
   - Done: emit pipeline stage events from `process_video` and `add_project_session`.
   - Later, stream compact camera/point diffs instead of full viewer refresh.

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
- V1: failure segment explanation panel with counts per reason. Done.
- V2: WebSocket job state. Done.
- V2: Pipeline stage event stream. Done.
- V2: Sparse snapshot watching. Done.
- V2: Compact live camera/point diff messages. Done.
- V2: COLMAP mapper snapshot CLI/settings. Done.
- V2: Automatic run/snapshot folder discovery. Done.
- V3: simple OBJ mesh preview. Done.
- V3: mesh preview render controls for shaded/wire/both modes and opacity. Done.
- V3: GLB/GLTF mesh discovery, serving, and browser preview. Done.
- V3: dense point downsampling and richer texture inspection tools.
- V4: session toggles, session colors, and coverage diff mode.
- V5: view presets, measurement tool, screenshot export, settings persistence.

## Current Known Blockers

- Full video-to-FBX validation now needs a short real sample phone video.
- Windows OpenMVS v2.4.0 release binaries are discoverable but currently exit 1 with empty logs before producing `scene.mvs`.
- Full OpenMVS/mesh validation is blocked until the Windows OpenMVS runtime issue is resolved.

## Completed Recently

- Windows RTX smoke: local `.tools` FFmpeg, COLMAP CUDA, and OpenMVS binaries are discoverable by `vidtolevel doctor`; Blender 5.0 is discovered from Program Files.
- COLMAP 4.x compatibility: GPU flags now adapt to `FeatureExtraction.use_gpu` / `FeatureMatching.use_gpu` while preserving old `Sift*` fallback.
- Synthetic sparse pipeline smoke: `vidtolevel process --skip-mvs --skip-optimize` registered 24/24 frames and the viewer rendered 24 cameras / 17,817 points.
- Viewer V3 mesh preview controls: first available `.obj` mesh can be viewed as shaded, wire, or both with adjustable opacity.
- Viewer V3 GLB preview: `.glb`/`.gltf` meshes are preferred over OBJ, served with matching media types and companion asset paths, and rendered with GLTFLoader.
- Viewer V3 simple mesh preview: first available `.obj` mesh is served and rendered as a translucent viewport layer.
- Viewer V1 diagnostics summary: side panel shows path issue counts by reason.
- Viewer V2 compact sparse diffs: project WebSocket reports camera/point count deltas and ID samples.
- COLMAP mapper snapshots: `process` and `add-session` can write sparse snapshots for live viewer refresh.
- Viewer discovery: parent folders such as `runs/` resolve child run projects, including snapshot-only sparse models.
- Pipeline stage events: job/input/frames/sfm/mvs/optimize events are stored in SQLite and surfaced in Viewer live status.
- Viewer V2 live job status: `/ws/jobs` streams SQLite job state to the status bar.
- Viewer V2 sparse snapshot status: `/ws/{project_id}` detects COLMAP sparse model changes and triggers viewer refresh.
- Phase 0 tool discovery: FFmpeg, COLMAP, Blender, and OpenMVS v2.4.0 are available locally.
- Added macOS OpenMVS prebuilt installer and local `.tools/openmvs/bin` discovery.
- Viewer V1 point color modes: RGB, reprojection error, observation count, session.
- Viewer V1 path issue highlighting: large camera gaps and weak observations.
- Viewer V1 cached thumbnails: `/thumb` returns 320px cached JPEGs.
