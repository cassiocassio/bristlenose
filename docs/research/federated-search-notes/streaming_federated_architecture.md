# Streaming federated search across lenses — architecture and UX

Scope: should Bristlenose's global toolbar search run one searcher per lens (quotes, transcript segments, people, tags, themes/sections, signals, sessions — optionally per project across a folder) simultaneously, and build the results UI as each returns? How to do it well in FastAPI + SQLite + React + Swift host + CLI.

Local codebase facts checked for this note (27 Sep 2026, `main` at `bc5cf34b`):
- `bristlenose/server/db.py:44-60` builds a SQLAlchemy engine with `check_same_thread=False` and the default pool (file DB) — i.e. each thread can get its own pooled connection. `db.py:79-81` sets `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` on every connect.
- No full-text index exists: `grep -rniE "fts5|create virtual table" bristlenose/` returns nothing, and no `/search` route exists in `bristlenose/server/routes/`. Any search today would be `LIKE` scans or Python-side filtering.

---

## 1. How do existing "search everywhere" products handle results arriving at different times?

### Takeaway
The two best-documented systems sit at opposite ends. JetBrains Search Everywhere is explicitly contributor-based and streaming: each contributor pushes items into a consumer as it finds them, groups are ordered by a *contributor* sort weight (not arrival time), and each contributor is capped with a "has more" flag. Algolia Autocomplete, by contrast, runs sources concurrently but **waits for all of them (`Promise.all`) before updating the panel once**, using a 300 ms "stalled" threshold to decide when to show a loading state. Progressive per-group rendering is therefore a deliberate choice, not the industry default — it pays off when sources have genuinely different latencies (JetBrains indexes; Bristlenose's cross-project fan-out), and costs layout stability when they don't.

### Cited Findings
**JetBrains (legacy `SearchEverywhereContributor`, still the model most plugins implement):**
- `fetchElements(String pattern, ProgressIndicator progressIndicator, Processor<? super Item> consumer)` — "Performs searching process. All found items will be passed to consumer." Search stops when the progress indicator is cancelled or the consumer returns `false` for an item (i.e. the UI can apply back-pressure/limits by refusing further items). — [SearchEverywhereContributor.java](https://raw.githubusercontent.com/JetBrains/intellij-community/master/platform/lang-api/src/com/intellij/ide/actions/searcheverywhere/SearchEverywhereContributor.java)
- `getSortWeight()` — "Defines weight for sorting contributors (not elements). This weight is used for example for ordering groups in results list when splitting by groups is enabled." Group order is a static property of the contributor, not of arrival. — [same source](https://raw.githubusercontent.com/JetBrains/intellij-community/master/platform/lang-api/src/com/intellij/ide/actions/searcheverywhere/SearchEverywhereContributor.java)
- `search(pattern, progressIndicator, elementsLimit)` returns a `ContributorSearchResult` and stops when "elementsLimit is reached" — the basis for per-group caps and a "more" row. `isShownInSeparateTab()` lets a contributor also have its own tab; `isEmptyPatternSupported()` defaults false; `getElementPriority` (deprecated) sorted items within results. — [same source](https://raw.githubusercontent.com/JetBrains/intellij-community/master/platform/lang-api/src/com/intellij/ide/actions/searcheverywhere/SearchEverywhereContributor.java)
- `WeightedSearchEverywhereContributor` adds weighted results (`fetchWeightedElements`) so items from different contributors can be merged on one scale in the "All" tab. — [JetBrains search result summary / Plugin SDK notable changes 2025](https://plugins.jetbrains.com/docs/intellij/api-notable-list-2025.html) (method detail not fully documented in what I retrieved)

**JetBrains (new API, 2025–2026):**
- The platform rewrote Search Everywhere to "separate data fetching from UI presentation" because the old API "coupled the search result data with the UI renderer", which made it impossible to "reliabl[y] serialize third-party search results" between a remote backend and a thin frontend. — [JetBrains Platform Blog, Dec 2025](https://blog.jetbrains.com/platform/2025/12/major-architectural-update-introducing-the-new-search-everywhere-api-built-for-remote-development/)
- New pieces: `SeItemsProvider` (analog of the contributor; "Can run on both the backend and frontend"; "Returns search results that include a serializable presentation"), `SeItemsProviderFactory` (extension point), `SeTab`/`SeTabFactory` ("Lives on the frontend only"). Timeline: default in remote dev 2025.2, default in monolith 2026.1, old API deprecated 2026.2. — [same](https://blog.jetbrains.com/platform/2025/12/major-architectural-update-introducing-the-new-search-everywhere-api-built-for-remote-development/)

**Algolia Autocomplete:**
- Multiple sources are first-class: `getSources` returns a list of sources, each with its own async `getItems`, called on input change; each source has a `sourceId`. — [Algolia Autocomplete: Sources](https://www.algolia.com/doc/ui-libraries/autocomplete/core-concepts/sources/)
- `onInput` fetches all sources concurrently via `Promise.all(sources.map(...))` and **only after all resolve** reshapes and updates collections. Status goes `loading` → `stalled` (after `setTimeout(..., props.stallThreshold)`) → `idle`; the stall timer is cleared on new input and in `finally`. — [autocomplete-core/src/onInput.ts](https://raw.githubusercontent.com/algolia/autocomplete/next/packages/autocomplete-core/src/onInput.ts)
- `stallThreshold` defaults to 300 ms. — [Algolia autocomplete API reference](https://www.algolia.com/doc/ui-libraries/autocomplete/api-reference/autocomplete-js/autocomplete); [createAutocomplete docs](https://autocomplete.algolia.com/docs/createautocomplete/)
- A shipped bug: responses resolved out of order and stale results overwrote fresh ones; fixed by `createConcurrentSafePromise`, which tags each call with an id, tracks `latestResolvedId`, and discards any resolution older than one already applied. — [algolia/autocomplete commit d15c404 (#753)](https://github.com/algolia/autocomplete/commit/d15c404845a1446ad2cc8673c44be4dbfa68723f)
- A related reported issue: status flipped `loading` → `idle` before results were in `collections`. — [algolia/autocomplete issue #754](https://github.com/algolia/autocomplete/issues/754)

**VS Code search view:**
- Text search has been powered by ripgrep since 1.11. — [Rust forum announcement](https://users.rust-lang.org/t/ripgrep-is-now-the-standard-text-search-provider-in-vs-code/10285); [vscode issue #19983](https://github.com/microsoft/vscode/issues/19983)
- `search.maxResults`: when it is hit "the expensive search should terminate as quickly as possible", and the service needs to know that the limit *would have been exceeded* so the viewlet can warn. — [vscode issue #47058](https://github.com/microsoft/vscode/issues/47058) (as summarised by search; not read in full)

### Inferences
- Two proven slot policies: **(a) fixed group order by lens weight** (JetBrains `getSortWeight`) with rows filling in as each lens reports, or **(b) one atomic paint when all local sources finish** (Algolia). For in-project lenses on one small SQLite file, (b) with a short stall threshold is likely sufficient and flicker-free; (a) earns its keep only for the cross-project fan-out where one source may be seconds slow or absent.
- The JetBrains move to a *serialisable presentation* is directly relevant: Bristlenose results must cross Python → HTTP → React and Python → Swift host, so each lens should emit a plain data row (kind, id, title, snippet, highlight ranges, route/deep-link, score) rather than anything render-specific.
- The consumer-returns-false contract and `elementsLimit` suggest a per-lens cap (e.g. 5 in the combined view) plus `has_more`/`total_estimate`, with a "Show all N in Quotes" row that routes to the lens's own filtered view — the VS Code `maxResults` warning is the same idea for a flat list.

### Gaps
- No primary documentation found (in this pass) for Spotlight, Alfred, Raycast, Xcode Find navigator, or Slack search on how they handle late-arriving groups, "Top hit" stability, or partial failure. Anything said about them would be from memory, not sources.
- The JetBrains SDK page for Search Everywhere (`plugins.jetbrains.com/docs/intellij/search-everywhere.html`) returned 404; details of `SeItemsProvider.collectItems` (flow semantics, concurrency, per-provider timeouts) and how the "All" tab reconciles late weighted items were not retrieved.
- VS Code's search-view rendering internals (batching of progress callbacks into the tree) not read from source.

---

## 2. Latency budgets, debounce vs per-keystroke, stale-response handling

### Takeaway
Nielsen's limits give the frame: under 0.1 s feels instantaneous and needs no feedback; under 1 s keeps flow uninterrupted without special feedback; past 10 s needs progress and a way to interrupt. Algolia's 300 ms stall threshold is a concrete, shipped number for "when to start showing loading". Out-of-order responses are a real, shipped bug class — every design needs either request cancellation or id-based stale-drop (ideally both).

### Cited Findings
- 0.1 s: "Limit for having the user feel that the system is reacting instantaneously" — just show the result. 1.0 s: "Limit for the user's flow of thought to stay uninterrupted" — no special feedback needed. 10 s: "Limit for keeping the user's attention focused on the dialogue" — use percent-done and allow interruption. 2–10 s: a less conspicuous indicator suffices; with unknown total work show running feedback of completed work. — [NN/g, Response Times: The 3 Important Limits](https://www.nngroup.com/articles/response-times-3-important-limits/)
- Algolia: loading state is only surfaced once `stallThreshold` (default 300 ms) elapses. — [Algolia autocomplete API](https://www.algolia.com/doc/ui-libraries/autocomplete/api-reference/autocomplete-js/autocomplete); [onInput.ts](https://raw.githubusercontent.com/algolia/autocomplete/next/packages/autocomplete-core/src/onInput.ts)
- Stale-drop by monotonically increasing request id (`createConcurrentSafePromise`, `latestResolvedId`). — [algolia/autocomplete d15c404](https://github.com/algolia/autocomplete/commit/d15c404845a1446ad2cc8673c44be4dbfa68723f)
- React positions `useDeferredValue` as an alternative to debouncing for *rendering* work: "Unlike debouncing or throttling, it doesn't require choosing any fixed delay", and deferred re-renders are interruptible; the docs note debouncing/throttling remain useful for non-rendering work such as network requests. — [react.dev useDeferredValue](https://react.dev/reference/react/useDeferredValue)

### Inferences
- Suggested budget for Bristlenose: in-project lenses target < 100 ms server time per keystroke (feasible only with an FTS index — see §3); show nothing-changed/"stale" dimming rather than a spinner below ~300 ms; show per-group skeleton/"searching…" only for groups still outstanding after ~300 ms; for cross-project sources, show a running "searched 7 of 9 projects" counter (NN/g's "running feedback of completed work") and a hard per-source timeout (e.g. 2–3 s) after which the source is reported as "not searched".
- Debounce the *network request* (roughly 100–150 ms) and use `useDeferredValue`/transitions for *rendering*; combine with `AbortController` so a superseded request stops server work, and keep a request id as belt-and-braces because abort is advisory once bytes are in flight.

### Gaps
- The Doherty threshold (~400 ms, Doherty & Thadani, IBM 1982) is widely cited but I did not retrieve a primary or reliable secondary source in this pass.
- No web.dev/INP-specific source retrieved for input responsiveness budgets.

---

## 3. Server side: one endpoint per lens vs one streaming endpoint; concurrent SQLite in Python

### Takeaway
FastAPI now has first-class SSE (`fastapi.sse.EventSourceResponse`, added 0.135.0) and a JSON Lines streaming guide, so a single `/search/stream` endpoint that yields one event per lens as it completes is cheap to build. SQLite WAL permits many concurrent readers on one host, and Python's `sqlite3` supports per-thread connections, `Connection.interrupt()` and a progress handler for cancellation. But on one small project DB the dominant cost is almost certainly *lack of an index* (there is no FTS5 today), not lack of parallelism; per-lens parallelism mainly helps when one lens is structurally slower (e.g. transcript segments via `LIKE`) or when fanning out across projects.

### Cited Findings
**FastAPI / Starlette transport:**
- SSE added in FastAPI 0.135.0; declare `response_class=EventSourceResponse` and `yield` items; "Each yielded item is encoded as JSON and sent in the `data:` field". `ServerSentEvent(data=..., event=..., id=..., retry=...)` gives event names/ids; `raw_data` for pre-encoded text (e.g. `[DONE]`). — [FastAPI docs: Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- SSE "works with any HTTP method, not just GET" (POST example given) — relevant because browser `EventSource` is GET-only, so a `fetch()` + stream reader client can POST a query body. — [same](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- FastAPI automatically sends a keep-alive `ping` comment every 15 s, sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`. — [same](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- The docs point to a sibling "Stream JSON Lines" tutorial as the similar non-SSE option. — [same](https://fastapi.tiangolo.com/tutorial/server-sent-events/); PR: [fastapi#15030](https://github.com/fastapi/fastapi/pull/15030)

**SQLite concurrency:**
- WAL: "readers do not block writers and a writer does not block readers"; multiple simultaneous readers each with their own end mark; one writer at a time. — [SQLite WAL](https://www.sqlite.org/wal.html)
- Checkpoint starvation: with "many concurrent overlapping readers and there is always at least one active reader, then no checkpoints will be able to complete and hence the WAL file will grow without bound". — [SQLite WAL](https://www.sqlite.org/wal.html)
- "All processes using a database must be on the same host computer; WAL does not work over a network filesystem." — [SQLite WAL](https://www.sqlite.org/wal.html)
- Python `sqlite3`: `check_same_thread=False` lets a connection be used from other threads ("write operations may need to be serialized by the user"); `sqlite3.threadsafety` reflects the compiled SQLite threading mode (serialized = 3 allows sharing connections and cursors; set dynamically since 3.11). — [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html)
- `Connection.interrupt()`: "Call this method from a different thread to abort any queries that might be executing on the connection" (raises `OperationalError`). `set_progress_handler(handler, n)` is called every n VM instructions; returning non-zero aborts the query. — [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html)
- Bristlenose already uses WAL + `busy_timeout=5000` + `check_same_thread=False` on every pooled connection (`bristlenose/server/db.py:55-81`) — local code, verified.

### Inferences
- **Transport choice.** Options ranked for Bristlenose:
  1. *Parallel per-lens GETs* (`/search/quotes?q=`, `/search/people?q=` …): simplest, each cacheable and independently abortable, trivially reused by each lens's own filter view and by MCP/CLI. Cost: N requests per keystroke; on HTTP/1.1 browsers cap ~6 connections per origin (not verified here), which is fine for ~7 lenses on localhost but not for 7 lenses × N projects.
  2. *One streaming endpoint* (SSE or NDJSON) that runs lenses concurrently server-side and emits `{lens, status, rows, has_more, elapsed_ms}` per lens, then a terminal `{done, unavailable:[...]}` event. One connection, one abort, and a natural place for a server-side deadline. This is the better fit for cross-project fan-out.
  3. *One combined query returning everything at once*: best when all lenses are fast; no partial states to design.
  A hybrid is natural: per-lens functions in Python (one searcher per lens, a shared interface like JetBrains' contributor), exposed both as individual routes and composed by a streaming route.
- **Concurrency inside one project.** With WAL, run each lens's query on its own pooled connection via `asyncio.to_thread` (or a small thread pool) and `asyncio.as_completed` to emit in completion order. Whether this beats sequential depends on whether `sqlite3` releases the GIL during `sqlite3_step` (see Gaps) and on disk cache; on a warm, small DB, sequential indexed queries may finish inside 100 ms total, making parallelism moot. Measure before building.
- **The bigger lever is an index.** An FTS5 virtual table (quotes + transcript segments + names/tags) would likely turn every lens into a sub-10 ms query and make "stream per lens" unnecessary within one project. Adding FTS5 is a schema/migration change (Alembic is in use — `db.py:run_migrations`).
- **Cancellation.** On client disconnect/abort, a streaming generator should stop yielding; long-running SQLite statements can be stopped with `interrupt()` from the event loop thread or a progress handler that checks a cancel flag. Avoid long-held read transactions to not starve WAL checkpoints (AutoCode writes concurrently).
- **Unmounted/network drives.** WAL's same-host rule means a project DB on an SMB share is itself a hazard; a cross-project search should treat such projects as a distinct "not searchable here" state rather than wait on them.

### Gaps
- Not verified from a primary source in this pass: whether CPython's `sqlite3` releases the GIL around `sqlite3_step` (my understanding from CPython source is that it does, which would make thread-parallel queries genuinely concurrent — but this is unsourced here and should be measured).
- No benchmark found for per-lens parallel vs single combined query on a small SQLite file; needs a local measurement on real project DBs.
- Starlette's client-disconnect detection semantics for streaming responses (`request.is_disconnected()` / cancellation of the generator) not retrieved.
- HTTP/1.1 per-origin connection limit (commonly 6) not sourced in this pass; WKWebView behaviour on localhost not checked.

---

## 4. Client side in React: consuming streams, cancellation, stable grouped model, transitions

### Takeaway
Keep input rendering urgent and results rendering deferred (`useDeferredValue` shows the previous results, dimmed, while new ones compute), cancel superseded requests, and merge arriving lens batches into a model whose group order is fixed in advance — so a late group fills its slot instead of shoving the list.

### Cited Findings
- `useDeferredValue`: "React will first attempt a re-render with the old value … and then try another re-render in the background with the new value"; the background render "is interruptible: if there's another update to the value, React will restart the background re-render from scratch". — [react.dev useDeferredValue](https://react.dev/reference/react/useDeferredValue)
- Integrated with Suspense: if the background update suspends, "the user will not see the fallback. They will see the old deferred value until the data loads." The `isStale = query !== deferredQuery` pattern (e.g. opacity 0.5) signals that shown results don't match current input. — [react.dev useDeferredValue](https://react.dev/reference/react/useDeferredValue)
- Algolia's lesson: tag requests and discard results older than the last applied (`latestResolvedId`). — [algolia/autocomplete d15c404](https://github.com/algolia/autocomplete/commit/d15c404845a1446ad2cc8673c44be4dbfa68723f)
- Browser `EventSource` would require GET; FastAPI SSE supports POST, which implies consuming with `fetch()` + a stream reader when the query is a body. — [FastAPI SSE docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

### Inferences
- Model shape: `Map<LensId, {status: 'pending'|'done'|'error'|'timeout'|'unavailable', rows, hasMore, total?}>` keyed by a `queryId`; rendering iterates a **fixed lens order** (like `getSortWeight`), rendering only groups with rows (plus, optionally, a thin "searching…" line for pending groups after the 300 ms stall). Dropping any event whose `queryId` ≠ current.
- Selection stability: store the selected item by *identity* (lens + row id), not by flat index; when a group above the selection fills in, keep the same identity selected so arrow-key focus never jumps. Only a group *below* the selection should be allowed to appear without adjustment; if a group above appears, keep scroll anchored on the selected row.
- "Top hit": either don't have one in the progressive path, or only promote it once the lenses that could supply it have reported (or after a short deadline), then freeze it for that query — otherwise it swaps under the user.
- TanStack Query per-lens `useQuery({queryKey:['search',lens,q], signal})` gives per-group status, abort-on-key-change (it passes an `AbortSignal` to the query function) and caching of recent queries — a good fit for option 1 (per-lens GETs); for option 2 (one stream) a custom hook with `AbortController` + `ReadableStream` reader + reducer is simpler. (TanStack behaviour stated from general knowledge — not retrieved in this pass.)
- Batch arriving events into one state update per animation frame to avoid N re-renders when lenses finish within milliseconds of each other.

### Gaps
- MDN pages on `ReadableStream`/`TextDecoderStream`/`AbortController` and TanStack Query's cancellation docs were not fetched in this pass; statements about them above are from general knowledge.
- No sourced guidance found on how Spotlight/Raycast keep selection stable under late inserts.

---

## 5. Cross-process fan-out across several project DBs/sidecars

### Takeaway
Fan-out is where streaming genuinely pays: sources have heterogeneous, unbounded latency (cold sidecar, spun-down drive, unmounted volume, network share where WAL is unsafe). The orchestrator must apply per-source deadlines, report unreachable sources explicitly, and avoid naive cross-source score merging.

### Cited Findings
- JetBrains redesigned specifically so providers can run remotely and return *serialisable* results to a frontend that composes tabs — the same shape as a Swift host or Python orchestrator composing N sidecars. — [JetBrains Platform Blog, Dec 2025](https://blog.jetbrains.com/platform/2025/12/major-architectural-update-introducing-the-new-search-everywhere-api-built-for-remote-development/)
- WAL requires all processes on the same host; it "does not work over a network filesystem". — [SQLite WAL](https://www.sqlite.org/wal.html)
- NN/g: for longer operations show running feedback of completed work and allow interruption. — [NN/g response times](https://www.nngroup.com/articles/response-times-3-important-limits/)

### Inferences
- Two orchestration placements: (a) **one Python process opens N project DBs read-only** (simplest; no IPC; can use `?mode=ro` URIs; avoids spinning up sidecars for projects that aren't open) vs (b) **the Swift host fans out to each open project's sidecar** (reuses live processes, but only covers *open* projects and couples search to sidecar lifecycle). For "all projects in a folder", (a) looks strictly better; (b) fits "all open windows".
- Group by project then lens (or lens then project, with a project badge per row). Rank normalisation across projects is only safe when every source uses the same scorer (e.g. FTS5 `bm25` over the same schema) — even then BM25 is corpus-relative, so prefer ordering groups by a stable key (recency, project name) and ranking within groups, rather than interleaving rows by raw score.
- Always end the stream with an explicit account: "Searched 7 of 9 projects — 2 not searched (drive not connected; still indexing)" with a retry affordance. Absence of a group must not silently mean "no matches".

### Gaps
- No sourced reference architecture found for rank normalisation across heterogeneous federated sources (e.g. CORI/score-normalisation literature) in this pass.
- macOS behaviour when touching a path on an unmounted/sleeping volume (blocking stat, spin-up delay) was not measured.

---

## 6. CLI analogue

### Takeaway
The terminal version of progressive grouped results is ripgrep's model: print each group as soon as it is complete, and offer `--json` as newline-delimited event records so other tools (and the MCP/agent path) can consume the same stream.

### Cited Findings
- VS Code's text search is ripgrep, and the search service needs to know when `maxResults` would be exceeded to warn — a precedent for per-group caps plus an "N more" marker in any streamed output. — [Rust forum](https://users.rust-lang.org/t/ripgrep-is-now-the-standard-text-search-provider-in-vs-code/10285); [vscode #47058](https://github.com/microsoft/vscode/issues/47058)
- FastAPI supports both SSE and JSON Lines streaming, so the server's per-lens event records can be the same shape the CLI prints with `--json`. — [FastAPI SSE docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

### Inferences
- `bristlenose search <folder> "query"`: human output prints a group header + up to K rows per lens in *fixed lens order*, holding a later group until earlier ones finish only if order matters more than speed; `--json` emits one NDJSON object per lens result/status plus a final summary record (including unsearched projects). On a TTY a Rich live region can show "searching 3 of 9 projects…"; off-TTY print plainly (per the repo's own "verify bare, not only through a pipe" rule).
- ripgrep's `--json` message types (`begin`/`match`/`end`/`summary`) are a good template, but I did not fetch ripgrep's docs to confirm the exact schema.

### Gaps
- ripgrep `--json` schema and output-ordering guarantees (it sorts only with `--sort`, otherwise prints in parallel completion order) not verified from its docs in this pass.

---

## 7. Pitfalls: races, flicker, count instability, accessibility

### Takeaway
The failure modes are known and specific: stale responses overwriting fresh ones, status saying "done" before data is in, groups reflowing under the keyboard selection, counts that climb as sources report, and screen-reader spam. The WAI-ARIA combobox pattern keeps DOM focus in the input and moves the *virtual* selection with `aria-activedescendant`; announcements of result counts should be polite and debounced (GOV.UK uses 1.4 s).

### Cited Findings
- Out-of-order resolution overwrote fresh results in Algolia Autocomplete until id-based stale-drop was added. — [algolia d15c404](https://github.com/algolia/autocomplete/commit/d15c404845a1446ad2cc8673c44be4dbfa68723f)
- Status transitioned `loading` → `idle` before results were available. — [algolia/autocomplete #754](https://github.com/algolia/autocomplete/issues/754)
- WAI-ARIA combobox: "DOM focus is maintained on the combobox and the assistive technology focus is moved within the listbox using `aria-activedescendant`"; `aria-expanded` reflects popup visibility; `aria-controls` references the popup; popup role can be `listbox`, `grid`, `tree` or `dialog`; Enter accepts, Escape closes, arrows navigate. The pattern page gives no guidance on grouped options or live-region announcement of counts. — [WAI-ARIA APG Combobox](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- GOV.UK accessible-autocomplete announces status via `aria-live="polite"`, debounced by `statusDebounceMillis = 1400`, alternates between two live regions (`bump`) to force re-announcement of identical text, and is silenced when the input loses focus or a choice is made; messages include "no results", "N results" and the selected option with position. — [alphagov/accessible-autocomplete src/status.js](https://raw.githubusercontent.com/alphagov/accessible-autocomplete/main/src/status.js)

### Inferences
- Announce **once per query, after results settle** (or after the debounce), not per arriving group: e.g. "23 results in 4 groups; 2 projects not searched". Per-group announcements as each lens lands would be exactly the spam GOV.UK's debounce exists to prevent.
- Group headings inside a listbox: use `role="group"` with `aria-labelledby` on a heading element and `role="option"` rows (standard listbox semantics; not specifically covered by the combobox pattern page retrieved). Headers must not be focusable options.
- Counts: show exact counts only for completed groups; show "20+" / "Show all" when `has_more`; show the overall total only once all sources report, otherwise "at least N" or no total. Never let a visible count drop as more sources arrive.
- Flicker: reserve no height for empty lenses (they'd flash in and out); instead only show pending placeholders after the stall threshold, and keep the previous query's results (dimmed via the `isStale` pattern) until the new query's first batch arrives rather than clearing to empty.

### Gaps
- No sourced guidance retrieved on `role="group"` inside `listbox` screen-reader support across VoiceOver/NVDA — needs testing in WKWebView with VoiceOver.
- No source on whether VoiceOver re-reads `aria-activedescendant` when the active option's DOM node is re-rendered (a real risk when groups stream in).

---

## 8. Trade-offs (synthesis for the decision)

### Takeaway
"Multiple simultaneous searchers, one per lens" is the right *code* architecture (a contributor-style interface per lens, as JetBrains does) regardless of transport. Whether the *UI* builds progressively should depend on measured latency spread: within one project, index first (FTS5) and paint atomically once all lenses return (Algolia-style, 300 ms stall threshold); across projects/sidecars, stream per source with fixed slot order, per-source deadlines, and an explicit "not searched" account.

### Cited Findings
- Contributor model with static group weight, per-contributor limit, consumer back-pressure, cancellation via progress indicator. — [SearchEverywhereContributor.java](https://raw.githubusercontent.com/JetBrains/intellij-community/master/platform/lang-api/src/com/intellij/ide/actions/searcheverywhere/SearchEverywhereContributor.java)
- Concurrent sources, single atomic update, stall threshold, stale-drop. — [onInput.ts](https://raw.githubusercontent.com/algolia/autocomplete/next/packages/autocomplete-core/src/onInput.ts); [d15c404](https://github.com/algolia/autocomplete/commit/d15c404845a1446ad2cc8673c44be4dbfa68723f)
- Native SSE in FastAPI ≥ 0.135.0. — [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- WAL concurrent readers; same-host only; checkpoint starvation under constant readers. — [SQLite WAL](https://www.sqlite.org/wal.html)

### Inferences
| Option | Wins | Costs | Fits |
|---|---|---|---|
| A. One combined server call, atomic paint | No partial states; stable layout; one request; easiest a11y | Slowest lens gates everything | In-project search once an FTS index exists |
| B. Parallel per-lens GETs, progressive paint | Reuses per-lens routes (lens views, MCP, CLI); per-lens caching/abort via TanStack Query | N requests/keystroke; client must manage ordering, stale-drop and selection stability | In-project, if lenses have very different costs |
| C. One streaming endpoint (SSE/NDJSON), per-lens events | One connection/abort; server-side deadlines; natural "not searched" terminal record; same records drive CLI `--json` | Streaming plumbing; still needs client ordering/selection discipline | Cross-project fan-out; slow/unavailable sources |
| D. Swift host fans out to sidecars | Reuses live processes | Only open projects; couples search to sidecar lifecycle; Swift-side merge duplicates Python logic | "Search all open windows" only |

- Recommended sequencing (inference): (1) define a per-lens searcher interface in Python returning serialisable rows + `has_more`; (2) add FTS5 and measure per-lens latency on the largest real project; (3) if every lens is < ~50 ms, ship option A with fixed lens order and a 300 ms stall indicator; (4) build option C for cross-project search, opening DBs read-only from one Python process, with per-project deadline and an explicit unavailable list; (5) share the event schema with CLI `--json` and MCP.
- The main risk of progressive-per-lens within a project is paying the UX complexity (selection jumps, count churn, a11y spam) for a latency spread of a few milliseconds that an index would erase.

### Gaps
- No local measurement yet of per-lens query times on a real Bristlenose project DB — the decision between A and B/C for in-project search hinges on it.
- Product behaviour of Spotlight/Raycast/Slack under partial results remains unsourced.
