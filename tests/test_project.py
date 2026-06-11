from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vidtolevel.core.project import active_sparse_model, append_session, init_project, load_metadata


class ProjectTests(unittest.TestCase):
    def test_init_project_creates_expected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            paths = init_project(root)
            self.assertTrue(paths.images.is_dir())
            self.assertTrue(paths.sparse.is_dir())
            self.assertTrue(paths.sparse_versions.is_dir())
            self.assertTrue(paths.sessions.is_dir())
            self.assertTrue(paths.meshes.is_dir())
            self.assertTrue(paths.coverage.is_dir())
            self.assertTrue(paths.reports.is_dir())
            self.assertTrue(paths.metadata.exists())
            self.assertIsNone(active_sparse_model(root))

    def test_append_session_updates_metadata_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            init_project(root)
            append_session(root, "s1", Path("a.mp4"), {"frames": {"accepted_count": 3}})
            append_session(root, "s1", Path("b.mp4"), {"frames": {"accepted_count": 4}})
            metadata = load_metadata(root)
            self.assertEqual(len(metadata["sessions"]), 1)
            self.assertEqual(metadata["sessions"][0]["video_path"], "b.mp4")


if __name__ == "__main__":
    unittest.main()

