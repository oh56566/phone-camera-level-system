# VidToLevel Progress

Updated: 2026-06-11

## Main Pipeline Status

| Phase | Status | Notes |
|---|---:|---|
| Phase 0: Environment | Near complete | Python package and tests work. Windows RTX 4070 Super has local FFmpeg, CUDA COLMAP, Blender, and discoverable OpenMVS binaries. CUDA COLMAP feature extraction/matching is verified. Remaining validation: short real phone-video smoke test and Windows OpenMVS runtime fix. |
| Phase 1: Shooting Protocol | Drafted | `docs/SHOOTING_GUIDE.md` contains the first capture checklist and residential street guidance. |
| Phase 2: Core Pipeline | Implemented scaffold | `vidtolevel process` extracts/filter frames, runs COLMAP/OpenMVS wrappers, records checkpoints, writes SQLite job state, and emits quality reports. Full run awaits external tools. |
| Phase 3: Incremental Sessions | Implemented scaffold | `vidtolevel add-session`, persistent project images/database, active sparse model replacement, bundle adjustment wrapper, and coverage command are present. Changed-area-only redensification is not implemented yet. |
| Phase 4: Game Optimization | Partial | Blender headless FBX export, decimation, and `UCX_` ground-slab/bounds collision modes exist. Building/ground semantic separation, normal baking, V-HACD, and texture tiling remain. |
| Phase 5: UE5 Integration | Partial | UE import script exists for FBX import and Nanite enable. Level template, material preset, and World Partition workflow remain. |
| Phase 6: Operations | Partial | FastAPI job API, watch folder, SQLite status/events, and Discord notifier are present. Robust queue locking and long-running job recovery remain. |

## Viewer Status

| Viewer Phase | Status | Notes |
|---|---:|---|
| V0: Static Viewer | Complete | COLMAP binary parser, FastAPI static/API serving, binary point stream, Three.js sparse point view, camera frustums, path, timeline, and local vendor assets are working. |
| V1: Diagnostics | Complete | Frustum click selection, cached frame thumbnails, camera path, timeline, metrics, coverage panel, point render modes, path issue highlighting, and diagnostic reason summaries are present. |
| V2: Real-time Monitoring | In progress | `/ws/jobs` streams SQLite job status and stage events. `/ws/{project_id}` watches sparse model signatures, reports compact camera/point diffs, and refreshes viewer data when snapshots change. COLMAP mapper snapshot settings and snapshot-only run discovery are wired. |
| V3: Dense Data + Mesh Preview | In progress | OBJ and GLB/GLTF mesh preview are available with shaded/wire/both render modes and adjustable opacity. Dense point downsampling, automated GLB conversion, and richer texture inspection remain. |
| V4: Coverage + Session Compare | Partial | Coverage grid API exists. Session coloring/diff reports and mobile capture-mode UI remain. |
| V5: Finish | Partial | `vidtolevel viewer` command launches server and browser. Measurement tools, screenshots, view presets, and settings persistence remain. |

## Verified

- `pytest`: 22 tests passing on Windows Python 3.12.
- `vidtolevel doctor` on Windows RTX 4070 Super resolves local `.tools` FFmpeg 8.1.1, COLMAP 4.1 dev with CUDA, Blender 5.0, and OpenMVS v2.4.0 binaries.
- COLMAP CUDA smoke on RTX 4070 Super: `feature_extractor` logs `Creating SIFT GPU feature extractor`; `sequential_matcher` logs GPU device 0 and `Creating SIFT GPU feature matcher`.
- Synthetic sparse pipeline smoke on Windows: `vidtolevel process .vidtolevel_smoke/synthetic_phone_like.mp4 --skip-mvs --skip-optimize` registered 24/24 images.
- Viewer on Windows: `vidtolevel viewer .vidtolevel_smoke/runs/synthetic_gpu_sparse --host 127.0.0.1 --port 8766` loads 24 cameras and 17,817 points; browser screenshot renders the point cloud and camera path.
- Windows local tool discovery handles `.exe`, versioned `.tools/<tool>/<version>/bin`, and Program Files Blender discovery.
- SQLite job DB helpers close connections explicitly so temp database tests pass on Windows.
- `vidtolevel process` now resolves FFmpeg through `require_tool("ffmpeg")` instead of assuming `ffmpeg` is on PATH.
- `vidtolevel doctor`: FFmpeg, COLMAP, Blender, and required OpenMVS binaries resolve successfully.
- OpenMVS v2.4.0 macOS arm64 prebuilt launches `InterfaceCOLMAP --help`.
- Viewer WebSocket job state connects in browser and reports `Live: no jobs` when no job database exists.
- Viewer WebSocket live status displays the latest pipeline stage event from SQLite.
- Viewer project WebSocket connects against a fixture sparse model and keeps shutdown clean.
- Viewer diagnostics panel displays path issue reason counts in browser.
- Viewer project WebSocket payload includes compact camera/point diff data.
- COLMAP mapper commands include snapshot flags when `--mapper-snapshot-frames-freq` is enabled.
- Viewer discovery loads child run projects from parent folders and handles snapshot-only sparse models.
- Viewer simple mesh preview renders the first available OBJ mesh in browser, and mesh mode/opacity controls switch the same mesh between shaded and wire views.
- Viewer GLB preview prefers `.glb`/`.gltf` meshes over OBJ, serves the selected mesh and companion assets with matching media types, and renders it in browser with GLTFLoader.
- `vidtolevel viewer` renders a fixture sparse model in browser.
- Viewer API returns projects, status, cameras, points, and coverage.
- Viewer uses local Three.js/OrbitControls assets instead of an external CDN.
- Git remote is configured and commits are pushed to `origin/main`.

## Current Blockers

- A real short phone video is needed for end-to-end video-to-sparse/MVS smoke testing.
- Windows OpenMVS v2.4.0 CPU and CUDA release binaries are discoverable but exit 1 with empty logs on `-h` and on valid `InterfaceCOLMAP` input; full MVS/mesh smoke is blocked until this runtime issue is resolved.

## Next Work Queue

1. Phase 0 first real phone-video smoke test.
2. Phase 4 collision upgrade: separate ground proxy from building proxies.
3. Viewer V3 mesh preview: automated OBJ-to-GLB conversion and texture/mesh inspection tools.
4. Phase 2 failure reports: parse COLMAP/OpenMVS logs into clearer recapture guidance.
5. Phase 6 operations: single-GPU queue locking and long-running job recovery.
