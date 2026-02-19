import sys
from pathlib import Path

from silentscan.report import read_report, format_size, format_duration

def _trash_file(file_path: Path) -> bool:
    try:
        if sys.platform == "darwin":
            import subprocess
            result = subprocess.run(
                ["trash", str(file_path)],
                capture_output=True,
            )
            return result.returncode == 0
        
        elif sys.platform == "win32":
            import winshell
            winshell.delete_file(
                str(file_path),
                no_confirm=True,
                allow_undo=True,
            )
            return True
        else:
            raise NotImplementedError(
                "Recycling Bin is not supported on this platform. Mac or Windows is only supported."
            )
    except Exception as e:
        return False
    
def _confirm(prompt: str) -> bool:
    """Prompt the user for confirmation. Returns True for yes."""
    while True:
        answer = input(f"{prompt} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False
        print("Please enter 'y' or 'n'.")

def collect_files(report: dict) -> list[dict]:
    """Collect all file paths from the report."""
    return [
        file
        for session in report["sessions"]
        for file in session["silent_files"]
    ]

def print_file_list(files: list[dict]) -> None:
    """Print the list of files staged for recycling."""
    print()
    for f in files:
        path = Path(f["path"])
        size = format_size(f["size_bytes"])
        duration = format_duration(f.get("duration_seconds"))
        print(f"  · {path.name}")
        print(f"    {path.parent}")
        print(f"    {size}  ·  {duration}")
    print()

def run_clean(
        report_path: Path,
        dry_run: bool = False,
        yes: bool = False,
) -> None:
    """Run cleaning"""
    report = read_report(report_path)
    files = collect_files(report)

    if not files:
        print("No silent files found. Nothing to clean.")
        return
    
    total_size = sum(f["size_bytes"] for f in files)

    print(f"\n── Clean: {report_path.name} {'(DRY RUN)' if dry_run else ''}".ljust(56, "─"))
    print(f"  {len(files)} file(s) staged  ·  {format_size(total_size)} reclaimable")
    print("────────────────────────────────────────────────────────")

    print_file_list(files)

    if dry_run:
        print("  Dry run — no files were moved to the Recycle Bin.\n")
        return
    
    if not yes:
        confirmed = _confirm(
            f"  Send {len(files)} file(s) to the Recycle Bin?"
        )
        if not confirmed:
            print("\n  Aborted. No files were moved.\n")
            return
        
    # Perform recycling
    print()
    succeeded = []
    failed = []

    for f in files:
        file_path = Path(f["path"])

        if not file_path.exists():
            print(f"  ⚠  Not found, skipping: {file_path.name}")
            failed.append(f)
            continue

        success = _trash_file(file_path)

        if success:
            print(f"  ✓  {file_path.name}")
            succeeded.append(f)
        else:
            print(f"  ✗  Failed: {file_path.name}")
            failed.append(f)

    # Summary
    print()
    print("── Result ".ljust(56, "─"))
    print(f"  Recycled   {len(succeeded)} file(s)  ({format_size(sum(f['size_bytes'] for f in succeeded))})")
    if failed:
        print(f"  Failed     {len(failed)} file(s)")
        print("\n  Files that could not be recycled:")
        for f in failed:
            print(f"    · {f['path']}")
    print()