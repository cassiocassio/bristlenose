# Hero shots — spike status

Autogenerating light/dark screenshots of the **native** window for the docs.
Conventions and the wider illustration ladder live in
[`docs/design-docs-system.md`](../../docs/design-docs-system.md) Part D; this
file is only "where the spike got to".

Native rather than a browser tab because the docs double as a brochure — the
Mac frame is part of what is being sold, and the native window already contains
the SPA, so one capture gets both the chrome and the report content.

## What works

`capture.py` finds the window via Quartz, switches appearance, and captures
with real rounded corners and a live shadow. Verified: the two captures in
`shots/` are genuinely different files, so the appearance switch reaches the
app.

```
uv run --with pyobjc-framework-Quartz python capture.py --list
uv run --with pyobjc-framework-Quartz python capture.py --out shots
```

Needs **Screen Recording**, granted *per process* — a terminal that has it does
not confer it on other tooling.

## Two things that cost time, so they are written down

**Appearance is the app's own preference, not the system's.** The app stores
`appearance` (auto|light|dark) via `@AppStorage` in the `app.bristlenose`
domain. The first run flipped *system* appearance, the app was pinned to light,
and both captures came back byte-identical — which looks like success in a file
listing. That is why the run now gates its exit code on the pair not being
identical.

**The UserDefaults domain IS the bundle identifier.** Holding it as two
constants let one copy drift onto the retired `research.bristlenose.app`, which
broke `--relaunch` silently while the `defaults` half kept working. One
constant, `BUNDLE_ID`.

## Open questions

- Does `@AppStorage` notice an external `defaults write` in a *running* app?
  cfprefsd caching makes it uncertain. `--relaunch` is the deterministic
  fallback (quit + reopen between modes).
- `--window <id>` cannot survive a relaunch — new ids get minted. It errors
  rather than capturing whatever inherited the number.

## Blocked on, and it is not a scripting problem

**State-driving is stubbed.** The `export-menu` entry's AppleScript addresses a
SwiftUI toolbar button through the accessibility hierarchy and is fragile.
Resist improving it — that is the signal to go app-side instead.

**Output is not publishable yet.** Captures currently show development state:
sidebar folders named "New Foldasdfaer", tags reading "Chocolate / Cold /
Booze / one / two / three", and the debug footer
(`v0.23.0 · main · … · Debug · sandbox=on HR=off · sidecar=bundled`) in every
frame. Fine for QA, fatal for a brochure.

The fix for both is the same and it is app-side: a **`--screenshot-mode` launch
argument** — curated fixture project, onboarding suppressed, debug footer
hidden, window sized, appearance forced. That is the load-bearing piece, since
it makes even *manual* capture repeatable and presentable. This script is the
cheap half. Part D §D4 has the sequencing.

The content half is already solved: the synthetic Fishkeeping dataset
(`docs/testing/test-data-generation.md`) is generated rather than recorded, so
it carries no participant-data constraint. What it does not fix is the shell
state around it — folder names, project names, tag vocabulary — which lives in
app preferences, not in the dataset.
