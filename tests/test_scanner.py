"""
test_scanner.py

Tests for silentscan/scanner.py covering:
  - is_silent() with silent, non-silent, and near-silent files
  - get_duration() accuracy
  - scan_directory() traversal, filtering, and result structure
"""

from pathlib import Path

import pytest

from silentscan.scanner import (
    DEFAULT_SILENCE_THRESHOLD_DB,
    is_silent,
    get_duration,
    scan_directory,
    SUPPORTED_EXTENSIONS,
)   

# ─── is_silent ────────────────────────────────────────────────────────────────

class TestIsSilent:

    def test_silent_wav_is_flagged(self, silent_wav):
        """A WAV file containing only zero samples should be flagged as silent."""
        assert is_silent(silent_wav, threshold_db=DEFAULT_SILENCE_THRESHOLD_DB)

    def test_tone_wav_is_not_flagged(self, tone_wav):
        """A WAV file containing a sine tone should not be flagged as silent."""
        assert not is_silent(tone_wav, threshold_db=DEFAULT_SILENCE_THRESHOLD_DB)

    def test_near_silent_wav_is_not_flagged(self, near_silent_wav):
        """
        A WAV file with peak just above the threshold should not be flagged.
        Confirms the threshold boundary is exclusive — files at or above
        the threshold are kept.
        """
        assert not is_silent(near_silent_wav) is False

    def test_near_silent_wav_flagged_at_higher_threshold(self, near_silent_wav):
        """
        The same near-silent file should be flagged when the threshold is
        raised above its peak amplitude.
        """
        assert is_silent(near_silent_wav, threshold_db=-59.0) is True

    def test_custom_threshold_flags_quiet_tone(self, tmp_path):
        """
        A tone at low amplitude should be flagged when threshold is raised
        above its peak.
        """
        import math
        import struct
        import wave

        # Write a tone at -40 dBFS
        path = tmp_path / "quiet_tone.wav"
        amplitude = 10 ** (-40 / 20)
        num_samples = 44100
        peak = int(amplitude * 32767)
        with wave.open(str(path), "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            for i in range(num_samples):
                sample = int(peak * math.sin(2 * math.pi * 440 * i / 44100))
                f.writeframes(struct.pack("<h", sample))

        # Should not be flagged at default threshold
        assert is_silent(path, threshold_db=-60.0) is False
        # Should be flagged when threshold is raised above its amplitude
        assert is_silent(path, threshold_db=-30.0) is True

    def test_nonexistent_file_returns_false(self, tmp_path):
        """
        A file that does not exist should return False rather than raising
        an exception — corrupt or missing files are never flagged for deletion.
        """
        missing = tmp_path / "does_not_exist.wav"
        assert is_silent(missing) is False

    def test_corrupted_file_returns_false(self, tmp_path):
        """
        A file with invalid audio content should return False rather than
        raising an exception.
        """
        corrupted = tmp_path / "corrupted.wav"
        corrupted.write_bytes(b"this is not valid audio data")
        assert is_silent(corrupted) is False

    # ─── get_duration ─────────────────────────────────────────────────────────────

class TestGetDuration:

    def test_duration_is_approximately_correct(self, silent_wav):
        """Duration should be within 0.1 seconds of the expected value."""
        duration = get_duration(silent_wav)
        assert duration is not None
        assert abs(duration - 2.0) < 0.1

    def test_duration_of_nonexistent_file_is_none(self, tmp_path):
        """Missing files should return None rather than raising."""
        missing = tmp_path / "does_not_exist.wav"
        assert get_duration(missing) is None

    def test_duration_of_corrupted_file_is_none(self, tmp_path):
        """Corrupted files should return None rather than raising."""
        corrupted = tmp_path / "corrupted.wav"
        corrupted.write_bytes(b"not audio")
        assert get_duration(corrupted) is None

    # ─── scan_directory ───────────────────────────────────────────────────────────

class TestScanDirectory:

    def test_correct_number_of_silent_files_found(self, fixture_root):
        """
        Scanning the full fixture tree should find exactly 4 silent files
        and leave 4 non-silent files unflagged.
        """
        results = scan_directory(fixture_root)
        assert len(results) == 4

    def test_silent_file_paths_are_correct(self, fixture_root, fixture_files):
        """All returned paths should correspond to known silent fixture files."""
        results = scan_directory(fixture_root)
        result_paths = {Path(r["path"]) for r in results}
        expected_silent = {
            fixture_files["silent_01"],
            fixture_files["silent_02"],
            fixture_files["silent_03"],
            fixture_files["silent_04"],
        }
        assert result_paths == expected_silent

    def test_non_silent_files_are_not_returned(self, fixture_root, fixture_files):
        """Tone and near-silent files should not appear in results."""
        results = scan_directory(fixture_root)
        result_paths = {Path(r["path"]) for r in results}
        non_silent = {
            fixture_files["tone_01"],
            fixture_files["tone_02"],
            fixture_files["tone_03"],
            fixture_files["near_silent_01"],
        }
        assert result_paths.isdisjoint(non_silent)

    def test_result_structure_has_required_keys(self, fixture_root):
        """Each result dict should contain path, size_bytes, and duration_seconds."""
        results = scan_directory(fixture_root)
        for result in results:
            assert "path" in result
            assert "size_bytes" in result
            assert "duration_seconds" in result

    def test_size_bytes_is_positive(self, fixture_root):
        """All flagged files should report a positive file size."""
        results = scan_directory(fixture_root)
        for result in results:
            assert result["size_bytes"] > 0

    def test_duration_seconds_is_positive(self, fixture_root):
        """All flagged files should report a positive duration."""
        results = scan_directory(fixture_root)
        for result in results:
            assert result["duration_seconds"] is not None
            assert result["duration_seconds"] > 0

    def test_traverses_nested_subdirectories(self, fixture_root, fixture_files):
        """Files in nested subdirectories should be found."""
        results = scan_directory(fixture_root)
        result_paths = {Path(r["path"]) for r in results}
        # silent_03 is in Project_Alpha/Clips — a nested subdirectory
        assert fixture_files["silent_03"] in result_paths

    def test_ignores_unsupported_file_types(self, fixture_root):
        """Non-audio files placed in the tree should not appear in results."""
        # Write a text file into the fixture tree
        decoy = fixture_root / "Project_Alpha" / "Audio Files" / "notes.txt"
        decoy.write_text("these are session notes")
        results = scan_directory(fixture_root)
        result_paths = {r["path"] for r in results}
        assert str(decoy) not in result_paths

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """Scanning a directory with no audio files should return an empty list."""
        results = scan_directory(tmp_path)
        assert results == []

    def test_on_progress_callback_is_called(self, fixture_root):
        """The on_progress callback should be called once per file."""
        calls = []

        def on_progress(current, total, path):
            calls.append((current, total))

        scan_directory(fixture_root, on_progress=on_progress)

        # Should be called once per file in the tree
        assert len(calls) == 8
        # Final call should have current == total
        assert calls[-1][0] == calls[-1][1]

    def test_on_progress_total_is_accurate(self, fixture_root):
        """The total passed to on_progress should match the actual file count."""
        totals = []

        def on_progress(current, total, path):
            totals.append(total)

        scan_directory(fixture_root, on_progress=on_progress)
        assert all(t == 8 for t in totals)

    def test_custom_threshold_changes_results(self, fixture_root, fixture_files):
        """
        Raising the threshold should cause the near-silent file to be flagged.
        At -59.0 dBFS, near_silent_01 should appear in results.
        """
        results = scan_directory(fixture_root, threshold_db=-59.0)
        result_paths = {Path(r["path"]) for r in results}
        assert fixture_files["near_silent_01"] in result_paths

    def test_supported_extensions(self):
        """SUPPORTED_EXTENSIONS should include .wav, .aiff, and .aif."""
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".aiff" in SUPPORTED_EXTENSIONS
        assert ".aif" in SUPPORTED_EXTENSIONS