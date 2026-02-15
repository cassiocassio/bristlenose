# Changelog

All notable changes to Bristlenose are documented here. See also the [README](README.md) for the latest releases.

**Unreleased** — _serve branch_

- `bristlenose serve` command — FastAPI local dev server with SQLite database, Vite + React 19 HMR, SQLAdmin database browser
- React islands architecture — SessionsTable and AboutDeveloper mount into static HTML via `createRoot()` on `<div>` mount points
- Renderer overlay (dev-only, press **D**) — colour-codes report regions by origin: blue for Jinja2, green for React, amber for Vanilla JS
- Session table comment markers (`<!-- bn-session-table -->`) — serve command swaps Jinja2 table for React mount point at runtime via `re.sub`
- Visual diff page — side-by-side comparison of Jinja2 vs React sessions table

**0.9.3** — _13 Feb 2026_

- Interactive dashboard — Project tab stat cards are clickable links to their target tabs (audio→Sessions, quotes→Quotes, sections/themes→Quotes anchors, AI tags→Analysis, user tags→Codebook); featured quote cards open video player or fall back to transcript; session table rows drill into Sessions tab; section/theme names switch to Quotes tab and scroll to the anchor
- New `--bn-colour-hover` design token with `light-dark()` support
- Speaker code lozenge attribution on featured quotes
- Reusable JS helpers (`scrollToAnchor`, `navigateToSession`) and Python helpers (`_timecode_html`, `_session_anchor`)
- Fix: logo dark/light swap on appearance toggle

**0.9.2** — _12 Feb 2026_

- Sessions table redesign — speaker badges with colour-coded IDs, user journey paths below start dates, video thumbnail placeholders (96×54px, 16:9), per-session sentiment sparkline mini-bar charts
- Appearance toggle — system/light/dark mode switcher in settings tab
- User journeys — derived from topic-segmentation screen clusters, shown in sessions table and sortable journeys table
- Time estimates — upfront pipeline duration estimate after ingest (`~8 min (±2 min)`), recalculated remaining time after each stage, Welford's online algorithm for per-metric running stats, hardware+config keyed profiles persisted to `~/.config/bristlenose/timing.json`
- Clickable logo — Bristlenose logo in report header navigates to project tab
- Fix: `llm_max_tokens` truncation causing silent 0-quote extraction — providers now detect truncation via `stop_reason`/`finish_reason` and raise `RuntimeError` with actionable `.env` fix
- Fix: sentiment sparkline bars now align with video thumbnail baseline (removed inline height override that capped sparkline container at 20px instead of the intended 54px)

**0.9.1** — _11 Feb 2026_

- Moderator and observer names shown in Project tab stats row (Oxford comma lists, observer box only when observers exist)
- Fix: clicking [+] to add a tag on a quote now tags that quote, not the previously-focused quote

**0.9.0** — _11 Feb 2026_

- Tab navigation — tabs remember their position across page reloads via URL hash (`#codebook`, `#analysis`, etc.); browser back/forward navigates between tabs; deep-linkable tab URLs
- Analysis tab — inline signal cards and heatmaps in the main report (previously a placeholder); `BRISTLENOSE_ANALYSIS` data injected into the report's script block alongside the standalone `analysis.html`
- Codebook tab — fixed empty grid caused by `_countQuotesPerTag` function name collision between `codebook.js` and `tag-filter.js` in the concatenated JS bundle; codebook panel now renders correctly in the main report
- Removed dead toolbar button handlers from `analysis.js` and `codebook.js` (replaced by navigation tabs)

**0.8.2** — _9 Feb 2026_

- Transcript annotations — per-participant transcript pages now highlight which segments were selected as quotes, with margin labels showing sentiment, colour-coded span bars connecting multi-segment quotes, and a citation toggle to show/hide annotations; playback-synced glow on both transcript segments and report quote cards when video is playing
- Gemini provider — `--llm gemini` for budget-conscious teams (~$0.20/study, 5–7× cheaper than Claude or ChatGPT); `bristlenose configure gemini` stores your key in the system credential store; interactive provider picker now includes Gemini as option [4]
- Jinja2 template extraction — report renderer migrated from f-strings to Jinja2 templates (13 templates extracted across two phases); pure refactor, no output changes
- Platform-specific credential language — doctor and configure now show the actual store name: "Keychain" on macOS, "Secret Service" on Linux, instead of generic "credential store"

**0.8.1** — _7 Feb 2026_

- Hidden quotes — press `h` (or click the eye-slash button) to hide volume quotes you want to keep as evidence but need out of your working view; per-subsection badge shows count with dropdown of truncated previews; click a preview to unhide with highlight animation; bulk hide via multi-select + `h`; hidden state persists in localStorage and survives search, tag filter, and view switching
- Codebook — standalone `codebook.html` page (opens in a new window via toolbar button) with interactive panel for organising tags into groups; drag-and-drop reordering within and between groups; inline editing of group names; add/delete groups with confirmation; toggle AI tag visibility per-tag; colour-coded tag badges with 24-colour palette; shared data model across report and codebook via localStorage
- Toolbar redesign — unified round-rect button styling with 3-state border progression (rest → hover → active); tag filter and view switcher use dual-class pattern for consistent appearance
- Python 3.14 compatibility — `check_pii` in doctor now catches `Exception` (not just `ImportError`) to handle pydantic v1 crash when importing presidio on Python 3.14

**0.8.0** — _7 Feb 2026_

- Azure OpenAI provider — `--llm azure` for enterprise users with Microsoft Azure contracts; uses `AsyncAzureOpenAI` from the existing OpenAI SDK (no new dependencies); configure with `bristlenose configure azure` or `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` env vars
- Install smoke tests — new CI workflow (`install-test.yml`) verifies install instructions work on clean Linux and macOS VMs; runs `bristlenose doctor` and `bristlenose render` from pre-built fixtures with no API key needed; weekly full-pipeline run with real API key catches integration regressions

**0.7.1** — _6 Feb 2026_

- Bar chart alignment — sentiment and user-tag charts use CSS grid so bar left edges align within each chart; labels hug text with variable gap to bars
- Histogram delete — hover × on user tag labels in the histogram to remove that tag from all quotes (with confirmation modal)
- Surprise placement — surprise sentiment bar now renders between positive and negative sentiments
- Quote exclusivity in themes — each quote assigned to exactly one theme (pick strongest fit)

**0.7.0** — _5 Feb 2026_

- Multi-select — Finder-like click selection (click, Shift-click, Cmd/Ctrl-click) with bulk starring (`s` key) and bulk tagging; selection count shown in view-switcher label; CSV export respects selection
- Tag filter — toolbar dropdown between search and view-switcher filters quotes by user tags; checkboxes per tag with "(No tags)" for untagged quotes; per-tag quote counts, search-within-filter for large tag lists, dropdown chevron, ellipsis truncation for long names

**0.6.15** — _4 Feb 2026_

- Unified tag close buttons — AI badges and user tags now use the same floating circle "×" style
- Tab-to-continue tagging — pressing Tab commits the current tag and immediately opens a new input for adding another tag (type, Tab, type, Tab, Enter for fast keyboard-only tagging)
- Render command path fix — `bristlenose render <input-dir>` now auto-detects `bristlenose-output/` inside the input directory

**0.6.14** — _4 Feb 2026_

- Doctor fixes — improved Whisper model detection and PII capability checking

**0.6.13** — _3 Feb 2026_

- Keychain credential storage — `bristlenose configure claude` (or `chatgpt`) validates and stores API keys securely in macOS Keychain or Linux Secret Service; keys are loaded automatically with priority keychain → env var → .env; `bristlenose doctor` now shows "(Keychain)" suffix when key comes from system credential store; `--key` option available for non-interactive use

**0.6.12** — _3 Feb 2026_

- File-level transcription progress — spinner now shows "(2/4 sessions)" during transcription
- Improved Ollama start command detection — uses `brew services start ollama` for Homebrew installs, `open -a Ollama` for macOS app, platform-appropriate commands for snap/systemd
- Doctor displays "(MLX)" accelerator — when mlx-whisper is installed on Apple Silicon, doctor now shows "(MLX)" instead of "(CPU)"
- Whisper model line fits 80 columns — shortened to "~1.5 GB download on first run"
- Provider header fix — pipeline header now shows "Local (Ollama)" instead of "ChatGPT" when using local provider
- Improved fix messages — doctor fix messages now use `pipx inject` for pipx installs, proper Homebrew Python path for brew installs (PEP 668 compliance)
- Retry logic catches ValidationError — local model retries now also handle Pydantic schema validation failures, not just JSON parse errors

**0.6.11** — _3 Feb 2026_

- Local AI support via Ollama — run bristlenose without an API key using local models like Llama 3.2; interactive first-run prompt offers Local/Claude/ChatGPT choice
- Automated Ollama installation — offers to install Ollama automatically (Homebrew on macOS, snap on Linux, curl script fallback); falls back to download page if installation fails
- Auto-start Ollama — if installed but not running, bristlenose will start it for you
- Provider registry — centralised `bristlenose/providers.py` with `ProviderSpec` dataclass, alias resolution (claude→anthropic, chatgpt→openai, ollama→local)
- Ollama integration — `bristlenose/ollama.py` with status checking, model detection, and auto-pull with consent
- Retry logic for local models — 3 retries with exponential backoff for JSON parsing failures (~85% reliability vs ~99% for cloud)
- Smart cloud fallback hints — fix messages for Ollama issues now check which API keys you have and only suggest providers you can actually use
- Doctor integration for local provider — shows "Local (llama3.2:3b via Ollama)" status, helpful fix messages for Ollama not running or model missing

**0.6.10** — _3 Feb 2026_

- Output directory inside input folder — `bristlenose run interviews/` now creates `interviews/bristlenose-output/` to avoid collisions when processing multiple projects
- New directory structure — `assets/` for static files, `sessions/` for transcript pages, `transcripts-raw/`/`transcripts-cooked/` for transcripts, `.bristlenose/` for internal files
- Report filenames include project name — `bristlenose-{slug}-report.html` so multiple reports in Downloads are distinguishable
- Coverage link fix — player.js no longer intercepts non-player timecode links
- Anchor highlight — transcript page segments flash yellow when arriving via anchor link

**0.6.9** — _3 Feb 2026_

- Transcript coverage section — collapsible section at the end of the report showing what % of the transcript made it into quotes (X% in report · Y% moderator · Z% omitted), with expandable omitted content per session
- Transcript page fix — pages now render correctly when PII redaction is off (was failing with assertion error)

**0.6.8** — _3 Feb 2026_

- Multi-participant session support — sessions with multiple interviewees get globally-numbered participant codes (p1–p11 across sessions); report header shows correct participant count
- Sessions table — restructured from per-participant rows to per-session rows with a Speakers column showing all speaker codes (m1, p1, p2, o1) per session
- Transcript page format — heading shows `Session N: m1 Name, p5 Name, o1`; segment labels show raw codes for consistency with the anonymisation boundary
- Session duration — now derived from transcript timestamps for VTT-only sessions (previously showed "—")
- Moderator identification (Phase 1) — per-session speaker codes (`[m1]`/`[p1]`) in transcript files, moderator entries in `people.yaml`, `.segment-moderator` CSS class for muted moderator styling

**0.6.7** — _2 Feb 2026_

- Search enhancements — clear button (×) inside the search input, yellow highlight markers on matching text, match count shown in view-switcher label ("7 matching quotes"), ToC and Participants hidden during search, CSV export respects search filter
- Pipeline warnings — clean dim-yellow warning lines when LLM stages fail (e.g. credit balance too low), with direct billing URL for Claude/ChatGPT; deduplication and 74-char truncation
- CLI polish — "Bristlenose" in regular weight in the header line, "Report:" label in regular weight in the summary

**0.6.6** — _2 Feb 2026_

- Cargo/uv-style CLI output — clean `✓` checkmark lines with per-stage timing, replacing garbled Rich spinner output; dim header (version · sessions · provider · hardware), LLM token usage with cost estimate, OSC 8 terminal hyperlinks for report path; output capped at 80 columns; all tqdm/HuggingFace progress bars suppressed
- Search-as-you-type quote filtering — collapsible magnifying glass icon in the toolbar; filters by quote text, speaker, and tag content; overrides view mode during search; hides empty sections/subsections; 150ms debounce
- Platform-aware session grouping — Teams, Zoom cloud, Zoom local, and Google Meet naming conventions recognised automatically; two-pass grouping (Zoom folders by directory, remaining files by normalised stem); audio extraction skipped when a platform transcript is present
- Man page — full troff man page (`man bristlenose`); bundled in the wheel and self-installs to `~/.local/share/man/man1/` for pip/pipx users on first run; wired into snap, CI version gate, and GitHub Release assets
- Page footer — "Bristlenose version X.Y.Z" colophon linking to the GitHub repo on every generated page

**0.6.5** — _2 Feb 2026_

- Timecode typography — two-tone treatment with blue digits and muted grey brackets; `:visited` colour fix so clicked timecodes stay blue
- Hanging-indent layout — timecodes sit in a left gutter column on both report quotes and transcript pages, making them scannable as a vertical column
- Non-breaking spaces on quote attributions prevent the `— p1` from widowing onto a new line
- Transcript name propagation — name edits made in the report's participant table now appear on transcript page headings and speaker labels via shared localStorage

**0.6.4** — _1 Feb 2026_

- Concurrent LLM calls — per-participant stages (speaker identification, topic segmentation, quote extraction) now run up to 3 API calls in parallel via `llm_concurrency` config; screen clustering and thematic grouping also run concurrently; ~2.7× speedup on the LLM-bound portion for multi-participant studies

**0.6.3** — _1 Feb 2026_

- Report header redesign — logo top-left (flipped horizontally), "Bristlenose" logotype with project name, right-aligned document title and session metadata
- View-switcher dropdown — borderless menu to switch between All quotes, Favourite quotes, and Participant data views; replaces old button-bar pattern
- Copy CSV button with clipboard icon — single adaptive button that exports all or favourites based on the current view
- Quote attributions use raw participant IDs (`— p1`) in the report for anonymisation; transcript pages continue to show display names
- Table of Contents reorganised — Sentiment, Tags, Friction points, and User journeys moved to a dedicated "Analysis" column, separate from Themes

**0.6.2** — _1 Feb 2026_

- Editable participant names — pencil icon on Name and Role cells in the participant table; inline editing with localStorage persistence; YAML clipboard export for writing back to `people.yaml`; reconciliation with baked-in data on re-render
- Auto name and role extraction — Stage 5b LLM prompt now extracts participant names and job titles alongside speaker role identification; speaker label metadata harvested from Teams/DOCX/VTT sources; empty `people.yaml` fields auto-populated (LLM results take priority over metadata, human edits never overwritten)
- Short name suggestion — `short_name` auto-suggested from first token of `full_name` with disambiguation for collisions ("Sarah J." vs "Sarah K."); works both in the pipeline and in-browser
- Editable section and theme headings — inline editing on section titles, descriptions, theme titles, and theme descriptions with bidirectional Table of Contents sync

**0.6.1** — _1 Feb 2026_

- Snap packaging for Linux — `snap/snapcraft.yaml` recipe and CI workflow (`.github/workflows/snap.yml`); builds on every push to main, publishes to edge/stable when Store registration completes
- Pre-release snap testing instructions in README for early feedback on amd64 Linux
- Author identity (Martin Storey) added to copyright headers, metadata, and legal files

**0.6.0** — _1 Feb 2026_

- `bristlenose doctor` command — checks FFmpeg, transcription backend, Whisper model cache, API key validity, network, PII dependencies, and disk space
- Pre-flight gate on `run`, `transcribe-only`, and `analyze` — catches missing dependencies before slow work starts
- First-run auto-doctor — runs automatically on first invocation, guides users through setup
- Install-method-aware fix messages — detects snap, Homebrew, or pip and shows tailored install instructions
- API key validation — cheap API call catches expired or revoked keys upfront

**0.5.0** — _1 Feb 2026_

- Per-participant transcript pages — full transcript for each participant with clickable timecodes and video player; participant IDs in the table link to these pages
- Quote attribution deep-links — clicking `— p1` at the end of a quote jumps to the exact segment in the participant's transcript page
- Segment anchors on transcript pages for deep linking from quotes and external tools

**0.4.1** — _31 Jan 2026_

- People file (`people.yaml`) — participant registry with computed stats (words, % words, % speaking time) and human-editable fields (name, role, persona, notes); preserved across re-runs
- Display names — set `short_name` in `people.yaml`, re-render with `bristlenose render` to update quotes and tables
- Enriched participant table in reports (ID, Name, Role, Start, Duration, Words, Source) with macOS Finder-style relative dates
- PII redaction now off by default; opt in with `--redact-pii` (replaces `--no-pii`)
- Man page updated for new CLI flags and output structure

**0.4.0** — _31 Jan 2026_

- Dark mode — report follows OS/browser preference automatically via CSS `light-dark()` function
- Override with `color_scheme = "dark"` (or `"light"`) in `bristlenose.toml` or `BRISTLENOSE_COLOR_SCHEME` env var
- Dark-mode logo variant (placeholder; proper albino bristlenose pleco coming soon)
- Print always uses light mode
- Replaced hard-coded colours in histogram JS with CSS custom properties

**0.3.8** — _31 Jan 2026_

- Timecode handling audit: verified full pipeline copes with sessions shorter and longer than one hour (mixed `MM:SS` and `HH:MM:SS` in the same file round-trips correctly)
- Edge-case tests for timecode formatting at the 1-hour boundary, sub-minute sessions, long sessions (24h+), and format→parse round-trips

**0.3.7** — _31 Jan 2026_

- Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting constants and formatter functions
- Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- Participant codes in transcript segments (`[p1]` instead of `[PARTICIPANT]`) for better researcher context when copying quotes
- Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes

**0.3.6** — _31 Jan 2026_

- Document full CI/CD pipeline topology, secrets, and cross-repo setup

**0.3.5** — _31 Jan 2026_

- Automated Homebrew tap updates and GitHub Releases on every tagged release

**0.3.4** — _31 Jan 2026_

- Participants table: renamed columns (ID→Session, Session date→Date), added Start time column, date format now dd-mm-yyyy

**0.3.3** — _31 Jan 2026_

- README rewrite: install moved up, new quick start section, changelog with all versions, dev setup leads with git clone
- Links to Anthropic and OpenAI API key pages in install instructions

**0.3.2** — _30 Jan 2026_

- Fix tag auto-suggest offering tags the quote already has
- Project logo in report header

**0.3.1** — _30 Jan 2026_

- Single-source version: `__init__.py` is the only place to bump
- Updated release process in CONTRIBUTING.md

**0.3.0** — _30 Jan 2026_

- CI on every push/PR (ruff, mypy, pytest)
- Automated PyPI publishing on tagged releases (OIDC trusted publishing)

**0.2.0** — _30 Jan 2026_

- Tag system: AI-generated badges (deletable/restorable) + user tags with auto-suggest and keyboard navigation
- Favourite quotes with reorder animation and CSV export (separate AI/User tag columns)
- Inline quote editing with localStorage persistence
- Sentiment histogram (side-by-side AI + user-tag charts)
- `bristlenose render` command for re-rendering without LLM calls
- Report JS extracted into 8 standalone modules under `bristlenose/theme/js/`
- Atomic CSS design system (`bristlenose/theme/`)

**0.1.0** — _30 Jan 2026_

- 12-stage pipeline: ingest, extract audio, parse subtitles/docx, transcribe (Whisper), identify speakers, merge, PII redaction (Presidio), topic segmentation, quote extraction, screen clustering, thematic grouping, render
- HTML report with clickable timecodes and popout video player
- Quote enrichment: intent, emotion, intensity, journey stage
- Friction points and user journey summaries
- Apple Silicon GPU acceleration (MLX), CUDA support, CPU fallback
- PII redaction with Presidio
- Cross-platform (macOS, Linux, Windows)
- Published to PyPI and Homebrew tap
- AGPL-3.0 licence with CLA
