# Bristlenose — Where I Left Off

Last updated: 1 Feb 2026 (v0.5.0, doctor + snap design session)

---

## Done

- [x] Full 12-stage pipeline (ingest → render)
- [x] HTML report with CSS theme (v5), clickable timecodes, popout video player
- [x] Sentiment histogram (horizontal bars, side-by-side AI + user-tag charts)
- [x] Friction points, user journeys
- [x] Favourite quotes (star, reorder, FLIP animation, CSV export)
- [x] Inline quote editing (pencil icon, contenteditable, localStorage persistence)
- [x] Tag system — AI-generated badges (deletable with restore) + user-added tags (auto-suggest, keyboard nav), localStorage persistence, CSV export with separate AI/User columns
- [x] Atomic design system (`bristlenose/theme/`) — tokens, atoms, molecules, organisms, templates; CSS concatenated at render time
- [x] JavaScript extraction — report JS broken out of `render_html.py` into 8 standalone modules (`bristlenose/theme/js/`): storage, player, favourites, editing, tags, histogram, csv-export, main; concatenated at render time mirroring the CSS pattern; `render_html.py` reduced from 1534 → 811 lines
- [x] `bristlenose render` command — re-render reports from intermediate JSON without retranscribing or calling LLMs
- [x] Apple Silicon GPU acceleration (MLX)
- [x] PII redaction (Presidio)
- [x] Cross-platform support (macOS, Linux, Windows)
- [x] AGPL-3.0 licence with CLA
- [x] Renamed gourani → bristlenose
- [x] Published to PyPI (0.1.0)
- [x] Published to GitHub (cassiocassio/bristlenose)
- [x] Homebrew tap (cassiocassio/homebrew-bristlenose) — `brew install cassiocassio/bristlenose/bristlenose` works
- [x] README with install instructions (brew, pipx, uv)
- [x] CONTRIBUTING.md with release process and design system documented
- [x] (0.3.2) Tag auto-suggest: don't offer tags the quote already has
- [x] Project logo in report header (top-right, copied alongside HTML)
- [x] (0.3.7) Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting; all stage files refactored to use it
- [x] (0.3.7) Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- [x] (0.3.7) Participant codes in transcript segments — `[p1]` instead of `[PARTICIPANT]` for researcher context
- [x] (0.3.7) Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes
- [x] (0.3.8) Timecode handling audit: verified full pipeline for sessions <1h and ≥1h, added edge-case tests
- [x] Sentiment histogram: tag text left-aligned, shared bar scale across AI + user charts, positive greens on top / negative reds below, negatives sorted ascending (worst near divider)
- [x] `bristlenose help` command — rich-formatted help with topics: commands, config, workflows; plus `--version` / `-V` flag
- [x] Man page (`man/bristlenose.1`) — full groff man page covering all commands, options, config, examples; included in sdist, Homebrew formula installs to `man1/`
- [x] (0.4.0) Dark mode — CSS `light-dark()` function, follows OS/browser preference by default, `color_scheme` config override (`auto`/`light`/`dark`), `<meta name="color-scheme">` tag, `<picture>` element for dark logo, print forced to light, histogram hard-coded colours replaced with CSS tokens, 17 tests
- [x] PII redaction default OFF — `pii_enabled: bool = False` in config; CLI flags `--redact-pii` (opt in) / `--retain-pii` (explicit default); replaced `--no-pii`; 3 tests
- [x] People file (participant registry) — `people.yaml` in output dir; Pydantic models (`PersonComputed`, `PersonEditable`, `PersonEntry`, `PeopleFile`); `bristlenose/people.py` (load, compute, merge, write, display name map); merge strategy preserves human edits across re-runs; display names in quotes/tables/friction/journeys in both markdown and HTML reports; `data-participant` HTML attributes kept as canonical `participant_id` for JS; 21 new tests (14 people, 3 PII, 2 models, 2 markdown)
- [x] Participant table redesign — columns now `ID | Name | Role | Start | Duration | Words | Source file` (was 9 cols, now 7); ID shows raw `p1`/`p2`/`p3`; Name shows `full_name` from people.yaml (pale-grey italic "Unnamed" placeholder when empty); Role moved next to Name; Date+Start merged into single Start column with macOS Finder-style relative dates (`Today at 16:59` / `Yesterday at 17:00` / `29 Jan 2026 at 20:56`); removed % Words and % Time; `format_finder_date()` helper in `utils/markdown.py` with 8 tests
- [x] `render --clean` accepted gracefully — flag is ignored with a reassuring message that render is always non-destructive (overwrites reports only)
- [x] Per-participant HTML transcript pages — `transcript_p1.html`, `transcript_p2.html` etc.; participant table ID column is a hyperlink; back button styled after Claude search (`← {project_name} Research Report`); timecodes clickable with video player; speaker names resolved (short_name → full_name → pid); prefers cooked transcripts over raw when both exist; `transcript.css` added to theme; only `storage.js` + `player.js` loaded (no favourites/editing/tags); 17 tests
- [x] Quote attribution links to transcripts — `— p1` at end of each quote is a hyperlink to `transcript_p1.html#t-{seconds}`, deep-linking to the exact segment; `.speaker-link` CSS in `blockquote.css` (inherits muted colour, accent on hover)

---

## Next up: CI/CD automation

These are ready to implement. Do them in order — each builds on the previous.

### 1. ✅ CI on every push/PR

Done — `.github/workflows/ci.yml`. Ruff and pytest are hard gates; mypy runs informational (`continue-on-error`) due to 9 pre-existing third-party SDK type errors.

### 2. ✅ Publish to PyPI on tagged release

Done — `.github/workflows/release.yml`. Triggers on `v*` tags, runs CI first, builds sdist + wheel, publishes via PyPI trusted publishing (OIDC, no token needed). Trusted publisher configured at pypi.org.

### 3. ✅ Auto-update Homebrew tap after PyPI publish

Done — `release.yml` dispatches to `cassiocassio/homebrew-bristlenose` after PyPI publish. The tap repo's `update-formula.yml` fetches the sdist sha256 from PyPI and patches the formula. Requires `HOMEBREW_TAP_TOKEN` secret (classic PAT with `repo` scope).

### 4. ✅ GitHub Release with changelog

Done — `release.yml` `github-release` job creates a GitHub Release on the tag with auto-generated release notes.

---

## Secrets management

Current state and planned improvements.

### Done

- [x] **GitHub token** — stored in macOS Keychain via `gh auth`, accessed by `gh` CLI and git-credential-manager
- [x] **PyPI token** — stored in macOS Keychain via `keyring set https://upload.pypi.org/legacy/ __token__`, picked up automatically by `twine upload`
- [x] **PyPI Trusted Publishing** — configured; `release.yml` publishes via OIDC, no token needed in CI or locally for releases
- [x] **`HOMEBREW_TAP_TOKEN`** — classic PAT with `repo` scope (no expiry), stored as a GitHub Actions secret in the bristlenose repo; used by `notify-homebrew` job to dispatch `repository_dispatch` to `cassiocassio/homebrew-bristlenose`

### Current (works but could be better)

- **Anthropic/OpenAI API keys** — shell env var (`ANTHROPIC_API_KEY`) set in shell profile, plus `.env` file in project root (gitignored). Standard approach, fine for local dev.

### To do

- [ ] **Bristlenose API keys → Keychain** — add optional `keyring` support in `config.py` so bristlenose can read `BRISTLENOSE_ANTHROPIC_API_KEY` from macOS Keychain (falling back to env var / `.env`). Would let users avoid plaintext keys on disk.

---

## Feature roadmap

Organised from easiest to hardest. The README has a condensed version; this is the full list.

### Trivial (hours each)

- [ ] Search-as-you-type filtering — filter visible quotes by text content
- [ ] Hide/show quotes — toggle individual quotes, persist state
- [ ] Keyboard shortcuts — j/k navigation, s to star, e to edit, / to search
- [ ] Timecodes: restore blue colour — currently showing visited-link colour; force `--bn-colour-accent` and drop the `[]` square brackets since the blue makes them visually distinct already
- [ ] User tag × button — vertically centre the close button optically (currently sits too low)
- [ ] AI badge × button — the circled × is ugly; restyle to match user tag delete or use a simpler glyph
- [ ] Indent tags — add left margin/padding so the badge row sits indented under the quote text
- [ ] Logo: slightly bigger — bump from 80px to ~100px
- [ ] JS: `'use strict'` — add to each JS module to catch accidental globals and silent errors
- [ ] JS: shared `utils.js` — extract duplicated quote-stripping regex (`QUOTE_RE` / `CSV_QUOTE_RE`) into a shared module
- [ ] JS: magic numbers → config — extract `150`ms blur delay, `200`ms animation, `250`ms FLIP duration, `2000`ms toast, `8` max suggestions, `48`px min input into a shared constants object
- [x] JS: histogram hardcoded colours — replaced inline `'#9ca3af'` / `'#6b7280'` with `var(--bn-colour-muted)` (done in v0.4.0 dark mode)
- [ ] JS: drop `execCommand('copy')` fallback — `navigator.clipboard.writeText` is sufficient for all supported browsers; remove deprecated fallback or gate behind a warning

### Small (a day or two each)

- [ ] Editable participant names in report — allow users to edit `full_name` directly in the HTML report participant table (currently shows pale-grey italic "Unnamed" placeholder when empty)
- [ ] Participant metadata: day of the week in recordings — Start column now shows date+time (Finder-style), but could also show day name (e.g. "Mon 29 Jan 2026 at 20:56")
- [ ] Reduce AI tag density — too many AI badges per quote; tune the LLM prompt or filter to show only the most relevant 2–3
- [ ] Sentiment & friction as standalone sections — currently listed under Themes in the TOC but they're not themes; give them their own subsection/heading level
- [ ] User-tags histogram: right-align bars — bars should grow from the same zero-x baseline as the AI sentiment chart so the two read side-by-side
- [ ] Clickable histogram bars — clicking a bar in sentiment or user-tags chart opens a filtered view showing only quotes with that tag/emotion
- [ ] Sticky header — move project name + logo into the sticky toolbar bar so they're always visible on scroll
- [ ] Burger menu — replace the export button bar with a dropdown/hamburger menu triggered from the logo; export favourites, export all, and room for future actions (settings, theme picker, etc.)
- [ ] Theme management in browser — create/rename/reorder/delete themes in the report, user-generated CSS themes (dark mode done; token architecture ready for custom themes)
- [ ] Dark logo — replace placeholder inverted image with a proper albino bristlenose pleco (transparent PNG, ~480x480, suitable licence)
- [ ] Lost quotes — surface quotes the AI didn't select, let users rescue them
- [x] Transcript linking — click a quote's `— p1` attribution to jump to that segment in the full transcript page (deep-link anchors `#t-{seconds}` on every segment)
- [ ] .docx export — export the report as a Word document
- [ ] Edit writeback — write inline corrections back to cooked transcript files
- [ ] JS: split `tags.js` (453 lines) — separate AI badge lifecycle, user tag CRUD, and auto-suggest UI into `ai-badges.js`, `user-tags.js`, `suggest.js`
- [ ] JS: explicit cross-module state — replace implicit globals (`userTags` read by `histogram.js`) with a shared namespace object (`bn.state.userTags`) or pass state through init functions
- [ ] JS: auto-suggest accessibility — add ARIA attributes (`role="combobox"`, `aria-expanded`, `aria-activedescendant`) so screen readers can navigate the tag suggest dropdown

### Medium (a few days each)

- [ ] Moderator identification and transcript page speaker styling (see design notes below)
- [ ] LLM name/role extraction from transcripts — auto-populate `people.yaml` editable fields (see design notes below)
- [ ] Multi-participant sessions — handle recordings with more than one interviewee
- [ ] Speaker diarisation improvements — better accuracy, manual correction UI
- [ ] Batch processing dashboard — progress bars, partial results, resume interrupted runs
- [ ] JS tests — add lightweight DOM-based tests (jsdom or Playwright) covering tag persistence, CSV export output, favourite reordering, and edit save/restore

### `bristlenose doctor` and dependency UX (designed, not yet implemented)

Full design doc: `docs/design-doctor-and-snap.md`

- [ ] `bristlenose doctor` command — seven checks (FFmpeg, backend, model, API key, network, PII, disk)
- [ ] Pre-flight gate on `run`/`transcribe-only`/`analyze` — catches problems before slow work starts
- [ ] First-run auto-doctor — runs automatically on first invocation, sentinel at `~/.config/bristlenose/.doctor-ran`
- [ ] Install-method-aware fix messages — detect snap/brew/pip, show tailored install instructions
- [ ] API key validation in pre-flight — cheap API call to catch expired/revoked keys upfront
- [ ] Whisper model cache check — detect whether model is cached without triggering download
- [ ] `--prefetch-model` flag — download Whisper model and exit (for slow connections, CI setups)
- [ ] Homebrew formula: add `post_install` for spaCy model download, improve caveats

### Packaging (partially done)

- [x] PyPI (`pipx install bristlenose`)
- [x] Homebrew tap (`brew install cassiocassio/bristlenose/bristlenose`)
- [ ] Snap for Ubuntu/Linux (`snap install bristlenose --classic`) — designed, not yet implemented. Full design doc: `docs/design-doctor-and-snap.md`. Classic confinement, ~150 MB full-featured snap, GitHub Actions CI, channels (edge/beta/candidate/stable). Key decisions: bundle FFmpeg + spaCy model + all ML deps; no torch needed on Linux (faster-whisper uses ctranslate2). Estimated snap size ~130-160 MB compressed.
- [ ] Windows installer (winget or similar)

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — read from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`); the only file to edit when releasing |
| `bristlenose/cli.py` | Typer CLI entry point (`run`, `transcribe-only`, `analyze`, `render`) |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator (full run, transcribe-only, analyze-only, render-only) |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/render_html.py` | HTML report renderer — loads CSS + JS from theme/, all interactive features |
| `bristlenose/theme/` | Atomic CSS design system (tokens, atoms, molecules, organisms, templates) |
| `bristlenose/theme/js/` | Report JavaScript modules (storage, player, favourites, editing, tags, histogram, csv-export, main) — concatenated at render time |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection |
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR; also called by release.yml via workflow_call |
| `.github/workflows/release.yml` | Release pipeline: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of the tap repo's workflow (authoritative copy is in homebrew-bristlenose) |
| `CONTRIBUTING.md` | CLA, code style, design system docs, full release process and cross-repo topology |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap repo:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions
- **Tap workflow runs:** https://github.com/cassiocassio/homebrew-bristlenose/actions
- **PyPI trusted publisher settings:** https://pypi.org/manage/project/bristlenose/settings/publishing/
- **Repo secrets:** https://github.com/cassiocassio/bristlenose/settings/secrets/actions

---

## Design notes: LLM name/role extraction (stretch goal)

This feature auto-populates `people.yaml` editable fields (`full_name`, `short_name`, `role`) by analysing raw transcripts with an LLM. It builds on the existing people file infrastructure.

### Architecture

- **New file**: `bristlenose/stages/extract_names.py`
- **Config flag**: `llm_extract_names: bool = False` in `bristlenose/config.py` (off by default — requires internet)
- **CLI flag**: `--extract-names` on the `run` command (opt in)
- **Pipeline position**: after stage 6 (merge transcript) and before people file compute/merge. The LLM reads raw transcripts, not PII-redacted ones, because names ARE the PII we want here

### How it works

1. For each session, send the raw transcript (or first N minutes) to the LLM
2. Prompt asks: "Extract the participant's name and role/occupation if mentioned in conversation"
3. LLM returns structured output: `{"full_name": "Sarah Jones", "short_name": "Sarah", "role": "Product Manager"}`
4. Results are passed to `merge_people()` — **only pre-populate fields that are currently empty**. If the user has already set a `short_name`, the LLM result is discarded for that field
5. This means: first run auto-fills; user edits override; subsequent runs don't clobber

### Key design decisions

- **Only fill empty fields**: human edits always win. The LLM is a convenience, not authoritative
- **Off by default**: this feature requires internet (LLM API call). The long-term vision is fully local operation ("works on a freelancer's laptop on a desert island"). When a capable local model is available, this could become default-on
- **Raw transcript input**: the LLM needs to see actual names to extract them. If PII redaction runs first, names are gone. Pipeline ordering matters
- **Graceful degradation**: if the LLM can't find a name (e.g., participant never introduces themselves), fields stay empty. The user can still set them manually in `people.yaml` or the future web UI
- **Per-session, not per-project**: each transcript is processed independently. No cross-session name matching (a participant might give different names in different sessions — the human resolves this)

### Future considerations

- **Local models**: when a local LLM (MLX, llama.cpp) can do reliable name extraction, make it the default path and remove the internet dependency
- **Web UI**: the planned web interface for editing `people.yaml` should show LLM-suggested names as pre-filled defaults that the user confirms or corrects
- **Confidence scores**: the LLM could return confidence, and low-confidence extractions could be flagged for review rather than auto-populated
- **⚠️ Internet required**: this is one of several features that need API access (speaker identification LLM pass is another). All such features should be clearly flagged and optional

---

## Design notes: Moderator identification and transcript page speaker styling

Transcript pages currently show every segment as the same speaker (`p1:`) because the `.txt` files store `[p1]` for all segments — the researcher/participant role distinction is lost when writing to disk. This needs to change before multi-speaker transcripts can render properly.

### The problem

In a real user research interview there are (at least) two speakers: a **moderator** (the researcher asking questions) and a **participant** (the user being interviewed). Currently:

- Speaker diarisation labels everyone as participants (`p1`, `p2`...)
- The `SpeakerRole` enum exists in models (`PARTICIPANT` / `RESEARCHER`) and is used during the pipeline
- But when transcripts are written to `.txt` files, only the participant code `[p1]` is stored — the role is discarded
- When transcript pages load from disk, all segments look the same

### What needs to happen

#### 1. Moderator identity in `people.yaml`

Moderators need entries in `people.yaml` with a distinct code scheme. Options to decide:

- **`m1`, `m2`** — clear prefix distinction from `p1`, `p2`
- **`moderator`** — single code if there's always one researcher (but some studies have two)
- **`r1`, `r2`** — "researcher" prefix

The `PersonEditable` model already has `full_name`, `short_name`, `role` — moderators would use the same fields. The `role` field could default to "Moderator" for these entries.

#### 2. Role preserved in `.txt` files

The canonical `.txt` format needs to encode who is the moderator vs participant. Options:

- **Extend the `[p1]` code** — use `[m1]` for moderator segments: `[00:16] [m1] So tell me about your experience...`
- **Add a role marker** — `[00:16] [p1:researcher] ...` (more explicit but noisier)
- Simplest: just use the `m1`/`m2` prefix convention — the parser already reads the code between `[]`, and anything not starting with `p` would be a non-participant

#### 3. Transcript page visual treatment

The moderator's questions should be visually distinct — they're context, not evidence. Design direction from user research practice:

- **Moderator lines are structural headers** — a good moderator speaks ~20% of the time, so their questions naturally break the participant's responses into chunks
- **Heavier/darker styling for moderator** — bold or semi-bold, slightly larger, acting as section breaks
- **Participant text flows beneath** — lighter weight, the "body text" of each Q&A block
- Think of it as a **Q&A layout**: moderator question as a bold heading, followed by the participant's response paragraphs

This is the opposite of what you might expect (usually the important content is bold) — but in research the moderator's words are scaffolding and the participant's words are the data. The moderator lines stand out as **structural markers** that help you navigate, while the participant's words are what you actually read.

#### 4. CSS classes needed

```css
.segment-moderator { font-weight: 600; /* or 700 */ }
.segment-participant { /* default weight, the readable body */ }
```

Possibly with spacing: more margin-top before a moderator segment to create visual "question blocks".

### Blockers

- **No multi-speaker test data** — current test recordings are single-person. Need a real two-person interview (moderator + participant) flowing through the full pipeline before we can validate the design
- **Speaker diarisation → role assignment** — the pipeline currently assigns `PARTICIPANT` / `RESEARCHER` roles during stage 5 (identify speakers), but this distinction doesn't survive to disk. Need to verify the role assignment logic works correctly before persisting it
- **Parser changes** — `load_transcripts_from_dir()` needs to handle moderator codes (`m1` etc.) and return the role information so the transcript page renderer can apply different CSS classes

### Dependencies

- Depends on having real multi-speaker test data
- Related to "Multi-participant sessions" TODO item
- Related to "Speaker diarisation improvements" TODO item
- LLM name extraction could auto-populate moderator names too
