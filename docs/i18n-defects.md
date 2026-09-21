# i18n defects — the running register

**What this is:** a place to drop an i18n defect the moment it is *noticed*,
so a nose-to-tail audit has a starting list instead of a blank page.

**What it is not:** `docs/i18n-reviews/` holds per-locale **wording** briefs for
native reviewers — "is this the right word in Czech". This file holds
**engineering** defects — a missing key, a hardcoded string, the wrong
namespace, a plural that will not inflect. Different question, different reader,
different fix.

**Why a file and not a test.** Most of these *cannot* fail a test today.
`scripts/check-locales.py` reports missing keys as warnings and CI runs it
non-strict, and `tests/test_pipeline_diagnostic_locale_keys.py` checks
hardcoded allow-lists rather than en→locale parity — so adding a key to `en`
never obliges anyone to extend anything. A green suite does not mean the locales
are complete, and that is exactly the gap this register covers.

**How to use it.** Add a row when you notice something, even mid-unrelated-work.
Do not fix it there and then unless it is free — the point is to stop losing
them. Strike the row when it lands, with the commit.

---

## The six ways a string goes wrong, and which one anything can see

The 21 Aug 2026 sweep found that most of what had accumulated was not one
problem but five, and that the tooling only ever looked for the first.

| # | Failure | What it looks like | What sees it |
|---|---|---|---|
| 1 | **Missing key** | key in `en`, absent from a locale | `check-locales.py` — as a **warning**, CI non-strict |
| 2 | **Surface absent from `en`** | a whole feature with no `i18n.t` call sites | **nothing** — with no `en` key there is nothing to be missing *from* |
| 3 | **Value drift** | `en` reworded; translations keep the old words | **nothing** finds it — but since 22 Aug a `_divergent_<key>` marker can record that a difference is *intended*, and `check-locales.py` errors when the marker goes stale |
| 4 | **Untranslated value** | a locale's value is byte-identical English | **nothing** — same reason |
| 5 | **Orphan key** | present in every locale, read by no call site | **nothing** — invisible from both directions |
| 6 | **Resolved once at construction** | key present, value correctly translated, `i18n.t` called — and it still renders in the wrong language, because the call happened once when an object was built rather than on each render | **nothing mechanical** — only a screenshot |

Gaps 3, 4 and 5 share one cause: **every gate we own asks "is the key there?",
and none asks "is the value right?" or "does anyone read it?"** Gap 6 is not in
that family at all and is worse: it answers *yes* to all three questions and is
still wrong, because the defect is **when** the call ran, not what it returned.
There is nothing for a key-set diff, a value diff or a call-site grep to find. Three throwaway
scripts found 3, 4 and 5 in one afternoon; none of them is in the repo, which is
the standing recommendation at the bottom of this file.

Detection recipes, if you need to re-run them:

- **Drift (3)** — for each key, compare the timestamp of the last commit that
  changed `en`'s value against the last commit that changed each locale's. If
  `en` is newer, the translation is a candidate. Walk `git log --format=%H %ct`
  per file and diff flattened blobs between consecutive commits.
- **Untranslated (4)** — flatten `en/<ns>.json` and each locale's, and report
  any value byte-identical to `en`. Discard the legitimately-invariant ones:
  shell commands, URLs, and strings that are pure `{placeholder}`.
- **Construction-time (6)** — brace-match every `lazy var` / `init` block in the
  app target and report any `i18n.t(` inside one. A string resolved there is
  outside the reactive graph and cannot re-render. Ran clean across
  `desktop/Bristlenose/Bristlenose/` on 21 Sep 2026 except the six it was written
  for. **Do not walk backwards from the call to the nearest declaration** — the
  first version did, broke on an intervening `let`, and reported zero on the very
  file it was written to catch.
- **Orphan (5)** — grep every `.tsx`/`.ts`/`.swift`/`.py` for the key, its
  namespace-qualified form, and every dotted prefix (to catch keys built at
  runtime). Match on the **fully-qualified** key, not the bare leaf: a leaf-name
  match finds doc comments and test fixtures and will tell you three dead keys
  are alive.

---

## The register

| # | Where | Defect | Noticed | Status |
|---|---|---|---|---|
| 1 | ~~`SettingsView.swift` — Accounts pane title~~ | ~~Hardcoded `"Accounts"`; the other five panes use `i18n.t("desktop.settingsTabs.*")` and no `settingsTabs.accounts` key exists. In every non-English build the Settings toolbar shows five translated labels and one English one. No already-translated twin to lift — needs a real translation × 21 locales.~~ | 18 Aug 2026, `/usual-suspects` | **struck — `d0478b15`**, 18 Aug 2026 |
| 2 | ~~`AccountsSettingsView.swift` — whole pane~~ | ~~Every user-facing string is English: state headlines, detail sentences, the disconnect alert, section footers.~~ **The stated rationale was false when written** — it cited §10 booking the cloud-import surface as realised debt, but that debt had been *paid* two days earlier (`49ec8a50`, 16 Aug), so the pane was not keeping company with an English neighbour; it was the only one left. Worth keeping visible: a "deliberate" status is only as good as the fact it rests on, and nothing re-checks that fact once the row is written. | 18 Aug 2026 | **struck — `d0478b15`**, 18 Aug 2026 (20 keys × 21 locales) |
| 3 | ~~`CloudImportWindow.swift` and the rest of the cloud-import surface~~ | ~~Hardcoded English throughout ("Import 1 Recording", "Filter", the plan-refusal sentences).~~ **This row was stale when it was last read.** Measured 21 Aug 2026: `CloudImportWindow` 38 `i18n.t` call sites and 0 literals, `CloudImportOutlineView` 34/0, `AccountsSettingsView` 18/0 — the surface was localised by `49ec8a50` (16 Aug), which item 2 already recorded and this row did not. The only remainder was `CloudImportWindowHost.swift`'s two state-restoration strings, which the pass missed because they live in the *host*, not the window. | recorded in `design-cloud-import.md` §10 | **struck — `cfcc2d67`**, 21 Aug 2026 — `cloudImport.restoredEmptyTitle` / `.restoredEmptyBody` × 21 |
| 4 | `tests/test_pipeline_diagnostic_locale_keys.py` | Looks like an en→locale parity gate and is not: it checks `_REQUIRED_PILL_CATEGORIES` / `_REQUIRED_HEADERS` / `_CHROME_COUNT_PREFIXES`, all hardcoded. A new `en` key never obliges anyone to extend them, so a gap ships silently. This is how `export.scope.*` sat in `en` alone and 19 `desktop.json` keys were missing from every non-en locale. | standing | open — by design, but see **Decision 2** below: `check-locales.py --strict` now costs nothing |
| 5 | `bristlenose/pipeline_view/cli.py` | Keeps its own English mirror of the pipeline reason/note strings (`_REASON_TEXT` / `_NOTE_TEXT`), keyed to the same locale keys. **Measured 21 Aug 2026: 3 of 23 diverge** — `mlx_whisper not installed` vs `MLX Whisper not installed`, `presidio_analyzer not installed` vs `Built-in anonymiser not installed`, `spaCy en_core_web_lg not installed` vs `language model not installed`. But look at *which* three: every one is a technical name in the CLI against a plain-English name in the SPA. That is not drift, it is a **register fork** — and if it is deliberate then the premise of this row ("keep both in sync") is wrong and no equality check should ever be written. Two corrections while here: the keys live in the **`settings`** namespace (`settings.pipeline.reasons.*`), not `pipeline.*` as this row and `CLAUDE.md` both said; and `_PROVIDER_DISPLAY` is built from the provider registry at import time, not hand-mirrored, so it cannot drift. | standing | **closed 21 Sep 2026 — see Decision 3.** The row's own last sentence called it: *"if it is deliberate then the premise of this row ('keep both in sync') is wrong and no equality check should ever be written."* It is deliberate. The terminal is English by design (`docs/design-i18n.md` §"Which surfaces are targets"), so the three divergences are a register fork — the terminal names the package, the SPA names the thing — and the mirror needs no gate. |
| 6 | `ProjectDiagnosticPopover.humanCategoryLabel` | English-only, and **a translation is the wrong fix**. It is the single source for two different readers: the category label rendered in the popover, and the English-only plaintext that `formatDiagnosticPlaintext` writes to the pasteboard for a bug report. Localising it in place would translate the copy payload too — which a maintainer then receives in Czech. Needs a **UI-vs-plaintext split**, not 21 translations of one function. **Scoped 21 Aug 2026:** 16 categories; `desktop.pipeline.diagnostic.pill.*` already covers 6 of them in all 21 locales, so the split needs ~10 more keys plus the `"Category: …"` prefix, which is itself a bare literal at `ProjectDiagnosticPopover.swift:108` sitting among seven `i18n.t` siblings. | cz i18n review Finding 13 (deferred); re-confirmed on screen 20 Aug 2026; scoped 21 Aug 2026 | open — see **Decision 4** |
| 7 | ~~`ProjectDiagnosticPopover` — bucket failure count~~ | ~~`Text("\(realFailures.count) failures")` — a bare Swift literal in a pane that is otherwise fully localised, and the wrong noun besides: a bucket of refusals is outcome 2, a pass.~~ Worth keeping visible next to item 6: **the same file held two instances of the same class**, one three lines from the other, and only one was on anyone's list. A register catches what someone noticed; it does not sweep. | 20 Aug 2026, from a screenshot of a real run | **struck — `04bf7a23`**, 20 Aug 2026 (`notAnalysedCount` / `failureCount` × 21) |
| 8 | ~~`en/common.json` — `codebook.foldedSummary_one` / `_other`~~ | ~~In `en` alone since `c0f4ec29` (26 Jul 2026) and absent from **all 21 full locales**, so the folded-codebook meta line renders English everywhere. This is 21 of the 22 warnings `check-locales.py` currently prints.~~ Seeded into 19 locales with CLDR forms matching each file's own shape (`_few`/`_many` for cs/pl/ru/uk, `_other` alone for ko/zh-Hant). The `·` separator was kept in every script — see **Question A**. | measured 20 Aug 2026 | **struck — `cfcc2d67`**, 21 Aug 2026 |
| 9 | ~~`it/server.json`, `zh-Hant/server.json` — `statusPage.*`~~ | ~~The whole 11-key block is missing from exactly these two locales; `en` and the other 19 all carry it in full. Whatever pass seeded the rest skipped two, and nothing since has noticed, because these are warnings and CI runs non-strict.~~ Seeded; `help` / `showDetails` / `sendFeedback` lifted verbatim from each locale's already-reviewed twins (`nav.help`, `boot.showDetails`, `menu.help.sendFeedback`) rather than re-translated. | measured 20 Aug 2026 | **struck — `cfcc2d67`**, 21 Aug 2026 |
| 10 | ~~`en/common.json` — the value-drift class~~ | **This row understated the problem by a factor of four.** It recorded five keys (`codebook.{heading,yourTags,builtIn,frameworks}`, `nav.codebook`) reworded by 0.26.0 and left untranslated. Running the drift detector over the whole history found **18**: the five sidebar keys, plus **thirteen** from the *earlier* Codebook Library rewrite (`7530106e`, 17 Jul; `e8745070`, 26 Jul) that nobody had noticed at all — Browse→Library, Import→**Install**, Remove/Hide→**Uninstall**, "AutoCode quotes"→**Apply**. The worst of them, `codebook.autoCodeQuotes`, labelled the same button **"Apply"** in English and **"✦ AutoCode citas"** in Spanish: not a wording nuance, two different actions. All 18 repaired against `ca`, which was seeded after both rewrites and was already correct — a useful accident, and the reason a newly-added locale is worth diffing against the old ones. | measured 20 Aug 2026; scope corrected 21 Aug 2026 | **struck — `cfcc2d67`**, 21 Aug 2026 (18 keys × 19 locales) |
| 11 | ~~`docs/platform-text-map.md`~~ | ~~The locale counts were trued 20 Aug (`7162eb54`); the **key** counts were not.~~ Regenerated 21 Aug 2026 from `bristlenose/locales/en/*.json`, which is what the doc's own note had been asking for. It had drifted further than the note claimed: `settings.json` was listed at ~20 keys and holds **179**; `common.json` at ~420 against **539**; the Desktop-only table named 8 of 22 sections and undercounted `chrome.*` by 92. Now the full inventory, with the totals stated as measured on a date. | 20 Aug 2026 | **struck**, 21 Aug 2026 (docs commit) |
| 12 | `WelcomeHomeView.swift` — the content pools | ~~Three call sites lost their `i18n.t` wrapper in the bento rewrite (`a310bca6`, 15 Jul 2026), which replaced them with the same English verbatim while `desktop.welcome.{dropFolderTitle,dropFolderHint,aiPrivacyLink}` stayed translated in all 21 locales — a five-week silent regression that no gate could report, because the keys were never missing.~~ **Restored 21 Aug 2026.** What remains is the harder half: `WelcomeContent`'s three rotator pools (`studyTools`, `science`, `tips`) are ~30 Swift string literals with no keys at all — failure class 2. That copy is actively moving (`docs/design-website-welcome-transfer.md`, `docs/mockups/website-bento-welcome.html`), so `feedback_hand_tune_copy_before_i18n` applies: settle the English first. `Text("Setup →")` is in the same pool. | 21 Aug 2026 | **partly struck — `cfcc2d67`** — 3 restored; the pools stay open, deliberately, pending settled copy |
| 13 | `AlphaExpiryFlow.swift`, `AlphaExpiryPill.swift`, `DoctorReportView.swift`, `MenuCommands.DiagnosticsMenuContent` | **English by decision, and the decision was re-verified 21 Aug 2026** rather than taken on trust — which is the correction item 2 asked for. Alpha expiry: "ephemeral alpha-only chrome", and `AlphaBuild.daysRemaining()` returns nil off the `.developerID` channel, so it genuinely cannot render anywhere else. Health: "matching the Diagnostics menu that opens it (and `doctor.py`, which is English-only in alpha)" — the Diagnostics menu **is** English-only by its own explicit note, and the checks it renders come from `doctor.py` as English payload. Both facts hold. Recorded here so the next sweep does not re-litigate them, and so that if either fact changes the row is the place it gets caught. | verified 21 Aug 2026; **reason upgraded 21 Sep 2026** | **closed — deliberate, and the reason is now durable.** The 21 Aug wording rested on *"a trim / reduce / possibly remove candidate — decide its fate first"*, which is a stage-shaped reason and would have expired the moment that decision landed. It has landed: **these surfaces are hidden on the App Store build and exposed during alpha / TestFlight only**, so they are never on the shipping consumer surface. That is a property of the surface, and it is now a row in `docs/design-i18n.md` §"Which surfaces are targets" rather than a carry in this register. |
| 14 | ~~The untranslated-value class (failure 4)~~ | Values sitting in locale files as raw English, invisible because the key is present. The substantial ones: `common.quotes.uncategorisedIntro_*` — a whole paragraph on the Quotes lens, English in **19 of 20** locales, with its own heading `uncategorisedHeading` ("Needs a home") English in 19 as well; `settings.appearance.animation{Legend,Help}` in **17**; the entire `preflight.*` surface in **de/es/fr/ja/ko** — 23 keys, the five *oldest* locales, which never received the wave that cs/it/nl/pl and the rest did, and which `bristlenose --lang=de run …` reaches today via `cli.py:_lang_callback`; and **ten** `desktop.pipeline.diagnostic.*` strings in `ja` alone, inside an otherwise-complete block. **The detector's own filter hid two of those.** The first pass skipped any value under three ≥2-letter words, to avoid drowning in product names — which made `"Needs a home"` invisible (`a` is one letter), and with it six of the ten ja strings. Caught only by reading a sample diff by eye and noticing an English heading above a paragraph the same sweep had just translated. Widening to *two words and eight characters* took the finding count 28 → 46 and the real defects 22 → 29; the extra 24 are all coincidental identity (`Local (Ollama)` in five Romance locales, `Heatmap (m)` in three Germanic ones, `in {{duration}}`, `Session {{id}}`). **The lesson is about noise budgets: a filter tuned to keep the output readable is a filter that decides what you never see.** | measured 21 Aug 2026 | **struck — `cfcc2d67`**, 21 Aug 2026 — 24 findings remain and are all coincidental identity or legitimately invariant (shell commands, URLs, one pure-placeholder string, loanwords, and `pictureInPicture` in it/pt-BR/pt-PT where Apple itself ships the English). **That last one now carries a `_divergent_` marker** rather than living in this sentence; the other 23 could take one too, which would make the untranslated-value sweep's output self-shrinking instead of needing the allow-list recommendation 3 warns about |
| 15 | ~~`desktop.llmSettings._comment_temperatureLabel`~~ | JSON has no comments, so the locale files carry notes as `_comment_*` pseudo-keys. This one — *"ja/ko keep English pending native-UX-friend review — see TODO.md"* — had been copied into **all 20 non-en locale files**, where a note about two languages sat inside the other eighteen. It could not be removed without the gate then demanding it back as a missing key. `check-locales.py` now drops `_comment_*` in `flatten()`, so the convention works as intended and the duplicates are gone. (The note's own referent is stale, incidentally: `TODO.md` no longer mentions temperature. Its substance still holds — ja/ko do keep `Temperature` in English.) | measured 21 Aug 2026 | **struck — `cfcc2d67`**, 21 Aug 2026 |
| 16 | `desktop.help.{privacy.redactionIntro, privacy.actionThreshold, contributing.beforeBody}` | **Failure class 5 — orphan keys.** `3f49d170` retired the SPA help modal and deleted `PrivacySection.tsx` / `ContributingSection.tsx`. The three `dt()` overrides they read stayed behind, in `en` and in all 20 locale `desktop.json` files, and nothing reported it: a key present on both sides and read by nobody is invisible to a key-set diff from either direction. `dt()` is now down to **one** live call site (`configReference.intro`). Note the sweep nearly missed these too — the bare leaf name `redactionIntro` still appears in `platformTranslation.ts`'s doc comment and its test fixture, so a leaf-match orphan check reports them as alive. | 21 Aug 2026 | open — see **Decision 5** |
| 17 | `desktop.menu.video.pictureInPicture` and the quote glyphs | Two terminology findings that are **reviewer questions, not engineering defects** — filed here only because the sweep surfaced them and `docs/i18n-reviews/` has no open brief. (a) Picture in Picture is a macOS *system feature*; seven locales named it something the user's own Mac does not, and were aligned to Apple's measured string (`cfcc2d67`). it / pt-BR / pt-PT keep the English because Apple itself does. (b) `codebook.hideTitle` showed **de, es, it, nl, pt-BR, pt-PT, tr and ko quoting with straight `"`** while ca/cs/da/fi/fr/nb/pl/ru/sv/uk/zh-Hant used their own typographic pair. That one string now carries the right pair in each — but only because the drift repair was rewriting it anyway, so it is a *side effect*, not a sweep. **The pattern is almost certainly not confined to one key**, and finding out is a measurement job before it is an editing one — see **Question B**. | 21 Aug 2026 | open — for `docs/i18n-reviews/`, not for a gate |
| 18 | ~~`ProjectDiagnosticPopover` — the reason column~~ | **Failure class 2, and the clearest example of it yet.** The pane rendered `Cause.message` raw, so a German, Japanese or Catalan researcher read *"Not a format Bristlenose reads."* while the header, count line and Show Log directly around it translated correctly. Not a missed key — **there was nothing to translate from.** All eight refusals share one `category`, and the discriminator existed only inside the English prose, so the pane had no key to look up; `refusals.py` had promised since Aug 2026 that *"the user-facing surfaces localise from the reason, not from this text"*, describing a field nobody had added. Worth noting against the table above: this was invisible to **three** gates, not two — `check-locales.py` (class 2, no `en` key to be missing from), `test_pipeline_diagnostic_locale_keys.py` (hardcoded allow-lists), **and** `test_swift_contract_parity.py`, which compares only the *intersection* of the two sides' fields and so would have passed on a Python-only `reason`. Fixed by putting the discriminator on the wire (`Cause.reason`) rather than by translating prose. | 22 Aug 2026, from the popover-sizing work — recorded as E3 in `design-pipeline-popover-sizing.md` before it was fixed | **struck**, 22 Aug 2026 — `desktop.pipeline.diagnostic.reason.*` × 8 × 21 locales; new gate parametrises over `UnusableReason` itself, so a ninth reason cannot ship untranslated. `git log -S'localisedReason' --` |
| 19 | `desktop.menu.codes.*` — the uninstall verb in fi, nl, ru, uk | **Not a translation defect — a semantic collision, and it needs a native eye rather than an edit.** `uninstallCodebook` was seeded 20 Sep 2026 using each locale's existing verb, and in these four that verb is identical to the one already on `deleteCode` and `deleteCodeGroup` in the same open menu: fi `Poista` ×3, nl `Verwijder` ×3, ru `Удалить` ×3, uk `Видалити` ×3. The objects differ so the rows are distinguishable, but English carries the reversible/destructive distinction **in the verb** (Uninstall vs Delete) and these do not — nothing signals that one is reinstallable from the Library and two are permanent. da and ko are clean (`Slet` / `삭제` for delete). **The obvious fix is wrong and was measured to be wrong:** the alternatives one would reach for — da `Afinstaller`, nl `Deïnstalleer`, fi `Poista asennus`, ru `Деинсталлировать`, ko `설치 제거` — appear **zero times** as strings in the system loctable corpus, while `Fjern` (435), `Verwijder` (969), `Poista`, `Удалить` and `제거` are precisely what Apple ships for Uninstall. So the seeded verbs are right and the collision is real at the same time. Candidate disambiguations for a reviewer to accept or reject: fi `Poista koodikirjan asennus`, nl `Deïnstalleer codeboek`, uk `Деінсталювати кодову книгу` (Apple uk uses it in prose, not as a button); ru has no good alternative. All four locales are machine-seeded pending native review anyway. | measured 20 Sep 2026, against the system loctable corpus | open — for `docs/i18n-reviews/`, not for a gate. **Do not "fix" it by substituting a dictionary word; that is the §6a colon mistake.** |
| 20 | ~~`bristlenose/locales/glossary.csv` — the `Codebook` rows for zh-Hant, ru, uk; and the machine-seeded noun in tr, ru, uk~~ | **The glossary and the shipped files named the same noun differently, and the glossary was the stale side in three of four.** zh-Hant shipped `編碼簿` against the glossary's `代碼簿` ×0 — and the glossary's own later `Library` row already said `編碼簿庫`, so a subsequent pass had contradicted the `Codebook` row; ru shipped `кодировочная книга` against `Книга кодов` ×0; uk shipped `кодова книга` against `Книга кодів` ×0. tr was the one case where the glossary was right. **Two separate machine-seeding errors surfaced in the same count** — ru `browseCodebooksButton` / `menu.codes.browseCodebooks` said `кодировщиков`, which means *of coders/encoders*, and uk `autocodeRefusal.alreadyRunning` / `.templateMissing` said `кодувальник`, likewise *coder*. Neither is a codebook; ru also carried `кодовый справочник` ×2 in the same block. **Fixed 20 Sep 2026.** Eight locale strings repointed to each locale's own established form, declined for the sentence rather than substituted as a lemma: ru instrumental `этой кодировочной книгой` and nominative `Эта кодировочная книга … недоступна`, uk `цією кодовою книгою` and `Ця кодова книга … недоступна`, tr dative plural `Kod Defterlerine`. Every form except the two instrumentals was checked against a string the locale already shipped (`titlebar.codebooks_one`, `help.navCodebook`, `nav.codebook`); the instrumentals are the only case in the tree and rest on the grammar. uk `alreadyRunning` also took `уже` → `вже`: that is not a style edit but the у/в alternation falling out of the noun change, since `книгою` ends in a vowel where `кодувальником` ended in a consonant. Three glossary rows corrected to the body form, and the derived taxonomy table in `i18n-language-decisions.md` § *Settled core taxonomy* — which declares itself built *from* `glossary.csv` — trued in the same pass, or the fix would have left that table contradicting its own stated source. **Two corrections to this row's own measurements.** The counts were low (`編碼簿` ×29 not ×27, `кодировочная книга` ×30 not ×19, `кодова книга` ×30 not ×10+) because the counting regex was case-sensitive and missed five sentence-initial forms per locale — the same class of undercount as item 14's word-length filter, and the reason a count in a register is worth re-deriving before it is cited. And **tr had four outliers, not two**: beyond the two `Kod Kitapları` strings now fixed, `autocodeRefusal.alreadyRunning` / `.templateMissing` still say `kod kitabı` against a body that says `kod defteri` ×26. Those two are left deliberately — `kod kitabı` is the glossary's own recorded *alt* form, so unlike `кодировщик` it is a synonym and not an error, and collapsing it is a register call rather than a defect fix. Same shape as item 5. The zh-Hant **terminology** question is likewise still open: `i18n-glossary-proposals.md` asks a Taiwan-native reviewer whether `編碼簿` is the right noun at all, and this fix resolved only the internal contradiction, not that question — a reviewer could still rule for `代碼簿` everywhere. **Prior art, measured later the same day** (MAXQDA's and NVivo's localised UIs and documents first, then the literature; the evidence is in `i18n-glossary-proposals.md` § *ru / uk / tr* and the zh-Hant brief). It reversed one premise and reframed another. **tr — the glossary was the wrong side:** MAXQDA's Turkish UI names its Codebook report *Kod kitabı* (two university decks list the Raporlar menu verbatim), its official Turkish webinar says *Kod Kitabı*, dergipark returns QDA papers for *kod kitabı* and Ottoman cryptography for *kod defteri*, and *Elektronik Kod Defteri* is the ECB cipher mode. The two `Kod Kitapları` outliers fixed above were the field's term; the sweep to *kod kitabı* (26 strings + three glossary rows, every inflected form mapped by hand because *defteri* is front-harmony and *kitabı* back-harmony) was applied later the same day on the maintainer's call — `git log -S'kitab' -- bristlenose/locales/tr`. **zh-Hant — a register fork, not a stale row:** MAXQDA zh-TW (代碼 ×96), MAXQDA zh-CN and NVivo zh-CN all use 代碼 for a code-as-noun and 編碼 for the activity, so the *old* rows `代碼`/`代碼簿` were the tool register; NAER and Academia Sinica's SRDA say 編碼簿, which the body follows. The proposals doc's "代碼 reads as an ID" is contradicted by MAXQDA's own usage. **ru:** MAXQDA ru says *Система кодов* and its Codebook label was not found; *кодировочная книга* is the survey-methods term, the qualitative literature says *кодировочная схема* (the old alt), *книга кодов* is Singh's cipher book. **uk:** no tool ships Ukrainian; Wikipedia attests both forms. And the history explains why nobody had checked: for ru, uk and zh-Hant the glossary row and the disagreeing body form were written in the *same* seeding commit — two machine outputs, no human decision — so "the body wins" resolved a contradiction and settled nothing about correctness. Apple's loctables were swept too and hold no *codebook* in any language, English included: not platform vocabulary, no false friend. | measured 20 Sep 2026; prior art the same day | **partly struck**, 20 Sep 2026 — 8 strings + 3 glossary rows + 1 derived table cell; `git log -S'Кодировочная книга' -- bristlenose/locales/glossary.csv`. tr swept to *kod kitabı* the same evening (26 strings + 3 rows). Open, all for native review and none a gate: **zh-Hant 代碼/編碼 register** (tools vs NAER), ru *книга* vs *схема*, uk *кодова книга* vs *книга кодів*, and tr's *Kod kitabı kitaplığı* (Codebook Library — a kitab-/kitapl- repetition a reviewer may want to rephrase) |
| 21 | ~~`common.json` — the Signals rename's prose, 5 keys × 20 locales~~ (+ `glossary.csv`, struck `5d98e73f`) | **Value drift, failure class 3 — and the plan's own close-out under-counted it.** `2aba263b` (20 Sep 2026) *rewrote* five `en` strings rather than swapping a word — `signals.{loadingData,noData,tagError}`, `help.guide.signalsBody`, `help.signals.intro` — and `design-signals-rename.md` §10 recorded three of them as English-only residue. Every other locale kept "analysis data" / "the analysis page" for a lens whose every *label* already read Signals in 21 locales, so the drift sat one heading below a correct title. **The two help strings were also the first time the word *lens* had to be rendered in any locale.** Measured against Apple's shipping `.loctable` corpus (3,400 files): `Lens` is the camera part in all 21 languages (*Objektiv*, *objectif*, 鏡頭), so a literal seed would have been wrong everywhere; `View` has a stable Apple noun per language (*Ansicht*, *vue*, *vista*, 表示, 보기, 檢視). Fixed by translating each string against its own file's existing vocabulary and rendering *lens* as the View noun with the lens's name, or the bare name in ja/zh-Hant. Rule recorded in `docs/glossary.md` (**lens**) and as a `Lens` row per locale in `glossary.csv`. Two measured corroborations of earlier calls while there: Apple ships *Signal* as 信号 / 신호 (the Wi-Fi sense), which is why ko went 신호→시그널 in Wave 1; and Apple's lone zh string is 信號 in `zh_TW` and 訊號 in `zh_HK`, so our zh-Hant 訊號 needs no HK override either way — one string is not a convention, filed as Question F. | measured 21 Sep 2026 | **struck**, 21 Sep 2026 — 100 values + `signals.intensityTitle` 0–3→1–3 × 21; `git log -S'Die Ansicht „Signale“' -- bristlenose/locales/de`. **Review the next day found the rule itself broken, and a sixth gate blind spot.** The 20 new `Lens` notes contain a comma and were written unquoted, so every one parsed one field wide and Weblate showed translators the note cut at *"Apple's own View noun"* — the bare-name alternative and the *build on the same noun as `nav.*`* clause never reached them. **Nothing in the repo reads `glossary.csv`**: no test, no script, no workflow, which is why twenty malformed rows shipped green. `check-locales.py` now asserts the header's field width per row (proved red against the defect first). Also fixed: the appended `Signals` notes ran two sentences together, and in `ca` the new text landed *after* `PENDING native review`, burying the flag. And cs/pl were made to quote the lens name (`Zobrazení „Signály“`, `Widok „Sygnały”`) — de/ru/uk/ja/zh-Hant had quoted it and these two had not. Measured, because the review's own precedent count was wrong: Apple's cs quotes a fixed interface name **3,328** times and pl **5,374**, in this exact shape (`Systemeinstellung „Drucker“`); both decline nouns, so an undeclined name wants setting off. **A second, adversarial pass over the 100 values then found the referential defect neither gate nor convention check could see.** *"…apply codebook tags to generate **them**"* — the pronoun's nearest candidate antecedent is the tags noun two words earlier, and in cs/pl/ru/uk/de the pronoun form matches that noun *exactly* (`je`, `je`, `их`, `їх`, `sie`), inviting the reading *apply tags to generate tags*. Every pre-edit value had named the noun (`die Analyse`, `analýzu`), so the ambiguity was **new in the target text while the translations were faithful** — it originates in the `en` string from `2aba263b`. Fixed by naming the noun in eleven locales and using the partitive in fr/it (`en`/`ne` reach the topic, not the tags); ca already had `-ne`, pt-BR/pt-PT are immune on gender, ja/ko/tr/zh-Hant name it. Four further defects, two grammatical: **fr** `tagError` had a bare countable plural after *de* — and the proposed *"Erreur des"* is **zero** in Apple's French against **87** for *"Erreur lors de…"*, so it reads `Erreur lors du calcul des signaux d'étiquettes`; **fr** `noData` took the partitive, having had no plural antecedent; **ko** read `시그널 보기는…`, where `보기` is the verb *view* in six other strings in that same file, so it parsed as *viewing signals displays…* — now locative with the name in ko's own quote pair, as ja does; **pl** had a view *wydobywa* (extracts, mines out) where every sibling shows or reveals. `b7982613`. **Both `en` copy regressions were then fixed on the maintainer's instruction, 21 Sep 2026.** `signals.noData` names the noun (*"…to generate signals"*), matching what the 20 locales now do. And the two help strings are definition-first — *"Signals are statistically notable concentrations of sentiment within report sections."* — which restores what the dropped apposition carried and matches `docs/glossary.md`'s canonical wording almost verbatim. Propagated to all 20 locales in the same commit, because rewording `en` alone *is* failure class 3: each locale's definition clause already existed, reviewed, in its pre-rename value, so this was a lift rather than a translation (`Signale sind…`, `Сигналы — это…`, `Sygnały to…`, `シグナルとは…`, tr's `-dır` copula). **Consequence worth reading twice: the word *lens* no longer appears in any product string**, so the View-noun renderings earlier in this item — and the cs/pl quoting fix, the ko locative and the pl verb that went with them — are superseded within the same day. They were correct for the copy that existed when they were made. The only `lens` left in `en` is `desktop.welcome.home.tips.frameworks.more` (*"brings its own lens"*), which is the metaphor, not the feature. The `Lens` glossary rows stay: the website uses the word throughout and the next string to need it should not be seeded as *Objektiv*. |
| 22 | ~~`SettingsView.swift` — the six Settings tab titles~~ | **Failure class 6, and the first one recorded.** The Settings window rendered its toolbar tabs — General / Appearance / LLM Provider / Transcription / Accounts / MCP Agents — and its window title in **English over fully-translated pane content**, in every locale. Not a missing key (all six present), not an untranslated value (`pl` reads *Ogólne / Wygląd / Dostawca LLM / Transkrypcja / Konta / Agenci MCP*), not a missing call (`i18n.t("desktop.settingsTabs.*")` at all six sites). The controller was a `private lazy var`, so the titles — plain `String`s on a `PkgSettings.Pane`, not views — were resolved **once per process** while the pane bodies re-rendered on every locale change. **Guaranteed rather than incidental: the language picker lives in that window**, so the only path to changing language resolves the titles at the old locale first, and they stayed wrong for the rest of the session. Every gate was green throughout. Found by a screenshot, which is the only thing that could have found it — the same lesson `CLAUDE.md` already records from the 20 Aug format-torture corpus (4,037 passing tests, three defects visible in one look at the app). Sibling worth noting: the MCP Agents pane *already* carried a comment in the same closure warning that it "runs ONCE, so anything resolved in it is pinned for the process" — `serveManager` had been fixed for exactly this reason and the titles, six lines up, were missed. | 21 Sep 2026, from a Polish screenshot | **struck** — controller rebuilds on `i18n.$locale`, restoring visibility and pane; Swift suite green (1463). The menu-bar titles in the same screenshot are a **separate** and known thing — `CommandMenu` takes `LocalizedStringKey`, which resolves from `.lproj` rather than runtime JSON; `LocalizedStringKey(i18n.t(…))` is used three times elsewhere in the tree and is the candidate fix, untested. |

---

## Decisions owed

Five, in rough order of how much they cost to leave open.

### Decision 1 — what "settled English" means (carried forward, now with three data points)

Items 2 and 3 were originally justified as "the copy is not settled, and asking
21 locales to carry unsettled copy wastes reviewer goodwill". Item 1 showed the
line is not "the whole feature" — a *toolbar title* among five translated
siblings reads as unfinished in a way a body sentence does not.

Three instances now, and they do not agree:

1. **18 Aug** — the Accounts pane shipped its English **verbatim into 21
   locales** the same day the row was written, because a lone English label
   among five translated ones looked worse than a machine seed.
2. **20 Aug** — the sidebar rewording shipped to `en` **only**, with the other
   twenty explicitly left holding the old words "until the English settles".
3. **21 Aug** — that hold was reversed, and the Codebook Library rewrite, which
   had been sitting unnoticed for **five weeks**, went with it.

So the register holds one feature that shipped unsettled English into 21
locales, one that withheld settled-enough English from 20, and one that
discovered the withholding had never been a decision at all — just nobody
looking. **The open question stands: does "settled" mean "no longer being
edited", or "reviewed against the glossary and signed off"?** But instance 3
adds something the first two did not have: a deliberate divergence and an
accidental one are **indistinguishable six weeks later**. Whatever the rule
turns out to be, it needs a mechanism — a marker in the file, or a detector run
on a schedule. Prose in a release note is not one.

**Half of that mechanism now exists (22 Aug 2026).** `_divergent_<key>` markers
record an intended divergence *in the locale data*, pinned to the English value
they were written against, and `check-locales.py` errors when the pin goes stale
— so a reword cannot silently inherit a note that was about different words.
Convention and worked example: `docs/design-i18n.md` § Divergence markers. Two
markers exist so far, both from the day the convention was written:
`desktop.welcome.aiSetup` (English noun, 20 verb forms) and
`desktop.menu.video.pictureInPicture` (three locales keep the English because
Apple does).

It is deliberately only half. The marker makes an intended divergence
*declarable* and keeps it honest; it does not find the undeclared kind. That is
still recommendation 1 below — and the two halves are worth building in this
order, because a detector without markers reports the same benign rows every
run until nobody reads it.

### Decision 2 — make `check-locales.py --strict` the CI gate

**`check-locales.py --strict` now exits 0.** It has never done that before;
items 8 and 9 were the entire warning output, and both are struck. Verified
21 Aug 2026 by running it. Making CI strict is a one-line change in
`.github/workflows/i18n-check.yml` and today it costs nothing.

The argument against is real and should be said: strict means a new `en` key
cannot land until all 21 locales have *something*, which in practice means a
machine seed. That is a policy choice about whether a machine seed beats a
visible gap — the same question as Decision 1, arriving from the other side.

And note what strict still would **not** catch: failure classes 2, 3, 4 and 5.
It is a stricter version of the one check we already have, not a new one.

### Decision 3 — what the `pipeline_view/cli.py` mirror is *for* — **CLOSED 21 Sep 2026**

> **Answered by the surface rule, not by a new judgement.** CLI terminal chrome is English *by design* — the terminal is the operator surface and the localised thing is the artefact it produces (`docs/design-i18n.md` §"Which surfaces are targets"). So the mirror is not drift awaiting a sync gate; it is a **register fork**, and the three measured divergences are the fork working as intended — the terminal names the package (`spaCy en_core_web_lg not installed`), the SPA names the thing (`language model not installed`). **No equality check should ever be written.** The open half of this decision was only ever open because the governing rule was phrased as "English-only *in alpha*", which reads as temporary. It was not temporary, and the register's own framing was what kept the question alive.

Item 5, restated as a question. Three of 23 strings diverge, and all three
diverge the same way: technical name in the terminal, plain name in the SPA.
Either

- **the mirror is a copy** — in which case pick the winner for those three and
  add a test asserting `_REASON_TEXT[k] == en[k]` for all 23; or
- **the mirror is a second register** — CLI for engineers, SPA for researchers —
  in which case the right check asserts the **key sets** match and says nothing
  about the values, and `CLAUDE.md`'s "silently diverges" wording is wrong and
  should be rewritten.

The second reading fits the evidence better. It cannot be settled by looking at
the code, because the code is consistent with both.

### Decision 4 — the UI-vs-plaintext split for failure categories

Item 6, scoped. The shape is not in doubt — a localised label for the pane, a
stable English token for the pasteboard. What is undecided is whether the pane
reads the existing `desktop.pipeline.diagnostic.pill.*` (6 of 16 categories, and
the pill and the popover would then have to agree forever) or gets its own
`category.*` block of 16. Plus the `"Category: "` prefix, which is a literal
today.

### Decision 5 — delete the dead `dt()` overrides, or restore what read them

Item 16. Three keys × 21 locales that no user can reach. Leaving them means
translators maintain strings that render nowhere. Deleting them is four lines of
JSON per locale — but do it with the block-scoped prune, **not** a file-wide
regex on the bare key name: `CLAUDE.md` records the day `menu.edit.undo` was
deleted from 21 locales by a regex aimed at `toast.undo`.

---

## Questions for native reviewers

These are wording, not engineering, and belong in `docs/i18n-reviews/`.
**Every one of the 20 full locales now has a brief there, as of 21 Sep 2026** —
the ten that were missing were written by the Signals-rename round, which
touched every language. So a question recorded below should also be *in* its
locale's brief; if it is only here, it is not in front of a reviewer.

**Everything seeded on 21 Aug 2026 is machine-seeded and unreviewed.** That is
862 new or replaced strings across 21 locales (305 added, 557 corrected).
`docs/i18n-reviews/it.md` carries a **round-two brief** written from this sweep
— it leads with the one thing I think is genuinely broken in Italian (three
different renderings of the codebook shelf sitting on one lens) and is the model
for the other nineteen when their reviewers are available. Where a term is Apple's, it was
**measured** — read out of the shipping `.loctable` files on a Mac, not taken
from a style guide, after the CJK punctuation sweep of 20 Aug got the polarity
backwards by reasoning from one. The measurements are recorded per-term in
`bristlenose/locales/glossary.csv`, each row ending `PENDING native review`.

**Question A — the `·` separator in CJK.** `codebook.foldedSummary` is the first
string in the project to use `·` as a stat separator, and it now carries it in
every script including ja/ko/zh-Hant. That may be right — it reads as a UI glyph
rather than punctuation — but it is a *decision made by default*, and there is no
measurement behind it, unlike the colon question §6a settled. Worth measuring
before it spreads to a second string.

**Question B — quote glyphs, now measured.** Found in `codebook.hideTitle`,
where de/es/it/nl/pt-BR/pt-PT/tr/ko wrote a straight `"` while their siblings
used a typographic pair. Rewriting that string meant choosing pairs, so they
were **measured** across every `/System/Library/**/*.loctable` rather than
recalled — and the measurement immediately caught me out. I had reached for
`«…»` in it, es and pt-PT on reputation. Apple's shipping counts:

| locale | Apple's pair | count | `«…»` |
|---|---|---|---|
| it | `“…”` | 39,356 | 9 |
| es | `“…”` | 36,261 | 9 |
| pt-PT | `“…”` | 31,029 | 9 |
| nl | `“…”` | 692 | 9 |
| de | `„…“` | 53,483 | — |
| cs | `„…“` | 30,260 | — |
| fi, sv, pl | `”…”` | 18k–33k | — |
| fr, ru, uk, nb | `«…»` | 29k–51k | — |
| zh-Hant | `「…」` | 67,034 | — |

That constant `9` is the tell: the same handful of shared strings, i.e. Apple
effectively never uses `«…»` in it/es/pt/nl. Corrected in `2a45020f`.

**Two pre-existing ones left alone**, because they are not from this sweep and
almost certainly are not confined to one key: **da** carries `„…“` where Apple
ships `“…”`, and **ca** carries `«…»` where Apple ships `“…”`. A sweep across
all locale files is the next step — and note it is a *measurement* task before
it is an editing one, with one caveat the table above hides: raw counts can be
inflated by English strings embedded in a locale table. `ja` reads `“…” 45,215`
against `「…」 1,747`, which is almost certainly that artefact rather than a
recommendation to quote a user's codebook name with `“…”` in Japanese.

**Question C — where Apple's word is not the industry's.** Three places the
measured platform term may lose to convention, flagged in the glossary:

- **tr `Default` → `Saptanmış`.** Apple ships it 261 times. Most Turkish
  software says `Varsayılan`. The house rule ("the platform wins — a label that
  reads differently from every other label on the user's Mac is the defect")
  says Apple; a Turkish researcher may disagree.
- **`Uninstall` in da, fi, nl, ru, uk, ko.** Apple lands on the Remove-family
  word rather than an un-install cognate. The risk is that it stops being
  distinguishable from the generic "remove" elsewhere in the codebook UI.
- **ca `Default`.** Apple ca ships `Per omissió`; the Catalan glossary chose
  `Per defecte` before anyone measured. Both are in the file now. Reconcile.

**Question D — a glossary that disagrees with the locale files.** For ru, uk and
zh-Hant the glossary's `Codebook` row and the shipped locale value are different
words: `Книга кодов` vs `Кодировочная книга`, `Книга кодів` vs `Кодова книга`,
`代碼簿` vs `編碼簿`. The 21 Aug pluralisation deliberately took the **locale
file's** root so as not to smuggle a terminology change into a grammar fix — but
that means the disagreement is now recorded twice. It is a reviewer call.

**Question E — two clunky compounds.** `Codebook Library` came out as
`Knihovna knih kódů` (cs) and `Libreria dei libri dei codici` (it). Both are
literal and unambiguous and neither is good. Flagged in the glossary for a
better proposal.

**Question F — 訊號, and a head noun nothing currently renders.** The Signals
rename briefly made `help.guide.signalsBody` / `help.signals.intro` the first
strings to render the word *lens* (item 21) — **and the definition-first rewrite
later the same day removed it again**, so (a)–(c) below are held against the next
string that needs the word rather than against anything shipped. **(d) is live.**
The superseded renderings were: The seeds use Apple's measured View noun with the lens
name — de *die Ansicht „Signale“*, fr *la vue Signaux*, sv *vyn Signaler* — or
the bare name in ja/zh-Hant (「シグナル」では…). Four calls for reviewers: (a) de
*die Ansicht „Signale“* vs *die Signale-Ansicht*; (b) ru *представление* and uk
*подання* were chosen over Apple's *Вид* / *Вигляд* because "в виде «Сигналы»"
reads as "in the form of signals" — confirm or overrule; (c) everyone else:
does the View noun read as a named screen, or would you drop it as ja/zh-Hant
do? (d) **zh-Hant 訊號 vs 信號** — Apple's one `Signal` string is 信號 in `zh_TW`
and 訊號 in `zh_HK`; our zh-Hant says 訊號 throughout (reviewed, `glossary.csv`).
For the Taiwan-native reviewer alongside the 代碼/編碼 question. The it strings
are a compact five-line sample for the reviewer already in the loop.

---

## What to build next

The three detectors used on 21 Aug are throwaway scripts in a scratch
directory. Two are worth keeping, and one probably is not:

1. **A value-side gate** — the highest-value one by a distance, because failure
   class 3 is where the 18-key Codebook Library drift lived unnoticed for five
   weeks. Cheapest workable form: store a hash of each `en` value alongside it
   (or in a sidecar), and fail when an `en` value changes without the locales
   being re-touched. This is the gate Decision 1 needs to make a "deliberate
   divergence" distinguishable from an accidental one.
2. **A call-site gate** — cheap, catches failure class 5, and would have caught
   the dead `dt()` keys in item 16 the day the help modal was retired. Must match
   on the fully-qualified key; a leaf-name match reports dead keys as alive.
3. **The untranslated-value detector** — genuinely useful today (it found item
   14's 29 real defects), but it cannot become a gate without a hand-maintained
   allow-list of legitimately-invariant strings, and an allow-list is precisely
   the shape that made `test_pipeline_diagnostic_locale_keys.py` unable to see
   anything new. Read item 14's own postscript before building it: the first
   version of this detector used a heuristic *instead of* an allow-list, to keep
   the output readable, and the heuristic silently ate two of the defects it was
   written to find. Better as a periodic sweep whose output a human reads than
   as a gate whose threshold nobody revisits.

A fourth thing is not a detector at all and matters more than any of them:
**a new user-facing surface is reviewed for `i18n.t` call sites at the point it
lands, because after that nothing mechanical will ever ask again.** Item 12 is
the case in point — a rewrite dropped three `i18n.t` wrappers while keeping the
English verbatim, and the only reason it surfaced was that somebody read the
file five weeks later.
