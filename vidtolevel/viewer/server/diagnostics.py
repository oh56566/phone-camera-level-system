from __future__ import annotations

import math
from statistics import median
from typing import Any


def annotate_camera_path(cameras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each camera with path quality information against the previous camera."""

    if not cameras:
        return cameras

    distances = [
        _distance(cameras[index - 1]["position"], cameras[index]["position"])
        for index in range(1, len(cameras))
    ]
    observed_counts = [int(camera.get("registeredPointCount") or 0) for camera in cameras]
    median_distance = median(distances) if distances else 0.0
    median_observed = median(observed_counts) if observed_counts else 0.0

    cameras[0]["pathDistanceFromPrevious"] = 0.0
    cameras[0]["pathIssueAfterPrevious"] = False
    cameras[0]["pathIssueReasons"] = []

    for index in range(1, len(cameras)):
        distance = distances[index - 1]
        reasons: list[str] = []
        if median_distance > 0 and distance > median_distance * 2.5:
            reasons.append("large_gap")
        previous_observed = int(cameras[index - 1].get("registeredPointCount") or 0)
        current_observed = int(cameras[index].get("registeredPointCount") or 0)
        if median_observed > 0 and min(previous_observed, current_observed) < median_observed * 0.35:
            reasons.append("weak_observations")

        cameras[index]["pathDistanceFromPrevious"] = distance
        cameras[index]["pathIssueAfterPrevious"] = bool(reasons)
        cameras[index]["pathIssueReasons"] = reasons

    return cameras


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(
        (float(a[0]) - float(b[0])) ** 2
        + (float(a[1]) - float(b[1])) ** 2
        + (float(a[2]) - float(b[2])) ** 2
    )

