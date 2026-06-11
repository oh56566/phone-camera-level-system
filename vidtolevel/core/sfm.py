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
    snapshot_path: str | None = None

    def to_dict(self) -> dict[str, float | int | str | None]:
        return asdict(self)


def _sparse_model_candidates(sparse_root: Path) -> list[Path]:
    return sorted(path for path in sparse_root.iterdir() if path.is_dir()) if sparse_root.exists() else []


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


def _analyze_sparse_models(
    *,
    colmap: str,
    sparse_root: Path,
    log_dir: Path,
) -> tuple[Path | None, int | None]:
    best_model: Path | None = None
    best_registered: int | None = None

    for candidate in _sparse_model_candidates(sparse_root):
        result = run_command(
            [colmap, "model_analyzer", "--path", str(candidate)],
            log_path=log_dir / f"colmap_model_analyzer_{candidate.name}.log",
            check=False,
        )
        registered = _parse_registered_images(result.output)
        best_score = best_registered if best_registered is not None else -1
        candidate_score = registered if registered is not None else -1
        if best_model is None or candidate_score > best_score:
            best_model = candidate
            best_registered = registered

    return best_model, best_registered


def _colmap_gpu_option(
    colmap: str,
    command: str,
    *,
    current_group: str,
    legacy_group: str,
    use_gpu: bool,
) -> list[str]:
    help_result = run_command([colmap, command, "-h"], check=False)
    current_option = f"--{current_group}.use_gpu"
    legacy_option = f"--{legacy_group}.use_gpu"
    option = current_option if current_option in help_result.output else legacy_option
    return [option, "1" if use_gpu else "0"]


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
    mapper_snapshot_path: Path | None = None,
    mapper_snapshot_frames_freq: int = 0,
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
        *_colmap_gpu_option(
            colmap,
            "feature_extractor",
            current_group="FeatureExtraction",
            legacy_group="SiftExtraction",
            use_gpu=use_gpu,
        ),
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
            *_colmap_gpu_option(
                colmap,
                "sequential_matcher",
                current_group="FeatureMatching",
                legacy_group="SiftMatching",
                use_gpu=use_gpu,
            ),
        ],
        log_path=log_dir / "colmap_sequential_matcher.log",
    )
    mapper_command = [
        colmap,
        "mapper",
        "--database_path",
        str(database_path),
        "--image_path",
        str(images_dir),
        "--output_path",
        str(sparse_dir),
    ]
    resolved_snapshot_path: Path | None = None
    if mapper_snapshot_path is not None and mapper_snapshot_frames_freq > 0:
        mapper_snapshot_path.mkdir(parents=True, exist_ok=True)
        resolved_snapshot_path = mapper_snapshot_path
        mapper_command.extend(
            [
                "--Mapper.snapshot_path",
                str(mapper_snapshot_path),
                "--Mapper.snapshot_frames_freq",
                str(mapper_snapshot_frames_freq),
            ]
        )
    run_command(mapper_command, log_path=log_dir / "colmap_mapper.log")

    sparse_model, registered_images = _analyze_sparse_models(
        colmap=colmap,
        sparse_root=sparse_dir,
        log_dir=log_dir,
    )

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
        snapshot_path=str(resolved_snapshot_path) if resolved_snapshot_path else None,
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
        *_colmap_gpu_option(
            colmap,
            "feature_extractor",
            current_group="FeatureExtraction",
            legacy_group="SiftExtraction",
            use_gpu=use_gpu,
        ),
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
                *_colmap_gpu_option(
                    colmap,
                    "vocab_tree_matcher",
                    current_group="FeatureMatching",
                    legacy_group="SiftMatching",
                    use_gpu=use_gpu,
                ),
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
                *_colmap_gpu_option(
                    colmap,
                    "sequential_matcher",
                    current_group="FeatureMatching",
                    legacy_group="SiftMatching",
                    use_gpu=use_gpu,
                ),
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
