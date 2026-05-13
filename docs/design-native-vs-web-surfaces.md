# Native vs web surfaces

A pattern note for deciding which dialogs in Bristlenose go native (SwiftUI / AppKit) on macOS and which stay React. Drafted alongside the export-dialog rebuild that introduced `WKDownloadDelegate` + `NSSavePanel`. Pattern is currently N=2 (Settings done, Export landing); expect this doc to true up after a third concrete surface lands and validates or stresses the framing.

## Why

Every web-shaped modal inside the macOS WKWebView reads as wrapped-web-app. The native Settings re-implementation is the proof point: same data, same options, but no fake. The design driver isn't pixel-perfection or feature parity — it's *not feeling fake*.

The trick is doing it without forking 30 surfaces. We need a rule that tells us, given a new surface, whether it's worth the native translation, and an architecture that makes the translation cheap and reliable when it is.

## Surface inventory (May 2026)

| Component | Complexity | Native today? | Native candidate? | Why / why not |
|---|---|---|---|---|
| `ConfirmDialog` | S | no | yes (next surface to validate the pattern) | Maps to NSAlert *if body content stays plain text*. Rich-formatted bodies fail the rule. |
| `ExportDialog` | M | landing | yes | One option + destination → NSSavePanel + accessory view. |
| `SettingsModal` | M | **yes** (pattern proof) | done | Frequently-poked trust-signal surface; Mail-Accounts pattern + Keychain integration. |
| `FeedbackModal` | M | no | **no** | Free-text composition; web's textarea + paste-image + autosave behaviour > rebuilt-poorly native. |
| `HelpModal` | M | no | no | Reading-shaped, multi-section, no decision asked. Web is correct. |
| `AutoCodeReportModal` | M | no | no | Live data table; per-row actions; tightly coupled to web codebook state. |
| `ThresholdReviewModal` | L | no | no | Histogram + dual-slider + zone interaction. Native rebuild is a quarter of work for one screen. |
| `InspectorPanel` | L | no | no | Bottom-panel pattern, drag-resize, multi-tab. Web-shaped. |
| `AboutPanel`, `CodebookPanel`, `SettingsPanel` (full-tab islands) | — | n/a | no | Full report tabs, not modals. |

3 of 9 are native candidates; the pattern is restrictive on purpose.

## Routing rule

A surface is a native candidate when **a native primitive fits** — NSAlert, NSSavePanel, NSOpenPanel, NSSharingServicePicker, the `Settings` scene. If we'd be rebuilding from raw `NSWindow`, the cost outruns the gain.

Sanity-check the fit with three tells (none is an independent gate; they're the reasons the primitive exists):

- **Decision-shaped, not reading-shaped.** Choosing, not reading.
- **Few controls.** Toggle, radio, dropdown, text field, save destination. ≤3.
- **Ends in a native verb.** Save, Open, Confirm, Apply.

**Override:** trust-signal surfaces (first-run, error-recovery, Settings-shaped) go native even when no perfect primitive fits, because the cost of feeling fake on the surfaces a sceptical user pokes early is asymmetric.

**Anti-patterns** (don't go native even when the primitive looks like it fits):
- **Rich-formatted content.** NSAlert's `informativeText` is one string with limited formatting; ConfirmDialog with embedded quote markup loses the bake-off.
- **Free-text composition.** Native textareas underperform `<textarea>` for paste-image, autosave, IME-heavy languages.
- **Web-context triggers (right-click on a web element).** Routing to native introduces perceived latency that reads less native, not more.

## Dispatch shapes

**Intent-driven** — toolbar/menu/keyboard fires a native handler that shows the sheet. Web may also dispatch the same intent over the bridge (`postProjectAction`), but the handler is one. This is Settings.

**Platform-intercepted** — the web emits a standard event (`<a download>`, `window.print()`, file upload), WebKit hands it to a registered delegate, native shows the sheet. **No bridge growth.** This is Export. Strongly preferred when applicable, because the web codepath is unchanged.

Web fallback: every native candidate must work in `bristlenose serve` browser mode. Either WebKit interception covers browsers too (browsers have their own download UI), or the React modal renders conditionally on `!isDesktop()`.

## Data flow

- **Server-state writes** (option changes the export URL): native makes the HTTP call to `127.0.0.1:<port>` with its own auth (`_BRISTLENOSE_AUTH_TOKEN` env var).
- **Web-state writes** (option changes appearance/locale): native updates `UserDefaults`, then calls `bridgeHandler.menuAction(...)` — web listens and re-applies. This is Settings.
- **Reads** (sheet needs context — active project, current selection): bridge `BridgeState` already exposes the read-shaped fields. Extend only when an existing field doesn't suffice.

## Adding a new native surface

1. Does an OS primitive fit (NSAlert / NSSavePanel / etc.)? If no, stop. If yes, sanity-check against the three tells and the anti-patterns.
2. Pick dispatch shape — *platform-intercepted* if WebKit has an event for it, otherwise *intent-driven*.
3. Map options to native controls. If a control needs custom geometry, the primitive doesn't actually fit — revert to web.
4. Tripwire: if native glue exceeds ~100 lines or fights the layout, the rule mis-scored. Revert and stay web.
5. Verify both paths: sandbox-on for native, `bristlenose serve` in Safari for web fallback.

## What this is NOT

- **Not a mandate to native-rebuild every modal.** The rule is restrictive on purpose. Most modals stay web.
- **Not a brand-style guide.** Native means using OS primitives, not "look native-ish." Styling a `<div>` to look like NSAlert fails the test.
- **Not a bridge-expansion plan.** Platform interception is preferred precisely because no bridge growth is required.
- **Not free.** Each native surface is two implementations to test, localise, and maintain. The rule's restrictiveness is the cost-control.

## Open questions / known gaps

- **N=2 risk.** ConfirmDialog will be the first new application of the rule. If body-formatting forces an exception this note doesn't anticipate, the rule needs revising.
- **Hybrid trigger + dispatch** (toolbar button = intent, web `<a download>` = platform-intercepted, both in one flow — what Export actually does) is the cleanest shape we've found and isn't fully named here. Document properly once Export ships.
- **Cost estimates** intentionally absent — the previous draft had ~30min / ~2d / ~1w tiers; reviewers flagged them as fictional precision.
