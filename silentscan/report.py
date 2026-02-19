import json
from datetime import datetime, timezone
from pathlib import Path


def group_by_session(silent_files: list[dict], root: Path) -> list[dict]:
    """
    Group silent files by their immediate parent directory relative to root.
    Each group represents a logical session or subfolder.
    """
    sessions: dict[str, list[dict]] = {}

    for file in silent_files:
        file_path = Path(file["path"])

        # Use the parent directory as the session key
        session_path = str(file_path.parent)
        if session_path not in sessions:
            sessions[session_path] = []
        sessions[session_path].append(file)

    return [
        {
            "session_path": session_path,
            "silent_file_count": len(files),
            "silent_files": files,
        }
        for session_path, files in sorted(sessions.items())
    ]


def build_report(
    root: Path,
    silent_files: list[dict],
    total_scanned: int,
    threshold_db: float,
    duration_seconds: float,
) -> dict:
    """
    Build the full report dictionary.

    Args:
        root: The root directory that was scanned.
        silent_files: List of silent file dicts from scanner.py.
        total_scanned: Total number of audio files scanned.
        threshold_db: The silence threshold used during the scan.
        duration_seconds: How long the scan took.

    Returns:
        A dict representing the full scan report.
    """
    total_silent_size = sum(f["size_bytes"] for f in silent_files)

    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "root_path": str(root),
        "threshold_db": threshold_db,
        "scan_duration_seconds": round(duration_seconds, 2),
        "total_files_scanned": total_scanned,
        "total_silent_files": len(silent_files),
        "total_silent_size_bytes": total_silent_size,
        "sessions": group_by_session(silent_files, root),
    }


def write_report(report: dict, output_path: Path) -> None:
    """Write the report dict to a JSON file at output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def read_report(report_path: Path) -> dict:
    """Read and parse a report JSON file."""
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def format_duration(seconds: float | None) -> str:
    """Human-readable duration string."""
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def summarize_report(report: dict) -> str:
    """
    Return a human-readable summary string of the report,
    suitable for printing to the terminal.
    """
    lines = [
        "",
        "── Scan Complete ──────────────────────────────────────",
        f"  Root          {report['root_path']}",
        f"  Scanned at    {report['scanned_at']}",
        f"  Scan took     {format_duration(report['scan_duration_seconds'])}",
        f"  Threshold     {report['threshold_db']} dBFS",
        "────────────────────────────────────────────────────────",
        f"  Files scanned   {report['total_files_scanned']}",
        f"  Silent files    {report['total_silent_files']}",
        f"  Reclaimable     {format_size(report['total_silent_size_bytes'])}",
        "────────────────────────────────────────────────────────",
    ]

    for session in report["sessions"]:
        lines.append(f"\n  {session['session_path']}")
        lines.append(f"  {session['silent_file_count']} silent file(s)")
        for f in session["silent_files"]:
            name = Path(f["path"]).name
            size = format_size(f["size_bytes"])
            duration = format_duration(f.get("duration_seconds"))
            lines.append(f"    · {name}  ({size}, {duration})")

    lines.append("")
    return "\n".join(lines)