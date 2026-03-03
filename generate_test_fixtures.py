"""
generate_test_fixtures.py

Generates a small tree of synthetic WAV files for testing silentscan.
Creates a mix of silent, non-silent, and near-silent files across a nested folder structure, mimicking a typical DAW session archive.

Usage:
    python generate_test_fixtures.py
    python generate_test_fixtures.py --output /path/to/fixtures
"""

import argparse
import struct
import wave
from pathlib import Path

# ─── WAV Writing ─────────────────────────────────────────────────

def write_wav(path: Path, samples: list[int], sample_rate: int = 44100) -> None:
    """Write a mono 16-bit WAV file from a list of integer samples."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)  # mono
        f.setsampwidth(2)  # 16-bit
        f.setframerate(sample_rate)
        for sample in samples:
            f.writeframes(struct.pack("<h", sample))

def write_aiff(path: Path, samples: list[int], sample_rate: int = 44100) -> None:
    """Write a mono 16-bit AIFF file from a list of integer samples."""
    import numpy as np
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.array(samples, dtype=np.int16)
    sf.write(str(path), audio, sample_rate, subtype="PCM_16", format="AIFF")

def silent_samples(duration_seconds: float = 5.0, sample_rate: int = 44100) -> list[int]:
    """Generate samples representing pure silence."""
    return [0] * int(duration_seconds * sample_rate)

def tone_samples(
        duration_seconds: float = 5.0,
        sample_rate: int = 44100,
        frequency: float = 440.0,
        amplitude: float = 0.5
) -> list[int]:
    """Generate samples for a sine wave tone at the given frequency and amplitude."""
    import math
    num_samples = int(duration_seconds * sample_rate)
    peak = int(amplitude * 32767)
    return [ 
        int(peak * math.sin(2 * math.pi * frequency * i / sample_rate))
        for i in range(num_samples)
    ]

def noise_samples(
        duration_seconds: float = 5.0,
        sample_rate: int = 44100,
        amplitude: float = 0.3
) -> list[int]:
    """Generate samples for white noise at the given amplitude."""
    import random
    num_samples = int(duration_seconds * sample_rate)
    peak = int(amplitude * 32767)
    return [random.randint(-peak, peak) for _ in range(num_samples)]

# ─── Fixture tree ─────────────────────────────────────────────────────────────

def generate_fixtures(output_root: Path) -> None:
    """
    Generate a fixture tree that mimics a DAW session archive:

    fixtures/
    ├── Project_Alpha/
    │   ├── Audio Files/          ← recorded audio
    │   │   ├── track_01.wav      SILENT
    │   │   ├── track_02.wav      SILENT
    │   │   ├── track_03.wav      non-silent (440Hz tone)
    │   │   └── track_04.wav      non-silent (noise)
    │   ├── Clips/                ← DAW-cropped audio
    │   │   ├── clip_01.aiff      SILENT
    │   │   └── clip_02.aiff      non-silent (tone)
    │   └── Freeze Files/         ← DAW-processed audio
    │       ├── freeze_01.wav     non-silent (noise)
    │       └── freeze_02.wav     SILENT
    └── Project_Beta/
        ├── Audio Files/
        │   ├── track_01.wav      SILENT
        │   ├── track_02.wav      SILENT
        │   └── track_03.wav      non-silent (tone)
        └── Clips/
            ├── clip_01.aiff      non-silent (noise)
            └── clip_02.aiff      SILENT

    Expected scan results:
      Silent:      7 files
      Non-silent:  5 files
      Total:      12 files
    """

    print(f"\n  Generating fixtures in: {output_root}\n")

    files = [
        # Project Alpha — Audio Files
        ("Project_Alpha/Audio Files/track_01.wav",     "wav",  "silent"),
        ("Project_Alpha/Audio Files/track_02.wav",     "wav",  "silent"),
        ("Project_Alpha/Audio Files/track_03.wav",     "wav",  "tone"),
        ("Project_Alpha/Audio Files/track_04.wav",     "wav",  "noise"),
        # Project Alpha — Clips
        ("Project_Alpha/Clips/clip_01.aiff",           "aiff", "silent"),
        ("Project_Alpha/Clips/clip_02.aiff",           "aiff", "tone"),
        # Project Alpha — Freeze Files
        ("Project_Alpha/Freeze Files/freeze_01.wav",   "wav",  "noise"),
        ("Project_Alpha/Freeze Files/freeze_02.wav",   "wav",  "silent"),
        # Project Beta — Audio Files
        ("Project_Beta/Audio Files/track_01.wav",      "wav",  "silent"),
        ("Project_Beta/Audio Files/track_02.wav",      "wav",  "silent"),
        ("Project_Beta/Audio Files/track_03.wav",      "wav",  "tone"),
        # Project Beta — Clips
        ("Project_Beta/Clips/clip_01.aiff",            "aiff", "noise"),
        ("Project_Beta/Clips/clip_02.aiff",            "aiff", "silent"),
    ]

    silent_count = 0
    non_silent_count = 0

    for relative_path, fmt, content in files:
        path = output_root / relative_path
        is_silent = content == "silent"

        if content == "silent":
            samples = silent_samples()
            silent_count += 1
        elif content == "tone":
            samples = tone_samples()
            non_silent_count += 1
        else:
            samples = noise_samples()
            non_silent_count += 1

        if fmt == "wav":
            write_wav(path, samples)
        else:
            write_aiff(path, samples)

        label = "SILENT    " if is_silent else "non-silent"
        print(f"  [{label}]  {relative_path}")

    print(f"\n  ── Summary ───────────────────────────────────────────")
    print(f"  Silent files:      {silent_count}")
    print(f"  Non-silent files:  {non_silent_count}")
    print(f"  Total:             {silent_count + non_silent_count}")
    print(f"\n  Fixtures ready. Run:")
    print(f"\n    python cli.py scan {output_root}")
    print(f"\n  Expected: {silent_count} silent files flagged.\n")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic test fixtures for silentscan."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="fixtures",
        help="Root directory to write fixtures into. Default: ./fixtures",
    )
    args = parser.parse_args()
    generate_fixtures(Path(args.output))