# VidToLevel Progress

Updated: 2026-06-11

## Main Pipeline Status

| Phase | Status | Notes |
|---|---:|---|
| Phase 0: Environment | Complete for smoke | Python package and tests work. Windows RTX 4070 Super has local FFmpeg, CUDA COLMAP, Blender, and OpenMVS binaries. CUDA COLMAP feature extraction/matching, synthetic full MVS, and real phone-video `--skip-optimize` smoke are verified. |
| Phase 1: Shooting Protocol | Drafted | `docs/SHOOTING_GUIDE.md` contains the first capture checklist and residential street guidance. |
| Phase 2: Core Pipeline | Implemented scaffold | `vidtolevel process` extracts/filter frames, runs COLMAP/OpenMVS wrappers, records checkpoints, writes SQLite job state, and emits quality reports. Synthetic and real phone video-to-OBJ smoke pass on Windows RTX; Blender optimization remains separate validation. |
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

- `pytest`: 26 tests passing on Windows Python 3.12.
- `vidtolevel doctor` on Windows RTX 4070 Super resolves local `.tools` FFmpeg 8.1.1, COLMAP 4.1 dev with CUDA, Blender 5.0, and OpenMVS v2.4.0 binaries.
- COLMAP CUDA smoke on RTX 4070 Super: `feature_extractor` logs `Creating SIFT GPU feature extractor`; `sequential_matcher` logs GPU device 0 and `Creating SIFT GPU feature matcher`.
- Synthetic sparse pipeline smoke on Windows: `vidtolevel process .vidtolevel_smoke/synthetic_phone_like.mp4 --skip-mvs --skip-optimize` registered 24/24 images.
- Viewer on Windows: `vidtolevel viewer .vidtolevel_smoke/runs/synthetic_gpu_sparse --host 127.0.0.1 --port 8766` loads 24 cameras and 17,817 points; browser screenshot renders the point cloud and camera path.
- Synthetic full MVS smoke on Windows: `vidtolevel process .vidtolevel_smoke/synthetic_phone_like.mp4 --skip-optimize` registered 24/24 images, ran COLMAP `image_undistorter`, and completed OpenMVS `InterfaceCOLMAP` -> `DensifyPointCloud` -> `ReconstructMesh` -> `RefineMesh` -> `TextureMesh`.
- OpenMVS CUDA smoke on RTX 4070 Super: `DensifyPointCloud`, `ReconstructMesh`, and `TextureMesh` logs initialize `NVIDIA GeForce RTX 4070 SUPER`; textured output is `openmvs/colmap_dense/scene_dense_mesh_refine_texture.obj` with MTL/JPG companion assets.
- Viewer full-MVS smoke on Windows: `vidtolevel viewer .vidtolevel_smoke/runs/synthetic_gpu_mvs --host 127.0.0.1 --port 8766` loads 24 cameras, 17,568 points, and renders the OBJ mesh preview.
- OpenMVS wrapper now converts the COLMAP sparse model through `colmap image_undistorter`, imports the undistorted dense workspace, runs OpenMVS commands with `cwd=colmap_dense`, and passes generated PLY mesh files to `RefineMesh` / `TextureMesh` through `-m`.
- Real phone-video smoke on Windows: `vidtolevel process IMG_0001.mov --job-id phone_img_0001_smoke_v2 --skip-optimize` extracted 107 frames, accepted 91, selected `colmap/sparse/1`, registered 91/91 images, and completed OpenMVS textured OBJ output.
- Real phone-video OpenMVS output: Densify produced 2,452,062 dense points, ReconstructMesh saved a 1,774,552-vertex / 3,549,094-face raw mesh, RefineMesh saved 309,546 vertices / 618,124 faces, and TextureMesh wrote `scene_dense_mesh_refine_texture.obj` with two JPG texture maps.
- Viewer real-video smoke on Windows: `vidtolevel viewer runs/phone_img_0001_smoke_v2 --host 127.0.0.1 --port 8766` serves `sparse/1`, reports 91 cameras and 19,080 sparse points, and exposes the real OBJ mesh.
- COLMAP multi-model selection is fixed: SFM analyzes all mapper output folders and selects the reconstruction with the most registered images; MVS and Viewer follow the selected/largest sparse model instead of assuming `sparse/0`.
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

- No current Phase 0 smoke blocker is known. The real phone-video run intentionally used `--skip-optimize`, so real FBX/Blender optimization is still unverified on the captured mesh.
- No current Windows OpenMVS runtime blocker is known. If it fails again, check OpenMVS per-tool logs written under the dense workspace, not only VidToLevel's captured stdout logs.

## Next Work Queue

1. Viewer V3 mesh preview: automated OBJ-to-GLB conversion.
2. Viewer V3 texture/mesh inspection tools.
3. Optional real-mesh Blender optimize/FBX smoke.
4. Phase 4 collision upgrade: separate ground proxy from building proxies.
5. Phase 2 failure reports: parse COLMAP/OpenMVS logs into clearer recapture guidance.
6. Phase 6 operations: single-GPU queue locking and long-running job recovery.
