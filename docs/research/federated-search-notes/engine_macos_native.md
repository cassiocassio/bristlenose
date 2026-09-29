# macOS-native search/indexing options for Bristlenose global search (as of 27 Sep 2026)

Scope: Core Spotlight (CSSearchableIndex / CSSearchQuery / CSUserQuery), App Intents IndexedEntity, NSMetadataQuery + Spotlight importers, SearchKit — measured against an app that must offer the *same* search from a Linux/macOS CLI and a browser SPA, over per-project SQLite, holding GDPR personal data (participant names, transcripts) for competing clients.

Version landmarks used below: macOS 15 Sequoia (2024, WWDC24), macOS 26 Tahoe (2025, WWDC25), **macOS 27 "Golden Gate" (WWDC26, released Sep 2026)** — the current OS. Bristlenose's deployment floor is macOS 15.0 (repo CLAUDE.md), so anything introduced in 15.4 / 26 / 27 needs availability gating.

Method note: Apple's doc pages are JS-rendered; API facts below were read from Apple's documentation JSON (`developer.apple.com/tutorials/data/documentation/<path>.json`), which is the same content as the human URL cited.

---

## 1. Core Spotlight: capabilities, what changed in macOS 15 / 26 / 27, fuzzy/semantic matching, latency, ranking, snippets

### Takeaway
Core Spotlight gives an app a private, on-device, per-app index it can query itself, with two query styles: a predicate language (`CSSearchQuery`) that supports case/diacritic-insensitive, word-boundary and wildcard matching but **no typo tolerance/edit-distance**, and (macOS 15+) `CSUserQuery` which adds ML ranking, suggestions and **semantic** matching — but semantic matching has been widely reported as non-functional or flaky through 2025–26, there is **no highlight/snippet API**, and ranking is Apple's, not yours. It is designed for item catalogues ("works best with no more than a few thousand items", older guidance), not for full-text search over hundreds of long transcripts with precise phrase/proximity semantics.

### Cited Findings
**Index model**
- `CSSearchableIndex` is "an on-device index for your app's searchable content"; available macOS 10.11+. Apple says to create **named** indexes (`init(name:)` / `init(name:protectionClass:)`) in production because "custom indexes support data protection… [and] batch operations"; the default index "doesn't protect data or support batch updates, so use it only during prototyping or testing." — [CSSearchableIndex](https://developer.apple.com/documentation/corespotlight/cssearchableindex); [CSSearchableIndex.default()](https://developer.apple.com/documentation/corespotlight/cssearchableindex/default())
- "Modify a CSSearchableIndex object from only one thread or task at a time, and modify it only from your signed app or app extension. It's a programming error to access a custom index from multiple threads simultaneously or from an unsigned bundle." — [CSSearchableIndex](https://developer.apple.com/documentation/corespotlight/cssearchableindex)
- Management API: `indexSearchableItems`, `deleteAllSearchableItems`, `deleteSearchableItems(withDomainIdentifiers:)`, `deleteSearchableItems(withIdentifiers:)`, `indexAppEntities(_:priority:)`, batching (`beginBatch`, `endIndexBatch(expectedClientState:newClientState:)`, `fetchLastClientState`), `isIndexingAvailable()`, `indexDelegate`. — [CSSearchableIndex topics](https://developer.apple.com/documentation/corespotlight/cssearchableindex)
- Domain identifiers: each `CSSearchableItem` takes a unique identifier, an attribute set, and "an optional string that specifies the domain or owner of the item" — enabling bulk delete by domain (e.g. one domain per project). — [Adding your app's content to Spotlight indexes](https://developer.apple.com/documentation/corespotlight/adding-your-app-s-content-to-spotlight-indexes)
- `isUpdate`: "If this property is false and the system encounters an item with the same identifier in the index, it deletes the old item and then inserts the new one. When the property is true, it updates the existing item… If this property is true and the item doesn't exist in the index, the system ignores the request." — [isUpdate](https://developer.apple.com/documentation/corespotlight/cssearchableitem/isupdate)
- Items expire: "If you don't set the expirationDate property appropriately, the system automatically expires the item after a period of time." — [expirationDate](https://developer.apple.com/documentation/corespotlight/cssearchableitem/expirationdate)
- Client state + index delegate extension: "When Spotlight needs to migrate the index, or otherwise recover from data corruption, interruption, or other issues, it will make a request to your app to re-index all items, or a specific set of items." Apps are expected to ship an index delegate extension for this. — [WWDC24 "Support semantic search with Core Spotlight"](https://developer.apple.com/videos/play/wwdc2024/10131/)
- Older (archived) Apple guidance: "Core Spotlight APIs work best when you have no more than a few thousand items." (pre-2016 App Search Programming Guide; mark as old) — [App Search Programming Guide (archive)](https://developer.apple.com/library/prerelease/ios/documentation/General/Conceptual/AppSearch/AppContent.html)

**Lexical query language (CSSearchQuery, macOS 10.12+; context-based init macOS 13+)**
- Predicates are `attributeName operator value[modifiers]` or `InRange(attr, min, max)`, combined with `&&` / `||`. Modifiers: `c` case-insensitive, `d` ignore diacritics, `w` word boundaries (also treats lower→upper transitions as boundaries), `t` tokenized value, `*` wildcard (prefix/suffix/infix). Example: `title == "Paris"wc` matches "I love Paris" but not "Comparison". Dates via `$time.today(-10)` etc. — [Searching for information in your app](https://developer.apple.com/documentation/corespotlight/searching-for-information-in-your-app)
- Queries "search all of your app's indexes by default"; can be limited by protection class. — [CSSearchQuery](https://developer.apple.com/documentation/corespotlight/cssearchquery)
- Results carry only the attributes you list in `fetchAttributes` ("the system doesn't automatically retrieve every property"). — [Searching for information in your app](https://developer.apple.com/documentation/corespotlight/searching-for-information-in-your-app)
- `CSSearchQueryContext` exposes `fetchAttributes`, `keyboardLanguage`, `sourceOptions` (only option: `allowMail`), `filterQueries`. — [CSSearchQueryContext](https://developer.apple.com/documentation/corespotlight/cssearchquerycontext); [SourceOptions](https://developer.apple.com/documentation/corespotlight/cssearchquerycontext/sourceoptions-swift.struct)

**User query / semantic search (CSUserQuery; class macOS 13+, semantic from macOS 15)**
- "In iOS 18 and macOS 15 and later, Spotlight also supports semantic searches of your content, in addition to lexical matching of a search term." — [Building a search interface for your app](https://developer.apple.com/documentation/corespotlight/building-a-search-interface-for-your-app)
- `CSUserQuery` "provide[s] the back-end support for your app's search features… perform lexical and semantic searches of human-entered search terms… ranked or unranked results… suggestions." Queries are one-shot; cancel and recreate per keystroke; Apple recommends a ~0.3 s debounce. — [CSUserQuery](https://developer.apple.com/documentation/corespotlight/csuserquery); [Building a search interface](https://developer.apple.com/documentation/corespotlight/building-a-search-interface-for-your-app)
- `CSUserQueryContext` options: `maxResultCount`, `maxSuggestionCount`, `disableSemanticSearch` (macOS 15+), `enableRankedResults`, `maxRankedResultCount`. — [CSUserQueryContext](https://developer.apple.com/documentation/corespotlight/csuserquerycontext)
- Apple's own doc for `disableSemanticSearch` is self-contradictory: "The default value of this property is `true`, which enables the delivery of semantic search results." It suggests disabling semantic search "when looking for a proper name." — [disableSemanticSearch](https://developer.apple.com/documentation/corespotlight/csuserquerycontext/disablesemanticsearch)
- Semantic search "requires machine learning models that must be downloaded to the device, and will be run in your app's process"; call `CSUserQuery.prepare()` before the search UI appears; results "must be sorted in your app once all results are returned" via `compareByRank`; "Currently, semantic search works best on text or media assets." Ranking adapts via `userEngaged(...)` and `lastUsedDate` ("Engagement and freshness are important signals"). — [WWDC24 session 10131](https://developer.apple.com/videos/play/wwdc2024/10131/)
- Field reports: semantic search "produces identical results to having it disabled" on iOS 26 beta and macOS 26.2 beta; logs show `Text embedding generation timeout (timeout=100ms)` → `semanticQuery failed to generate, using "(false)"`. April 2026 posters report inverted boolean behaviour for `disableSemanticSearch`, that `prepare()` doesn't prevent the first-query timeout (workaround: fire a dummy query), no Apple reply to feedback, and one developer abandoning it for their own CoreML sentence-transformer embeddings. The WWDC24 sample code was never released. — [Apple Developer Forums thread 793867](https://developer.apple.com/forums/thread/793867)
- Quality in practice (older, 2021): "In practice, Core Spotlight search in apps like Mail and Notes is poor in comparison with mainstream macOS Spotlight." — [Eclectic Light, Feb 2021](https://eclecticlight.co/2021/02/05/spotlight-on-search-in-app-search-core-spotlight/)

**macOS 26 (WWDC25) — App Intents / IndexedEntity**
- `IndexedEntity` (macOS 15+): "Adding entities to Spotlight makes them discoverable by Apple Intelligence." — [IndexedEntity](https://developer.apple.com/documentation/appintents/indexedentity)
- WWDC25: `@Property(indexingKey:)` / custom indexing keys map entity properties to Spotlight attributes; the system auto-generates Shortcuts **Find** actions from indexed entities; Spotlight on Mac can now run App Intents directly; entities passed to "Use Model" are serialised to JSON including "all entity properties exposed to Shortcuts". — [WWDC25 "Develop for Shortcuts and Spotlight with App Intents"](https://developer.apple.com/videos/play/wwdc2025/260/)

**macOS 27 (WWDC26)**
- "Entity schemas contribute your app's content to the Spotlight semantic index, so Siri can surface it with attribution back to your app." — [What's new in macOS 27](https://developer.apple.com/macos/whats-new/)
- `CSSearchableIndex.indexAppEntities` "populates the Spotlight semantic index… Apple Intelligence and Siri can understand your entities based on meaning." New `IndexedEntityQuery` for reindexing. For large/server/fast-changing datasets, Apple recommends **not** indexing and using `IntentValueQuery` instead ("your app receives a structured search input from the system"). The in-app search schema is renamed `.system.searchInApp` and "lets people search in your app with Siri… even if you don't index your entities." — [WWDC26 "Explore advanced App Intents features for Siri and Apple Intelligence"](https://developer.apple.com/videos/play/wwdc2026/343/)
- New `SpotlightSearchTool` (macOS 27.0+): a Foundation Models tool letting a language model search "your app's Spotlight index, files and directories your app created, or both." "By default, SpotlightSearchTool uses the complete option which works best with Private Cloud Compute (PCC) models." — [SpotlightSearchTool](https://developer.apple.com/documentation/corespotlight/spotlightsearchtool)
- Apple says it rebuilt the search infrastructure behind Spotlight/Photos/Mail in the 27-series OSes, claiming it is more stable and content becomes searchable almost immediately (Apple keynote claim, via secondary summaries) — [WWDC26 Keynote](https://developer.apple.com/videos/play/wwdc2026/101/); [Fenn blog on WWDC26 Spotlight](https://www.usefenn.com/blog/wwdc-26-apple-spotlight-macos-27)

### Inferences
- **Typo tolerance:** nothing in the lexical query language does edit distance; the only "fuzzy" path is semantic search, which is (a) embedding-based, not typo-based, (b) unreliable per 2025–26 forum reports, and (c) explicitly unsuited to proper names per Apple's own doc — and participant names are exactly what a researcher types. So Core Spotlight is weakest precisely where Bristlenose's search needs to be strongest.
- **Snippets/highlighting:** I found no API that returns match offsets or KWIC snippets; results return only requested attributes. Bristlenose would have to re-find the match in its own data to highlight — i.e. keep a second matcher anyway.
- **Ranking control:** you can fetch unranked results and sort yourself, or accept Apple's opaque adaptive ranking; you cannot supply a BM25/field-weight model. Result sets would differ from the CLI/SPA engine's ranking by construction.
- **Latency:** no Apple figures published. Architecture is XPC to `corespotlightd` plus (for semantic) in-process model with a 100 ms embedding timeout (from the forum log). Plausibly fine for type-ahead but unmeasured; would need a spike.
- **Scale fit:** the "few thousand items" guidance is ~10 years old, but indexing every quote/segment across many projects (tens of thousands of items) sits outside the design centre Apple describes ("favorites, purchased items, messages").

### Gaps
- No published latency/throughput numbers for CSUserQuery on macOS; no Apple statement on maximum index size.
- No confirmation whether macOS 27's rebuilt index fixed the semantic-search timeouts reported on 26.x.
- Could not confirm which languages semantic search supports on macOS (CJK, Catalan etc.); `keyboardLanguage` exists but no documented language list.
- Could not confirm whether a nested helper executable (the PyInstaller Python sidecar) counts as "your signed app or app extension" for CSSearchableIndex writes, or whether its items would be attributed to the host app's bundle ID. Any design should assume the **Swift host** must do the indexing, fed data by the sidecar.

---

## 2. NSMetadataQuery / file-level Spotlight — can it search inside our SQLite data?

### Takeaway
No, not directly. NSMetadataQuery searches the file-system Spotlight index (per-volume, `.Spotlight-V100`), which only knows what an importer extracted from files. SQLite contents are invisible unless an `.mdimporter` plugin extracts them; the modern `CSImportExtension` is documented as non-functional on macOS. Finder/file search also cannot see Core Spotlight app content.

### Cited Findings
- Spotlight (files) uses per-volume indexes in `.Spotlight-V100`; Core Spotlight uses `~/Library/Metadata/CoreSpotlight` as per-user, per-app indexes, run by `corespotlightd`; the Finder's Find window "seems not to have Core Spotlight access." — [Eclectic Light, "Spotlight and Core Spotlight are different", 4 Jul 2026](https://eclecticlight.co/2026/07/04/spotlight-and-core-spotlight-are-different/)
- Apple: "Spotlight File Import extensions don't provide functionality in macOS. To make custom files available to Spotlight in macOS, create a Spotlight importer plugin." — [CSImportExtension](https://developer.apple.com/documentation/corespotlight/csimportextension); corroborated by developers reporting CSImportExtension "failing to index" on macOS — [Apple Developer Forums 713953](https://developer.apple.com/forums/thread/713953)
- Spotlight importers ship inside the app bundle at `Contents/Library/Spotlight/*.mdimporter` — [Apple archive: Troubleshooting Spotlight Importers](https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/MDImporters/Concepts/Troubleshooting.html)
- Importer fragility example: plain-text files beginning with certain byte sequences went unindexed from Mojave through Tahoe 26.6.2 due to `file(1)` magic misidentification, fixed only in macOS 27.0; "there's no way for a third-party importer to override this behaviour." — [Eclectic Light, 17 Sep 2026](https://eclecticlight.co/2026/09/17/spotlight-indexing-bug-fixed-in-golden-gate/)
- Precedent for the importer route: DEVONthink's database format is not indexable by Spotlight, so it optionally writes out per-record metadata files (`.dtp2`) for Spotlight; results are those proxy files, and "If you reveal the file, it will not be the file you're looking for." (2018) — [DEVONtechnologies blog](https://www.devontechnologies.com/blog/devonthink-and-spotlight)

### Inferences
- NSMetadataQuery is irrelevant for in-app content search. The only file-Spotlight route to our SQLite contents is a custom mdimporter over a project file type, which would push participant text into the **system-wide, per-volume** index (worse privacy than Core Spotlight) — rule it out.

### Gaps
- Whether a sandboxed Mac App Store app's bundled mdimporter is still loaded on macOS 26/27, and under what sandbox, was not confirmed.

---

## 3. SearchKit (SKIndex) in 2026

### Takeaway
SearchKit is old (macOS 10.3/10.4-era C API) but **not formally deprecated**: Apple's current reference shows no deprecation on `SKIndexCreateWithURL`. It is a self-contained, file-backed inverted index you own (so it lives in your container and never enters system Spotlight), with phrase, prefix/suffix/substring, Boolean and relevance-ranked search plus summarisation — but no fuzzy/typo matching, macOS-only, C/CF API, and effectively unmaintained.

### Cited Findings
- "Search Kit is a powerful and streamlined C language framework for indexing and searching text in most human languages… Apple's Spotlight technology is built on top of Search Kit… Search Kit is appropriate when you want your application to have full control over indexing and searching, and when your focus is file content… thread-safe and works with Cocoa and command-line tools… supports phrase searches, prefix/suffix/substring searches, Boolean searches, summarization, and relevance ranking." — [Search Kit (Core Services)](https://developer.apple.com/documentation/coreservices/search_kit)
- `SKIndexCreateWithURL` — available macOS 10.3, no deprecation listed; "A file can contain more than one index… Your application is responsible for ensuring that no more than one process is open at a time for writing to an index." Memory-based indexes via `SKIndexCreateWithMutableData`. — [SKIndexCreateWithURL](https://developer.apple.com/documentation/coreservices/1446111-skindexcreatewithurl)
- Search types: `kSKSearchRanked`, `kSKSearchBooleanRanked`, `kSKSearchRequiredRanked`, `kSKSearchPrefixRanked`; index types inverted / vector / inverted-vector; `SKDocumentCreate` allows non-file documents; `SKIndexAddDocumentWithText` indexes arbitrary strings. — [Search Kit topics](https://developer.apple.com/documentation/coreservices/search_kit)
- Community reports of SearchKit oddities (e.g. "not producing search terms") exist on Apple forums — [Apple Developer Forums 117036](https://developer.apple.com/forums/thread/117036); the Search Kit Programming Guide is in Apple's documentation archive (legacy) — [NSHipster: Search Kit](https://nshipster.com/search-kit/)

### Inferences
- Sandbox: an SKIndex is just a file the app writes in its own container, so it should work under App Sandbox without entitlements (inferred from the file-based API; not explicitly documented).
- SearchKit offers nothing over SQLite FTS5 that Bristlenose needs, while adding a macOS-only third engine and a second copy of the data. It is dominated by FTS5 for this use case.

### Gaps
- No authoritative source found on SearchKit's CJK/Thai segmentation quality or `kSKLanguageTypes` behaviour on current macOS.
- No Apple statement on SearchKit's maintenance status beyond the non-deprecated reference pages.

---

## 4. Sandbox and App Store constraints

### Takeaway
A sandboxed Mac App Store app can use Core Spotlight with no special entitlement; indexes are per-app (per bundle) and per-user, readable only by that app (plus the system Spotlight UI, Siri/Apple Intelligence). There is no App Review guideline specific to indexing; the governing rules are general privacy ones. Per-app user opt-out on macOS is not clearly documented.

### Cited Findings
- "Searchable content that your app donates is stored in a private, entirely local index, that never leaves the device. Users can search for your content in Spotlight, but no other apps will be able to see the data." — [WWDC24 session 10131](https://developer.apple.com/videos/play/wwdc2024/10131/)
- "The items you index using Core Spotlight APIs are not added to Apple's server-side index or synced between devices." (older guide) — [App Search Programming Guide (archive)](https://developer.apple.com/library/prerelease/ios/documentation/General/Conceptual/AppSearch/AppContent.html)
- Access "is strictly limited to the app which controls it and rare exceptions including Spotlight's menu bar search"; third-party apps cannot read another app's Core Spotlight index even with Full Disk Access (2021). — [Eclectic Light, Feb 2021](https://eclecticlight.co/2021/02/05/spotlight-on-search-in-app-search-core-spotlight/)
- Must be modified "only from your signed app or app extension." — [CSSearchableIndex](https://developer.apple.com/documentation/corespotlight/cssearchableindex)
- Protection classes: "You can specify a default protection class for index items in the entitlements for your app." — [init(name:protectionClass:)](https://developer.apple.com/documentation/corespotlight/cssearchableindex/init(name:protectionclass:))
- User controls documented by Apple for Mac: result categories and **Search Privacy** exclusion of folders/disks; the support page does not describe excluding an individual third-party app's content. — [Apple Support: Spotlight settings on Mac](https://support.apple.com/guide/mac-help/mchl1bb43b84/mac); user reports of Tahoe settings describe "Results from Apps / Results from System" category toggles — [MacRumors forum](https://forums.macrumors.com/threads/upgraded-to-tahoe-see-too-much-noise-in-spotlight-searches-i-have-toggled-off-all-search-categories-except-apps-and-still-see-files-suggestions.2475878/); [Cult of Mac on Tahoe Spotlight](https://www.cultofmac.com/how-to/spotlight-mac)

### Inferences
- App groups: Bristlenose's MAS build carries `group.app.bristlenose` (repo CLAUDE.md) but the Core Spotlight index is keyed to the indexing bundle, not the group; the Developer-ID `.dmg` has no group. Nothing found suggesting app groups share Core Spotlight indexes. Low relevance either way.
- Since the Python sidecar is the data owner and the Swift host must do the indexing (see §1 gaps), a Core Spotlight engine needs a new sidecar→host change feed (adds/updates/deletes per project), a reindex delegate extension, and domain-per-project deletion on project removal — new cross-process plumbing with its own failure modes (stale index after crash, orphaned items after a project folder is deleted outside the app).

### Gaps
- No Mac App Store Review Guideline text found that addresses Spotlight indexing specifically (general §5.1 privacy rules apply). Not verified against the current guideline text.
- Whether macOS 26/27 System Settings offers a per-app toggle to hide one app's Core Spotlight results: unconfirmed.
- Whether the Mac honours data-protection classes for Core Spotlight indexes the way iOS does: unconfirmed.

---

## 5. Privacy: putting participant-identifying text into the system index

### Takeaway
Core Spotlight is "private to the app" only in the sense that *other apps* can't read it. The same content surfaces in the system Spotlight window, feeds Siri/Apple Intelligence (and in macOS 27 the Spotlight *semantic* index and a PCC-oriented LLM tool), lives in a per-user store that forensic tools parse, and sits outside Bristlenose's own data boundary (per-project folder the researcher owns and deletes). There is a per-entity `hideInSpotlight` (macOS 15.4+) to keep App Intents entities out of Spotlight results; for raw `CSSearchableItem`s I found no documented "in-app only" flag.

### Cited Findings
- Core Spotlight app content appears in the system Spotlight window: Eclectic Light searched a unique word and "At the top of the list of hits is my test note" (Notes, via Core Spotlight), while Finder Find could not see it. (Jul 2026, macOS 26) — [Eclectic Light, 8 Jul 2026](https://eclecticlight.co/2026/07/08/core-spotlight-in-action-notes-and-contacts/)
- Apple frames indexing as feeding many system surfaces: "Search… plays a role both inside your app and for features like Spotlight Search, Handoff, Siri Suggestions, Reminders, and more." And "Indexing your content makes it available to both your app and to the system's Spotlight search feature." — [Adding your app's content to Spotlight indexes](https://developer.apple.com/documentation/corespotlight/adding-your-app-s-content-to-spotlight-indexes); [Searching for information in your app](https://developer.apple.com/documentation/corespotlight/searching-for-information-in-your-app)
- "Adding entities to Spotlight makes them discoverable by Apple Intelligence." — [IndexedEntity](https://developer.apple.com/documentation/appintents/indexedentity)
- `hideInSpotlight` (iOS 18.4 / **macOS 15.4**+): "When the value of this property is true, Spotlight doesn't include the entity in search results. The default value… is false." Its abstract says it "indicates whether Spotlight prevents the inclusion of the entity in the index" — the two phrasings differ (excluded from *results* vs from the *index*). — [hideInSpotlight](https://developer.apple.com/documentation/appintents/indexedentity/hideinspotlight-7sp5n)
- Entities handed to "Use Model" are serialised to JSON with "all entity properties exposed to Shortcuts". — [WWDC25 session 260](https://developer.apple.com/videos/play/wwdc2025/260/)
- macOS 27 `SpotlightSearchTool` defaults to an option that "works best with Private Cloud Compute (PCC) models" — i.e. the Apple-intended pattern for LLM search over the Core Spotlight index involves server-side (PCC) inference. — [SpotlightSearchTool](https://developer.apple.com/documentation/corespotlight/spotlightsearchtool)
- The per-user Core Spotlight store (`~/Library/Metadata/CoreSpotlight/index.spotlightV3/`, `store.db`) holds metadata "from items that aren't files or folders" — Safari history, Notes content, etc. — and the open-source forensic tool mac_apt parses it to spreadsheets/SQLite (2018; path confirmed as still per-user in 2026 by Eclectic Light). — [Swift Forensics, 2018](http://www.swiftforensics.com/2018/10/the-user-spotlight-database.html); [Eclectic Light, Jul 2026](https://eclecticlight.co/2026/07/04/spotlight-and-core-spotlight-are-different/)
- `NSUserActivity.isEligibleForSearch` is the separate switch for activity donation; Apple says to set it true "if you want them to appear in search results" — i.e. it controls donation of *activities*, not an in-app-only mode for CSSearchableItems. — [CSSearchableIndex](https://developer.apple.com/documentation/corespotlight/cssearchableindex)
- Third-party design pattern (a notes app's public issue, **not Bear**): treats "the Spotlight index lives outside the encryption boundary", excludes locked notebooks, indexes titles only, and lists Spotlight in a privacy dashboard with purge. — [swiftsaneai/sanenotes issue #979](https://github.com/swiftsaneai/sanenotes/issues/979) (search-engine summaries wrongly attributed this to Bear; treat as an unrelated app)

### Inferences
- **Client-presentation risk:** a researcher sharing their screen and pressing ⌘Space to find an unrelated file could surface Client A's participant quote or name while presenting to Client B. This is the concrete, non-hypothetical failure for competing-client work, and it follows directly from the Eclectic Light observation above.
- **Data-subject erasure / retention:** GDPR deletion of a participant would have to reach a second store Bristlenose doesn't own and can't inspect (no CLI tooling, per Eclectic Light), and items the host failed to delete (crash, project folder deleted in Finder) would linger until expiry. This conflicts with the repo's stance that `pii_summary.txt` and `llm-calls.jsonl` are re-identification keys that must stay inside the project's `.bristlenose/` (repo CLAUDE.md) — Core Spotlight would be a third, uncontrolled copy.
- **Apple Intelligence / Siri reach:** anything indexed via IndexedEntity is, by Apple's own framing, for Apple Intelligence; on macOS 27 entity schemas feed the Spotlight *semantic* index for Siri. Researchers under client NDAs may not be permitted to route participant data into OS assistant features, whatever Apple's privacy posture.
- **Backups/MDM:** not verified (see gaps); assume the index can be included in a user-home backup and cannot be selectively managed by MDM for one app.
- Net: the safe Core Spotlight payload for Bristlenose is **non-personal, non-client-sensitive** metadata only — and even project names can be client-identifying ("Acme checkout study"), so even that should be opt-in.

### Gaps
- Whether `~/Library/Metadata/CoreSpotlight` is included in Time Machine / iCloud backups on macOS 26/27: not found.
- Whether any MDM payload can suppress one third-party app's Core Spotlight content: not found.
- No documented in-app-only flag for plain `CSSearchableItem` (only `hideInSpotlight` for App Intents entities); unclear whether `hideInSpotlight` keeps entities out of the Siri/semantic index or only out of Spotlight UI results (the doc's two sentences differ).
- No Apple HIG text found on indexing sensitive personal data.

---

## 6. Cross-platform cost of running both engines

### Takeaway
None of the Apple options exist on Linux or in a browser, so the SQLite+Python engine must be built regardless for the CLI (PyPI/Homebrew/Snap/Fedora) and the SPA-in-browser. A native engine would be a strict *addition*: a second indexer, a second query semantics, a second ranking, a second deletion path, plus a Swift/Python sync channel — for one of three surfaces.

### Cited Findings
- Core Spotlight, CSUserQuery, IndexedEntity, SpotlightSearchTool and SearchKit are all Apple-platform-only APIs (platform lists on each reference page) — [CSSearchableIndex](https://developer.apple.com/documentation/corespotlight/cssearchableindex); [CSUserQuery](https://developer.apple.com/documentation/corespotlight/csuserquery); [SpotlightSearchTool](https://developer.apple.com/documentation/corespotlight/spotlightsearchtool); [SKIndexCreateWithURL](https://developer.apple.com/documentation/coreservices/1446111-skindexcreatewithurl)
- NetNewsWire, a native Mac/iOS app, still implements its in-app article search as SQLite FTS4 (`CREATE VIRTUAL TABLE if not EXISTS search using fts4(title, body)`) rather than CSSearchQuery. — [NetNewsWire ArticlesDatabase.swift](https://github.com/Ranchero-Software/NetNewsWire/blob/main/Modules/ArticlesDatabase/Sources/ArticlesDatabase/ArticlesDatabase.swift)

### Inferences (estimates, not measured)
Work items a dual-engine design adds on top of the SQL engine:
1. Sidecar→Swift change feed (per-project add/update/delete events, including edits to quotes, renames, hides, tag changes) and a full-reindex path; the index must be written by the Swift host (§1 gap).
2. Index delegate extension target (reindex on Spotlight's request), with its own signing/sandbox profile — nontrivial in this repo, where extension/signing mistakes have historically cost release cycles (repo CLAUDE.md incidents).
3. Result mapping from Core Spotlight identifiers back to SPA routes across the WKWebView bridge.
4. Parity problem: matching rules differ (Core Spotlight has no typo tolerance but may add semantic hits; SQL engine does whatever we build), so the Mac app and the CLI/browser would return **different results for the same query on the same project** — a correctness/trust issue for researchers and an unbounded test surface.
5. Snippet highlighting still needs our own matcher (§1), so the SQL engine's text-matching code runs on the Mac anyway.
6. Availability gating: semantic CSUserQuery needs macOS 15 (OK at the floor), `hideInSpotlight` 15.4, SpotlightSearchTool 27.0.
Rough order of magnitude: the native path duplicates indexing + query + ranking + deletion + tests, i.e. comparable to building the SQL engine a second time, plus the cross-process sync that the SQL engine doesn't need (the SQL engine reads the same DB the sidecar writes).

### Gaps
- No public case study quantifying dual-engine maintenance cost; the above is reasoned from the architecture.

---

## 7. Hybrids worth doing

### Takeaway
Use our own SQLite/Python engine for all content search on every surface. If any native integration is wanted, the two defensible hybrids are (a) **App Intents search exposure backed by our engine** (`ShowInAppSearchResultsIntent` / `.system.searchInApp` / `IntentValueQuery`), which puts nothing in the system index, and (b) an **opt-in, project-level-only** Core Spotlight donation (project name → open project), with `hideInSpotlight`/opt-in default off because project names can themselves identify clients.

### Cited Findings
- `ShowInAppSearchResultsIntent` (macOS 14.2+): "The system uses this protocol to route search requests for your app's entities to your app… use it to display the entities that match the provided search criteria… This app intent needs to run from your app." — [ShowInAppSearchResultsIntent](https://developer.apple.com/documentation/appintents/showinappsearchresultsintent)
- macOS 27: `.system.searchInApp` "lets people search in your app with Siri… even if you don't index your entities"; for large or fast-changing data, use `IntentValueQuery`, where "your app receives a structured search input from the system." — [WWDC26 session 343](https://developer.apple.com/videos/play/wwdc2026/343/)
- `hideInSpotlight` lets an app index an entity yet keep it out of Spotlight results (macOS 15.4+). — [hideInSpotlight](https://developer.apple.com/documentation/appintents/indexedentity/hideinspotlight-7sp5n)
- Hybrid precedents:
  - **NetNewsWire**: in-app search = SQLite FTS4; Spotlight = `NSUserActivity` with `isEligibleForSearch = true` for articles/feeds the user reads, with a thin `CSSearchableItem` bridge (title, summary, keywords) — and the Core Spotlight item code is `#if os(iOS)`-gated. — [NetNewsWire ActivityManager.swift](https://github.com/Ranchero-Software/NetNewsWire/blob/main/Shared/Activity/ActivityManager.swift); [ArticlesDatabase.swift](https://github.com/Ranchero-Software/NetNewsWire/blob/main/Modules/ArticlesDatabase/Sources/ArticlesDatabase/ArticlesDatabase.swift)
  - **DEVONthink**: its own search engine (with fuzzy search, hit highlighting, precise operators) for in-app search; Spotlight exposure is an **opt-in per-database** option ("Create Spotlight Index") that writes metadata proxy files. — [DEVONtechnologies blog, Dec 2018](https://www.devontechnologies.com/blog/devonthink-and-spotlight); [DEVONthink forum: built-in search vs Spotlight](https://discourse.devontechnologies.com/t/built-in-dt-search-vs-spotlight/63728); [Macdrifter 2015](https://www.macdrifter.com/2015/01/searching-without-spotlight.html)
  - **Zotero**: own SQLite full-text word index (`fulltextWords` / `fulltextItemWords` tables) — cross-platform app, no Core Spotlight. — [zotero schema.js](https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/schema.js)
  - **Apple Contacts** (macOS 26) does not search via Core Spotlight; it "maintains any separate index" — even Apple keeps some personal-data search out of Core Spotlight. **Apple Notes** does use Core Spotlight (and its notes then appear in system Spotlight). — [Eclectic Light, 8 Jul 2026](https://eclecticlight.co/2026/07/08/core-spotlight-in-action-notes-and-contacts/)

### Inferences
- **Hybrid A (recommended if any native work is done): App Intent → our engine.** An `AppEntity` for Project/Quote whose query and `ShowInAppSearchResultsIntent.perform()` call the sidecar's search endpoint and navigate the SPA. Gains Siri/Shortcuts/Spotlight-action reach on macOS 26/27 without copying any participant text into OS stores; one engine, one ranking. Caveat: entities returned to Shortcuts/"Use Model" get serialised (§5), so keep exposed properties minimal (IDs, project name) and decide deliberately whether quote text is ever an entity property.
- **Hybrid B (optional, opt-in): project-level discoverability.** Donate only project name + folder (domain = project id) so ⌘Space → project opens the app. Default **off** or behind `hideInSpotlight`-style control, because project names are often client names; delete by domain on project removal. Low effort, low value; worth it only if users ask to launch projects from Spotlight.
- **Not worth doing:** indexing quotes/transcripts/participant names in Core Spotlight; SearchKit (dominated by SQLite FTS5); an mdimporter (pushes content into the system-wide per-volume index); semantic CSUserQuery (unreliable, Mac-only, bad at proper names). If semantic search is wanted, do it in our own stack (embeddings in SQLite, e.g. an extension or Python-side vectors) so it exists on all three surfaces — the forum developer who gave up on Core Spotlight semantic search did the equivalent with CoreML sentence-transformers ([forum 793867](https://developer.apple.com/forums/thread/793867)).

### Gaps — app examples requested but not verified
- **Bear, Craft, Things, Obsidian**: no primary source found in this pass on whether their in-app search uses Core Spotlight or their own engine. (A search result attributing a Core Spotlight privacy design to Bear actually came from an unrelated project's GitHub issue — do not cite it as Bear.) Obsidian is an Electron app with its own in-app search (general knowledge, not sourced here). Treat all four as unverified.
