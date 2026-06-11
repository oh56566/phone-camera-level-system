from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vidtolevel.core.coverage import build_coverage_grid, parse_points3d_text, write_grid_csv


class CoverageTests(unittest.TestCase):
    def test_parse_points3d_text_and_grid(self) -> None:
        text = "\n".join(
            [
                "# POINT3D_ID X Y Z R G B ERROR TRACK[]",
                "1 0.0 0.0 0.0 255 0 0 0.2 1 2 3 4",
                "2 1.1 0.2 0.0 0 255 0 0.3 1 2",
                "3 1.9 1.1 0.0 0 0 255 0.4 1 2",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            points_path = Path(tmp) / "points3D.txt"
            points_path.write_text(text, encoding="utf-8")
            points = parse_points3d_text(points_path)
            grid, bounds = build_coverage_grid(points, cell_size=1.0, axes=("x", "y"))
            csv_path = write_grid_csv(Path(tmp) / "coverage.csv", grid)
            self.assertEqual(len(points), 3)
            self.assertEqual(sum(sum(row) for row in grid), 3)
            self.assertEqual(bounds["x_min"], 0.0)
            self.assertTrue(csv_path.exists())


if __name__ == "__main__":
    unittest.main()

