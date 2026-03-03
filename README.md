# silentscan

A command-line tool for finding and removing silent audio files from DAW session archives.

## Background

Recording with all inputs armed is a common defensive practice — it means you never miss a take. The tradeoff is that most of those tracks record nothing. Over years of sessions, this adds up to gigabytes of completely silent files scattered across project folders.

`silentscan` automates the cleanup. It recursively scans a folder tree, identifies silent audio files using peak amplitude analysis, generates a structured report, and sends flagged files to the Recycle Bin.

---

## Requirements

- Python 3.12+
- macOS or Windows
- [pyenv](https://github.com/pyenv/pyenv) (recommended for managing Python versions)
- On macOS: [`trash`](https://formulae.brew.sh/formula/trash) CLI for Recycle Bin support

---

## Installation

### 1. Clone the repository

### 2. Create and activate a virtual environment

**macOS (fish shell):**

```fish
python3 -m venv .venv
source .venv/bin/activate.fish
```

**macOS (bash/zsh):**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements-dev.txt
```

### 4. Install the CLI

```bash
pip install -e .
```

### 5. macOS only — install the `trash` CLI

```bash
brew install trash
```

This is required for sending files to the Trash on macOS. `silentscan` will not perform permanent deletion under any circumstances.

---

## Typical Workflow

```
silentscan scan /path/to/sessions
silentscan reports
silentscan clean-all --dry-run
silentscan clean-all --yes
```

---

## Commands

### `scan`

Recursively scan a directory for silent `.wav` and `.aiff` files. All subdirectories are traversed with no depth limit. Results are saved as a JSON report in the silentscan reports directory.

```bash
silentscan scan /path/to/sessions
```

**Options:**

| Flag              | Description                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| `--output, -o`    | Custom path for the report file. Defaults to the silentscan reports directory.                       |
| `--threshold, -t` | Silence threshold in dBFS. Default: `-60.0`. Files with peak amplitude below this value are flagged. |
| `--quiet, -q`     | Suppress per-file progress output. Only show the final summary.                                      |

**Example:**

```bash
silentscan scan ~/Music/Sessions --threshold -48.0
```

---

### `reports`

List all scan reports saved in the silentscan reports directory.

```bash
silentscan reports
```

### `clean`

Send silent files from a single report to the Recycle Bin.

```bash
silentscan clean /path/to/report.silentscan.json
```

**Always run with `--dry-run` first.**

**Options:**

| Flag            | Description                                                |
| --------------- | ---------------------------------------------------------- |
| `--dry-run, -n` | Preview what would be recycled without touching any files. |
| `--yes, -y`     | Skip the confirmation prompt.                              |

---

### `clean-all`

Send silent files from **all** saved reports to the Recycle Bin in a single pass with one confirmation prompt.

```bash
silentscan clean-all --dry-run
silentscan clean-all --yes
```

**Options:**

| Flag            | Description                                            |
| --------------- | ------------------------------------------------------ |
| `--dry-run, -n` | Preview across all reports without touching any files. |
| `--yes, -y`     | Skip confirmation and recycle immediately.             |

---

### `summary`

Print a detailed summary of an existing report without scanning or cleaning anything.

```bash
silentscan summary /path/to/report.silentscan.json
```

---

## How Silence Detection Works

`silentscan` reads each `.wav` or `.aiff` file and measures its **peak amplitude** — the highest absolute sample value in the file. If the peak is below the silence threshold (default `-60.0 dBFS`), the file is flagged as silent.

Peak amplitude is used rather than RMS (average loudness) because it is stricter: even a single non-silent sample anywhere in the file will cause it to be kept. A file that was never recorded to will have a peak of exactly zero.

Corrupted or unreadable files are skipped and never flagged for deletion.

---

## Report Storage

Reports are saved to a platform-appropriate directory:

- **macOS:** `~/Library/Application Support/silentscan/reports/`
- **Windows:** `%APPDATA%\silentscan\reports\`

Reports are named after the scanned root folder: scanning `/Sessions/Project_Alpha` produces `Project_Alpha.silentscan.json`.

Reports are excluded from version control via `.gitignore`.

---

## Safety

- Files are **always** sent to the OS Recycle Bin / Trash — permanent deletion is not possible
- `--dry-run` is available on all destructive commands
- Confirmation is required before any files are moved unless `--yes` is passed explicitly
- Scan reports are written before any files are touched, providing a full audit trail

## Development

### Generate test fixtures

```bash
python generate_test_fixtures.py
```

Creates a `fixtures/` directory with a mix of silent and non-silent `.wav` and `.aiff` files across a nested folder structure that mimics a real DAW session archive.

### Run a test scan

```bash
silentscan scan fixtures
silentscan reports
silentscan clean-all --dry-run
```

---

## License

MIT
