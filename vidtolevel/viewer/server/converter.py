from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable

from vidtolevel.viewer.server.colmap_parser import ColmapImage, ColmapPoint3D


POINT_BINARY_MIME = "application/vnd.vidtolevel.points+binary"
POINT_BINARY_STRIDE = 15
POINT_COLOR_MODES = {"rgb", "error", "track", "session"}


def pack_points_binary(
    points: Iterable[ColmapPoint3D],
    *,
    limit: int | None = None,
    color_mode: str = "rgb",
    images: dict[int, ColmapImage] | None = None,
) -> tuple[bytes, int]:
    """Pack sparse points as repeated little-endian x/y/z float32 + r/g/b uint8."""

    if color_mode not in POINT_COLOR_MODES:
        raise ValueError(f"Unsupported point color mode: {color_mode}")

    collected = list(points)
    if limit is not None:
        collected = collected[:limit]
    colors = _point_colors(collected, color_mode=color_mode, images=images or {})
    buffer = bytearray()
    for point, color in zip(collected, colors, strict=False):
        buffer.extend(struct.pack("<fffBBB", *point.xyz, *color))
    return bytes(buffer), len(collected)


def _point_colors(
    points: list[ColmapPoint3D],
    *,
    color_mode: str,
    images: dict[int, ColmapImage],
) -> list[tuple[int, int, int]]:
    if color_mode == "rgb":
        return [point.rgb for point in points]

    if color_mode == "error":
        max_error = max((point.error for point in points), default=1.0)
        return [_heat_color(point.error / max(max_error, 1e-9), invert=True) for point in points]

    if color_mode == "track":
        max_track = max((point.track_length for point in points), default=1)
        return [
            _heat_color(point.track_length / max(max_track, 1), invert=False)
            for point in points
        ]

    return [_session_color(_point_session(point, images)) for point in points]


def _heat_color(value: float, *, invert: bool) -> tuple[int, int, int]:
    ratio = max(0.0, min(1.0, value))
    if invert:
        ratio = 1.0 - ratio
    red = int(238 - ratio * 162)
    green = int(106 + ratio * 95)
    blue = int(95 + ratio * 81)
    return red, green, blue


def _point_session(point: ColmapPoint3D, images: dict[int, ColmapImage]) -> str:
    if not point.track:
        return "unknown"
    image = images.get(point.track[0][0])
    if image is None:
        return "unknown"
    return image.name.split("/", 1)[0] if "/" in image.name else "root"


def _session_color(session: str) -> tuple[int, int, int]:
    palette = [
        (76, 201, 176),
        (232, 168, 79),
        (238, 106, 95),
        (112, 161, 255),
        (180, 136, 255),
        (134, 211, 91),
        (255, 126, 182),
        (240, 222, 93),
    ]
    value = sum((index + 1) * ord(char) for index, char in enumerate(session))
    return palette[value % len(palette)]


def find_first_sparse_model(root: Path) -> Path | None:
    root = root.resolve()
    direct = find_direct_sparse_model(root)
    if direct is not None:
        return direct

    sparse_root = root / "colmap" / "sparse"
    if sparse_root.exists():
        for candidate in sorted(path for path in sparse_root.iterdir() if path.is_dir()):
            if _is_sparse_model(candidate):
                return candidate

    if root.exists():
        for candidate in sorted(root.glob("**/cameras.bin")):
            model_path = candidate.parent
            if _is_sparse_model(model_path):
                return model_path
    return None


def find_direct_sparse_model(root: Path) -> Path | None:
    root = root.resolve()
    if _is_sparse_model(root):
        return root

    direct_candidates = [
        root / "colmap" / "sparse" / "0",
        root / "sparse" / "0",
        root / "sparse",
    ]
    for candidate in direct_candidates:
        if _is_sparse_model(candidate):
            return candidate
    return None


def find_images_dir(root: Path, sparse_model: Path) -> Path | None:
    candidates = [
        root / "colmap" / "images",
        root / "images",
        sparse_model.parent.parent / "images",
        sparse_model.parent / "images",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    return None


def find_mesh_file(root: Path) -> Path | None:
    candidates = [
        root / "openmvs" / "scene_dense_mesh_refine_texture.obj",
        root / "openmvs" / "scene_dense_mesh_refine.obj",
        root / "output" / f"{root.name}.obj",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    search_roots = [
        root / "openmvs",
        root / "output",
        root / "meshes",
    ]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for candidate in sorted(search_root.rglob("*.obj")):
            if candidate.is_file():
                return candidate.resolve()
    return None


def _is_sparse_model(path: Path) -> bool:
    return all((path / name).exists() for name in ("cameras.bin", "images.bin", "points3D.bin"))
