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


if __name__ == "__main__":
    unittest.main()
