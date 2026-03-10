# IDE-Inspired Codebook Autocomplete — Design Research

_Desk research: 9 Mar 2026. Prior art survey for the inline tag-application experience._

## The question

How should a researcher apply tags to quotes in Bristlenose's serve mode? Today, the `+` badge opens a `TagInput` with prefix-match suggestions and ghost text. That works, but it's one of several patterns. Before designing the next iteration, this document surveys how **IDEs, productivity tools, and competing qualitative-research platforms** solve the same problem: _give the user a large vocabulary of terms, let them pick or create one quickly, with minimal friction._

The core interaction is identical across domains:
1. User signals intent ("I want to label this thing")
2. A picker appears with the full vocabulary, filtered as they type
3. User selects an existing item or creates a new one
4. Picker closes; the label is applied

What varies — and what matters — is the trigger, filtering, visual hierarchy, keyboard flow, metadata display, and "create new" affordance.

---

## Part 1: IDE autocomplete patterns

### VS Code IntelliSense

**The gold standard for developer autocomplete.** VS Code's IntelliSense is the most studied and imitated suggestion UI in software.

**Trigger:**
- Automatic: appears as you type (controlled by `editor.quickSuggestions` — on by default in code, off in strings/comments)
- Manual: `Ctrl+Space` / `⌃Space`
- Character triggers: `.` in JavaScript, `::` in C++, etc. — language servers declare which characters trigger suggestions

**Filtering:**
- **Fuzzy matching** with CamelCase awareness — typing "cra" matches "createApplication"
- **Locality bonus** — variables from nearby scopes rank higher than distant ones
- **Recently-used bias** — `editor.suggestSelection: recentlyUsedByPrefix` remembers which suggestion you picked for each typed prefix
- Filter narrows as you type; the list contains "only members containing your typed characters"

**Visual design:**
- Popup appears directly below the cursor (or above if near the bottom of the viewport)
- ~12 visible items, scrollable
- Each row: **icon** (method, variable, field, class, interface, snippet, keyword — each with a distinct colour/shape) + **label** + **type annotation** (dimmed, right-aligned)
- Selected item: highlighted background row
- **Detail pane**: expands to the right of the list showing full documentation, parameter signatures, JSDoc comments. Toggled with `⌃Space` again or docs icon
- Width adapts to content; typically 300–450px

**Keyboard:**
- `↑` / `↓` to navigate suggestions
- `Tab` to accept (inserts at cursor)
- `Enter` to accept (behaviour controlled by `editor.acceptSuggestionOnEnter`)
- `Escape` to dismiss
- `Ctrl+Space` to re-invoke or toggle docs pane
- Continued typing filters without dismissing

**Snippet integration:**
- Snippets appear alongside language completions
- Configurable priority (`editor.snippetSuggestions`: `top`, `bottom`, `inline`, `none`)

**What makes it great:**
- Zero-latency filtering — the list feels instantaneous
- Fuzzy matching forgives typos and lets you type any substring
- The icon column gives instant visual categorisation without reading text
- Detail pane provides confidence ("is this the right `map`?") without leaving the list
- Tab vs Enter distinction lets power users commit without accidentally inserting newlines

**Relevance to Bristlenose:**
The vocabulary of codebook tags (~20–200 items) is far smaller than a typical codebase's symbol table (~10,000+). VS Code's fuzzy matching is designed for huge lists — we can borrow the interaction model (filter-as-you-type, icon column, keyboard navigation) without needing the full scoring algorithm. The **detail pane** is directly applicable: showing a tag's definition, example quotes, or group colour alongside the suggestion.

---

### JetBrains IntelliJ / WebStorm

**Three tiers of completion.** JetBrains takes a layered approach that progressively widens the search scope.

**Trigger:**
- Automatic: appears as you type (on by default, "Show suggestions as you type")
- Manual: `Ctrl+Space` (basic), `Ctrl+Shift+Space` (smart/type-matching), `Ctrl+Shift+Enter` (statement completion)

**Three completion levels (invoked by pressing `Ctrl+Space` repeatedly):**

| Invocation | Scope | What it shows |
|------------|-------|---------------|
| 1st `Ctrl+Space` | Current scope | Reachable symbols: classes, methods, fields, keywords, live templates |
| 2nd `Ctrl+Space` | Extended scope | Inaccessible classes (auto-imports) |
| 3rd `Ctrl+Space` | Entire project | Everything, regardless of dependencies |

**Smart completion** (`Ctrl+Shift+Space`) filters by **expected type at the cursor position** — if the context expects a `String`, only `String`-compatible suggestions appear. This is the "I know what type you need" mode.

**Filtering:**
- Partial matching: type any substring, suggestions contain your characters regardless of position
- CamelCase/snake_case recognition: typing initial letters matches compound names
- Case sensitivity: configurable (first letter only, or all)
- **ML-assisted ranking**: "prioritises completion suggestions based on choices that other users made in similar situations" — data collected locally, not uploaded. Indicated by up/down arrows on items showing ML reranking

**Visual design:**
- Similar popup to VS Code but with ML ranking indicators (↑↓ arrows showing items promoted/demoted by ML)
- Documentation panel: `Ctrl+Q` for quick docs, configurable auto-show delay
- Quick definition: `Ctrl+Shift+I` shows implementation inline

**Acceptance:**
| Key | Behaviour |
|-----|-----------|
| `Enter` | Insert at cursor |
| `Tab` | **Replace** existing text to the right (important distinction from VS Code) |
| `(` | Accept + auto-insert parentheses |
| `.` / space | Accept current + trigger next completion (if configured) |

**What makes it different from VS Code:**
- The **three-tier invocation** (scope → imports → project) is a deliberate "start narrow, widen on demand" pattern. The user controls how much noise they see
- **Tab replaces** (VS Code Tab inserts) — a subtle but important distinction. In JetBrains, Tab means "I meant this instead of what was already there"
- **ML ranking** is surfaced visually (arrows) so the user knows the order isn't purely alphabetical
- **Statement completion** (`Ctrl+Shift+Enter`) goes beyond picking a name — it completes the entire syntactic structure (adds parentheses, braces, semicolons). This has no analogue in tag picking

**Relevance to Bristlenose:**
The **three-tier widening** maps well to codebook hierarchies: first suggest tags from the _current framework/group_, then all tags, then offer to create a new one. The **Tab-replaces** behaviour is useful for our ghost text — Tab commits the ghost suggestion and replaces the typed prefix. ML ranking is interesting for future work: rank tags by how often the researcher has used them, or how often AutoCode proposed them.

---

### GitHub Copilot inline suggestions

**Ghost text, not a popup.** Copilot's innovation is showing suggestions _inline as grey text_ rather than in a floating list.

**Trigger:**
- Automatic: appears after a brief pause while typing (no explicit trigger needed)
- The suggestion appears at the cursor as **dimmed ghost text** — visually distinct from authored code

**Visual design:**
- Ghost text is rendered in a lighter/dimmed colour, inline with the cursor position
- Since Nov 2025: **syntax highlighting** in ghost text (`editor.inlineSuggest.syntaxHighlightingEnabled`) — not just grey, but colour-coded by language. Reduces cognitive load when scanning multi-line suggestions
- A small toolbar appears on hover (accept, cycle, dismiss)
- Font family configurable (`editor.inlineSuggest.fontFamily`)

**Acceptance:**
| Key | Behaviour |
|-----|-----------|
| `Tab` | Accept entire suggestion |
| `⌘→` / `Ctrl+Right` | Accept **next word** (partial accept) |
| `⌘⇧→` / `Ctrl+Shift+Enter` | Accept **first line** only |
| `⌥]` / `Alt+]` | Cycle to next suggestion |
| `⌥[` / `Alt+[` | Cycle to previous suggestion |
| Keep typing | Dismiss/ignore the suggestion |
| `Escape` | Dismiss |

**Multiple suggestions:**
- When multiple alternatives exist, hover reveals navigation arrows
- The ⌥] / ⌥[ shortcuts cycle through them without using the mouse

**What makes it work:**
- **Zero UI chrome** — no popup, no list, just grey text appearing where you'd type it. The cognitive cost of "reading a suggestion" is near zero because it's already in context
- **Partial acceptance** is powerful — accept word-by-word or line-by-line, keeping what's useful and diverging where needed
- **Dismissal is free** — just keep typing. No Escape needed. If the suggestion is wrong, your keystrokes overwrite it naturally

**Relevance to Bristlenose:**
We already have ghost text in `TagInput` — a lighter version of this pattern. The **partial acceptance** concept could apply: typing "us" shows ghost "ability" (completing "usability"), and pressing `→` accepts the suffix. Our current implementation already supports ArrowRight for ghost acceptance. The **word-by-word** accept could be useful for longer tag names like "Information Architecture" — type "Info", see ghost "rmation Architecture", press `→` to accept.

---

### Figma's Quick Actions / Component search

**Command palette meets component browser.**

**Trigger:**
- `⌘/` or `Ctrl+/` opens Quick Actions
- Also accessible from the menu

**What it searches:**
- Actions/commands (like VS Code's command palette)
- Components from team libraries
- Plugins
- Files

**Visual design:**
- Centered modal with search input at top
- Results grouped by category (Actions, Components, Plugins) with section headers
- Each result: icon + name + source (which library/file)
- Keyboard navigable

**Filtering:**
- Fuzzy search across all categories simultaneously
- Results ranked by relevance and recency
- Categories collapse/expand as results narrow

**Relevance to Bristlenose:**
The **multi-category grouping** is directly applicable. Our tag suggestions could be grouped by codebook framework: "Garrett Elements" section, "Norman Principles" section, "User Tags" section. Each group has its own colour, and the visual grouping helps the researcher navigate a mixed vocabulary. The **centered modal** approach is heavier than our inline popup, but the section-header pattern within a popup is worth borrowing.

---

### Slack's trigger-character patterns

**Three distinct autocomplete triggers in one text field.**

| Trigger | What it invokes | Filter behaviour |
|---------|----------------|------------------|
| `/` | Slash commands | Prefix match on command name, shows description |
| `:` | Emoji picker | Appears after `:` + 2 chars (avoids false positives on `:)` and `:D`). Matches emoji name substrings |
| `@` | User/channel mentions | Fuzzy match on display name |

**Visual design (emoji):**
- Small popup below the cursor
- Grid or list of matching emoji with name labels
- `Enter` selects, popup closes
- The `:` trigger + 2-char minimum is clever — prevents the popup from appearing on emoticon text like `:)`

**Visual design (slash commands):**
- List popup below the cursor
- Each entry: `/command-name` + short description text
- Type-to-filter narrows the list

**Relevance to Bristlenose:**
The **trigger character** concept is directly applicable. Marvin already uses this: `/` for questions, `#` for labels. We could adopt a trigger character for tag application (perhaps `#` on a selected quote, or a hotkey that opens the tag picker). The **2-character minimum** before showing suggestions avoids false triggers — useful if we use a common character as the trigger. The **description text** alongside each suggestion is essential for codebook tags where the name alone may not convey meaning (e.g., "Feedback" could mean Norman's design feedback or generic user feedback).

---

### Notion's slash commands

**The productivity-tool implementation of command palettes.**

**Trigger:**
- Type `/` at the beginning of a line or after a space
- Immediately shows a categorised menu of block types

**Visual design:**
- Dropdown appears inline below the slash
- Sections: "Basic blocks", "Media", "Databases", "Advanced", etc.
- Each item: icon + name + brief description
- Scrollable, ~8 visible items
- Type-to-filter narrows across all sections

**"Create new" affordance:**
- Not applicable for Notion's block types (fixed vocabulary)
- For tags/labels in Notion databases: the property field shows existing options with a "Create [typed text]" option at the bottom when no match

**Relevance to Bristlenose:**
The **"Create [typed text]"** affordance at the bottom of the suggestion list is exactly what we need. When the researcher types a tag name that doesn't exist, the last item in the dropdown should say "Create 'usability'" — making it clear that Enter will create a new tag rather than applying an existing one. Notion's database tag pickers also support **multi-select** — clicking multiple tags before closing the picker. This could be useful for bulk-tagging.

---

## Part 2: Qualitative research tools

### Dovetail — the market leader

**Highlight → Tag workflow.** Dovetail is the closest competitor and the tool most researchers compare us against.

**Creating highlights:**
- Select text in a transcript/note → an **action menu** appears (floating toolbar above/below selection)
- Options in the action menu: Highlight, Tag, and other actions
- **Tab** key cycles through the action menu items (power-user shortcut)
- Selecting "Tag" creates a highlight _and_ opens the tag picker simultaneously

**Tag picker:**
- Appears as a dropdown/popover near the selection
- Type to filter existing tags — **autocomplete** narrows the list as you type
- Tags are organised into **groups** (visible as section headers in the picker)
- Each tag appears with its **group colour** as a visual indicator
- "Create new tag" option available inline — type a name that doesn't exist, option to create it

**Tag creation flow:**
- **Inline creation**: From the tag picker, type a new name → create it on the spot
- **Tag board**: Dedicated view for organising tags into groups, defining colours, managing taxonomy
- Tags can be created either from the tag board (admin mode) or inline during coding (rapid mode)

**AI-assisted tagging ("Magic Highlights"):**
- **Suggest** button in the highlights sidebar: Dovetail's AI automatically highlights and tags content using existing project tags
- Auto-tagging improves over time as more highlights are tagged (learns from usage patterns)
- Since 2025: Magic Highlights automatically tags highlights using both project and workspace tags
- AI suggestions are presented as tentative — the researcher reviews and can accept or dismiss them

**Keyboard shortcuts:**
- `Tab` to cycle through the action menu on text selection
- No documented hotkey to directly apply a specific tag (unlike Atlas.ti's quick coding)
- The emphasis is on mouse-driven selection + type-to-filter

**Visual design of tags:**
- **Colour-coded pills** — each tag inherits its group colour
- Tags appear as small coloured badges on highlighted text
- On the tag board: tags are organised into columns by group, each with a header colour
- A single highlight can have **multiple tags** (many-to-many relationship)

**Notable UX decisions:**
- The action menu is a **floating toolbar** (not a context menu) — it appears right at the selection, minimising mouse travel
- "Highlight" and "Tag" are separate actions — you can highlight without tagging, or tag (which auto-creates a highlight)
- Tag autocomplete searches across all project tags, not just the currently visible group

**Commentary:**
Dovetail's approach is clean but **mouse-heavy**. The floating action menu is fast for occasional tagging but slower than keyboard-driven workflows for batch coding. The AI auto-tagging is the most aggressive in the market — it applies tags automatically rather than just suggesting. From our codebook strategy doc: "Existing tools (e.g. Dovetail) attempt auto-tagging based on the researcher's own tags, but with no conceptual grounding the LLM is essentially doing autocomplete on vibes."

**What Bristlenose can learn:**
- The floating action menu on selection is effective — consider it for transcript-page tagging
- Group colours in the tag picker are essential for visual orientation in a mixed vocabulary
- Inline tag creation (without leaving the picker) is table stakes
- Auto-tagging that pulls from existing project tags is the baseline expectation

---

### HeyMarvin — AI-first tagging

**The most keyboard-friendly qual tool.** Marvin differentiates by making tagging fast and AI-assisted.

**Trigger characters for tagging:**
- **`/`** for questions (from discussion guide) — triggers autocomplete showing pre-created questions
- **`#`** for labels/tags — triggers autocomplete showing pre-created tags
- This is the only qual tool that uses **IDE-style trigger characters** for tagging

**Live Notes (real-time tagging during interviews):**
- Collaborative note-taking panel alongside the transcript
- Type `#` → autocomplete appears with existing labels
- Type `/` → autocomplete appears with discussion guide questions
- Press **Return** to bookmark a moment for later tagging
- Timestamps are automatically attached to every tag application

**Tag creation flow:**
- **Pre-interview setup**: create tags before research begins (recommended workflow)
- **Templates**: save and reuse tag sets across projects ("Save labels as template")
- **Inline creation**: create new tags on the fly during tagging if unexpected themes emerge
- Tags support **parent-child hierarchy** (nested codes)

**Tag hierarchy:**
- **Parent-child relationships** — e.g., "Product Features" → "Live Notes", "Transcription", "AI Analysis"
- Hierarchy visible in the tag picker, enabling both broad and specific coding
- **Template tags** shown in **purple**; project-specific tags in **pink** — visual distinction of tag origin/provenance

**AI features ("Ask Marvin"):**
- AI automatically tags important moments during transcription
- AI can "review codes, suggest sub-codes, and apply tags across transcripts"
- AI suggestions are presented as automatic tags that the researcher can review/modify
- Marvin's approach is more aggressive than Dovetail — the AI **applies** tags rather than just suggesting them

**Post-interview analysis (Analyze page):**
- Filter by questions: group tagged responses by discussion guide question
- Pencil icon to view individual responses
- Add/refine tags during analysis
- **Multi-label filtering**: AND/OR logic to combine tags

**Visual design:**
- Template tags: **purple** pills
- Project tags: **pink** pills (Marvin's brand colour)
- Parent-child hierarchy shown with indentation in the tag picker
- Highlight reels: video playlists filtered by tag combinations

**Notable UX decisions:**
- The **trigger character** approach (`#` and `/`) is borrowed directly from Slack/IDE patterns — it's the fastest way to tag because you never leave the keyboard
- The distinction between **template tags** (purple, shared) and **project tags** (pink, local) is a provenance signal — you can see at a glance whether a tag came from a reusable template or was created ad hoc
- Marvin encourages **"more is greater than less"** for initial tags — create many, refine later. This is the opposite of Atlas.ti's academic approach (define carefully first)

**Commentary:**
Marvin's `#` trigger for tags is the closest thing to IDE-style autocomplete in the qual research space. It eliminates the "click +, then type" two-step that most tools (including Bristlenose) currently require. The provenance colouring (purple template vs pink project) is clever and maps directly to our framework tags (imported codebook) vs user tags distinction.

**What Bristlenose can learn:**
- **Trigger characters** for tagging reduce friction dramatically — consider `#` or a hotkey to invoke the tag picker inline
- **Tag provenance colouring** — visually distinguish framework tags (imported codebook) from user-created tags from AutoCode-proposed tags
- **Template/reusable tag sets** — we already have this via codebook import, but the template UX (save/load) is worth studying
- The **aggressive AI tagging** (apply, not just suggest) is Marvin's bet. We've chosen tentative badges with accept/deny — a more conservative approach that preserves researcher agency

---

### Atlas.ti — the academic heavyweight

**The most keyboard-rich coding tool.** Atlas.ti has been the standard for academic qualitative research since 1993. Its coding UX prioritises speed for power users.

**Core coding flow:**
1. Select text segment in the document
2. Open the **Coding Dialog** (`Ctrl+J` / right-click → "Apply Codes")
3. Type to search existing codes — **type-ahead filtering** narrows the list by initial letters
4. Select a code and click `+` or press `Enter`
5. Dialog closes automatically after application

**Quick Coding (`Ctrl+L`):**
- Applies the **most recently used code** to the current selection — one keystroke, no dialog
- This is the power user's workhorse: select text, `Ctrl+L`, done
- The "last used" code is shown in the toolbar dropdown; click the dropdown to change it

**In-Vivo Coding (`Ctrl+Shift+V`):**
- Creates a code using the **selected text itself as the code name**
- Simultaneously creates a quotation (highlight) — two actions in one keystroke
- Powerful for grounded theory methodology where codes emerge from data
- Warning from Atlas.ti docs: "Over-dependence on in-vivo codes can limit your ability to transcend to more conceptual levels"

**Drag-and-Drop Coding:**
- Drag a code from the Code Browser/Manager onto highlighted text
- Works across panes: Code Manager can be docked alongside the document

**Coding Dialog details:**
- Search box at top: type to filter
- Code list below: all project codes, filterable
- `+` button to create new code inline
- Comment field for adding definitions
- Dialog closes after each code application (not modal — it's a one-shot action)

**Code Manager:**
- Dedicated panel for code administration
- Codes can be organised into **groups** (but the coding dialog shows a flat list, not grouped)
- Each code shows: name, frequency count (groundedness), comment indicator (yellow post-it icon)

**Visual feedback:**
- **Margin area**: coded segments shown as coloured bars in the document margin, with code names
- Blue bars mark quotation boundaries
- Multiple overlapping codes stack in the margin
- Colour coding per code/group

**AI Coding (Atlas.ti 24+):**
- AI suggests initial codings automatically
- Presented as suggestions for researcher review
- Details sparse in documentation — relatively new feature

**Keyboard shortcuts summary:**
| Shortcut | Action |
|----------|--------|
| `Ctrl+J` | Open Coding Dialog |
| `Ctrl+L` | Quick Coding (apply last used code) |
| `Ctrl+Shift+V` | In-Vivo Coding |
| `Ctrl+K` | Create Free Code (not linked to a selection) |

**Notable UX decisions:**
- **The Coding Dialog is a one-shot action**, not a persistent panel. Apply one code, dialog closes. This matches the rhythm of qualitative coding: select, code, move on
- **Quick Coding** is the fastest tag application in any tool — a single keystroke applies a code. No picker, no typing, no confirmation
- **The margin area** is a persistent visual summary of all coding — you can see at a glance how densely coded a passage is without any click

**Commentary:**
Atlas.ti's UX is optimised for **throughput** — how many segments can a researcher code per minute. The Quick Coding shortcut alone is a significant speed advantage. The downside is **discoverability**: the three coding modes (dialog, quick, in-vivo) are hidden behind keyboard shortcuts that new users don't know exist.

**What Bristlenose can learn:**
- **Quick Coding** (apply last used code with one keystroke) is directly applicable. After a researcher tags a quote with "Usability", the next time they want to apply the same tag, one keystroke should do it
- **In-Vivo Coding** is interesting for user-created tags: select the quote text, and the selected words become the tag name. We don't need this yet, but it's a natural extension
- **The margin annotation** pattern — showing codes in the document margin — is valuable for the transcript page where coded segments should be visible at a glance
- The **one-shot dialog** (apply and close) matches our current TagInput behaviour. Don't change this — it's right

---

### NVivo — the enterprise/academic standard

**Ribbon UI, node-based coding.** NVivo (by Lumivero, which acquired Atlas.ti in Sept 2024) uses a different mental model: codes are called "nodes" and live in a hierarchical tree.

**Coding flow:**
- Select text → right-click → "Code At" → navigate the node tree to find the target node
- Or: drag selected text onto a node in the left sidebar
- Or: use the **Quick Coding Bar** (toolbar at top) — type a node name, autocomplete suggests matches

**Quick Coding Bar:**
- Persistent toolbar at the top of the document view
- Type to search nodes — **autocomplete** filters the node tree
- Select a node → code is applied to the current selection
- Can create new nodes inline

**Coding Stripes:**
- Visual bars in the right margin showing which nodes are applied to which text ranges
- Colour-coded by node
- Click a stripe to see the full node details
- Density of stripes gives a visual sense of how thoroughly the passage has been coded

**AI features (NVivo 15+):**
- Text summarisation
- Coding suggestions (AI suggests which nodes to apply)
- Sentiment analysis
- **AI suggests child codes** within existing categories — not just applying existing codes but proposing new sub-codes

**Node hierarchy:**
- Tree structure: parent nodes → child nodes → grandchild nodes
- The tree is the primary organisational metaphor (vs Atlas.ti's flat list + groups)
- Hierarchy visible in the Quick Coding Bar autocomplete

**Relevance to Bristlenose:**
The **Quick Coding Bar** concept — a persistent search input at the top of the coding view — is worth considering as an alternative to the inline `+` button popup. The persistent bar means the researcher doesn't need to click `+` first; they just start typing in the bar. The **coding stripes** are essentially our margin annotations from the transcript page.

---

### Dedoose — mixed methods, cloud-based

**Designed for team-based mixed-methods research.**

**Coding flow:**
- Select text → apply codes from a sidebar code tree
- Code tree is persistent in the left panel
- Click a code in the tree → it applies to the current selection
- Supports code **ratings** (not just present/absent — each application can have a numeric weight)

**Notable features:**
- **Code tree** always visible in the sidebar (no popup needed)
- Codes have **definitions** visible on hover
- Designed for **distributed teams** — cloud-based, real-time collaboration
- Mixed methods: codes can be linked to quantitative descriptors

**Relevance to Bristlenose:**
The persistent sidebar code tree is similar to our Tag Sidebar. The **ratings** concept (scoring each code application) is interesting for future work but not immediately relevant.

---

### Delve Tool — lightweight, modern

**Minimal UI for small-team qualitative coding.**

**Coding flow:**
- Select text → code picker appears as a dropdown
- Type to search codes
- Codes organised in a flat list (no hierarchy)
- Create new codes inline

**Notable features:**
- Intentionally simple — no code groups, no hierarchy
- Designed for researchers who find Atlas.ti/NVivo overwhelming
- Fast onboarding — "start coding in 5 minutes"

**Relevance to Bristlenose:**
Validates the "simple flat list with search" approach for small codebooks. Our Tag Sidebar already provides hierarchy — the inline picker can be flat (all tags) with visual group indicators, leaving the full hierarchy to the sidebar.

---

### Condens.io — repository-focused

**Emphasis on insights and evidence, not heavy coding.**

**Tagging flow:**
- Tag highlights with labels from a shared vocabulary
- Type to filter tags — autocomplete with prefix matching
- Colour-coded tags
- Designed for insight repositories, not deep qualitative analysis

**Relevance to Bristlenose:**
Similar to our use case for the export/sharing scenario — lightweight tagging for insight organisation rather than academic coding rigour.

---

## Part 3: Productivity-tool patterns

### GitHub Issues / Linear — label pickers

**Multi-select label dropdowns with search.**

**Interaction:**
- Click the "Labels" field → dropdown opens with all available labels
- Search input at top of dropdown: type to filter
- Click labels to toggle selection (multi-select by default)
- Each label: **colour dot** + name + optional description
- "Create new label" link at the bottom (GitHub) or "Create [typed text]" (Linear)
- Click outside or press Escape to close
- Selected labels appear as coloured pills on the issue

**What makes this relevant:**
- The **multi-select** pattern — clicking multiple tags before closing — could speed up initial coding where a quote clearly belongs to multiple tags
- The **colour dot** next to each label provides instant visual categorisation
- The **"Create [typed text]"** affordance at the bottom normalises inline creation

### Slack's @ / # / : pickers

**Trigger-character autocomplete in a text field.**

| Trigger | What | Filter | Min chars |
|---------|------|--------|-----------|
| `@` | Users/channels | Fuzzy on display name | 1 char |
| `#` | Channels | Prefix on channel name | 1 char |
| `:` | Emoji | Substring match | **2 chars** (avoids `:)` `:D` false positives) |
| `/` | Slash commands | Prefix on command name | 0 chars (shows all on `/`) |

**Design details:**
- Popup appears **below the cursor** in the text field
- Each entry: icon/avatar + name + metadata (status for users, purpose for channels)
- `Enter` selects, popup closes, the entity is inserted as a rich token
- The **2-char minimum** for emoji is a defensive measure against false triggers — important if we use a common character like `#` as our trigger

---

## Part 4: Synthesis — patterns that matter for Bristlenose

### Universal patterns (every good implementation has these)

| Pattern | Description | Already in Bristlenose? |
|---------|-------------|------------------------|
| **Type-to-filter** | List narrows as you type | Yes (TagInput) |
| **Keyboard navigation** | ↑↓ to move, Enter/Tab to accept, Escape to cancel | Yes (TagInput) |
| **Ghost text** | Preview of best match inline | Yes (TagInput) |
| **Immediate filtering** | No delay between keystroke and filter update | Yes |
| **Inline creation** | "Create [typed text]" when no match | Partial (TagInput creates on Enter, but no explicit "Create X" label in dropdown) |

### Patterns we're missing

| Pattern | Where it's used | Benefit | Priority |
|---------|----------------|---------|----------|
| ~~**Group headers in suggestions**~~ | ~~Figma, VS Code (categories), NVivo (node tree)~~ | ~~Researcher can see which framework a tag belongs to~~ | ~~High~~ ✅ Stage 1 |
| ~~**Tag colour in suggestions**~~ | ~~Dovetail, GitHub Labels, NVivo~~ | ~~Visual orientation in a mixed vocabulary~~ | ~~High~~ ✅ Stage 1 |
| ~~**Quick-apply last tag**~~ | ~~Atlas.ti (`Ctrl+L`)~~ | ~~One-keystroke repeat for batch coding~~ | ~~High~~ ✅ Stage 2 |
| **Trigger character** | Marvin (`#`), Slack (`:`), Notion (`/`) | Invoke picker without clicking a button first | Medium |
| **Detail/definition pane** | VS Code (docs panel), Atlas.ti (comments) | Show tag `apply_when` text alongside the suggestion | Medium |
| **Fuzzy matching** | VS Code, JetBrains, Slack (@) | Forgive typos: "usblty" → "Usability" | Medium |
| **Recently-used ranking** | VS Code (`recentlyUsedByPrefix`), JetBrains (ML) | Most-used tags float to the top | Medium |
| **Multi-select** | GitHub Labels, Notion database tags | Apply several tags before closing the picker | Low (our badge UX is one-at-a-time) |
| **Provenance colouring** | Marvin (purple template vs pink project) | Distinguish framework vs user vs AI tags visually | Low (we have this via group colours) |

### Key design questions for Bristlenose

1. **Where should the picker appear?**
   - Current: inline popup attached to the `+` badge (below the quote card badges)
   - Alternative A: floating popover near the cursor/badge (Dovetail style)
   - Alternative B: persistent Quick Coding Bar at top of quotes page (NVivo style)
   - Alternative C: sidebar tag panel with click-to-apply (Dedoose style — we already have the Tag Sidebar)

2. **Should we add a trigger character?**
   - Marvin uses `#` for labels. We could intercept `#` while a quote is focused to open the tag picker
   - Risk: false triggers. Slack's 2-char minimum is a good safeguard
   - The existing `+` button click is explicit and discoverable; a trigger character is faster but hidden

3. **Should we add Quick Coding (repeat last tag)?**
   - Atlas.ti's `Ctrl+L` is the single biggest speed boost for batch coding
   - In Bristlenose: when a quote is focused, pressing a hotkey (e.g., `T` or `Ctrl+T`) applies the last-used tag instantly
   - This pairs well with j/k navigation: j → T → j → T → j → T (move through quotes, stamping the same tag)

4. **How should group/framework context appear in the suggestion list?**
   - Option A: Section headers between groups (like Figma categories)
   - Option B: Coloured dot prefix per item (like GitHub Labels) + dimmed group name
   - Option C: Indented tree (like NVivo) — probably too heavy for a popup

5. **Should we show tag definitions in the picker?**
   - VS Code's detail pane shows documentation alongside suggestions
   - Our codebook tags have `apply_when` and `not_this` descriptions
   - Showing these in a side panel (VS Code style) would help researchers distinguish similar tags
   - Cost: wider popup, more visual complexity

6. **Should we support multi-select?**
   - GitHub Labels let you click multiple labels before closing
   - Our current flow: add one tag → picker closes → click `+` again for another
   - Tab-to-reopen (`onCommitAndReopen` in TagInput) already supports rapid multi-entry
   - True multi-select (checkboxes) changes the mental model from "pick one" to "configure a set"

---

## Part 5: Design decisions

_Decisions agreed 9 Mar 2026._

### Decision 1: Picker placement — keep the `[+]` badge inline popup

**Decision:** Keep the current `[+]` badge → inline TagInput popup. No change to placement.

**Rationale:** Unless we change the model to text-selection-based tagging (Dovetail) or line-based coding (Atlas.ti), we are applying tags to the **paragraph-quote unit**. The `[+]` affordance on the badge row is the right place — it's visually attached to the thing being tagged. Alternatives considered:
- Floating popover (Dovetail) — suited to text selection, not paragraph units
- Persistent Quick Coding Bar (NVivo) — adds always-visible chrome; too heavy
- Sidebar click-to-apply (Dedoose) — we _will_ add this as an additional path (see Decision 6/sidebar interactions), but it's additive, not a replacement

### Decision 2: Trigger — keep `t` hotkey, no trigger character

**Decision:** No trigger character (`#`, `/`). The existing `t` keyboard shortcut (when a quote has focus) opens the tag picker. This is sufficient.

**Rationale:** `#` requires Shift on US keyboards and is worse on non-US layouts (e.g., UK: `Alt+3`, German: dead key). The `t` hotkey is already discovered via the `?` help modal and pairs naturally with `j`/`k` navigation. Adding a trigger character inside the TagInput text field would conflict with legitimate tag names containing `#`.

### Decision 3: Quick-repeat — `r` applies last-used tag

**Decision:** Press `r` to apply the **most recently used tag** to the focused quote(s) or all selected quotes. `t` still opens the TagInput picker. `r` is right next to `t` on QWERTY — ergonomic for the `j → t → ... → j → r → j → r` batch-coding workflow.

**Rationale:** This borrows Atlas.ti's `Ctrl+L` Quick Coding concept but uses a single unmodified key. Originally designed as double-tap `t` (within 400ms), but that conflicted with TagInput — the first `t` opens the picker and the second types `t` into it, triggering autocomplete for t-prefixed tags instead of quick-applying. A dedicated `r` key avoids the conflict entirely. The workflow becomes:

```
j → t → type "usability" → Enter    (tag first quote)
j → r                               (stamp same tag on next quote)
j → r                               (and the next)
j → t → type "learnability" → Enter  (switch to a different tag)
j → r                               (stamp the new tag)
```

**Implementation notes:**
- `lastUsedTag: TagResponse | null` module-level variable in `QuotesContext.tsx` — stores full `TagResponse` (with colour metadata) set by `addTag()`, cleared by `resetStore()`
- `r` keydown in `useKeyboardShortcuts.ts` calls `handleQuickApply()` which reads `getLastUsedTag()`, applies to all targets (selected quotes or focused quote), and triggers flash animation via `flashTag()` FocusContext registry
- Flash animation reuses the existing `badge-accept-flash` CSS keyframe (Decision 7 — flash on all tag adds)
- If no `lastUsedTag` exists (first tag action in the session), `r` is a no-op (silent, no error)

### Decision 4: Group context in suggestions — section headers with indented tags

**Decision:** Option A — Figma-style section headers between groups. Tags indented below their group header. Tags render in their codebook font and colour. Group headers show the group background colour and are **non-selectable** (arrow keys skip them).

**Detailed design:**

When the researcher types "Fee" in the TagInput, the dropdown shows:

```
 Feedback                        ← group header (Norman), non-selectable
   ┊ delayed feedback            ← tag, monospace, coloured pill style
   ┊ ambiguous feedback          ← tag
   ┊ missing feedback            ← tag

 User Tags                       ← group header, non-selectable
   ┊ feedback loop               ← tag, different colour
```

When the researcher types "Sig":

```
 Signifiers                      ← group header (Norman), non-selectable
   ┊ affordance                  ← tag
   ┊ perceived affordance        ← tag
   ┊ false signifier             ← tag
   ┊ missing signifier           ← tag
```

But typing "miss" (matching only one tag, not the group name):

```
   ┊ missing signifier           ← tag (group header omitted when only 1 match? or shown dimmed?)
   ┊ missing feedback            ← tag from different group
```

**Visual rules:**
- Tags display in their actual codebook font and colour (monospace badge styling)
- Group headers show the group's background colour (the codebook palette colour)
- Group header text is _not_ monospace — it's the regular UI font, slightly bolder/larger
- **Selection highlight for active tag:** Can't use blue background + blue text (would clash with tag colours). Instead: **bright white text in dark mode / fully black text in light mode**, with a moderate background lightness shift. Use CSS `color-mix()` to derive the highlight background from the tag's group colour at ~15% opacity (light mode) or ~25% opacity (dark mode). This preserves the tag's colour identity while clearly showing selection
- Arrow-down/up **skips** group headers — you can only land on tags
- If a group has zero matching tags after filtering, the entire group (header + tags) is hidden

**Data requirements:**
- TagInput needs to receive not just a flat `vocabulary: string[]` but a **structured vocabulary** with group metadata: `{ groupName: string; colourSet: string; tags: string[] }[]`
- The filtering logic groups results by their parent group and renders section headers between them
- Sort order: groups in their codebook order, tags alphabetically within each group

### Decision 5: Tag definitions — not shown in picker

**Decision:** No definition/detail pane in the autocomplete picker.

**Rationale:** Too much visual complexity for the inline popup. The codebook tab is the right place to read `apply_when` / `not_this` descriptions. If needed in the future, consider a tooltip on hover over a suggestion item, or a detail pane in the codebook tab.

### Decision 6: Multi-select — no, but sidebar interactions add bulk tagging

**Decision:** The TagInput picker remains single-select (one tag per invocation). Tab-to-reopen (`onCommitAndReopen`) already supports rapid multi-entry. True multi-select (checkboxes) is not needed.

However, **three new sidebar interaction patterns** enable bulk tagging and filtering:

#### 6a. Sidebar tick click — hide/show quotes with a specific tag

**Current behaviour (eye toggle):** Click the eye icon on a tag group to hide/show badges for that group. This is a _badge visibility_ toggle, not a _quote filter_.

**New interaction:** Clicking the **tick/checkbox** next to a tag in the sidebar toggles quote _visibility_ — unchecked tags' quotes are hidden from the main view. This is the existing tag filter behaviour but exposed per-tag in the sidebar.

#### 6b. Sidebar count/bar click — "show only this tag"

**New interaction:** Clicking the **count number** or **micro-bar** on a tag in the sidebar activates a "show only" mode:
1. All other tag ticks are unchecked (their quotes hidden)
2. Only quotes with the clicked tag are shown
3. The researcher can now read through all quotes with that specific tag

**Undo behaviour:**
- Clicking the same count/bar **again** restores the previous tick state (toggle back)
- If the researcher starts clicking _other_ count/bars, they're now "building up from nothing" — the previous state is lost, and they're free to tick individual tags to add them to the view. This is acceptable because the user has clearly shifted intent from "undo my filter" to "construct a new filter"

**"No tags" checkbox:** Add a "No tags" checkbox at the top of the tag sidebar to show/hide quotes that have no tags applied. Currently this is implicit — we show untagged quotes by default. Making it explicit lets the researcher filter to "only untagged" (useful for finding what still needs coding).

#### 6c. Sidebar tag click — assign tag to focused/selected quotes

**New interaction:** When one or more quotes are focused/selected (blue outline), clicking a **tag name** in the sidebar **assigns that tag** to the focused/selected quote(s).
- Quotes stay selected after assignment (user can click multiple tags to assign several)
- Use the success blink animation (same as badge accept) to confirm each assignment
- This is the Dedoose-style "click to apply from sidebar" pattern, but only active when quotes are selected — otherwise clicking a tag name could be confused with filtering

#### 6d. Drag-and-drop tag → quote

**Future interaction (not in first implementation):** Drag a tag from the sidebar onto a quote card (or a multi-selected set) to assign that tag. Natural extension of 6c. Atlas.ti and NVivo both support this. Defer to a later iteration — the click-to-assign from 6c covers the same use case with less implementation complexity.

### Decision 7: Success animation — reuse badge-accept-flash everywhere

**Decision:** The success blink animation currently used for accepting proposed (tentative) badges should play on **every** tag assignment action:
- `[+]` → type → Enter/Tab (existing TagInput flow)
- Double-`t` quick-repeat
- Sidebar click-to-assign (6c)
- Future: drag-and-drop (6d)

This gives consistent visual confirmation that "yes, the tag was applied" regardless of the assignment method.

---

## Part 6: Implementation roadmap

_Multi-stage implementation plan. Each stage is independently shippable._

### Stage 1: Structured autocomplete with group headers ✅

_Completed 10 Mar 2026 — commits `fbba431`, `c27351a`, `9e21266`._

**What:** Upgrade TagInput from flat vocabulary to grouped suggestions with section headers, tag colours, and proper selection highlighting.

**Changes (as designed):**
- **TagInput props**: Added `groupedVocabulary: TagVocabularyGroup[]` where `TagVocabularyGroup = { groupName: string; colourSet: string; tags: { name: string; colourIndex: number }[] }`. Kept `vocabulary` as backward-compat flat list (flat → single unnamed group)
- **Filtering**: Tags filtered within each group. Group-name matching shows all its tags. Individual tag matches show under their group header. Groups with zero matches hidden
- **Rendering**: Group headers as non-selectable section dividers (`.tag-suggest-header`). Tags rendered as coloured pills (`.tag-suggest-pill`) using `getTagBg(colourSet, colourIndex)`. Group headers use sentence-case, matching sidebar typography
- **Selection highlight**: Active tag row gets `background: var(--bn-colour-quote-bg)`. Active pill gets `outline: 2px solid var(--bn-colour-accent)` with `outline-offset: 1px`. Dark mode: white bold text on active pill only (not all pills — QA fix)
- **Arrow key navigation**: `selectableIndices` array maps only tag rows. ArrowUp/ArrowDown skip group headers. Only tags receive focus
- **Data plumbing**: QuoteCard → QuoteGroup → QuoteSections/QuoteThemes pass `groupedVocabulary` built from codebook API response

**Implementation notes (deviations from original design):**
- `TagVocabularyGroup.tags` carries `{ name, colourIndex }` (not just `string[]`) — needed for per-tag colour lookup via `getTagBg()`
- Selection highlight uses `outline` on the pill (not `color-mix()` background) — simpler, works across all group colours without per-colour calculation
- `maxSuggestions` default raised from 8 to 12 — 158 codebook tags + user tags, worst-case single-letter query ("s") returns ~18 matches
- Dropdown CSS `max-height: min(24rem, 50dvh)` — caps at 384px or half the dynamic viewport, whichever is smaller. Prevents dropdown overflowing near the bottom of the page
- Z-index fix: `.quote-card:has(.tag-suggest) { z-index: 10; }` elevates the card containing an open dropdown above siblings
- **resolveValue() priority fix** (`9e21266`): `selectedTagName` (arrow-key highlighted suggestion) now wins over `ghostText`. Previously, ghost text had priority, so arrowing to a different suggestion and pressing Enter committed the ghost-text completion instead of the highlighted tag
- Internal `SuggestRow` discriminated union: `{ type: "header" | "tag"; groupName; colourSet; tagName?; colourIndex? }` — single flat array drives rendering while separating selectable from non-selectable rows

**Files touched:**
- `frontend/src/components/TagInput.tsx` — major refactor (grouped vocabulary, SuggestRow, selectableIndices, resolveValue fix)
- `frontend/src/components/TagInput.test.tsx` — 40 tests (26 original + 14 for grouped features)
- `frontend/src/islands/QuoteCard.tsx` — pass `groupedVocabulary`
- `frontend/src/islands/QuoteGroup.tsx` — build `groupedVocabulary` from codebook data
- `frontend/src/pages/QuoteSectionsTab.tsx` / `QuoteThemesTab.tsx` — thread `groupedVocabulary` through
- `bristlenose/theme/molecules/tag-input.css` — group headers, pills, dark mode active state, z-index fix, dropdown depth

**Actual effort:** 2 sessions (implementation + QA polish + bug fix)

### Stage 2: `r` key quick-repeat ✅

_Completed 10 Mar 2026._

**What:** Press `r` to apply the last-used tag to focused/selected quotes. Originally designed as double-tap `t`, but that conflicted with TagInput (first `t` opens picker, second types `t` into it). Changed to dedicated `r` key.

**Changes (as implemented):**
- **Last-used tag tracking**: `lastUsedTag: TagResponse | null` module-level variable in `QuotesContext.tsx`. Set automatically by `addTag()` (full `TagResponse` with colour metadata). Cleared by `resetStore()`. Exported via `getLastUsedTag()`
- **`useKeyboardShortcuts`**: `r` keydown calls `handleQuickApply()` — reads `getLastUsedTag()`, calls `addTag()` for each target (selected quotes or focused quote), triggers flash animation via `flashTag()` FocusContext registry. No-op if no last tag exists
- **Flash animation**: `flashTag` registry in `FocusContext` (same pattern as `openTagInput`/`hideQuote`). QuoteGroup registers per-quote handlers that set `flashingTags` state. Also added flash to `handleTagAdd` (all manual tag adds flash, not just proposed accepts — Decision 7)
- **Bulk support**: Selected quotes all get the tag. Falls back to focused quote if no selection
- **HelpModal**: `r` → "Repeat last tag"

**Files touched:**
- `frontend/src/hooks/useKeyboardShortcuts.ts` — `r` key handler, `handleQuickApply()` callback
- `frontend/src/contexts/QuotesContext.tsx` — `lastUsedTag`, `getLastUsedTag()`, auto-set in `addTag()`, clear in `resetStore()`
- `frontend/src/contexts/FocusContext.tsx` — `flashTag`/`registerFlashTag`/`unregisterFlashTag` registry
- `frontend/src/islands/QuoteGroup.tsx` — flash-tag handler registration, flash on all tag adds
- `frontend/src/components/HelpModal.tsx` — `r` shortcut entry
- `frontend/src/hooks/useKeyboardShortcuts.test.ts` — 6 tests (apply, bulk, no-op, store tracking)
- `frontend/src/components/HelpModal.test.tsx` — updated assertion

**Actual effort:** Half session

### Stage 3: Sidebar tag interactions (filter + assign)

**What:** Three new click behaviours in the Tag Sidebar.

**3a — "Show only" via count/bar click:**
- Click a tag's count number or micro-bar → uncheck all other tags, show only quotes with that tag
- Click again → restore previous tick state
- Clicking a _different_ count/bar → switch to that tag's "show only" (previous state lost)
- Store the "previous tick state" in SidebarStore for undo

**3b — "No tags" filter:**
- Add a "No tags" row at the top of the Tag Sidebar
- Tick/untick to show/hide quotes that have zero tags
- Default: checked (untagged quotes visible)

**3c — Click tag name to assign:**
- When quotes are focused/selected, clicking a tag _name_ (not count, not tick) in the sidebar assigns that tag to the focused/selected quotes
- Play the success blink animation
- Quotes stay selected (user can click multiple tags)
- When no quotes are focused/selected, clicking a tag name does nothing (or could navigate to that tag in the codebook — TBD)

**Files touched:**
- `frontend/src/components/TagSidebar.tsx` — new click handlers on count/bar, tag name
- `frontend/src/components/TagRow.tsx` — click zones (name vs count vs tick)
- `frontend/src/components/TagGroupCard.tsx` — pass through click handlers
- `frontend/src/contexts/SidebarStore.ts` — "show only" state, previous tick state for undo, "no tags" filter
- `frontend/src/contexts/QuotesContext.tsx` — tag mutation API calls from sidebar
- `frontend/src/contexts/FocusContext.tsx` — read focused/selected IDs for sidebar-assign

**Estimated effort:** Large (1–2 sessions)

### Stage 4: Success animation unification

**What:** Ensure the badge-accept-flash animation plays consistently on all tag assignment paths.

**Changes:**
- Audit all tag assignment paths: `[+]` TagInput commit, double-`t` quick-repeat, sidebar click-to-assign
- The flash animation currently lives on proposed badge accept. Extract it into a reusable utility (e.g., `flashBadge(quoteId, tagName)`) that works for any badge, not just proposed ones
- Ensure the animation fires after successful API response (not optimistically)

**Files touched:**
- `frontend/src/islands/QuoteCard.tsx` — flash trigger points
- CSS: extract `badge-accept-flash` into shared utility if needed

**Estimated effort:** Small (< half session)

### Future stages (not in scope)

- **Fuzzy matching** — Levenshtein or bigram scoring for typo tolerance. Only valuable when codebooks grow beyond ~50 tags
- **Recently-used ranking** — track tag usage frequency, float most-used to top of suggestions
- **Drag-and-drop tag → quote** — drag from sidebar onto quote card(s). Deferred until click-to-assign (Stage 3c) is validated
- **Tag definitions tooltip** — hover over a suggestion to see `apply_when` text. Deferred (Decision 5)
- **Sidebar undo history stack** — multi-step undo for filter state changes. Make a TODO item

---

## Part 7: Competitive comparison matrix

| Feature | Bristlenose (current) | Dovetail | Marvin | Atlas.ti | NVivo |
|---------|----------------------|----------|--------|----------|-------|
| **Tag picker trigger** | Click `+` badge | Selection action menu | `#` trigger char | `Ctrl+J` dialog | Quick Coding Bar / right-click |
| **Autocomplete** | Prefix + contains match, ghost text | Type-to-filter | `#` → autocomplete | Type-ahead in dialog | Type-to-filter in bar |
| **Fuzzy matching** | No (contains only) | Unknown | Unknown | No (prefix) | No (prefix) |
| **Ghost text** | Yes (best prefix match suffix) | No | No | No | No |
| **Quick-repeat** | `r` (last tag) | No | No | `Ctrl+L` (last code) | No |
| **Group context in picker** | Yes (section headers + coloured pills) | Group colours | Hierarchy visible | Flat list | Node tree |
| **Inline creation** | Yes (type + Enter) | Yes | Yes | Yes (`+` in dialog) | Yes |
| **"Create X" label** | No | Yes | Unknown | No | Unknown |
| **AI-suggested tags** | AutoCode → tentative badges | Magic Highlights (auto-apply) | Auto-apply during transcription | AI Coding (v24+) | AI coding suggestions (v15+) |
| **Tag definitions visible** | No (only in codebook) | On tag board | On hover | Comment field | Node description |
| **Multi-select** | No (Tab-reopen for rapid entry) | Yes (multi-tag per highlight) | Unknown | One code per dialog invocation | One node per action |
| **Keyboard shortcut** | `t` (add tag), `r` (repeat) | Tab on selection menu | `#` in live notes | `Ctrl+J` / `Ctrl+L` / `Ctrl+Shift+V` | None documented |
| **Provenance distinction** | Group colours only | Group colours | Purple (template) vs pink (project) | Code comments | Node tree position |

---

## Part 8: Recommended reading and references

### IDE autocomplete
- [VS Code IntelliSense docs](https://code.visualstudio.com/docs/editor/intellisense)
- [JetBrains IntelliJ code completion](https://www.jetbrains.com/help/idea/auto-completing-code.html)
- [GitHub Copilot inline suggestions in VS Code](https://code.visualstudio.com/docs/copilot/ai-powered-suggestions)
- [GitHub Copilot code suggestions (concepts)](https://docs.github.com/en/copilot/concepts/completions/code-suggestions)

### Qualitative research tools
- [Dovetail: Highlights and tags](https://dovetail.com/help/highlight-and-tag-project-content/)
- [Dovetail: Speed up your tag game](https://dovetail.com/blog/three-features-quick-accurate-tagging/)
- [Dovetail: Auto-tagging for Magic Highlights](https://champions.dovetail.com/x/announcements/jwxkp3s9sc7z/introducing-auto-tagging-for-magic-highlights-in-d)
- [HeyMarvin: How tagging expedites qualitative analysis](https://help.heymarvin.com/en/articles/10130442-how-tagging-expedites-qualitative-analysis-in-marvin)
- [HeyMarvin: Automated tagging and notes](https://heymarvin.com/product/automated-tagging-and-notes)
- [Atlas.ti 24: Creating and applying codes](https://manuals.atlasti.com/Win/en/quicktour/Codes/CodingData.html)
- [Atlas.ti vs NVivo vs Delve comparison](https://delvetool.com/blog/atlasti-vs-nvivo-vs-delve)
- [Qualitative analysis tools comparison 2026](https://skimle.com/blog/qualitative-data-analysis-tools-complete-comparison)

### Productivity patterns
- [Slack: Rebuilding the emoji picker in React](https://slack.engineering/rebuilding-slacks-emoji-picker-in-react/)
- [Notion: Using slash commands](https://www.notion.com/help/guides/using-slash-commands)
- [Algolia: Slack-like autocomplete pattern](https://www.algolia.com/developers/code-exchange/slack-like-autocomplete-for-emojis-and-slash-commands)
- [UX Patterns: Autocomplete](https://uxpatterns.dev/patterns/forms/autocomplete)

### Bristlenose internal context
- `docs/codebook futures/bristlenose-codebook-strategy-and-design.md` — codebook strategy, layer 4 custom tags ("frictionless creation"), Dovetail critique
- `docs/design-codebook-island.md` — TagInput decision (no autocomplete on codebook page, yes on quote page)
- `docs/mockups/codebook-audit.html` — TagInput feature comparison table
- `docs/design-transcript-editing.md` — Dovetail prior art (transcript editing, not tagging, but UX patterns overlap)
- `frontend/src/components/TagInput.tsx` — current implementation (prefix + contains match, ghost text, grouped vocabulary with section headers, 12 max suggestions, keyboard navigation with header skipping)
