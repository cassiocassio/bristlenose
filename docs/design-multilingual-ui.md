# Multilingual UI Support

## Status

**Draft** — Mar 2026

## Problem

Bristlenose's UI is English-only. The tool is useful to UX researchers worldwide —
particularly in Japan, Korea, Germany, France, and Latin America where active UX/UR
communities exist (HCD-Net in Tokyo, UX Days Tokyo, etc.). Researchers who conduct
interviews in their native language should be able to read the tool's chrome in that
language too.

**What this covers:** The application's own UI labels, navigation, buttons, error
messages, settings, CLI output, and help text.

**What this does NOT cover:** User-generated content (quotes, themes, headings,
transcript text, codebook tags). These are always in whatever language the research
was conducted in. LLM prompts are also out of scope — the prompts already instruct
the model to respond in the same language as the source material.

## Current state

Infrastructure is **in place but unpopulated**:

| Layer | Library/module | English extracted? | Non-English translations? |
|-------|---------------|--------------------|--------------------------|
| React frontend | i18next + react-i18next + browser-languagedetector | Yes — 3 namespaces (`common`, `settings`, `enums`) | Locale dirs created (de/es/fr/ja/ko), all empty |
| Python CLI/server | `bristlenose/i18n.py` — custom `t()` function | Yes — 5 namespaces (`cli`, `doctor`, `enums`, `pipeline`, `server`) | Locale dirs created, all empty |
| Settings UI | `LocaleStore.ts` + `<select>` in SettingsPanel | Working locale selector with browser detection + localStorage | Switching to non-English shows English fallback for all strings |

### Frontend adoption gap

- `useTranslation()` is only called in `main.tsx` (1 file)
- ~140+ component/test files import or reference hardcoded English strings
- `SettingsPanel.tsx` has a working language selector but the panel's own labels
  ("Settings", "Application appearance", etc.) are hardcoded English

### Python adoption

- `bristlenose/i18n.py` exists with `t()`, `set_locale()`, `get_locale()`
- English JSON files exist with CLI stage names, error messages, progress labels
- No call sites use `t()` yet — CLI output still uses hardcoded English in
  `pipeline.py`, `cli.py`, etc.

## Supported locales

```
en  English     (default, bundled inline)
es  Español     (Spanish)
ja  日本語       (Japanese)
fr  Français    (French)
de  Deutsch     (German)
ko  한국어       (Korean)
```

Already declared in `SUPPORTED_LOCALES` in both `frontend/src/i18n/index.ts` and
`bristlenose/i18n.py`.

## Design decisions

### 1. UI chrome only — not research content

Researchers work with multilingual source material already. Bristlenose should
translate its own interface (nav tabs, buttons, labels, settings, CLI output, error
messages) but never touch user content (quotes, themes, transcripts, codebook tags,
participant names). This keeps the tool honest — a Japanese researcher seeing
English quotes from English interviews is expected; machine-translating those quotes
would corrupt the research.

### 2. Frontend: i18next with namespace-scoped JSON

Already chosen and partially implemented. Key choices:

- **Namespaces**: `common` (nav, buttons, labels, footer), `settings` (settings
  panel), `enums` (sentiment names, speaker roles). Add new namespaces as needed
  (e.g. `dashboard`, `codebook`, `toolbar`, `export`, `analysis`)
- **Lazy loading**: English bundled inline (zero latency). Other locales loaded via
  `import()` on demand. Already implemented in `ensureLocaleLoaded()`
- **Fallback**: missing keys fall back to English string, never to raw key
- **No ICU MessageFormat** — simple `{{interpolation}}` is sufficient. Bristlenose
  UI text is short labels and messages, not complex plurals or gendered text

### 3. Python: lightweight `t()` function with same JSON format

Already implemented in `bristlenose/i18n.py`. Shares JSON files with the same
structure as the frontend, so translators work with one format. Python uses
`str.format_map()` for interpolation (`{version}` not `{{version}}`).

### 4. Locale detection priority

Already implemented in `LocaleStore.ts`:

1. `localStorage("bn-locale")` — explicit user choice in Settings
2. `navigator.languages` / `navigator.language` — browser preference
3. `"en"` fallback

For CLI: check `BRISTLENOSE_LOCALE` env var → system locale (`locale.getdefaultlocale()`) → `"en"`.

### 5. `<html lang>` attribute

Already set by `setLocale()` in `LocaleStore.ts`. Critical for:

- CJK font selection (ja vs zh vs ko share Unicode codepoints but need different
  glyphs)
- Screen reader pronunciation
- CSS `:lang()` pseudo-class for language-specific typography

### 6. No RTL support initially

Arabic and Hebrew would need RTL layout (`dir="rtl"`). Out of scope for v1. The
locale list can be extended later — the infrastructure is locale-agnostic.

## Implementation plan

### Phase 1: Wire up frontend components (strings → `t()`)

**Goal**: Every hardcoded English string in the React frontend goes through `t()`.

1. **Add `useTranslation()` to each component** that renders user-visible text.
   Pattern:
   ```tsx
   import { useTranslation } from "react-i18next";

   export function NavBar() {
     const { t } = useTranslation();
     return <nav>{t("nav.quotes")}</nav>;
   }
   ```

2. **Extract strings to namespaces**. Start with the most visible surfaces:
   - `common.json` — nav tabs, buttons, loading/error states, footer, search
   - `settings.json` — appearance options, language selector, config reference
     headings
   - `enums.json` — sentiment labels, speaker roles
   - New `dashboard.json` — stat labels, headings, empty states
   - New `toolbar.json` — view switcher, density, sort controls
   - New `codebook.json` — codebook panel labels, autocode UI
   - New `analysis.json` — analysis page headings, signal labels
   - New `transcript.json` — transcript page labels
   - New `export.json` — export dialog labels

3. **SettingsPanel**: migrate hardcoded labels to `t("settings.heading")`,
   `t("settings.appearance.legend")`, etc. The config reference table labels
   (LLM Provider, Transcription, etc.) stay in English — they're developer/config
   vocabulary, not researcher-facing prose.

4. **Test files**: test assertions that check rendered text should use the English
   translation value (since tests run with `"en"` locale). No need to mock i18n in
   most tests — i18next is initialised with English as default.

**Estimated scope**: ~50 component files + ~30 island/page files. Mechanical
refactor — low risk per file, high cumulative volume.

### Phase 2: Wire up Python CLI

**Goal**: CLI output, error messages, and doctor output go through `t()`.

1. Add `BRISTLENOSE_LOCALE` env var to `config.py`
2. Call `set_locale()` early in CLI startup (`cli.py`)
3. Replace hardcoded strings in:
   - `pipeline.py` — stage names, progress lines, completion message
   - `cli.py` — help text, error messages, version string
   - `bristlenose/stages/` — stage-specific error/warning messages
   - `doctor.py` — health check labels and results
4. Server routes: translate user-facing error messages (404s, validation errors).
   API field names stay in English (they're a programming interface).

### Phase 3: Translate the English strings

**Goal**: Populate `ja/`, `ko/`, `es/`, `fr/`, `de/` locale directories.

Priority order by community size and demand:

1. **Japanese (ja)** — strongest demand signal (active HCD-Net community,
   UX Days Tokyo, DDX Tokyo)
2. **Korean (ko)** — Samsung/LG UX research communities, growing indie scene
3. **Spanish (es)** — large Latin American UX community
4. **French (fr)** — France + Quebec research firms
5. **German (de)** — SAP, automotive UX research

**Translation approach**:

- **Machine-translate first** (Claude or similar) to unblock testing
- **Human review** by native-speaker UX researchers before release
- **Keep files in sync** — when English strings change, non-English files get a
  `// TODO: update translation` comment (or use i18next's missing key handler in
  dev mode)
- **Glossary**: maintain a shared glossary per language for UX research terms
  (e.g. "quote" → 引用 in ja, "theme" → テーマ, "sentiment" → 感情). Store in
  `docs/translation-glossary.md`

### Phase 4: Polish

1. **CJK typography** — ja/ko/zh text is typically 1.5× taller than Latin text at
   the same font size. May need `line-height` and padding adjustments via
   `:lang(ja)` / `:lang(ko)` CSS rules in the theme
2. **String length** — German and French translations are typically 30% longer than
   English. Audit UI for overflow, especially:
   - Nav tabs (compact horizontal space)
   - Buttons and badges
   - Sidebar headings
   - Toast messages
3. **Date/number formatting** — use `Intl.DateTimeFormat` and `Intl.NumberFormat`
   with the active locale. Currently dates are formatted with hardcoded English
   patterns
4. **Keyboard shortcuts help** — `HelpModal.tsx` lists keyboard shortcuts. Labels
   should be translated, key names stay as-is (Ctrl, Shift, etc.)
5. **Export** — exported HTML snapshots should carry the active locale's strings
   (the export already snapshots the DOM, so this may work automatically)

## File map

```
frontend/src/
  i18n/
    index.ts              ← i18next init, SUPPORTED_LOCALES, ensureLocaleLoaded()
    LocaleStore.ts        ← module-level store, useLocaleStore(), setLocale()
  locales/
    en/
      common.json         ← nav, buttons, labels, footer
      settings.json       ← settings panel
      enums.json          ← sentiment names, speaker roles
      dashboard.json      ← (new) dashboard stats and headings
      toolbar.json        ← (new) view switcher, density, sort
      codebook.json       ← (new) codebook panel
      analysis.json       ← (new) analysis page
      transcript.json     ← (new) transcript page
      export.json         ← (new) export dialog
    ja/                   ← (empty — Phase 3)
    ko/                   ← (empty — Phase 3)
    es/                   ← (empty — Phase 3)
    fr/                   ← (empty — Phase 3)
    de/                   ← (empty — Phase 3)

bristlenose/
  i18n.py                 ← Python t(), set_locale(), get_locale()
  locales/
    en/
      cli.json            ← CLI stage names, errors, progress
      doctor.json         ← doctor check labels
      enums.json          ← sentiment/role names (shared with frontend)
      pipeline.json       ← pipeline messages
      server.json         ← server/API error messages
    ja/                   ← (empty — Phase 3)
    ko/                   ← (empty — Phase 3)
    es/                   ← (empty — Phase 3)
    fr/                   ← (empty — Phase 3)
    de/                   ← (empty — Phase 3)
```

## What NOT to translate

- **User content**: quotes, themes, headings, transcript text, codebook tags,
  participant names, project names
- **API field names**: JSON keys in API responses (`sentiment`, `speaker_role`,
  `confidence`)
- **Config variable names**: `BRISTLENOSE_LLM_PROVIDER`, `.env` keys
- **Log messages**: internal logs stay in English (developer audience)
- **LLM prompts**: already handle source language dynamically
- **Code comments and docstrings**
- **File format names**: VTT, SRT, DOCX, JSON, CSV, HTML

## Testing strategy

1. **Unit tests** — run with English locale (default). Assertions check English
   strings. No i18n mocking needed
2. **Locale switching test** — one dedicated test that calls `setLocale("ja")`,
   renders a component, and verifies the Japanese string appears (requires at least
   one translated string in `ja/common.json`)
3. **Missing key coverage** — in dev mode, enable i18next's `saveMissing` to log
   any hardcoded strings that weren't extracted. Run the app and navigate all
   tabs/modals to generate a missing key report
4. **Snapshot tests** — existing visual diff tests remain English-only. Add a
   dedicated `?locale=ja` visual diff route if CJK typography needs pixel-level QA
5. **E2E** — Playwright tests run English-only. No locale-specific E2E unless we
   see locale-dependent bugs

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Translation quality — machine translation of UX research terminology may be wrong | Glossary per language, human review before release, community feedback channel |
| String drift — English changes without updating translations | CI check: compare key sets across locale files, warn on missing keys |
| UI overflow — German/French longer strings break layout | Audit compact UI surfaces (nav, buttons, badges) with longest translations |
| CJK line height — ja/ko text looks cramped | `:lang()` CSS rules for line-height/padding adjustments |
| Maintenance burden — 6 languages × N namespaces = many files | Start with 2 languages (ja, ko), add others when community translators volunteer |
| Bundle size — loading all translations upfront | Already mitigated — only English is bundled, others lazy-loaded |

## Open questions

1. **Should the CLI respect the frontend's locale setting?** The frontend persists
   to `localStorage("bn-locale")`, but the CLI can't read that. Options: (a) separate
   `BRISTLENOSE_LOCALE` env var, (b) persist to a config file both can read,
   (c) CLI always uses system locale. Leaning toward (a) for simplicity.

2. **Should exported HTML carry the locale?** If a Japanese researcher exports and
   shares with an English-speaking colleague, should the export be in Japanese (the
   researcher's setting) or English (universal)? Leaning toward: export uses the
   active locale, with a "Language" dropdown in the export dialog for override.

3. **Community translation workflow** — accept PRs with JSON files? Use a platform
   like Crowdin/Weblate? For v1, JSON files in the repo are fine. Consider a
   platform if we reach >3 active languages.

## References

- [react-i18next docs](https://react.i18next.com/)
- [i18next interpolation](https://www.i18next.com/translation-function/interpolation)
- `frontend/src/i18n/index.ts` — current init code
- `frontend/src/i18n/LocaleStore.ts` — locale store
- `bristlenose/i18n.py` — Python translation module
- `docs/design-react-component-library.md` — component inventory (scope for Phase 1)
- HCD-Net Japan: https://www.hcdnet.org/en/ — primary outreach for ja translators
