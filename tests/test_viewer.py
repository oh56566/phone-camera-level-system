from __future__ import annotations

import importlib.util
import math
import struct
import tempfile
import unittest
from pathlib import Path

NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None
FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
REPO_ROOT = Path(__file__).resolve().parents[1]


class ViewerParserTests(unittest.TestCase):
    def test_viewer_static_assets_are_local(self) -> None:
        index = (REPO_ROOT / "vidtolevel" / "viewer" / "web" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('"/assets/vendor/three.module.js"', index)
        self.assertIn('"/assets/vendor/examples/jsm/"', index)
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
            projects = discover_projects([run_root])

            self.assertEqual(list(projects), ["run"])

            app = create_viewer_app([run_root])
            project_endpoint = _endpoint(app, "/api/projects")
            cameras_endpoint = _endpoint(app, "/api/{project_id}/cameras")
            points_endpoint = _endpoint(app, "/api/{project_id}/points")

            project_response = project_endpoint()
            self.assertEqual(project_response[0]["id"], "run")

            cameras_response = cameras_endpoint("run")
            self.assertEqual(len(cameras_response["cameras"]), 2)
            self.assertEqual(cameras_response["cameras"][0]["thumbnailUrl"], "/api/run/thumb/0001.jpg")

            points_response = points_endpoint("run")
            self.assertEqual(points_response.headers["x-vidtolevel-point-count"], "2")
            self.assertEqual(len(points_response.body), 30)

            error_points_response = points_endpoint("run", color_mode="error")
            self.assertEqual(error_points_response.headers["x-vidtolevel-color-mode"], "error")
            self.assertEqual(len(error_points_response.body), 30)


def _write_sparse_model(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "cameras.bin").write_bytes(
        struct.pack("<Q", 1)
        + struct.pack("<iiQQ", 1, 1, 640, 480)
        + struct.pack("<dddd", 500.0, 500.0, 320.0, 240.0)
    )
    (path / "images.bin").write_bytes(
        struct.pack("<Q", 2)
        + _image_record(1, (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0), "0001.jpg", [1, -1])
        + _image_record(2, (1.0, 0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), "0002.jpg", [1])
    )
    (path / "points3D.bin").write_bytes(
        struct.pack("<Q", 2)
        + _point_record(1, (0.0, 0.0, 2.0), (255, 0, 0), 0.5, [(1, 0)])
        + _point_record(2, (1.0, 0.0, 2.0), (0, 255, 0), 0.7, [(2, 0)])
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
