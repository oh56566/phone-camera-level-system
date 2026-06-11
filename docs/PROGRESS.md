# VidToLevel Progress

Updated: 2026-06-11

## Main Pipeline Status

| Phase | Status | Notes |
|---|---:|---|
| Phase 0: Environment | Near complete | Python package and tests work. FFmpeg, COLMAP, Blender, and OpenMVS are available locally. Remaining validation: short real phone-video smoke test and CUDA-enabled COLMAP check on the RTX machine. |
| Phase 1: Shooting Protocol | Drafted | `docs/SHOOTING_GUIDE.md` contains the first capture checklist and residential street guidance. |
| Phase 2: Core Pipeline | Implemented scaffold | `vidtolevel process` extracts/filter frames, runs COLMAP/OpenMVS wrappers, records checkpoints, writes SQLite job state, and emits quality reports. Full run awaits external tools. |
| Phase 3: Incremental Sessions | Implemented scaffold | `vidtolevel add-session`, persistent project images/database, active sparse model replacement, bundle adjustment wrapper, and coverage command are present. Changed-area-only redensification is not implemented yet. |
| Phase 4: Game Optimization | Partial | Blender headless FBX export, decimation, and `UCX_` ground-slab/bounds collision modes exist. Building/ground semantic separation, normal baking, V-HACD, and texture tiling remain. |
| Phase 5: UE5 Integration | Partial | UE import script exists for FBX import and Nanite enable. Level template, material preset, and World Partition workflow remain. |
| Phase 6: Operations | Partial | FastAPI job API, watch folder, SQLite status, and Discord notifier are present. Robust queue locking, live progress events, and long-running job recovery remain. |

## Viewer Status

| Viewer Phase | Status | Notes |
|---|---:|---|
| V0: Static Viewer | Complete | COLMAP binary parser, FastAPI static/API serving, binary point stream, Three.js sparse point view, camera frustums, path, timeline, and local vendor assets are working. |
| V1: Diagnostics | In progress | Frustum click selection, cached frame thumbnails, camera path, timeline, metrics, coverage panel, point render modes, and path issue highlighting are present. Failure explanation summaries are the remaining V1 polish. |
| V2: Real-time Monitoring | Not started | WebSocket, COLMAP snapshot watching, and live diff updates remain. |
| V3: Dense Data + Mesh Preview | Not started | Dense point downsampling, GLB conversion, mesh preview, wireframe/texture toggles remain. |
| V4: Coverage + Session Compare | Partial | Coverage grid API exists. Session coloring/diff reports and mobile capture-mode UI remain. |
| V5: Finish | Partial | `vidtolevel viewer` command launches server and browser. Measurement tools, screenshots, view presets, and settings persistence remain. |

## Verified

- `pytest`: 13 tests passing.
- `vidtolevel doctor`: FFmpeg, COLMAP, Blender, and required OpenMVS binaries resolve successfully.
- OpenMVS v2.4.0 macOS arm64 prebuilt launches `InterfaceCOLMAP --help`.
- `vidtolevel viewer` renders a fixture sparse model in browser.
- Viewer API returns projects, status, cameras, points, and coverage.
- Viewer uses local Three.js/OrbitControls assets instead of an external CDN.
- Git remote is configured and commits are pushed to `origin/main`.

## Current Blockers

- A real short phone video is needed for end-to-end video-to-sparse/MVS smoke testing.
- CUDA validation cannot be completed on this Mac because Homebrew COLMAP reports `without CUDA`.

## Next Work Queue

1. Phase 0 first real phone-video smoke test.
2. Phase 4 collision upgrade: separate ground proxy from building proxies.
3. Viewer V2 live monitoring: WebSocket job state and COLMAP snapshot updates.
4. Viewer V3 mesh preview: convert textured mesh outputs to GLB for inspection.
5. Viewer V1 failure explanation summaries with counts per issue reason.
