from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from vidtolevel.core.project import active_sparse_model, init_project
from vidtolevel.core.tools import run_command, which


@dataclass(frozen=True)
class Point3D:
    point_id: int
    x: float
    y: float
    z: float
    error: float
    track_length: int


@dataclass(frozen=True)
class CoverageStats:
    point_count: int
    occupied_cells: int
    total_cells: int
    cell_size: float
    bounds: dict[str, float]
    csv_path: str
    svg_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_points3d_text(path: Path) -> list[Point3D]:
    points: list[Point3D] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        track_values = parts[8:]
        points.append(
            Point3D(
                point_id=int(parts[0]),
                x=float(parts[1]),
                y=float(parts[2]),
                z=float(parts[3]),
                error=float(parts[7]),
                track_length=len(track_values) // 2,
            )
        )
    return points


def parse_points3d_binary(path: Path) -> list[Point3D]:
    from vidtolevel.viewer.server.colmap_parser import read_points3d_binary

    binary_points = read_points3d_binary(path)
    return [
        Point3D(
            point_id=point.point3d_id,
            x=point.xyz[0],
            y=point.xyz[1],
            z=point.xyz[2],
            error=point.error,
            track_length=point.track_length,
        )
        for point in binary_points.values()
    ]


def export_model_text(model_path: Path, output_dir: Path, *, colmap: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    points_txt = output_dir / "points3D.txt"
    if points_txt.exists():
        return points_txt
    resolved_colmap = colmap or which("colmap")
    if not resolved_colmap:
        raise FileNotFoundError(
            f"{model_path} does not contain points3D.txt and colmap is not on PATH for model conversion."
        )
    run_command(
        [
            resolved_colmap,
            "model_converter",
            "--input_path",
            str(model_path),
            "--output_path",
            str(output_dir),
            "--output_type",
            "TXT",
        ],
        log_path=output_dir / "colmap_model_converter.log",
    )
    if not points_txt.exists():
        raise FileNotFoundError(f"COLMAP conversion did not create {points_txt}")
    return points_txt


def _axis_value(point: Point3D, axis: str) -> float:
    return getattr(point, axis)


def _bounds(values: Iterable[float]) -> tuple[float, float]:
    collected = list(values)
    return min(collected), max(collected)


def _color(value: int, max_value: int) -> str:
    if max_value <= 0 or value <= 0:
        return "#f3f4f6"
    ratio = min(1.0, math.log1p(value) / math.log1p(max_value))
    red = int(40 + ratio * 215)
    green = int(170 - ratio * 120)
    blue = int(220 - ratio * 170)
    return f"#{red:02x}{green:02x}{blue:02x}"


def build_coverage_grid(
    points: list[Point3D],
    *,
    cell_size: float = 1.0,
    axes: tuple[str, str] = ("x", "y"),
) -> tuple[list[list[int]], dict[str, float]]:
    if not points:
        raise ValueError("No sparse points available for coverage.")
    x_min, x_max = _bounds(_axis_value(point, axes[0]) for point in points)
    y_min, y_max = _bounds(_axis_value(point, axes[1]) for point in points)
    width = max(1, int(math.ceil((x_max - x_min) / cell_size)) + 1)
    height = max(1, int(math.ceil((y_max - y_min) / cell_size)) + 1)
    grid = [[0 for _ in range(width)] for _ in range(height)]
    for point in points:
        gx = int((_axis_value(point, axes[0]) - x_min) / cell_size)
        gy = int((_axis_value(point, axes[1]) - y_min) / cell_size)
        grid[gy][gx] += 1
    bounds = {
        f"{axes[0]}_min": x_min,
        f"{axes[0]}_max": x_max,
        f"{axes[1]}_min": y_min,
        f"{axes[1]}_max": y_max,
    }
    return grid, bounds


def write_grid_csv(path: Path, grid: list[list[int]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(reversed(grid))
    return path


def write_grid_svg(path: Path, grid: list[list[int]], *, cell_px: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    height = len(grid)
    width = len(grid[0]) if height else 0
    max_value = max((value for row in grid for value in row), default=0)
    rects: list[str] = []
    for y, row in enumerate(reversed(grid)):
        for x, value in enumerate(row):
            rects.append(
                f'<rect x="{x * cell_px}" y="{y * cell_px}" width="{cell_px}" '
                f'height="{cell_px}" fill="{_color(value, max_value)}" />'
            )
    svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * cell_px}" height="{height * cell_px}" viewBox="0 0 {width * cell_px} {height * cell_px}">',
            *rects,
            "</svg>",
        ]
    )
    path.write_text(svg, encoding="utf-8")
    return path


def generate_project_coverage(
    project_root: Path,
    *,
    cell_size: float = 1.0,
    axes: tuple[str, str] = ("x", "y"),
    colmap: str | None = None,
) -> CoverageStats:
    paths = init_project(project_root)
    model = active_sparse_model(project_root)
    if not model:
        raise FileNotFoundError(f"No active sparse model found under {paths.sparse}")
    points_txt = model / "points3D.txt"
    points_bin = model / "points3D.bin"
    if points_txt.exists():
        points = parse_points3d_text(points_txt)
    elif points_bin.exists():
        points = parse_points3d_binary(points_bin)
    else:
        converted_points = export_model_text(model, paths.coverage / "model_text", colmap=colmap)
        points = parse_points3d_text(converted_points)
    grid, bounds = build_coverage_grid(points, cell_size=cell_size, axes=axes)
    csv_path = write_grid_csv(paths.coverage / "coverage.csv", grid)
    svg_path = write_grid_svg(paths.coverage / "coverage.svg", grid)
    occupied = sum(1 for row in grid for value in row if value > 0)
    stats = CoverageStats(
        point_count=len(points),
        occupied_cells=occupied,
        total_cells=sum(len(row) for row in grid),
        cell_size=cell_size,
        bounds=bounds,
        csv_path=str(csv_path),
        svg_path=str(svg_path),
    )
    (paths.coverage / "coverage.json").write_text(
        json.dumps(stats.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return stats
