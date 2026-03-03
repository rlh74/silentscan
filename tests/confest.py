"""
conftest.py

Pytest fixtures for silentscan. Generates synthetic audio files in a
temporary directory that is automatically created before each test and
cleaned up afterward.

Fixture tree:
    tmp_path/
    ├── Project_Alpha/
    │   ├── Audio Files/
    │   │   ├── silent_01.wav           — pure silence
    │   │   ├── silent_02.wav           — pure silence
    │   │   ├── tone_01.wav             — non-silent (440Hz tone)
    │   │   └── near_silent_01.wav      — peak just above threshold (-59.9 dBFS)
    │   └── Clips/
    │       ├── silent_03.wav           — pure silence
    │       └── tone_02.wav             — non-silent (880Hz tone)
    └── Project_Beta/
        └── Audio Files/
            ├── silent_04.wav           — pure silence
            └── tone_03.wav             — non-silent (220Hz tone)

Expected results at default threshold (-60.0 dBFS):
    Silent:      4 files  (silent_01 through silent_04)
    Non-silent:  4 files  (tone_01, tone_02, tone_03, near_silent_01)
    Total:       8 files
"""

import math
import struct
import wave
from pathlib import Path

import pytest

# ─── Audio generation helpers ─────────────────────────────────────────────────

SAMPLE_RATE = 44100
DURATION = 2.0  # seconds — short enough to keep tests fast

def _write_wav(path: Path, samples: list[int]) -> None:
    """Write a list of integer samples to a WAV file."""
    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        sample_data = struct.pack('<' + 'h' * len(samples), *samples)
        wf.writeframes(sample_data)

def _silent_samples() -> list[int]:
    """Generate samples representing pure silence."""
    return [0] * int(SAMPLE_RATE * DURATION)

def _tone_samples(frequency: float = 440.0, amplitude_db: float = 0.5) -> list[int]:
    """Generate samples for a sine wave tone at the given frequency and amplitude."""
    num_samples = int(SAMPLE_RATE * DURATION)
    peak = int(amplitude_db * 32767)
    return [
        int(peak * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE))
        for i in range(num_samples)
    ]

def _near_silent_samples(threshold_db: float = -60.0, offset_db: float = 0.1) -> list[int]:
    """
    Generate samples with a peak just above the silence threshold.

    By default produces a peak at -59.9 dBFS — above the default threshold
    of -60.0 dBFS, so the file should be treated as non-silent.

    Args:
        threshold_db: The silence threshold in dBFS.
        offset_db: How many dB above the threshold the peak should sit.
    """
    target_db = threshold_db + offset_db
    amplitude = 10 ** (target_db / 20)
    num_samples = int(DURATION * SAMPLE_RATE)
    peak = int(amplitude * 32767)
    samples = [0] * num_samples
    samples[num_samples // 2] = peak
    return samples

# ─── Fixture tree builder ─────────────────────────────────────────────────────

def build_fixture_tree(root: Path) -> dict:
    """
    Write the full fixture tree to root and return a dict describing
    what was created, keyed by logical name.
    """
    files = {
        "silent_01": root / "Project_Alpha" / "Audio Files" / "silent_01.wav",
        "silent_02": root / "Project_Alpha" / "Audio Files" / "silent_02.wav",
        "tone_01":   root / "Project_Alpha" / "Audio Files" / "tone_01.wav",
        "near_silent_01": root / "Project_Alpha" / "Audio Files" / "near_silent_01.wav",
        "silent_03": root / "Project_Alpha" / "Clips" / "silent_03.wav",
        "tone_02":   root / "Project_Alpha" / "Clips" / "tone_02.wav",
        "silent_04": root / "Project_Beta"  / "Audio Files" / "silent_04.wav",
        "tone_03":   root / "Project_Beta"  / "Audio Files" / "tone_03.wav",
    }

    _write_wav(files["silent_01"],      _silent_samples())
    _write_wav(files["silent_02"],      _silent_samples())
    _write_wav(files["tone_01"],        _tone_samples(frequency=440.0))
    _write_wav(files["near_silent_01"], _near_silent_samples())
    _write_wav(files["silent_03"],      _silent_samples())
    _write_wav(files["tone_02"],        _tone_samples(frequency=880.0))
    _write_wav(files["silent_04"],      _silent_samples())
    _write_wav(files["tone_03"],        _tone_samples(frequency=220.0))

    return files


# ─── Pytest fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """
    Pytest fixture that builds the full audio fixture tree in a temporary
    directory and returns the root path.

    tmp_path is provided by pytest and is automatically cleaned up after
    each test.
    """
    build_fixture_tree(tmp_path)
    return tmp_path


@pytest.fixture
def fixture_files(tmp_path: Path) -> dict:
    """
    Pytest fixture that builds the fixture tree and returns the file dict,
    giving tests direct access to individual file paths by logical name.

    Example:
        def test_something(fixture_files):
            path = fixture_files["silent_01"]
    """
    return build_fixture_tree(tmp_path)


@pytest.fixture
def silent_wav(tmp_path: Path) -> Path:
    """A single silent WAV file."""
    path = tmp_path / "silent.wav"
    _write_wav(path, _silent_samples())
    return path


@pytest.fixture
def tone_wav(tmp_path: Path) -> Path:
    """A single non-silent WAV file."""
    path = tmp_path / "tone.wav"
    _write_wav(path, _tone_samples())
    return path


@pytest.fixture
def near_silent_wav(tmp_path: Path) -> Path:
    """A single WAV file with peak just above the default silence threshold."""
    path = tmp_path / "near_silent.wav"
    _write_wav(path, _near_silent_samples())
    return path


