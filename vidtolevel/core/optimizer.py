from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path

from vidtolevel.core.tools import run_command


@dataclass(frozen=True)
class OptimizeStats:
    output_fbx: str
    target_faces: int
    collision_mode: str

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def run_blender_optimize(
    *,
    blender: str,
    input_mesh: Path,
    output_fbx: Path,
    log_dir: Path,
    target_faces: int = 500_000,
    collision_mode: str = "ground-slab",
) -> OptimizeStats:
    output_fbx.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    script_path = files("vidtolevel.optimize").joinpath("blender_optimize.py")
    run_command(
        [
            blender,
            "--background",
            "--python",
            str(script_path),
            "--",
            "--input",
            str(input_mesh),
            "--output",
            str(output_fbx),
            "--target-faces",
            str(target_faces),
            "--collision-mode",
            collision_mode,
        ],
        log_path=log_dir / "blender_optimize.log",
    )
    return OptimizeStats(
        output_fbx=str(output_fbx),
        target_faces=target_faces,
        collision_mode=collision_mode,
    )
