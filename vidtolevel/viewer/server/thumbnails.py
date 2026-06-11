from __future__ import annotations

import hashlib
from pathlib import Path


def cached_thumbnail_path(
    *,
    project_root: Path,
    source_path: Path,
    max_size: int = 320,
) -> Path:
    stat = source_path.stat()
    key = hashlib.sha256(
        f"{source_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}:{max_size}".encode("utf-8")
    ).hexdigest()[:24]
    return project_root / ".vidtolevel_viewer" / "thumbs" / f"{key}.jpg"


def build_cached_thumbnail(
    *,
    project_root: Path,
    source_path: Path,
    max_size: int = 320,
    jpeg_quality: int = 82,
) -> Path:
    """Create a bounded JPEG thumbnail and return the cached path."""

    cache_path = cached_thumbnail_path(
        project_root=project_root,
        source_path=source_path,
        max_size=max_size,
    )
    if cache_path.exists():
        return cache_path

    import cv2

    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image for thumbnail: {source_path}")

    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions for thumbnail: {source_path}")

    scale = min(float(max_size) / float(width), float(max_size) / float(height), 1.0)
    if scale < 1.0:
        resized = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        resized = image

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(
        str(cache_path),
        resized,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
    )
    if not ok:
        raise ValueError(f"Could not write thumbnail cache file: {cache_path}")
    return cache_path

