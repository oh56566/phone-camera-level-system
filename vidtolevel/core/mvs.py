from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from vidtolevel.core.tools import output_contains_oom, run_command


@dataclass(frozen=True)
class MvsStats:
    resolution_level: int
    undistorted_workspace: str
    scene_path: str
    dense_scene_path: str
    mesh_path: str
    refined_mesh_path: str
    textured_mesh_path: str

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def run_openmvs(
    *,
    colmap: str,
    interface_colmap: str,
    densify_point_cloud: str,
    reconstruct_mesh: str,
    refine_mesh: str,
    texture_mesh: str,
    colmap_workspace: Path,
    output_dir: Path,
    log_dir: Path,
    image_folder: Path | None = None,
    resolution_level: int = 1,
    fallback_resolution_level: int = 2,
) -> MvsStats:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    resolved_image_folder = image_folder or (colmap_workspace / "images")
    sparse_model = _first_sparse_model(colmap_workspace)
    if sparse_model is None:
        raise FileNotFoundError(f"No COLMAP sparse model found under: {colmap_workspace}")

    dense_workspace = output_dir / "colmap_dense"
    scene = dense_workspace / "scene.mvs"
    dense_scene = dense_workspace / "scene_dense.mvs"
    mesh_ply = dense_workspace / "scene_dense_mesh.ply"
    refined_ply = dense_workspace / "scene_dense_mesh_refine.ply"
    textured_obj = dense_workspace / "scene_dense_mesh_refine_texture.obj"

    run_command(
        [
            colmap,
            "image_undistorter",
            "--image_path",
            str(resolved_image_folder),
            "--input_path",
            str(sparse_model),
            "--output_path",
            str(dense_workspace),
            "--output_type",
            "COLMAP",
        ],
        log_path=log_dir / "colmap_image_undistorter.log",
    )

    run_command(
        [
            interface_colmap,
            "-i",
            str(dense_workspace),
            "-o",
            scene.name,
            "--image-folder",
            "images",
        ],
        cwd=dense_workspace,
        log_path=log_dir / "openmvs_interface_colmap.log",
    )

    active_level = resolution_level
    densify = run_command(
        [
            densify_point_cloud,
            scene.name,
            "--resolution-level",
            str(active_level),
            "-o",
            dense_scene.name,
        ],
        cwd=dense_workspace,
        log_path=log_dir / "openmvs_densify.log",
        check=False,
    )
    if densify.returncode != 0:
        if output_contains_oom(densify.output):
            active_level = fallback_resolution_level
            densify = run_command(
                [
                    densify_point_cloud,
                    scene.name,
                    "--resolution-level",
                    str(active_level),
                    "-o",
                    dense_scene.name,
                ],
                cwd=dense_workspace,
                log_path=log_dir / "openmvs_densify_retry.log",
            )
        else:
            from vidtolevel.core.tools import ToolError

            raise ToolError(densify.command, densify.returncode, densify.output[-4000:])

    run_command(
        [reconstruct_mesh, dense_scene.name, "-o", mesh_ply.name],
        cwd=dense_workspace,
        log_path=log_dir / "openmvs_reconstruct_mesh.log",
    )
    run_command(
        [
            refine_mesh,
            dense_scene.name,
            "-m",
            mesh_ply.name,
            "--resolution-level",
            str(active_level),
            "-o",
            refined_ply.name,
        ],
        cwd=dense_workspace,
        log_path=log_dir / "openmvs_refine_mesh.log",
    )
    run_command(
        [
            texture_mesh,
            dense_scene.name,
            "-m",
            refined_ply.name,
            "--export-type",
            "obj",
            "-o",
            textured_obj.name,
        ],
        cwd=dense_workspace,
        log_path=log_dir / "openmvs_texture_mesh.log",
    )

    return MvsStats(
        resolution_level=active_level,
        undistorted_workspace=str(dense_workspace),
        scene_path=str(scene),
        dense_scene_path=str(dense_scene),
        mesh_path=str(mesh_ply),
        refined_mesh_path=str(refined_ply),
        textured_mesh_path=str(textured_obj),
    )


def _first_sparse_model(colmap_workspace: Path) -> Path | None:
    candidates = [
        colmap_workspace / "sparse" / "0",
        colmap_workspace / "sparse",
        colmap_workspace / "colmap" / "sparse" / "0",
    ]
    for candidate in candidates:
        if _is_sparse_model(candidate):
            return candidate

    sparse_root = colmap_workspace / "sparse"
    if sparse_root.exists():
        for candidate in sorted(path for path in sparse_root.iterdir() if path.is_dir()):
            if _is_sparse_model(candidate):
                return candidate
    return None


def _is_sparse_model(path: Path) -> bool:
    return all((path / name).exists() for name in ("cameras.bin", "images.bin", "points3D.bin"))
