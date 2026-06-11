from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from vidtolevel.core.tools import output_contains_oom, run_command


@dataclass(frozen=True)
class MvsStats:
    resolution_level: int
    scene_path: str
    dense_scene_path: str
    textured_mesh_path: str

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def run_openmvs(
    *,
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

    scene = output_dir / "scene.mvs"
    dense_scene = output_dir / "scene_dense.mvs"
    mesh_scene = output_dir / "scene_dense_mesh.mvs"
    refined_scene = output_dir / "scene_dense_mesh_refine.mvs"
    textured_scene = output_dir / "scene_dense_mesh_refine_texture.mvs"
    textured_obj = output_dir / "scene_dense_mesh_refine_texture.obj"
    resolved_image_folder = image_folder or (colmap_workspace / "images")

    run_command(
        [
            interface_colmap,
            "-i",
            str(colmap_workspace),
            "-o",
            str(scene),
            "--image-folder",
            str(resolved_image_folder),
        ],
        log_path=log_dir / "openmvs_interface_colmap.log",
    )

    active_level = resolution_level
    densify = run_command(
        [
            densify_point_cloud,
            str(scene),
            "--resolution-level",
            str(active_level),
            "-o",
            str(dense_scene),
        ],
        log_path=log_dir / "openmvs_densify.log",
        check=False,
    )
    if densify.returncode != 0:
        if output_contains_oom(densify.output):
            active_level = fallback_resolution_level
            densify = run_command(
                [
                    densify_point_cloud,
                    str(scene),
                    "--resolution-level",
                    str(active_level),
                    "-o",
                    str(dense_scene),
                ],
                log_path=log_dir / "openmvs_densify_retry.log",
            )
        else:
            from vidtolevel.core.tools import ToolError

            raise ToolError(densify.command, densify.returncode, densify.output[-4000:])

    run_command(
        [reconstruct_mesh, str(dense_scene), "-o", str(mesh_scene)],
        log_path=log_dir / "openmvs_reconstruct_mesh.log",
    )
    run_command(
        [refine_mesh, str(mesh_scene), "-o", str(refined_scene)],
        log_path=log_dir / "openmvs_refine_mesh.log",
    )
    run_command(
        [
            texture_mesh,
            str(refined_scene),
            "--export-type",
            "obj",
            "-o",
            str(textured_scene),
        ],
        log_path=log_dir / "openmvs_texture_mesh.log",
    )

    return MvsStats(
        resolution_level=active_level,
        scene_path=str(scene),
        dense_scene_path=str(dense_scene),
        textured_mesh_path=str(textured_obj if textured_obj.exists() else textured_scene),
    )
