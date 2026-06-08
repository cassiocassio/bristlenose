# So you're adding a new language

A playbook for adding a locale to Bristlenose end-to-end (CLI, desktop, React).
Distilled from the Czech (`cs`) wave, 8 Jun 2026 — it's the sequenced procedure
the cs session wished it had at the start.

**Sibling docs and how they differ:**

- `docs/design-i18n.md` — the **engineering reference** (gotchas, patterns,
  per-locale notes, plural-mechanism details). Read it for *why*. This doc is
  *how*.
- `docs/design-multilingual-ui.md` — the **strategy** (which languages, why,
  the reviewer-gate-as-recruitment model). Read it before deciding to add
  a language.
- The per-language handoff brief in your branch's local-only handoffs
  directory — the **per-language spec** for a specific wave (reviewer plan,
  scale estimate, intra-pair leverage if a pair like pt-BR/pt-PT). Read
  whichever applies to your current branch.

This doc is intentionally tonal: friendly, opinionated, ordered. If you're
adding a language and you're not sure where to start, start at the top and
work down. The gotchas are deferred to design-i18n.md — when you hit one
mid-step, that's where to look.

**Why a sibling doc and not a section of design-i18n.md.** design-i18n.md is
the engineering reference; jamming a long ordered playbook into the middle
of it would mix two registers and bloat the reference for everyone who isn't
adding a language. A standalone "how to add a language" doc is what someone
actually searches for. The two cross-reference each other and stay short.

---

## Before you start: is this language actually wanted?

**Don't add languages speculatively.** The bar is a demand signal:

- **Cs gold standard:** a volunteer signed up on Weblate and started
  translating *before* the language was supported. That's the cleanest
  signal — someone bothered to act before being asked.
- **Pt gold standard:** a contact (Lisbon UR conference) + market size
  (Brazilian UR community). A different shape — channel + scale, not a
  volunteer in hand — but still a real signal.
- **Anti-pattern:** "we should probably do German next." No. Wait for
  evidence. Bristlenose at alpha-cohort scale is six locales because six
  showed up, not because someone tier-listed them.

If the demand signal isn't there, the work that follows is wasted.

## Pick the language code

- **ISO 639-1 bare 2-letter** for languages without internal variation that
  matters to translation: `cs`, `ja`, `ko`. **Use the language code, not the
  country code** — Czech is `cs` (the language) not `cz` (the country).
- **Region subtag (hyphen)** when a single bare code would read as foreign
  to one side: `pt-BR` / `pt-PT`, `zh-Hans` / `zh-Hant`. Apple uses the
  hyphen form; we match. Don't use the underscore form (`pt_BR`) anywhere
  in our code — it's Apple's internal `Locale.current.identifier` shape and
  we don't touch that surface (see Swift section below).

The code you pick is the directory name under `bristlenose/locales/`, the
`Locale` union member in the frontend, the `Set<String>` member in Swift,
the `SUPPORTED_LOCALES` tuple member in Python, and the `.tag(...)` value
in the macOS picker. One name, six places.

## Region subtags — what the plumbing already handles

You do NOT need to make the plumbing "support region subtags" before
translating. The plumbing handles them, with one config decision and no
infra surgery:

- **Don't touch:** all `SUPPORTED_LOCALES` lists (literal union / tuple /
  Set are just strings — hyphens work), the locale-dir glob
  (`scripts/check-locales.py` uses `iterdir()` — name-agnostic), the Vite
  `@locales` alias (filesystem path), the dynamic-import path in
  `frontend/src/i18n/index.ts` (template string — hyphen is a valid path
  char), the PyInstaller spec (whole-dir entry).
- **Do touch once:** if you want bare-`pt` browsers (older Chrome, no
  region) to fall back to a region variant rather than `en`, add
  `nonExplicitSupportedLngs: true` + `supportedLngs: [...SUPPORTED_LOCALES]`
  to the `i18n.init()` block in `frontend/src/i18n/index.ts`. Two-line
  config addition. Decide once which subtag is the default for bare `pt`
  (probably `pt-BR` by population) and document it in design-i18n.md.
- **Don't worry about Apple's underscore form.** `I18n.swift` never reads
  `Locale.current` — `configure()` defaults to `"en"` until the user picks
  from Settings. So the Apple `pt_BR` vs i18next `pt-BR` convention
  mismatch never surfaces. The picker writes the hyphen form to
  `UserDefaults`; that string round-trips through `supportedLocales.contains`
  unchanged.

## Decide BEFORE you touch code: Weblate-first or branch-first?

The cs experience picked this fight late and paid for it. **Decide WITH
the user before any code lands:**

- **Weblate-first:** create the locale component on Weblate, merge an
  empty skeleton PR (cs's was #103), then machine-seed in-branch
  fill-empty-only. The Weblate skeleton creates the dir; your seed fills
  it. Risk: extra coordination round-trip.
- **Branch-first:** create the dir in your branch with the full
  machine-seed, then coordinate a Weblate import. Risk: add/add conflicts
  if Weblate also creates the dir before merge.

There's no clean way to do both in parallel — pick one, then do it. The
cs branch did Weblate-first and it worked, but the sequence is
load-bearing both ways.

## Step 1 — Register the code in three places

```
frontend/src/i18n/index.ts          SUPPORTED_LOCALES literal union  (line ~19)
bristlenose/i18n.py                 SUPPORTED_LOCALES tuple          (line ~23)
desktop/Bristlenose/Bristlenose/I18n.swift  supportedLocales Set     (line ~29)
```

Adding the new code to all three is the minimum smoke test that the rest of
the work will be plumbed. Do this first; the test suite will start failing
loudly on missing key files, which is what you want for the next steps.

## Step 2 — Make the locale directory + namespace files

```
bristlenose/locales/<code>/
  common.json          ~452 keys (largest)
  desktop.json         ~331 keys (desktop chrome + pipeline messaging)
  settings.json        ~85 keys
  cli.json             ~19 keys (CLI is English-only in alpha — mirror only)
  enums.json           ~11 keys
  doctor.json          ~6 keys
  server.json          ~5 keys
  pipeline.json        ~4 keys
bristlenose/locales/<code>/preflight.json   ~33 keys (root namespace, not under desktop)
```

Mirror an existing locale (`es/` is a good "average" baseline; `cs/` is a
good plural reference). Empty values are fine — the test suite will tell
you which are missing.

## Step 3 — Seed the strings (fill-empty-only)

Machine-translation seed via your preferred path (Weblate's
glossary-aware MT is fine for the first pass). **Fill-empty-only** is the
invariant: for each English key, write a translation *only* where the
target locale is currently empty. Never overwrite a non-empty value.

- **JSON editing rule:** do NOT round-trip via `json.load` + `json.dump`
  — it causes massive escape-churn (literal Unicode ↔ `\u` escapes
  flipping per locale). See CLAUDE.md root §"Don't round-trip locale JSON".
  Targeted string replace + `json.dumps(value, ensure_ascii=True)` per
  inserted value is the cs-validated pattern.
- **For `desktop.json` specifically:** mixed escaping is intentional and
  documented; preserve it. The Czech wave's conversion script renamed keys
  + added whole lines, never re-encoding existing values — that's the
  pattern to mirror.

## Step 4 — Plurals (the pernickety bit)

i18next handles CLDR plurals automatically on the frontend — your
seeded `_one` / `_other` / `_few` / `_many` keys get picked up by suffix.
Python and Swift need explicit work:

- **Python:** the active surface (`bristlenose/i18n.py`) is English-only
  in alpha for CLI. No plural selector needed yet.
- **Swift:** if your language has more than `one`/`other`, add a case to
  `I18n.pluralCategory(_:)` in `desktop/Bristlenose/Bristlenose/I18n.swift`.
  The cs case is the canonical template — count ranges with CLDR semantics
  inline-commented. **Look up your language's CLDR rules at
  [unicode.org/cldr/charts](https://www.unicode.org/cldr/charts/47/supplemental/language_plural_rules.html)
  before writing the case** — Polish has different boundaries than Czech;
  Russian distinguishes `many` from `other` for integers (Czech doesn't).
- **For non-binary plural locales:** add `_few` / `_many` / etc. to every
  pluralised key (typically `interviewCount_*`, `unanalysedSubtitle_*`,
  `missingSubtitle_*` in `desktop.json` chrome, and `overflow_*` in
  `pipeline.diagnostic`). The parametrised test
  `test_chrome_count_four_form_locales_carry_all_forms` gates on presence
  of `_few` — so any new four-form locale auto-acquires coverage without
  a test edit.
- **Add a Swift `@Test`** for plural selection per language; mirror
  `pluralCategory_czech_picksFewForCounts2to4` and
  `chromeInterviewCount_czech_selectsCldrForm` in
  `desktop/Bristlenose/BristlenoseTests/I18nTests.swift`. The shape is
  generic; copy and substitute.

See design-i18n.md "Czech plurals — the pernickety one/few/many/other
rule" for what each CLDR category means in practice and the seeded-inventory
brief format.

## Step 5 — Glossary

`bristlenose/locales/glossary.csv` carries Apple HIG + Bristlenose QDA
terms. Add rows for the new locale. The `language` column is a string —
hyphenated codes work fine, no parser truncates (no consumer in the
codebase as of cs; Weblate reads it).

Minimum coverage: the ~30 Apple-HIG core verbs (Save, Cancel, Delete,
Close, Open, Export, Search, OK, Settings, Preferences, …) and the
Bristlenose QDA domain terms (Codebook, Quotes, Sessions, Themes, Tags,
Sentiment, Codes, Participants, Transcript, Project). Source the Apple
verbs from `applelocalization.com` or whatever your Apple-glossary tool
of choice is.

## Step 6 — Pickers (three sites)

```
frontend/src/islands/SettingsPanel.tsx       LOCALE_LABELS  (line ~31)
frontend/src/components/SettingsModal.tsx    LOCALE_LABELS  (line ~39)
desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift   .tag(...)  (line ~36)
```

Use the **native name** of the language ("Čeština" not "Czech", "日本語"
not "Japanese", "Português (Brasil)" not "Portuguese (Brazil)"). Users
pick in their own language.

## Step 7 — Doctor + bundle expectation

```
bristlenose/doctor.py  expected = {"en", "es", ...}  (line ~972)
```

One-line edit. Otherwise `bristlenose doctor` flags your new locale as
missing on first run.

PyInstaller doesn't need a spec change — `desktop/bristlenose-sidecar.spec`
already has the whole `bristlenose/locales/` tree in `datas`, so new dirs
ride along on the next sidecar build.

## Step 8 — Tests

Add the new locale to test parametrisation:

```
tests/test_pipeline_diagnostic_locale_keys.py
    _ALL_LOCALES                — add your code
    _PLURAL_LOCALES             — add if your language has _one (i.e. anything that's not ko/ja)
    _SINGLE_FORM_LOCALES        — add if your language is ko/ja-shaped (other-only)
```

The four-form parametrised tests
(`test_four_form_locales_carry_all_forms` /
`test_chrome_count_four_form_locales_carry_all_forms`) derive coverage
from the presence of `_few` — no edit needed for new four-form locales.

`scripts/check-locales.py` needs no code change — it iterates whatever
dirs exist.

## Step 9 — Run the sweep

```sh
.venv/bin/python -m pytest tests/test_pipeline_diagnostic_locale_keys.py
.venv/bin/python scripts/check-locales.py
.venv/bin/ruff check .
xcodebuild -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -scheme Bristlenose build CODE_SIGNING_ALLOWED=NO
xcodebuild -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -scheme Bristlenose test -only-testing:BristlenoseTests/I18nTests \
  CODE_SIGNING_ALLOWED=NO
cd frontend && PATH="/opt/homebrew/opt/node@24/bin:$PATH" npm run build
```

Node 24 explicitly — Node 26 breaks jsdom localStorage in vitest (root
CLAUDE.md gotcha; this is the recurring papercut). After xcodebuild,
revert `desktop/Bristlenose/Bristlenose/GeneratedBuildInfo.swift` — it's
dirtied every build.

## Step 10 — Manual smoke

Open the desktop app, switch to the new locale via Settings → Language,
verify three quick surfaces:

- Sidebar count strings render the right plural form (analyse a folder
  with 2–4 interviews if your language has a `few` form).
- A pipeline run shows the localised activity status.
- The transcript page loading / error / empty states are localised.

The 30 seconds of clicking catches anything the test suite missed.

## Step 11 — Native-speaker review is a FINAL gate, not the first step

Ship as **community preview** (`"Português (Brasil) — community preview"`)
labelled in the picker until a native reviewer signs off. Recruit by:

1. **Weblate volunteer** (best — they're already engaged).
2. **Cohort introduction** (warm — fish where the fish are).
3. **Cold contact in the language community** (last resort).

The reviewer gate is recruitment leverage — see design-multilingual-ui.md
§"Language roadmap" + the cs experience with Pavel as the worked
example. Catalogue what's machine-seeded (especially plural forms) in
design-i18n.md or a per-language section so the reviewer knows what to
verify.

## Step 12 — Done criteria

- [ ] Code registered in 3 SUPPORTED_LOCALES sites
- [ ] Locale dir + 8 namespace files + preflight.json populated
- [ ] Plural selector case added (if not one/other-shaped) + Swift @Test
- [ ] Glossary rows added (Apple HIG + Bristlenose QDA)
- [ ] 3 picker labels updated (native name)
- [ ] doctor expected set updated
- [ ] Tests parametrised
- [ ] Full sweep green (pytest + check-locales + ruff + xcodebuild build
      + xcodebuild test + npm build)
- [ ] Manual smoke on desktop in the new locale
- [ ] Native reviewer contacted (or "preview" labelled if not)
- [ ] CHANGELOG entry framed broadly enough that follow-up fixes can
      ride the same release narrative (cs lesson — see the post-cs note
      in design-i18n.md on multi-commit wave CHANGELOG framing)
- [ ] Version bump (real user-facing work — one or two new languages
      is always a bump)

That's the playbook. design-i18n.md is where you go for *why* any single
step looks the way it does; here's where you find out *which* step is
next.
