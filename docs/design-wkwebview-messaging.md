# WKWebView Cross-View Messaging

## What this is

A validated architectural pattern for communication between multiple `WKWebView` instances in the same macOS app. Applies to any feature where two or more web views need to share state: inspector panels, popout windows, side-by-side editing, secondary displays.

## The finding

**BroadcastChannel works across WKWebViews that share the same `WKWebsiteDataStore` instance.** Process pool isolation does not matter — only the data store.

Validated 28 Mar 2026 on macOS 26.1 Tahoe (M2 Max). BroadcastChannel has been in WebKit since Safari 15.4 (March 2022, macOS 12.3), so this works on all supported OS versions (deployment target: macOS 15 Sequoia).

### Spike results

| Configuration | Data store | Process pool | BroadcastChannel | localStorage |
|--------------|-----------|-------------|:---:|:---:|
| Shared config | `.default()` (persistent singleton) | default | Pass | Pass |
| Shared store + shared pool | `.nonPersistent()` (same instance) | same `WKProcessPool` | **Pass** | Pass |
| Shared store + separate pools | `.nonPersistent()` (same instance) | separate `WKProcessPool()` | Pass | Pass |
| Fully isolated | `.nonPersistent()` (different instances) | separate `WKProcessPool()` | Fail | Fail |

**Key insight:** `WKWebsiteDataStore.nonPersistent()` creates a new ephemeral partition on every call. Two views that each call `.nonPersistent()` independently get separate partitions — BroadcastChannel, localStorage, cookies, and all Web Storage APIs are isolated between them. To share, you must pass the **same instance** to both configurations.

### Why this matters

The Bristlenose desktop app uses `.nonPersistent()` for security (rule 4: no cross-project cookie/session leakage). Every call to `.nonPersistent()` returns a fresh store, so naively creating two WKWebViews would get two isolated stores with no communication path. The spike confirmed that sharing a single `.nonPersistent()` instance — stored as a singleton — gives both views the same storage partition, enabling BroadcastChannel communication while preserving the ephemeral (no-disk) security property.

## Architecture: the shared store singleton

```swift
/// Vends a single .nonPersistent() data store instance for all WKWebViews
/// within the same project that need to communicate.
class SharedConfigStore {
    static let shared = SharedConfigStore()

    let dataStore: WKWebsiteDataStore
    let processPool: WKProcessPool  // optional — pool doesn't affect BC

    private init() {
        dataStore = .nonPersistent()
        processPool = WKProcessPool()
    }
}
```

Both the main content WKWebView and any secondary WKWebViews (inspector, popout) must use `SharedConfigStore.shared.dataStore` instead of calling `.nonPersistent()` directly.

### Multi-project scoping

When multi-project support ships, the singleton becomes a per-project dictionary:

```swift
class SharedConfigStore {
    static let shared = SharedConfigStore()
    private var stores: [String: WKWebsiteDataStore] = [:]

    func dataStore(for projectId: String) -> WKWebsiteDataStore {
        if let existing = stores[projectId] { return existing }
        let store = WKWebsiteDataStore.nonPersistent()
        stores[projectId] = store
        return store
    }
}
```

Each project gets its own ephemeral partition. Views within the same project share the partition (enabling BroadcastChannel). Views across different projects are isolated (no cross-project leakage).

## BroadcastChannel usage pattern

### Channel naming convention

```
bristlenose-{purpose}-{projectId}
```

Examples:
- `bristlenose-tags-1` — tag sidebar ↔ main content
- `bristlenose-player-1` — player popout ↔ main content (future)
- `bristlenose-search-1` — search results panel ↔ main content (future)

The `projectId` scopes the channel to the project. Two projects open simultaneously use different channels.

### Message envelope

Every message includes metadata for ordering and defence-in-depth:

```typescript
interface ChannelEnvelope {
    seq: number;       // monotonic counter — detect out-of-order delivery
    nonce: string;     // random per-session — detect cross-session replay
    type: string;      // discriminated union tag
    [key: string]: unknown;
}
```

### Lifecycle

```
Main WKWebView loads /report/
  → React mounts, creates BroadcastChannel('bristlenose-tags-{projectId}')
  → Publishes initial state (tag counts, selection, active tab)

Inspector WKWebView loads /report/_inspector/tags
  → React mounts in standalone mode
  → Creates same BroadcastChannel('bristlenose-tags-{projectId}')
  → Receives initial state, renders sidebar

User action (either side):
  → Sender publishes message with seq + nonce
  → Receiver processes, updates local state
  → ~0ms latency (same process, shared memory)
```

### Peer detection and orphan recovery

BroadcastChannel has no built-in peer discovery. Two patterns for detecting whether the other side is alive:

1. **Heartbeat:** Periodic `{ type: "heartbeat" }` messages. If no heartbeat for N seconds, show "Reconnecting..." state. Simple, slightly wasteful.

2. **Request/response:** On connect, send `{ type: "hello" }`. Peer responds with `{ type: "hello-ack", state: {...} }`. If no ack after timeout, peer isn't running. More efficient, slightly more complex.

Recommended: **heartbeat** for the first implementation. Switch to request/response if heartbeat traffic becomes a concern (unlikely — these are local, in-process messages).

## Transport comparison (for future reference)

| Transport | Latency | Complexity | Cross-window | Cross-process | Auth needed |
|-----------|---------|------------|:---:|:---:|:---:|
| **BroadcastChannel** | ~0ms | Low | Yes | No | No |
| Native bridge relay (Swift) | ~1-5ms | High | Yes | Yes | No |
| WebSocket via serve | ~5-20ms | Medium | Yes | Yes | Yes |
| `postMessage` (window ref) | ~0ms | Medium | Yes | No | No |
| SharedWorker | ~0ms | Medium | Yes | No | No |

**BroadcastChannel is the default choice** for any WKWebView-to-WKWebView communication within the same app, provided both views share a data store instance.

Use **native bridge relay** (Swift `WKScriptMessageHandler` → Swift relay → `callAsyncJavaScript`) only when views are in separate processes or separate data stores (e.g. cross-project communication, if ever needed).

Use **WebSocket** only when communication crosses process boundaries (e.g. a separate Electron app talking to Bristlenose serve — not a current use case).

## Gotchas

- **`.nonPersistent()` creates a new partition every call** — the most important thing to remember. Two views that each call `.nonPersistent()` cannot communicate. Store the instance in a singleton
- **Custom URL schemes + `.nonPersistent()` crash on macOS 26** — `WKURLSchemeHandler` with a `spike://` scheme and `.nonPersistent()` data store crashes the WebKit network process. Use HTTP (localhost) instead. This is a WebKit bug specific to custom schemes, not a general `.nonPersistent()` regression
- **`WKWebViewConfiguration` cannot be shared between two WKWebViews** — each view needs its own config object (they have their own `userContentController` for message handlers and user scripts). Share the data store and process pool via the config, not the config itself
- **`WKUserScript` injection is the cleanest way to add test/instrumentation JS** — `.atDocumentEnd` fires after the page's DOM is ready. Cleaner than `evaluateJavaScript` (which requires timing coordination) and avoids baking test code into the HTML
- **Process pool sharing is optional** — separate `WKProcessPool` instances do not break BroadcastChannel. Pool isolation gives WebKit freedom to use separate renderer processes, but BroadcastChannel works regardless. Share the pool only if you want to minimize process count
- **Sandbox + Outgoing Connections** — if the app has App Sandbox enabled, "Outgoing Connections (Client)" must be ticked for WKWebViews to load from localhost. Without it, navigation silently fails (blank page, no error)

## Spike code

`desktop/testtest/` — standalone Xcode project with two side-by-side WKWebViews, a segmented picker (Q1–Q3), and a colour-coded log pane. Loads from a running `bristlenose serve` instance. Test JS injected via `WKUserScript`. Run with `bristlenose serve trial-runs/project-ikea` + Cmd+R in Xcode.

## Use cases (current and future)

| Feature | Channel | Main → Secondary | Secondary → Main |
|---------|---------|:---:|:---:|
| **Tag Inspector** (planned) | `bristlenose-tags-{pid}` | Tag counts, selection, tab changes | Filter changes, tag assignments, solo mode |
| **Tag Inspector popout** (planned) | Same channel | Same | Same |
| **CLI browser tab popout** (free) | Same channel | Same | Same |
| Video player state sync (future) | `bristlenose-player-{pid}` | Seek commands, speed changes | Play state, current time |
| Search results panel (future) | `bristlenose-search-{pid}` | Search query | Result selection, scroll-to |
| Annotation overlay (future) | `bristlenose-annotations-{pid}` | Transcript position | Annotation edits |

## Related docs

- `docs/design-native-inspector.md` — Tag Inspector panel design (first consumer of this pattern)
- `desktop/CLAUDE.md` — desktop app architecture, security rules, bridge communication
- `SECURITY.md` — local-first design, credential storage
