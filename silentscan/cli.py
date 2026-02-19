import os
import time
from pathlib import Path

import click

from silentscan.scanner import (
    SUPPORTED_EXTENSIONS,
    is_silent,
    get_duration,
    DEFAULT_SILENCE_THRESHOLD_DB,
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
    for report_path in report_files:
        try:
            results.append((report_path, read_report(report_path)))
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
    help="Path to write the JSON report. Defaults to silentscan reports directory.",
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
    output_path = Path(output) if output else get_default_report_path(root_path)

    click.echo(f"\n  Scanning: {root_path}")
    click.echo(f"  Threshold: {threshold} dBFS")
    click.echo(f"  Report: {output_path}\n")

    # Collect all supported audio files
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

    start_time = time.monotonic()
    silent_files = []
    found_silent = 0
    current_dir = None
    dir_silent = 0

    for index, file_path in enumerate(all_files, start=1):
        if not quiet:
            if file_path.parent != current_dir:
                current_dir = file_path.parent
                dir_silent = 0
                click.echo(f"\n  {current_dir}")

        if is_silent(file_path, threshold):
            found_silent += 1
            dir_silent += 1
            silent_files.append({
                "path": str(file_path),
                "size_bytes": file_path.stat().st_size,
                "duration_seconds": get_duration(file_path),
            })

        if not quiet:
            pct = int((index / total) * 100)
            click.echo(
                f"\r {pct:>3}% [{index}/{total}]  {file_path.name[:50]:<50}  "
                f"({dir_silent} silent audio files in folder)",
                nl=False,
            )

    duration = time.monotonic() - start_time

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

# ─── Reports subcommand ───────────────────────────────────────────────────────

@cli.command("reports")
def list_reports():
    """
    List all scan reports saved in the silentscan reports directory.
    """
    reports = load_all_reports()

    if not reports:
        click.echo("\n  No reports found. Run 'silentscan scan' to generate one.\n")
        return

    click.echo(f"\n── Reports ({len(reports)} found) {'─' * 35}")
    click.echo(f"  {'Name':<35} {'Scanned':<22} {'Silent':>8} {'Reclaimable':>12}")
    click.echo(f"  {'─'*35} {'─'*22} {'─'*8} {'─'*12}")

    for report_path, report in reports:
        name = report_path.stem.replace(".silentscan", "")[:35]
        scanned_at = report.get("scanned_at", "unknown")[:19].replace("T", " ")
        silent = report.get("total_silent_files", 0)
        size = format_size(report.get("total_silent_size_bytes", 0))
        click.echo(f"  {name:<35} {scanned_at:<22} {silent:>8} {size:>12}")

    click.echo()
    click.echo(f"  Reports directory: {get_reports_dir()}")
    click.echo()


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

# ─── Clean-all subcommand ─────────────────────────────────────────────────────

@cli.command("clean-all")
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Preview what would be recycled across all reports without touching any files.",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation and recycle all flagged files across all reports.",
)
def clean_all(dry_run, yes):
    """
    Send silent files from ALL saved reports to the Recycle Bin in one pass.

    Processes every report in the silentscan reports directory with a single
    confirmation prompt. Always run with --dry-run first.
    """
    reports = load_all_reports()

    if not reports:
        click.echo("\n  No reports found. Run 'silentscan scan' first.\n")
        return

    # Tally across all reports
    all_files = [
        f
        for _, report in reports
        for session in report.get("sessions", [])
        for f in session.get("silent_files", [])
    ]

    if not all_files:
        click.echo("\n  No silent files found across all reports. Nothing to do.\n")
        return

    total_size = sum(f["size_bytes"] for f in all_files)

    click.echo(f"\n── Clean All {'(DRY RUN) ' if dry_run else ''}{'─' * 43}")
    click.echo(f"  {len(reports)} report(s)  ·  {len(all_files)} file(s)  ·  {format_size(total_size)} reclaimable\n")

    for report_path, report in reports:
        files_in_report = [
            f
            for session in report.get("sessions", [])
            for f in session.get("silent_files", [])
        ]
        report_size = sum(f["size_bytes"] for f in files_in_report)
        click.echo(f"  {report_path.stem:<45} {len(files_in_report):>4} file(s)  {format_size(report_size):>10}")

    click.echo()

    if dry_run:
        click.echo("  Dry run — no files were moved to the Recycle Bin.\n")
        return

    if not yes:
        confirmed = click.confirm(
            f"  Send {len(all_files)} file(s) across {len(reports)} report(s) to the Recycle Bin?",
            default=False,
        )
        if not confirmed:
            click.echo("\n  Aborted. No files were moved.\n")
            return

    click.echo()

    # Process each report
    for report_path, _ in reports:
        click.echo(f"  ── {report_path.stem}")
        run_clean(report_path, dry_run=False, yes=True)


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