---
status: decided
decided: 2026-08-01
implementation: pending
---

# Show, not Reveal — the Finder verb

_Panel review 1 Aug 2026 (`what-would-gruber-say` + `user-documentation-review` +
`i18n-review`). Decision recorded; no code changed yet. This doc exists because
the evidence behind the call was expensive to gather — disk scans of Apple's
shipped `.strings`/`.loctable` files and a 20-locale measurement — and nobody
should have to re-derive it to re-open the question._

---

## Decision

**One verb: "Show".** For handing an object to Finder, for naming a secondary
object, and (pending one open call, §4) for in-app navigation.

This finishes a call already made once. [`design-desktop-menu-actions.md:147`](design-desktop-menu-actions.md)
carries the note _"Doc previously named this `revealInFinder`"_ — April 2026.
Three surfaces followed it; two didn't.

---

## 1. What Apple ships

Scanned on macOS 26.4.1: `/System/Applications`, `/System/Library/CoreServices`,
Safari's private framework, Xcode, and installed reference apps.

**"Show in Finder"** — Finder itself (`LocalizableMerged.strings` keys `A34`,
`N207`), Music (`SHOW_IN_FINDER_MENU_ITEM`), TV, Photos
(`IPXMenuItemShowInFinder`), Safari (three keys incl. the downloads button),
Notes, Mail Preferences, Font Book (`mainMenu-showInFinder`), Automator, Disk
Utility, Photo Booth, Dock, screencaptureui, the Gatekeeper quarantine dialog,
Xcode (IDEKit).

**"Reveal in Finder"** survivors, all non-menu-bar or fossils: Console's main
menu, Script Editor's document-window button, Photos' export-completion panel,
Font Book's duplicates sheet, Notification Center, Archive Utility settings, and
`Xcode.IDEKit.Snapshots.RevealInFinder` — Snapshots being a feature Apple
removed years ago.

### The rename is visible in the keys

Three independent codebases show the same migration, old word left in the
identifier:

| File | Key | Shipped string |
|---|---|---|
| `Finder.app/…/ServicesMenu.strings` | `Finder/Reveal` | **Show in Finder** |
| `Photos.app/…/IPXMain.loctable` | `IPXReferencedFileRevealInFinderMenuTitle` | **Show Referenced File in Finder** |
| `BBEdit.app/…/ContextualMenuCommands.strings` | `REVEAL_IN_FINDER` | **Show in Finder** |

Apple renamed it. Bare Bones renamed it. Both kept the key.

### The API's word does not bind the menu's word

Finder's only remaining "reveal" strings are its scripting and Intents
vocabulary — `Reveal Items`, `Reveal ${targets}`, `Items to reveal`, `Always
reveal in a new Finder window`. Its Services menu says "Show in Finder". Same
bundle, two registers: **reveal** for automation, **Show** for humans.

So `NSWorkspace.activateFileViewerSelecting` naming itself "reveal" is not an
argument for the menu item's label.

---

## 2. The distinction does not survive translation

Two independent measurements.

**Inside Bristlenose** — `sessions.showInFinder` (EN "Show") vs
`export.clips.revealMac` (EN "Reveal"):

- **15 of 20 locales byte-identical** (cs, da, es, fi, it, ja, ko, nb, nl, pl,
  pt-PT, ru, sv, uk, zh-Hant)
- **tr** differs only by apostrophe codepoint (U+2019 vs U+0027) — semantically
  identical, separately a defect
- **4 genuinely distinct**: en, de, fr, pt-BR

All three non-English distinctions are errors, not linguistic facts:

| Locale | Ships | Apple ships | Diagnosis |
|---|---|---|---|
| fr | `Révéler dans le Finder` | `Afficher dans le Finder` | "révéler" appears in **zero** Apple groups — machine artefact |
| pt-BR | `Revelar no Finder` | `Mostrar no Finder` | machine artefact (pt-PT already collapsed correctly) |
| de | `Im Finder anzeigen` | `Im Finder zeigen` | Apple's **folder** verb bleeding into the **Finder** string — Apple does split verbs, but by object (`Im Finder zeigen` / `Im Ordner anzeigen`), not by English verb |

**Inside Apple** — Apple ships English "Reveal in Finder" in five real groups
(Console title + tooltip, three `iLifeMediaBrowser` plugins). In **every one of
the 18 comparable languages the target string is character-for-character
identical to their translation of "Show in Finder"**. Example, group 79070
(`Console.app`), source `Reveal in Finder`:

```
cs 'Zobrazit ve Finderu'   de 'Im Finder zeigen'    fr 'Afficher dans le Finder'
ja 'Finderに表示'           ko 'Finder에서 보기'      tr 'Finder’da Göster'
```

Apple's localisers reached this conclusion and normalised on the Show-form in
all 20 target languages.

### Cost asymmetry

| Direction | Edits | Effect |
|---|---|---|
| Unify on **Show** | ~10 string edits | 16/20 locales already say it; de/fr/pt-BR move **toward** Apple |
| Unify on **Reveal** | ~57 edits | lands in the same place for 16 locales; moves 3 **away** from Apple |

---

## 3. The object doesn't change the verb — but it earns being named

The two "different" surfaces make the identical call:

- [`MenuCommands.swift:678`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift) — `selectFile(nil, inFileViewerRootedAtPath: path)`
- [`ContentView.swift:2689`](../desktop/Bristlenose/Bristlenose/ContentView.swift) (`revealTranscripts()`) — same call

Both open a folder and select nothing. There is no behavioural distinction to
encode in a verb. Nor is the folder-vs-file distinction felt: Music's "Show in
Finder" selects a track file, Automator's opens a folder — same words.

**Apple's actual rule: one verb, name the object only when ambiguous, leave the
primary object bare.** Photos ships both "Show in Finder" and "Show Referenced
File in Finder". Music ships "Show in Finder", "Show Album in Library", "Show
Artist in Library". Archive Utility names the object twice and keeps one verb.

So the adjacent pair in the Project menu is a feature, not a collision:

```
Show in Finder                 ⇧⌘R
Show Transcripts in Finder
```

Keep the `folder` / `doc.text` glyph split — it now reinforces the object
distinction instead of papering over a verb inconsistency. **The comment at
[`MenuCommands.swift:686-690`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift)
justifying the glyph split is the thing to fix** — it reasons from "two adjacent
reveals", a problem that only existed because the verbs differed.

[`TranscriptsRevealTarget.swift:3`](../desktop/Bristlenose/Bristlenose/TranscriptsRevealTarget.swift)
already reads `/// Which folder "Show Transcripts in Finder" should reveal.` The
helper is named for the label not yet adopted.

---

## 4. Per-surface punch list

| # | Site | Now | Change to |
|---|---|---|---|
| 1 | `sessions.showInFinder` — [`SessionsTable.tsx:221`](../frontend/src/islands/SessionsTable.tsx) | Show in Finder | — |
| 2 | `menu.project.showInFinder` — `MenuCommands.swift:676`, `ProjectSidebarOutline.swift:1605`, `ContentView.swift:2183` | Show in Finder | — |
| 3 | `menu.quotes.revealTranscripts` — `MenuCommands.swift:691`, `ContentView.swift:2655` | Reveal Transcripts in Finder | **Show Transcripts in Finder** (keep key, change value) |
| 4 | `export.clips.reveal` — [`AppLayout.tsx:581`](../frontend/src/layouts/AppLayout.tsx) | Show in folder | **open — see below** |
| 5 | `export.clips.revealMac` | Reveal in Finder | **delete** — 20 locales, zero call sites |
| 6 | [`UnsupportedSubsetView.swift:77`](../desktop/Bristlenose/Bristlenose/UnsupportedSubsetView.swift) | hardcoded `Text("Show in Finder")` | `i18n.t(…)` — right words, wrong mechanism |
| 7 | `menu.quotes.revealInTranscript` — `MenuCommands.swift:952` | Reveal in Transcript | **open — see below** |

**#5 is the elegant move.** `export.clips.revealMac` is the *sole* English home
of "Reveal in Finder" anywhere in the product, and the only reason de/fr/pt-BR
carry a second verb at all. Deleting it makes the question disappear rather than
answering it.

Capitalisation: lowercase `in`. Apple ships both forms; "Show in Finder"
dominates modern surfaces ("Show In Finder" survives in OBEXAgent, Certificate
Assistant, and Xcode's legacy key). Bristlenose is already correct.

### Open calls

**#4 — "Show in folder".** The reveal is decided **server-side**:
[`clips_export.py:496`](../bristlenose/server/routes/clips_export.py) branches
`open -R` on Darwin, `xdg-open` on Linux. This matters: a `dt()` / `isEmbedded()`
fork keys on the **client shell**, so a Mac user running `bristlenose serve` in
Safari would get Finder from the server but the neutral string from the label.
`revealMac` was keyed on the wrong axis and could never have worked.

The panel split on what follows. One reading: neutral prose is therefore correct
and plain `t()` is right, which is what shipped. The other: say "Show in Finder"
now and earn the Linux label later from a platform-reporting endpoint, rather
than hedging for a Linux-clip-export-then-reveal user who may not exist. Both
noted "Show in folder" is slightly untrue on macOS — `open -R` selects the first
clip *inside* the folder rather than opening the folder.

**#7 — "Reveal in Transcript".** The "Reveal in Library" precedent is out of
date: current Music ships `SHOW_ALBUM_IN_LIBRARY_MENU_ITEM` = "Show Album in
Library" and "Show Artist in Library"; its only remaining Reveal string is a bare
"Reveal" in `MusicStorageExtension.appex`. So Apple's in-app navigation verb is
**also** Show, and the Reveal-inside / Show-outside split isn't Apple's split.

The one real counter-voice is BBEdit, which keeps "Reveal Start / End /
Selection" for scroll-within-document while shipping "Show in Finder" for the
handoff — a coherent house style Bare Bones has earned. Nothing forces the call:
the two items are never adjacent (`revealInTranscript` renders in the **Quotes**
menu, `revealTranscripts` in **Project**, despite sharing the `menu.quotes.`
namespace).

**⇧⌘R — unresolved.** Could not be verified from disk: compiled nibs are
`NIBArchive`, not property lists, so key equivalents don't come out with
`plutil`, and Apple's shortcut support pages truncate on fetch. Recollection
(explicitly **not** asserted) is that Finder's Go menu takes ⇧⌘R for AirDrop and
Music takes it for Show in Finder. Thirty seconds in Finder ▸ Go and a
right-click in Music settles it. `⌃⌘R` at `MenuCommands.swift:184` is Run
Inspector — different modifier, different menu, no in-app collision. Nothing
argues for changing it today.

---

## 5. Constraint: never template the object

`Show {{object}} in Finder` is untemplatable, and the current fixed-string form
is right by design rather than luck. Two independent reasons:

**The object must decline.** cs `přepisy`, pl `transkrypcje`, ru `транскрипты`,
uk `транскрипти` are accusative plural; fi `litteroinnit` is nominative-plural
total object; tr `Dökümleri` carries accusative `-leri`. A caller passing a
nominative noun into a slot produces broken grammar in 6+ locales.

**Word order takes five distinct positions.** cs/pl/ru/uk/de put the object
*before* the Finder phrase; fr/it/es/pt/nl/da/sv/nb after the verb but before the
prepositional phrase; tr object-first verb-last (`Dökümleri Finder’da Göster`);
ja between (`Finder にトランスクリプトを表示`); zh-Hant last.

Finder's own case is safe — it's governed by the preposition (`ve` → cs locative
`Finderu`, `w` → pl `Finderze`, fi inessive `Finderissa`), not by anything
inserted. So naming an object doesn't break it. **If a third object ever needs
this, write a third fixed key.**

Related: `revealTranscripts` is correctly a fixed plural — no `{{count}}`, no
`_one`/`_other` in any locale. If it ever became count-bearing, note that
`pluralCategory` in [`I18n.swift`](../desktop/Bristlenose/Bristlenose/I18n.swift)
falls through to a `one`/`other` default that is **wrong for all four Slavic
locales**.

---

## 6. Verb-independent findings

Actionable regardless of where §4's open calls land.

- **[`UnsupportedSubsetView.swift`](../desktop/Bristlenose/Bristlenose/UnsupportedSubsetView.swift)
  has 4 hardcoded strings, not 1** — lines 20, 26, 32, 77. English in 19 locales,
  in a view that only renders when something already went wrong. The button needs
  **no new key**: `I18n.swift:43` lists `common` in its namespaces, so
  `i18n.t("common.sessions.showInFinder")` resolves today; `.environmentObject(i18n)`
  is already in scope at the instantiation site
  ([`ContentView.swift:2274`](../desktop/Bristlenose/Bristlenose/ContentView.swift)),
  so adding `@EnvironmentObject` needs zero call-site change. Lines 20/26/32 need
  three new `desktop.json` keys.
- **de `In Ordner anzeigen` is ungrammatical** — `in` + dative needs `im`. Apple
  ships `Im Ordner anzeigen`. `export.clips.reveal` is wrong in 5 of 20 (de, es,
  tr, uk, zh-Hant); correct values liftable verbatim from Apple's
  `DocumentManager.framework` group.
- **Three locales miss Apple on `showInFinder`** — es `Mostrar en Finder` →
  `Mostrar en el Finder` (Apple takes the article 8/8); ja `Finder に表示` →
  `Finderに表示` (ja is internally consistent about the space, so ask whether it's
  house style before a blanket change); zh-Hant `在 Finder 中顯示` → `顯示於Finder`.
- **Term drift found en route** — ko `전사` (common) vs `전사본` (desktop); tr
  `Deşifre` (common) vs `Döküm` (desktop, ×3 in menus). pt-BR/pt-PT use English
  title case (`Revelar Transcrições no Finder`) where Portuguese wants sentence
  case.
- **`glossary.csv` gaps** — no row for **Finder**, **Reveal**, **Folder**, or
  **Transcript**; **Show** covered for only 3 of 19 languages. Four of the defects
  above would have been prevented by a glossary row. Finder is the highest-value
  addition: some languages decline it (cs `Finderu`, pl `Finderze`, fi
  `Finderissa`, tr `Finder’da`), others keep it bare (ru, uk) — a translator
  currently has to guess.
- **⇧⌘R is undocumented** in the website's `docs-src/keyboard-shortcuts.md`,
  which *does* document `⌃⌘R` (Run Inspector). Two near-identical chords, the
  rarer one documented.
- **[`platform-text-map.md`](platform-text-map.md) undercounts forks** — its
  summary asserts `Forked | 4`; `sessions.showInFinder` / `sessions.copyFolderPath`
  at `SessionsTable.tsx:213-222` is a fifth. It also uses `isEmbedded()` rather
  than the documented `dt()`, which is arguably the *correct* signal here (the
  native bridge is what's actually present or absent) but is undocumented as a
  sanctioned mechanism.

---

## 7. What's in good shape

Worth recording so a future sweep doesn't "fix" it:

- **120/120 key parity** across all 20 full locales for the seven keys in this
  family. Zero missing, zero orphans.
- **17/20 exact matches** against Apple's shipped `showInFinder` — including
  **9/9 in the machine-seeded set** (pl, ru, uk, da, sv, nb, tr, nl, fi). Whoever
  seeded those did the Apple cross-check properly.
- **`zh-Hant-HK` correctly carries none of these keys**, inheriting `zh-Hant` per
  the override-fork rule. Adding an English placeholder would pin it and break the
  `zh-Hant-HK → zh-Hant → en` fallback. *Once `zh-Hant` is corrected*,
  `export.clips.reveal` becomes a legitimate HK override — the folder noun splits
  TW `檔案夾` / HK `資料夾`, exactly the `軟件`/`軟體` pattern.
- **`sessions.showInFinder` ≡ `menu.project.showInFinder`** byte-identical in
  20/20. Whichever verb wins, one is a free copy-paste for the other — no new
  machine translation needed in either direction (CLAUDE.md's twin rule).
- **Surface 1's embedded/browser fork** — a browser can't open Finder, so it
  copies the path instead. The appliance coping rather than offering a button that
  lies.
- **`TranscriptsRevealTarget.resolve`** fallback ladder (cooked → raw → output →
  project folder) prefers the most shareable artefact and can't no-op into
  silence.

---

## Method note — Apple's shipped translations are queryable

The Apple-HIG cross-check that `design-i18n.md` describes as a mandatory manual
step is scriptable. applelocalization.com has an undocumented JSON API:

```
https://applelocalization.com/api/macos/26/search?q=Show+in+Finder&b=
```

Returns `{data:[{source, target, language, file_name, bundle_name, group_id}], total, last_page}`
— i.e. Apple's shipped string per language per bundle. §2's measurements come
from it rather than from recall. Worth wiring into `design-i18n.md` §Step 2 as a
gate.

---

## Related

- [`design-desktop-menu-actions.md`](design-desktop-menu-actions.md) — action catalogue and wiring cookbook; §147 carries the April `revealInFinder` → `showInFinder` note
- [`glossary.md`](glossary.md) — Actions & UI table; now carries the Finder row
- [`design-i18n.md`](design-i18n.md) — Apple glossary cross-check procedure
- [`platform-text-map.md`](platform-text-map.md) — `dt()` / `ct()` fork inventory
