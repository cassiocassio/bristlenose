# Sidebar status roll: the plan

**Status: a plan, not approved to build.** Written 30 Oct 2026 after the owner chose the roll in the mockup. Nothing in `desktop/` or `frontend/` has changed. The behaviour spec is the mockup, [`mockups/sidebar-status-roll.html`](mockups/sidebar-status-roll.html) (PROPOSED in `mockups/STATUS.md`); this document says how it would be built, in what order, what could go wrong, and how each part is proven.

## 1. What and why

A sidebar project row has one subtitle line. When several background states are true at once (for example "Screens · 3 of 40", which can run for hours, and "Picking up Signals…", about 30 seconds, both starting right after an analysis) a fixed precedence chain shows one and hides the rest. The owner's idea is a line that rolls vertically between them, so none is hidden for more than one dwell.

The recommendation I gave was the fixed order, because the overlap that prompted this is about 30 s. The owner's lean is the roll, and the audit of concurrent states (30 Oct) showed the larger win is elsewhere: a persistent warning, such as a partial completion, hides progress for hours today.

## 2. Decisions on record (owner, 30 Oct 2026)

- The roll. 5 s dwell. Pause on hover. Shimmer kept. **No count** ("+1" rejected).
- Errors displace everything. Warnings and info may roll with progress.
- Every state carries a flag, `holds` or `rolls`, with guidelines for when to assert `holds`; when unsure, `holds`.
- A second concurrent error has no door. A future popover listing every error is a 100-day item, not v1 (reason on record: a failure the researcher must fix is usually all they look at, and three rolling states means the project is mostly working).

Unresolved owner calls, each stated in the mockup: the cloud batch rolls; Queued, Stopped and Transcribed hold; the report-crash warning rolls; Reduce Motion falls back to the fixed order (Apple's guidance leans to a dissolve); the cap of three lines.

## 3. Gates before any build

1. **UX approval.** The R114 gate wants explicit owner approval of the mockup before any new UX is built. "Good enough for v1" is close; a plain "approved to build" ends it.
2. **Beta policy.** Beta means almost no new features. The board card says Could, post-launch. This plan does not change that.
3. **A flag.** Swift has no parked-feature flag yet (`docs/design-feature-flags.md` gives the shape to copy). The first merge sits behind one, default off, so the fixed order is the shipped behaviour until the roll is proven.
4. **Release freeze.** A running release freezes commits locally; this work waits for a gap.

## 4. Where it touches the code

Read on 30 Oct 2026; line numbers will drift.

| Place | What is there | What changes |
|---|---|---|
| `ProjectSubtitle.swift` | `SubtitleVariant` (includes `.preparingSignals`, landed), `resolve` and `resolveIdle` returning **one** variant; `glyphKind` and `glyphAction`, both exhaustive with no `default` | Add `rollPolicy` beside them, same convention. Add `resolveAll`. `resolve` stays as its head so existing callers and tests keep working. |
| `SidebarSubtitleText.swift` | `text(for:)`, `activityText`, `tooltip(for:)` (single variant) | `tooltip` takes all lines and lists them in rank order. Its own comment calls "a cycling departure-board line" the intended direction and says not to grow the tooltip; this is that direction. |
| `ProjectSidebarOutline.swift` | `subtitleVariant(for:)`, `projectTwoLineCell`, `SubtitleActionButton` wrapping glyph and text, `subtitleActionClicked`, `shimmerSubtitle` (`.running` only, hosts `ShimmerText`), `withTooltip` (static `toolTip` on the cell), `update()` calling a full `reloadData()` | The subtitle area becomes a rolling view. The roll clock lives in the controller. A visible rollable row is refreshed in place. Click resolves against the visible line. Shimmer extends to the Signals line (already readiness decision 5). |
| `ProjectRow.swift` | The SwiftUI flag-off path, also calls `resolve` | Untouched. The roll is the AppKit path only, as every new sidebar work is. |
| Tests | `ProjectSubtitleTests`, `SubtitleGlyphContractTests`, `SignalsPreparingTests` and siblings | New pure tests (section 7). Existing ones must stay green unchanged. |
| Locales | Strings for every state already exist | **No new keys for the roll itself.** |

## 5. Work packages, in order

**W0. Spike: measure reload churn (about half a day, read-only).** The main risk is that `update()` rebuilds every cell with `reloadData()`, which would tear down a transition and restart a dwell. Add temporary logging (never committed) of how often `update()` runs while Screens reads and while a run is in flight, and of how many rows each call rebuilds. Then try, on one row only, a refresh in place of the subtitle text (the precedent is `refreshRowsAroundRename`, with the `reloadSuppressed` guard). **Go or no-go:** if a visible row's subtitle can be refreshed in place without a full reload, continue. If not, the estimate roughly doubles and the plan is re-opened with the owner.

**W1. The model (pure, safe to land alone).**
- `SubtitleVariant.rollPolicy`: exhaustive, no `default`, so a new variant cannot compile without the decision. Guidelines as in the mockup (G1 error-kind or unusable; G2 gesture acknowledgement or shorter than one cycle; G3 verb-led run ladder or a row control such as a cancel ring; otherwise rolls; unsure holds).
- `resolveAll(...) -> SubtitleLines`: holders first (highest-ranked holder, today's precedence), then rollers in rank order, capped at three (above three, the top-ranked line holds). Rank is today's chain plus Signals above Screens. A holder beats a roller even where today ranks the roller higher.
- `resolve` returns the head of `resolveAll`, which must equal today's answer wherever no roller is involved. This is the regression pin.

**W2. The clock (pure).** `SubtitleRollClock`: given the current line set, a dwell, and an injected time source, answers which line shows. Jump to the top-ranked line when a state starts (one roll). Settle on a survivor when the visible state ends, or do nothing when a hidden one ends. Text changes inside a state never roll. Hold a new state for at least 2 s. Pause and resume. Reduce Motion returns the fixed answer. One clock per controller (so per window), keyed by project.

**W3. The view.** A fixed-height clipping view inside the subtitle control, holding two text layers, moved with a push transition (`CATransition`, or `CABasicAnimation` on position). The glyph is part of its line. The ring stays in the trailing slot and belongs to the run, which holds. Shimmer starts after the line settles and never under Reduce Motion (`NSWorkspace.shared.accessibilityDisplayShouldReduceMotion`, already read by `shimmerSubtitle`). Row height must not change: the line is one line high in every state.

**W4. Interaction.** A tracking area pauses the clock on hover and restarts a full dwell on exit. The tooltip lists every state running, in full, in rank order (built once from the line set, so it stays correct across a roll). A click resolves against the line on screen **at mouse-down**, and a roll that would begin inside the hover delay is cancelled, so the pointer never lands on a line that has just changed. The click path stays `subtitleActionClicked`, reading the visible line's `glyphAction`.

**W5. Accessibility.** The row's accessibility value lists every line once and is byte-identical across a roll. A line is announced when its state starts, never on a roll and never on a finish. Announcement goes through an injected poster so a test can count posts. A non-pointer route to a rolling warning's door: a key `desktop.menu.project.showDiagnostics` exists, which suggests a project menu item; **confirm in W0** that the row's context menu offers it, and add it if not (one string, 21 locales).

**W6. Docs and flag.** Amend §5 of `design-desktop-project-status.md`: it keeps "never two conditions on one line" for every holder and is relaxed only for rollers, where two conditions share a line in time, not in space. Add the flag per `design-feature-flags.md`. Update the mockup register row, `TODO.md` and the changelog entry at release time (a user-visible change, so a minor bump under the house rule, owner's call).

## 6. Estimate

About 3 to 4 working days, plausible range 2.5 to 5, from reading the code and not from having built it. Rough split: W0 0.5, W1 0.5, W2 0.5, W3 and W4 1 to 1.5 (the uncertain part, set by W0), W5 0.5, W6 0.5, plus review (`/usual-suspects` on the Swift) and a by-hand walk. For scale, the Signals "Picking up" variant took two commits and a review round; this is two to three times that.

## 7. How each part is proven

**Pure, table-driven, mutation-proved (the house standard):**
- `rollPolicy` pin: one row per `SubtitleVariant` case, so adding a case fails until it is classified.
- Head equality: `resolveAll(...).head == resolve(...)` over every existing `ProjectSubtitleTests` input where no roller is involved.
- Holders: an error, an acknowledgement or a run always yields one fixed line, whatever else is true.
- Rollers: two or three give a rank-ordered roll; four give the top-ranked held; the count falling back resumes.
- Clock: a start jumps once; the visible state ending settles once; a hidden state ending does nothing; a text change does nothing; the 2 s floor holds a short job; pause then resume gives a full dwell; Reduce Motion gives the fixed answer.
- Announcement decision: a function from the set before and after to "announce or not"; a roll tick yields none.

**Seams, not UI:** inject the time source and the accessibility poster. Do not assert on animation, because AppKit animations stall when the display sleeps (a known trap in `desktop/CLAUDE.md`), and use `Task.sleep`, never `RunLoop.main.run`, in any async test.

**By hand (the only check for these):**
1. Walk the eight mockup scenarios on the real app.
2. VoiceOver: focus the row, wait three cycles and expect silence; start a job and expect exactly one utterance.
3. Click a rolling warning's glyph while the line is moving; the popover must belong to the line the pointer was on.
4. Reduce Motion on and off, light and dark, German at the narrow width.
5. Leave it running for an hour with Screens reading and watch CPU and wake-ups. Not measured so far.

## 8. Risks

Engineering, worst first: **reload churn** (W0 decides it); **a click landing on a line that has just changed** (mouse-down resolution); **merge friction**, since `ProjectSidebarOutline.swift` is about 3,100 lines and other sessions edit it; **timer cost** (one controller timer, running only while a row is rollable and the window is key); **the test-host animation trap**. Communication risks and the rule that answers each are in the mockup's commentary table, and the open ones are the unreachable second error (100 days), the shorter German Signals phrase (readiness doc), and the owner calls in section 2.

## 9. Out of scope

A popover listing several errors (100 days). Rolling the gesture acknowledgements (they hold by rule). A count, or any "finished" message. A detail pane listing the hidden states (the status doc's stated home for non-winners; not built, not needed for v1). Rolling in the SwiftUI flag-off row. Any change to what a state says.

## 10. First move

W0, the spike, after the gates in section 3 are cleared. It is read-only, takes half a day, and turns the estimate from a range into a number.
