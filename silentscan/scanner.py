import os
import soundfile as sf
import numpy as np
from pathlib import Path

SUPPORTED_EXTENSIONS = {'.wav', '.aiff', '.aif'}
DEFAULT_SILENCE_THRESHOLD_DB = -60.0

def db_to_amplitude(db: float) -> float:
    """Convert dBFS value to a linear amplitude value."""
    return 10 ** (db / 20)

def is_silent(file_path: Path, threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB) -> bool:
    """Check if the audio file is silent based on the given dB threshold."""
    try:
       data, _ = sf.read(str(file_path), always_2d=True)
       peak = np.max(np.abs(data))
       threshold = db_to_amplitude(threshold_db)
       return peak < threshold
    except Exception:
        # Unreadable file or corrupt file ignored.
        return False
    
def get_duration(file_path: Path) -> float | None:
    """Get the duration of the audio file in seconds."""
    try:
        info = sf.info(str(file_path))
        return info.duration
    except Exception:
        # Unreadable file or corrupt file ignored.
        return None
    
def scan_directory(
        root: Path, 
        threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB,
        on_progress=None
        ) -> list[dict]:
    """Scan the directory for silent audio files."""
    all_files = [
        Path(dirpath) / filename
        for dirpath, _, filenames in os.walk(root)
        for filename in filenames
        if Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    total = len(all_files)
    silent_files = []

    for index, file_path in enumerate(all_files, start=1):
        if on_progress:
            on_progress(index, total, file_path)

        if is_silent(file_path, threshold_db):
            silent_files.append({
                'path': str(file_path),
                'size_bytes': file_path.stat().st_size,
                'duration_seconds': get_duration(file_path),
            })

    return silent_files