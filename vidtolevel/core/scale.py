from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkerDetection:
    image_path: str
    marker_id: int
    corner_pixels: list[list[float]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_aruco_markers(frames_dir: Path, *, dictionary_name: str = "DICT_4X4_50") -> list[MarkerDetection]:
    import cv2

    aruco = cv2.aruco
    dictionary_id = getattr(aruco, dictionary_name)
    dictionary = aruco.getPredefinedDictionary(dictionary_id)
    parameters = aruco.DetectorParameters()
    detector = aruco.ArucoDetector(dictionary, parameters)

    detections: list[MarkerDetection] = []
    for image_path in sorted(frames_dir.glob("*.jpg")):
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        corners, ids, _ = detector.detectMarkers(image)
        if ids is None:
            continue
        for marker_corners, marker_id in zip(corners, ids.flatten(), strict=False):
            detections.append(
                MarkerDetection(
                    image_path=str(image_path),
                    marker_id=int(marker_id),
                    corner_pixels=marker_corners.reshape(4, 2).astype(float).tolist(),
                )
            )
    return detections
