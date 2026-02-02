# HTML Report — Design and Implementation Notes

Reference doc for the generated HTML report and per-participant transcript pages. Covers interactive features, JS modules, CSS architecture, and rendering pipeline.

## People file (participant registry)

`people.yaml` lives in the output directory. It tracks every participant across pipeline runs.

- **Models**: `PersonComputed` (refreshed each run) + `PersonEditable` (preserved across runs) → `PersonEntry` → `PeopleFile` — all in `bristlenose/models.py`
- **Core logic**: `bristlenose/people.py` — load, compute, merge, write, build display name map, extract names from labels, auto-populate names, suggest short names
- **Merge strategy**: computed fields always overwritten; editable fields always preserved; new participants added with empty defaults; old participants missing from current run are **kept** (not deleted)
- **Display names**: `short_name` → used as display name in quotes/friction/journeys. `full_name` → used in participant table Name column. Resolved at render time only — canonical `participant_id` (p1, p2) stays in all data models and HTML `data-participant` attributes. Display names are cosmetic
- **Participant table columns**: `ID | Name | Role | Start | Duration | Words | Source file`. ID shows raw `participant_id`. Name column has pencil icon for inline editing (see "Name editing in HTML report" below). Start uses macOS Finder-style relative dates via `format_finder_date()` in `utils/markdown.py`
- **Pipeline wiring**: `run()` and `run_transcription_only()` compute+write+auto-populate; `run_analysis_only()` and `run_render_only()` load existing for display names only
- **Key workflows**:
  - User edits `short_name` / `full_name` in `people.yaml` → `bristlenose render` → report uses new names
  - User edits name in HTML report → localStorage → "Export names" → paste YAML into `people.yaml` → `bristlenose render`
  - Full pipeline run auto-extracts names from LLM + speaker label metadata → auto-populates empty fields
- **YAML comments**: inline comments added by users are lost on re-write (PyYAML limitation, documented in file header)

### Auto name/role extraction

Stage 5b (speaker identification) extracts participant names and job titles alongside role classification — no extra LLM call.

- **LLM extraction**: `SpeakerRoleItem` in `bristlenose/llm/structured.py` has optional `person_name` and `job_title` fields (default `""`). The Stage 5b prompt in `prompts.py` asks the LLM to extract these from self-introductions. `identify_speaker_roles_llm()` in `identify_speakers.py` returns `list[SpeakerInfo]` (dataclass: `speaker_label`, `role`, `person_name`, `job_title`)
- **Metadata extraction**: `extract_names_from_labels()` in `people.py` harvests real names from `speaker_label` on `TranscriptSegment` — works for Teams/DOCX/VTT sources where labels are real names (e.g. "Sarah Jones"), skips generic labels ("Speaker A", "SPEAKER_00", "Unknown")
- **Auto-populate**: `auto_populate_names()` fills empty `full_name` (LLM > label metadata) and `role` (LLM only). Never overwrites user edits
- **Short name suggestion**: `suggest_short_names()` auto-fills `short_name` from first token of `full_name`. Disambiguates collisions: "Sarah J." vs "Sarah K." when two participants share a first name
- **Pipeline wiring**: `run()` collects `SpeakerInfo` from Stage 5b → calls `extract_names_from_labels()` + `auto_populate_names()` + `suggest_short_names()` after `merge_people()` and before `write_people_file()`. `run_transcription_only()` uses label extraction only (no LLM)

### Moderator identification and speaker codes

Within each session, speakers are assigned **speaker codes** that distinguish moderators from participants. This is Phase 1 — per-session only, no cross-session moderator linking.

- **Code scheme**: `p1` = participant (uses session's participant_id), `m1`/`m2` = moderator(s) (researcher role), `o1` = observer. A session's `.txt` file contains segments from all speakers: `[00:16] [m1] Can you tell me...` / `[00:28] [p1] Yeah I've been using...`
- **Model field**: `TranscriptSegment.speaker_code: str = ""` — per-segment speaker identity. Default empty string for backward compat (existing code that doesn't set it falls back to `transcript.participant_id`)
- **Assignment**: `assign_speaker_codes(participant_id, segments)` in `identify_speakers.py` — called after Stage 5b role classification. Groups segments by `speaker_label`, maps each label to a code based on its `speaker_role` (RESEARCHER → m1/m2, OBSERVER → o1, PARTICIPANT/UNKNOWN → session pid). Returns `dict[str, str]` (label → code) for people-file wiring
- **Disk format**: `write_raw_transcripts()` and `write_cooked_transcripts()` now write `seg.speaker_code` instead of `transcript.participant_id` for the bracket token. File is still named `p1_raw.txt` (session identity), but contains `[m1]` and `[p1]` segments
- **Parser**: `load_transcripts_from_dir()` recognises `[m1]` → `speaker_role=RESEARCHER, speaker_code="m1"`, `[o1]` → `speaker_role=OBSERVER, speaker_code="o1"`, `[p1]` → `speaker_code="p1"` (role stays UNKNOWN for backward compat with old files)
- **People entries**: `compute_participant_stats()` in `people.py` creates `PersonComputed` entries for moderator/observer codes found in segments, alongside the session participant entry. Moderators get full `PersonEntry` in `people.yaml` with editable name/role fields
- **Name auto-population**: Pipeline collects `SpeakerInfo` for both participants and researchers, keyed by their speaker code (not just session pid). Moderator names and job titles populate into `m1`/`m2` people entries
- **Transcript page rendering**: `_render_transcript_page()` now resolves speaker name **per-segment** using `seg.speaker_code` (instead of once per page). Adds `.segment-moderator` CSS class to researcher segments
- **CSS**: `.segment-moderator .segment-body` and `.segment-moderator .segment-speaker` use `--bn-colour-muted` — moderator text is visually receded so participant answers stand out
- **Backward compat**: Old `.txt` files with `[p1]` for all segments continue to work — all segments get `speaker_role=UNKNOWN`, no `.segment-moderator` class, rendered identically to before
- **Phase 2 (not yet implemented)**: Cross-session moderator linking (`same_as` field in people.yaml), web UI for declaring "m1 in sessions 1,2,4 = same person", aggregated moderator stats
- **Tests**: `tests/test_moderator_identification.py` — 21 tests: `assign_speaker_codes()` (6 cases), transcript round-trip (5), backward compat (2), people stats (2), HTML rendering (5), CSS (1)

### Name editing in HTML report

Participant names and roles are editable inline in the HTML report.

- **Pencil icon**: `.name-pencil` button in Name and Role table cells, visible on row hover. Same contenteditable lifecycle as quote editing (Enter/Escape/click-outside)
- **JS module**: `bristlenose/theme/js/names.js` — `initNames()` in boot sequence (after `initSearchFilter()`). Uses `createStore('bristlenose-names')` for localStorage. Shape: `{pid: {full_name, short_name, role}}`
- **Live DOM updates**: `updateAllReferences(pid)` propagates name changes to participant table Name and Role cells only. Quote attributions (`.speaker-link`) intentionally show raw pids — not updated by JS (anonymisation boundary)
- **Short name auto-suggest**: JS-side `suggestShortName()` mirrors the Python heuristic — when `full_name` is edited and `short_name` is empty, auto-fills with first name
- **YAML export**: "Export names" toolbar button copies edited names as a YAML snippet via `buildNamesYaml()` + `copyToClipboard()`. User pastes into `people.yaml`
- **Reconciliation**: `reconcileWithBaked()` on page load prunes localStorage entries that match the baked-in `BN_PARTICIPANTS` data (user already pasted edits and re-rendered)
- **BN_PARTICIPANTS**: JSON blob emitted in the HTML `<script>` block containing `{pid: {full_name, short_name, role}}` from people.yaml at render time. Used by JS for reconciliation and display name resolution
- **CSS**: `molecules/name-edit.css` — `.name-cell`, `.role-cell` positioning; `.name-pencil` hover reveal; `.unnamed` placeholder style; `.edited` indicator; print hidden

## Editable section/theme headings

Section titles, section descriptions, theme titles, and theme descriptions are editable inline in the HTML report — same UX as quote editing.

- **Markup**: `<span class="editable-text" data-edit-key="{anchor}:title|desc" data-original="...">` wraps the text inside `<h3>` (titles) and `<p class="description">` (descriptions). Pencil button (`.edit-pencil-inline`) sits inline after the text
- **ToC entries**: Section and theme titles in the Table of Contents are also editable (same `data-edit-key`). Sentiment and Friction points are NOT editable
- **Bidirectional sync**: Editing a title in the ToC updates the heading, and vice versa. Uses `_syncSiblings()` — all `.editable-text` spans sharing the same `data-edit-key` are kept in sync
- **Storage**: Reuses the same `bristlenose-edits` localStorage store as quote edits. Keys: `section-{slug}:title`, `section-{slug}:desc`, `theme-{slug}:title`, `theme-{slug}:desc`
- **JS**: `initInlineEditing()` in `editing.js`, called from `main.js` boot sequence after `initEditing()`. Separate `activeInlineEdit` tracker from `activeEdit` (quote editing)
- **CSS**: `.edit-pencil-inline` in `atoms/button.css` (static inline positioning); `.editable-text.editing` and `.editable-text.edited` in `molecules/quote-actions.css`
- **Tests**: `tests/test_editable_headings.py` — 19 tests covering markup, data attributes, CSS, JS bootstrap, ToC editability, and sentiment exclusion

## Report header and toolbar

The HTML report header uses a two-column flexbox layout with the logo, logotype, and project name on the left, and the document title and metadata on the right.

- **Header structure**: `.report-header` flex container → `.header-left` (logo + logotype + project name) + `.header-right` (doc title + meta line)
- **Logo**: fish image flipped horizontally (`transform: scaleX(-1)`) so it faces into the page from the right. 80px wide, positioned with `top: 1.7rem` to align nose near the text baseline. Dark mode uses `<picture>` with separate dark logo
- **Logotype**: "Bristlenose" (capitalised) in semibold 1.35rem, followed by an em-space (`\u2003`), then project name in regular weight at same size
- **Meta line**: session/participant count and Finder-style date in muted 0.82rem
- **Spacing**: `.report-header + hr` has tightened margins (0.75rem top/bottom); toolbar has negative top margin (-0.5rem) to pull it closer to the rule
- **CSS**: `atoms/logo.css` — header layout, logotype, project name, doc title, meta, print overrides
- **Shared layout**: both report and transcript pages use the same header structure (logotype + project name). The transcript page additionally has a back-link nav and `<h1>` heading below

### Sticky toolbar

Below the header rule, a sticky toolbar holds the view-switcher dropdown and export buttons.

- **CSS**: `organisms/toolbar.css` — `.toolbar` (sticky, flex, right-aligned), `.view-switcher-btn`, `.view-switcher-arrow` (SVG chevron), `.view-switcher-menu` (dropdown), `.menu-icon` (invisible spacers for alignment)
- **View switcher**: borderless dropdown button showing current view ("All quotes" default). Three views: `all` (show everything), `favourites` (show only starred quotes), `participants` (show only participant table)
- **JS**: `view-switcher.js` — `initViewSwitcher()` handles menu toggle, item selection, section visibility. Sets `currentViewMode` global (defined in `csv-export.js`) so the CSV export button adapts
- **Export buttons**: single `#export-csv` button (Copy CSV) with inline SVG clipboard icon; `#export-names` button (Export names) shown only in participants view. Both swap visibility based on view mode
- **Menu items**: "All quotes" (no icon), "★ Favourite quotes" (star icon), "⊞ Participant data" (grid icon). Items without icons get `<span class="menu-icon">&nbsp;</span>` spacers for text alignment
- **Boot order**: `initViewSwitcher()` runs after `initCsvExport()` in `main.js` because it depends on `currentViewMode`

### Search filter

Search-as-you-type filtering for report quotes. Collapsed by default to a magnifying glass icon on the left side of the toolbar.

- **HTML**: search container (`#search-container`) with toggle button (`#search-toggle`, SVG magnifying glass) and field wrapper (`.search-field` containing `#search-input` + `#search-clear`). Emitted in `render_html.py` before the view-switcher in the toolbar
- **Expand/collapse**: clicking the icon toggles `.expanded` class on the container, showing/hiding the field. Escape key clears and collapses. Clicking icon when expanded+empty also collapses
- **Clear button**: `#search-clear` (SVG × icon) positioned inside the input field (right-aligned via `position: absolute` inside `.search-field` wrapper). Appears when query is non-empty (`.has-query` class on container). Clears input and re-focuses for a new query
- **Min 3 chars**: no filtering until query >= 3 characters
- **Match scope**: `.quote-text` content, `.speaker-link` text, `.badge` text (skipping `.badge-add`). Case-insensitive substring match via `indexOf()`
- **Yellow highlights**: matched substrings in `.quote-text` wrapped in `<mark class="search-mark">` with `--bn-colour-highlight` background (soft yellow in light mode, amber in dark). `_highlightMatches()` uses a TreeWalker to wrap text nodes; `_clearHighlights()` unwraps on each new query
- **Search overrides view mode**: an active query always searches across ALL quotes regardless of the view-switcher state (all/favourites). Researchers working across 10–20 hours of interviews need to find any idea, verb, name, or product across all extracted quotes. When the query is cleared, the view-switcher state is restored
- **View-switcher label override**: during active search, the view-switcher button shows the match count ("7 matching quotes" / "1 matching quote" / "No matching quotes") via `_overrideViewLabel()`. Puts the count right next to the "Copy CSV" button. Original label saved in `_savedViewLabel` and restored when search clears
- **ToC + Participants hiding**: `_setNonQuoteVisibility('none')` hides `.toc-row` and the Participants section during active search. Restored to `display: ''` when search clears
- **Section hiding**: `_hideEmptySections()` hides outer `<section>` elements (and preceding `<hr>`) when all child blockquotes are hidden. `_hideEmptySubsections()` hides individual h3+description+quote-group clusters within a section. Only targets sections with `.quote-group` (skips Participants, Sentiment, Friction, Journeys)
- **CSV export filtering**: `buildCsv()` in `csv-export.js` skips blockquotes with `style.display === 'none'` — "Copy CSV" exports only visible (matching) quotes during an active search
- **View mode hook**: `_onViewModeChange()` (defined in `search.js`) called from `view-switcher.js` `_applyView()` — hides search in participants mode, re-applies filter or restores view mode otherwise. The call in `view-switcher.js` is guarded with `typeof _onViewModeChange === 'function'` so transcript pages (which don't load search.js) don't error
- **Debounce**: 150ms debounce on input handler via `setTimeout`
- **CSS**: `molecules/search.css` — `.search-container`, `.search-toggle`, `.search-field` (relative wrapper, hidden until `.expanded`), `.search-input` (right padding for clear button), `.search-clear` (absolute right inside field, hidden until `.has-query`), `.search-mark` (highlight background)
- **Colour token**: `--bn-colour-highlight` in `tokens.css` — `#fef08a` (light) / `light-dark(#fef08a, #854d0e)` (dark)
- **JS**: `js/search.js` — `initSearchFilter()` in boot sequence (after `initViewSwitcher()`, before `initNames()`)
- **Print**: hidden automatically (`.toolbar { display: none }` in `print.css`)
- **Tests**: `tests/test_search_filter.py` — 20 tests covering HTML structure (clear button, field wrapper), CSS output (clear, field, highlight token, search-mark), JS bootstrap, transcript exclusion

### Table of Contents

The ToC row (`.toc-row` flexbox) shows up to three navigation columns:

- **Sections** — screen-specific findings (editable titles with pencil icons)
- **Themes** — thematic clusters (editable titles with pencil icons)
- **Analysis** — Sentiment, Tags, Friction points, User journeys (not editable, plain links)

## Page footer

A minimal colophon at the bottom of every generated page (report + transcript pages): "Bristlenose" logotype + "version X.Y.Z" linking to the GitHub repo.

- **HTML**: `_footer_html()` helper in `render_html.py` — renders a `<footer class="report-footer">` after `</article>` on both report and transcript pages. Version string imported from `bristlenose.__version__` (local import inside the helper)
- **CSS**: `atoms/footer.css` — `.report-footer` (max-width aligned with article, top border, 0.72rem muted text), `.footer-logotype` (semibold), `.footer-version` (subtle link: muted colour, no underline, underline on hover, `:visited` locked to muted)
- **Print**: `templates/print.css` locks footer link to muted colour
- **Link**: `https://github.com/cassiocassio/bristlenose`

## Timecode typography

Timecodes use a two-tone treatment: blue digits (`--bn-colour-accent`) with muted grey brackets (`--bn-colour-muted`). This makes the actionable timecode scannable while the `[]` brackets provide genre context (established subtitle/transcription convention).

- **CSS**: `atoms/timecode.css` — `a.timecode` and `span.timecode` both get accent colour; `a.timecode:visited` forced to accent (prevents browser default purple); `.timecode-bracket` gets muted colour
- **Specificity overrides**: `organisms/blockquote.css` has `blockquote .timecode` and `.rewatch-item .timecode` rules that must also use `--bn-colour-accent` (not muted) — the bracket spans handle the muting
- **HTML helper**: `_tc_brackets(tc)` in `render_html.py` wraps digits in bracket spans: `<span class="timecode-bracket">[</span>00:42<span class="timecode-bracket">]</span>`
- **Applied everywhere**: report quotes, transcript segments, rewatch items — all 6 rendering sites use `_tc_brackets()`

## Quote card layout (hanging indent)

Report quotes use a flexbox hanging-indent layout: timecodes sit in a left gutter column, quote text + speaker + badges flow indented beside them. This makes timecodes scannable as a vertical column.

- **HTML structure**: `<div class="quote-row">` contains the `.timecode` and `<div class="quote-body">` (quote text, speaker, badges)
- **CSS**: `blockquote .quote-row` (`display: flex; gap: 0.5rem; align-items: baseline`), `.quote-body` (`flex: 1; min-width: 0`)
- **Transcript pages**: use the same layout — `.transcript-segment` is also `display: flex` with `.segment-body` (`flex: 1`)
- **Timecode** is `flex-shrink: 0` so it never wraps or compresses

## Quote attribution and anonymisation boundary

Quote attributions in the main report intentionally show **raw participant IDs** (`— p1`, `— p2`) instead of display names. This is the anonymisation boundary: when researchers copy quotes to external tools (Miro, presentations, etc.), the IDs protect participant identity.

- **Report quotes**: `_format_quote_html()` uses `pid_esc` for the `.speaker-link` text. `names.js` `updateAllReferences()` does NOT update `.speaker-link` text. Attribution uses `&nbsp;` around the em-dash (`"…text"&nbsp;—&nbsp;p1`) to prevent widowing at line breaks
- **Transcript pages**: use display names (`short_name` → `full_name` → `pid`) since these are private to the researcher
- **Participant table**: Name column shows `full_name` (editable); ID column shows raw `p1`/`p2` as a link to the transcript page

## PII redaction

PII redaction is **off by default** (transcripts retain PII). Opt in with `--redact-pii`.

- **Config**: `pii_enabled: bool = False` in `bristlenose/config.py`
- **CLI flags**: `--redact-pii` (opt in) / `--retain-pii` (explicit default, redundant). Mutually exclusive
- When off: transcripts pass through as `PiiCleanTranscript` wrappers, no `cooked_transcripts/` directory written

## Per-participant transcript pages

Each participant gets a dedicated HTML page (`transcript_p1.html`, etc.) showing their full transcript with clickable timecodes. Generated at the end of `render_html()`.

- **Data source**: prefers `cooked_transcripts/` (PII-redacted) over `raw_transcripts/`. Uses `load_transcripts_from_dir()` from `pipeline.py` (public function, formerly `_load_transcripts_from_dir`)
- **Page heading**: `{pid} {full_name}` (e.g. "p1 Sarah Jones") or just `{pid}` if no name
- **Speaker name per segment**: resolved as `short_name` → `full_name` → `pid` via `_resolve_speaker_name()` in `render_html.py`
- **Back button**: `← {project_name} Research Report` linking to `research_report.html`, styled muted with accent on hover, hidden in print
- **JS**: `storage.js` + `player.js` + `transcript-names.js` — no favourites/editing/tags modules. `transcript-names.js` reads localStorage name edits (written by `names.js` on the report page) and updates the heading + speaker labels on load
- **Name propagation**: `transcript-names.js` reads `bristlenose-names` localStorage store on page load; updates `<h1 data-participant>` heading and `.segment-speaker[data-participant]` labels. Read-only — no editing UI on transcript pages
- **Participant table linking**: ID column (`p1`, `p2`) is a hyperlink to the transcript page
- **Quote attribution linking**: `— p1` at end of each quote in the main report links to `transcript_p1.html#t-{seconds}`, deep-linking to the exact segment. `.speaker-link` CSS in `blockquote.css` (inherits muted colour, accent on hover)
- **Segment anchors**: each transcript segment has `id="t-{int(seconds)}"` for deep linking from quotes
- **CSS**: `transcript.css` in theme templates (back button, segment layout, meta styling); `.speaker-link` in `organisms/blockquote.css`
