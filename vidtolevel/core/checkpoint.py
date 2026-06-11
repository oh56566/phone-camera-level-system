from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Checkpoint:
    path: Path
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Checkpoint":
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(path=path, stages=data.get("stages", {}))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"stages": self.stages, "updated_at": utc_now()}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def done(self, stage: str) -> bool:
        return self.stages.get(stage, {}).get("status") == "done"

    def start(self, stage: str, **extra: Any) -> None:
        self.stages[stage] = {
            "status": "running",
            "started_at": utc_now(),
            **extra,
        }
        self.save()

    def finish(self, stage: str, **extra: Any) -> None:
        current = self.stages.get(stage, {})
        self.stages[stage] = {
            **current,
            "status": "done",
            "finished_at": utc_now(),
            **extra,
        }
        self.save()

    def fail(self, stage: str, message: str, **extra: Any) -> None:
        current = self.stages.get(stage, {})
        self.stages[stage] = {
            **current,
            "status": "failed",
            "failed_at": utc_now(),
            "message": message,
            **extra,
        }
        self.save()

