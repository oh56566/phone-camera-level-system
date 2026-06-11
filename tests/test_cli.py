from __future__ import annotations

import unittest

from vidtolevel.cli.main import build_parser


class CliParserTests(unittest.TestCase):
    def test_parser_accepts_process_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["process", "sample.mp4", "--fps", "2"])
        self.assertEqual(args.video, "sample.mp4")
        self.assertEqual(args.fps, 2)

    def test_parser_accepts_project_session_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["add-session", "sample.mp4", "--project", "projects/demo", "--skip-mvs"]
        )
        self.assertEqual(args.video, "sample.mp4")
        self.assertEqual(args.project, "projects/demo")
        self.assertTrue(args.skip_mvs)

    def test_parser_accepts_viewer_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["viewer", "runs", "projects", "--no-open"])
        self.assertEqual(args.paths, ["runs", "projects"])
        self.assertFalse(args.open_browser)

    def test_process_defaults_to_ground_slab_collision(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["process", "sample.mp4"])
        self.assertEqual(args.collision_mode, "ground-slab")

    def test_process_accepts_mapper_snapshot_frequency(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["process", "sample.mp4", "--mapper-snapshot-frames-freq", "10"])
        self.assertEqual(args.mapper_snapshot_frames_freq, 10)


if __name__ == "__main__":
    unittest.main()
