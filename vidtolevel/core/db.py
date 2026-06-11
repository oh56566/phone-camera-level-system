from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
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

CREATE TABLE IF NOT EXISTS job_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  event TEXT NOT NULL,
  message TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id_event_id
ON job_events (job_id, event_id DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def managed_connection(db_path: Path):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_job(
    db_path: Path,
    *,
    job_id: str,
    project: str | None,
    video_path: Path,
    work_dir: Path,
) -> None:
    now = utc_now()
    with managed_connection(db_path) as conn:
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
    with managed_connection(db_path) as conn:
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


def add_job_event(
    db_path: Path,
    *,
    job_id: str,
    stage: str,
    event: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    with managed_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO job_events
              (job_id, stage, event, message, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                stage,
                event,
                message,
                json.dumps(payload or {}, sort_keys=True, ensure_ascii=False),
                utc_now(),
            ),
        )


def list_jobs(db_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    with managed_connection(db_path) as conn:
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


def list_job_events(
    db_path: Path,
    *,
    job_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if job_id is None:
        query = """
            SELECT event_id, job_id, stage, event, message, payload_json, created_at
            FROM job_events
            ORDER BY event_id DESC
            LIMIT ?
            """
        params: tuple[Any, ...] = (limit,)
    else:
        query = """
            SELECT event_id, job_id, stage, event, message, payload_json, created_at
            FROM job_events
            WHERE job_id = ?
            ORDER BY event_id DESC
            LIMIT ?
            """
        params = (job_id, limit)

    with managed_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        events.append(item)
    return events


def get_job(db_path: Path, job_id: str) -> dict[str, Any] | None:
    with managed_connection(db_path) as conn:
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
