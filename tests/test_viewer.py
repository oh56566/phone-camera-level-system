from __future__ import annotations

import importlib.util
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None
FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None
REPO_ROOT = Path(__file__).resolve().parents[1]


class ViewerParserTests(unittest.TestCase):
    def test_camera_path_diagnostics_flags_large_gaps_and_weak_observations(self) -> None:
        from vidtolevel.viewer.server.diagnostics import annotate_camera_path, summarize_camera_path

        cameras = annotate_camera_path(
            [
                {"position": [0.0, 0.0, 0.0], "registeredPointCount": 100},
                {"position": [1.0, 0.0, 0.0], "registeredPointCount": 100},
                {"position": [2.0, 0.0, 0.0], "registeredPointCount": 12},
                {"position": [20.0, 0.0, 0.0], "registeredPointCount": 100},
            ]
        )

        self.assertFalse(cameras[1]["pathIssueAfterPrevious"])
        self.assertTrue(cameras[2]["pathIssueAfterPrevious"])
        self.assertIn("weak_observations", cameras[2]["pathIssueReasons"])
        self.assertTrue(cameras[3]["pathIssueAfterPrevious"])
        self.assertIn("large_gap", cameras[3]["pathIssueReasons"])
        summary = summarize_camera_path(cameras)
        self.assertEqual(summary["issueCount"], 2)
        self.assertEqual(summary["reasonCounts"]["weak_observations"], 2)
        self.assertEqual(summary["reasonCounts"]["large_gap"], 1)

    def test_viewer_static_assets_are_local(self) -> None:
        index = (REPO_ROOT / "vidtolevel" / "viewer" / "web" / "index.html").read_text(
            encoding="utf-8"
        )
        app = (REPO_ROOT / "vidtolevel" / "viewer" / "web" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('"/assets/vendor/three.module.js"', index)
        self.assertIn('"/assets/vendor/examples/jsm/"', index)
        self.assertIn('id="status-live"', index)
        self.assertIn('id="diagnostic-body"', index)
        self.assertIn('id="layer-mesh"', index)
        self.assertIn('id="mesh-mode"', index)
        self.assertIn('id="mesh-opacity"', index)
        self.assertIn("map_Kd", app)
        self.assertIn("TextureLoader", app)
        self.assertNotIn("unpkg.com", index)
        self.assertTrue(
            (REPO_ROOT / "vidtolevel" / "viewer" / "web" / "vendor" / "three.module.js").exists()
        )
        self.assertTrue(
            (
                REPO_ROOT
                / "vidtolevel"
                / "viewer"
                / "web"
                / "vendor"
                / "examples"
                / "jsm"
                / "controls"
                / "OrbitControls.js"
            ).exists()
        )
        self.assertTrue(
            (
                REPO_ROOT
                / "vidtolevel"
                / "viewer"
                / "web"
                / "vendor"
                / "examples"
                / "jsm"
                / "loaders"
                / "GLTFLoader.js"
            ).exists()
        )
        self.assertTrue(
            (
                REPO_ROOT
                / "vidtolevel"
                / "viewer"
                / "web"
                / "vendor"
                / "examples"
                / "jsm"
                / "utils"
                / "BufferGeometryUtils.js"
            ).exists()
        )

    @unittest.skipIf(not NUMPY_AVAILABLE, "numpy is not installed")
    def test_colmap_parser_reads_binary_sparse_model(self) -> None:
        from vidtolevel.viewer.server.colmap_parser import read_sparse_model

        with tempfile.TemporaryDirectory() as tmp:
            sparse = _write_sparse_model(Path(tmp) / "run" / "colmap" / "sparse" / "0")

            model = read_sparse_model(sparse)

            self.assertEqual(len(model.cameras), 1)
            self.assertEqual(len(model.images), 2)
            self.assertEqual(len(model.points3d), 2)
            self.assertEqual(model.images[2].center.tolist(), [1.0, 0.0, 0.0])
            self.assertEqual(model.images[1].registered_point_count, 1)
            self.assertTrue(
                math.isclose(model.cameras[1].fov[0], 2.0 * math.atan(640 / 1000), rel_tol=1e-6)
            )

    @unittest.skipIf(not (NUMPY_AVAILABLE and FASTAPI_AVAILABLE), "viewer dependencies are not installed")
    def test_viewer_api_exposes_projects_cameras_and_points(self) -> None:
        from vidtolevel.viewer.server.api import create_viewer_app, discover_projects

        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            _write_sparse_model(run_root / "colmap" / "sparse" / "0")
            images_dir = run_root / "colmap" / "images"
            images_dir.mkdir(parents=True)
            (images_dir / "0001.jpg").write_bytes(b"fake-jpeg")
            _write_obj_mesh(run_root / "openmvs" / "scene_dense_mesh_refine_texture.obj")
            _write_glb_mesh(run_root / "openmvs" / "scene_dense_mesh_refine_texture.glb")
            (run_root / "openmvs" / "preview.bin").write_bytes(b"mesh-asset")
            projects = discover_projects([run_root])

            self.assertEqual(list(projects), ["run"])
            self.assertTrue(projects["run"].mesh_path)
            self.assertEqual(projects["run"].mesh_path.suffix, ".glb")

            app = create_viewer_app([run_root])
            project_endpoint = _endpoint(app, "/api/projects")
            cameras_endpoint = _endpoint(app, "/api/{project_id}/cameras")
            points_endpoint = _endpoint(app, "/api/{project_id}/points")
            status_endpoint = _endpoint(app, "/api/{project_id}/status")
            mesh_endpoint = _endpoint(app, "/api/{project_id}/mesh.{extension}")
            mesh_asset_endpoint = _endpoint(app, "/api/{project_id}/mesh-assets/{asset_path:path}")

            project_response = project_endpoint()
            self.assertEqual(project_response[0]["id"], "run")

            status_response = status_endpoint("run")
            self.assertIn("modelSignature", status_response)
            self.assertIn("diagnostics", status_response)
            self.assertEqual(status_response["cameraCount"], 2)
            self.assertEqual(status_response["diagnostics"]["issueCount"], 0)
            self.assertTrue(status_response["meshAvailable"])
            self.assertEqual(status_response["meshFormat"], "glb")
            self.assertEqual(status_response["meshUrl"], "/api/run/mesh.glb")
            self.assertEqual(status_response["meshResourceUrl"], "/api/run/mesh-assets/")

            cameras_response = cameras_endpoint("run")
            self.assertEqual(len(cameras_response["cameras"]), 2)
            self.assertEqual(cameras_response["cameras"][0]["thumbnailUrl"], "/api/run/thumb/0001.jpg")
            self.assertIn("pathIssueAfterPrevious", cameras_response["cameras"][0])

            points_response = points_endpoint("run")
            self.assertEqual(points_response.headers["x-vidtolevel-point-count"], "2")
            self.assertEqual(len(points_response.body), 30)

            error_points_response = points_endpoint("run", color_mode="error")
            self.assertEqual(error_points_response.headers["x-vidtolevel-color-mode"], "error")
            self.assertEqual(len(error_points_response.body), 30)

            mesh_response = mesh_endpoint("run", "glb")
            self.assertEqual(mesh_response.media_type, "model/gltf-binary")
            self.assertTrue(str(mesh_response.path).endswith("scene_dense_mesh_refine_texture.glb"))

            asset_response = mesh_asset_endpoint("run", "preview.bin")
            self.assertEqual(asset_response.media_type, "application/octet-stream")
            self.assertTrue(str(asset_response.path).endswith("preview.bin"))

    @unittest.skipIf(
        not (NUMPY_AVAILABLE and FASTAPI_AVAILABLE and CV2_AVAILABLE),
        "viewer thumbnail dependencies are not installed",
    )
    def test_viewer_thumbnail_endpoint_returns_cached_jpeg(self) -> None:
        import cv2
        import numpy as np

        from vidtolevel.viewer.server.api import create_viewer_app

        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            _write_sparse_model(run_root / "colmap" / "sparse" / "0")
            images_dir = run_root / "colmap" / "images"
            images_dir.mkdir(parents=True)
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            image[:, :, 1] = 180
            self.assertTrue(cv2.imwrite(str(images_dir / "0001.jpg"), image))

            app = create_viewer_app([run_root])
            thumbnail_endpoint = _endpoint(app, "/api/{project_id}/thumb/{image_name:path}")
            response = thumbnail_endpoint("run", "0001.jpg")

            self.assertEqual(response.media_type, "image/jpeg")
            self.assertIn(".vidtolevel_viewer", str(response.path))
            self.assertTrue(Path(response.path).exists())
            cached = cv2.imread(str(response.path))
            self.assertIsNotNone(cached)
            self.assertLessEqual(max(cached.shape[:2]), 320)

    def test_live_jobs_payload_reads_existing_database_only(self) -> None:
        from vidtolevel.core import db
        from vidtolevel.viewer.server.live import build_jobs_payload

        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "jobs.sqlite3"
            missing = Path(tmp) / "missing.sqlite3"

            empty_payload = build_jobs_payload(missing)
            self.assertEqual(empty_payload["jobs"], [])
            self.assertFalse(missing.exists())

            db.create_job(
                database,
                job_id="job-1",
                project="demo",
                video_path=Path("sample.mp4"),
                work_dir=Path("runs/job-1"),
            )
            db.update_job(database, job_id="job-1", status="running", message="run colmap")
            db.add_job_event(
                database,
                job_id="job-1",
                stage="sfm",
                event="started",
                message="run colmap",
                payload={"use_gpu": True},
            )

            payload = build_jobs_payload(database)
            self.assertEqual(payload["type"], "jobs")
            self.assertEqual(payload["jobs"][0]["id"], "job-1")
            self.assertEqual(payload["jobs"][0]["message"], "run colmap")
            self.assertEqual(payload["events"][0]["stage"], "sfm")
            self.assertTrue(payload["events"][0]["payload"]["use_gpu"])

    @unittest.skipIf(not (NUMPY_AVAILABLE and FASTAPI_AVAILABLE), "viewer dependencies are not installed")
    def test_discover_projects_treats_parent_folder_children_as_projects(self) -> None:
        from vidtolevel.viewer.server.api import discover_projects

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "runs"
            run_root = parent / "run_a"
            _write_sparse_model(run_root / "snapshots" / "sfm" / "0")
            images_dir = run_root / "colmap" / "images"
            images_dir.mkdir(parents=True)

            projects = discover_projects([parent])

            self.assertEqual(list(projects), ["run-a"])
            self.assertEqual(projects["run-a"].root, run_root.resolve())
            self.assertEqual(projects["run-a"].images_dir, images_dir.resolve())

    @unittest.skipIf(not (NUMPY_AVAILABLE and FASTAPI_AVAILABLE), "viewer dependencies are not installed")
    def test_discover_projects_uses_largest_sparse_model(self) -> None:
        from vidtolevel.viewer.server.api import discover_projects

        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            small = _write_sparse_model(run_root / "colmap" / "sparse" / "0", image_count=1)
            large = _write_sparse_model(run_root / "colmap" / "sparse" / "1", image_count=3)
            images_dir = run_root / "colmap" / "images"
            images_dir.mkdir(parents=True)

            projects = discover_projects([run_root])

            self.assertNotEqual(projects["run"].sparse_model, small.resolve())
            self.assertEqual(projects["run"].sparse_model, large.resolve())

    @unittest.skipIf(not NUMPY_AVAILABLE, "numpy is not installed")
    def test_sparse_snapshot_signature_tracks_model_file_changes(self) -> None:
        from vidtolevel.viewer.server.colmap_parser import read_sparse_model
        from vidtolevel.viewer.server.live import (
            SparseSnapshotState,
            build_sparse_snapshot_payload,
            sparse_model_signature,
            sparse_snapshot_diff,
        )

        with tempfile.TemporaryDirectory() as tmp:
            sparse = _write_sparse_model(Path(tmp) / "run" / "colmap" / "sparse" / "0")
            first = sparse_model_signature(sparse)
            self.assertIn("images.bin", first)

            model = read_sparse_model(sparse)
            payload = build_sparse_snapshot_payload(
                project_id="run",
                sparse_model=sparse,
                model=model,
            )
            self.assertEqual(payload["type"], "sparse_snapshot")
            self.assertEqual(payload["cameraCount"], 2)
            self.assertEqual(payload["pointCount"], 2)
            self.assertTrue(payload["diff"]["initial"])

            (sparse / "points3D.bin").write_bytes((sparse / "points3D.bin").read_bytes() + b" ")
            second = sparse_model_signature(sparse)
            self.assertNotEqual(first, second)

            diff = sparse_snapshot_diff(
                SparseSnapshotState("a", frozenset({1, 2}), frozenset({10, 11})),
                SparseSnapshotState("b", frozenset({2, 3}), frozenset({11, 12, 13})),
            )
            self.assertFalse(diff["initial"])
            self.assertEqual(diff["cameraCountDelta"], 0)
            self.assertEqual(diff["pointCountDelta"], 1)
            self.assertEqual(diff["addedCameraIds"], [3])
            self.assertEqual(diff["removedCameraIds"], [1])
            self.assertEqual(diff["addedPointCount"], 2)
            self.assertEqual(diff["removedPointCount"], 1)


def _write_sparse_model(path: Path, image_count: int = 2) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "cameras.bin").write_bytes(
        struct.pack("<Q", 1)
        + struct.pack("<iiQQ", 1, 1, 640, 480)
        + struct.pack("<dddd", 500.0, 500.0, 320.0, 240.0)
    )
    images = bytearray(struct.pack("<Q", image_count))
    for image_id in range(1, image_count + 1):
        images.extend(
            _image_record(
                image_id,
                (1.0, 0.0, 0.0, 0.0),
                (float(1 - image_id), 0.0, 0.0),
                f"{image_id:04d}.jpg",
                [1, -1] if image_id == 1 else [1],
            )
        )
    (path / "images.bin").write_bytes(bytes(images))
    second_track_image = min(2, image_count)
    (path / "points3D.bin").write_bytes(
        struct.pack("<Q", 2)
        + _point_record(1, (0.0, 0.0, 2.0), (255, 0, 0), 0.5, [(1, 0)])
        + _point_record(2, (1.0, 0.0, 2.0), (0, 255, 0), 0.7, [(second_track_image, 0)])
    )
    return path


def _write_obj_mesh(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "f 1 2 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_glb_mesh(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    positions = struct.pack("<fffffffff", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    indices = struct.pack("<HHH", 0, 1, 2)
    binary = positions + indices
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    payload = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {"attributes": {"POSITION": 0}, "indices": 1, "material": 0, "mode": 4}
                ]
            }
        ],
        "materials": [
            {
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.25, 0.85, 0.9, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(positions),
                "byteLength": len(indices),
                "target": 34963,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 0.0],
            },
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
    }
    json_chunk = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(binary), b"BIN\x00")
        + binary
    )
    return path


def _endpoint(app, path: str):
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"Route not found: {path}")


def _image_record(
    image_id: int,
    qvec: tuple[float, float, float, float],
    tvec: tuple[float, float, float],
    name: str,
    point_ids: list[int],
) -> bytes:
    payload = struct.pack("<idddddddi", image_id, *qvec, *tvec, 1)
    payload += name.encode("utf-8") + b"\x00"
    payload += struct.pack("<Q", len(point_ids))
    for idx, point_id in enumerate(point_ids):
        payload += struct.pack("<ddq", float(idx), float(idx), point_id)
    return payload


def _point_record(
    point_id: int,
    xyz: tuple[float, float, float],
    rgb: tuple[int, int, int],
    error: float,
    track: list[tuple[int, int]],
) -> bytes:
    payload = struct.pack("<QdddBBBd", point_id, *xyz, *rgb, error)
    payload += struct.pack("<Q", len(track))
    for image_id, point_idx in track:
        payload += struct.pack("<ii", image_id, point_idx)
    return payload


if __name__ == "__main__":
    unittest.main()
