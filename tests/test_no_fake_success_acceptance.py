"""End-to-end acceptance: the pipeline must never *fake* success.

The 7 May 2026 quality reset named the **fake-success-feedback** bug class —
a surface that signals done / complete / exported / applied while the artifact
doesn't exist or is empty (exports that don't export, "Analysed" with no
transcript, a report that renders an empty state on a completed run,
AutoCode buttons that can't produce work). The quality reset called for a
one-read audit of that class. This file is the *executable* form of that
audit: run the FULL pipeline on real inputs, across both cloud providers, over
each input format we advertise — and assert every success signal corresponds
to a real, non-empty artifact.

Why it's ``@pytest.mark.slow`` (skipped in CI): it calls real Claude / OpenAI
and, for the video leg, real Whisper transcription. CI has no API keys and no
model, so every case below **skips** there — it never fails CI. Run it locally,
deliberately, with keys set and the ``trial-runs/`` data present::

    BRISTLENOSE_ANTHROPIC_API_KEY=... BRISTLENOSE_OPENAI_API_KEY=... \
      .venv/bin/python -m pytest -m slow \
      tests/test_no_fake_success_acceptance.py -v

Inputs are real data under ``trial-runs/`` (gitignored) and each case
**skips if its input is absent**, so the file is safe to commit and run
anywhere. Do one ~5-min call and export it natively from each platform into
``trial-runs/format-acceptance/`` — same conversation, three formats, one
apples-to-apples format-parity proof:

  * ``zoom_vtt``   — Zoom native export ``zoom-transcript.vtt``    → ``s03`` subtitles
  * ``teams_docx`` — Teams native export ``teams-transcript.docx`` → ``s04`` docx
  * ``meet_docx``  — Google Meet (Doc → ``.docx``) ``meet-transcript.docx`` → ``s04`` docx
  * ``video``      — a clean unprocessed interview video (FOSSDA)  → transcription

We advertise ".docx from Zoom, Teams, or Google Meet" (README / manual) — but
note Zoom actually exports ``.vtt``, not ``.docx`` (only Teams and Meet-via-
Google-Docs produce ``.docx``). The ``.docx`` parser (``s04_parse_docx.py``) is
Teams-shaped with a plain-text fallback; the meet_docx leg is the real test of
whether Google Meet's ``.docx`` shape actually parses. Each leg activates when
its file lands in ``format-acceptance/``; otherwise it skips.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.output_paths import OutputPaths
from bristlenose.pipeline import Pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAL_RUNS = REPO_ROOT / "trial-runs"

# --- Real-data inputs (gitignored; each case skips if its file is absent) ---
# USER-SUPPLIED: the same ~5-min call, exported NATIVELY from each platform,
# dropped into trial-runs/format-acceptance/. Same content, three formats →
# apples-to-apples proof that every advertised input path produces a real,
# non-empty analysis (and never fakes success).
_FMT = TRIAL_RUNS / "format-acceptance"
ZOOM_VTT_INPUT = _FMT / "zoom-transcript.vtt"  # Zoom native export → s03 subtitles
TEAMS_DOCX_INPUT = _FMT / "teams-transcript.docx"  # Teams native export → s04 docx
MEET_DOCX_INPUT = _FMT / "meet-transcript.docx"  # Google Meet (Google Doc → .docx) → s04
# Clean unprocessed video → transcription path. FOSSDA is a known-good public
# dataset (already the perf baseline); swap for the call recording if wanted.
VIDEO_INPUT = TRIAL_RUNS / "fossda-opensource" / "01-bruce-perens.mp4"

INPUTS: dict[str, Path] = {
    "zoom_vtt": ZOOM_VTT_INPUT,
    "teams_docx": TEAMS_DOCX_INPUT,
    "meet_docx": MEET_DOCX_INPUT,
    "video": VIDEO_INPUT,
}

PROVIDER_KEY_ENV = {
    "anthropic": "BRISTLENOSE_ANTHROPIC_API_KEY",
    "openai": "BRISTLENOSE_OPENAI_API_KEY",
}


def _provider_key(provider: str) -> str:
    """The configured API key for ``provider`` (env / .env), or ''."""
    settings = BristlenoseSettings(llm_provider=provider)
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
    }[provider]


def _whisper_available() -> bool:
    """True if any Whisper backend can be imported (video leg only)."""
    for mod in ("mlx_whisper", "faster_whisper"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False


def _distinctive_word(text: str) -> str:
    """Longest 6+-letter alpha token in ``text`` — robust to HTML escaping."""
    words = re.findall(r"[A-Za-z]{6,}", text)
    return max(words, key=len) if words else ""


def _first_quote(result) -> object | None:
    """First quote found in any screen cluster (defensive against empties)."""
    for cluster in result.screen_clusters:
        if cluster.quotes:
            return cluster.quotes[0]
    return None


def _run_pipeline(input_file: Path, provider: str, tmp_path: Path):
    """Copy one real input into a temp project and run the full pipeline."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy2(input_file, input_dir / input_file.name)
    output_dir = input_dir / "bristlenose-output"

    settings = BristlenoseSettings(llm_provider=provider)
    pipeline = Pipeline(settings=settings, skip_confirm=True)
    result = asyncio.run(pipeline.run(input_dir, output_dir))
    return result, OutputPaths(output_dir, result.project_name)


def _assert_no_fake_success(result, out: OutputPaths) -> None:
    """Every success signal must map to a real, non-empty artifact."""
    # 1. No pipeline error / abandonment.
    assert result.pipeline_error == "", f"pipeline errored: {result.pipeline_error!r}"

    # 2. A transcript was actually produced (transcription OR subtitle/docx parse).
    assert result.raw_transcripts, "no raw transcripts produced"
    total_chars = sum(
        len(seg.text) for tr in result.raw_transcripts for seg in tr.segments
    )
    assert total_chars > 200, f"transcript suspiciously empty ({total_chars} chars)"

    # 3. PII stage produced cleaned transcripts (not silently skipped).
    assert result.clean_transcripts, "no clean transcripts — PII stage silently skipped?"

    # 4. Quotes were actually extracted — the headline fake-success is
    #    "Analysed" with zero quotes on a completed run.
    assert result.total_quotes > 0, "0 quotes extracted on a completed run"
    clustered = sum(len(c.quotes) for c in result.screen_clusters)
    assert clustered > 0, "quotes extracted but none placed in a cluster"

    # 5. Theming produced groups that actually contain quotes.
    assert result.theme_groups, "no theme groups"
    themed = sum(len(t.quotes) for t in result.theme_groups)
    assert themed > 0, "theme groups exist but contain no quotes"

    # 6. The report on disk is real and non-trivial — not an empty-state page.
    report = out.html_report
    assert report.exists(), f"report not written: {report}"
    html = report.read_text(encoding="utf-8")
    assert len(html) > 10_000, f"report suspiciously small ({len(html)} bytes)"

    # 7. The claimed quotes are actually IN the report — the number isn't a lie.
    quote = _first_quote(result)
    assert quote is not None, "no quote available to verify against the report"
    word = _distinctive_word(quote.text)
    assert word, f"quote has no distinctive word to check: {quote.text!r}"
    assert word.lower() in html.lower(), (
        f"a real extracted quote ({word!r}) is missing from the rendered report"
    )

    # 8. The markdown deliverable is written and non-empty.
    assert out.md_report.exists(), f"markdown report not written: {out.md_report}"
    assert out.md_report.stat().st_size > 200, "markdown report is empty"

    # 9. On-disk transcript files exist and are non-empty (no silent-skip).
    raw_dir = out.transcripts_raw_dir
    assert raw_dir.exists(), "transcripts-raw/ missing"
    raw_files = list(raw_dir.glob("*.txt")) + list(raw_dir.glob("*.md"))
    assert raw_files, "no raw transcript files written"
    assert any(f.stat().st_size > 100 for f in raw_files), "raw transcript files are empty"


@pytest.mark.slow
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("input_key", ["zoom_vtt", "teams_docx", "meet_docx", "video"])
def test_pipeline_never_fakes_success(
    provider: str, input_key: str, tmp_path: Path
) -> None:
    """Full pipeline on a real input + real provider must not fake success.

    2 providers × 4 input formats (Zoom .vtt, Teams .docx, Google Meet .docx,
    raw video) = 8 cases. Each self-skips when its API key, input file, or
    (video only) Whisper backend is unavailable — so this never fails in CI,
    only reports real regressions when run locally with the world present.
    """
    if not _provider_key(provider):
        pytest.skip(f"{PROVIDER_KEY_ENV[provider]} not set — {provider} unavailable")

    input_file = INPUTS[input_key]
    if not input_file.exists():
        pytest.skip(f"input absent: {input_file} (gitignored trial-runs data)")

    if input_key == "video" and not _whisper_available():
        pytest.skip("no Whisper backend (mlx_whisper / faster_whisper) for the video leg")

    result, out = _run_pipeline(input_file, provider, tmp_path)
    _assert_no_fake_success(result, out)
