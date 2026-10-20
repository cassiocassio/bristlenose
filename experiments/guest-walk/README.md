# Guest walk — proof of concept (20 Oct 2026)

**Productionised the same day:** the scripts moved to `desktop/scripts/guest-walk/` and run
nightly from `guest-matrix.sh`; the design is `docs/design-guest-walk.md`. This folder keeps
the spike's record (this file, `COVERAGE.md`) and `vision-probe.swift`.

A nightly click-through of the Mac app inside a tart guest, diffed against the
last accepted walk, with the changed screens painted pink. Two halves:

- **What we'd see:** [`docs/mockups/guest-walk-diff.html`](../../docs/mockups/guest-walk-diff.html)
  (invented data, ~100 screens), and the real page this spike generates
  (`out/change/index.html`, `out/noise/index.html`; gitignored, regenerate below).
- **Can we drive it:** `walker.swift` + `walk.sh`, run against the signed 0.42.0
  Developer-ID build in a clone of the `tahoe` guest.

It builds on the overnight guest matrix (`desktop/scripts/guest-matrix.sh`,
`docs/design-test-environments.md` §3.6–3.7) and its recipe on Iona
(`/Volumes/Iona/tart/bin/README.md`).

## Files

| File | What |
|---|---|
| `walker.swift` | One CLI, built on the host, run in the guest via `tart exec`. Finds elements **by name** through the accessibility API: press buttons and menu items by path, read the whole menu tree (title, enabled, shortcut) as JSON lines, wait for a window or an element, set a field's value without keystrokes, screenshot every window. `walker diff` (host side) is the pixel diff: CoreGraphics, no dependencies, masks, pink overlay |
| `walk.sh` | One walk. Each step acts, **asserts the state it should produce**, and captures window + menu tree. A failed step halts with a screenshot and the reason in `verdict.txt` |
| `report.py` | Two walks → the morning page. Standard library only |
| `g.sh`, `pull.sh` | `tart exec` into the guest; rsync results back (the share is read-only) |

## Run it

```bash
export TART_HOME=/Volumes/Iona/tart
tart clone tahoe bn-walk && tart set bn-walk --cpu 4 --memory 8192
(cd / && nohup tart run bn-walk --dir="walk:/Volumes/Iona/tart/share/bn-walk:ro" >/dev/null 2>&1 &)
# stage Bristlenose.app as a tarball + the smoke fixture in /Volumes/Iona/tart/share/bn-walk,
# untar into the guest's /Applications (ditto from VirtioFS breaks bundles)
swiftc -O -target arm64-apple-macos15.0 walker.swift -o /Volumes/Iona/tart/share/bn-walk/walker
cp /Volumes/Iona/tart/share/bn-walk/walker walker-host
OUT=/tmp/bn-walk ./walk.sh base && OUT=/tmp/bn-walk ./walk.sh tonight
python3 report.py /tmp/bn-walk/base /tmp/bn-walk/tonight out/tonight
```

## Measured (20 Oct 2026, macOS 26.6.2 guest, app 0.42.0 (5269))

- **A walk of 15 steps / 19 captures takes about 61 s**, start to pulled results: ~4 s
  a step, so a 100-step walk is ~7 min plus the run itself. An hour is far more than needed.
- **Three consecutive walks all completed.** Each starts from a fresh app container.
- **Noise floor: 0 of 19 screens changed** between two unchanged walks, once three
  regions are masked (each mask is printed on the page with its reason):
  - the text cursor blinking in the sidebar rename field;
  - the Welcome window's animated cards (AutoCode types its quote out);
  - the checkbox's focus ring, which follows key-window timing.

  Unmasked, 17 of 18 captures matched pixel for pixel.
- **One deliberate change is caught exactly.** `CHANGE=1` raises the Concurrency slider
  two notches on the LLM Provider tab: **1 of 19 screens changed**, that screen, 0.10% of
  its pixels, with the changed region drawn in pink.
- **The menu tree reads in under a second**: 209 items with enabled state and shortcut. The
  system's Apple menu is dropped, because its Recent Items change every night.

## What the spike taught (each one cost a failed walk)

1. **Two copies with one bundle id were running.** The guest reopened yesterday's Debug
   test host (0.35.0, from the Swift-suite run) at login, and the walker drove it. The walker now
   targets the copy at `WALK_APP`; the walk guest has login reopening turned off.
2. **"Sent a key" is not "did the thing."** One walk reported success with the Open panel
   still up and nothing added. Every step now asserts its result.
3. **Fixed sleeps lose races.** The panel became key later than `sleep 2` assumed, and
   the copied file landed after the check. The walk now waits for named elements and polls for files.
4. **Typing into an Open panel is fragile.** Re-activating the app moved focus off the
   Go-to sheet and every character beeped in the file list. `walker set` writes the field's
   value through accessibility instead: one call, no keystrokes.
5. **Window geometry can't tell a sheet from a window.** The About window sits inside the
   main window's frame. The accessibility window list can: sheets are never in it.
6. **System privacy prompts are invisible to the walker.** "tart-guest-agent wants to
   bypass the private window picker" came from UserNotificationCenter, which the walker could
   not reach. Grant it once in the base image, and have the walk halt on any window it doesn't
   own (the `walker owners` command is ready for this; the check per step is not wired yet).
7. **The main window's title is the project's name**, so a capture filter on "Bristlenose"
   stopped matching once a project existed.

## The clean macOS 27 guest (20 Oct 2026, afternoon)

- **Base `walk27-base`** = `ghcr.io/cirruslabs/macos-golden-gate-vanilla:27.0` (SIP on, no
  Homebrew, no Xcode) + only the tart guest agent (`prep-base.sh`, the Cirrus-signed binary
  copied from the tahoe guest) + three grants a person gave once: Accessibility, Screen &
  System Audio Recording, Full Disk Access, all to `/usr/local/bin/tart-guest-agent`.
  `night.sh` clones it, walks, and deletes the clone.
- **The run uses the host's Ollama** through `tunnel.sh` (an ssh reverse forward of
  :11434; the app hardwires localhost). `llama3.2:3b` on the host GPU: 1–2 min, about 12k
  tokens in and 3k out, £0.
- **Two unattended nights in a row: no prompt, both completed, about 4 min each** including
  clone, boot and teardown. 22 steps, 26 captures.
- **Between those two nights, 5 of 26 screens differ, and none is a UI change:** four are
  model output (Project, Quotes, Sessions, run outcome) and one is the Welcome animation.
  Edit ▸ Paste's state followed the host clipboard, which tart shares (now masked). So
  lens screens need the frozen project (COVERAGE.md, stage 3).
- **Traps found on the clean machine:**
  - **SIP-on grants can't be pre-written,** and a grant clicked in a nightly clone dies with
    the clone. Grant in the base. `tccutil reset` wipes a grant someone gave by hand; don't.
  - **`~/Documents` is protected,** so the harness reading the project there prompted for
    Documents access. Full Disk Access for the agent covers it, and Downloads and Desktop too.
  - **`python3` in the guest opens the "install developer tools" dialog** on a machine
    without them. The harness runs Python only on the host.
  - **Accessibility accepts a press on a disabled button.** The walker now refuses one,
    or "pressed Add" passes with the panel still open.
  - **Vision OCR does not work in a macOS 27 guest** and does in 26.6 (see COVERAGE.md,
    stage 4).

## A product finding from the first full walk (not verified at HEAD)

With no provider configured, adding an interview starts a run that fails. The failure log
knows why ("✗ API key — No Anthropic API key"), but it classifies the failure as
`category=unknown`. The sidebar says "Something went wrong during analysis., 0 interviews",
and the main view says "No interviews to analyse yet. Drop a folder of interviews here",
with the interview sitting in the folder. The log's advice is the CLI's
(`bristlenose configure claude`).

## Prior art (light review, 20 Oct 2026)

Almost every piece exists elsewhere. What's ours is the combination: the shipped,
notarised app driven from outside, in a disposable guest, with a menu tree diff
next to a pixel diff.

| Prior art | What it is | What we take | Why not adopt it whole |
|---|---|---|---|
| **XCUITest** | Apple's UI automation; the same accessibility API underneath; screenshot attachments; `performAccessibilityAudit()` | The audit idea: our element dump can flag unlabelled buttons per screen at no extra cost | It needs a UI-test target built with the app, and `docs/design-test-philosophy.md` set the bar for adding one. The walker drives the build that ships |
| **Appium Mac2 driver** | WebDriver over XCTest | — | A Node + Appium server stack for what 400 lines of Swift already do; same accessibility blind spots |
| **Peekaboo** (steipete) | CLI + MCP that lets agents capture windows and menus and use set-value / perform-action | The closest match; the conventions agree | v3 is in beta, and it adds a dependency inside the guest. Revisit if the walker grows past a few hundred lines |
| **Playwright `toHaveScreenshot`, Percy, Chromatic, BackstopJS, reg-suit** | Visual regression: baselines, masks, animations disabled, accept flow | Masks (ours carry a printed reason), freezing animations, the accept-a-baseline step | They are browser-side; this is native windows |
| **pixelmatch / odiff** | Pixel diff with anti-aliasing detection | If anti-aliasing noise ever appears, port its detection instead of raising the tolerance | Today's per-channel tolerance gives 0 of 19 |
| **ApprovalTests** (Falco) | `received` vs `approved` files; approving = copying | The vocabulary for the baseline step | — |
| **swift-snapshot-testing** | View-level snapshots in unit tests | — | A different layer, and the test philosophy calls it a consolation prize |

Animation freeze, the conventional way: rather than a test-only launch flag, have the
Welcome cards honour **Reduce Motion** (`NSWorkspace.accessibilityDisplayShouldReduceMotion`)
and turn it on in the walk guest. That puts no test hook in the product and is an
accessibility fix in its own right.

A second, smaller one from the Ollama run: the run's terminus event carried
`cost_usd_estimate: 0.10` for a free local run, because the model stayed at the Claude
default (`claude-sonnet-4-6`) while the provider resolved to `local`, so the estimate was
priced as Sonnet. I haven't checked whether the Mac app shows that figure.

## Open, before this is a nightly job

1. **A real analysis run needs an LLM in the guest.** Cheapest in the Mac picker:
   `gpt-5.6-luna` ($0.20 / $1.20 per million tokens, `llm/pricing.py`), then
   `gemini-3.5-flash-lite` (a promotional rate until 31 Dec 2026), then `claude-haiku-4-5`.
   On the 1 KB smoke fixture each is cents a night. **But LLM output differs every night,**
   so lens screens from a fresh run would be pink every morning whatever the model.
   The split: the real run proves the lifecycle and is checked on counts and the end
   state. The lens screens are diffed on a frozen, already-analysed project, so a pink
   lens means the UI changed, not the model.
2. **Which build.** The spike installs the notarised Developer-ID export. A nightly needs
   HEAD: either a signed `.dmg` build each night, or an unsigned guest-local build, which is
   not sandboxed the way the shipped app is.
3. **Determinism at the source:** a walk-mode switch (or Reduce Motion in the guest) that
   freezes the Welcome cards, instead of masking them.
4. **Halt on any foreign window** at every step (system prompt, crash reporter).
5. **Coverage:** context menus, the codebook and quote lenses, exports, and drag-and-drop.
   The web content of the lenses needs a completed run first.
6. **Wiring:** a second job in `guest-matrix.sh` under the same gates, with "walk: N of M
   changed" in the morning line. Only two macOS guests may run at once, so it runs after the
   suite, not alongside it. Accepting a baseline means copying tonight's walk over it.
