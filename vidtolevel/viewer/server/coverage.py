from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from vidtolevel.viewer.server.colmap_parser import ColmapPoint3D


@dataclass(frozen=True)
class CoverageCell:
    x: int
    z: int
    point_count: int
    average_track_length: float
    average_error: float


def compute_topdown_coverage(
    points: list[ColmapPoint3D],
    *,
    cell_size: float = 0.5,
) -> dict[str, object]:
    buckets: dict[tuple[int, int], list[ColmapPoint3D]] = defaultdict(list)
    for point in points:
        x, _y, z = point.xyz
        buckets[(int(x // cell_size), int(z // cell_size))].append(point)

    cells: list[CoverageCell] = []
    for (x, z), bucket in sorted(buckets.items()):
        cells.append(
            CoverageCell(
                x=x,
                z=z,
                point_count=len(bucket),
                average_track_length=sum(point.track_length for point in bucket) / len(bucket),
                average_error=sum(point.error for point in bucket) / len(bucket),
            )
        )

    return {
        "cellSize": cell_size,
        "cells": [cell.__dict__ for cell in cells],
    }
