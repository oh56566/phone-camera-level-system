from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class ToolError(RuntimeError):
    """Raised when an external command fails."""

    def __init__(self, command: Sequence[str], returncode: int, tail: str) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.tail = tail
        super().__init__(
            f"Command failed with exit code {returncode}: {' '.join(command)}\n{tail}"
        )


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    output: str
    log_path: Path | None = None


def which(name: str) -> str | None:
    return shutil.which(name)


def require_tool(name: str) -> str:
    resolved = which(name)
    if not resolved:
        raise FileNotFoundError(
            f"Required tool '{name}' was not found on PATH. Install it or add it to PATH."
        )
    return resolved


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    log_path: Path | None = None,
    check: bool = True,
) -> CommandResult:
    """Run a command, mirror combined output to an optional log, and return it."""

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)

    output_parts: list[str] = []
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    log_file = log_path.open("w", encoding="utf-8") if log_path else None
    try:
        assert process.stdout is not None
        for line in process.stdout:
            output_parts.append(line)
            if log_file:
                log_file.write(line)
                log_file.flush()
        returncode = process.wait()
    finally:
        if log_file:
            log_file.close()

    output = "".join(output_parts)
    if check and returncode != 0:
        raise ToolError(command, returncode, output[-4000:])

    return CommandResult(
        command=list(command),
        returncode=returncode,
        output=output,
        log_path=log_path,
    )


def output_contains_oom(text: str) -> bool:
    lower = text.lower()
    needles = [
        "out of memory",
        "cuda error 2",
        "cuda_error_out_of_memory",
        "std::bad_alloc",
    ]
    return any(needle in lower for needle in needles)

