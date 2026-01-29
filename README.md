# Gourani

User-research transcription and quote extraction engine.

Drop a folder of interview recordings in, get themed verbatim quotes out --
as a browsable HTML report with clickable timecodes and a popout video player.

## What it does

Gourani processes user-research interview files through a 12-stage pipeline:

1. **Ingest** -- discovers audio, video, subtitle (.srt/.vtt), and Teams .docx files; assigns participant IDs (p1, p2...) by file creation date
2. **Extract audio** -- pulls audio from video files via ffmpeg
3. **Parse subtitles/docx** -- reads existing transcripts from .srt, .vtt, or Teams .docx exports
4. **Transcribe** -- speech-to-text via faster-whisper (skipped if a transcript already exists)
5. **Identify speakers** -- works out who is the researcher and who is the participant
6. **Merge transcripts** -- normalises all sources into one transcript per session
7. **Remove PII** -- redacts names, phone numbers, emails, etc. via Presidio
8. **Segment topics** -- LLM identifies when participants transition between screens or topics
9. **Extract quotes** -- LLM pulls verbatim quotes from participant speech with editorial cleanup
10. **Cluster by screen** -- groups screen-specific quotes across all participants
11. **Group by theme** -- groups general/contextual quotes into emergent themes
12. **Render output** -- writes `research_report.html` and `research_report.md`

### Output

```
output/
  research_report.html         # the deliverable -- browsable report
  research_report.md           # Markdown version
  gourani-theme.css            # editable theme (auto-generated, safe to customise)
  gourani-player.html          # popout video player (auto-generated)
  raw_transcripts/             # one .txt per participant
  cooked_transcripts/          # cleaned transcripts after PII removal
  intermediate/                # JSON debug files (quotes, clusters, themes)
```

### HTML report

The HTML report is the primary output. It includes:

- **Participant table** at the top with session dates, durations, and clickable source file links
- **Table of contents** -- side-by-side Sections and Themes columns on wide screens, stacked on narrow
- **Sections** -- screen-specific quote clusters, ordered by product flow
- **Themes** -- emergent cross-participant themes with grouped quotes
- **Sentiment** -- mirror-reflection histogram showing the balance of positive and negative emotions across all quotes
- **Friction points** -- moments flagged for researcher review (confusion, frustration, error-recovery)
- **User journeys** -- per-participant stage progression and friction point counts

Every timecode is a clickable link. Clicking opens a **popout video player** that seeks to that moment. The player stays in a separate resizable window so you can arrange the report and video side by side at whatever sizes work for your screen.

### Quote format

Quotes preserve authentic participant expression with light editorial cleanup:

```
[05:23] "I was... trying to find the button and it just... wasn't there." -- p3
```

- Timecodes use `MM:SS` when under one hour, `HH:MM:SS` when over
- `...` replaces removed filler (um, uh, like, you know)
- `[square brackets]` mark editorial insertions for clarity
- `[When asked about X]` prefixes researcher context where needed
- Emotion, frustration, humour, and strong language are preserved verbatim

### Theming

The report ships with `gourani-theme.css` -- a clean, print-friendly stylesheet.
You can edit it freely; Gourani won't overwrite your changes on re-run. If you
want to reset to the default theme, just delete the file and re-run.

---

## Setup

### Prerequisites

- **Python 3.10+** (3.12 recommended)
- **ffmpeg** (for video/audio processing and building the `av` dependency)
- **pkg-config** (needed to compile PyAV against ffmpeg headers)
- An API key for **Anthropic** (Claude) or **OpenAI**

### macOS (Apple Silicon)

macOS ships with Python 3.9 which is too old. Use Homebrew:

```bash
# Install prerequisites (skip if you already have them)
brew install python@3.12 ffmpeg pkg-config

# Clone and enter the project
cd gourani

# Create a virtual environment with Homebrew Python
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Enable Apple Silicon GPU acceleration (M1/M2/M3/M4 -- all variants)
pip install -e ".[apple]"

# Set up your API key
cp .env.example .env
# Edit .env and add your GOURANI_ANTHROPIC_API_KEY
```

**Tip -- avoid typing `source .venv/bin/activate` every time:**

Add this to your `~/.zshrc` (or `~/.zprofile`):

```bash
# Auto-activate venv when entering a project directory
auto_activate_venv() {
  if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
  fi
}
chpwd_functions=(${chpwd_functions[@]} "auto_activate_venv")
auto_activate_venv  # also run on shell startup
```

Now any time you `cd` into a directory containing `.venv/`, it activates automatically.

### macOS (Intel)

Same as above, but Homebrew installs to `/usr/local`:

```bash
/usr/local/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Linux (Ubuntu/Debian)

```bash
# Install Python 3.12 and ffmpeg
sudo apt update
sudo apt install python3.12 python3.12-venv ffmpeg pkg-config libavformat-dev libavcodec-dev libavutil-dev libswscale-dev libswresample-dev

# Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Tip -- auto-activate for bash users**, add to `~/.bashrc`:

```bash
auto_activate_venv() {
  if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
  fi
}
PROMPT_COMMAND="auto_activate_venv; ${PROMPT_COMMAND}"
```

### Windows

```powershell
# Install Python 3.12 from https://www.python.org/downloads/
# Make sure to tick "Add Python to PATH" during installation
# Install ffmpeg from https://ffmpeg.org/download.html (or via winget/choco)

# Create venv and install
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

**Tip -- auto-activate for PowerShell users**, add to your `$PROFILE`:

```powershell
function Invoke-AutoVenv {
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        & .venv\Scripts\Activate.ps1
    }
}
# Run on every prompt
function prompt {
    Invoke-AutoVenv
    "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) "
}
```

### Using `gourani` from any directory

The auto-activate snippets above only activate the venv when you `cd` into the
project directory. If you want the `gourani` command available globally -- from
any folder on your system -- you have two options:

**Option A: pipx (recommended)**

[pipx](https://pipx.pypa.io/) installs Python CLI tools into isolated
environments and puts them on your PATH automatically:

```bash
# macOS
brew install pipx
pipx ensurepath

# Linux
sudo apt install pipx
pipx ensurepath

# Windows
python -m pip install --user pipx
pipx ensurepath
```

Then install gourani globally:

```bash
# For regular use
pipx install /path/to/gourani --python python3.12

# For development (picks up code changes automatically)
pipx install --editable /path/to/gourani --python python3.12
```

Now `gourani` works from any directory. To add Apple Silicon GPU support:

```bash
pipx inject gourani mlx mlx-whisper
```

> **Troubleshooting pipx install**
>
> - **`pkg-config is required for building PyAV`** -- Install the build
>   prerequisites first: `brew install pkg-config ffmpeg` (macOS) or
>   `sudo apt install pkg-config libavformat-dev libavcodec-dev libavutil-dev`
>   (Linux). The `av` package (a dependency of faster-whisper) needs to compile
>   C extensions against ffmpeg headers.
>
> - **`ResolutionImpossible` / dependency conflicts** -- pipx uses your system's
>   default `python3`, which may be too new (e.g. 3.14) for some packages.
>   Pin it to 3.12:
>   ```
>   pipx install --editable /path/to/gourani --python python3.12
>   ```
>   On macOS with Homebrew you can also use the full path:
>   ```
>   pipx install --editable /path/to/gourani --python /opt/homebrew/bin/python3.12
>   ```
>
> - **`gourani: command not found` after install** -- Run `pipx ensurepath` and
>   open a new terminal. This adds `~/.local/bin` to your PATH.

**Option B: Add the venv's bin to your PATH**

Simpler but couples your shell to the project's venv. Add to your shell config:

```bash
# macOS / Linux -- add to ~/.zshrc or ~/.bashrc
export PATH="/path/to/gourani/.venv/bin:$PATH"
```

```powershell
# Windows -- add to $PROFILE
$env:PATH = "C:\path\to\gourani\.venv\Scripts;$env:PATH"
```

Open a new terminal (or `source ~/.zshrc`) for the change to take effect.

---

## Hardware acceleration

Gourani auto-detects your hardware and uses the fastest available transcription
backend. No configuration needed -- it just does the right thing.

| Hardware | Backend | What happens |
|---|---|---|
| Apple Silicon (M1/M2/M3/M4, any variant) | `mlx-whisper` | Runs on Metal GPU via unified memory |
| NVIDIA GPU | `faster-whisper` + CUDA | Runs on GPU with float16 |
| CPU (any platform) | `faster-whisper` + INT8 | Runs on CPU with quantization |

On Apple Silicon, the GPU and CPU share the same memory pool (unified memory),
so the full 32GB (or whatever your Mac has) is available to the model without
any copying. This means you can run `large-v3` comfortably on a 32GB Mac.

To enable Apple Silicon GPU acceleration:

```bash
pip install gourani[apple]
```

This installs `mlx` and `mlx-whisper`. Without it, gourani falls back to
faster-whisper on CPU -- still works, just ~2-3x slower.

You can override the auto-detection:

```bash
gourani run ./interviews/ --whisper-backend mlx          # force MLX
gourani run ./interviews/ --whisper-backend faster-whisper # force CPU/CUDA
```

This is future-proof: any current or future Apple Silicon chip (M1 through
M4 Ultra and beyond) exposes the same Metal compute API that MLX targets.

---

## Usage

```bash
# Full pipeline: transcribe + analyse + output
gourani run ./interviews/ -o ./results/

# Project name defaults to the input folder name.
# Override with --project:
gourani run ./interviews/ -o ./results/ -p "Q1 Usability Study"

# Transcribe only (no LLM needed, no API key required)
gourani transcribe-only ./interviews/ -o ./results/

# Analyse existing transcripts (skip transcription)
gourani analyze ./results/raw_transcripts/ -o ./results/

# Options
gourani run ./interviews/ \
  --verbose \                  # detailed logging
  --no-pii \                   # skip PII removal
  --whisper-model medium.en \  # smaller/faster model
  --llm openai                 # use OpenAI instead of Anthropic
```

### Supported input files

| Type | Extensions |
|------|-----------|
| Audio | `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac` |
| Video | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` |
| Subtitles | `.srt`, `.vtt` |
| Documents | `.docx` (Teams transcript exports) |

Mix and match -- a folder can contain any combination. Files sharing the same
name stem (e.g. `interview_01.mp4` and `interview_01.srt`) are treated as one
session.

### Configuration

Copy `.env.example` to `.env` and set your API key. All settings can also be
set via environment variables (prefix `GOURANI_`) or a `gourani.toml` file:

```toml
[project]
project_name = "Mobile App Usability Study"

[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"

[whisper]
model = "medium.en"
device = "cpu"

[pii]
enabled = true
custom_names = ["Acme Corp", "Jane Doe"]
```

---

## Cross-platform notes

| | macOS | Linux | Windows |
|---|---|---|---|
| Python | Homebrew 3.12 (`/opt/homebrew/bin/python3.12`) | System or deadsnakes PPA | python.org installer |
| ffmpeg | `brew install ffmpeg` | `apt install ffmpeg` | winget/choco/manual |
| venv activation | `source .venv/bin/activate` | `source .venv/bin/activate` | `.venv\Scripts\activate` |
| File creation dates | Accurate (`st_birthtime`) | Falls back to modification date | Accurate (NTFS `st_ctime`) |
| Whisper GPU | Apple Silicon via MPS | CUDA (NVIDIA) | CUDA (NVIDIA) |

The pipeline is pure Python except for the ffmpeg dependency. Everything else
(faster-whisper, Presidio, Pydantic) installs from PyPI on all three platforms.

---

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=gourani

# Lint
ruff check .

# Type check
mypy gourani/
```
