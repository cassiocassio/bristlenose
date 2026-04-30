# Dashboard Cross-Tab Navigation

The Project tab dashboard is fully interactive — stat cards, featured quotes, session table rows, and section/theme lists all navigate to other tabs. Working context lives in `bristlenose/theme/CLAUDE.md` and `bristlenose/stages/CLAUDE.md`.

> **The two-axis quotes model.** The dashboard surfaces both *Sections* and *Themes* as parallel navigation entries because they organise the same quote pool along two complementary axes — sections are units of the artefact a single team owns (a page, a component, a flow, a hardware feature), themes are cross-cutting concerns that demultiplex across many teams (performance, brand, comparison-anchoring). Both are required; neither subsumes the other. Empirical validation in `experiments/thematic-spike/FINDINGS.md` (*"Two-axis quotes page"* and *"What the spike validated about the existing architecture"*).
>
> **Naming-debt notice (Sections vs Screens).** The spike landed on *"Sections, not screens"* as the generalising term — the unit can be a page, a component, a multi-page flow, a hardware feature, or a service moment. The user-facing label is already "Sections" (this doc, the dashboard, the report nav). The code constant `SCREEN_SPECIFIC` is on the rename list (FINDINGS *"Smallest possible product touches"* item 3) but no rename has shipped yet. When the rename does ship, this doc and `design-html-report.md` should be checked for cascade.

> **Serve mode (React Router):** Navigation is handled by React Router. The `data-stat-link` convention, `switchToTab()`, `scrollToAnchor()`, and `navigateToSession()` still work via backward-compat shims installed by `frontend/src/shims/navigation.ts`. The shims delegate to React Router's `navigate()`. The conventions below apply to both paths — shims bridge the gap in serve mode.

## `data-stat-link` convention

Stat cards use `data-stat-link="tab"` or `data-stat-link="tab:anchorId"` attributes. JS in `global-nav.js` handles the click: calls `switchToTab(tab)` then `scrollToAnchor(anchorId)` if present. In serve mode, the Dashboard React island calls the same `window.switchToTab` / `window.scrollToAnchor` globals (shimmed to React Router). Current mappings:

| Stat | Target |
|------|--------|
| Audio/video duration | `sessions` |
| Word count | `sessions` |
| Quote count | `quotes` |
| Section count | `quotes:sections` |
| Theme count | `quotes:themes` |
| AI tag count | `analysis:section-x-sentiment` |
| User tag count | `codebook` |

The anchor IDs `sections` and `themes` come from `content_section.html` (`id="{{ heading | lower }}"`). The `section-x-sentiment` anchor is on the h2 in `analysis.html`.

## `--bn-colour-hover` token

Interactive hover background for clickable rows and cards: `light-dark(#e8f0fe, #1e293b)`. Used by stat cards, featured quotes, and session table rows. Dark mode value is a dark blue-grey so white text stays readable (not a light blue which would require black text).

## Featured quote attribution

Featured quote footer shows a speaker code lozenge (`<a class="badge speaker-link">`) instead of the display name. The lozenge links to the session transcript via `data-nav-session` / `data-nav-anchor`. Clicking the card body tries the video player first (`seekTo`), falls back to transcript navigation.

## Python render helpers

Two helpers in `render/html_helpers.py` reduce duplication across quote rendering:

- **`_timecode_html(quote, video_map)`** — returns `<a class="timecode" ...>` if video exists for the participant, otherwise `<span class="timecode">`. Used by `_format_quote_html()` and `_render_featured_quote()`
- **`_session_anchor(quote)`** — returns `(pid_esc, sid_esc, anchor)` tuple for session navigation attributes. The anchor format is `t-{sid}-{start_seconds}`

## JS navigation helpers (global-nav.js / React shims)

- **`scrollToAnchor(anchorId, opts)`** — rAF + `getElementById` + `scrollIntoView`. Options: `block` (`'start'`/`'center'`), `highlight` (adds `anchor-highlight` class for yellow flash). Retry-aware: 50 × 100ms (5s) for async-rendered targets. In serve mode, this is the `useScrollToAnchor` React hook (`frontend/src/hooks/useScrollToAnchor.ts`) installed as a shim on `window.scrollToAnchor`
- **`navigateToSession(sid, anchorId)`** — static render: `switchToTab('sessions')` + `_showSession(sid)` + optional `scrollToAnchor` with highlight. Serve mode shim: `navigate("/report/sessions/${sid}")` + optional scroll. Used by speaker links, featured quotes, and dashboard table rows
- **`switchToTab(tab)`** — static render: toggles `.active` class on tabs/panels, pushes URL hash. Serve mode shim: `navigate("/report/{tab}/")`. All callers work unchanged via `window.switchToTab`
- **Sticky toolbar scroll offset** — `--bn-toolbar-height` CSS variable (default `3rem` in `tokens.css`, measured at runtime on first tab switch in `global-nav.js`). `toolbar.css` applies `scroll-margin-top` to `h2[id]`/`h3[id]` inside containers with a toolbar. **Two selectors required**: `.bn-tab-panel:has(.toolbar)` for the static render path, `.center:has(.toolbar)` for the React SPA (where `SidebarLayout` wraps content in `div.center`, not `.bn-tab-panel`). This prevents anchor links from scrolling headings behind the sticky toolbar. If the toolbar height changes (new buttons, typography), the JS measurement auto-adapts. **When adding new sticky elements that occlude content, always add a matching `scroll-margin-top` rule for both render paths** — check that the CSS selector matches the actual DOM wrapper in each path

## Session table helpers (render/dashboard.py)

- **`_derive_journeys(screen_clusters, all_quotes)`** — extracts per-participant journey paths from screen clusters. Returns `(participant_screens, participant_session)`. Shared by the session table and user journeys table — extracted from `_build_task_outcome_html()` to avoid duplication
- **`_oxford_list_html(*items)`** — joins pre-escaped HTML fragments with Oxford commas ("A", "A and B", "A, B, and C"). Different from the plain-text `_oxford_list()` helper — this one does NOT escape its arguments (caller must pre-escape). Used for moderator header with badge markup
- **`_build_session_rows()` return type** — returns `tuple[list[dict[str, object]], str]` (row dicts + moderator header HTML). The second element is empty string when no moderators. Both Sessions tab (~line 311) and Project tab (~line 1195) destructure this tuple
- **`_render_sentiment_sparkline(counts)`** — generates an inline bar chart (div with per-sentiment spans) from a `dict[str, int]` of sentiment counts. Bar heights are normalised to `_SPARKLINE_MAX_H` (20px). Uses `--bn-sentiment-{name}` CSS custom properties for colours. Returns `"&mdash;"` when all counts are zero
- **`_FAKE_THUMBNAILS` feature flag** — `os.environ.get("BRISTLENOSE_FAKE_THUMBNAILS", "") == "1"`. When enabled, all sessions with files show thumbnail placeholders (even VTT-only projects). Used for layout testing. The shipped version retains real `video_map` logic — only the env var override is added
- **`format_finder_filename(name, *, max_len=24)`** in `utils/markdown.py` — Finder-style middle-ellipsis filename truncation. Preserves extension, splits stem budget 2/3 front + 1/3 back. Returns unchanged if within `max_len`. Used by `_build_session_rows()` for the Interviews column with `title` attr for full name on hover
- **Moderator display logic** — 1 moderator globally → shown in header only, omitted from row speaker lists. 2+ moderators → header AND in each row's speaker list. Header uses `_oxford_list_html()` with `bn-person-badge` molecule markup (regular-weight names, not semibold)
