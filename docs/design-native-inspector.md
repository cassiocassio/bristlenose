# Tag Inspector — Native Inspector Panel Design

## Vision

Make the tag sidebar a **truly independent module** that can render in any container:

| Container | Status | Panel name |
|-----------|--------|------------|
| Inline div (CLI serve mode, browser) | Shipped | Tag sidebar |
| Native macOS `.inspector()` panel | Planned (Phase 1) | **Tag Inspector** |
| Popout NSWindow (second monitor) | Planned (Phase 2) | Tag Inspector (detached) |
| CLI browser tab (bonus) | Free with BroadcastChannel | Tag sidebar in new tab |

Same HTML, same CSS, same React component — different wiring underneath. The native panel uses SwiftUI's `.inspector(isPresented:)` (macOS 14+), giving Xcode-style open/close animation, drag-to-resize, and system chrome for free. The content inside is a WKWebView rendering the same `TagSidebar` React component.

## Nomenclature (user-facing)

| Panel | User-facing name | Location | Shortcut | Notes |
|-------|-----------------|----------|----------|-------|
| Right panel (native, tags) | **Tag Inspector** | SwiftUI `.inspector()` | `Cmd+Opt+I` | Rename to just "Inspector" when more tabs land |
| Bottom panel (web, Analysis tab) | **Heatmap** | Web content, unchanged | None (toolbar only) | `Cmd+Opt+D` is system-reserved (Dock) |
| Left web panel (sections/themes) | **Navigator** | Web content | existing | Xcode precedent. Per-tab content: Contents / Codes / Signals |
| Left native panel (projects) | **Projects Sidebar** | `NavigationSplitView` | `Cmd+Opt+S` | System-provided toggle |

## The Hard Problem: Bidirectional State

The tag sidebar isn't a read-only display. It has dense, bidirectional interactions with the quotes content:

### Sidebar → Quotes (sidebar actions that affect the main content)

| Action | Effect on quotes | Current mechanism |
|--------|-----------------|-------------------|
| Check/uncheck tag | Filter visible quotes | `QuotesStore.setTagFilter()` |
| Solo mode (click bar) | Show only quotes with this tag | `QuotesStore.setTagFilter()` + snapshot |
| Eye toggle (hide group) | Hide badges on quote cards | `SidebarStore.hiddenTagGroups` → read by QuoteCard |
| Click badge (with selection) | Assign tag to selected quotes | `QuotesStore.addTag()` → API PUT |
| Select All / Clear | Bulk filter toggle | `QuotesStore.setTagFilter()` |

### Quotes → Sidebar (main content actions that affect the sidebar)

| Action | Effect on sidebar | Current mechanism |
|--------|------------------|-------------------|
| Add/remove tag on quote | Update tag counts + micro-bars | `QuotesStore.tags` change → re-render |
| Hide/unhide quote | Recalculate visible tag counts | `QuotesStore.hidden` change → re-render |
| Star/unstar quote | (No effect currently) | — |
| Select/deselect quotes | Enable "assign" mode on badges | `FocusContext.selectedIds` |
| Autocode proposals | Show tentative counts (two-tone bars) | `codebook.tentative_count` from API |

### Shared state reads

| State | Who reads | Who writes |
|-------|-----------|------------|
| `quotes[]` | Sidebar (for counts) | QuoteSections (init from API) |
| `tags[domId][]` | Sidebar (for counts), QuoteCard (for badges) | QuotesStore (from API + user edits) |
| `hidden[domId]` | Sidebar (exclude from counts), QuoteCard | QuotesStore |
| `tagFilter` | Sidebar (checkbox state), QuoteGroup (filter) | Sidebar |
| `hiddenTagGroups` | Sidebar (eye icons), QuoteCard (badge filter) | Sidebar |
| `selectedIds` | Sidebar (assign mode) | FocusContext (click/keyboard) |
| `soloTag` | Sidebar (highlight) | Sidebar |

**Core challenge:** In-process, these are just shared JS variables. Cross-process (separate WKWebView), every mutation becomes a message.

## Architecture: Message Channel

When the tag sidebar runs in a separate WKWebView (Tag Inspector or popout window), the shared stores are replaced by a message channel.

### Channel options

| Channel | Latency | Complexity | Works for popout? |
|---------|---------|------------|-------------------|
| `BroadcastChannel` API | ~0ms | Low | Yes (same origin) |
| Native bridge relay (WKWebView → Swift → WKWebView) | ~1-5ms | High | Yes (any window) |
| WebSocket/SSE via FastAPI | ~5-20ms | High | Yes (any process) |

**Confirmed: `BroadcastChannel`** — spike passed (28 Mar 2026). See general pattern docs at `docs/design-wkwebview-messaging.md`.

### Prerequisite: BroadcastChannel + non-persistent WKWebView spike (DONE)

`WebView.swift` uses `WKWebsiteDataStore.nonPersistent()`. Each call creates a separate ephemeral store. BroadcastChannel is scoped to the storage partition, not just the origin. Spike validated that two WKWebViews sharing the same `.nonPersistent()` data store instance communicate via BroadcastChannel successfully. Separate instances are fully isolated (negative test confirmed).

**Full messaging architecture:** `docs/design-wkwebview-messaging.md` — covers shared store singleton, channel naming, message envelope, peer detection, multi-project scoping, transport comparison, and gotchas. That doc is the general reference; this doc covers Tag Inspector-specific protocol and interactions.

### Spike Results

**Spike run: 28 Mar 2026, macOS 26.1 Tahoe, M2 Max.**

Both WKWebViews load `http://127.0.0.1:8150/report/` from a running `bristlenose serve` instance.
Test JS injected via `WKUserScript(.atDocumentEnd)`. Spike code: `desktop/testtest/`.

| Question | Data store | Process pool | BroadcastChannel | localStorage |
|----------|-----------|-------------|:---:|:---:|
| Q1: Shared config | `.default()` (persistent singleton) | default | Pass | Pass |
| Q2a: Shared store + pool | `.nonPersistent()` (shared instance) | shared | **Pass** | Pass |
| Q2b: Shared store only | `.nonPersistent()` (shared instance) | separate | Pass | Pass |
| Q3: Fully isolated | `.nonPersistent()` (separate instances) | separate | Fail | Fail |

**Decision: BroadcastChannel is the transport.** Q2a (the production scenario) passes — two WKWebViews sharing the same `.nonPersistent()` data store instance communicate via BroadcastChannel with ~0ms latency. No native bridge relay needed. Process pool isolation (Q2b) does not break BC — only the data store instance matters.

Note: the original spike used a custom `spike://` scheme which crashed with `.nonPersistent()` on macOS 26. Switching to HTTP (matching production) eliminated the crash. The `.nonPersistent()` crash was scheme-specific, not a general WebKit regression.

### Message protocol

```typescript
// Every message includes seq + nonce for ordering and defence-in-depth
type ChannelMessage = { seq: number; nonce: string } & (MainToSidebar | SidebarToMain)

// Main content → Tag sidebar
type MainToSidebar =
  | { type: "tag-counts"; counts: Record<string, number>; tentative: Record<string, number> }
  | { type: "selection-changed"; selectedIds: string[] }
  | { type: "quotes-changed" }
  | { type: "project-changed"; projectId: string }
  | { type: "tab-changed"; tab: string }
  | { type: "flash-tag"; tag: string }

// Tag sidebar → Main content
type SidebarToMain =
  | { type: "filter-changed"; unchecked: string[] }
  | { type: "solo-enter"; tag: string }
  | { type: "solo-exit" }
  | { type: "assign-tag"; tag: string; quoteIds: string[] }
  | { type: "hidden-groups-changed"; groups: string[] }
```

### Solo mode teardown rules

Solo mode is dangerous across windows because the snapshot (`savedTagFilter`) lives in the sidebar but the actual filter mutation happens on the main side. Three teardown triggers:

1. **Tab change:** Main content navigates away from Quotes → sends `tab-changed` → sidebar auto-exits solo mode → sends `solo-exit` back → main restores saved filter.
2. **Sidebar/popout close:** Main-side hook detects peer disappearance (heartbeat or `BroadcastChannel.close`). If `soloTag` active, auto-restores saved filter. Saved filter stored on **both sides** for orphan recovery.
3. **Project switch:** `project-changed` clears all sidebar state. Main restores saved filter before switching.

### Tag counts: hybrid approach

Sidebar fetches codebook independently via `GET /codebook` (already returns `tag.count`). Self-sufficient for initial render. Main content pushes live delta updates during the session for real-time counts. Best of both worlds.

## Component Refactoring

### `TagSidebarChannel` interface

```typescript
interface TagSidebarChannel {
  // Read — state pushed from main content (or derived locally in inline mode)
  tagCounts: Record<string, number>;
  tentativeCounts: Record<string, number>;
  selectedQuoteIds: Set<string>;
  hiddenGroups: Set<string>;
  soloTag: string | null;
  uncheckedTags: Set<string>;
  activeTab: string | null;

  // Write — actions that flow back to main content
  setTagFilter(unchecked: string[]): void;
  enterSoloMode(tag: string): void;
  exitSoloMode(): void;
  assignTag(tag: string, quoteIds: string[]): void;
  setHiddenGroups(groups: string[]): void;

  // Feedback — animation triggers from main content
  onFlashTag?: (tag: string) => void;
}
```

### `useTagSidebarChannel()` hook

```typescript
// Inline mode — delegates to existing stores
function useTagSidebarChannel(mode: "inline"): TagSidebarChannel

// Standalone mode — uses BroadcastChannel (or native relay)
function useTagSidebarChannel(mode: "standalone"): TagSidebarChannel
```

TagSidebar.tsx receives a `TagSidebarChannel` instead of importing stores directly. Same component, different plumbing.

### `useTagSidebarBroadcast()` hook (main content side)

Installed in the main app when a standalone sidebar is connected. Listens for sidebar messages, dispatches to QuotesStore/FocusContext. Publishes state changes to the channel. Stores solo `savedTagFilter` copy for orphan recovery.

## Native macOS Integration

### Security: `SecureWebViewConfiguration` factory

The main WebView in `WebView.swift` enforces five security rules inline in `makeNSView()`:
1. Navigation restricted to `127.0.0.1`
2. Bridge origin validation
3. No string interpolation into JS
4. Ephemeral `WKWebsiteDataStore`
5. Settings interception

**Extract a `makeSecureConfiguration()` static method** that both `WebView` and `InspectorView` call. Single source of truth for WKWebView security policy.

The Tag Inspector WKWebView should **not** register the `navigation` bridge message handler — it communicates via BroadcastChannel (or native relay), not the bridge. Use a separate config from the factory (without bridge handler) but share the same `.nonPersistent()` data store instance.

### Phase 1: Tag Inspector panel

```swift
// ContentView.swift
.inspector(isPresented: $bridgeHandler.showTagInspector) {
    TagInspectorView(bridgeHandler: bridgeHandler, serveManager: serveManager)
        .inspectorColumnWidth(min: 220, ideal: 280, max: 400)
}
```

`TagInspectorView.swift`:
- Tab picker at top (SF Symbol icons): Tags, Info (future: Quick Help)
- Tags tab: WKWebView loading `/report/_inspector/tags` route (standalone TagSidebar)
- Info tab: native SwiftUI view showing selected quote metadata
- WKWebView created via `SecureWebViewConfiguration.make(bridgeHandler: nil, authToken:)`
- `webView.underPageBackgroundColor = .clear` for native vibrancy bleed-through
- Visual integration: SF Pro font injection, density-matched spacing, transparent background CSS

Route `/report/_inspector/tags` — under `/report/` namespace, `_` prefix signals internal. Also accessible in CLI serve mode browser tabs (bonus popout workflow).

### Phase 2: Popout window

"Detach to Window" button in inspector creates an `NSWindow` directly (not via `WKUIDelegate`/`window.open()` like the video player). Same React component, same channel, different native container.

### Popout window lifecycle

**(a) Main window closes → popout must close too.**
`NSWindow.addChildWindow(_:ordered:)` — popout is a child, auto-closes with parent.

**(b) Project switch with popout open.**
Close the popout automatically. Channel is scoped to project ID — old channel goes silent on switch.

**(c) Multiple popouts for same project.**
`hasTagInspectorPopout: Bool` in BridgeHandler. If already open, bring to front instead of creating a second.

**(d) Inspector WKWebView lifecycle on project switch.**
`.id(project.id)` on the inspector's WKWebView wrapper forces recreation.

### Menu and toolbar rewiring

When the Tag Inspector ships:
- View menu "Show Tags" → rename to "Show Tag Inspector", change shortcut from `Cmd+Opt+T` to `Cmd+Opt+I` (Xcode inspector convention). Toggles `bridgeHandler.showTagInspector` (native state), not `toggleRightPanel` (web bridge message). Frees `Cmd+Opt+T` for system Show/Hide Toolbar duty
- Toolbar button `sidebar.right` on `ContentView.swift:425` → writes to `showTagInspector`
- Embedded mode suppresses web tag sidebar: SidebarLayout skips columns 5+6 when `isEmbedded()`

## Multi-Project / Multi-Window

| Scenario | Channel scoping |
|----------|----------------|
| Single project, single window | `bristlenose-tags-{projectId}-{nonce}` |
| Single project, inspector + popout | Same channel |
| Multiple projects (future) | Different project IDs = different channels |
| CLI serve, different ports | Origin isolation (different ports = different origins) |

Channel name includes project ID **and** a session-random nonce for defence-in-depth against same-origin message spoofing.

## UX Enhancements for Standalone Mode

- **Optimistic count update:** Sidebar increments tag count immediately on assign-click (before round-trip confirms). Reconciles on `tag-counts` response from main.
- **Selection status line:** When `mode === "standalone"` and quotes are selected, show "3 quotes selected" at the top of the sidebar. Researcher may not be looking at the main window.
- **Reconnection state:** When BroadcastChannel connection lost (inspector WKWebView reloads, main navigates away), sidebar shows "Reconnecting..." rather than stale data.

## Implementation Sequence

0. ~~**Spike: BroadcastChannel across non-persistent WKWebViews** — DONE (28 Mar 2026). Pass. BroadcastChannel confirmed as transport. See `docs/design-wkwebview-messaging.md`~~
1. **Extract `SecureWebViewConfiguration` factory** from `WebView.swift` — use `SharedConfigStore` pattern from messaging doc
2. **Refactor TagSidebar to accept a `TagSidebarChannel`** (React only). Inline mode delegates to existing stores. All existing tests pass unchanged
3. **Add `/report/_inspector/tags` route** — minimal page rendering standalone TagSidebar
4. **Implement BroadcastChannel adapter** — channel `bristlenose-tags-{projectId}`, `seq` + `nonce` envelope per `docs/design-wkwebview-messaging.md`
5. **Add `useTagSidebarBroadcast()` to main content** — publishes state, listens for commands, stores solo `savedTagFilter` copy
6. **Visual integration** — transparent background, SF Pro font, density-matched spacing
7. **Native: add `.inspector()` to ContentView** — WKWebView via `SecureWebViewConfiguration`. Rewire toolbar + View menu to toggle `showTagInspector`
8. **Suppress web tag sidebar in embedded mode** — SidebarLayout skips columns 5+6 when `isEmbedded()`
9. **Native: popout window** — "Detach to Window", `addChildWindow` lifecycle, `hasTagInspectorPopout` guard
10. **Test** — Vitest for channel adapters, Playwright for cross-tab (CLI), manual QA for native

## Files Affected

### Frontend (React)
- `TagSidebar.tsx` — accept `TagSidebarChannel` instead of direct store imports
- New: `hooks/useTagSidebarChannel.ts` — inline vs standalone adapters
- New: `hooks/useTagSidebarBroadcast.ts` — main content side publisher
- New: `pages/InspectorTagsPage.tsx` — standalone route wrapper
- `router.tsx` — add `/report/_inspector/tags` route
- `components/SidebarLayout.tsx` — suppress columns 5+6 when `isEmbedded()`

### Desktop (Swift)
- `ContentView.swift` — add `.inspector()` modifier, rewire toolbar button
- New: `TagInspectorView.swift` — tab picker + WKWebView content
- New: `SecureWebViewConfiguration.swift` — shared config factory
- `BridgeHandler.swift` — add `showTagInspector`, `hasTagInspectorPopout`
- `MenuCommands.swift` — rewire "Show Tags" to toggle native inspector

### Shared CSS
- Inspector-specific overrides via CSS custom properties (no component fork). Transparent background, SF Pro font, density adjustments

## Review Findings (from usual suspects, 27 Mar 2026)

20 items triaged. Bugs/errors all addressed in this doc. Full findings in conversation history. Key items actioned:
- BroadcastChannel + non-persistent data store spike (critical — step 0)
- `SecureWebViewConfiguration` factory (step 1)
- Solo mode teardown rules (3 triggers)
- Popout window lifecycle (child window, project switch, duplicate guard)
- Route under `/report/_inspector/` namespace
- Bridge handler collision prevention (separate config, no bridge handler on inspector)
- Menu + toolbar rewiring traced
- Channel interface expanded (hiddenGroups, soloTag, uncheckedTags, flashTag)
- Sequence numbers + nonce on protocol messages
- Security gate: production must use HTTP navigation, not `loadHTMLString`
- SECURITY.md update needed when BroadcastChannel ships
