# Transcript Coverage Feature

## Problem

Researchers using Bristlenose worry that the AI may have silently dropped important material during quote extraction. They can't verify completeness without re-reading the full transcript — which defeats the purpose of the tool.

## Solution

A collapsible "Transcript coverage" section at the end of the research report that:

1. Shows three percentages as a triage signal (in report / moderator / omitted)
2. Lists omitted participant speech so researchers can verify it's chaff
3. Collapses short fragments into a dense summary to reduce noise

## UX Design

### Section structure

The coverage section is a proper `<section>` with `<h2>` heading, same level as "User journeys":

```
Transcript coverage
───────────────────

78% in report · 14% moderator · 8% omitted

▶ Show omitted segments
```

The percentages serve as triage:
- **High "in report"** — reassuring, probably don't need to expand
- **High "moderator"** — self-awareness feedback (researcher talked a lot)
- **High "omitted"** — researcher should expand and review

### Expanded state

Clicking "Show omitted segments" expands to show per-session details:

```
▼ Show omitted segments

Session 1

  [p1 02:01]  No, for the hernia. For the hernia. Okay. Because it didn't heal...
  [p1 03:35]  So, I've got a series of messages that would all come together...

  Also omitted: Okay. (4×), Yeah. (2×)

Session 2

  Okay. (6×), Reload.

Session 3

  oh

Session 4

  [p4 01:22]  Add a shopping bag.

  Also omitted: Okay. (10×), Choose., Right., And..., Oh, yes.
```

### Content rules

- **Only participant speech** — moderator/observer speech is counted in the percentage but never shown in the review section
- **Segments ≤3 words** — collapsed into a comma-separated summary line with repeat counts (e.g., `Okay. (4×)`)
- **Segments >3 words** — shown in full with speaker code and timecode; timecode links to the transcript page
- **"Also omitted:" prefix** — only used when there are full segments above; if a session has only fragments, show them directly without the prefix
- **Styling** — omitted text in dark grey (not body black), transcript-style formatting (no stars, tags, or quote styling)

### Edge cases

- **0% omitted** — show "Nothing omitted — all participant speech is in the report."
- **No moderator identified** — show `0% moderator` (indicates self-recorded/think-aloud sessions)
- **Session with nothing omitted** — don't show that session in the expanded view

## Percentage calculation

All percentages are whole numbers (no decimals), based on word count:

```
total_words = participant_words + moderator_words + observer_words

pct_in_report = participant_words_in_quotes / total_words
pct_moderator = (moderator_words + observer_words) / total_words
pct_omitted = participant_words_not_in_quotes / total_words
```

**"In quotes" definition:** A transcript segment is considered "in quotes" if its timecode falls within the `start_timecode`–`end_timecode` range of any extracted quote.

## Implementation

### Data flow

This is a **render-time calculation** — no new pipeline stage needed. The data already exists:

1. `PipelineResult.raw_transcripts` — all transcript segments with timecodes and speaker codes
2. `PipelineResult.screen_clusters` + `theme_groups` — all extracted quotes with `start_timecode`/`end_timecode`
3. Speaker codes (`p*`, `m*`, `o*`) — already assigned by Stage 5b

### New module

`bristlenose/coverage.py`:

```python
@dataclass
class CoverageStats:
    pct_in_report: int  # 0-100
    pct_moderator: int  # 0-100
    pct_omitted: int    # 0-100
    omitted_by_session: dict[str, SessionOmitted]

@dataclass
class SessionOmitted:
    full_segments: list[OmittedSegment]  # >3 words
    fragments: list[tuple[str, int]]     # (text, count) pairs

@dataclass
class OmittedSegment:
    speaker_code: str
    timecode: str
    text: str

def calculate_coverage(
    transcripts: list[FullTranscript],
    quotes: list[ExtractedQuote],
) -> CoverageStats:
    ...
```

### Rendering

In `render_html.py`, add a new section at report end:

- Proper `<section>` with `<h2 id="transcript-coverage">` heading (same level as User Journeys)
- Percentages as paragraph content below heading
- `<details>` element for session details (collapsed by default)
- `<summary>` says "Show omitted segments"
- Body contains session-grouped omitted content
- Timecodes link to transcript pages (`transcript_{session_id}.html#t-{seconds}`)
- Add `.coverage-details` wrapper with muted text colour

### Files modified

1. **New:** `bristlenose/coverage.py` — calculation logic (`CoverageStats`, `SessionOmitted`, `OmittedSegment`, `calculate_coverage()`)
2. **New:** `bristlenose/theme/organisms/coverage.css` — styling for the disclosure section
3. **New:** `tests/test_coverage.py` — 14 tests covering percentage calculation, fragment threshold, repeat counting, edge cases
4. **Edit:** `bristlenose/stages/render_html.py` — added `transcripts` parameter, `_build_coverage_html()` function, coverage section after User Journeys, import for coverage module, CSS file added to `_THEME_FILES`
5. **Edit:** `bristlenose/pipeline.py` — pass transcripts to `render_html()` in `run()`, `run_analysis_only()`, `render_only()`

## Out of scope

- **Transcript page highlighting** — showing which parts of transcript became quotes (adds complexity, "find Waldo" UX problem)
- **Manual quote extraction** — selecting transcript text to add to report (scope creep, turns tool into editor)
- **Filler word tracking** — counting "um"s removed during quote cleanup (unknowable without diffing, different concern)
- **Per-participant breakdown** — aggregated project-level numbers are sufficient for triage

## Open questions

None — design validated against real data (ikea project trial run).

## Commit summary

**add transcript coverage section to research report**

Shows what participant speech wasn't extracted as quotes, helping researchers verify the AI didn't silently drop important material.

- Three-way percentage split: X% in report · Y% moderator · Z% omitted
- Proper `<section>` with `<h2>` heading (same level as User Journeys)
- Collapsible "Show omitted segments" disclosure for per-session details
- Full segments (>3 words) shown with speaker code and linked timecode
- Fragments (≤3 words) collapsed with repeat counts: `Okay. (4×)`
- Added to ToC Analysis column
- 14 tests covering calculation, thresholds, edge cases

## References

- Real output reviewed: 63% in report · 0% moderator · 37% omitted (ikea project trial run)
