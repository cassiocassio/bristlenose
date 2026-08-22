---
status: proposed
last-trued: 2026-08-23
trued-against: HEAD@main (628d0b99) on 2026-08-23
---

# Export locale — one language per deliverable

**Status:** proposed, not built · 23 Aug 2026
**Supersedes nothing.** Extends the locale bake shipped 26 Jul 2026 (`30c5c2f7`,
`22980677`), described in [`design-export-html.md`](design-export-html.md).

An exported report is a document a researcher hands to someone. Documents have a
language. This proposes that the language is **chosen at the moment of export,
defaulted to the researcher's own**, and that the file then carries that language
and no other — which halves it, and is the smaller half of the argument.

---

## 1. What exists today

Measured 23 Aug 2026 against `HEAD@main`, not inferred from the config.

**The default is already right.** `30c5c2f7` (26 Jul) bakes the researcher's UI
language into the export as `BRISTLENOSE_EXPORT.locale`, and
`LocaleStore.detectLocale` reads it at **priority 0.5** — above `localStorage`,
above `navigator.language`. Before that bake, an English report opened on a French
Mac rendered French chrome, because an offline file has no server to inject a
locale and no prior `localStorage`. `22980677` fixed the follow-on: raw
`i18n.language` is `en-GB` for a researcher who never opened Settings, which is
not in `SUPPORTED_LOCALES`, so the bake was rejected and the bug reappeared for
the commonest case. Both are shipped and correct.

**So the report already opens in the language it was written in.** What follows is
not about the default. It is about what the file carries in order to honour it.

### 1.1 The bundle carries 22 locales × 9 namespaces

The export is a deliberate single-file build — `inlineDynamicImports: true`
([`vite.export.config.ts:31`](../frontend/vite.export.config.ts)) — because a
blob/data-URL module bootstrap does not work from an opaque `file://` origin.
That is load-bearing and stays.

The locale loader asks for three namespaces:

```js
const NAMESPACES = ["common", "settings", "enums"] as const;
const mod = await import(`../../../bristlenose/locales/${locale}/${ns}.json`);
```

Both `locale` and `ns` are variables, so Vite compiles the template literal into
a glob — `locales/*/*.json` — matching **all 192 files**. Inlining pulls every one
into the single chunk.

Verified by sampling real strings from each namespace against the built
`bristlenose/server/static-export/app.js` (2.26 MB). Every namespace is present,
in every locale:

| Namespace | Weight, all locales (minified) | Reachable from a browser report? |
|---|---:|---|
| `common` | 750 KB | yes |
| `desktop` | 739 KB | only if opened inside the Mac app |
| `settings` | 192 KB | yes |
| `preflight` | 75 KB | **no** — Whisper model download prompts |
| `cli` | 17 KB | **no** — command-line strings |
| `server` | 15 KB | **no** — HTTP error messages |
| `enums` | 6 KB | yes |
| `doctor` | 4 KB | **no** — dependency health checks |
| `pipeline` | 4 KB | **no** — and it has zero live consumers anywhere |
| **total** | **1,802 KB** | |

English alone is 74 KB. The other 21 locales are **1,727 KB**.

That is roughly **half of a 3.38 MB exported report**, and a slice of it is Czech
text for a `--whisper-model` flag, inside a file a researcher gives to a client.

### 1.2 Recipient language-switching is an accident, and a broken one

`SettingsModal` renders unconditionally ([`AppLayout.tsx:756`](../frontend/src/layouts/AppLayout.tsx)),
`export.css` hides 27 things and the language picker is not among them, and no
`isExportMode()` gate covers the locale store. So a recipient **can** switch the
chrome — in-session.

It does not survive a reload. Switching writes `localStorage`, which sits at
priority 1, *below* the baked locale at 0.5. Reopen the file and the researcher's
language wins again, silently discarding the reader's choice.

**This is worth stating plainly because it removes the only apparent cost of the
proposal.** Nothing here is a designed capability being traded for file size. It
is a control that half-works, and the proposal replaces it with one that works.

---

## 2. Proposal

**Choose the language at export. Default it to the researcher's own. Carry only
that language.**

Three changes, of which only the first is user-visible:

1. **A language line in the export control.** [`ExportDropdown.tsx`](../frontend/src/components/ExportDropdown.tsx)
   already asks a question at this moment — `All (n)` / `Selected (n)` /
   `Starred (n)`. Language is a sibling of that, not a new flow.
2. **Bake only the chosen locale's fallback chain**, instead of all 22.
3. **Narrow the export build's glob** to `{common,settings,enums}`, so the
   backend namespaces stop shipping regardless of locale count.

### 2.1 The default must be stated, not silent

Render it as `Language: English` — a **stated default the researcher can
change**, never a dropdown they must engage. This follows the house rule that a
governing control sits trailing on the pane's opening line.

Three things fall out, and the third is the one that justifies the affordance:

1. The 99% case costs zero thought.
2. The researcher discovers that multi-language deliverables are possible.
3. **It names the language they are about to hand to a client.** A researcher
   running the UI in Catalan today would otherwise ship a client-facing
   deliverable in a machine-seeded community preview whose native review is still
   owed, and never see it happen. A silent default hides that; a stated one does
   not. This is a disclosure property, not decoration.

### 2.2 Bake the chain, never the leaf

`fallbackLng: { "zh-Hant-HK": ["zh-Hant", "en"], default: ["en"] }`
([`i18n/index.ts:82`](../frontend/src/i18n/index.ts)).

`zh-Hant-HK` is **deliberately** a thin override fork carrying only genuine
HK-idiom differences; it inherits everything else. Baking it alone would render
raw keys — `codebook.frameworks` — in a client deliverable.

So "one locale" means:

| Chosen | Baked | Size |
|---|---|---|
| `en` | `en` | ~74 KB |
| `zh-Hant-HK` | `zh-Hant-HK` + `zh-Hant` + `en` | ~105 KB |
| everything else | *locale* + `en` | ~70 KB |

**English is baked under every locale, deliberately**, even where the locale is
complete. It costs ~35 KB and removes the failure mode where a future key gap
prints a raw key at a stakeholder. `check-locales.py` was warning-free when
measured on 21 Aug 2026; that is a measurement, not a guarantee, and the artefact
in question is one we cannot correct after it is sent.

### 2.3 Filenames carry the language

Three files in Downloads all named `Acme Research.html` is worse than the problem
being solved. Use `safe_filename()` — which preserves spaces and case for
readable Finder names, unlike `slugify()` — and append the language.

### 2.4 v1 is single-select

One language per export; a researcher wanting French, German and Italian for a
Swiss client runs it three times. Consistent with the scope chooser, which is
also single-select, and it defers a question that does not need answering yet:
what a three-language export *produces* — three saves, a folder, or a zip. Clip
export already had to settle that shape; no need to reopen it here.

---

## 3. Consequences

**Size.** ~3.38 MB → ~1.65 MB, roughly halved. This is the least interesting
reason to do it and should not be the one quoted in a changelog.

**A document gets a language.** The export is already read-only by decision —
controls hidden, not disabled. A read-only artefact whose chrome the *reader*
silently re-languages is an app property leaking into a document. Choosing at
export time is the same reasoning that made it read-only, applied one step
further.

**Growth slows but does not stop.** Every future locale still adds ~35 KB of
`common`+`settings` to *its own* exports, rather than ~80 KB to *every* export.
Adding the 23rd language stops being a tax on every report ever exported.

**The Perf gate.** Export HTML has exceeded its 3.2 MB fail threshold since
21 Aug 2026 (four consecutive red runs, non-blocking by design). Change 3 alone
lands it near 2.4 MB; the full proposal near 1.65 MB. **The threshold should not
be re-baselined to accommodate a defect** — see `docs/release-log.md`, 0.27.0.

**What is lost:** nothing that works. See §1.2.

---

## 4. Open questions

1. **Native or researcher's language in the filename?** `LOCALE_LABELS` holds
   native names, and the researcher picked "Deutsch" from that list — but they
   are the one filing the file. `Acme Research (Deutsch).html` or
   `(German).html`. Genuine coin-flip; decide deliberately rather than by
   whichever is easier to implement.
2. **Does the data/chrome boundary hold under a single locale?** A German export
   must translate chrome and leave participant-derived content alone — quote
   text, speaker names, LLM-generated theme names. `design-i18n.md` has the
   boundary; today's all-locales export would hide any place that gets it wrong,
   so this wants checking *before* baking one locale, not after.
3. **Is the picker for anyone, or only for the default?** If researchers almost
   never export in a language other than their own, the control is one nobody
   touches — and that is acceptable, because the default delivers both the size
   and the disclosure. Worth being clear-eyed that the Swiss-client case may be
   the justification rather than the usage; it does not change the design, only
   how much polish the multi-export path earns.

---

## 5. Related docs

- [`design-export-html.md`](design-export-html.md) — the export overall; §"What
  exists today" records the locale bake this extends
- [`design-i18n.md`](design-i18n.md) — the data/chrome boundary, the
  `zh-Hant-HK` fallback rationale
- [`release-log.md`](release-log.md) — 0.27.0 records the measurement that
  surfaced this
