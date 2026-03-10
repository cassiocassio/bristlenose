# Design Decisions

Why Bristlenose works the way it does. Each entry captures a choice where alternatives existed and a non-obvious path was taken, with enough rationale to understand the reasoning.

This is not an ADR log (no numbers, no lifecycle ceremony). It is not a CLAUDE.md duplicate (no gotchas, no import patterns). It is a curated narrative that explains the "why" behind major product, UX, and architectural choices, with links to the detailed design docs.

## Adding a new decision

When making a decision worth recording, add an entry in the appropriate category. An entry needs: a heading (2-6 words), a bold one-sentence summary, and 2-4 sentences of rationale. Link to the detailed design doc if one exists. If a decision supersedes an older one, add _Superseded by [X]_ to the old entry — don't delete it.

Not every choice is a design decision. Conventions (code style, import patterns, naming) belong in CLAUDE.md. Gotchas (things that break if you do X) belong in the relevant CLAUDE.md child file. A design decision has alternatives that were considered and a rationale for why this alternative was chosen.

---

## Guiding principles

Five values that recur across many individual decisions. Each one shaped multiple entries below.

### Local-first

**No Bristlenose server, no accounts, no telemetry.** Audio never leaves your machine. LLM analysis sends transcript text to your configured provider — and if you use Ollama, nothing leaves your machine at all. The user owns their data and their infrastructure. This is a tool for their laptop, not a SaaS product.

This shapes: [LLM provider selection](#llm-provider-selection), [Credential storage](#credential-storage), [PII redaction](#pii-redaction), [Serve mode stack](#serve-mode-stack), [Export as DOM snapshot](#export-as-dom-snapshot), [Output inside input folder](#output-inside-input-folder).

### Dignity without distortion

**Participants deserve to look articulate without having their words changed.** Interview transcripts are messy — fillers, false starts, tangled grammar. The editorial cleanup philosophy is: remove noise (um, uh, filler "like"), preserve meaning (self-corrections, tone, emotional register), and insert `[clarifying context]` only where meaning would be lost. Never change what the participant said; change how clearly they said it.

This shapes: [Quote extraction](#quote-extraction), [Anonymisation boundary](#anonymisation-boundary).

_See also: `docs/design-research-methodology.md` §Editorial cleanup_

### Pre-flight catches everything catchable

**Never waste 30 minutes of pipeline time before revealing a missing dependency.** If FFmpeg is missing, the user finds out in 2 seconds, not after attempting to process 10 video files. The doctor command runs automatically on first use and checks everything upfront — FFmpeg, transcription backend, API keys, network, disk space — before any slow work begins.

This shapes: [Doctor command](#doctor-command), [Session-count guard](#session-count-guard).

_See also: `docs/design-doctor-and-snap.md` §Design principles_

### Researcher-first, then stakeholders

**Display names are a working tool for the research team; speaker codes are the anonymisation boundary for everyone else.** The research team (who were on the call) needs "p3 — Mary" to recall context. Product managers and executives receiving findings need "p3" — no names, no demographics, no opportunity for bias. Two audiences, two levels of detail, enforced by the export path.

This shapes: [Anonymisation boundary](#anonymisation-boundary), [Export as DOM snapshot](#export-as-dom-snapshot), [Speaker role identification](#speaker-role-identification), [Product-name convention](#product-name-convention).

### Respect the user's intelligence

**Show the fix command, not a paragraph explaining what went wrong.** The CLI output feels like `git status`: clean checkmark lines, minimal colour (green checkmarks, dim timing), width capped at 80. Doctor fix instructions give the command to run, not a tutorial. No emoji. No boxes. No dashboards. Researchers and developers are busy; respect their time and reading level.

This shapes: [CLI output style](#cli-output-style), [Doctor command](#doctor-command), [Quote editing](#quote-editing).

---

## Product and audience

### Product-name convention

**User-facing text says "Claude" and "ChatGPT", not "Anthropic" and "OpenAI".** Researchers know the products (they use Claude, they use ChatGPT), not the companies behind them. Internal code uses `"anthropic"` / `"openai"` / `"azure"` as config values — that's fine, only human-readable strings need product names. This avoids the awkward moment when a non-technical user sees "Anthropic" and has no idea what it refers to.

### Desktop app: SwiftUI + sidecar

**macOS native shell wrapping the CLI as a PyInstaller sidecar, targeting macOS 15 + Apple Silicon (M1+).** The desktop app exists to remove the terminal barrier. Researchers see "open your terminal" in a README and bounce. The app is a folder picker, one button, and a report in their browser — no Python, no Homebrew, no API key signup (bundled capped key as fallback).

The compatibility target covers ~90% of professional Mac users. Intel is ~5-10% of the installed base and falling; Sequoia (macOS 15) will be n-1 by launch. Targeting it avoids SwiftUI contortion for older APIs. The chip floor will bump to M2+ when local inference features arrive (Neural Engine improvements, unified memory bandwidth).

_See also: `docs/design-desktop-app.md`_

### LLM provider selection

**Five providers: Claude, ChatGPT, Azure OpenAI, Gemini, and Ollama (local).** The interactive first-run prompt offers three choices with cost estimates: Local (free, no account), Claude (~$1.50/study), ChatGPT (~$1.00/study). This covers the full spectrum: enterprise security requirements (Azure), cost-sensitive teams (Ollama), and the default path (Claude/ChatGPT for quality).

The local provider (Ollama) is the zero-friction fallback — it runs on the user's machine with no API key, no account, no cost. Reliability is lower (~85% valid JSON vs ~99% for cloud providers), with 3 retries and exponential backoff, but it's good enough for users who can't or won't use cloud APIs.

_See also: `bristlenose/llm/CLAUDE.md`, `docs/design-llm-providers.md`_

### Export as DOM snapshot

**Export is a DOM snapshot from the served React app, not a second render path.** The served app is the canonical experience — it has all the user's edits, stars, tags, and curated state. The static renderer (`render_html.py`) is a legacy offline fallback, not the export engine. Exporting by snapshotting the served DOM means the export always matches what the user sees, with embedded state as JSON and inlined CSS for standalone viewing.

Two export modes match two audiences: "report only" (curated findings, optional anonymisation, optional video clips) for managers and PMs, and "full archive" (everything, including transcripts and media) for research team handoff.

_See also: `docs/design-export-sharing.md`_

---

## Architecture and stack

### React as primary rendering path

**All visual and design work targets the React serve version; the static HTML renderer is legacy.** The framework decision came down to technical fit vs business risk. Svelte was the better technical fit (compiles to imperative DOM updates, handles contentEditable natively, ~2 KB runtime), but React is too big to fail. Meta runs Facebook, Instagram, WhatsApp Web, and Threads on it. The Angular 1-to-2 lesson applies: choosing a framework that fades means spending years rewriting while shipping nothing.

The contentEditable and TreeWalker pain with React is real but bounded — a few hundred lines of careful ref management, not a fundamental impossibility. The price is boilerplate. The price you don't pay is ever worrying whether your framework exists next year.

Rules: (1) New features and design changes: React only. (2) CSS is shared — changes apply to both paths. (3) Vanilla JS is frozen — data-integrity fixes only. (4) When a section becomes a React component, its Jinja2 equivalent is dead code. (5) `bristlenose render` continues for offline HTML but is the "frozen snapshot" format.

_See also: `docs/design-reactive-ui.md` §Business risk assessment, `docs/design-react-migration.md`_

### Module-level store

**`useSyncExternalStore` with module-level state, not React Context.** Originally required because quote islands mounted as separate `createRoot()` calls — Context doesn't cross root boundaries. In serve mode they now share a single React tree via `RouterProvider`, so Context would work, but the module-level store remains. It's proven, simpler, and doesn't depend on tree structure.

The store is the single source of truth for quote mutations (star, hide, edit, tag, badge, proposed tags) and toolbar filter state (view mode, search query, tag filter). The same pattern was used for `SidebarStore` (sidebar open/close, widths, hidden groups). Both are lightweight, testable, and have no provider nesting to reason about.

### Serve mode stack

**FastAPI + SQLite + React Router with pathname-based routing.** The server runs on localhost, auto-imports pipeline output into SQLite on startup (idempotent upsert), and serves a React Router SPA. Pathname routing (`/report/`, `/report/quotes/`, `/report/sessions/:id`) frees hash fragments for scroll targets and player parameters — the previous hash routing (`#quotes`, `#t-123`, `#src=...&t=...`) created conflicts between navigation, timecodes, and player state.

A single `RouterProvider` replaces 11 separate `createRoot()` calls from the island era. The SPA catch-all route returns the same transformed HTML for all `/report/*` paths; React Router handles client-side navigation.

_See also: `bristlenose/server/CLAUDE.md`_

### Bulk data API

**GET/PUT of full state maps, not per-item PATCH.** Each data endpoint mirrors one localStorage key — `PUT /projects/{id}/starred` replaces the entire starred map, just like `localStorage.setItem()` replaces the entire JSON blob. Larger payloads but simpler code: no partial-state bugs, no optimistic-update rollback, no PATCH merge logic. The tradeoff works because these maps are small (hundreds of entries, not thousands) and writes are infrequent (user clicks, not real-time streaming).

_See also: `bristlenose/server/CLAUDE.md` §Bulk maps_

### Pipeline as build system + event store

**Stages form a dependency DAG (like Make); edits form event history (like event sourcing).** The key insight is that pipeline resilience is a well-studied CS problem. Stage caching uses verifying traces: record input/output hashes, skip stages where inputs haven't changed, re-run from the first point of divergence. This is the same model as Shake and Bazel.

Human edits (tags, renames, hidden quotes) will eventually form an immutable event log. The current state is a projection rebuilt by replaying events. This gives provenance (who changed what), undo/redo (drop last N events), and merge after re-run (replay human edits on new LLM outputs).

Currently implemented: crash recovery, stage-level caching, per-session tracking within stages, transcription caching. Future: source change detection via file hashing, incremental session addition, analytical context preservation.

_See also: `docs/design-pipeline-resilience.md`_

### Fixed 12-stage pipeline

**Topological scheduler with within-stage concurrency.** The 12 stages execute in fixed order: ingest, extract audio, parse subtitles, parse docx, transcribe, identify speakers, merge transcript, PII removal, topic segmentation, quote extraction, quote clustering, thematic grouping, render. Per-participant LLM calls within a stage run concurrently (bounded by `asyncio.Semaphore(3)` + `asyncio.gather()`), but stages are sequential — topic maps from Stage 8 feed quote extraction in Stage 9.

Error isolation: a failed participant gets empty results (empty topic map, empty quote list), logged and skipped. The pipeline continues with the remaining participants. No cross-stage semaphore, no global error state.

### Pydantic for data, dataclasses for ephemeral

**Pydantic models for all persisted data structures; plain dataclasses for ephemeral computation.** Pipeline models, API schemas, and configuration use Pydantic — type safety, validation, serialization are all needed for data that crosses boundaries (disk, network, process). The analysis module uses plain dataclasses because its computations are ephemeral (signal concentration metrics computed on the fly, never persisted to disk).

### Atomic CSS design system

**Tokens, atoms, molecules, organisms, templates — all values via `--bn-*` custom properties, never hard-coded.** The design system uses CSS custom properties as a single source of truth for colours, spacing, typography, and breakpoints. Dark mode uses the CSS `light-dark()` function (no JavaScript). Four font-weight tiers (420/490/520/700) and five type-size pairs (12px–22px) with line-height decreasing per Bringhurst as size increases.

File boundaries are aligned to match React component boundaries, so CSS refactoring and component development track each other.

_See also: `bristlenose/theme/CLAUDE.md`, `docs/design-react-component-library.md`_

---

## Pipeline and analysis

### Speaker role identification

**Two-pass approach: fast heuristic, then LLM refinement.** Three roles — researcher (never quoted), participant (primary data), observer (excluded). The heuristic pass scores speakers by question ratio and researcher-phrase frequency; the LLM refines on the first ~5 minutes of transcript. The heuristic catches obvious cases (the person asking all the questions is the researcher); the LLM handles ambiguous ones (a chatty participant who asks a lot of questions back).

Why three roles? User-research sessions have a clear power dynamic: one person asks, another answers. Enterprise sessions often include silent stakeholders on the call. Misidentifying who is who contaminates the report with researcher questions presented as participant opinions.

_See also: `docs/design-research-methodology.md` §Speaker roles_

### Topic segmentation types

**Four transition types reflecting how moderated sessions actually flow.** `screen_change` (participant navigates to a new screen), `task_change` (researcher assigns a new task), `topic_shift` (discussion shifts within the same screen), `general_context` (conversation leaves screens entirely — job role, daily workflow, life context).

The `general_context` type is the mechanism that separates product-specific data from general data. Screen-specific quotes feed the clustering stage (organised by screen/task); general-context quotes feed thematic grouping (organised by emerging patterns). Without this separation, clustering would try to assign life-context quotes to screens they have nothing to do with.

_See also: `docs/design-research-methodology.md` §Topic segmentation_

### Quote extraction

**Deliberately over-extract, then let clustering and theming organise.** The extraction bar is low: anything revealing experience, opinion, behaviour, confusion, delight, or frustration. Think-aloud narration ("Home textiles and rugs. Bedding. Duvets.") is data — it shows the user journey through the interface. Minimum quote length is 5 words (below this, utterances rarely carry enough meaning to stand alone).

The philosophy is that a missed quote is worse than an extra quote. Extra quotes get organised into report sections where they strengthen patterns. Missed quotes are lost data that no downstream stage can recover.

_See also: `docs/design-research-methodology.md` §Quote extraction_

### Quote exclusivity

**Every quote appears in exactly one report section, enforced at three levels.** Level 1: quote type separation — screen-specific quotes go to clustering (Stage 10), general-context quotes go to theming (Stage 11). Level 2: within-cluster deduplication. Level 3: within-theme deduplication. This matches researcher expectations for handoff: each quote appears once, suitable for non-researchers who would be confused by duplicates.

_See also: `bristlenose/stages/CLAUDE.md`_

### Analysis thresholds

**Strict `>` comparisons, not `>=`.** Strong signal requires concentration > 2, moderate > 1.5. The analysis module is pure math — no LLM calls. Using strict inequality avoids edge-case ambiguity at threshold boundaries. Cell keys use `"label|sentiment"` format (pipe in labels is a known limitation, documented but not guarded).

### Session-count guard

**If ingest discovers more than 16 sessions, prompt before proceeding.** Prevents accidentally transcribing an entire multi-project directory. The guard applies to all three pipeline methods (`run`, `transcribe-only`, `analyze-only`). `--yes` / `-y` CLI flag bypasses the prompt for scripting and CI.

### Video thumbnail heuristic

**Use the end of the first participant segment within 3 minutes.** Segment boundary means mouth likely closed; face visible before screen sharing typically begins. Fallback: 60 seconds for longer videos, 0.0 for very short ones, grey placeholder for audio-only. File existence is the cache — no manifest tracking needed. Future: manual "set keyframe" override.

### LLM prompt versioning

**Prompts as Markdown files with `## System` and `## User` sections, archived with date-stamped names.** When iterating on a prompt, the old version is archived to `bristlenose/llm/prompts-archive/` with naming convention `prompts_YYYY-MM-DD_description.md`. This keeps history browsable without digging through git commits. Future goal: user-customisable prompts via config.

---

## User interface

### React migration sequencing

**Trivial to heavyweight, unless dependencies force otherwise.** Settings panel (105 lines, self-contained) first, then About panel, then QuotesStore (infrastructure, unblocks toolbar), then Toolbar (first user-facing surface), then Router (the hinge), then Player, Keyboard, JS stripping, full shell, Export. Each step self-contained and shippable. The vanilla JS modules are frozen for feature work, so there was no pressure to migrate everything at once — each step just shrank the vanilla surface.

_See also: `docs/design-react-migration.md`_

### Quote editing

**Single unified mode: click enters edit and crop simultaneously.** No pencil icon, no separate crop toggle, no mode switching. The report is primarily a reading surface; every idle-state affordance (pencil icons, dotted borders, hover outlines) was removed to reduce visual noise. Edit discoverability comes from the `text` cursor on hover and `...` ellipsis on previously cropped quotes.

Design details: caret placed at click position (not select-all, which destroys the quote on accidental keystroke); gold bracket crop handles appear after 250ms delay (lets yellow editing background register first, creating a two-beat sequence: "this is editable" then "you can also trim").

_See also: `docs/design-quote-editing.md`_

### Dark mode: CSS-only

**No JavaScript involved in theme switching.** The CSS `light-dark()` function resolves light and dark values automatically from `color-scheme`. The cascade: OS preference by default, user override via config (`bristlenose.toml`), `data-theme` HTML attribute for forced mode, print always light. No localStorage, no toggle button, no runtime colour calculations.

This was a deliberate choice to avoid the flash-of-wrong-theme problem. CSS-native colour scheme resolution happens before first paint. Browser support is ~87%+ globally (mid-2024 onwards); older browsers get light-only fallback from the plain `:root` values.

_See also: `bristlenose/theme/CLAUDE.md` §Dark mode_

### Dual sidebar layout

**5-column CSS grid on the Quotes tab only: rail, sidebar, center, sidebar, rail.** Left sidebar: table of contents with scroll spy (IntersectionObserver, RAF-throttled). Right sidebar: tag filter with codebook tree and eye toggles for badge hiding. Drag-to-resize with pointer events and snap-close at 120px threshold. Keyboard shortcuts (`[` left, `]` right, `\` both, `Cmd-.` tag sidebar) route-guarded to `/report/quotes`.

The sidebar is active only on the Quotes tab — other tabs have full-width content. This avoids the complexity of a global sidebar that would need to adapt its content per tab.

### Tag autocomplete with codebook

**Grouped suggestions with section headers and codebook colours.** When adding tags to quotes, the autocomplete dropdown groups suggestions by codebook section with colour-coded headers. Hidden-group tags (eye-toggled off in the sidebar) show a grey closed-eye icon in the suggestion list; accepting a hidden-group tag auto-unhides the group so the badge is immediately visible. Case-insensitive dedup guard prevents duplicate tags at the single point of entry (`addTag()`).

_See also: `docs/design-codebook-autocomplete.md`_

---

## Data and privacy

### Anonymisation boundary

**Speaker codes (p1, p2) are the external boundary; display names are internal team tools.** The HTML report embeds first names in the page source and session table — these help the research team recall who's who. When findings are presented to a wider audience, the speaker codes provide the anonymisation boundary. Export strips names by default, making this the safe path for external distribution.

Moderator and observer names are never stripped — they are part of the research team, not research subjects. Full names and surnames are never shown in the report UI; they exist only in `people.yaml` for the researcher's reference.

_See also: `SECURITY.md` §Anonymisation boundary_

### Credential storage

**Native keychain on macOS (Keychain) and Linux (Secret Service), with env var fallback.** Keys are never written to disk in plaintext by Bristlenose. The `.env` fallback is read-only — Bristlenose reads it if present but does not create or modify it. Priority order: keychain, env var, `.env` file. Keys are validated before storing to catch typos and truncation.

_See also: `docs/design-keychain.md`_

### PII redaction

**Opt-in, with location names deliberately excluded.** When enabled (`--redact-pii`), Microsoft Presidio + spaCy detect and replace personal information in transcripts before LLM analysis. Location names are excluded because redacting them would destroy research data — "Oxford Street IKEA" becomes "[ADDRESS] IKEA", which is useless for understanding user behaviour in physical spaces. An audit trail (`pii_summary.txt`) lists every redaction for review.

_See also: `SECURITY.md` §PII redaction_

### Output inside input folder

**`<folder>/bristlenose-output/` by default.** The researcher's files stay in their folder structure. Override with `--output` for cases where the input directory is read-only. Report filenames include the project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

---

## Developer experience

### Doctor command

**Three modes: explicit `bristlenose doctor`, first-run auto-doctor, and per-command pre-flight.** Seven checks: FFmpeg, transcription backend (faster-whisper/MLX), API keys, network, disk space, local LLM (Ollama), PII redaction (spaCy). Each returns ok, warn, or fail. Fix instructions are install-method-aware — they suggest `brew install` vs `apt-get` vs `curl` based on what's available on the user's system.

The auto-doctor on first run is critical: most users won't run `doctor` unprompted. The per-command pre-flight runs the full setup table on every pipeline invocation so the user always sees their setup context before committing to a long run.

_See also: `docs/design-doctor-and-snap.md`_

### CLI output style

**Cargo/uv-inspired: clean checkmark lines with per-stage timing.** `console.status()` spinner during work, `_print_step()` checkmark when done. Width capped at 80 characters. Minimal colour: green checkmarks, dim timing and stats. No emoji, no boxes, no progress bars (yet — `PipelineEvent` infrastructure exists for future visual UI).

The aesthetic is: the pipeline should feel like a build tool, not an app. Researchers using the CLI are comfortable with terminal output that looks like `cargo build` or `uv pip install`. The warning style uses bold yellow (not red) — yellow means "action needed", red means "something broke right now".

### Time estimation

**Welford's online algorithm with progressive disclosure.** After ingest, the pipeline prints an upfront time estimate (e.g. "~8 min (+/- 2 min)") using running mean and variance per metric. Profiles are keyed by hardware + config combo.

Progressive disclosure prevents nonsensical early estimates: no estimate until n >= 4 runs (insufficient data), point estimate only until n >= 8 (Welford variance with few samples produces absurdly wide ranges — e.g. +/- 16 min on a 14 min estimate with n=2). This means users see increasingly precise estimates as they use the tool more, rather than getting a misleading number on their first run.

_See also: `bristlenose/timing.py`_
