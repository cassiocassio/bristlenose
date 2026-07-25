# Export HTML doesn't hide badges you hid in-app

**Status:** issue captured, **unbuilt**. For a future export-work session. Surfaced
by the codebook enable/disable review (25 Jul 2026). Related:
[design-export-html.md](design-export-html.md),
[design-codebook-library.md](design-codebook-library.md) (Decision A + Outstanding
call 1).

## One-line

You hide a codebook group (eye toggle) or disable a whole framework (the codebook
switch) to keep its badges out of the report — then **Export HTML**, and every one
of those badges is back in the file you share.

## Product principle — the export is the researcher's deliverable (settled 25 Jul 2026)

The framing that decides this fix: **an exported report is not "all of Bristlenose
baked into a page." It is what the researcher decided the recipient should
receive — their curated deliverable.** The visible + starred quotes are the
researcher's *final judgement calls*; the things they hid, they hid for a reason
(evidence they judged not relevant). The export should present that judgement, not
the raw working state.

Corollaries:
- **The default view must honour the researcher's curation.** Hidden quotes stay
  hidden, hidden/disabled badges stay hidden. The current bug (badges reappear)
  violates this — the recipient sees material the researcher deliberately removed.
- **Recoverable-if-you-dig is fine, and even nice.** A recipient would be *happy* to
  be able to un-hide a quote to see what was set aside — but *unsurprised* if it were
  simply gone. So the underlying data being present-but-hidden (like `is_hidden`
  already is) is acceptable; we don't need aggressive stripping.
- **Re-curation is an app activity, not an export activity.** "If you want to carry
  on editing, you install the app." The exported HTML is a read deliverable; it is
  not meant to be a surface for re-doing the researcher's decisions.

This is why the fix is **parity, not stripping** (Option A below): match how hidden
*quotes* already behave — curated by default, recoverable by a curious reader — and
don't build a heavier sanitation pass the researcher didn't ask for.

## Symptom / repro

1. `bristlenose serve --dev <project>`; open the report.
2. On the Quotes tab, eye-toggle a tag group off (its badges vanish from quote
   cards). **Or** on the Codebook tab, switch a framework off (Decision A: folds
   the section *and* hides its badges report-wide).
3. Toolbar → **Export HTML**.
4. Open the exported `.html`. **The hidden/disabled badges are all rendered.** The
   deliverable does not match what you were looking at.

Both toggles leak. (The framework switch is the newer of the two; the eye toggle
has had the identical gap since it shipped — see Scope.)

## Root cause — a data-flow asymmetry

Badge hiding is a **client-side render filter**, and the two toggles' state lives in
**separate API endpoints that the export never embeds**.

- **Quote-level state round-trips.** `is_hidden` / `is_starred` are baked **into the
  per-quote payload** (`QuoteResponse.is_hidden`, `frontend/src/utils/types.ts:51`
  and `:128`). The export embeds `quotes` wholesale
  (`bristlenose/server/routes/export.py:418`), so `QuotesContext` reads the flag
  directly and hides the quote (`.bn-hidden`). Hidden **quotes** therefore survive
  export correctly.

- **Group / framework view-state does NOT round-trip.** It's fetched from two
  dedicated endpoints and filtered in `QuoteGroup`:
  - eye toggle → `GET /hidden-tag-groups` → `SidebarStore.hiddenTagGroups`
  - framework disable → `GET /framework-states` → `SidebarStore.disabledFrameworks`
    (via `hydrateFrameworkStates`)
  - `QuoteGroup.effectiveHiddenGroups = hiddenTagGroups ∪ {groups whose framework is
    disabled}` drives the badge filter (`frontend/src/islands/QuoteGroup.tsx`).

  The export payload (`export.py:411-430`, `export_data = {...}`) embeds
  `version, exported_at, project, health, dashboard, sessions, quotes, codebook,
  analysis, transcripts, people, videoMap, logos` — **neither `hidden-tag-groups`
  nor `framework-states`.** And `resolveFromExport` (`frontend/src/utils/
  exportData.ts:70-97`) has **no case** for either path.

So in the exported file: `getFrameworkStates()`/`getHiddenTagGroups()` →
`resolveFromExport(...)` returns `null` → falls through to `fetch(apiBase()...)` →
no server → rejects → the hydration `.catch(() => {})` swallows it →
`disabledFrameworks` and `hiddenTagGroups` stay **empty** →
`effectiveHiddenGroups` collapses to `∅` → **the badge filter passes everything.**

```
serve mode:  toggle → SidebarStore set → PUT persists ─┐
                                                        ├─ GET on next load → filter applies ✓
export mode: (no server) → GET fails → set stays empty ─┘ → filter is a no-op ✗
             but the per-quote is_hidden flag IS embedded → hidden quotes still hide ✓
```

The tell that it's not a codec/anonymise issue: hidden **quotes** hide correctly in
the same file, because their flag travels *in the quote*, not in a side endpoint.

## Scope — fix both toggles together

This is **one bug with two entry points**. `hidden-tag-groups` (eye toggle) and
`framework-states` (disable switch) both fail the same way for the same reason. Fix
them in one pass or the deliverable stays half-right.

## The fork: parity vs sanitation

The export already has a *sanitation* pass — `_anonymise_data` (`export.py:33`,
opt-in via the `anonymise` query param) strips participant names. That raises the
real question for this fix:

### Option A — Parity (recommended default)

Embed the two view-state blobs so the exported client filters **identically to
serve mode**.

- `export.py`: add `"hidden_tag_groups": _to_dict(...)` and `"framework_states":
  _to_dict(...)` to `export_data` (call the same handlers the endpoints use, like
  `quotes`/`codebook` already do at `export.py:362-363`).
- `exportData.ts`: add `if (path === "/hidden-tag-groups") return
  data.hidden_tag_groups` and `if (path === "/framework-states") return
  data.framework_states` to `resolveFromExport`; add the fields to the `ExportData`
  interface.
- No frontend logic change — `getHiddenTagGroups`/`getFrameworkStates` resolve from
  the embedded blob exactly as `getCodebook` does today.

**Why this is the consistent default:** it mirrors how `is_hidden` already behaves —
state embedded, client hides, **the underlying data is still present in the JSON**
(a hidden quote's text is likewise still in the embedded `quotes`). Minimal, matches
precedent, no new privacy posture. Ships the "what you see is what you share" fix
without pretending the hidden tags are *gone*.

### Option B — Sanitation (strip at export time)

Filter the hidden tags **out of the embedded `quotes` payload server-side** (drop
tags whose group is eye-hidden or whose framework is disabled before embedding), so
they're absent from the file's JSON entirely — `view-source` can't recover them.

- Heavier: `export.py` must join the two state tables and prune each quote's tags.
- **Inconsistent with hidden quotes**, which are *not* stripped today (their text
  stays in the JSON, only `.bn-hidden`-suppressed). Choosing B for badges but not
  for quotes would be a split personality.
- Arguably the right long-term posture for a *shared deliverable* (you disabled a
  framework because it's noisy or sensitive; you may not want its tags readable in
  the file at all) — but that's really a **broader "export sanitation" feature**
  that should also cover hidden quotes, and probably belongs under the `anonymise`
  opt-in umbrella rather than being silently always-on.

**Recommendation:** ship **A** — it *is* the settled direction, per the Product
principle above. Parity honours the researcher's curation by default while keeping
hidden content recoverable, exactly like `is_hidden` quotes. Option B (stripping) is
**not** wanted now: the researcher hasn't asked to redact hidden evidence from the
file, and doing it for badges but not quotes would be inconsistent. If a cohort
researcher ever explicitly wants hidden content *gone* from shared files, that's a
deliberate, opt-in "sanitise on export" feature spanning **both** hidden quotes and
hidden badges (probably under the `anonymise` umbrella) — not this fix.

## Touchpoints (for whoever picks this up)

| File | Change (Option A) |
|---|---|
| `bristlenose/server/routes/export.py` | `export_data`: add `hidden_tag_groups` + `framework_states` (reuse the `get_hidden_tag_groups` / `get_framework_states` handlers, mirroring the `quotes`/`codebook` calls). Confirm `_anonymise_data` / `_strip_filesystem_paths` don't need to touch them (they don't — no names/paths). |
| `frontend/src/utils/exportData.ts` | `ExportData` interface: `hidden_tag_groups: string[]`, `framework_states: Record<string, boolean>`. `resolveFromExport`: two exact-match cases. |
| tests | Export-payload test (`tests/test_serve_export*.py` or wherever the payload shape is asserted): the two keys are present. A frontend test that in export mode a disabled framework's badges don't render (mirror an existing export-mode QuoteGroup test if one exists). |

## Gotchas for the fix

- **`framework-states` is a `Record<string, boolean>` (absence = enabled), not a
  list** — don't model it like `hidden-tag-groups` (`string[]`). See
  `SidebarStore.hydrateFrameworkStates` for the "keep the `enabled === false` ones"
  shape.
- **`hydrateFrameworkStates` is fetch-once-guarded and swallows errors.** In export
  mode with Option A the GET resolves from the embedded blob (no fetch, no error),
  so hydration succeeds. Verify the guard doesn't interfere (it won't — it only
  blocks a *second* hydrate).
- **Don't regress the anonymise path.** Neither blob carries participant names, so
  `_anonymise_data` needs no change — but add a line to its docstring noting it
  intentionally leaves view-state untouched, so a later reader doesn't "fix" it.
