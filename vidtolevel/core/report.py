from __future__ import annotations

from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value * 100:.1f}%"


def quality_findings(stats: dict[str, Any]) -> list[str]:
    findings: list[str] = []

    frames = stats.get("frames", {})
    extracted = int(frames.get("extracted_count") or 0)
    accepted = int(frames.get("accepted_count") or 0)
    if extracted and accepted / extracted < 0.5:
        findings.append(
            "Accepted frame ratio is below 50%. Re-shoot with slower motion or stronger AE/AF lock."
        )

    sfm = stats.get("sfm", {})
    registered_ratio = sfm.get("registered_ratio")
    if isinstance(registered_ratio, int | float) and registered_ratio < 0.6:
        findings.append(
            "COLMAP registered less than 60% of session frames. Increase overlap and add a loop closure pass."
        )
    if sfm.get("registered_images") in (None, 0):
        findings.append("Sparse reconstruction did not report registered images. Inspect COLMAP logs.")

    mvs = stats.get("mvs", {})
    if mvs.get("resolution_level", 1) != 1:
        findings.append("OpenMVS fell back to a lower resolution level after memory pressure.")

    if not findings:
        findings.append("No blocking quality issue was detected from available pipeline statistics.")
    return findings


def write_quality_report(
    *,
    report_path: Path,
    title: str,
    stats: dict[str, Any],
    work_dir: Path,
) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    frames = stats.get("frames", {})
    sfm = stats.get("sfm", {})
    mvs = stats.get("mvs", {})
    optimize = stats.get("optimize", {})

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Work directory: `{work_dir}`",
        f"- Extracted frames: {frames.get('extracted_count', 'unknown')}",
        f"- Accepted frames: {frames.get('accepted_count', 'unknown')}",
        f"- Rejected blur frames: {frames.get('rejected_blur_count', 'unknown')}",
        f"- Rejected duplicate frames: {frames.get('rejected_duplicate_count', 'unknown')}",
        f"- Registered image ratio: {_pct(sfm.get('registered_ratio'))}",
        f"- Sparse model: `{sfm.get('sparse_model', 'unknown')}`",
        f"- MVS resolution level: {mvs.get('resolution_level', 'not run')}",
        f"- Textured mesh: `{mvs.get('textured_mesh_path', 'not run')}`",
        f"- Optimized FBX: `{optimize.get('output_fbx', 'not run')}`",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in quality_findings(stats))
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

