from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vidtolevel.core.mvs import run_openmvs
from vidtolevel.core.tools import CommandResult


class MvsCommandTests(unittest.TestCase):
    def test_openmvs_uses_undistorted_colmap_workspace_and_mesh_file_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            colmap_workspace = root / "colmap"
            sparse = colmap_workspace / "sparse" / "0"
            images = colmap_workspace / "images"
            logs = root / "logs"
            output = root / "openmvs"
            sparse.mkdir(parents=True)
            images.mkdir()
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (sparse / name).write_bytes(b"bin")

            calls: list[tuple[list[str], Path | None]] = []

            def fake_run(command, **kwargs):
                command_list = list(command)
                cwd = kwargs.get("cwd")
                calls.append((command_list, cwd))
                if command_list[1] == "image_undistorter":
                    dense = Path(command_list[command_list.index("--output_path") + 1])
                    (dense / "images").mkdir(parents=True)
                    (dense / "sparse").mkdir()
                elif command_list[0] == "InterfaceCOLMAP":
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"scene")
                elif command_list[0] == "DensifyPointCloud":
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"dense")
                elif command_list[0] == "ReconstructMesh":
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"mesh")
                elif command_list[0] == "RefineMesh":
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"refined")
                elif command_list[0] == "TextureMesh":
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"obj")
                return CommandResult(command=command_list, returncode=0, output="")

            with patch("vidtolevel.core.mvs.run_command", side_effect=fake_run):
                stats = run_openmvs(
                    colmap="colmap",
                    interface_colmap="InterfaceCOLMAP",
                    densify_point_cloud="DensifyPointCloud",
                    reconstruct_mesh="ReconstructMesh",
                    refine_mesh="RefineMesh",
                    texture_mesh="TextureMesh",
                    colmap_workspace=colmap_workspace,
                    output_dir=output,
                    log_dir=logs,
                )

            dense_workspace = output / "colmap_dense"
            commands = [command for command, _ in calls]
            self.assertEqual(commands[0][1], "image_undistorter")
            self.assertIn(str(sparse), commands[0])
            self.assertEqual(commands[1][0], "InterfaceCOLMAP")
            self.assertEqual(commands[1][commands[1].index("--image-folder") + 1], "images")
            self.assertEqual(commands[2][0], "DensifyPointCloud")
            self.assertEqual(commands[3][0], "ReconstructMesh")
            self.assertEqual(commands[4][0], "RefineMesh")
            self.assertIn("-m", commands[4])
            self.assertEqual(commands[5][0], "TextureMesh")
            self.assertIn("-m", commands[5])
            self.assertTrue(all(cwd == dense_workspace for _, cwd in calls[1:]))
            self.assertEqual(stats.textured_mesh_path, str(dense_workspace / "scene_dense_mesh_refine_texture.obj"))

    def test_openmvs_fallback_uses_largest_sparse_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            colmap_workspace = root / "colmap"
            small_sparse = colmap_workspace / "sparse" / "0"
            large_sparse = colmap_workspace / "sparse" / "1"
            images = colmap_workspace / "images"
            logs = root / "logs"
            output = root / "openmvs"
            images.mkdir(parents=True)
            for sparse, size in ((small_sparse, 1), (large_sparse, 64)):
                sparse.mkdir(parents=True)
                (sparse / "cameras.bin").write_bytes(b"bin")
                (sparse / "images.bin").write_bytes(b"x" * size)
                (sparse / "points3D.bin").write_bytes(b"bin")

            commands: list[list[str]] = []

            def fake_run(command, **kwargs):
                command_list = list(command)
                commands.append(command_list)
                cwd = kwargs.get("cwd")
                if command_list[1] == "image_undistorter":
                    dense = Path(command_list[command_list.index("--output_path") + 1])
                    (dense / "images").mkdir(parents=True)
                    (dense / "sparse").mkdir()
                elif "-o" in command_list and cwd is not None:
                    (cwd / command_list[command_list.index("-o") + 1]).write_bytes(b"out")
                return CommandResult(command=command_list, returncode=0, output="")

            with patch("vidtolevel.core.mvs.run_command", side_effect=fake_run):
                run_openmvs(
                    colmap="colmap",
                    interface_colmap="InterfaceCOLMAP",
                    densify_point_cloud="DensifyPointCloud",
                    reconstruct_mesh="ReconstructMesh",
                    refine_mesh="RefineMesh",
                    texture_mesh="TextureMesh",
                    colmap_workspace=colmap_workspace,
                    output_dir=output,
                    log_dir=logs,
                )

            undistort_command = commands[0]
            self.assertEqual(
                undistort_command[undistort_command.index("--input_path") + 1],
                str(large_sparse),
            )


if __name__ == "__main__":
    unittest.main()
