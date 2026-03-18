# i18n Wiring — Connect React Components to Translation Keys

## Context

The i18n infrastructure is complete: i18next initialised, locale files exist (en + es), language switcher works, dynamic loading works. But **zero components call `useTranslation()`** — all user-facing strings are hardcoded English. This plan wires the existing 34 `common` + 18 `settings` + 14 `enums` keys into their components.

Branch: `i18n-wiring` (create from main via `/new-feature`)

## Scope: only wire existing keys

No new keys. No new translated strings. Just replace hardcoded English with `t()` calls using keys that already exist in `en/*.json` and `es/*.json`. The English experience should be pixel-identical after this change.

## Components to modify

### 1. NavBar (`src/components/NavBar.tsx`)

- Add `const { t } = useTranslation();`
- Replace 5 tab labels: `"Project"` → `t("nav.project")`, `"Sessions"` → `t("nav.sessions")`, `"Quotes"` → `t("nav.quotes")`, `"Codebook"` → `t("nav.codebook")`, `"Analysis"` → `t("nav.analysis")`
- Replace icon button aria-labels/titles: `"Settings"` → `t("nav.settings")`, `"About"` → `t("nav.about")`
- Export button: `"Export"` → `t("buttons.export")`

### 2. Footer (`src/components/Footer.tsx`)

- Add `const { t } = useTranslation();`
- `"Report a bug"` → `t("footer.reportIssue")`
- `"Feedback"` → `t("footer.giveFeedback")`
- Note: "Built with Bristlenose" may not be rendered by Footer — check if it's in About panel instead

### 3. SettingsPanel (`src/islands/SettingsPanel.tsx`)

- Add `const { t } = useTranslation("settings");` (settings namespace)
- `"Settings"` (h2) → `t("heading")`
- `"Application appearance"` → `t("appearance.legend")`
- `"Use system appearance"` → `t("appearance.auto")`
- `"Light"` → `t("appearance.light")`
- `"Dark"` → `t("appearance.dark")`
- `"Language"` → `t("language.legend")`
- `"Controls the display language..."` → `t("language.description")`
- `"Configuration reference"` → `t("configReference.heading")`
- Config reference intro paragraph → `t("configReference.intro")` (contains `<code>` — use `Trans` component or `dangerouslySetInnerHTML`)
- `"Click to copy"` → `t("configReference.clickToCopy")`
- `"Copied"` → `t("configReference.copied")`
- Keep `LOCALE_LABELS` hardcoded — native script names don't translate

### 4. ExportDialog (`src/components/ExportDialog.tsx`)

- `"Cancel"` → `t("buttons.cancel")`
- `"Export"` → `t("buttons.export")`
- Other strings (anonymise description, etc.) are NOT in current keys — skip

### 5. ConfirmDialog (`src/components/ConfirmDialog.tsx`)

- Default `confirmLabel="Delete"` → `t("buttons.delete")`
- `"Cancel"` → `t("buttons.cancel")`

### 6. ActivityChip (`src/components/ActivityChip.tsx`)

- `"Cancel"` → `t("buttons.cancel")`

### 7. Dashboard (`src/islands/Dashboard.tsx`)

- `"Loading dashboard…"` → `t("labels.loading")`

### 8. TranscriptPage (`src/islands/TranscriptPage.tsx`)

- `"Loading transcript…"` → `t("labels.loading")`

### 9. Sentiment badges (wherever rendered)

- Find where sentiment enum values are displayed as human-readable labels
- Replace with `t("sentiment.<key>", { ns: "enums" })`
- Keys: frustration, confusion, doubt, surprise, satisfaction, delight, confidence

### 10. Speaker roles (wherever rendered)

- Replace with `t("speakerRole.<key>", { ns: "enums" })`
- Keys: researcher, participant, observer, unknown

## Pattern

Every component follows the same pattern:

```tsx
import { useTranslation } from "react-i18next";

export function MyComponent() {
  const { t } = useTranslation(); // default "common" namespace
  // or: const { t } = useTranslation("settings");

  return <h2>{t("heading")}</h2>;
}
```

For the `enums` namespace from a component already using `common`:

```tsx
const { t } = useTranslation();
const { t: tEnum } = useTranslation("enums");

// ...
<span>{tEnum(`sentiment.${quote.sentiment}`)}</span>
```

## Config reference intro (HTML in translation)

The `configReference.intro` value contains `<code>.env</code>`. Options:
1. **`Trans` component** from react-i18next (preferred — type-safe)
2. **`dangerouslySetInnerHTML`** (simpler but less safe)
3. **Split into parts** (over-engineered)

Use `Trans`: `<Trans i18nKey="configReference.intro" ns="settings" components={{ code: <code /> }} />`

## Testing impact

- Existing tests that assert on English text (`getByText("Settings")`, `getByRole("tab", { name: "Quotes" })`) will still pass because `fallbackLng: "en"` means `t()` returns English when no locale is loaded in tests
- If any test mocks i18n or imports components that now use `useTranslation`, they may need an `I18nextProvider` wrapper — but typically `react-i18next` returns the key as fallback in test environments, so this shouldn't break
- Run `npm test && npm run build` to verify

## Verification

1. `npm test` — all 1072 tests pass
2. `npm run build` — tsc clean
3. `.venv/bin/python -m pytest tests/` — Python tests unaffected
4. Manual QA: `bristlenose serve --dev trial-runs/smoke-test`, switch to Espanol, verify:
   - Nav tabs: Proyecto, Sesiones, Citas, Libro de codigos, Analisis
   - Settings: heading, appearance options, language section all in Spanish
   - Footer: Spanish labels
   - Sentiment badges on quote cards: Spanish names
   - Switch back to English: everything reverts
5. Check no visual regression in English (pixel-identical)

## Not in scope (future work)

- ~180 hardcoded strings not yet in locale files (Tier 1-3 from design-i18n.md)
- Codebook translations (Phase 3)
- Feedback modal strings
- Keyboard shortcut descriptions
- Export dialog descriptions
