from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vidtolevel.core.tools import which


class ToolDiscoveryTests(unittest.TestCase):
    def test_openmvs_env_bin_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = Path(tmp) / "InterfaceCOLMAP"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

            with patch.dict(os.environ, {"VIDTOLEVEL_OPENMVS_BIN": tmp}, clear=False):
                self.assertEqual(which("InterfaceCOLMAP"), str(tool))

    def test_configured_dir_uses_pathext_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool = Path(tmp) / "colmap.EXE"
            tool.write_text("", encoding="utf-8")
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

            with (
                patch("vidtolevel.core.tools.os.name", "nt"),
                patch.dict(os.environ, {"VIDTOLEVEL_TOOL_PATHS": tmp, "PATHEXT": ".EXE"}, clear=False),
            ):
                self.assertEqual(which("colmap"), str(tool))

    def test_local_versioned_tool_dir_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp) / ".tools" / "ffmpeg" / "ffmpeg-test" / "bin"
            tool_dir.mkdir(parents=True)
            tool = tool_dir / "ffmpeg"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

            with patch("vidtolevel.core.tools.Path.cwd", return_value=Path(tmp)):
                self.assertEqual(which("ffmpeg"), str(tool))


if __name__ == "__main__":
    unittest.main()
