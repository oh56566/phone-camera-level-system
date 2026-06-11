from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vidtolevel.core.sfm import run_new_reconstruction
from vidtolevel.core.tools import CommandResult


class SfmCommandTests(unittest.TestCase):
    def test_mapper_snapshot_options_are_added_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "0001.jpg").write_bytes(b"jpg")
            (images / "0002.jpg").write_bytes(b"jpg")
            sparse = root / "sparse"
            commands: list[list[str]] = []

            def fake_run(command, **kwargs):
                command_list = list(command)
                commands.append(command_list)
                if command_list[1] == "mapper":
                    (sparse / "0").mkdir(parents=True)
                output = "Registered images: 2" if command_list[1] == "model_analyzer" else ""
                return CommandResult(command=command_list, returncode=0, output=output)

            with patch("vidtolevel.core.sfm.run_command", side_effect=fake_run):
                stats = run_new_reconstruction(
                    colmap="colmap",
                    images_dir=images,
                    database_path=root / "database.db",
                    sparse_dir=sparse,
                    log_dir=root / "logs",
                    mapper_snapshot_path=root / "snapshots" / "sfm",
                    mapper_snapshot_frames_freq=10,
                )

            mapper_command = next(command for command in commands if command[1] == "mapper")
            self.assertIn("--Mapper.snapshot_path", mapper_command)
            self.assertIn("--Mapper.snapshot_frames_freq", mapper_command)
            self.assertIn("10", mapper_command)
            self.assertEqual(stats.snapshot_path, str(root / "snapshots" / "sfm"))

    def test_colmap_four_gpu_option_names_are_used_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            (images / "0001.jpg").write_bytes(b"jpg")
            sparse = root / "sparse"
            commands: list[list[str]] = []

            def fake_run(command, **kwargs):
                command_list = list(command)
                commands.append(command_list)
                if command_list == ["colmap", "feature_extractor", "-h"]:
                    return CommandResult(command=command_list, returncode=0, output="--FeatureExtraction.use_gpu")
                if command_list == ["colmap", "sequential_matcher", "-h"]:
                    return CommandResult(command=command_list, returncode=0, output="--FeatureMatching.use_gpu")
                if command_list[1] == "mapper":
                    (sparse / "0").mkdir(parents=True)
                output = "Registered images: 1" if command_list[1] == "model_analyzer" else ""
                return CommandResult(command=command_list, returncode=0, output=output)

            with patch("vidtolevel.core.sfm.run_command", side_effect=fake_run):
                run_new_reconstruction(
                    colmap="colmap",
                    images_dir=images,
                    database_path=root / "database.db",
                    sparse_dir=sparse,
                    log_dir=root / "logs",
                )

            feature_command = next(
                command for command in commands if command[1] == "feature_extractor" and "-h" not in command
            )
            matcher_command = next(
                command for command in commands if command[1] == "sequential_matcher" and "-h" not in command
            )
            self.assertIn("--FeatureExtraction.use_gpu", feature_command)
            self.assertIn("--FeatureMatching.use_gpu", matcher_command)

    def test_largest_colmap_reconstruction_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            images.mkdir()
            for index in range(4):
                (images / f"{index:04d}.jpg").write_bytes(b"jpg")
            sparse = root / "sparse"

            def fake_run(command, **kwargs):
                command_list = list(command)
                if command_list[1] == "mapper":
                    (sparse / "0").mkdir(parents=True)
                    (sparse / "1").mkdir(parents=True)
                output = ""
                if command_list[1] == "model_analyzer":
                    output = (
                        "Registered images: 4"
                        if Path(command_list[-1]).name == "1"
                        else "Registered images: 2"
                    )
                return CommandResult(command=command_list, returncode=0, output=output)

            with patch("vidtolevel.core.sfm.run_command", side_effect=fake_run):
                stats = run_new_reconstruction(
                    colmap="colmap",
                    images_dir=images,
                    database_path=root / "database.db",
                    sparse_dir=sparse,
                    log_dir=root / "logs",
                )

            self.assertEqual(stats.sparse_model, str(sparse / "1"))
            self.assertEqual(stats.registered_images, 4)
            self.assertEqual(stats.registered_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
