from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np


@dataclass(frozen=True)
class CameraModel:
    id: int
    name: str
    param_count: int


CAMERA_MODELS: dict[int, CameraModel] = {
    0: CameraModel(0, "SIMPLE_PINHOLE", 3),
    1: CameraModel(1, "PINHOLE", 4),
    2: CameraModel(2, "SIMPLE_RADIAL", 4),
    3: CameraModel(3, "RADIAL", 5),
    4: CameraModel(4, "OPENCV", 8),
    5: CameraModel(5, "OPENCV_FISHEYE", 8),
    6: CameraModel(6, "FULL_OPENCV", 12),
    7: CameraModel(7, "FOV", 5),
    8: CameraModel(8, "SIMPLE_RADIAL_FISHEYE", 4),
    9: CameraModel(9, "RADIAL_FISHEYE", 5),
    10: CameraModel(10, "THIN_PRISM_FISHEYE", 12),
}


@dataclass(frozen=True)
class ColmapCamera:
    camera_id: int
    model_id: int
    model_name: str
    width: int
    height: int
    params: tuple[float, ...]

    @property
    def focal_lengths(self) -> tuple[float, float]:
        if self.model_name == "PINHOLE":
            return self.params[0], self.params[1]
        if self.model_name in {"OPENCV", "OPENCV_FISHEYE", "FULL_OPENCV", "THIN_PRISM_FISHEYE"}:
            return self.params[0], self.params[1]
        focal = self.params[0]
        return focal, focal

    @property
    def fov(self) -> tuple[float, float]:
        fx, fy = self.focal_lengths
        if fx <= 0 or fy <= 0:
            return math.radians(60.0), math.radians(45.0)
        return (
            2.0 * math.atan(float(self.width) / (2.0 * fx)),
            2.0 * math.atan(float(self.height) / (2.0 * fy)),
        )


@dataclass(frozen=True)
class ColmapImage:
    image_id: int
    qvec: tuple[float, float, float, float]
    tvec: tuple[float, float, float]
    camera_id: int
    name: str
    point3d_ids: tuple[int, ...]

    @property
    def registered_point_count(self) -> int:
        return sum(1 for point_id in self.point3d_ids if point_id != -1)

    @property
    def rotation_world_to_camera(self) -> np.ndarray:
        return qvec_to_rotmat(np.array(self.qvec, dtype=np.float64))

    @property
    def rotation_camera_to_world(self) -> np.ndarray:
        return self.rotation_world_to_camera.T

    @property
    def center(self) -> np.ndarray:
        r_cw = self.rotation_world_to_camera
        t = np.array(self.tvec, dtype=np.float64)
        return -r_cw.T @ t


@dataclass(frozen=True)
class ColmapPoint3D:
    point3d_id: int
    xyz: tuple[float, float, float]
    rgb: tuple[int, int, int]
    error: float
    track: tuple[tuple[int, int], ...]

    @property
    def track_length(self) -> int:
        return len(self.track)


@dataclass(frozen=True)
class SparseModel:
    path: Path
    cameras: dict[int, ColmapCamera]
    images: dict[int, ColmapImage]
    points3d: dict[int, ColmapPoint3D]


def qvec_to_rotmat(qvec: np.ndarray) -> np.ndarray:
    qw, qx, qy, qz = qvec
    return np.array(
        [
            [
                1.0 - 2.0 * qy * qy - 2.0 * qz * qz,
                2.0 * qx * qy - 2.0 * qw * qz,
                2.0 * qz * qx + 2.0 * qw * qy,
            ],
            [
                2.0 * qx * qy + 2.0 * qw * qz,
                1.0 - 2.0 * qz * qz - 2.0 * qx * qx,
                2.0 * qy * qz - 2.0 * qw * qx,
            ],
            [
                2.0 * qz * qx - 2.0 * qw * qy,
                2.0 * qy * qz + 2.0 * qw * qx,
                1.0 - 2.0 * qx * qx - 2.0 * qy * qy,
            ],
        ],
        dtype=np.float64,
    )


def _read(fid: BinaryIO, fmt: str) -> tuple:
    size = struct.calcsize(fmt)
    data = fid.read(size)
    if len(data) != size:
        raise EOFError("Unexpected end of COLMAP binary model.")
    return struct.unpack(fmt, data)


def _read_c_string(fid: BinaryIO) -> str:
    name = bytearray()
    while True:
        char = fid.read(1)
        if char == b"":
            raise EOFError("Unexpected end of COLMAP image name.")
        if char == b"\x00":
            return name.decode("utf-8", errors="replace")
        name.extend(char)


def read_cameras_binary(path: Path) -> dict[int, ColmapCamera]:
    cameras: dict[int, ColmapCamera] = {}
    with path.open("rb") as fid:
        (count,) = _read(fid, "<Q")
        for _ in range(count):
            camera_id, model_id, width, height = _read(fid, "<iiQQ")
            model = CAMERA_MODELS.get(model_id)
            if model is None:
                raise ValueError(f"Unsupported COLMAP camera model id: {model_id}")
            params = _read(fid, "<" + "d" * model.param_count)
            cameras[camera_id] = ColmapCamera(
                camera_id=camera_id,
                model_id=model_id,
                model_name=model.name,
                width=int(width),
                height=int(height),
                params=tuple(float(value) for value in params),
            )
    return cameras


def read_images_binary(path: Path) -> dict[int, ColmapImage]:
    images: dict[int, ColmapImage] = {}
    with path.open("rb") as fid:
        (count,) = _read(fid, "<Q")
        for _ in range(count):
            payload = _read(fid, "<idddddddi")
            image_id = int(payload[0])
            qvec = tuple(float(value) for value in payload[1:5])
            tvec = tuple(float(value) for value in payload[5:8])
            camera_id = int(payload[8])
            name = _read_c_string(fid)
            (point_count,) = _read(fid, "<Q")
            point3d_ids: list[int] = []
            for _point_idx in range(point_count):
                _x, _y, point3d_id = _read(fid, "<ddq")
                point3d_ids.append(int(point3d_id))
            images[image_id] = ColmapImage(
                image_id=image_id,
                qvec=qvec,
                tvec=tvec,
                camera_id=camera_id,
                name=name,
                point3d_ids=tuple(point3d_ids),
            )
    return images


def read_points3d_binary(path: Path) -> dict[int, ColmapPoint3D]:
    points: dict[int, ColmapPoint3D] = {}
    with path.open("rb") as fid:
        (count,) = _read(fid, "<Q")
        for _ in range(count):
            point_id, x, y, z, r, g, b, error = _read(fid, "<QdddBBBd")
            (track_length,) = _read(fid, "<Q")
            track = tuple((int(image_id), int(point_idx)) for image_id, point_idx in (_read(fid, "<ii") for _ in range(track_length)))
            points[int(point_id)] = ColmapPoint3D(
                point3d_id=int(point_id),
                xyz=(float(x), float(y), float(z)),
                rgb=(int(r), int(g), int(b)),
                error=float(error),
                track=track,
            )
    return points


def read_sparse_model(model_path: Path) -> SparseModel:
    path = model_path.resolve()
    required = ["cameras.bin", "images.bin", "points3D.bin"]
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing COLMAP sparse model files in {path}: {missing_list}")
    return SparseModel(
        path=path,
        cameras=read_cameras_binary(path / "cameras.bin"),
        images=read_images_binary(path / "images.bin"),
        points3d=read_points3d_binary(path / "points3D.bin"),
    )


def model_bounds(points: dict[int, ColmapPoint3D], images: dict[int, ColmapImage]) -> dict[str, list[float]]:
    coords: list[np.ndarray] = [np.array(point.xyz, dtype=np.float64) for point in points.values()]
    coords.extend(image.center for image in images.values())
    if not coords:
        return {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0], "center": [0.5, 0.5, 0.5]}
    matrix = np.vstack(coords)
    min_xyz = matrix.min(axis=0)
    max_xyz = matrix.max(axis=0)
    center = (min_xyz + max_xyz) / 2.0
    return {
        "min": [float(value) for value in min_xyz],
        "max": [float(value) for value in max_xyz],
        "center": [float(value) for value in center],
    }
