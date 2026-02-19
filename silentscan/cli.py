import time
from pathlib import Path

import click

from silentscan.scanner import (
    SUPPORTED_EXTENSIONS,
    is_silent,
    get_duration,
    scan_directory, 
    DEFAULT_SILENCE_THRESHOLD_DB
)
from silentscan.report import (
    build_report, 
    write_report, 
    read_report, 
    summarize_report, 
    format_size,
    format_duration,
    )
from silentscan.cleaner import run_clean

def get_reports_dir() -> Path:
    """Return platform-appropriate directory for storing silentscan reports."""
    app_dir = click.get_app_dir("silentscan", force_posix=False)
    reports_dir = Path(app_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True) 
    return reports_dir

def get_default_report_path(root: Path) -> Path:
    """Generate a default report filename based on the scanned root folder name."""
    return get_reports_dir() / f"{root.name}.silentscan.json"

def load_all_reports() -> list[tuple[Path, dict]]:
    """
    Load all .silentscan.json reports from the central reports directory.
    Returns a list of (path, report_dict) tuples sorted by scan date descending.
    """
    reports_dir = get_reports_dir()
    report_files = sorted(reports_dir.glob("*.silentscan.json"), reverse=True)
    results = []
    for report_file in report_files:
        try:
            results.append((report_file, read_report(report_path)))
        except Exception:
            click.echo(f"  ⚠  Could not read report: {report_path.name}")
    return results


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0", prog_name="silentscan")
def cli():
    """
    silentscan — find and remove silent audio files from DAW session archives.

    \b
    Typical workflow:
      1. silentscan scan /path/to/sessions --output report.silentscan.json
      2. silentscan clean report.silentscan.json --dry-run
      3. silentscan clean report.silentscan.json
    """
    pass


# ─── Scan subcommand ──────────────────────────────────────────────────────────

@cli.command()
@click.argument("root", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Path to write the JSON report. Defaults to <folder_name>.silentscan.json in the current directory.",
)
@click.option(
    "--threshold", "-t",
    type=float,
    default=DEFAULT_SILENCE_THRESHOLD_DB,
    show_default=True,
    help="Silence threshold in dBFS. Files with peak amplitude below this value are flagged.",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress per-file progress output. Only show the final summary.",
)
def scan(root, output, threshold, quiet):
    """
    Recursively scan ROOT for silent .wav and .aiff files.

    ROOT is the top-level directory to scan. All subdirectories are
    traversed with no depth limit.
    """
    root_path = Path(root)
    output_path = Path(output) if output else _default_report_path(root_path)

    click.echo(f"\n  Scanning: {root_path}")
    click.echo(f"  Threshold: {threshold} dBFS")
    click.echo(f"  Report will be saved to: {output_path}\n")

    start_time = time.monotonic()
    found_silent = 0

    def on_progress(current: int, total: int, path: Path):
        nonlocal found_silent
        if not quiet:
            # Overwrite the current line for a clean progress display
            click.echo(
                f"\r  [{current}/{total}]  {path.name[:50]:<50}  "
                f"({found_silent} silent found)",
                nl=False,
            )

    def on_silent_found():
        nonlocal found_silent
        found_silent += 1

    # Patch on_progress to also count silent files
    original_on_progress = on_progress

    silent_files = []
    total_scanned = [0]

    def progress_and_collect(current, total, path):
        total_scanned[0] = total
        original_on_progress(current, total, path)

    from silentscan.scanner import (
        SUPPORTED_EXTENSIONS,
        is_silent,
        get_duration,
        db_to_amplitude,
    )
    import os
    import numpy as np

    # Run scan manually here so we can update found_silent in real time
    all_files = [
        Path(dirpath) / filename
        for dirpath, _, filenames in os.walk(root_path)
        for filename in filenames
        if Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    total = len(all_files)

    if total == 0:
        click.echo(
            f"\n  No .wav or .aiff files found in {root_path}.\n"
            "  Check that you selected the correct root folder.\n"
        )
        return

    for index, file_path in enumerate(all_files, start=1):
        if not quiet:
            click.echo(
                f"\r  [{index}/{total}]  {file_path.name[:50]:<50}  "
                f"({found_silent} silent found)",
                nl=False,
            )

        if is_silent(file_path, threshold):
            found_silent += 1
            silent_files.append({
                "path": str(file_path),
                "size_bytes": file_path.stat().st_size,
                "duration_seconds": get_duration(file_path),
            })

    duration = time.monotonic() - start_time

    # Clear the progress line
    if not quiet:
        click.echo()

    report = build_report(
        root=root_path,
        silent_files=silent_files,
        total_scanned=total,
        threshold_db=threshold,
        duration_seconds=duration,
    )

    write_report(report, output_path)

    click.echo(summarize_report(report))
    click.echo(f"  Report saved: {output_path}\n")


# ─── Clean subcommand ─────────────────────────────────────────────────────────

@cli.command()
@click.argument("report", type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Preview what would be recycled without touching any files.",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Skip the confirmation prompt and recycle immediately.",
)
def clean(report, dry_run, yes):
    """
    Send silent files listed in REPORT to the Recycle Bin.

    REPORT is the path to a .silentscan.json file generated by the scan command.

    Always run with --dry-run first to verify the file list before recycling.
    """
    report_path = Path(report)
    run_clean(report_path, dry_run=dry_run, yes=yes)


# ─── Summary subcommand ───────────────────────────────────────────────────────

@cli.command()
@click.argument("report", type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def summary(report):
    """
    Print a summary of an existing REPORT without scanning or cleaning.

    Useful for reviewing a report generated in a previous session.
    """
    report_path = Path(report)
    data = read_report(report_path)
    click.echo(summarize_report(data))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()