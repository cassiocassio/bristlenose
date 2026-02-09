# Reactive UI Architecture

Local dev server + framework migration for the HTML report.

**Status:** Not started. Tracked as GitHub issue #29.

---

## Problem statement

The current report is static HTML with vanilla JS and localStorage for state. This worked for single-page interactions but is hitting walls:

- **Cross-page state**: name edits on the report don't propagate to transcript pages without hacks (currently: read-only localStorage bridge via `transcript-names.js`). Any new cross-page feature (e.g. hiding quotes, search state) would need the same workaround
- **Data binding**: every piece of interactive state (favourites, edits, tags, names, hidden quotes) needs hand-written DOM update functions. Adding a new interactive feature means writing both the data logic and the DOM synchronisation from scratch
- **No server**: static HTML can't write files. The YAML clipboard export → manual paste → re-render workflow is friction that users shouldn't need to accept
- **Growing JS complexity**: 17 modules, ~2,800 lines, implicit globals for cross-module communication

---

## What we need

A local dev server (bundled with bristlenose) that:
1. **Serves the report** as a local web app (`bristlenose serve` or auto-open after `bristlenose run`)
2. **Provides a data API** — reads/writes `people.yaml`, intermediate JSON, and edit state directly (no clipboard export dance)
3. **Uses a reactive UI framework** — component model, reactive data binding, declarative rendering
4. **Stays local-first** — no cloud, no accounts, no telemetry. The server runs on localhost and dies when you close it

---

## Framework options

| Framework | Bundle size | Learning curve | Ecosystem | Notes |
|-----------|------------|----------------|-----------|-------|
| **Svelte** | ~2 KB runtime | Low | Growing | Compiles to vanilla JS; smallest bundle; no virtual DOM; reactive by default. Best fit for "feels like enhanced HTML" |
| **Preact** | ~3 KB | Low (React-compatible) | Large (React) | Drop-in React alternative at 1/10th the size; familiar API; huge ecosystem via compat layer |
| **Vue** | ~33 KB | Medium | Large | Single-file components; good template syntax; heavier than Svelte/Preact |
| **React** | ~42 KB | Medium | Largest | Industry standard; heaviest bundle; most hiring/docs/tooling |
| **HTMX + Alpine.js** | ~15 KB + ~15 KB | Low | Niche | Server-rendered HTML with sprinkles of interactivity; closest to current architecture; limited for complex client state |
| **Solid** | ~7 KB | Medium | Small | Fine-grained reactivity (no virtual DOM); React-like JSX; very fast; smaller ecosystem |

---

## Business risk assessment (Feb 2026)

Technical fit and business risk point in opposite directions. Svelte compiles to imperative DOM updates (what we already write by hand), handles contenteditable natively, doesn't fight TreeWalker text mutation, and has ~2 KB runtime. React's virtual DOM fights all of those patterns and needs workarounds (uncontrolled refs, dangerouslySetInnerHTML, careful memoisation for large quote lists).

But technical fit is not the deciding factor. The Angular 1 → 2 lesson applies: choosing a framework that fades means spending years rewriting while shipping nothing. Business risk assessment:

| Risk | React | Svelte | Vue |
|------|-------|--------|-----|
| Abandoned in 5 years | ~0% | ~5-10% | ~2-5% |
| Breaking rewrite (Angular-style) | ~2% | ~10-15% | ~5-10% |
| "Still works but feels legacy" in 5 years | ~15% | ~20% | ~25% |
| Can't hire devs who know it (UK market) | ~0% | ~40% | ~20% |
| Security patches stop within 3 years of last major | ~0% | ~10% | ~5% |

**React is too big to fail.** Meta runs Facebook, Instagram, WhatsApp Web, and Threads on it. Next.js, Remix, React Native, and thousands of enterprise apps depend on it. Even if Meta walked away, it's MIT-licensed and Vercel has existential dependency. The only realistic risk is React becoming the new jQuery — still maintained, but gradually "legacy." That's a 10-year timeline.

**Svelte's risk is funding concentration.** One primary maintainer (Rich Harris), funded by Vercel, who use Next.js (React) for their own commercial product. Svelte is a strategic bet for Vercel, not a core dependency. Svelte 4 → 5 (runes) showed willingness to break the API. Community is enthusiastic but thin.

**Vue's risk is similar but mitigated.** Evan You is funded by sponsors + VoidZero. Large adoption in Asia (Alibaba, Baidu). Vue 2 → 3 transition was painful (ecosystem split for years). UK/US hiring pool is thinner than React.

**Preact deserves a second look.** ~3 KB, React-compatible API (full compat layer via preact/compat), access to the entire React ecosystem. If React is the safe long-term bet, Preact gives you the API without the bundle size — and migration to full React is near-trivial if Preact ever fades. The contenteditable and TreeWalker pain from React applies equally, but the escape hatch (uncontrolled refs) is the same.

**Recommendation (revised)**: React. The contenteditable and TreeWalker pain is real but bounded — a few hundred lines of careful ref management, not a fundamental impossibility. The price is boilerplate and some fights with the reconciler. The price you don't pay is ever worrying whether your framework exists next year. Consider starting with Preact (identical API, 1/10th bundle) and swapping to full React only if needed — the migration is a dependency change, not a rewrite.

---

## file:// → http:// migration audit (Feb 2026)

Assumptions in the current JS/HTML that break or need rework when moving to served http://:

### Hard breaks (must fix)

- `BRISTLENOSE_VIDEO_MAP` contains `file://` URIs from `Path.as_uri()` — invalid from http:// pages. Need backend media endpoint or upload model
- `localStorage` keys have no project namespace — all reports on same http:// origin will clobber each other's edits, stars, hidden quotes, tags, codebook. Fix: prefix keys with project slug
- `postMessage(msg, '*')` in `player.js` — security hole over http://. Tighten to `window.location.origin`

### Architecture mismatches (work at migration time)

- 17 JS modules concatenated as IIFEs with implicit global dependencies → need ES modules + bundler
- All DOM manipulation is imperative (classList.toggle, innerHTML rebuild, TreeWalker text mutation) → must become component state in any framework
- `storage` event as IPC between report/codebook windows → won't fire if both become routes in same SPA window. Replace with state management
- Relative paths (`assets/…`, `../assets/…`, `sessions/…`) break with client-side routing. Need absolute paths from configurable base URL
- Hash fragments used for both player params (`#src=…&t=…`) and deep links (`#t-123`, `#sentiment`) — conflicts with hash-based SPA routing
- `setInterval` polling for closed player window — leaks in SPA (no cleanup on unmount)
- `codebook.html` opened via `window.open()` with hardcoded relative path

### Actually fine (survives migration unchanged)

- Dark mode (CSS custom properties + `light-dark()`)
- Print styles (media query)
- CSV export (blob URL in JS)
- Feedback HTTP check (already tests `location.protocol`)
- Modal infrastructure (event-driven, no protocol assumption)
- Toast notifications, keyboard shortcuts (just need cleanup on unmount)

---

## Server options

- **FastAPI** (Python) — already in the Python ecosystem; async; easy to add alongside the CLI; serves both the API and the built frontend
- **Flask** — simpler, synchronous, lighter weight; fine for a local tool
- Built-in `http.server` — too basic, no routing/API support

FastAPI is the natural choice: async (matches our pipeline), Pydantic models (already used everywhere), auto-generated API docs, WebSocket support for live updates.

---

## Migration path

This is a large effort. Incremental approach:

1. **`bristlenose serve`** — add a FastAPI server that serves the current static HTML + a few API endpoints (read/write people.yaml, read intermediate JSON)
2. **Data API first** — replace localStorage → clipboard → paste → re-render with direct API calls. Keep the vanilla JS but swap the storage layer
3. **Component-by-component migration** — replace one interactive feature at a time (e.g. participant table → Svelte component) while keeping the rest as static HTML
4. **Full SPA** — eventually the entire report is a framework app served by the local server

Step 1 alone would fix the immediate pain (cross-page state, file writes) without touching the frontend. Steps 2–4 can happen gradually.

### Export-sharing depends on this migration

The export-sharing feature (see `docs/design-export-sharing.md`) was originally designed for the vanilla JS + static HTML stack, using browser-side DOM cloning and a zip library (fflate). Analysis in Feb 2026 concluded: **build export once, after React, not twice.** The React app can hydrate from either a server API or an embedded JSON blob, so export falls out naturally as "snapshot the project data, embed in the React app shell, output a standalone file." Building it on vanilla JS first would create plumbing that the migration replaces, and maintaining two export paths during the hybrid phase adds friction to every component migration. See the "Dependency on React migration" section in `docs/design-export-sharing.md`.

This makes the reactive UI migration not just a developer experience improvement but a **prerequisite for the sharing story** — the feature that makes Bristlenose useful beyond the solo researcher. The near-term sharing mechanism is CSV/Miro export (see `docs/private/design-miro-bridge.md`); the long-term mechanism is the rich interactive report itself as a shareable artefact, which requires this migration.
