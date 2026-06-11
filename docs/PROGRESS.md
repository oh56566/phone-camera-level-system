# VidToLevel Progress

Updated: 2026-06-11

## Main Pipeline Status

| Phase | Status | Notes |
|---|---:|---|
| Phase 0: Environment | Partial | Python package and tests work. `ffmpeg` is available. `colmap`, `blender`, and OpenMVS binaries are still missing on this machine. |
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
| V1: Diagnostics | In progress | Frustum click selection, available frame thumbnail display, camera path, timeline, metrics, coverage panel, and point render modes are present. Failure-gap highlighting is the next active work. |
| V2: Real-time Monitoring | Not started | WebSocket, COLMAP snapshot watching, and live diff updates remain. |
| V3: Dense Data + Mesh Preview | Not started | Dense point downsampling, GLB conversion, mesh preview, wireframe/texture toggles remain. |
| V4: Coverage + Session Compare | Partial | Coverage grid API exists. Session coloring/diff reports and mobile capture-mode UI remain. |
| V5: Finish | Partial | `vidtolevel viewer` command launches server and browser. Measurement tools, screenshots, view presets, and settings persistence remain. |

## Verified

- `pytest`: 10 tests passing.
- `vidtolevel viewer` renders a fixture sparse model in browser.
- Viewer API returns projects, status, cameras, points, and coverage.
- Viewer uses local Three.js/OrbitControls assets instead of an external CDN.

## Current Blockers

- External photogrammetry tools are not installed locally: COLMAP, Blender, OpenMVS.
- No Git remote is configured yet, so push cannot be completed until a remote URL is added.

## Next Work Queue

1. Viewer V1 path gap highlighting: detect large camera jumps or weak observed-point segments.
2. Viewer V1 thumbnail generation: create cached 320px thumbnails instead of serving originals.
3. Phase 0 external tool install and first real phone-video smoke test.
4. Phase 4 collision upgrade: separate ground proxy from building proxies.
5. Viewer V2 live monitoring: WebSocket job state and COLMAP snapshot updates.
