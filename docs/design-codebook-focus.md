---
status: proposed
last-trued: 2026-09-12
trued-against: HEAD@main on 2026-09-12
---

# Codebook focus — a cursor for code groups and codes

**Status: proposed, 12 Sep 2026.** Not a decision. Supersedes the reasoning —
though not yet the code — behind four of the six Codes commands retired earlier
the same day.

Mockup: [`docs/mockups/codes-menu-focus.html`](mockups/codes-menu-focus.html).

---

## 1 — The claim this corrects

On 12 Sep 2026 six commands were removed from the desktop **Codes** menu. Four
of them — Rename/Delete Code Group, Rename/Delete Code — were removed on this
reasoning, quoted from the commit:

> The 29 Aug pin makes selection **single**, living **in the master list**, with
> the detail pane "a pure function of it"; the master list selects a *codebook*,
> so a command naming one group or one tag has no target the model permits.

**That is too strong.** The pin governs **selection** — which codebook the
detail pane renders. It does not forbid a **focus cursor** inside that pane, and
the app already ships exactly such a cursor in two places:

| | Where | State | Read by |
|---|---|---|---|
| **Quotes** | `frontend/src/contexts/FocusContext.tsx` | `focusedId` + a separate `selectedIds` | `QuoteCard`, the bridge's `focusedQuoteId` |
| **Analysis** | `frontend/src/contexts/AnalysisSignalStore.ts` | `focusedKey` | signal card (`bn-selected`), sidebar, inspector |

`FocusContext`'s own docstring draws the distinction in its first three lines —
*"Focus (keyboard cursor): at most one quote focused at a time"* against
*"Selection (multi-select): zero or more quotes selected for bulk actions"*. The
Quotes lens has carried both since the React migration and nobody has ever
called the focused quote a second selection.

So the honest statement is narrower: **the codebook lens has no focus model
yet.** That is a gap, not a prohibition.

**Two of the six stay retired, on arguments focus does not touch:**

- **`showHideCodeGroup`** — D7: hide and enable are different axes on different
  lenses; the eye lives in `TagSidebar` / `TagGroupCard` on **Quotes**, and hide
  *"was never a third axis here"*. **G7 and Q11 stay closed.**
- **`mergeCodes`** — merge needs a source *and* a destination. A focus cursor
  gives one. Drag-one-chip-onto-another is still the only gesture that names
  two.

## 2 — The proposal

Add a focus cursor to the codebook detail pane, modelled on
`AnalysisSignalStore` — a module-level store over `useSyncExternalStore`,
holding two nullable ids:

```ts
interface CodebookFocusState {
  focusedGroupId: number | null;
  focusedTagId: number | null;
}
```

One click on a group card's background focuses the group, the same gesture and
the same `bn-selected` wash as a signal card. One click on a chip focuses the
code. Click elsewhere or press Escape to clear. **Focus is a cursor, not a
mode:** every existing direct-manipulation affordance keeps working untouched,
and each menu command is defined as the twin of one of them.

| Menu item | Twin on the page | Target | Enabled when |
|---|---|---|---|
| New Code Group | the *New Group* button | none — creation | floor page open |
| New Code | a group's *+ Add code* row | focused group | floor + group focused |
| Rename Code Group | click the group title (`group-title-text`) | focused group | floor + group focused |
| Delete Code Group | the ✕ top-right (`group-close`) | focused group | floor + group focused |
| Rename Code | click the chip's name | focused code | floor + code focused |
| Delete Code | hover the chip, click ✕ | focused code | floor + code focused, **including while renaming** |
| Browse Codebooks | the *Browse Library* button | none — navigation | always, on the lens |
| Install ⇄ Uninstall Codebook | the page's own button | the open codebook | detail page open; not floor, not Sentiment |

Three structural facts the table leans on, all already in the code:

- **Authoring is floor-only.** `CodebookV2Page.tsx:326` gates group-growing on
  `book.floor`; a framework's structure is read-only. So every mutation dims on
  a framework page.
- **`createCodebookTag(name, groupId)` requires a group.** There is no
  uncategorised group to default into — the `uncategorised` bucket in the tree
  is quotes, not codebook tags. This is precisely why New Code needs focus, and
  why it could not have been wired before.
- **`canInstall` already excludes the floor and Sentiment** (D20), on both the
  browse card and the detail page. The menu mirrors that predicate rather than
  restating it.

**Install/Uninstall is one row whose verb swaps** — the same idiom as *Turn On /
Turn Off Agent Access* in the project sidebar (`design-mcp-extension.md` §3.6a),
not a checkmark. It replaces `importFramework` (which needed a `templateId` the
menu cannot name) and `removeFramework`.

## 3 — What it costs, and where

**The web half is small.** One ~40-line store, a click handler and a wash class
on `CodebookAuthoring`'s group card and chip, and handlers that call the
functions the buttons already call — `onCreateGroup`, `onRenameTag`,
`onDeleteTag`, `onDeleteGroup` are all live in `useCodebookAuthoring`.

**The native half is most of the work.** Dimming needs the Swift side to know
`focusedGroupId`, `focusedTagId`, and which codebook page is open. That is a new
bridge payload alongside `focusedQuoteId`, and per the house rule it is a
two-file change plus the fixture (`bristlenose/events.py` has no part in it, but
`shims/bridge.ts` and `BridgeHandler.swift` do, and a Swift-side test must
exercise the new fields or the round-trip proves nothing about them).

## 4 — Open decisions

**D-a. Delete Code takes no keyboard shortcut.** A SwiftUI `.keyboardShortcut`
installs an NSMenu key equivalent, matched **before** the responder chain — the
same mechanism that forces Edit ▸ Undo to *hide* itself while editing rather
than dim. A ⌫ on Delete Code would therefore steal the keystroke from the rename
field this proposal explicitly wants live, and ⌘⌫ is already spent twice in
Project. Recommendation: no shortcut on the six new/rename/delete rows;
`⇧⌘L` on Browse Codebooks, which is free.

**D-b. Focus lands on a framework's group, but the mutations dim.** A cursor is
useful for reading, and refusing focus there would mean one control with two
click behaviours depending on provenance. Dim, never hide.

**D-c. The 29 Aug pin needs amending if this lands.** Its wording — *"no second
place a thing can be 'current'"* — is what invited the over-reading, and it has
now done so once. The pin should say **selection** is single and name focus as a
separate axis, or a future session re-retires these commands on the same
misreading. This is the cheapest half of the whole proposal and the one most
likely to be skipped.

## 5 — Not in scope

Keyboard navigation between groups (j/k, arrows) is the obvious follow-on —
`spatialNav` already exists for the quote grid and the Sessions table — but
focus can ship click-only, exactly as signal cards did.
