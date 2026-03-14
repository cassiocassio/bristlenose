# Prompt: Build Sessions Left Sidebar

Use this prompt to implement the sessions sidebar in a fresh Claude session.

---

## Context

Read the plan first: `.claude/plans/jaunty-brewing-cocke.md`

The sessions sidebar is a left-hand navigation panel for the Sessions tab and Transcript pages. It's a compact, data-adaptive version of the sessions table. Clicking a session navigates to its transcript. The active session highlights when viewing a transcript page.

The design is finalised in the HTML mockup at `docs/mockups/sidebar-all-tabs.html` — open it in a browser (`python3 -m http.server 8199` from repo root, then visit `http://localhost:8199/docs/mockups/sidebar-all-tabs.html`). Drag-resize the "i-A" and "i-B" panels to see all responsive breakpoints.

## Design rules (non-obvious, learned through iteration)

1. **Date > duration priority** — date is always the first metadata shown (most useful for recall: "the Monday one"). Duration appears second
2. **No stacking without thumbnail** — when there's no video thumbnail, duration and date stay inline on the same row. Never stack vertically without a thumbnail
3. **Thumbnail forces row depth** — the 36px thumbnail height creates vertical space, which justifies stacking date above duration in a right-aligned column. The thumbnail is the structural trigger for stacking
4. **Names > thumbnails** — readable names are more important than showing thumbnails. Thumbnails only appear at 360px+ where there's enough room for everything
5. **Middle dot separator** (`·`) between duration and date when both are inline
6. **Compact formats** — duration: "47m" / "1h 03" (not "47 min"). Date: "12 Feb" / "Wed 12 Feb"
7. **Multiple moderators is rare, multiple participants per session is rare** — the common case is simple. Don't optimise the narrow layout for the rare worst case

## What to build

### 1. Utility functions in `frontend/src/utils/format.ts`

Add two new functions (with tests):

```typescript
/** "47m" / "1h 03" / "2h 23" */
export function formatCompactDuration(seconds: number): string

/** "12 Feb" or "Wed 12 Feb" (includeDay=true) */
export function formatCompactDate(isoDate: string, includeDay?: boolean): string
```

### 2. `frontend/src/components/SessionsSidebar.tsx` — NEW

Reference implementation: `frontend/src/components/TocSidebar.tsx` (183 lines, independent fetch, overlay auto-close pattern).

Data:
- Fetch `GET /api/projects/{id}/sessions` via `apiGet()` + `useProjectId()`
- Derive variant from data: `isOneToOne` (every session has exactly 1 participant), `hasMultipleModerators`, `hasVideo`

Width response (read `tocWidth` from `useSidebarStore()`):
- 200px: badge + name + date
- 260px: + duration + `·` separator
- 320px: + day-of-week prefix
- 360px: + full names (no-thumb) / + thumbnail + stacked date/duration + full names (has-thumb)

The component renders into the `.toc-sidebar-body` slot — it does NOT render its own header or close button (SidebarLayout handles that).

HTML structure per entry — follow the mockup exactly. Two variants:

**No-thumbnail (1:1, no video):**
```html
<a class="session-entry" href="/report/sessions/{id}">
  <div class="session-entry-row">
    <span class="badge">p1</span>
    <span class="session-entry-name">Rachel</span>
    <span class="session-entry-duration">47m</span>
    <span class="session-entry-sep">·</span>
    <span class="session-entry-date"><span class="session-entry-dow">Wed </span>12 Feb</span>
  </div>
</a>
```

**Has-thumbnail (multi-participant, video):**
```html
<a class="session-entry" href="/report/sessions/{id}">
  <div class="session-entry-row">
    <span class="badge session-id-badge">#1</span>
    <div class="session-entry-speakers">
      <div class="session-entry-speaker-row">
        <span class="badge">m1</span>
        <span class="badge">p1</span>
        <span class="session-entry-name">Rachel</span>
      </div>
      <div class="session-entry-speaker-row">
        <!-- spacer for moderator badge column -->
        <span class="badge">p2</span>
        <span class="session-entry-name">David</span>
      </div>
    </div>
    <!-- Inline: shown < 360px -->
    <span class="session-entry-duration session-entry-inline-duration">1h 00</span>
    <span class="session-entry-sep session-entry-inline-sep">·</span>
    <span class="session-entry-date session-entry-inline-date">15 Feb</span>
    <!-- Stacked: shown >= 360px (when thumbnail appears) -->
    <div class="session-entry-right">
      <span class="session-entry-date">Sat 15 Feb</span>
      <span class="session-entry-duration">1h 00</span>
    </div>
    <div class="session-entry-thumb"><img src="..." alt="" /></div>
  </div>
</a>
```

Element visibility is JS-driven in production (not CSS container queries). Read `tocWidth` from SidebarStore and derive booleans:
```typescript
const showDuration = tocWidth >= 260;
const showDow = tocWidth >= 320;
const showThumb = hasVideo && tocWidth >= 360;
const showFullNames = tocWidth >= 360;
```

Conditionally render elements based on these. When `showThumb` is true, render the stacked `.session-entry-right` + `.session-entry-thumb` and hide the inline duration/sep/date. When false, render inline duration/sep/date and hide the stacked elements.

Active state:
- `useMatch("/report/sessions/:sessionId")` → compare `params.sessionId`
- Apply `.active` class to matching entry

Click handling:
- Use `<a>` with real `href` for Cmd+click support
- `onClick`: `if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); navigate(path);`

Data-shape rules:
- `isOneToOne`: every session has exactly 1 participant AND exactly 1 moderator across the project → no `#N` session IDs, no moderator badges
- `hasMultipleModerators`: >1 distinct moderator across all sessions → show moderator badges
- `hasVideo`: any session has `has_video === true` → enable thumbnail variant at 360px+

### 3. CSS in `bristlenose/theme/organisms/sidebar.css`

Add the `.session-entry` molecule. Copy the styles from the mockup's `<style>` block — everything between the `session-entry` comment and the `codebook-entry` comment. These are marked `/* NEW */` in the mockup.

**Do NOT** copy the container query rules (`@container`) — those are mockup-only. Production uses JS-driven visibility.

### 4. `frontend/src/components/SidebarLayout.tsx` — MODIFY

Add props:
```typescript
interface SidebarLayoutProps {
  active: boolean;
  leftPanel?: React.ReactNode;
  leftPanelTitle?: string;
  children: React.ReactNode;
}
```

- Default `leftPanel` to `<TocSidebar>`, `leftPanelTitle` to `"Contents"`
- Render `leftPanel` into the `.toc-sidebar-body` slot
- Render `leftPanelTitle` into the `.sidebar-title` span
- Conditionally render Minimap + TagSidebar + tag-rail only when on Quotes route (check with `useMatch`)

### 5. `frontend/src/layouts/AppLayout.tsx` — MODIFY

```typescript
const isQuotes = useMatch("/report/quotes");
const isSessions = useMatch("/report/sessions");
const isTranscript = useMatch("/report/sessions/:sessionId");
const showSidebar = !!(isQuotes || isSessions || isTranscript);

<SidebarLayout
  active={showSidebar}
  leftPanel={(isSessions || isTranscript) ? <SessionsSidebar /> : undefined}
  leftPanelTitle={(isSessions || isTranscript) ? "Sessions" : undefined}
>
```

### 6. Tests

- `SessionsSidebar.test.tsx`: mock API response, test variant A (1:1 → no session IDs), variant B (multi-participant → session IDs shown), active highlight, click navigation
- `formatCompactDuration.test.ts` / `formatCompactDate.test.ts`: edge cases (0 seconds, exactly 1 hour, null date, etc.)
- Update `SidebarLayout.test.tsx` if it exists: test new props

### 7. Type exports

The sessions API types (`SessionResponse`, `SessionsListResponse`, `SpeakerResponse`) are currently private in `frontend/src/islands/SessionsTable.tsx`. Either:
- Extract them to `frontend/src/utils/types.ts` (preferred), or
- Duplicate the minimal subset needed in `SessionsSidebar.tsx`

## Verification

1. `cd frontend && npm run build` — type-checks
2. `cd frontend && npm test` — unit tests pass
3. `.venv/bin/python -m pytest tests/` — Python tests pass
4. `.venv/bin/ruff check .` — no lint errors
5. Manual QA: `bristlenose serve trial-runs/project-ikea`
   - Sessions tab: sidebar shows sessions
   - Click session → navigates to transcript, sidebar highlights
   - `[` keyboard shortcut toggles sidebar
   - Drag-to-resize works, content adapts
   - Quotes tab: unchanged (TocSidebar still works)

## Files reference

- Plan: `.claude/plans/jaunty-brewing-cocke.md`
- Mockup: `docs/mockups/sidebar-all-tabs.html` (v4 — the canonical design reference)
- TocSidebar (reference impl): `frontend/src/components/TocSidebar.tsx`
- SidebarLayout: `frontend/src/components/SidebarLayout.tsx`
- SidebarStore: `frontend/src/contexts/SidebarStore.ts`
- AppLayout: `frontend/src/layouts/AppLayout.tsx`
- Session types: `frontend/src/islands/SessionsTable.tsx` (private, lines ~1-30)
- Format utils: `frontend/src/utils/format.ts`
- Production sidebar CSS: `bristlenose/theme/organisms/sidebar.css`
- API endpoint: `bristlenose/server/routes/sessions.py`
