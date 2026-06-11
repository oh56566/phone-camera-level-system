from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vidtolevel.core import db


class JobEventTests(unittest.TestCase):
    def test_job_events_are_listed_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "jobs.sqlite3"
            db.create_job(
                database,
                job_id="job-1",
                project="demo",
                video_path=Path("sample.mp4"),
                work_dir=Path("runs/job-1"),
            )
            db.add_job_event(
                database,
                job_id="job-1",
                stage="frames",
                event="started",
                message="extract frames",
                payload={"fps": 1},
            )
            db.add_job_event(
                database,
                job_id="job-1",
                stage="frames",
                event="done",
                message="frames filtered",
                payload={"accepted_count": 12},
            )

            events = db.list_job_events(database)

            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "done")
            self.assertEqual(events[0]["payload"]["accepted_count"], 12)
            self.assertEqual(events[1]["payload"]["fps"], 1)


if __name__ == "__main__":
    unittest.main()
