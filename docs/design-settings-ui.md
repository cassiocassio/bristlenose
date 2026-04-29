---
status: partial
last-trued: 2026-04-29
trued-against: HEAD@main on 2026-04-29
---

> **Truing status:** Partial — Phase 1 (web gear-icon modal, `SettingsModal.tsx`, `ModalNav.tsx`, `⌘,` shortcut) **shipped**; Phases 2/3/4 remain pending as described. The "API Keys" section is architecturally superseded for the desktop-embedded deployment — see banner there. The serve-mode CLI path still applies when running `bristlenose serve` outside the sandboxed desktop app.

## Changelog

- _2026-04-29_ — trued: Tier 1 table updated to 5 providers (added Ollama as Local, no key); §Add new key step 3 annotated to call out that no live API roundtrip validation is shipped on either surface (desktop LLMSettingsView is Keychain-presence-only; web SettingsModal API Keys is `<StubSection>`); cross-reference to AIConsentView added.
- _2026-04-21_ — trued up: marked Phase 1 as shipped with anchors; fixed `bristlenose credential` → `bristlenose configure` (shipped command name, 2 occurrences); added "Shipping status (Apr 2026)" callout; added supersedence banner to §API Keys pointing at `design-desktop-settings.md` + `design-keychain.md` §Desktop credential path; corrected "Existing infrastructure → Config loading" claim (keychain lookup is in `credentials.py`, not `config.py`); added cross-references to `design-desktop-settings.md`. Anchors: `frontend/src/components/SettingsModal.tsx:414`, `frontend/src/components/ModalNav.tsx`, `frontend/src/layouts/AppLayout.tsx:17,162,171,545`, `frontend/src/hooks/useKeyboardShortcuts.ts:284`, `bristlenose/cli.py:1613`. Preserved: Phase 2/3/4 plans (still correct, still pending).

# Settings UI — API Keys & Provider Switching

How Bristlenose lets users manage LLM credentials and switch providers from the serve-mode GUI.

_Last updated: 2026-04-21_

> **Shipping status (Apr 2026):**
> - **Phase 1** ✅ shipped — web gear-icon `SettingsModal` with `ModalNav`, `⌘,` shortcut, settings card migration from About panel. Anchors: `frontend/src/components/SettingsModal.tsx:414`, `frontend/src/components/ModalNav.tsx`, `frontend/src/layouts/AppLayout.tsx:17,162,171,545`, `frontend/src/hooks/useKeyboardShortcuts.ts:284`.
> - **Phase 2** (API key CRUD endpoints, keychain validation) — pending. API Keys section in `SettingsModal.tsx` is currently a `<StubSection>`.
> - **Phase 3** (project settings endpoints) — pending. No `/api/projects/{id}/settings` routes.
> - **Phase 4** (appearance/language migration) — pending. Currently still in About panel.
> - **Desktop embedded path**: sandboxed alpha bypasses the Phase-2/3 web API Key flow entirely — Swift SwiftUI Settings writes to Keychain, injects env vars to the sidecar. See §API Keys banner below, `design-desktop-settings.md`, and `design-keychain.md` §Desktop credential path.

---

## The problem

Bristlenose has ~30 configurable settings. The only way to change them today is via environment variables, `.env` files, or CLI flags. This works for CLI users, but serve-mode and desktop app users need a GUI for the most common operations: managing API keys and switching providers.

The full settings surface is large, but the urgent need is narrow: **safe CRUD of LLM API keys and switching between providers.** Everything else has reasonable defaults.

First-run onboarding (no keys at all, no project) belongs in the **macOS desktop app** — SwiftUI setup wizard, Keychain entry, folder picker. The serve-mode settings modal assumes the user already has at least one working key.

---

## Scope — what goes in the GUI vs stays CLI-only

### Tier 1 — Must have in GUI (blocks provider switching)

| Setting | Scope | Why GUI |
|---------|-------|---------|
| API keys (Claude, ChatGPT, Gemini, Azure) — and Ollama URL (Local, no key) | App-wide | Can't analyse without one of the five providers configured |
| Active LLM provider | Per-project | Must match an available key |
| LLM model | Per-project | Power users want to pick model |

### Tier 2 — Should have (improves experience, has defaults)

| Setting | Scope | Default |
|---------|-------|---------|
| Whisper backend | App-wide | `auto` |
| Whisper model | Per-project | `large-v3-turbo` |
| Whisper language | Per-project | `en` |
| PII redaction | Per-project | `off` |

### Stays CLI-only

Temperature, max_tokens, concurrency, Azure multi-field config, Ollama URL/model, quote extraction params, pipeline flags, thumbnail params, logging, timing. The Configuration Reference panel (already in the Settings tab) documents all of these.

### Already done (client-side only)

- Appearance toggle (auto/light/dark)
- Language selector (6 locales)

These move into the settings modal as part of this work.

---

## App-wide vs per-project

Two distinct scopes with different storage:

### App-wide (identity, hardware, preferences)

These describe the *user and their machine*, not a research study.

| Setting | Why app-wide |
|---------|-------------|
| API keys | You're the same person across projects |
| Default LLM provider | Personal preference |
| Appearance | Personal preference |
| Language | Personal preference |
| Whisper backend/device | Hardware-dependent |

**Storage**: Keychain (API keys), localStorage (appearance, language — already working), app-wide config file or a new mechanism (default provider, whisper backend).

### Per-project (research decisions)

These describe the *study*, not the user.

| Setting | Why per-project |
|---------|----------------|
| LLM provider override | "This client requires Azure" |
| LLM model | "Use the big model for this important study" |
| Whisper language | "This study is in Spanish" |
| Whisper model | "Small model is fine for these short clips" |
| PII redaction | "This study has sensitive participant data" |

**Storage**: SQLite `settings` table in the project database.

**Fallback chain**: project DB → env var → `.env` → default. Existing `.env` configs keep working. The GUI adds a higher-priority layer.

---

## Existing infrastructure

### Credential storage (complete)

| Layer | File | CRUD |
|-------|------|------|
| Abstract store | `credentials.py` | `get`, `set`, `delete`, `exists` |
| macOS Keychain | `credentials_macos.py` | Full CRUD via `security` CLI |
| Linux Secret Service | `credentials_linux.py` | Full CRUD via `secretstorage` |
| Env fallback | `credentials.py` | Read-only |
| Desktop (Swift) | `KeychainHelper.swift` | Full CRUD, same service names |

Python and Swift share the same Keychain entries. A key saved via CLI is visible to the desktop app and vice versa.

### CLI credential command (complete)

`bristlenose configure <provider>` — validates key with test API call, stores in keychain. See `bristlenose/cli.py:1613`.

### Config loading (complete)

`config.py` → `BristlenoseSettings` (Pydantic) — loads env vars + `.env`. Keychain lookup lives in `bristlenose/credentials.py` (`_populate_keys_from_keychain`, `bristlenose/config.py:137-178`), not in `config.py` directly; the two cooperate via the credential store protocol.

---

## Design

### Settings as a modal dialog

Settings open as a **modal dialog with internal sidebar navigation** — similar to Claude's macOS app settings or VS Code settings. Not a tab, not a page.

Triggered by a settings gear icon in the nav bar, or `⌘,` (`Ctrl+,` on non-Mac).

```
┌──────────────────────────────────────────────────┐
│ Settings                                    [×]  │
│                                                  │
│  ┌──────────┐ ┌──────────────────────────────┐   │
│  │ General  │ │                              │   │
│  │ Project  │ │  (content for selected       │   │
│  │ Profile  │ │   category)                  │   │
│  │ API Keys │ │                              │   │
│  │ Config   │ │                              │   │
│  │          │ │                              │   │
│  └──────────┘ └──────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
```

Five nav categories:

1. **General** — the 80/20 quick settings: appearance, language, default provider. Opens by default. The things users change often
2. **Project** — per-project preferences: PII redaction, and more TBD
3. **Profile** — who you are: name, email, whisper backend
4. **API Keys** — named key list with full CRUD: click row to select, edit name/key separately, delete, add new
5. **Config** — disclosure triangle in the sidebar that expands to show 12 indented sub-categories. Currently read-only reference — individual items graduate to editable controls over time

```
  ▶ Config
```
expands to:
```
  ▼ Config
      LLM Provider & Model
      Transcription
      Privacy
      Quotes
      Analysis
      AutoCode
      Display
      Pipeline
      Thumbnails
      Server
      Logging
      Timing
```

Clicking a sub-category shows that category's settings in the content pane (env var name, current value, default, valid options). This is the existing `CONFIG_DATA` from `SettingsPanel.tsx` reorganised into the modal's sidebar navigation.

"General" is the first nav item and the default landing page — the things you reach for most often. "Settings" is the modal title only. This avoids the confusing self-referential pattern of a "Settings" section inside a "Settings" dialog.

### General section (default landing)

The 20% of settings users need 80% of the time. Opens when the modal launches.

- **Appearance** — auto/light/dark radio (existing, moved here)
- **Language** — locale selector (existing, moved here)
- **Default provider** — dropdown (only providers with a configured key). When no keys are configured, show "No API keys configured" with a link to the API Keys section. The full key management lives in the API Keys section

Deliberately sparse to start. As we learn what users reach for, more items migrate here from Project or Profile. The bar for inclusion: "do users change this more than once per week?"

### Project section

Per-project preferences. Stored in the project's SQLite database (`settings` table). Overrides app-wide defaults.

- **PII redaction** — hide/show toggle (redact names and identifying information from transcripts). Per-project because sensitivity varies by study

More candidates TBD — LLM provider/model override, whisper language, project name. Will be determined as we learn which settings researchers actually want to vary between studies.

### Profile section

Who you are. Set once, used across all projects.

- **Name** — researcher's display name (used in exports, reports, "analysed by")
- **Email** — contact email (used in exports, optional)
- **Whisper backend** — auto/mlx/faster-whisper

Room for more personal settings over time (e.g. organisation name, default codebook preference).

### API Keys section

> **Architecturally superseded for the desktop-embedded case as of 2026-04-21.** In the sandboxed macOS alpha, Swift owns Keychain CRUD — SwiftUI Settings → LLM tab writes entries; `ServeManager.overlayAPIKeys` injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars into the Python sidecar; Python never touches Keychain. The list UI below is the correct design for **serve-mode CLI use** (running `bristlenose serve` outside the sandbox). For the embedded path see `design-desktop-settings.md` §Tab 2 LLM and `design-keychain.md` §Desktop (sandboxed) credential path. Body retained — the web-UI list design still applies when not embedded.

A list of all configured keys. Click a row to make it the active key. Actions on hover or via kebab menu.

```
 Name              Provider        Status
 ─────────────────────────────────────────────
 Work key          Claude          ● Active        ⋮
 Personal key      ChatGPT         ○ Ready         ⋮
 Client project    Azure OpenAI    ○ Ready         ⋮
 Old key           Claude          ✕ Invalid       ⋮

                               [+ Add new key]
```

**Columns:**
- **Name** — user-chosen label (e.g. "Work key", "Client project", "Personal"). Lets researchers manage multiple keys for the same provider
- **Provider** — Claude, ChatGPT, Gemini, Azure OpenAI
- **Status** — Active (currently in use), Ready (valid, not selected), Invalid (last test failed), Unknown (not yet tested)
- **Row click** — selects this key as the active key (like a radio list)
- **Kebab menu (⋮)** — Rename, Replace key, Test, Delete

**Key masking**: first 7 + last 4 characters, dots in the middle. Full key never sent to frontend — only the masked version.

**Source indicator**: keys from env vars or `.env` are read-only in the GUI — show a hint: "Set via environment variable. Remove the env var to manage here."

#### Multiple keys per provider

A researcher might have a personal Claude key and a work Claude key, or keys for different billing accounts. The list supports multiple keys for the same provider. Only one key is active at a time — clicking a different row switches it.

#### Add new key

1. Click `[+ Add new key]`
2. Form appears: Name (text), Provider (dropdown), Key (password input)
3. Save button shows "Validating..." spinner during API round-trip (form disabled during validation) — **note: as of 29 Apr 2026, no shipped surface implements live API roundtrip validation. Desktop `LLMSettingsView` saves to Keychain on blur; status dot reflects Keychain presence only. The web `SettingsModal` API Keys section is still a `<StubSection>`. Live validation is the design intent for both, not the shipped reality. AIConsentView gates first LLM use on consent version, not on key validity.**
4. Success → stores in Keychain → row appears in list
5. Failure → inline error message, form stays open

#### Rename key

Kebab → Rename → inline edit of the name field only. Does not touch the key value.

#### Replace key

Kebab → Replace key → password input appears. Must re-enter full key. Save button shows "Validating..." spinner during test. On success, updates Keychain entry.

Separate from Rename — changing a key's name should never require re-pasting the secret.

#### Delete key

1. Kebab → Delete → confirmation dialog
2. If deleting the active key: "This is your active key. Deleting it will prevent analysis until you select another."
3. If deleting the **only** key: stronger warning: "This is your only configured key. You will not be able to run analysis until you add a new one."
4. Removes from Keychain

---

## Accessibility

### Dialog semantics

- `role="dialog"` + `aria-modal="true"` + `aria-labelledby` pointing to the "Settings" heading
- **Focus trap** — implement at the atom level as a shared `useModalAccessibility` hook or `<ModalShell>` wrapper, then retrofit to all existing modals (HelpModal, ExportDialog, FeedbackModal, AutoCodeReportModal, ThresholdReviewModal). No existing modal has a focus trap today — building it for settings alone creates inconsistency
- **Focus on open** — move focus to the close button
- **Focus restore on close** — return focus to the gear icon
- **Escape** closes the modal

### Gear icon trigger

`<button aria-label="Settings" aria-haspopup="dialog">` in the nav bar. Receives focus restoration on modal close.

### Sidebar nav keyboard model

- Tab moves between nav items (standard `role="navigation"` landmark with `aria-current="page"` on active item)
- Enter/Space activates a nav item and moves focus to the content pane heading (`<h2 tabindex="-1">`) so screen readers announce the section change
- **Disclosure sub-items** — Enter/Space on Config expands and moves focus to first sub-item. `aria-expanded="true|false"` on the disclosure `<button>`, `aria-controls` pointing to the sub-list `<ul>` id

### API Keys keyboard model

- Key rows form a radio group (`role="radiogroup"`, each row `role="radio"`). Arrow Up/Down moves between rows; Space/Enter selects the active key
- Kebab button: `aria-haspopup="menu"` + `aria-expanded`. Menu: `role="menu"` + `role="menuitem"`, arrow keys navigate, Escape closes and returns focus to kebab
- Inline rename: activation moves focus to text input (EditableText pattern — Enter commits, Escape cancels)
- Password inputs: `aria-label="API key"`, `autocomplete="off"`

### Delete confirmation

Nested `role="alertdialog"` with `aria-describedby` pointing to the warning text. Focus moves to Cancel button on open (safe default for destructive actions). Escape = Cancel.

### Async feedback

`aria-live="polite"` region in the API Keys content area announces: "Validating key...", "Key validated successfully" / "Key validation failed: {error}", "Key deleted", "Key renamed to {name}".

### Status indicators

- Active: `var(--bn-colour-accent)` + filled circle icon
- Ready: `var(--bn-colour-muted)` + open circle icon
- Invalid: `var(--bn-colour-danger)` + cross icon

Each status uses colour + icon shape + text label (three redundant cues — colour is never the sole indicator).

### Reduced motion

`@media (prefers-reduced-motion: reduce)` disables overlay fade transition and disclosure triangle rotation (instant state changes). Follows existing precedent in `sidebar.css`.

### Responsive dropdown (≤500px)

Prefer native `<select>` element for guaranteed accessibility. If custom dropdown is needed: `role="listbox"` + `role="option"`, `aria-expanded`, `aria-activedescendant`, arrow key navigation, Escape to close.

---

## Responsive behaviour

At narrow viewports (below `--bn-breakpoint-compact`, 500px), the two-column sidebar+content layout doesn't fit.

**Collapse strategy**: sidebar becomes a dropdown selector at the top of the modal. Content pane takes full width.

```
┌──────────────────────────────┐
│ Settings                [×]  │
│                              │
│  [General ▾]                 │
│                              │
│  (content for selected       │
│   category, full width)      │
│                              │
└──────────────────────────────┘
```

The dropdown contains the same 5 items. Config sub-categories appear as indented items in the dropdown when Config is selected. This is a CSS-only change — the `ModalNav` component renders both layouts, switching via `@media (max-width: 500px)`.

---

## API endpoints

### Credentials (Keychain CRUD — app-wide)

```
GET    /api/credentials
       → [{ provider, masked_key, source, is_active }]

POST   /api/credentials/{provider}
       Body: { "key": "sk-ant-..." }
       → { provider, masked_key, source, valid, error? }

DELETE /api/credentials/{provider}
       → { ok: true }

POST   /api/credentials/{provider}/test
       → { valid, error?, latency_ms? }
```

### Project settings (per-project)

```
GET    /api/projects/{id}/settings
       → { llm_provider, llm_model, whisper_language, pii_enabled, ... }

PATCH  /api/projects/{id}/settings
       Body: { "llm_provider": "openai" }
       → updated settings
```

### Security

- Keys never returned unmasked, never logged, never in URLs
- Validated before storage (test API call)
- Localhost-only binding (no external access)

---

## Data model

### SQLite settings table (new, per-project DB)

```sql
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Simple key-value. `CREATE TABLE IF NOT EXISTS` — no migration framework needed.

### App-wide default provider

Needs a home. Options:

| Option | Pros | Cons |
|--------|------|------|
| `~/.config/bristlenose/settings.json` | Standard XDG, survives project deletion | New file, new loader |
| `.env` rewrite | Matches current system | Fragile, editing dotfiles programmatically |
| localStorage in frontend | Already works for appearance | Not visible to CLI/pipeline |

**Recommendation**: `~/.config/bristlenose/settings.json`. Tiny file, read at startup, written by the settings API. CLI can read it too. But this can wait — for Phase 1, the env var / `.env` default is fine. The per-project override in SQLite covers the GUI use case.

---

## Implementation plan

### Phase 1 — Modal shell + Settings page

Build the container and the most-used section. Stub the rest.

**Reusable `ModalNav` component** — the sidebar-nav-with-content-pane pattern is generic. About/Help will move into the same structure later, so the nav component is not settings-specific.

#### Layout spec

**Modal dimensions:**
- Max-width: `42rem` (672px) — wide enough for nav+content, not overwhelming
- Max-height: `80vh` — triggers scroll when content overflows
- Width: `90%` (inherits from `.bn-modal`, responsive on narrow viewports)

**Sidebar nav (fixed width):**
- Width: `11rem` (176px) — enough for "API Keys" and Config sub-categories
- Border-right: `1px solid var(--bn-colour-border)`
- Overflow-y: `auto` — scrolls independently when Config is expanded
- Padding: `var(--bn-space-md) 0` top/bottom; items get `var(--bn-space-xs) var(--bn-space-md)`

**Content pane (fluid):**
- Flex: `1` (takes remaining ~31rem / 496px)
- Overflow-y: `auto` — scrolls independently
- Padding: `var(--bn-space-lg)` all sides

**Nav item styling** (borrows from `.toc-link` in `sidebar.css`):
- Font-size: `var(--bn-text-body-sm)` (13px), line-height: `var(--bn-text-body-sm-lh)` (1.45)
- Active: `var(--bn-weight-emphasis)` + `var(--bn-colour-accent)` + `var(--bn-colour-hover)` bg
- Hover: `var(--bn-colour-hover)` bg
- Border-radius: `var(--bn-radius-sm)`
- Disclosure triangle: CSS `::before` `▶`/`▼`, `font-size: 0.6em`, rotation transition
- Indented sub-items: `padding-left: calc(var(--bn-space-md) + 1rem)`, muted when inactive

**Future-proofing:**
- `ModalNav` accepts optional `searchSlot` prop — DOM slot above nav list, zero height when unused. Adding search later doesn't require restructuring
- Both sidebar and content are independently scrollable from day one

#### Design system reuse

**Atoms (no changes):** `.bn-overlay`, `.bn-modal` (override max-width), `.bn-modal-close`, `.bn-checkbox`

**Organisms (no changes):** `.bn-setting-group`, `.bn-radio-label`, `.bn-locale-select`, `.bn-setting-description`, `.bn-config-ref-*`

**Patterns from existing sidebar:** `.toc-link.active` tokens, `.session-entry:hover` hover, `.toc-sidebar-body` independent scroll

**New CSS (one file — `organisms/settings-modal.css`):**
- `.settings-modal` — max-width override
- `.modal-nav` — two-column flex. Reusable (not settings-specific)
- `.modal-nav-sidebar`, `.modal-nav-item`, `.modal-nav-disclosure`, `.modal-nav-sub`, `.modal-nav-content`, `.modal-nav-search`

No new atoms or tokens.

#### New files
- `frontend/src/components/ModalNav.tsx` — reusable sidebar-nav modal shell
- `frontend/src/components/SettingsModal.tsx` — settings content using ModalNav
- `frontend/src/components/SettingsModal.test.tsx`
- `bristlenose/theme/organisms/settings-modal.css`

#### Modified files
- `frontend/src/layouts/AppLayout.tsx` — gear icon, render SettingsModal
- `frontend/src/hooks/useKeyboardShortcuts.ts` — `⌘,` handler
- `frontend/src/islands/SettingsPanel.tsx` — extract constants for reuse
- `frontend/src/components/HelpModal.tsx` — add `⌘,` to shortcut list
- `frontend/src/router.tsx` — remove `/report/settings` route
- `bristlenose/stages/s12_render/theme_assets.py` — add CSS to `_THEME_FILES`

#### Steps
1. Create `ModalNav.tsx` (generic: sections array, disclosure, search slot, scroll)
2. Create `SettingsModal.tsx` (5 sections, General page functional, rest stubbed)
3. Create `settings-modal.css` (all `.modal-nav-*` classes + `.settings-modal` override)
4. Wire into AppLayout (gear icon + render)
5. Add `⌘,` shortcut
6. Update HelpModal shortcut list
7. Remove Settings tab from router
8. Accessibility (role="dialog", focus trap, focus restore, aria-expanded on disclosure)
9. Responsive collapse (dropdown selector at ≤500px)
10. Tests (open/close, nav switching, disclosure, appearance, language, focus management)

### Phase 2 — API Keys section

9. Credential CRUD endpoints in `routes/settings.py`
10. Key masking utility
11. API Keys list (click-to-select rows, kebab menu: rename, replace key, test, delete)
12. Named keys in SQLite (maps name → provider + keychain ref)

### Phase 3 — Project settings

13. `settings` table in `db.py`
14. `PATCH /api/projects/{id}/settings` endpoint
15. Project section content
16. `load_settings()` integration — project DB overrides env vars in serve mode

### Phase 4 — Profile + Tier 2 settings

17. Profile section (name, email, whisper backend)
18. App-wide defaults file (`~/.config/bristlenose/settings.json`)
19. Config sub-categories become editable (graduated from read-only)

---

## Gap analysis: all settings by surface

| Setting | `.env` | CLI | Keychain | GUI today | GUI proposed | Scope |
|---------|--------|-----|----------|-----------|-------------|-------|
| **API keys (4)** | Yes | `credential` | Yes | Ref only | **Phase 1** | App-wide |
| **LLM provider** | Yes | `--llm` | — | Ref only | **Phase 1** | Per-project |
| **LLM model** | Yes | — | — | Ref only | **Phase 2** | Per-project |
| **Appearance** | Yes | — | — | **Done** | Move to modal | App-wide |
| **Language** | — | — | — | **Done** | Move to modal | App-wide |
| **Whisper backend** | Yes | `--whisper-backend` | — | Ref only | Phase 3 | App-wide |
| **Whisper model** | Yes | `--whisper-model` | — | Ref only | Phase 3 | Per-project |
| **Whisper language** | Yes | — | — | Ref only | Phase 3 | Per-project |
| **PII redaction** | Yes | `--redact-pii` | — | Ref only | Phase 3 | Per-project |
| Azure endpoint etc. | Yes | — | — | Ref only | Stays CLI | — |
| Ollama URL/model | Yes | — | — | Ref only | Stays CLI | — |
| Temperature | Yes | — | — | Ref only | Stays CLI | — |
| Max tokens | Yes | — | — | Ref only | Stays CLI | — |
| Concurrency | Yes | — | — | Ref only | Stays CLI | — |
| Quote params | Yes | — | — | Ref only | Stays CLI | — |
| Pipeline flags | Yes | CLI | — | Ref only | Stays CLI | — |
| Thumbnail params | Yes | — | — | Ref only | Stays CLI | — |
| Logging/timing | Yes | — | — | Ref only | Stays CLI | — |

---

## Concurrency and state conflicts

The Settings UI introduces a third mutation surface for configuration (alongside CLI and desktop app). Analysis of how these interact:

### What's safe today

- **Keychain is atomic.** CLI (`bristlenose configure`), desktop app (`KeychainHelper.swift`), and the new web UI all write to the same macOS Keychain entries. Keychain handles concurrent access — last writer wins, no corruption. *Note: in the sandboxed-desktop deployment, the web UI never writes Keychain — Swift does. See `design-desktop-settings.md`.*
- **Settings are not cached in serve mode.** `load_settings()` is called fresh per-request in routes that need it (AutoCode, elaboration). A Keychain change from CLI is picked up on the next serve-mode request without restart.
- **SQLite WAL mode** serialises writers. CLI pipeline and serve mode can both access the same project DB safely. Writes queue; no data corruption.

### Known stale-state scenarios

| Change | CLI picks up? | Serve picks up? | Action needed |
|--------|:---:|:---:|---|
| Keychain write (any surface) | Yes (next run) | Yes (next request) | None |
| `.env` file edit | Yes (next run) | **No** (loaded at process start) | Restart serve |
| Shell `export` of env var | Yes (next run) | **No** (separate process env) | Restart serve |
| SQLite write from CLI pipeline | — | Yes (next DB read) | Page refresh |
| SQLite write from web UI | Yes (next DB read) | — | None |
| localStorage change in browser | — | N/A (client-only) | None |

### Risks introduced by Settings UI

1. **Web UI writes project settings to SQLite while CLI is running.** Both mutate the same `settings` table. SQLite WAL serialises writes, so no corruption, but last-writer-wins means a CLI override could silently undo a web UI change (or vice versa). **Mitigation**: the `settings` table is key-value with `INSERT OR REPLACE` semantics — individual keys don't conflict unless both surfaces change the same key simultaneously. In practice, CLI flags are transient (per-run, not persisted) so this is unlikely.

2. **Web UI writes credentials while `.env` has a different key.** The priority chain is: project DB → Keychain → env var → `.env` → default. If the web UI writes to Keychain and `.env` also has a key, Keychain wins (checked first). This is correct but could confuse users who expect `.env` to take precedence. **Mitigation**: the API Keys section shows the source label ("Keychain" vs "Environment variable") so users can see where the active key came from.

3. **Stale `.env` in serve mode.** If a user edits `.env` while serve is running, the server keeps the old values. The web UI can't fix this — it writes to Keychain/SQLite, not `.env`. **Mitigation**: document that `.env` changes require server restart. Long-term: add a "Reload settings" action or file watcher.

### Design decisions

- **Don't write to `.env` from the web UI.** Programmatically editing dotfiles is fragile and surprising. The web UI writes to Keychain (credentials) and SQLite (project settings). `.env` remains the CLI/power-user surface.
- **Show source labels.** Every setting in the UI shows where its value comes from (Keychain, env var, config file, default). This makes the priority chain visible.
- **No locking between CLI and web UI.** SQLite WAL is sufficient. Adding application-level locks would add complexity for a scenario (simultaneous CLI pipeline + web settings change) that rarely occurs in practice.
- **External change indicator.** When the modal fetches fresh values, compare against last-seen state. If a value changed recently, show a relative timestamp next to it: "just now", "3 minutes ago", "2 hours ago". Changes older than 24 hours are not flagged — they're no longer news. Keeps the UI clean while making CLI/env edits visible.

---

## Open questions

1. ~~**Model list**~~ — **deferred.** Hardcoded vs fetched from provider, "Custom" text input. Decide when we build the provider/model UI.

2. ~~**What happens to the Settings tab?**~~ — **decided: Config moves into the modal** as the fourth nav item. The Settings tab becomes redundant — remove it, replace with a gear icon in the nav bar that opens the modal.

3. ~~**Keyboard shortcut**~~ — **decided: `⌘,`** (macOS convention for settings). `Ctrl+,` on other platforms. Add to `useKeyboardShortcuts.ts` and the HelpModal shortcut list.

---

## References

- **Credential store**: `bristlenose/credentials.py`, `credentials_macos.py`, `credentials_linux.py`
- **CLI credential command**: `bristlenose/cli.py` lines 1579–1709
- **Config loading**: `bristlenose/config.py`
- **Desktop keychain**: `desktop/Bristlenose/Bristlenose/Model/KeychainHelper.swift`
- **Existing settings panel**: `frontend/src/islands/SettingsPanel.tsx`
- **Settings CSS**: `bristlenose/theme/organisms/settings.css`
- **Desktop app design**: `docs/design-desktop-app.md`
