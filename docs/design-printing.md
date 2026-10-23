# Printing (post-v1)

**Status: not in v1.** On 23 Oct 2026 the owner withdrew printing from the Mac
app for v1. It needs its own design and debugging, and what printed was not a
deliverable a researcher could hand over. This note records what was measured,
what was taken out, and what bringing it back involves.

## What was measured, 23 Oct 2026

A Chromium print-to-PDF of the `project-ikea` report, Quotes lens. Four
defects:

1. **Quote cards below the fold print blank.** The card grid uses
   `content-visibility`, so cards the browser never rendered on screen have no
   content when the page is paginated. The printout has the right number of
   card-shaped gaps and nothing in most of them.
2. **The app chrome prints.** Tabs, icons, the minimap, the rails, the toggles
   and the footer all appear on the page. A print stylesheet exists,
   `bristlenose/theme/templates/print.css`, and the SPA loads it with the theme,
   but it was written for the static render: it hides that report's toolbar,
   view switcher and edit controls, and knows nothing of the SPA's chrome.
3. **Real names print whatever the Anonymise setting says.** Anonymise is a
   choice on the export save panel (`ExportAccessoryView`), and the print path
   never sees it. The printout renders whatever is on screen, real names
   included. For participant data, this is the defect that decides it.
4. **Nothing on the page says what it is.** There is no study name, date or
   lens heading, so a printed sheet separated from its stack cannot be
   identified.

The measurement was made in Chromium, not through the Mac app's
`NSPrintOperation` on the WKWebView. Defects 2–4 come from the page itself, so
they do not depend on the engine. Whether WebKit's print pagination honours
`content-visibility` differently has not been measured.

## What was taken out

- **File ▸ Page Setup… and File ▸ Print… (⌘P).** Both items are gone from
  `MenuCommands.swift`, and nothing else binds ⌘P: not the SPA's keyboard
  shortcuts, not the frozen report JS, and no SwiftUI default print group.
- **`com.apple.security.print`.** `ENABLE_RESOURCE_ACCESS_PRINTING = NO` in both
  configurations. R69 (`344c76bb`, 21 Oct 2026) had turned it on, so the
  print panel would open instead of the sandbox's "This application does not
  support printing".

## What holds it out

Each of these fails if the entitlement or the menu items come back:

- `tests/test_entitlements_split.py::TestTheSandboxRefusesPrinting` checks the
  pbxproj setting in both configurations, the three `.entitlements` files, and
  that both artefact gates refuse it.
- `desktop/scripts/check-pkg-shippable.sh` (`host print`) and
  `check-dmg-shippable.sh` (`print`) read the signed artefact. The pkg gate's
  negative fixture is case 8 in `test-check-pkg-shippable.sh`.
- `PrintEntitlementTests` (Swift) checks that the running host has no print
  entitlement, no menu item answers ⌘P, and no menu item has a print action or
  the Print or Page Setup title in any bundled locale.

## What is kept for later

- `PrintActions.swift` is unreferenced. Its native half is right: render the web
  view's current document with `NSPrintOperation`, set the operation view's
  frame explicitly, and attach the panel as a sheet to `PanelHost.window`.
- The locale keys `desktop.menu.file.print` and `desktop.menu.file.pageSetup`
  are still in all locales. `pageSetup` is registered as `RESERVED` in
  `tests/test_locale_key_readers.py`.
- The R69 record of how the sandbox refuses a print panel, and how to probe that
  refusal without hanging a test, is in `desktop/CLAUDE.md` and
  `docs/fix-the-menus.md`.

## Bringing it back

The four defects above are the design brief. To revive printing: design the
printed page first (`print.css` extended to the SPA's chrome, every card
rendered, the study identified, Anonymise honoured), then restore the menu items, set
`ENABLE_RESOURCE_ACCESS_PRINTING = YES`, and invert the pins listed above in the
same commit. The pins are one decision on purpose: a spike that prints behind
a flag would need the entitlement on, so it relaxes all of them or none. The
App Review justification R69 drafted is in
`docs/design-desktop-python-runtime.md`'s entitlement table.
