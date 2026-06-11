from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from vidtolevel.core.checkpoint import utc_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  project TEXT,
  video_path TEXT NOT NULL,
  work_dir TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT,
  stats_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def create_job(
    db_path: Path,
    *,
    job_id: str,
    project: str | None,
    video_path: Path,
    work_dir: Path,
) -> None:
    now = utc_now()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs
              (id, project, video_path, work_dir, status, message, stats_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                project,
                str(video_path),
                str(work_dir),
                "queued",
                None,
                "{}",
                now,
                now,
            ),
        )


def update_job(
    db_path: Path,
    *,
    job_id: str,
    status: str,
    message: str | None = None,
    stats: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    with connect(db_path) as conn:
        if stats is None:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, message = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, message, now, job_id),
            )
        else:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, message = ?, stats_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, message, json.dumps(stats, sort_keys=True), now, job_id),
            )


def list_jobs(db_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, project, video_path, work_dir, status, message, stats_json, created_at, updated_at
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    jobs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["stats"] = json.loads(item.pop("stats_json") or "{}")
        jobs.append(item)
    return jobs


def get_job(db_path: Path, job_id: str) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, project, video_path, work_dir, status, message, stats_json, created_at, updated_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["stats"] = json.loads(item.pop("stats_json") or "{}")
    return item
