# macOS search-field and search-suggestion micro-interactions in Apple's apps (current to September 2026, macOS 26 Tahoe / macOS 27)

Evidence labels used throughout:
- **CITED**: stated in an Apple source (HIG, developer docs, WWDC transcript, Apple Support) or a named secondary source, linked inline.
- **OBSERVED (user screenshot)**: seen in the Photos screenshot the user shared ("bury st"). This is first-hand evidence, but it is not documented anywhere I could find.
- **OBSERVED/UNVERIFIED**: behaviour recalled from Apple apps. I could not find it documented and did not re-check it on a live macOS 26/27 machine during this pass. Verify it by hand before treating it as a spec.

The HIG pages "Search fields" and "Searching" were both revised on **8 June 2026** (WWDC26). The "Search fields" page had already been reorganised on 9 June 2025 to consolidate the iPadOS and macOS guidance and to add token guidance. The quotations below come from the current (June 2026) text.

---

## 1. What the HIG and AppKit/SwiftUI docs actually say (the normative layer)

### Takeaway
The HIG's search guidance is short and principle-level. It covers placeholder text that states the scope, starting the search as the person types, suggestions (recents before typing, predictive suggestions while typing), relevance-ordered and categorised results, and a broad default scope that people narrow. Tokens act as filters and should be paired with suggestions so people discover them. Search history is privacy-sensitive and must be clearable. The concrete micro-interaction detail lives in the APIs. Since macOS 15, AppKit has a system-standard suggestions menu (`NSTextField.suggestionsDelegate`) with sections, an image, a secondary title, highlight-time completion, and sync/async phases. It is the closest thing to a codified version of the Photos/Mail menu.

### Cited findings — HIG "Search fields" (updated 8 Jun 2026)
- Definition: a search field "displays a Search icon, a Clear button, and placeholder text"; it "can use a scope bar as well as tokens to help filter and refine the scope of their search." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Use placeholder text to help people know what they can search for… to reinforce the scope of your search or to educate people about the type of content that search has access to." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "If possible, start search immediately when a person types… provides results that are continuously refined as the text becomes more specific." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Consider showing suggested search terms. For example, you can display recent searches before search begins, or predictive search suggestions as a person types." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Simplify search results. Provide the most relevant search results first… consider categorizing them." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- Scope bar: "Use a scope bar to filter among clearly defined search categories"; "Default to a broader scope and let people refine it as they need. A broader scope provides context for the full set of available results." The Mail example given is on iPhone: the scope bar moves from the entire mailbox to the current one. — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- Token definition: "A visual representation of a search term that someone can select and edit, and acts as a filter for any additional terms in the search." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Use tokens to filter by common search terms or items… the term it represents gains a visual treatment that encapsulates it, indicating that people can select and edit it as a single item… like filtering by a specific contact in Mail, or… filtering by photos in Messages." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Consider pairing tokens with search suggestions. People may not know which tokens are available, so pairing them with search suggestions can help people learn how to use them." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- iPadOS/macOS: "Put a search field at the trailing side of the toolbar for many common uses", especially "apps with split views that need to search across multiple columns… like Mail, Notes, and Voice Memos… it lets people navigate results while keeping their selection visible in the detail view." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Include search at the top of the sidebar when filtering content or navigation there", with System Settings as the example: it filters the sidebar and exposes deeply nested sections. — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Include search as an item in the sidebar or tab bar when you want an area dedicated to discovery", as in Music and TV, which provide "suggested content, categories, and recent searches". In such an area, "consider immediately focusing the field when a person navigates to the area". — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- "Account for window resizing with the placement of the search field." Notes and Mail move search above the list column in compact widths (iPad). — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)

### Cited findings — HIG "Searching" (updated 8 Jun 2026)
- "Aim to make your app's content searchable through a single location." — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)
- "Clearly display the current scope of a search. Use a descriptive placeholder text, a scope bar, or a title… in the Mail app there is always a clear reference to the mailbox someone is searching." — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)
- "Provide suggestions to make searching easier… display a person's recent searches before they start typing or offer predictive search suggestions while they're typing". The developer pointer is `searchSuggestions(_:)`. — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)
- "Take privacy into consideration before displaying search history… If you do show search history, provide a way for people to clear it." — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)
- The page also says people may want to scope by attributes such as "creation date, file size, or file type". This is the Finder attribute-row model. — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)

### Cited findings — HIG "Token fields" (macOS only)
- Mail's address fields are the canonical token field: tokens can be selected, dragged to reorder, and moved between fields. — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)
- Suggestions: "When people select a suggested recipient, Mail inserts the recipient into the field as a token." — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)
- "Add value with a context menu." The Mail recipient token menu offers edit name, mark as VIP, and view contact card. — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)
- "By default, text people enter turns into a token whenever they type a comma. You can specify additional shortcuts, such as pressing Return." — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields). My summarised fetch of the `NSTokenField` reference said the default tokenizing set is "space and return". That contradicts the HIG, and I could not confirm it from the raw page. **Trust the HIG (comma).**
- "Consider customizing the delay… By default, suggestions appear immediately. However, suggestions that appear too quickly may distract people while they're typing." — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)
- "Not supported in iOS, iPadOS, tvOS, visionOS, and watchOS. Token fields are macOS only." — [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)

### Cited findings — AppKit
- **`NSSearchToolbarItem` (macOS 11+).** It "automatically resizes to accommodate typing when the focus switches to the toolbar item. When the toolbar is low on space, the system may collapse the search item into a button representation, which then expands to a full search field when the user clicks on it." Its API:
  - `preferredWidthForSearchField`: the width when focused.
  - `resignsFirstResponderWithCancel`: lets the cancel (ⓧ) button also resign focus, not only clear.
  - `beginSearchInteraction()`: moves keyboard focus into the field. This is what a ⌘F handler should call.
  - `endSearchInteraction()`: gives up focus and shrinks back to the available width.

  Source: [NSSearchToolbarItem](https://developer.apple.com/documentation/appkit/nssearchtoolbaritem)
- **`NSSearchField` recents.** It provides `recentSearches`, `recentsAutosaveName` (archives recents automatically), `maximumRecents`, and `searchMenuTemplate`. The template is the pop-up menu from the magnifier icon, assembled from tagged items: `recentsTitleMenuItemTag`, `recentsMenuItemTag`, `noRecentsMenuItemTag`, `clearRecentsMenuItemTag`. This is the legacy Mac pattern for "Recent Searches… Clear Recent Searches" in the magnifier drop-down. — [NSSearchField](https://developer.apple.com/documentation/appkit/nssearchfield)
- **`NSSearchField` search modes.** `sendsSearchStringImmediately` and `sendsWholeSearchString` choose between searching on each keystroke and searching on Return/search-button. The delegate has `searchFieldDidStartSearching` / `searchFieldDidEndSearching`. — [NSSearchField](https://developer.apple.com/documentation/appkit/nssearchfield)
- **Text entry suggestions, new in macOS 15 Sequoia.** WWDC24: "It allows your app to provide custom suggestions as people type, in a system standard suggestions menu. This common pattern seen across many apps is now being standardized in AppKit in macOS Sequoia. It works on any NSTextField, including subclasses like NSSearchField." — [WWDC24 "What's new in AppKit" @17:22](https://developer.apple.com/videos/play/wwdc2024/10124/)
- Apple's design tips from the same session: suggestions must stay "relevant to the typed text, as people expect the interface to keep up with how fast they type"; "Provide consistent and predictable suggestions, to preserve muscle memory"; "When asynchronous suggestions are provided, place those after the immediate suggestions you already provided"; "Don't provide anything but the most important results and details." — [WWDC24 10124](https://developer.apple.com/videos/play/wwdc2024/10124/)
- **`NSTextSuggestionsDelegate` (macOS 15+).**
  - `textField(_:provideUpdatedSuggestions:)` is called when the text **or tokens** change.
  - `textField(_:didSelect:)` handles selection.
  - `textField(_:textCompletionFor:)` returns "the full completion text for a particular item to use when the item is highlighted or selected". This is the API form of Photos' inline completion.
  - `appending(_:)` concatenates delegates, with "a separator" between their groups.

  Source: [NSTextSuggestionsDelegate](https://developer.apple.com/documentation/appkit/nstextsuggestionsdelegate)
- **`NSSuggestionItem` (macOS 15+).** It has `title`/`attributedTitle`, an optional `secondaryTitle`/`attributedSecondaryTitle`, an optional `image` ("to display before the title"), an optional `toolTip`, and `representedValue`. It has **no dedicated trailing-count or badge property**. A Photos-style right-aligned count would have to go in `secondaryTitle`; how that renders (trailing or not) is **UNVERIFIED**. — [NSSuggestionItem](https://developer.apple.com/documentation/appkit/nssuggestionitem)
- **`NSSuggestionItemSection` and `NSSuggestionItemResponse`.** A section can carry an optional localized title; WWDC24's example has a "Favorites" section followed by an untitled one. A response carries `phase = .intermediate` or `.final`, which is how the synchronous-then-asynchronous refinement works. — [WWDC24 10124 code @17:49](https://developer.apple.com/videos/play/wwdc2024/10124/); [NSTextSuggestionsDelegate](https://developer.apple.com/documentation/appkit/nstextsuggestionsdelegate)
- **`NSTokenField`.**
  - `tokenStyle`: `.default`, `.rounded`, `.squared`, `.plainSquared`, `.none`.
  - `tokenizingCharacterSet` and `completionDelay`.
  - Delegate hooks: `hasMenuForRepresentedObject` / `menuForRepresentedObject` (the per-token pop-up menu, i.e. the Mail/Finder token disclosure arrow), `completionsForSubstring`, `displayString…`/`editingString…`, `styleForRepresentedObject`, and `writeRepresentedObjects` (drag/copy tokens).

  Source: [NSTokenField](https://developer.apple.com/documentation/appkit/nstokenfield)

### Cited findings — SwiftUI
- Search scopes "appear in a scope bar beneath the toolbar on macOS and as a segmented control within the navigation bar on iOS." — [WWDC22 "Craft search experiences in SwiftUI"-era session 10052](https://developer.apple.com/videos/play/wwdc2022/10052/)
- On macOS the scope picker appears "when search is active". On iOS it appears when someone starts entering text. This can be overridden with `searchScopes(_:activation:_:)` using `.onTextEntry` / `.onSearchPresentation`. The default scope is the initial value of the bound property. — [Scoping a search operation](https://developer.apple.com/documentation/swiftui/scoping-a-search-operation)
- Suggestions on macOS appear "in a list below the search field" in a separate shadowed panel, and may use `Section` headers "to distinguish different kinds of suggestions (e.g., recent searches vs. common search terms)". Choosing a `.searchCompletion("text")` row **replaces the field's text**; `.searchCompletion(token)` **adds a token**. `searchSuggestions(_:for:)` controls `.menu` vs `.content` placement. "Certain events… like when someone moves a macOS window, might dismiss the suggestion list." — [Suggesting search terms](https://developer.apple.com/documentation/swiftui/suggesting-search-terms)
- Tokens: `searchable(text:tokens:suggestedTokens:…)`. On macOS, tokens render "as dark gray rectangles" and appear "at the beginning of the search field before plain text" (on iOS they can be `Label`s). Tokens can carry a `Picker` so their meaning can be changed in place, which is the SwiftUI analogue of Mail's From/To/Subject disclosure. Documented ways to add tokens are:
  - suggested tokens;
  - detecting a matching substring in the text;
  - a dividing character (comma or space);
  - on submit.

  Source: [Performing a search operation](https://developer.apple.com/documentation/swiftui/performing-a-search-operation)

### Inferences
- For a native macOS 15+ app, the house route to "Photos-like suggestions under a toolbar search" is `NSSearchToolbarItem` plus `suggestionsDelegate` with `NSSuggestionItem` (image = type glyph, title = attributed label, sections). That gives the system-standard menu and its keyboard handling for free. Bristlenose's search lives in a WKWebView SPA, so the practical use of these docs is as the **spec to imitate**, not the implementation.
- None of the documented APIs has a first-class "count" slot. Counts in Photos are a product-level choice, not an AppKit convention.

### Gaps
- I did not find any HIG text on: how many suggestion rows to show; count capping ("280+"); the typed-versus-completion colour treatment; diacritic and case folding; or "Indexing…" states. These are documented only by the behaviour of Apple's apps.
- Whether the `NSSuggestionItem` system menu is the same component Photos/Mail use internally is unknown (UNVERIFIED).

---

## 2. Suggestions: grouping, glyphs, ordering, counts, matched-text emphasis, prefix matching

### Takeaway
Apple uses two layouts. The first is a **mixed list with a leading type glyph per row**, as in Photos: one ranked list, each row self-describing via its icon, with a trailing count. The second is **sectioned lists with headers**, as in Mail ("Top Hits", then per-category groups), SwiftUI Section headers, and the AppKit `NSSuggestionItemSection`. Photos shows what was typed in primary colour and the completion in secondary colour, matches every word as an independent prefix, and caps large counts with "+". None of that is documented; it is observed.

### Cited findings
- Photos: "As you type, suggested searches appear below the search field." Multiple words separated by a space search on multiple criteria, e.g. "a location and a month". Natural-language description search is supported ("'Maya skateboarding in a tie-dye shirt'"). ⌘F focuses the field, and a cancel button restores all photos. A Shared Library contributor filter uses "Shared by" plus a name. The guide is for macOS 27. — [Apple Support: Search for photos and videos in Photos on Mac](https://support.apple.com/guide/photos/search-for-photos-and-videos-pht64de33e5a/mac)
- Mail: "Mail displays suggestions organized by category", with "Top Hits" first. Choosing a suggestion "creates a search filter in the search field and lists the matching messages found". The guide is for macOS Tahoe 26. — [Apple Support: Search for emails in Mail on Mac (UK)](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac); [Apple Support (US)](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac)
- Mail header-field syntax: type the field name, a colon and the value ("from: Ashley Rico", "priority: high"), then choose a suggestion. Attribute suggestions come from a keyword: "flag" → "Message is flagged", "unread" → "Message is unread", "attachment" → "Message with attachments". — [Apple Support: Mail search](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac); [search snippet](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac)
- The AppKit guidance is to append async suggestions after the immediate ones, keep suggestions consistent and predictable, and keep them minimal. — [WWDC24 10124](https://developer.apple.com/videos/play/wwdc2024/10124/)
- Xcode Open Quickly (⇧⌘O) uses fuzzy (non-contiguous) matching and shows results with the matched characters highlighted. This comes from secondary sources, not Apple docs. — [Effortless Code: Xcode Open Quickly](https://effortlesscode.com/xcode-open-quickly/); [objc.io: A Fast Fuzzy Search Implementation](https://www.objc.io/blog/2020/08/18/fuzzy-search/)
- Spotlight (macOS 26): "Dynamic category chips appear beneath the search field during typing"; clicking one (e.g. Screenshots, Folders) filters instantly. — [MacRumors: Do More With Spotlight in macOS Tahoe](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)

### Observed (user screenshot, Photos, macOS 26/27)
- **Row anatomy:** a leading monochrome SF-Symbol-style type glyph, then the label, then a right-aligned count in secondary colour. The glyphs were:
  - person silhouette for a person;
  - map pin for a place;
  - magnifying glass for a plain text search term;
  - calendar for a date or holiday;
  - building for a business/POI.
- **Matched-text emphasis:** the typed portion is in primary label colour and the untyped remainder in secondary colour ("**Bury St**" dark, "Edmunds" grey). This is a colour contrast, not bold-on-match.
- **Per-word prefix matching:** each query token matches independently as a word prefix. "st" matched Storey, Steppe, Store and St Andrew's, while "bury" is carried by the place row.
- **Count capping:** large counts shown as "280+" alongside exact small counts (79, 927, 6, 3). This suggests capping applies only to some types or ranges, possibly where the count is estimated. The cap threshold and rule are **UNVERIFIED**; 927 was shown exactly, so the rule is not a simple numeric threshold.
- **Incomplete-index footer:** a non-selectable footer row, "Indexing…", when the library index is incomplete.
- **Mixed list:** people, places, terms, holidays and businesses interleaved in a single list, with no section headers.

### Observed/unverified (other apps)
- Mail on macOS: section headers such as People, Subject, Mailboxes and Attachments; each People row shows name and address. Picking one makes a lozenge token.
- Safari address bar: a "Top Hit" row at the top, then groups (Search Engine Suggestions, Bookmarks and History, Siri Suggestions). The completion is written inline into the field, pre-selected so that further typing replaces it. This is the "inline autocomplete" idiom that `textCompletionFor:` enables in AppKit.
- System Settings: the sidebar search filters the sidebar list. Choosing a result navigates to the pane and briefly **highlights the matching control** with a spotlight/pulse. On macOS 13+ the matching sidebar rows are shown and the result list may carry sub-results. (Older System Preferences, up to macOS 12, dimmed the whole grid and spotlit the matching pane icons.)
- Case- and diacritic-insensitive matching is standard across Apple search ("cafe" finds "Café"). There is no Apple doc for this in these apps; `NSString.CompareOptions.diacriticInsensitive/.caseInsensitive` and Spotlight's `cd` query modifiers are the platform primitives.
- Suggestion row counts are short (roughly 5–10 rows in Photos/Mail). No documented number.

### Inferences
- Bristlenose searches typed entities across one corpus. For that, the Photos pattern (mixed ranked list, type glyph per row, trailing count, primary/secondary completion colour, per-word prefix) is the closest precedent. Mail's sectioned pattern suits scenarios where the *same string* resolves to many kinds, for example a participant name that appears as a person, in quotes and in transcript lines.
- Use "N+" capping only when the count is estimated or still growing (e.g. during indexing). Otherwise show exact numbers, as Photos does for 927.

### Gaps
- No Apple source documents the capping rule, the glyph set per facet, or the colour treatment. Treat them as observed.
- Photos' full facet list on macOS 27 (people, places, dates/holidays, events/memories, scenes/objects, media types, text-in-image, captions, keywords) is not enumerated on the macOS 27 support page I fetched. That page covers title/caption, keyword, date, natural-language and "Shared by". The rest is OBSERVED/UNVERIFIED.

---

## 3. Tokens (lozenges): creation, editing, keyboard, menus, combining

### Takeaway
On the Mac, picking a suggestion converts it into a lozenge token at the leading edge of the field. Free text can follow and is ANDed with the tokens. A token with a disclosure arrow opens a menu that changes its meaning (Mail: from / to / subject / entire message; Finder: name matches vs contains). Several tokens are combined by adding more, and the field scrolls horizontally.

### Cited findings
- Mail: "If a search filter contains a down arrow, you can click it to change the filter. For example… search for messages to or from a certain person, or search subject lines or entire messages." — [Apple Support: Mail search](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac)
- Mail: to add multiple filters, "place the pointer after the first search filter, start typing search text, then choose a suggestion. Repeat as needed; the search field scrolls as you add more search filters." — [Apple Support: Mail search](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac)
- Mail also accepts Boolean operators in uppercase: `AND`, `OR`, `NOT`, and `-` as NOT. Example: "yellowstone AND cascades NOT teton". Date ranges are typed as "02/04/23 to 19/04/23". — [Apple Support: Mail search](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac)
- The HIG says a token "acts as a filter for any additional terms in the search". Tokens are a filter; the free text searches within it. — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- SwiftUI on macOS renders tokens at the start of the field, before the text. Tokens can embed a `Picker` so their meaning can be edited in place. — [Performing a search operation](https://developer.apple.com/documentation/swiftui/performing-a-search-operation)
- `NSTokenField` supports a per-token menu (`menuForRepresentedObject`) and drag/copy of tokens (`writeRepresentedObjects`). — [NSTokenField](https://developer.apple.com/documentation/appkit/nstokenfield); [HIG: Token fields](https://developer.apple.com/design/human-interface-guidelines/token-fields)
- Spotlight (macOS 26) scopes by typing a location or app name and pressing **Tab**, then the search term; `/PDF`-style slash syntax narrows by kind. — [MacRumors: Spotlight in macOS Tahoe](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)

### Observed/unverified
- **Keyboard:**
  - ↓/↑ move through suggestions.
  - Return (or Tab in some apps) commits the highlighted suggestion as a token.
  - With the caret immediately after a token, **Backspace first selects the token** (it turns highlighted), and a second Backspace deletes it whole. In some apps the first Backspace deletes it directly.
  - ← moves the caret onto or before a token, and a token can be selected with the arrow keys.
  - ⌘A selects all tokens and text.

  This matches `NSTokenField` behaviour; the two-step select-then-delete is a recollection to check against Mail on macOS 26.
- **Appearance:** rounded lozenge with a tinted fill. In Mail and Finder the token carries its kind as a prefix label, e.g. "From: Eileen Storey" or "Kind: PDF", and has a small chevron when it has a menu. SwiftUI documents the macOS tokens as grey rectangles.
- **Finder:** typing in the Finder search field offers suggestions such as "Kinds › PDF Document", "Filenames containing…", or "Name matches: …". Choosing one creates a token (e.g. "Kind: PDF"), and a token's pop-up switches between "Name matches" and "contains". I could not retrieve the Apple Support page for Finder search in this pass (fetch timeout / wrong article), so this is UNVERIFIED.
- Mixing tokens with free text: the tokens come first and trailing free text is ANDed with them (Mail, Photos, SwiftUI).
- Photos: choosing a suggestion adds it as a token in the field, and further terms can be typed after it. Combining e.g. a person and a place narrows results (AND). The support page only confirms the space-separated multiple-criteria (AND) semantics; the token rendering itself is OBSERVED.

### Inferences
- Bristlenose tokens should:
  - carry the type glyph and/or a "Kind:"-style prefix;
  - be ANDed with each other and with free text;
  - offer a chevron menu wherever a token's *role* is ambiguous (e.g. participant as *speaker of* vs *mentioned in*, or tag vs theme). This mirrors Mail's From/To/Any.
- Backspace-selects-then-deletes protects against deleting a hard-won token by accident, which is worth matching.

### Gaps
- There is no documented keyboard contract for search tokens in macOS 26 apps. Test Mail, Photos and Finder by hand.
- No source was found for token drag between search fields.

---

## 4. Recents / history and saved searches

### Takeaway
The HIG recommends showing recent searches when the field is focused but empty, and requires a way to clear them. The legacy AppKit mechanism is the magnifier pop-up menu (`recentsAutosaveName`, "Clear Recent Searches"). Saved searches are the Mac's power idiom: Smart Mailboxes (Mail), Smart Folders (Finder, "Save" in the search bar) and Smart Albums (Photos).

### Cited findings
- "Display recent searches before search begins… provide a way for people to clear it." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields); [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching)
- `NSSearchField` archives recents via `recentsAutosaveName`, limited by `maximumRecents`, and shown in the `searchMenuTemplate` using the recents / clear-recents / no-recents / recents-title menu tags. — [NSSearchField](https://developer.apple.com/documentation/appkit/nssearchfield)
- SwiftUI recommends implementing recents as a dynamic array rendered in `.searchSuggestions`, optionally under a Section header. — [Suggesting search terms](https://developer.apple.com/documentation/swiftui/suggesting-search-terms)
- Spotlight (macOS 26): "Pressing the up arrow key after opening Spotlight reveals a history of your past searches"; the history is cleared in System Settings. — [MacRumors: Spotlight in macOS Tahoe](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)
- Music and TV use a dedicated search area with "suggested content, categories, and recent searches". — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)

### Observed/unverified
- Mail (macOS): the magnifier drop-down or an empty focused field lists Recent Searches with "Clear Recents". A search can be saved as a Smart Mailbox via a **Save** button in the favourites/scope bar while searching, or via Mailbox ▸ New Smart Mailbox. The Mail support page I fetched does not cover recents or Smart Mailbox saving.
- Finder: while searching, the search bar under the toolbar carries a **Save** button that saves the search as a Smart Folder (.savedSearch). A **+** button at the right of that bar adds attribute rows (Kind, Last opened date, Name, Contents, Other…), and each row has pop-ups plus −/+ buttons. This is the Spotlight criteria editor, and it is the Mac's canonical "query builder".
- Photos: Smart Albums are built separately, via File ▸ New Smart Album with rule rows. In my recollection they are not saved directly from the search field. Photos shows recent searches when the field is focused and empty.
- Safari: the empty focused address bar shows Favorites/Frequently Visited rather than recent search strings.
- Xcode Open Quickly remembers the last query and shows recent files when empty.

### Inferences
- For Bristlenose, show "Recent searches" (with a clear action) in the empty-focus state. A "Save search" affordance would map naturally onto a saved lens or view, as Smart Mailbox maps onto Mail. Recent searches in a research tool can include participant names, so the HIG's privacy clause applies: they must be clearable, and should never be exported.

### Gaps
- No current Apple Support text was found for Mail/Photos recents or for Mail's "save search" affordance on macOS 26/27.

---

## 5. Scope bars and default scope

### Takeaway
Default to the broad scope and let people narrow it. On macOS the scope bar sits beneath the toolbar and appears when search is active: Mail's "All Mailboxes | <current mailbox>", Finder's "This Mac | '<folder>' | Shared".

### Cited findings
- "Default to a broader scope and let people refine it as they need." — [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)
- The macOS scope bar is beneath the toolbar and appears when search is active. — [WWDC22 10052](https://developer.apple.com/videos/play/wwdc2022/10052/); [Scoping a search operation](https://developer.apple.com/documentation/swiftui/scoping-a-search-operation)
- Mail: "Select mailboxes in the Mail sidebar or Favourites bar to search specific locations or 'Search all mailboxes'." — [Apple Support: Mail search](https://support.apple.com/en-gb/guide/mail/mlhlp1003/mac)
- Spotlight's scoping uses Tab (location/app) and chips rather than a scope bar. — [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)

### Observed/unverified
- Finder's default scope follows Settings ▸ Advanced ▸ "When performing a search": Search This Mac / Search the Current Folder / Use the Previous Search Scope. The default is This Mac.
- In Mail, the scope bar item for the current mailbox is named after that mailbox, so the scope is always stated (per the HIG's "Mail… clear reference to the mailbox").

### Inferences
- For a federated, cross-lens search, the "broad" default is *whole project, all lenses*. A scope bar of "All | <current lens>" is the Mail analogue.

---

## 6. States: focus, expand/collapse, typing, indexing, empty, clearing, ⌘F

### Cited findings
- The toolbar search expands when focused (`preferredWidthForSearchField`) and may collapse to a magnifier button under space pressure, expanding on click. `endSearchInteraction()` restores the width. — [NSSearchToolbarItem](https://developer.apple.com/documentation/appkit/nssearchtoolbaritem)
- The cancel button can clear *and* resign focus (`resignsFirstResponderWithCancel`). — [NSSearchToolbarItem](https://developer.apple.com/documentation/appkit/nssearchtoolbaritem)
- ⌘F focuses the Photos search field. — [Apple Support: Photos search](https://support.apple.com/guide/photos/search-for-photos-and-videos-pht64de33e5a/mac)
- Asynchronous suggestions use `.intermediate` then `.final` response phases, with async items appended after sync ones. This is the documented "loading" model: no spinner, the list simply refines. — [WWDC24 10124](https://developer.apple.com/videos/play/wwdc2024/10124/)
- Moving the window may dismiss the suggestion list. — [Suggesting search terms](https://developer.apple.com/documentation/swiftui/suggesting-search-terms)

### Observed (user screenshot)
- Photos shows an "Indexing…" footer row in the suggestions menu while its index is incomplete. Suggestions still appear; the footer signals that they may be partial.

### Observed/unverified
- **Escape:** the first Escape dismisses the suggestion menu. A further Escape clears the field (NSSearchField's cancel action), and in toolbar search items it also ends the search and restores the view. The exact sequence differs by app.
- **ⓧ clear button:** appears only when the field has content. It clears text and tokens.
- **Focus ring:** the standard system focus ring (accent colour) is drawn around the capsule field.
- **⌘F vs ⌥⌘F:**
  - In apps whose main job is a collection (Mail, Photos, Notes, Music, Finder), ⌘F or ⌥⌘F focuses the toolbar search.
  - In Mail, Edit ▸ Find ▸ **Mailbox Search** is ⌥⌘F, and ⌘F is Find (in the message).
  - In Safari, ⌘F is Find in Page.
  - In Finder, ⌘F opens a search in the window and ⌥⌘F focuses the search field.
  - In Notes, ⌥⌘F searches all notes and ⌘F finds within the note.

  **The convention is: ⌘F = find in the current document/content; ⌥⌘F = search the collection (toolbar field) when both exist.** Verify on macOS 26/27 menus.
- **No results:** Mail and Photos show an in-content "No Results" state (large centred title plus secondary text, like `ContentUnavailableView.search`) rather than an empty menu. SwiftUI's `ContentUnavailableView.search(text:)` (macOS 14+) is the standard form. It is not fetched this pass, so it is UNVERIFIED as to Apple app parity.

### Gaps
- No Apple documentation was found for the Escape sequence, the empty/no-results state in the menu, or the "Indexing…" row.

---

## 7. App-by-app quick reference

| App | Placement | Suggestions | Tokens | Scope | Recents / saved | Evidence |
|---|---|---|---|---|---|---|
| Photos | Toolbar, ⌘F | Mixed list, type glyph, trailing count (N+ cap), typed=primary / completion=secondary, per-word prefix, "Indexing…" footer, natural language | Picks become tokens; ANDed; "Shared by" | — | Recents on empty focus (unverified); Smart Albums separate (File menu) | Support page CITED; rest OBSERVED |
| Mail | Toolbar trailing | Sectioned by category, "Top Hits" first; `from:`, `flag`, `unread`, `attachment` keywords | Filters with ▾ menu (from/to/subject/entire message); multiple, field scrolls; Boolean AND/OR/NOT | Favourites bar: All Mailboxes / current | Recents + Smart Mailbox save (unverified) | CITED (Support, HIG) |
| Finder | Toolbar | Kind / filename suggestions | "Kind: PDF", "Name matches" token menus | This Mac / folder / Shared; Settings default | Save → Smart Folder; + attribute rows | UNVERIFIED (fetch failed) |
| Spotlight (26) | Global ⌘Space | Category chips under the field | Tab-scoping by app/location; `/kind` | ⌘1–4 browse modes (Apps/Files/Actions/Clipboard) | ↑ shows history; clear in Settings; Quick Keys | CITED (MacRumors, TWiT) |
| System Settings | Top of sidebar | Filters the sidebar; highlights the target control | — | — | — | HIG CITED; highlight OBSERVED |
| Safari | Address bar | Top Hit, inline completion, grouped sources | — | — | Favourites on empty | OBSERVED |
| Xcode | ⇧⌘O panel | Fuzzy, matched chars highlighted | — | — | Last query | Secondary sources |
| Music / TV | Dedicated sidebar item | Rich suggestions, categories, recents | — | Library vs Apple Music (scope) | Recents | HIG CITED |

Sources for the table rows are those cited in sections 1–6, plus [TWiT: Spotlight browsing tools in macOS Tahoe](https://twit.tv/posts/tech/how-use-new-spotlight-browsing-tools-macos-tahoe), which reports the ⌘1–⌘4 browse modes and Quick Keys.

Notes, Messages, Reminders, Contacts, Calendar and App Store were **not researched in this pass**. Messages is cited by the HIG only as the example of a token that filters to photos ([HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)), and Notes only as an app whose toolbar search moves above the list in compact widths.

---

## 8. Accessibility conventions

### Takeaway
Little is documented specifically. Using the system components (`NSSearchField`, the `suggestionsDelegate` menu, `NSTokenField`) inherits VoiceOver, keyboard and focus-ring behaviour. A web reimplementation must reproduce those roles and announcements itself.

### Cited findings
- `NSSuggestionItem` takes localized `title`, `secondaryTitle` and `toolTip`. These are the strings VoiceOver would read, so localization is required on each. — [NSSuggestionItem](https://developer.apple.com/documentation/appkit/nssuggestionitem)
- Searching fast is a stated goal ("help people search faster and type less"), and focusing the field on entering a dedicated search area is recommended. — [HIG: Searching](https://developer.apple.com/design/human-interface-guidelines/searching); [HIG: Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields)

### Inferences
- A web port should use the ARIA combobox pattern: the field has `role="combobox"` with `aria-expanded`/`aria-controls`/`aria-activedescendant`, and the list has `role="listbox"` with `option` rows. Each option's accessible name should include type and count ("Eileen Storey, person, 79 results"), because the glyph and the count are visual-only. Tokens need a removable-button semantics. Announce "Indexing, results may be incomplete" and result-count changes via a polite live region. This is standard web a11y practice, not an Apple source.

### Gaps
- No Apple source was found on VoiceOver phrasing for suggestion rows, tokens, or counts in Photos/Mail.

---

## Consolidated gaps (for the report writer)
- I could not retrieve the Finder search support article; the Finder token and Smart Folder behaviour is UNVERIFIED.
- The Photos support page for macOS 27 does not enumerate facet types, the count display, recents, or the indexing state. All of those come from the user's screenshot or from recollection.
- No official source covers:
  - the primary/secondary completion colouring;
  - count capping ("280+");
  - per-word prefix matching;
  - diacritic folding;
  - the Escape sequence;
  - backspace-selects-token;
  - the suggestion row limit.
- Notes, Messages, Reminders, Contacts, Calendar and App Store were not examined.
- I did not check the WWDC26 AppKit session ("Modernize your AppKit app", [video 289](https://developer.apple.com/videos/play/wwdc2026/289/)) for search changes in macOS 27.
