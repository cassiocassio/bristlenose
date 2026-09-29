# Federated "search everything" across entity types — UX prior art in desktop and productivity apps

_Researched 27 Sep 2026. Sources are vendor docs, engineering blogs, reviews (Six Colors, MacRumors) and NN/g. The Apple HIG pages (developer.apple.com) returned an empty body to the fetcher, so HIG guidance below is taken from search-result excerpts of that page and is marked as such. Where a note comes from my own knowledge and I could not find a source this session, it sits under **Inferences** and is labelled "(unverified)"._

## 1. How are results grouped by type — fixed group order or ranked? Caps per group? Is there a "Top hit"?

### Takeaway
There are two families. One is **a single blended list with a best match first, and browse filters beside it**: Spotlight in macOS 26 and later, Raycast root search, Linear, and the command-palette tools. The other is **type buckets you switch between with tabs or a sidebar**: Slack's results view, Spotlight's ⌘1–⌘4 modes, Finder's Kind criteria. Mail sits between them: its suggestion dropdown is grouped by category, and a "Top Hits" block heads the results. Within this set, only Mail and Spotlight name a cross-type best match explicitly. Hardly any vendor documents a fixed per-group cap.

### Cited Findings
- **Spotlight (macOS 26 Tahoe)** drops the old per-type sections. All result types (files, folders, events, apps, messages and so on) are "now listed together and ranked intelligently based on relevance". Apple "refocused the Spotlight interface to list all result types in a single view, rather than separating them by type as before." — [AppleInsider, macOS Tahoe](https://appleinsider.com/inside/macos-tahoe)
- Spotlight 26 adds four **browse filters**: Apps, Files, Actions, Clipboard (⌘1–⌘4). "Files shows … suggestions even if you don't type anything." — [Six Colors Tahoe review](https://sixcolors.com/post/2025/09/macos-26-tahoe-review-power-under-glass/); [MacRumors how-to](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)
- In Spotlight 26, "dynamic categories such as Screenshots, System Settings, or Folders will appear" under the search field as filter chips. — [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)
- The current Apple Support Spotlight page, which as fetched describes **macOS 27**, says results appear "instantly, with the best match at the top", and the fetcher's summary says they are grouped by type. The page lists no category labels. — [Apple Support: Search with Spotlight on Mac](https://support.apple.com/guide/mac-help/search-with-spotlight-mchlp1008/mac). _This conflicts with AppleInsider's "single view, not separated by type" for macOS 26. It may reflect a macOS 27 change or just the summariser's wording, so verify on a macOS 27 machine._
- **Apple Mail**: as you type, "suggestions appear below the search field. They are organized into categories, such as Subject or Attachments", and "Top Hits puts the most relevant results first." The dropdown suggests *filters* (people, subjects, attributes), not messages. — [Apple Support: Search for emails in Mail on Mac](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac); [Macworld](https://www.macworld.com/article/223175/how-to-search-smarter-in-mail.html)
- **Slack** full results: "Click Messages, Files, People, Channels, or Canvases in the sidebar to switch between result types." Type is a sidebar tab, not a blended list. — [Slack Help: Search in Slack](https://slack.com/help/articles/202528808-Search-in-Slack)
- **Raycast** root search shows Favorites, upcoming calendar events and recently used files when empty. While you type it shows a results list of apps, commands, files, contacts and so on. ⌘↑/⌘↓ jumps between sections, so sections exist even in the ranked list. — [Raycast Manual: Search Bar](https://manual.raycast.com/search-bar)
- **Things 3 Quick Find** searches only names of to-dos, projects, areas and tags at first, "so suggestions can be shown as soon as you start typing". A **"Continue Search"** row widens the search to notes, checklists and completed items from the Logbook. This is a two-tier model: cheap name matches first, a deeper search on request. — [Things Support: Quick Find](https://culturedcode.com/things/support/articles/2803584/)
- **Linear** `/` search returns "issues, projects, and documents across your workspace". By default results are ordered by assumed relevance, with unstarted and in-progress issues first; they can be re-sorted by last updated or last created. The cap is 500 results. — [Linear Docs: Search](https://linear.app/docs/search)
- **Notion** search shows recently viewed pages below results and adds badges such as "Most viewed" or "Popular this week" to some results. — [Notion Help: Search](https://www.notion.com/help/search)
- **Slack Quick Switcher** limits the list it shows on open to 24 unread channels and DMs. — [Slack Engineering: A faster, smarter Quick Switcher](https://slack.engineering/a-faster-smarter-quick-switcher/)
- NN/g on blended versus tabbed results: web search results "were once divided by tabs into separate results pages, but are now blended together." Type tabs help only "if the filters match dimensions important to users". — [search-result excerpt, NN/g-adjacent summary](https://www.nngroup.com/reports/ecommerce-ux-search-including-faceted-search/) _(snippet from a search index, not a fetched article)_

### Inferences
- The field has moved from type sections to one ranked list plus filters. Spotlight 26 is the flagship example, and Apple framed the change as a feature. When the type is the user's intent, the type buckets come back as filters or tabs: Spotlight ⌘1–⌘4, Slack's sidebar.
- The Mail pattern fits a toolbar field that turns picks into tokens best. The dropdown offers **filters grouped by kind** (People / Subject / Mailbox …) plus a "Top Hits" block of actual items. For Bristlenose that maps to: suggestions for speakers, tags, themes and sessions become tokens, and a couple of top quotes are direct hits.
- The Things "Continue Search" row is a good model for "this project → all projects", or "names → full transcript text". Keep the fast tier instant and make the expensive tier an explicit row.
- (unverified) Pre-Tahoe Spotlight showed a "Top Hit" row, then fixed type sections (Applications, Documents, Mail & Messages, Folders …) with a few rows each, and a "Show all in Finder" row. ⌘↑/⌘↓ jumped between sections. VS Code quick open and Xcode Open Quickly are single fuzzy-ranked lists of one type (files or symbols), with no groups.

### Gaps
- None of the apps documents a per-group row cap (e.g. "3 per group, then Show more"). I found no primary source giving numbers for Mail, pre-Tahoe Spotlight, Notion or Google Drive.
- I could not confirm how Mail's "Top Hits" chooses its members. Apple says only "most relevant".
- I could not fetch Google Drive, Apple Notes or Alfred sources this session.

## 2. How is ranking across heterogeneous types handled (a person vs a message)?

### Takeaway
No vendor publishes a formula for comparing different types. In practice, ranking is **match quality on the title or name, plus personal frecency**, with exact or alias matches pinned first. Type is broken out with filters rather than weighed against other types.

### Cited Findings
- **Raycast** ranking priority, highest first: exact alias match → alias prefix → title fuzzy match score → subtitle/keyword matches → **frecency**. "Root Search learns from you. The more often, and the more recently, you pick a result for a given query, the higher it ranks." Users can "Reset Ranking" per command. — [Raycast Manual: Search Bar](https://manual.raycast.com/search-bar)
- **Slack Quick Switcher frecency**: recency buckets score 100 (≤4 h), 80 (≤1 day), 60 (≤3 days), 40 (≤1 week), 20 (≤1 month), 10 (≤90 days), 0 beyond. Score = "Total Count × Score / Number of Timestamps recorded (up to 10)". Frecency applies to all types (channels, DMs, people). The article does not say how types are weighed against each other. — [Slack Engineering](https://slack.engineering/a-faster-smarter-quick-switcher/)
- Slack rebuilt its sort and match rules as reusable modules "to ensure that all filters, type-aheads and autocompletes in Slack work the same way". — [Slack Engineering](https://slack.engineering/a-faster-smarter-quick-switcher/)
- **Linear** default relevance ranks unstarted and in-progress issues first, which is a workflow-state prior layered on text match. — [Linear Docs: Search](https://linear.app/docs/search)
- **Notion** signals popularity with badges ("Most viewed", "Popular this week"). — [Notion Help](https://www.notion.com/help/search)
- Spotlight 26 claims ranking "intelligently based on relevance to the user". A critic (Rob Jonson, via Michael Tsai) complained that "Tahoe removes the information that allows you to differentiate app versions". — [AppleInsider](https://appleinsider.com/inside/macos-tahoe); [Michael Tsai blog](https://mjtsai.com/blog/2025/09/15/macos-tahoe-26/)

### Inferences
- For Bristlenose, the portable recipe is: (1) an exact name hit on a small-cardinality entity (speaker code, tag, theme or section name) outranks everything; (2) then title or name match quality; (3) then body-text hits (quotes, transcript segments); (4) frecency only as a tie-breaker. Raycast deliberately puts frecency *below* exact and title matches.
- Entity types with short names (people, tags, themes, sessions) will always match more cleanly than long text (quotes, transcript). Scoring on one scale will push structural entities to the top. That is usually what the user wants, because they are the navigation targets, and text hits can take the "Top Hits"/quotes block.

### Gaps
- No source describes an explicit cross-type normalisation, such as score calibration or interleaving. Google's blending patents exist, but I found nothing on how productivity apps do it.

## 3. Tokens and filters: how do apps turn text into structured filters? How discoverable? How removed?

### Takeaway
Three mechanisms recur. **Pick a suggestion to create a token**: Mail, Finder, Apple's HIG guidance. **Typed operators**: Slack `from:`/`in:`, GitHub `repo:`/`org:`, Obsidian `path:`/`tag:`, Spotlight `kind:` and `/pdf`. **Type a scope name and press Tab**: Spotlight 26. Mail's token has a menu that changes its *meaning* (From / To / Subject / anywhere), which is the most transferable detail. Operators are powerful and poorly discoverable, and the better apps autocomplete them.

### Cited Findings
- **HIG (search-result excerpt of the Search fields page)**: "Use tokens to filter by common search terms or items. When you define a token, the term it represents gains a visual treatment that encapsulates it, indicating that people can select and edit it as a single item. Tokens can clarify a search term, like filtering by a specific contact in Mail, or focus a search to a specific set of attributes, like filtering by photos in Messages. Consider pairing tokens with search suggestions." — [Apple HIG: Search fields](https://developers.apple.com/design/human-interface-guidelines/components/navigation-and-search/search-fields)
- **Mail**: selecting a suggestion "appears as a token in the Search field". "If a search filter contains a down arrow, you can click it to change the filter", for example From versus To versus Subject versus entire message. To add more, "place the pointer after the first search filter, start typing search text, then choose a suggestion. Repeat as needed". Multiple tokens are ANDed ("Mail looks for messages that match all of the search filters"). Mail also accepts Boolean AND/OR/NOT and attribute words: type "flag" to get "Message is flagged", "unread", "attachment". — [Apple Support: Mail search](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac); [search excerpts of the same guide](https://support.apple.com/en-za/guide/mail/mlhlp1003/16.0/mac/26)
- **Finder**: the Add (+) button below the search field adds criteria rows with pop-ups (Kind → Document/Image; Name matches versus Contents). You can type metadata syntax such as `trip kind:document`. A search can be saved as a **Smart Folder**. — [Apple Support: Narrow search results on Mac](https://support.apple.com/guide/mac-help/narrow-search-results-mh15155/mac)
- **Spotlight 26**: "type the app name (e.g. Notes, Calendar) then press Tab" to scope to that app. "Type 'iCloud Drive,' press Tab, then type filename" to scope by location. "/" plus a type (e.g. `/pdf`) filters by kind, and `kind:images Edinburgh` works too. — [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/). Six Colors: "Type `/pdf` and then press return, and your search is automatically limited to PDFs." It criticises coverage gaps: no filter for Markdown, disk images or zips. — [Six Colors](https://sixcolors.com/post/2025/09/macos-26-tahoe-review-power-under-glass/)
- **Slack** modifiers: `from:`, `in:`, `has:`, `before:`/`after:`/`on:`/`during:`, `is:saved`, `is:thread`, `with:`. Example: "marketing report in:#team-marketing from:@Sara". After searching, a **Filters** button offers the same controls as a GUI. Slack AI search "automatically add[s] relevant filters". — [Slack Help](https://slack.com/help/articles/202528808-Search-in-Slack)
- **GitHub** code search: `org:`/`repo:` qualifiers "with auto-completion suggestions in the search box", plus `language:`, `path:`, `extension:`, `symbol:`, Boolean and regex. The input was redesigned with "suggestions and completions as you type". — [GitHub Changelog, Nov 2022](https://github.blog/changelog/2022-11-09-introducing-an-all-new-code-search-and-code-browsing-experience/); [GitHub Blog](https://github.blog/developer-skills/github/a-better-way-to-search-navigate-and-understand-code-on-github/)
- **Linear**: you narrow search by `@`-mentioning teams, users, status and properties, plus a Filter menu. The ⌘K command menu takes type prefixes: `i` issues, `p` projects, `u` users, `t` team, `l` labels, `f` favorites, `d` documents. — [Linear Docs: Search](https://linear.app/docs/search)
- **Obsidian** search operators: `tag:`, `path:`, `file:`, `line:`, `block:`, `section:`, and regex inside operators. The Quick Switcher, by contrast, is plain fuzzy file navigation. — [Obsidian Help: Search](https://obsidian.md/help/plugins/search); [Obsidian Rocks](https://obsidian.rocks/obsidian-search-five-hidden-features/)
- **Notion** filters: Last edited date, "Title only", Creators. An AI mode, "Search all sources with AI", opens a full page with filters by source, title and author. Preset filters cannot be customised. — [Notion Help](https://www.notion.com/help/search)
- NN/g on scoped suggestions: show the typed text, the suggested completion, and the scope "indented beneath, lighter gray", e.g. Amazon's "water bottle … _in Home & Kitchen_". — [NN/g: Site Search Suggestions](https://www.nngroup.com/articles/site-search-suggestions/)

### Inferences
- The Mail model is the closest analogue for Bristlenose's "picks become tokens" plan. The dropdown offers *filters*, grouped by kind. Picking one creates a token. The token has a disclosure menu that changes its role, for example a speaker token that can switch between "said by P3" and "mentions P3", or a tag token between "tagged" and "text contains". Tokens combine with AND.
- Make operators an accelerator that autocompletes into the same tokens, as GitHub and Slack do. They should not be the only way in. Slack exposes the same filters behind a GUI Filters button.
- The Spotlight 26 "type a name then Tab" pattern is a cheap way to scope to a lens: type "Quotes" and press Tab to get a Quotes-scoped search. Its discoverability is poor, as reviewers had to explain it.
- (unverified) Token removal in AppKit `NSTokenField`/`NSSearchField` token mode is Backspace at the token boundary, which selects the token and then deletes it. Mail and Finder follow this.

### Gaps
- I found no published usability data on operator discoverability (for example, share of Slack users using `from:`).

## 4. Scope: how do apps show and switch scope (this folder vs this Mac, this channel vs workspace)? Where does it live?

### Takeaway
The convention is: default broad (NN/g, HIG); show the active scope next to the field or at the top of results; give a one-click "search everywhere" escape. Apple desktop apps put scope in a **scope bar under the toolbar** (Finder, DEVONthink) or in a **"Search all mailboxes" row under the field** (Mail). Apps that put *local* search and *global* search on different shortcuts (Slack ⌘F vs ⌘G, Linear ⌘F vs `/`) sidestep the scope question.

### Cited Findings
- **HIG (search-result excerpt)**: "Default to a broader scope and let people refine it as they need. A broader scope provides context for the full set of available results." Also: "it's generally better to favor improving search results over including a scope bar … useful when there are clearly defined categories." — [Apple HIG: Search fields](https://developers.apple.com/design/human-interface-guidelines/components/navigation-and-search/search-fields)
- **NN/g**: "Always set the default scope to 'all'." Users "don't examine interfaces closely enough to notice restrictions", and they "forget previously selected scopes when returning to search". Users prefer to refine *after* seeing results. Show the scope label close to the search box and at the top of results, with "a one-click option to expand the search to the entire site." — [NN/g: Scoped Search](https://www.nngroup.com/articles/scoped-search/)
- **Mail** does the opposite of the NN/g default. It searches the current mailbox first, and users "click 'Search all mailboxes' below the search field" to widen. — [Apple Support: Mail search](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac)
- **DEVONthink**: in a toolbar search, a scope bar "below the toolbar" names the location. Selecting a different location in the sidebar updates the scope bar and the results. ⌘-click selects several locations. — [DEVONtechnologies blog (older app generation)](https://www.devontechnologies.com/blog/20231107-narrow-search-devonthink)
- **Xcode Find navigator**: a scope control ("In Project"/workspace) opens a list of scopes. Custom scopes persist across launches, stored in `IDEFindNavigatorScopes.plist` with name, predicate and source. — [Patrick Balestra: Xcode's Find Navigator & Search Scopes](https://patrickbalestra.com/blog/2020/02/09/xcode-find-navigator.html)
- **Slack**: ⌘G searches the workspace; ⌘F searches the current conversation. — [Slack Help](https://slack.com/help/articles/202528808-Search-in-Slack)
- **Linear**: `/` searches the workspace; ⌘F searches only the current board, list or Inbox. — [Linear Docs](https://linear.app/docs/search)
- **Things** puts the scope widening (to notes, checklists and the Logbook) in a result row, "Continue Search". — [Things Support](https://culturedcode.com/things/support/articles/2803584/)

### Inferences
- For Bristlenose's "this project vs all projects in a folder", use the Finder/DEVONthink placement: a scope bar at the top of the full results view, reading "This project · All projects". In the suggestion dropdown, add a Mail/Things-style bottom row ("Search all projects…"). NN/g's "default to all" conflicts with Mail's "current mailbox first". For a researcher inside one project, current-project-first with a visible escape row is defensible *if* the scope is named in the results header.
- Keep lens-scoped search, which already exists on individual lenses as ⌘F, separate from global search, following the ⌘F/⌘G split in Slack and Linear. That avoids hidden-scope confusion.

### Gaps
- I could not retrieve the macOS Finder scope-bar default preference ("When performing a search: Search This Mac / current folder / previous scope") from a primary source this session (unverified, from knowledge: Finder ▸ Settings ▸ Advanced).

## 5. Keyboard model: arrows, Return vs ⌘-Return, Tab between groups, Escape

### Takeaway
There is a strong shared grammar: ↑/↓ moves through rows; **⌘↑/⌘↓ jumps between sections** (Raycast; pre-Tahoe Spotlight, unverified); Return runs the primary action; ⌘Return runs the secondary action; ⌘K opens an actions panel (Raycast); holding ⌘ reveals the path (Spotlight). Escape clears first and closes second. Spotlight 26 gave **Tab** new meanings: scope to an app or location, and move between action parameters.

### Cited Findings
- **Raycast**: ↑/↓ navigate; ⌘↑/⌘↓ jump between sections; ⌥↑/⌥↓ page; Enter runs the primary action and ⌘Enter the secondary; ⌘K opens the Action Panel; "Escape: Clear search or close if empty"; Backspace on an empty field navigates back. — [Raycast Manual](https://manual.raycast.com/search-bar)
- **Spotlight 26**: Tab scopes to an app or location; Return executes; holding ⌘ reveals the file location path; ↑ in an empty field browses search history. — [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/). For actions, "use the tab key to move around and fill in the blanks". — [Six Colors](https://sixcolors.com/post/2025/09/macos-26-tahoe-review-power-under-glass/)
- **Spotlight (macOS 27 support page)**: Space previews (Quick Look); Tab "reveal[s] Quick Actions"; hold ⌘ to find the item's location. — [Apple Support](https://support.apple.com/guide/mac-help/search-with-spotlight-mchlp1008/mac). _Note that Tab here means Quick Actions, while the 26-era how-to says Tab means scope. The behaviour may differ by selection or version._
- **VS Code Quick Open**: pressing → opens the selected file in the background and keeps the picker open, for multi-open; pressing the shortcut repeatedly cycles recent files. — [VS Code Tips and Tricks](https://code.visualstudio.com/docs/getstarted/tips-and-tricks)
- **Things**: on Mac, just start typing anywhere to open Quick Find (or ⌘F). — [Things Support](https://culturedcode.com/things/support/articles/2803584/)
- **Linear** ⌘K menu: "brought closer to the UI element that it was invoked from … still retaining its searchability and keyboard controllability". — [Linear: Invisible details](https://linear.app/now/invisible-details)

### Inferences
- For a Mail-style dropdown with a Finder-style full view, a defensible mapping is: ↑/↓ over rows across groups (group headers skipped); ⌘↑/⌘↓ to the next or previous group; Return on a *filter* suggestion creates a token; Return on an *item* opens it in its lens; ⌘Return (or Return with no selection) opens the full grouped results view; Space previews a quote or clip; Escape first dismisses the dropdown, then clears the tokens and text, then gives up focus. Tab is contested (Spotlight uses it for scope and parameters), so don't rely on it for group navigation.

### Gaps
- Apple's own Mail and Finder keyboard behaviour inside the suggestion menu is not documented in the support pages I fetched.

## 6. Provenance: how does each result show where it came from?

### Takeaway
Provenance is usually a **secondary line or trailing label** (path, channel, mailbox, project), sometimes shown only on demand (Spotlight holding ⌘). Suggestion rows name their category (Mail), or their scope in grey beneath the text (NN/g/Amazon).

### Cited Findings
- Spotlight: hold ⌘ to "reveal its location path beneath the name". — [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/); [Apple Support](https://support.apple.com/guide/mac-help/search-with-spotlight-mchlp1008/mac)
- Raycast matches on "subtitle and keyword" as well as title, so rows carry a subtitle. — [Raycast Manual](https://manual.raycast.com/search-bar)
- NN/g scoped suggestions: the scope is "visually distinguished from the rest of the suggestion", indented and lighter grey. — [NN/g: Site Search Suggestions](https://www.nngroup.com/articles/site-search-suggestions/)
- Notion adds signal badges ("Most viewed", "Popular this week") to rows. — [Notion Help](https://www.notion.com/help/search)
- Xcode's Find navigator and VS Code's Search view group results **by file**, so the file header is the provenance for its match rows. VS Code offers sort and collapse for large result sets. — [VS Code Tips and Tricks](https://code.visualstudio.com/docs/getstarted/tips-and-tricks); [Patrick Balestra](https://patrickbalestra.com/blog/2020/02/09/xcode-find-navigator.html)

### Inferences
- For transcript and quote hits, the Xcode/VS Code "grouped by container" pattern maps onto Bristlenose as session (and speaker) headers with match lines beneath. Provenance becomes structural rather than repeated on each row. For cross-project search, add the project as an outer group or trailing label.

### Gaps
- Spotlight 26's default secondary-line content (app, folder, date?) was not documented in the sources I retrieved.

## 7. Fuzziness: typo tolerance, prefix, acronyms, semantic/natural-language search

### Takeaway
Navigation pickers (Slack Quick Switcher, Xcode Open Quickly, VS Code, Raycast) use **aggressive fuzzy matching**: acronyms, dropped separators, reordered words. Content search (Mail, Linear, Obsidian, DEVONthink) defaults to substring or word match, with natural-language or semantic layers on top: Mail NL, Spotlight "intelligent" relevance, Slack AI and Notion AI search. Some tools let users tune fuzziness (Raycast, DEVONthink).

### Cited Findings
- **Slack**: matches substrings split by `-`/`_`; separators can be omitted ("devweb" → "#devel-webapp"); word order is flexible ("design team" → "#design-team" and "#team-design"); acronyms work ("dh" → "Duretti Hirpa"). The implementation is a graph where each letter has "weighted edges to the following letter and to the beginning of other substrings". Target median render time is 7 ms. — [Slack Engineering](https://slack.engineering/a-faster-smarter-quick-switcher/)
- **Xcode Open Quickly**: "for DirectoryViewController.swift, you can just type 'dvc'". — [Effortless Code / Sarunw via search excerpt](https://sarunw.com/posts/xcode-shortcuts-for-navigation/). Developers reported that "the fuzzy search results of Xcode 15 beta Quick Open are inferior to Xcode 14", which shows fuzzy-ranking regressions are noticed. — [Apple Developer Forums](https://developer.apple.com/forums/thread/733567)
- Fuzzy ranking by "quality of the match, like the number of gaps and gap sizes" (a reference implementation modelled on Open Quickly). — [objc.io: A Fast Fuzzy Search Implementation](https://www.objc.io/blog/2020/08/18/fuzzy-search/)
- **Raycast**: three typo-sensitivity levels (High / Medium default / Low) adjust "how strict the fuzzy search algorithm is". — [Raycast Manual](https://manual.raycast.com/search-bar)
- **DEVONthink**: substring by default ("some" matches "something", "worrisome"). An optional fuzzy mode lets "Test" find "Text". — [DEVONthink help via search excerpt](https://download.devontechnologies.com/download/devonthink/3.8.2/DEVONthink.help/Contents/Resources/pgs/inspectors-search.html)
- **Mail natural language**: "searching 'NYC business trip' brings up emails about your itinerary, travel details, event locations". — [Apple Support: Mail search](https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac)
- **Linear** excludes common English stop words unless quoted. — [Linear Docs](https://linear.app/docs/search)
- **Slack AI** answers questions "in your own words" and adds filters itself; **Notion AI** "Search all sources with AI" opens a full filterable page. — [Slack Help](https://slack.com/help/articles/202528808-Search-in-Slack); [Notion Help](https://www.notion.com/help/search)
- Complaints about Spotlight on Tahoe: search "fixates on the first letter I type and does not adjust according to the full search term", along with missing results and unresponsiveness after the upgrade. — [Apple Community](https://discussions.apple.com/thread/256173961); [Mac Observer](https://www.macobserver.com/tips/how-to/spotlight-search-broken-since-update-to-macos-tahoe/)

### Inferences
- Split the matcher by entity type. Use Slack-style fuzzy/acronym matching for short-named entities (speaker names, tags, themes, sessions). Use word/prefix match with stemming for quote and transcript text, where fuzzy matching over long prose returns noise. Semantic search is the next tier, not the default: Notion and Slack put AI search behind an explicit row or mode.

### Gaps
- No source quantifies user satisfaction with semantic versus lexical search in these apps.

## 8. Progressive / streamed results — which fill in visibly, and how do they avoid "jumping"?

### Takeaway
The documented tactic is to **make the first tier fast enough that nothing streams**: prefetch on open, search only names at first, and push slow tiers behind a row the user chooses ("Continue Search"). I found no vendor write-up of anti-jump techniques for results that arrive late.

### Cited Findings
- Slack prefetches the Quick Switcher data "on open rather than on keystroke" and targets a 7 ms median render. — [Slack Engineering](https://slack.engineering/a-faster-smarter-quick-switcher/)
- Things searches names only at first "so suggestions can be shown as soon as you start typing". The deep search is a separate, deliberate step. — [Things Support](https://culturedcode.com/things/support/articles/2803584/)
- Spotlight's documentation says results appear "instantly". — [Apple Support](https://support.apple.com/guide/mac-help/search-with-spotlight-mchlp1008/mac)

### Inferences
- (unverified, from knowledge) Pre-Tahoe Spotlight visibly filled sections in as metadata queries returned, and the Top Hit could change under the cursor. This is a long-standing user annoyance, where Return hits a different item than intended. Common mitigations: keep the selected item pinned while late results arrive; append late groups below, never above, the current selection; fix group order so a late group occupies a reserved slot; or debounce and render once the local tier is complete.
- For Bristlenose, the local SQLite/FTS project search can be the fast tier. Cross-project search in a folder is the slow tier and belongs in a reserved "Other projects" group at the bottom, or behind a "Search all projects" row. It should not be interleaved.

### Gaps
- There is no primary source on Spotlight's, Mail's or Raycast's handling of late results. It would need hands-on observation or screen recording.

## 9. Empty and no-result states; recent searches

### Takeaway
An empty field shows **recents and pinned items**: Raycast favourites, calendar and recent files; Linear recent searches and recent issues; Notion recently viewed; Slack's clock-icon history; Spotlight 26 Files suggestions before typing, with ↑ for history. No results leads to **fallback actions**: Raycast fallback commands, Things' Continue Search, Mail's "Search all mailboxes". NN/g warns that every suggestion must lead to real results.

### Cited Findings
- Raycast's empty state shows Favorites, upcoming calendar events and recently used files. "Fallback commands" are user-configurable commands that "show up when there are no results in the Root Search", and they can be reordered. — [Raycast Manual](https://manual.raycast.com/search-bar); [Raycast v1.23 changelog](https://www.raycast.com/changelog/1-23-0)
- Linear: opening search displays "recent searches as well as a list of recent issues". — [Linear Docs](https://linear.app/docs/search)
- Slack: a "clock icon to show and hide your previous searches". — [Slack Help](https://slack.com/help/articles/202528808-Search-in-Slack)
- Notion shows recently viewed pages below results; presets, recent pages and recent searches cannot be customised. — [Notion Help](https://www.notion.com/help/search)
- Spotlight 26: Files "suggestions even if you don't type anything"; ↑ browses search history. — [Six Colors](https://sixcolors.com/post/2025/09/macos-26-tahoe-review-power-under-glass/); [MacRumors](https://www.macrumors.com/how-to/do-more-with-spotlight-in-macos-tahoe/)
- Xcode Find navigator keeps recent search history behind the magnifying-glass button. — [Patrick Balestra](https://patrickbalestra.com/blog/2020/02/09/xcode-find-navigator.html)
- NN/g: "Make sure every suggested query actually has good, relevant results". Users selected suggested queries in only 23% of cases where they were offered (ecommerce studies). — [NN/g: Site Search Suggestions](https://www.nngroup.com/articles/site-search-suggestions/)
- Finder saves a search as a Smart Folder, which gives a search a persistent identity. — [Apple Support: Narrow search results](https://support.apple.com/guide/mac-help/narrow-search-results-mh15155/mac)

### Inferences
- For Bristlenose's empty state: recent searches (token sets, restorable whole), then the current lens's most useful entry points (starred quotes, recent sessions). For no results: widen-scope rows ("Search all projects", "Search transcripts too") rather than a dead end. Finder's Smart Folder suggests a later "save search as a view", which ties into the codebook and tag lenses.

### Gaps
- No source documents Mail's or Finder's no-results state.

## 10. Published design rationale

### Takeaway
The Apple HIG token and scope guidance, NN/g's scoped-search and suggestion articles, Slack's Quick Switcher post and Linear's "Invisible details" are the citable rationale. I found no WWDC session on Spotlight 26's UI design this session.

### Cited Findings
- Apple HIG Search fields: tokens + suggestions, broad default scope, prefer better results over scope bars. — [HIG](https://developers.apple.com/design/human-interface-guidelines/components/navigation-and-search/search-fields) (from search-excerpt only; fetch returned empty)
- NN/g Scoped Search ("dangerous, but sometimes useful") and Site Search Suggestions. — [NN/g scoped](https://www.nngroup.com/articles/scoped-search/); [NN/g suggestions](https://www.nngroup.com/articles/site-search-suggestions/)
- Slack Engineering, "A faster, smarter Quick Switcher" (frecency + fuzzy graph). — [link](https://slack.engineering/a-faster-smarter-quick-switcher/); "Search at Slack" (architecture) — [link](https://slack.engineering/search-at-slack/)
- Linear, "Invisible details" (contextual command menu anchored to its invoking element) and the 2019 command menu changelog. — [Linear Now](https://linear.app/now/invisible-details); [Changelog 2019-12-18](https://linear.app/changelog/2019-12-18-new-command-menu)
- GitHub's code-search redesign posts. — [GitHub Blog: improving code search](https://github.blog/engineering/architecture-optimization/improving-github-code-search/)
- Apple Newsroom on Tahoe Spotlight ("list all result types … ranked intelligently", "advanced filtering … like PDFs or Mail messages", hundreds of actions). — [Apple Newsroom, June 2025](https://www.apple.com/newsroom/2025/06/macos-tahoe-26-makes-the-mac-more-capable-productive-and-intelligent-than-ever/)

### Inferences
- The strongest cross-source consensus: a broad default scope that is always visible and escapable; suggestions that pair with tokens; exact and name matches above frecency; a cheap first tier with a deliberate deep tier; a keyboard grammar of ↑↓ / ⌘↑↓ sections / Return / ⌘Return / Esc-clears-then-closes.

### Gaps
- There is no WWDC session transcript on the Spotlight 26 or macOS 27 search UI in this pass. The HIG "Searching" pattern page and the Search fields page need a direct read (the fetch was blocked) to quote exact wording on macOS scope bars.
- Not covered for lack of sources this session: Apple Notes search, Google Drive search chips, Alfred, VS Code's fuzzy scoring details, Xcode ⇧⌘F result-count display.
