from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


OPENMVS_TOOL_NAMES = {
    "InterfaceCOLMAP",
    "DensifyPointCloud",
    "ReconstructMesh",
    "RefineMesh",
    "TextureMesh",
}


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
    explicit = _which_in_configured_dirs(name)
    if explicit:
        return explicit

    resolved = shutil.which(name)
    if resolved:
        return resolved

    return _which_in_local_tool_dirs(name)


def require_tool(name: str) -> str:
    resolved = which(name)
    if not resolved:
        raise FileNotFoundError(
            f"Required tool '{name}' was not found on PATH. Install it or add it to PATH."
        )
    return resolved


def _which_in_configured_dirs(name: str) -> str | None:
    directories: list[Path] = []
    if name in OPENMVS_TOOL_NAMES:
        openmvs_bin = os.environ.get("VIDTOLEVEL_OPENMVS_BIN")
        if openmvs_bin:
            directories.append(Path(openmvs_bin))

    tool_paths = os.environ.get("VIDTOLEVEL_TOOL_PATHS")
    if tool_paths:
        directories.extend(Path(entry) for entry in tool_paths.split(os.pathsep) if entry)

    return _first_executable(name, directories)


def _which_in_local_tool_dirs(name: str) -> str | None:
    package_root = Path(__file__).resolve().parents[2]
    roots = [Path.cwd(), package_root]
    directories = _dedupe_paths(
        directory
        for root in roots
        for directory in _local_tool_dirs(root, name)
    )
    local = _first_executable(name, directories)
    if local:
        return local

    return _first_executable(name, _common_windows_tool_dirs(name))


def _local_tool_dirs(root: Path, name: str) -> list[Path]:
    tool_root = root / ".tools" / _local_tool_group(name)
    directories = [tool_root / "bin"]
    if tool_root.exists():
        directories.extend(sorted(path for path in tool_root.glob("*/bin") if path.is_dir()))
    return directories


def _local_tool_group(name: str) -> str:
    return "openmvs" if name in OPENMVS_TOOL_NAMES else name.lower()


def _common_windows_tool_dirs(name: str) -> list[Path]:
    if os.name != "nt":
        return []

    directories: list[Path] = []
    if name == "blender":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            program_files = os.environ.get(env_name)
            if not program_files:
                continue
            blender_root = Path(program_files) / "Blender Foundation"
            if blender_root.exists():
                directories.extend(sorted(path for path in blender_root.glob("Blender *") if path.is_dir()))
    return directories


def _first_executable(name: str, directories: Sequence[Path]) -> str | None:
    names = _candidate_names(name)
    for directory in directories:
        for candidate_name in names:
            candidate = directory / candidate_name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def _candidate_names(name: str) -> list[str]:
    if Path(name).suffix or os.name != "nt":
        return [name]

    extensions = [
        extension
        for extension in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep)
        if extension
    ]
    return [name, *(f"{name}{extension}" for extension in extensions)]


def _dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve() if path.exists() else path.absolute())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


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
