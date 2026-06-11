from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from vidtolevel.core.tools import run_command


@dataclass(frozen=True)
class SfmStats:
    total_images: int
    registered_images: int | None
    registered_ratio: float | None
    sparse_model: str | None

    def to_dict(self) -> dict[str, float | int | str | None]:
        return asdict(self)


def _first_sparse_model(sparse_root: Path) -> Path | None:
    candidates = sorted(path for path in sparse_root.iterdir() if path.is_dir()) if sparse_root.exists() else []
    return candidates[0] if candidates else None


def _parse_registered_images(text: str) -> int | None:
    patterns = [
        r"Registered images:\s*(\d+)",
        r"Images:\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def run_new_reconstruction(
    *,
    colmap: str,
    images_dir: Path,
    database_path: Path,
    sparse_dir: Path,
    log_dir: Path,
    camera_model: str = "OPENCV",
    single_camera: bool = True,
    use_gpu: bool = True,
    image_list_path: Path | None = None,
) -> SfmStats:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    feature_command = [
        colmap,
        "feature_extractor",
        "--database_path",
        str(database_path),
        "--image_path",
        str(images_dir),
        "--ImageReader.camera_model",
        camera_model,
        "--ImageReader.single_camera",
        "1" if single_camera else "0",
        "--SiftExtraction.use_gpu",
        "1" if use_gpu else "0",
    ]
    if image_list_path:
        feature_command.extend(["--image_list_path", str(image_list_path)])
    run_command(feature_command, log_path=log_dir / "colmap_feature_extractor.log")
    run_command(
        [
            colmap,
            "sequential_matcher",
            "--database_path",
            str(database_path),
            "--SequentialMatching.loop_detection",
            "1",
            "--SiftMatching.use_gpu",
            "1" if use_gpu else "0",
        ],
        log_path=log_dir / "colmap_sequential_matcher.log",
    )
    run_command(
        [
            colmap,
            "mapper",
            "--database_path",
            str(database_path),
            "--image_path",
            str(images_dir),
            "--output_path",
            str(sparse_dir),
        ],
        log_path=log_dir / "colmap_mapper.log",
    )

    sparse_model = _first_sparse_model(sparse_dir)
    registered_images: int | None = None
    if sparse_model:
        result = run_command(
            [colmap, "model_analyzer", "--path", str(sparse_model)],
            log_path=log_dir / "colmap_model_analyzer.log",
            check=False,
        )
        registered_images = _parse_registered_images(result.output)

    total_images = (
        len([line for line in image_list_path.read_text(encoding="utf-8").splitlines() if line.strip()])
        if image_list_path
        else len(sorted(images_dir.rglob("*.jpg")))
    )
    ratio = registered_images / total_images if registered_images is not None and total_images else None
    return SfmStats(
        total_images=total_images,
        registered_images=registered_images,
        registered_ratio=ratio,
        sparse_model=str(sparse_model) if sparse_model else None,
    )


def register_incremental_session(
    *,
    colmap: str,
    images_dir: Path,
    database_path: Path,
    existing_sparse_model: Path,
    output_sparse_model: Path,
    log_dir: Path,
    vocab_tree_path: Path | None = None,
    use_gpu: bool = True,
    image_list_path: Path | None = None,
) -> SfmStats:
    """Register new images against an existing COLMAP sparse model."""

    log_dir.mkdir(parents=True, exist_ok=True)
    output_sparse_model.parent.mkdir(parents=True, exist_ok=True)
    if output_sparse_model.exists():
        shutil.rmtree(output_sparse_model)

    feature_command = [
        colmap,
        "feature_extractor",
        "--database_path",
        str(database_path),
        "--image_path",
        str(images_dir),
        "--ImageReader.camera_model",
        "OPENCV",
        "--ImageReader.single_camera",
        "1",
        "--SiftExtraction.use_gpu",
        "1" if use_gpu else "0",
    ]
    if image_list_path:
        feature_command.extend(["--image_list_path", str(image_list_path)])
    run_command(feature_command, log_path=log_dir / "colmap_incremental_feature_extractor.log")

    if vocab_tree_path:
        run_command(
            [
                colmap,
                "vocab_tree_matcher",
                "--database_path",
                str(database_path),
                "--VocabTreeMatching.vocab_tree_path",
                str(vocab_tree_path),
                "--SiftMatching.use_gpu",
                "1" if use_gpu else "0",
            ],
            log_path=log_dir / "colmap_vocab_tree_matcher.log",
        )
    else:
        run_command(
            [
                colmap,
                "sequential_matcher",
                "--database_path",
                str(database_path),
                "--SequentialMatching.loop_detection",
                "1",
                "--SiftMatching.use_gpu",
                "1" if use_gpu else "0",
            ],
            log_path=log_dir / "colmap_incremental_sequential_matcher.log",
        )

    run_command(
        [
            colmap,
            "image_registrator",
            "--database_path",
            str(database_path),
            "--input_path",
            str(existing_sparse_model),
            "--output_path",
            str(output_sparse_model),
        ],
        log_path=log_dir / "colmap_image_registrator.log",
    )

    bundle_output = output_sparse_model.parent / f"{output_sparse_model.name}_ba"
    if bundle_output.exists():
        shutil.rmtree(bundle_output)
    run_command(
        [
            colmap,
            "bundle_adjuster",
            "--input_path",
            str(output_sparse_model),
            "--output_path",
            str(bundle_output),
        ],
        log_path=log_dir / "colmap_bundle_adjuster.log",
    )
    if output_sparse_model.exists():
        shutil.rmtree(output_sparse_model)
    shutil.move(str(bundle_output), str(output_sparse_model))

    result = run_command(
        [colmap, "model_analyzer", "--path", str(output_sparse_model)],
        log_path=log_dir / "colmap_incremental_model_analyzer.log",
        check=False,
    )
    registered_images = _parse_registered_images(result.output)
    total_images = (
        len([line for line in image_list_path.read_text(encoding="utf-8").splitlines() if line.strip()])
        if image_list_path
        else len(sorted(images_dir.rglob("*.jpg")))
    )
    ratio = registered_images / total_images if registered_images is not None and total_images else None
    return SfmStats(
        total_images=total_images,
        registered_images=registered_images,
        registered_ratio=ratio,
        sparse_model=str(output_sparse_model),
    )
