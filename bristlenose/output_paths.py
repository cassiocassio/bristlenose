"""Output directory structure and path helpers.

This module defines the canonical output directory layout and provides
helpers for constructing paths consistently across all pipeline stages.

Layout (v2):
    output/
    ├── bristlenose-{slug}-report.html    # Main HTML report
    ├── bristlenose-{slug}-report.md      # Markdown report
    ├── people.yaml                        # Participant registry (user-editable)
    ├── assets/                            # Static assets
    │   ├── bristlenose-theme.css
    │   ├── bristlenose-logo.png
    │   ├── bristlenose-logo-dark.png
    │   ├── bristlenose-player.html
    │   └── thumbnails/                    # Video keyframe thumbnails
    │       ├── s1.jpg
    │       └── ...
    ├── sessions/                          # Per-session transcript pages
    │   ├── transcript_s1.html
    │   └── ...
    ├── transcripts-raw/                   # Raw transcript files
    │   ├── s1.txt
    │   ├── s1.md
    │   └── ...
    ├── transcripts-cooked/                # PII-redacted transcripts (if --redact-pii)
    │   ├── s1.txt
    │   ├── s1.md
    │   └── ...
    └── .bristlenose/                      # Internal/intermediate files
        ├── intermediate/
        │   ├── extracted_quotes.json
        │   ├── screen_clusters.json
        │   ├── theme_groups.json
        │   └── topic_boundaries.json
        └── temp/

Notes:
    - The Lévi-Strauss "raw/cooked" naming is intentional — researchers get it
    - Project slug is derived from project_name via slugify()
    - people.yaml has no prefix — it's the one file users actually edit
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bristlenose.utils.text import slugify


@dataclass
class OutputPaths:
    """Computed paths for all output files in a project.

    Instantiate with output_dir and project_name, then access paths as
    attributes. All paths are absolute.

    Example:
        paths = OutputPaths(output_dir, "My Research Project")
        paths.html_report  # → output_dir / "bristlenose-my-research-project-report.html"
        paths.assets_dir   # → output_dir / "assets"
    """

    output_dir: Path
    project_name: str

    def __post_init__(self) -> None:
        self._slug = slugify(self.project_name)

    # --- Main deliverables (root level) ---

    @property
    def html_report(self) -> Path:
        """Main HTML report: bristlenose-{slug}-report.html"""
        return self.output_dir / f"bristlenose-{self._slug}-report.html"

    @property
    def md_report(self) -> Path:
        """Markdown report: bristlenose-{slug}-report.md"""
        return self.output_dir / f"bristlenose-{self._slug}-report.md"

    @property
    def people_file(self) -> Path:
        """Participant registry: people.yaml (no prefix — user-editable)"""
        return self.output_dir / "people.yaml"

    @property
    def codebook_file(self) -> Path:
        """Codebook page: codebook.html (same level as report)"""
        return self.output_dir / "codebook.html"

    @property
    def analysis_file(self) -> Path:
        """Analysis page: analysis.html (same level as report)"""
        return self.output_dir / "analysis.html"

    # --- Asset directory ---

    @property
    def assets_dir(self) -> Path:
        """Static assets directory: assets/"""
        return self.output_dir / "assets"

    @property
    def css_file(self) -> Path:
        """Theme CSS: assets/bristlenose-theme.css"""
        return self.assets_dir / "bristlenose-theme.css"

    @property
    def logo_file(self) -> Path:
        """Logo (light): assets/bristlenose-logo.png"""
        return self.assets_dir / "bristlenose-logo.png"

    @property
    def logo_dark_file(self) -> Path:
        """Logo (dark): assets/bristlenose-logo-dark.png"""
        return self.assets_dir / "bristlenose-logo-dark.png"

    @property
    def logo_transparent_file(self) -> Path:
        """Logo (transparent): assets/bristlenose-logo-transparent.png"""
        return self.assets_dir / "bristlenose-logo-transparent.png"

    @property
    def logo_video_webm(self) -> Path:
        """Animated logo (WebM VP9 alpha): assets/bristlenose-alive.webm"""
        return self.assets_dir / "bristlenose-alive.webm"

    @property
    def logo_video_mov(self) -> Path:
        """Animated logo (HEVC alpha): assets/bristlenose-alive.mov"""
        return self.assets_dir / "bristlenose-alive.mov"

    @property
    def player_file(self) -> Path:
        """Video player page: assets/bristlenose-player.html"""
        return self.assets_dir / "bristlenose-player.html"

    @property
    def thumbnails_dir(self) -> Path:
        """Video thumbnails: assets/thumbnails/"""
        return self.assets_dir / "thumbnails"

    def thumbnail(self, session_id: str) -> Path:
        """Thumbnail for a session: assets/thumbnails/{session_id}.jpg"""
        return self.thumbnails_dir / f"{session_id}.jpg"

    # --- Sessions directory ---

    @property
    def sessions_dir(self) -> Path:
        """Per-session transcript pages: sessions/"""
        return self.output_dir / "sessions"

    def transcript_page(self, session_id: str) -> Path:
        """Transcript page for a session: sessions/transcript_{session_id}.html"""
        return self.sessions_dir / f"transcript_{session_id}.html"

    # --- Transcript directories ---

    @property
    def transcripts_raw_dir(self) -> Path:
        """Raw transcripts: transcripts-raw/"""
        return self.output_dir / "transcripts-raw"

    @property
    def transcripts_cooked_dir(self) -> Path:
        """PII-redacted transcripts: transcripts-cooked/"""
        return self.output_dir / "transcripts-cooked"

    def raw_transcript_txt(self, session_id: str) -> Path:
        """Raw transcript text: transcripts-raw/{session_id}.txt"""
        return self.transcripts_raw_dir / f"{session_id}.txt"

    def raw_transcript_md(self, session_id: str) -> Path:
        """Raw transcript markdown: transcripts-raw/{session_id}.md"""
        return self.transcripts_raw_dir / f"{session_id}.md"

    def cooked_transcript_txt(self, session_id: str) -> Path:
        """Cooked transcript text: transcripts-cooked/{session_id}.txt"""
        return self.transcripts_cooked_dir / f"{session_id}.txt"

    def cooked_transcript_md(self, session_id: str) -> Path:
        """Cooked transcript markdown: transcripts-cooked/{session_id}.md"""
        return self.transcripts_cooked_dir / f"{session_id}.md"

    # --- Internal directory ---

    @property
    def internal_dir(self) -> Path:
        """Internal/hidden directory: .bristlenose/"""
        return self.output_dir / ".bristlenose"

    @property
    def intermediate_dir(self) -> Path:
        """Intermediate JSON files: .bristlenose/intermediate/"""
        return self.internal_dir / "intermediate"

    @property
    def temp_dir(self) -> Path:
        """Temporary files: .bristlenose/temp/"""
        return self.internal_dir / "temp"

    def intermediate_json(self, filename: str) -> Path:
        """Intermediate JSON file: .bristlenose/intermediate/{filename}"""
        return self.intermediate_dir / filename

    # --- PII summary (still at root level) ---

    @property
    def pii_summary(self) -> Path:
        """PII redaction summary: pii_summary.txt"""
        return self.output_dir / "pii_summary.txt"

    # --- Directory creation ---

    def ensure_dirs(self) -> None:
        """Create all output directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_raw_dir.mkdir(parents=True, exist_ok=True)
        # Note: transcripts_cooked_dir only created when --redact-pii is used
        # Note: internal_dir/intermediate/temp created on demand

    def ensure_internal_dirs(self) -> None:
        """Create internal directories (.bristlenose/intermediate/, .bristlenose/temp/)."""
        self.intermediate_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)


# --- Relative path helpers for HTML cross-references ---


def report_to_asset(filename: str) -> str:
    """Relative path from report.html to an asset file."""
    return f"assets/{filename}"


def report_to_session(session_id: str) -> str:
    """Relative path from report.html to a session transcript page."""
    return f"sessions/transcript_{session_id}.html"


def session_to_report() -> str:
    """Relative path from session page back to report.html."""
    # Session pages are in sessions/, report is at root
    return "../bristlenose-{slug}-report.html"  # Caller must format with slug


def session_to_asset(filename: str) -> str:
    """Relative path from session page to an asset file."""
    return f"../assets/{filename}"
