# Bristlenose — Where I Left Off

Last updated: 3 Feb 2026 (v0.6.11, Ollama local LLM support)

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
- [x] JavaScript extraction — report JS broken out of `render_html.py` into standalone modules (`bristlenose/theme/js/`): storage, player, favourites, editing, tags, histogram, csv-export, view-switcher, search, names, transcript-names, main; concatenated at render time mirroring the CSS pattern
- [x] `bristlenose render` command — re-render reports from intermediate JSON without retranscribing or calling LLMs
- [x] Apple Silicon GPU acceleration (MLX)
- [x] PII redaction (Presidio)
- [x] Cross-platform support (macOS, Linux, Windows)
- [x] AGPL-3.0 licence with CLA
- [x] Renamed gourani → bristlenose (including repo directory)
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
- [x] Man page (`man/bristlenose.1`) — full groff man page covering all commands, options, config, examples. Canonical file at `bristlenose/data/bristlenose.1` (bundled in wheel), symlinked from `man/`. Self-installs to `~/.local/share/man/man1/` on first run (piggybacks on auto-doctor sentinel). Snap installs via `snapcraft.yaml`. GitHub Release asset. CI enforces version match with `__version__`. Homebrew formula needs `man1.install "man/bristlenose.1"` (tap repo change)
- [x] (0.4.0) Dark mode — CSS `light-dark()` function, follows OS/browser preference by default, `color_scheme` config override (`auto`/`light`/`dark`), `<meta name="color-scheme">` tag, `<picture>` element for dark logo, print forced to light, histogram hard-coded colours replaced with CSS tokens, 17 tests
- [x] PII redaction default OFF — `pii_enabled: bool = False` in config; CLI flags `--redact-pii` (opt in) / `--retain-pii` (explicit default); replaced `--no-pii`; 3 tests
- [x] People file (participant registry) — `people.yaml` in output dir; Pydantic models (`PersonComputed`, `PersonEditable`, `PersonEntry`, `PeopleFile`); `bristlenose/people.py` (load, compute, merge, write, display name map); merge strategy preserves human edits across re-runs; display names in quotes/tables/friction/journeys in both markdown and HTML reports; `data-participant` HTML attributes kept as canonical `participant_id` for JS; 21 new tests (14 people, 3 PII, 2 models, 2 markdown)
- [x] Participant table redesign — columns now `ID | Name | Role | Start | Duration | Words | Source file` (was 9 cols, now 7); ID shows raw `p1`/`p2`/`p3`; Name shows `full_name` from people.yaml (pale-grey italic "Unnamed" placeholder when empty); Role moved next to Name; Date+Start merged into single Start column with macOS Finder-style relative dates (`Today at 16:59` / `Yesterday at 17:00` / `29 Jan 2026 at 20:56`); removed % Words and % Time; `format_finder_date()` helper in `utils/markdown.py` with 8 tests
- [x] `render --clean` accepted gracefully — flag is ignored with a reassuring message that render is always non-destructive (overwrites reports only)
- [x] Per-participant HTML transcript pages — `transcript_p1.html`, `transcript_p2.html` etc.; participant table ID column is a hyperlink; back button styled after Claude search (`← {project_name} Research Report`); timecodes clickable with video player; speaker names resolved (short_name → full_name → pid); prefers cooked transcripts over raw when both exist; `transcript.css` added to theme; only `storage.js` + `player.js` loaded (no favourites/editing/tags); 17 tests
- [x] Quote attribution links to transcripts — `— p1` at end of each quote is a hyperlink to `transcript_p1.html#t-{seconds}`, deep-linking to the exact segment; `.speaker-link` CSS in `blockquote.css` (inherits muted colour, accent on hover)
- [x] Editable participant names in report — pencil icon on participant table Name/Role cells; `contenteditable` inline editing; localStorage persistence; YAML clipboard export; reconciliation with baked-in data on re-render; `names.js` module + `name-edit.css` molecule
- [x] Auto name/role extraction from transcripts — Stage 5b LLM prompt extended to extract `person_name` and `job_title`; `SpeakerInfo` dataclass; speaker label metadata harvesting for Teams/DOCX/VTT sources; `auto_populate_names()` fills empty editable fields (LLM > metadata, never overwrites); wired into `run()` and `run_transcription_only()`
- [x] Short name suggestion heuristic — `suggest_short_names()` in `people.py`; first token of `full_name`, disambiguates collisions with last-name initial ("Sarah J." vs "Sarah K."); JS mirror `suggestShortName()` in `names.js` for browser-side auto-fill; 26 new tests
- [x] Editable section/theme headings — pencil icon inline editing on section titles, section descriptions, theme titles, theme descriptions; bidirectional ToC sync; shared `bristlenose-edits` localStorage; `initInlineEditing()` in `editing.js`; 19 tests
- [x] (0.6.3) Header redesign — logo top-left (flipped, baseline-aligned), "Bristlenose" logotype + project name, right-aligned doc title + participant/session count + Finder-date meta; new `atoms/logo.css` layout
- [x] (0.6.3) View-switcher dropdown — borderless "All quotes" / "Favourite quotes" / "Participant data" menu in sticky toolbar; `view-switcher.js` module; replaces old hamburger/button-bar pattern; `currentViewMode` global shared with `csv-export.js`
- [x] (0.6.3) Copy CSV button with clipboard SVG icon — single adaptive button (exports all or favourites based on view mode); inline SVG replaces character entity
- [x] (0.6.3) Quote attributions use raw pids — report quotes show `— p1` (anonymisation boundary); transcript pages keep display names; `names.js` no longer updates `.speaker-link` text
- [x] (0.6.3) Analysis ToC column — Sentiment, Tags, Friction points, and User journeys in their own "Analysis" nav column, separate from Themes
- [x] (0.6.5) Timecode two-tone typography — blue digits + muted grey brackets, `:visited` fix, `_tc_brackets()` helper in `render_html.py`, applied to all 6 rendering sites
- [x] (0.6.5) Hanging-indent quote layout — flexbox `.quote-row` with timecode in left gutter, `.quote-body` indented beside it; badges naturally indented; same layout on transcript pages (`.transcript-segment` + `.segment-body`)
- [x] (0.6.5) Non-breaking spaces on quote attribution — `&nbsp;` around em-dash prevents `— p1` widowing at line breaks
- [x] (0.6.5) Transcript page name propagation — `transcript-names.js` reads localStorage name edits from report page, updates heading + speaker labels on load; `data-participant` attributes on `<h1>` and `.segment-speaker`
- [x] Platform-aware session grouping — `_normalise_stem()` strips Teams/Zoom cloud/Google Meet naming conventions; `_is_zoom_local_dir()` detects Zoom local folders; `group_into_sessions()` two-pass grouping (Zoom folders by directory, remaining by normalised stem); `extract_audio.py` skips FFmpeg when platform transcript present; 37 new tests. Design doc: `docs/design-platform-transcripts.md`
- [x] CLI output overhaul — Cargo/uv-style green `✓` checkmark lines with per-stage timing, dim header (version · sessions · provider · hardware), LLM token usage tracking with cost estimate, OSC 8 terminal hyperlinks. Output capped at 80 columns. All tqdm/HuggingFace progress bars suppressed (mlx-whisper `verbose=None`, module-level `TQDM_DISABLE`, programmatic `disable_progress_bars()`). New: `LLMUsageTracker`, `estimate_cost()`, `HardwareInfo.label`, `_format_duration()`, `_print_step()`. 23 new tests

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

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` on every push (informational, non-blocking). This schedule keeps things from rotting.

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [ ] **May 2026** — Run `pip list --outdated` in the venv. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind. Run tests, commit
- [ ] **Aug 2026** — Same as above
- [ ] **Nov 2026** — Same as above

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Check Python EOL dates — Python 3.10 EOL is Oct 2026; if past EOL, bump `requires-python`, `target-version` (ruff), `python_version` (mypy)
  - Check faster-whisper / ctranslate2 project health — is ctranslate2 still maintained? If dormant, evaluate `whisper.cpp` bindings or `mlx-whisper` as default
  - Check spaCy major version — if spaCy 4.x is out, plan coordinated upgrade of spacy + thinc + models (only affects PII/presidio)
  - Check Pydantic major version — if Pydantic 3.x is out, assess migration scope
  - Rebuild snap to pick up fresh transitive deps
  - Review `pip-audit` CI output for any persistent unfixed CVEs; decide if workarounds needed

### Risk register

| Dependency | Risk | Why | Escape hatch |
|---|---|---|---|
| faster-whisper / ctranslate2 | High | Fragile chain, ctranslate2 ties to specific torch versions, maintenance activity varies | `mlx-whisper` (macOS), `whisper.cpp` Python bindings |
| spaCy + thinc + presidio | Medium | spaCy 3.x pins thinc 8.x; a spaCy 4.x release forces coordinated upgrade | Contained to PII stage only; can pin spaCy 3.x indefinitely |
| anthropic / openai SDKs | Low | Bump weekly, backward-compatible within major versions | Floor pins are fine; no action needed |
| Pydantic | Low | Stable at 2.x; no 3.x imminent | Would be a large migration but not urgent |
| Python itself | Low (now) | 3.10 EOL Oct 2026; running 3.12 | Bump floor when 3.10 reaches EOL |
| protobuf (transitive) | Low | CVE-2026-0994 (DoS via nested Any); no fix version yet; we don't parse untrusted protobuf | Resolves when patched version ships |

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

- [x] Search-as-you-type filtering — collapsible magnifying glass icon in toolbar, filters quotes by text/speaker/tags, overrides view mode, hides empty sections
- [ ] Hide/show quotes — toggle individual quotes, persist state
- [ ] Keyboard shortcuts — j/k navigation, s to star, e to edit, / to search
- [x] Timecodes: two-tone typography — blue digits + muted grey brackets, `:visited` fix, `_tc_brackets()` helper; hanging-indent layout for quote cards and transcript segments
- [ ] User tag × button — vertically centre the close button optically (currently sits too low)
- [ ] AI badge × button — the circled × is ugly; restyle to match user tag delete or use a simpler glyph
- [x] Indent tags — badges now sit inside `.quote-body` div, naturally indented at the quote text level by the hanging-indent flexbox layout
- [ ] Logo: slightly bigger — bump from 80px to ~100px
- [ ] JS: `'use strict'` — add to each JS module to catch accidental globals and silent errors
- [ ] JS: shared `utils.js` — extract duplicated quote-stripping regex (`QUOTE_RE` / `CSV_QUOTE_RE`) into a shared module
- [ ] JS: magic numbers → config — extract `150`ms blur delay, `200`ms animation, `250`ms FLIP duration, `2000`ms toast, `8` max suggestions, `48`px min input into a shared constants object
- [x] JS: histogram hardcoded colours — replaced inline `'#9ca3af'` / `'#6b7280'` with `var(--bn-colour-muted)` (done in v0.4.0 dark mode)
- [ ] JS: drop `execCommand('copy')` fallback — `navigator.clipboard.writeText` is sufficient for all supported browsers; remove deprecated fallback or gate behind a warning

### Small (a day or two each)

- [x] Editable participant names in report — pencil icon inline editing, localStorage, YAML export, reconciliation
- [ ] Participant metadata: day of the week in recordings — Start column now shows date+time (Finder-style), but could also show day name (e.g. "Mon 29 Jan 2026 at 20:56")
- [ ] Reduce AI tag density — too many AI badges per quote; tune the LLM prompt or filter to show only the most relevant 2–3
- [x] Sentiment & friction as standalone sections — moved to "Analysis" TOC column alongside Tags and User journeys
- [ ] User-tags histogram: right-align bars — bars should grow from the same zero-x baseline as the AI sentiment chart so the two read side-by-side
- [ ] Clickable histogram bars — clicking a bar in sentiment or user-tags chart opens a filtered view showing only quotes with that tag/emotion
- [ ] Sticky header — the toolbar (view-switcher + Copy CSV) is sticky but the header (logo, logotype, project name) scrolls away; decide whether to make the full header sticky or keep current behaviour where only the toolbar sticks
- [x] Burger menu — replaced with borderless view-switcher dropdown (All quotes / Favourite quotes / Participant data) + Copy CSV button in sticky toolbar
- [ ] Refactor render_html.py header/toolbar into template helpers — the report page and transcript page duplicate header HTML (logo, logotype, project name, meta) and toolbar markup; extract into shared helper functions so page-specific rendering doesn't repeat the boilerplate
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

- [x] Moderator identification Phase 1 — per-session speaker codes (`[m1]`/`[p1]`), moderator entries in `people.yaml`, per-segment speaker rendering on transcript pages, `.segment-moderator` CSS
- [ ] Moderator identification Phase 2 — cross-session moderator linking (`same_as` field), web UI for declaring same-person across sessions
- [x] LLM name/role extraction from transcripts — extended Stage 5b, `SpeakerInfo` dataclass, metadata harvesting, auto-populate
- [x] Multi-participant sessions — session_id decoupling from participant_id, global participant numbering (`p1`–`p11` across sessions), sessions table with Speakers column, transcript page heading format (`Session N: m1 Name, p5 Name`), raw code segment labels, `PersonComputed.session_id` for grouping, VTT duration from transcript timestamps
- [ ] Speaker diarisation improvements — better accuracy, manual correction UI
- [ ] Batch processing dashboard — progress bars, partial results, resume interrupted runs
- [ ] JS tests — add lightweight DOM-based tests (jsdom or Playwright) covering tag persistence, CSV export output, favourite reordering, and edit save/restore

### Large: Reactive UI architecture (local dev server + framework)

The current report is static HTML with vanilla JS and localStorage for state. This worked for single-page interactions but is hitting walls:

- **Cross-page state**: name edits on the report don't propagate to transcript pages without hacks (currently: read-only localStorage bridge via `transcript-names.js`). Any new cross-page feature (e.g. hiding quotes, search state) would need the same workaround
- **Data binding**: every piece of interactive state (favourites, edits, tags, names, hidden quotes) needs hand-written DOM update functions. Adding a new interactive feature means writing both the data logic and the DOM synchronisation from scratch
- **No server**: static HTML can't write files. The YAML clipboard export → manual paste → re-render workflow is friction that users shouldn't need to accept
- **Growing JS complexity**: 10 modules, ~2,200 lines, implicit globals for cross-module communication. Adding search, keyboard shortcuts, and hide/show will push this further

#### What we need

A local dev server (bundled with bristlenose) that:
1. **Serves the report** as a local web app (`bristlenose serve` or auto-open after `bristlenose run`)
2. **Provides a data API** — reads/writes `people.yaml`, intermediate JSON, and edit state directly (no clipboard export dance)
3. **Uses a reactive UI framework** — component model, reactive data binding, declarative rendering
4. **Stays local-first** — no cloud, no accounts, no telemetry. The server runs on localhost and dies when you close it

#### Framework options

| Framework | Bundle size | Learning curve | Ecosystem | Notes |
|-----------|------------|----------------|-----------|-------|
| **Svelte** | ~2 KB runtime | Low | Growing | Compiles to vanilla JS; smallest bundle; no virtual DOM; reactive by default. Best fit for "feels like enhanced HTML" |
| **Preact** | ~3 KB | Low (React-compatible) | Large (React) | Drop-in React alternative at 1/10th the size; familiar API; huge ecosystem via compat layer |
| **Vue** | ~33 KB | Medium | Large | Single-file components; good template syntax; heavier than Svelte/Preact |
| **React** | ~42 KB | Medium | Largest | Industry standard; heaviest bundle; most hiring/docs/tooling |
| **HTMX + Alpine.js** | ~15 KB + ~15 KB | Low | Niche | Server-rendered HTML with sprinkles of interactivity; closest to current architecture; limited for complex client state |
| **Solid** | ~7 KB | Medium | Small | Fine-grained reactivity (no virtual DOM); React-like JSX; very fast; smaller ecosystem |

**Recommendation**: Svelte or Preact. Both are small, fast, and work well for a local tool where bundle size matters less than developer experience. Svelte's compiler approach means the runtime cost is near-zero, and its reactivity model is the most natural fit for "data changes → DOM updates" without boilerplate. Preact is the safe choice if we want React ecosystem access.

#### Server options

- **FastAPI** (Python) — already in the Python ecosystem; async; easy to add alongside the CLI; serves both the API and the built frontend
- **Flask** — simpler, synchronous, lighter weight; fine for a local tool
- Built-in `http.server` — too basic, no routing/API support

FastAPI is the natural choice: async (matches our pipeline), Pydantic models (already used everywhere), auto-generated API docs, WebSocket support for live updates.

#### Migration path

This is a large effort. Incremental approach:

1. **`bristlenose serve`** — add a FastAPI server that serves the current static HTML + a few API endpoints (read/write people.yaml, read intermediate JSON)
2. **Data API first** — replace localStorage → clipboard → paste → re-render with direct API calls. Keep the vanilla JS but swap the storage layer
3. **Component-by-component migration** — replace one interactive feature at a time (e.g. participant table → Svelte component) while keeping the rest as static HTML
4. **Full SPA** — eventually the entire report is a framework app served by the local server

Step 1 alone would fix the immediate pain (cross-page state, file writes) without touching the frontend. Steps 2–4 can happen gradually.

### CLI improvements (Feb 2026)

Full design doc: `docs/design-cli-improvements.md`

**Done in this session:**
- [x] `analyse` alias — hidden alias for `analyze` (British English convenience)
- [x] `transcribe` is now primary — renamed from `transcribe-only`
- [x] `render` argument fix — now auto-detects output dir, positional renamed from `INPUT_DIR` to `OUTPUT_DIR`
- [x] Command reordering — help shows `run`, `transcribe`, `analyze`, `render`, `doctor`, `help` (workflow order)
- [x] `--llm claude/chatgpt` aliases — normalised in `load_settings()`

**Documented for later:**
- [ ] File-level progress — "Transcribing... (2/5 files)" gives sense of movement
- [ ] Time estimate warning — warn before jobs >30min, based on audio duration
- [ ] Britannification pass — standardise on British spellings throughout

**Backward compat policy:** Don't worry until v1.0.0. Make the CLI good, don't carry cruft.

### LLM provider roadmap (Feb 2026)

Full design doc: `docs/design-cli-improvements.md` — "LLM Provider Roadmap" section

Goal: support whatever LLM your organisation has access to. Detailed designs for all providers with implementation sketches, testing checklists, and abstraction patterns.

**Phase 1: Ollama as zero-friction entry point** ✅ DONE
- [x] `bristlenose/providers.py` — `ProviderSpec` registry, `resolve_provider()`, config fields
- [x] Interactive first-run prompt when no API key configured — offer Local/Claude/ChatGPT choice
- [x] Ollama detection — check if running, find suitable models (`bristlenose/ollama.py`)
- [x] Automated Ollama installation — `get_install_method()` detects brew/snap/curl, `install_ollama()` runs appropriate command, falls back to download page on failure
- [x] Auto-start Ollama — `start_ollama_serve()` launches Ollama if installed but not running (macOS: `open -a Ollama`, Linux: `ollama serve` in background)
- [x] Model auto-pull with consent — download `llama3.2:3b` (2 GB) on first use
- [x] Retry logic for JSON parsing failures (local models are ~85% reliable) — 3 retries with exponential backoff
- [x] Doctor integration — show "Local (llama3.2:3b via Ollama)" status
- [x] Smart cloud fallback hints — fix messages check which API keys are configured and only suggest usable providers

**Why Ollama first:** Removes biggest adoption barrier. No signup, no payment, no API key. Users can try the tool for free in 10 minutes.

**Phase 2: Azure OpenAI (~2h)**
- [ ] Add Azure to registry (same SDK as OpenAI/Ollama)
- [ ] `_analyze_openai_compatible()` — unified method for OpenAI/Azure/Local
- [ ] Doctor validation for Azure credentials
- [ ] Config: `BRISTLENOSE_AZURE_ENDPOINT`, `BRISTLENOSE_AZURE_KEY`, `BRISTLENOSE_AZURE_DEPLOYMENT`

**Why Azure:** High enterprise demand. Users with Microsoft 365 E5 contracts need Azure routing for compliance.

**Phase 3: Keychain integration (~3h)**
- [ ] `bristlenose/keychain.py` using `keyring` library
- [ ] `bristlenose config set-key claude` CLI command
- [ ] Credential loading: Keychain → env var → .env (fallback chain)
- [ ] Doctor shows key source (Keychain vs env var)

**Phase 4: Gemini (~3h)**
- [ ] Add `google-genai` dependency (~15 MB)
- [ ] Add Gemini to registry — native JSON schema support
- [ ] `_analyze_gemini()` method (different SDK pattern)
- [ ] Pricing: Gemini Flash is 5–7× cheaper than Claude/GPT-4o

**Phase 5: Documentation (~2h)**
- [ ] README section: "Choosing an LLM provider"
- [ ] Man page updates
- [ ] `.env.example` with all provider env vars

**GitHub Copilot:** NOT supported. Copilot ≠ Azure OpenAI. No public inference API. Point enterprise users to Azure instead.

### `bristlenose doctor` and dependency UX

Full design doc: `docs/design-doctor-and-snap.md`

- [x] `bristlenose doctor` command — seven checks (FFmpeg, backend, model, API key, network, PII, disk)
- [x] Pre-flight gate on `run`/`transcribe-only`/`analyze` — catches problems before slow work starts
- [x] First-run auto-doctor — runs automatically on first invocation, sentinel at `~/.config/bristlenose/.doctor-ran`
- [x] Install-method-aware fix messages — detect snap/brew/pip, show tailored install instructions
- [x] API key validation in pre-flight — cheap API call to catch expired/revoked keys upfront
- [x] Whisper model cache check — detect whether model is cached without triggering download
- [ ] `--prefetch-model` flag — download Whisper model and exit (for slow connections, CI setups)
- [ ] Homebrew formula: add `post_install` for spaCy model download, improve caveats

### Platform detection refactor (future PR)

The codebase has grown to have 12+ instances of `shutil.which() + subprocess.run() + exception handling` across `ollama.py`, `doctor.py`, `hardware.py`, and `audio.py`. Worth consolidating into a shared module.

**Proposed `bristlenose/utils/system.py`** (~100 lines):
- `which(name: str) -> Path | None` — wraps `shutil.which`
- `command_exists(name: str) -> bool`
- `run_safe(cmd: list[str], timeout: int = 10) -> CompletedProcess | None` — handles all exception patterns
- `is_darwin()`, `is_linux()`, `is_windows()`, `is_apple_silicon()` → simple booleans
- `can_import(module_name: str) -> bool` — try-import pattern

**Keep domain-specific detection where it is:**
- `detect_install_method()` stays in `doctor_fixes.py` (how Bristlenose was installed)
- `get_ollama_install_method()` stays in `ollama.py` (how Ollama was installed — different thing)
- `HardwareInfo` stays in `hardware.py` — already well-encapsulated

**Benefits:**
- Reduces repeated subprocess boilerplate by ~30-40%
- Standardises timeout constants (currently 5, 10, 30, 600 scattered as magic numbers)
- Makes tests cleaner (mock one function instead of patching subprocess everywhere)
- Foundation for future providers (Azure, Gemini will need similar checks)

**Files to simplify:**
- `ollama.py` — 6 instances of which + subprocess pattern
- `doctor.py` — 3 instances
- `hardware.py` — 5 instances (sysctl, nvidia-smi, system_profiler)
- `audio.py` — 2 instances (ffprobe, ffmpeg)

### Performance (audited Feb 2026)

Full audit done. Stage concurrency (item 1) is shipped. Remaining items ranked by impact.

#### Done

- [x] **Concurrent per-participant LLM calls** — stages 5b, 8, 9 use `asyncio.Semaphore(llm_concurrency)` + `asyncio.gather()` to run up to 3 concurrent API calls per stage. Stages 10+11 (clustering + theming) also run concurrently via `asyncio.gather()`. Wires up the existing `llm_concurrency: int = 3` config. For 8 participants, estimated ~2.5x speedup on LLM-bound time (~220s → ~85s)

#### Quick wins (minimal code changes)

- [x] **Compact JSON in LLM prompts** — `quote_clustering.py:54` and `thematic_grouping.py:53` switched from `json.dumps(indent=2)` to `separators=(",",":")`. Saves 10–20% input tokens on the two cross-participant calls
- [x] **FFmpeg VideoToolbox hardware decode** — `utils/audio.py` now passes `-hwaccel videotoolbox` on macOS, offloading H.264/HEVC video decode to the Apple Silicon media engine. No-op for audio-only inputs and non-macOS platforms
- [ ] **Cache `system_profiler` results** — `utils/hardware.py` runs `system_profiler SPHardwareDataType` and `system_profiler SPDisplaysDataType` on every startup (~2–4s on macOS). Results don't change between runs. Cache to `~/.config/bristlenose/.hardware-cache.json` with a TTL (e.g. 24h). Change: ~30 lines in `hardware.py`
- [ ] **Skip logo copy when unchanged** — `render_html.py` runs `shutil.copy2()` for both logo images on every render. Add a size/mtime check first. Minor savings but avoids unnecessary disk writes

#### Medium effort (one module each)

- [ ] **Pipeline stages 8→9 per participant** — instead of "all stage 8 then all stage 9", run `_segment_single(p) → _extract_single(p)` as a chained coroutine per participant, then gather all. This lets participant B's topic segmentation overlap with participant A's quote extraction. Max utilisation of the `llm_concurrency` window across both stages. Change: refactor the stage 8→9 calls in `pipeline.py` into a per-participant async chain, bounded by the same semaphore
- [ ] **Pass transcript data to renderer** — `render_transcript_pages()` in `render_html.py:652` re-reads `.txt` files from disk via `load_transcripts_from_dir()`, even though the full pipeline had all transcript data in memory during stages 6–11. Thread `clean_transcripts` through to the render call to avoid redundant disk I/O. Change: add a `transcripts` parameter to `render_html()` and `render_transcript_pages()`, pass it from `pipeline.py`
- [x] **Concurrent FFmpeg audio extraction** — `extract_audio_for_sessions()` is now async with `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Up to 4 FFmpeg processes in parallel, stacks with VideoToolbox hardware decode. Default of 4 is optimal across all Apple Silicon (M1–M4 Ultra) — bottleneck is the shared media engine, not CPU cores
- [ ] **Temp WAV cleanup** — extracted WAV files in `output/temp/` are never cleaned up. At ~115 MB per hour of audio per participant, 10 one-hour interviews leave ~1.15 GB of temp files. Add a cleanup step after transcription (or a `--clean-temp` flag). Change: add `shutil.rmtree(temp_dir)` after `_gather_all_segments` in `pipeline.py`, guarded by a config flag

#### Larger effort (new subsystem)

- [ ] **LLM response cache** — hash `(transcript content + prompt template + model name)` → store response JSON in `output/intermediate/cache/`. On `analyze` re-runs with unchanged transcripts, skip the API call and return cached response. Benefits: saves money and time on re-runs (e.g. after editing prompts for one stage, the other stages don't re-run). Implementation: compute SHA-256 of `(system_prompt + user_prompt + model)` in `LLMClient.analyze()`, check for cached file, write on miss. Add `--no-cache` flag to force fresh calls. Change: ~80 lines in `llm/client.py` + config flag
- [ ] **Word timestamp pruning** — `TranscriptSegment.words: list[Word]` stores per-word timing for every segment. These are used only during transcript merging (overlap detection). After stage 6 (merge), the word lists could be dropped to free memory. For 10 one-hour interviews: ~80,000 Word objects freed. Also reduces intermediate JSON size. Change: add a `strip_word_timestamps()` pass after merge in `pipeline.py`

#### Not worth optimising (documented for completeness)

- **Whisper transcription is sequential**: GPU is already saturated by a single transcription. Parallelising wouldn't help on single-GPU machines. On CPU-only builds, `asyncio.to_thread()` could help for multi-file runs but the speedup is marginal vs the total transcription time
- **CSS/JS reads (32 small files)**: already lazy-cached in module-level globals. Only read once per process. Not a bottleneck
- **Intermediate JSON `indent=2` on disk**: adds ~15% file size vs compact JSON, but these files are for human debugging. Keep pretty-printed
- **Pydantic `model_dump()` serialisation cost**: called for every model when writing intermediate JSON. Profiling shows this is <100ms even for large quote lists. Not worth optimising
- **spaCy GPU acceleration for PII redaction**: benchmarked Feb 2026 — Presidio+spaCy (`en_core_web_sm`) processes 1,600 segments (8 participants × 200 segs) in ~6s on CPU (3.7ms/seg). For 10 participants that's 7.5s; for 20 it's 15s. Compared to transcription (~50 min for 10 participants) PII is 0.2% of total runtime. Adding `thinc-apple-ops` for Metal GPU would save single-digit seconds, add a dependency, and risk version compatibility issues. The `en_core_web_sm` model is too small to benefit from GPU — data-transfer overhead would likely negate any speedup

### Packaging (partially done)

- [x] PyPI (`pipx install bristlenose`)
- [x] Homebrew tap (`brew install cassiocassio/bristlenose/bristlenose`)
- [x] Snap for Ubuntu/Linux (`snap install bristlenose --classic`) — `snap/snapcraft.yaml` + `.github/workflows/snap.yml`. Classic confinement, ~307 MB full-featured snap, GitHub Actions CI (edge on push to main, stable on tags). Bundles FFmpeg + spaCy model + all ML deps. Tested locally on arm64 (Multipass), CI builds amd64. Pre-launch: register name, request classic confinement approval, add `SNAPCRAFT_STORE_CREDENTIALS` secret.
- [ ] Windows installer (winget or similar)

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — read from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`); the only file to edit when releasing |
| `bristlenose/cli.py` | Typer CLI entry point (`run`, `transcribe-only`, `analyze`, `render`, `doctor`) |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator (full run, transcribe-only, analyze-only, render-only) |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/render_html.py` | HTML report renderer — loads CSS + JS from theme/, all interactive features |
| `bristlenose/theme/` | Atomic CSS design system (tokens, atoms, molecules, organisms, templates) |
| `bristlenose/theme/js/` | Report JavaScript modules (storage, player, favourites, editing, tags, histogram, csv-export, view-switcher, search, names, transcript-names, main) — concatenated at render time |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection |
| `bristlenose/doctor.py` | Doctor check logic (pure, no UI) — 7 checks, `run_all()`, `run_preflight()` |
| `bristlenose/doctor_fixes.py` | Install-method-aware fix instructions (`detect_install_method()`, `get_fix()`) |
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR; also called by release.yml via workflow_call |
| `.github/workflows/release.yml` | Release pipeline: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/snap.yml` | Snap build & publish: edge on push to main, stable on v* tags |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of the tap repo's workflow (authoritative copy is in homebrew-bristlenose) |
| `snap/snapcraft.yaml` | Snap recipe: classic confinement, core24, Python plugin, bundles FFmpeg + spaCy |
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

## Implementation notes: Name extraction and editable names (done)

Implemented as an extension to the existing Stage 5b speaker identification — no new pipeline stage, no new config flag.

### How it works

1. **LLM extraction**: Stage 5b prompt asks for `person_name` and `job_title` alongside role assignment. `SpeakerRoleItem` (structured output model) has both fields defaulting to `""`. `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` with extracted data
2. **Metadata harvesting**: `extract_names_from_labels()` in `people.py` checks `speaker_label` metadata for real names (Teams/DOCX/VTT sources often have them). Skips generic labels ("Speaker A", "SPEAKER_00", "Unknown") via `_GENERIC_LABEL_RE`
3. **Auto-populate**: `auto_populate_names()` fills empty `full_name` (LLM > metadata) and empty `role` (LLM only). Never overwrites human edits
4. **Short name**: `suggest_short_names()` takes first token of `full_name`, disambiguates collisions ("Sarah J." vs "Sarah K.")
5. **Browser editing**: `names.js` — pencil icon inline editing, localStorage persistence, YAML clipboard export, reconciliation with baked-in `BN_PARTICIPANTS` data
6. **Data flow**: pipeline → auto-populate → write people.yaml → bake into HTML → browser edits → export YAML → paste into people.yaml → re-render → reconcile

### Key decisions

- **Extends Stage 5b** (no extra LLM call) — name extraction piggybacks on the speaker identification prompt
- **Always on** — no opt-in flag; the LLM is already being called for role assignment
- **localStorage only** — static HTML can't write files; YAML clipboard export bridges the gap
- **Human edits always win** — `auto_populate_names()` only fills empty fields

---

## Design notes: Moderator identification and transcript page speaker styling

### Phase 1 — IMPLEMENTED

Per-session moderator identification. Speaker codes (`[m1]`/`[p1]`/`[o1]`) in transcript files, moderator entries in `people.yaml`, per-segment speaker rendering on transcript pages with `.segment-moderator` CSS styling.

**How it works:**

1. Stage 5b identifies speaker roles (RESEARCHER, PARTICIPANT, OBSERVER) via heuristic + LLM
2. `assign_speaker_codes(session_id, next_participant_number, segments)` maps each `speaker_label` to a code based on role: RESEARCHER → `m1`/`m2`, OBSERVER → `o1`, PARTICIPANT/UNKNOWN → globally-numbered `p{next_participant_number}`. Returns `(dict[str, str], int)` — label→code map and updated next number
3. Transcript write functions use `seg.speaker_code` for the bracket token in `.txt`/`.md` files
4. Parser (`load_transcripts_from_dir()`) recognises `[m1]` prefix → `speaker_role=RESEARCHER, speaker_code="m1"`
5. `compute_participant_stats()` creates `PersonComputed` entries for moderator codes alongside participant entries
6. Transcript pages resolve speaker name per-segment and apply `.segment-moderator` class (muted colour)

**Decisions made:**
- `m` prefix for moderator (not `r` for researcher) — "moderator" is the user-research term
- Moderator text is muted (visually receded) — participant answers are the primary content
- Moderators get full `PersonEntry` in `people.yaml` with editable name/role fields
- Per-session codes: `m1` in session 1 and `m1` in session 2 are independent entries

**Key files:** `identify_speakers.py` (`assign_speaker_codes()`), `models.py` (`speaker_code` field), `merge_transcript.py` / `pii_removal.py` (write functions), `pipeline.py` (wiring + parser), `people.py` (stats), `render_html.py` (per-segment rendering), `transcript.css` (`.segment-moderator`)

**Tests:** `tests/test_moderator_identification.py` — 21 tests

### Phase 2 — NOT YET IMPLEMENTED

Cross-session moderator linking. The same researcher moderating 10 interviews creates 10 independent `m1` entries. Phase 2 adds:

- **`same_as` field in `PersonEditable`** — declare "this `m1` is the same person as that `m1`"
- **Auto-linking signals**: platform speaker labels (Teams carries real names), LLM-extracted `person_name`, frequency heuristic (speaker appearing in most sessions)
- **Web UI for manual linking** — drag-and-drop or checkbox-select moderator entries across sessions
- **Aggregated moderator stats** in participant table
- **Data complexity**: two moderators in one session (`m1`, `m2`); same researcher with different labels across sessions; multiple researchers in a study

Needs real multi-speaker data from Phase 1 runs to inform the right approach.
