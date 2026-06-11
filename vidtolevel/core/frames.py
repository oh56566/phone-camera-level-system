from __future__ import annotations

import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from vidtolevel.core.tools import run_command


@dataclass(frozen=True)
class FrameFilterStats:
    extracted_count: int
    accepted_count: int
    rejected_blur_count: int
    rejected_duplicate_count: int
    blur_threshold: float
    blur_percentile: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def extract_frames(
    video_path: Path,
    output_dir: Path,
    *,
    fps: float = 2.0,
    ffmpeg: str = "ffmpeg",
    log_path: Path | None = None,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "%06d.jpg"
    command = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "2",
        str(pattern),
    ]
    run_command(command, log_path=log_path)
    return len(sorted(output_dir.glob("*.jpg")))


def laplacian_variance(image_path: Path) -> float:
    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def _signature(image_path: Path, size: int = 64):
    import cv2
    import numpy as np

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    resized = cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)
    vector = resized.astype(np.float32).reshape(-1)
    vector -= float(vector.mean())
    norm = float(np.linalg.norm(vector))
    if math.isclose(norm, 0.0):
        return vector
    return vector / norm


def _cosine(a, b) -> float:
    import numpy as np

    return float(np.dot(a, b))


def filter_frames(
    extracted_dir: Path,
    accepted_dir: Path,
    rejected_dir: Path,
    *,
    blur_percentile: float = 15.0,
    duplicate_threshold: float = 0.985,
) -> FrameFilterStats:
    import numpy as np
    from tqdm import tqdm

    frames = sorted(extracted_dir.glob("*.jpg"))
    accepted_dir.mkdir(parents=True, exist_ok=True)
    rejected_blur = rejected_dir / "blur"
    rejected_duplicate = rejected_dir / "duplicate"
    rejected_blur.mkdir(parents=True, exist_ok=True)
    rejected_duplicate.mkdir(parents=True, exist_ok=True)

    if not frames:
        return FrameFilterStats(0, 0, 0, 0, 0.0, blur_percentile)

    blur_scores = [(frame, laplacian_variance(frame)) for frame in tqdm(frames, desc="blur")]
    threshold = float(np.percentile([score for _, score in blur_scores], blur_percentile))

    accepted_count = 0
    rejected_blur_count = 0
    rejected_duplicate_count = 0
    previous_signature = None

    for frame, blur_score in tqdm(blur_scores, desc="filter"):
        if blur_score < threshold:
            shutil.copy2(frame, rejected_blur / frame.name)
            rejected_blur_count += 1
            continue

        signature = _signature(frame)
        if previous_signature is not None and _cosine(signature, previous_signature) > duplicate_threshold:
            shutil.copy2(frame, rejected_duplicate / frame.name)
            rejected_duplicate_count += 1
            continue

        shutil.copy2(frame, accepted_dir / frame.name)
        previous_signature = signature
        accepted_count += 1

    return FrameFilterStats(
        extracted_count=len(frames),
        accepted_count=accepted_count,
        rejected_blur_count=rejected_blur_count,
        rejected_duplicate_count=rejected_duplicate_count,
        blur_threshold=threshold,
        blur_percentile=blur_percentile,
    )
