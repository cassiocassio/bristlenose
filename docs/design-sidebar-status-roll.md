# Sidebar status roll: the plan

**Status: approved to build by the owner (30 Oct 2026); W0 (the spike) is done and four independent reviews are in. Revised the same day: §11 holds the results and what changed, and §2 lists the owner decisions still needed before W1.** Nothing in `desktop/` or `frontend/` has been changed; the spike ran in a throwaway worktree. The behaviour spec is the mockup, [`mockups/sidebar-status-roll.html`](mockups/sidebar-status-roll.html) (PROPOSED in `mockups/STATUS.md`); this document says how it would be built, in what order, what could go wrong, and how each part is proven.

## 1. What and why

A sidebar project row has one subtitle line. When several background states are true at once (for example "Screens · 3 of 40", which can run for hours, and "Picking up Signals…", about 30 seconds, both starting right after an analysis) a fixed precedence chain shows one and hides the rest. The owner's idea is a line that rolls vertically between them, so none is hidden for more than one dwell.

The recommendation I gave was the fixed order, because the overlap that prompted this is about 30 s. The owner's lean is the roll, and the audit of concurrent states (30 Oct) showed the larger win is elsewhere: a persistent warning, such as a partial completion, hides progress for hours today.

## 2. Decisions on record (owner, 30 Oct 2026)

- The roll. 5 s dwell. Pause on hover. Shimmer kept. **No count** ("+1" rejected).
- Errors displace everything. Warnings and info may roll with progress.
- Every state carries a flag, `holds` or `rolls`, with guidelines for when to assert `holds`; when unsure, `holds`.
- A second concurrent error has no door. A future popover listing every error is a 100-day item, not v1 (reason on record: a failure the researcher must fix is usually all they look at, and three rolling states means the project is mostly working).

**Owner decisions needed before W1** (my recommendation in each; reasons in §11):
1. **Queued, Stopped and Transcribed:** roll as info states, not hold. A decision already on record (#2, commit `66e945551`, pinned by `ReportCrashTests.restingStatesYield`) makes a report crash beat them, which my "they hold" classification would undo.
2. **The cloud batch:** hold, not roll. It carries a stop ring in the trailing slot that does not follow a line, so it fails G3 as I wrote it.
3. **Perpetual cycle or event-driven:** a reviewer suggests rolling once when a state starts and then settling, with no cycle. That removes most motion and the reload risk, but a long warning then hides progress again after the first entrance, which loses the win you wanted. I recommend keeping the cycle, with extra stop conditions (§11).
4. **Reduce Motion:** fixed order (my draft) or a slow dissolve. Apple's accessibility text supports both; the fixed order brings back hours-long hiding for those users.
5. The cap of three lines and the 5 s dwell stand unless you say otherwise.

## 3. Gates before any build

1. **UX approval.** The R114 gate wants explicit owner approval of the mockup before any new UX is built. "Good enough for v1" is close; a plain "approved to build" ends it.
2. **Beta policy.** Beta means almost no new features. The board card says Could, post-launch. This plan does not change that.
3. **A flag.** Swift has no parked-feature flag yet (`docs/design-feature-flags.md` gives the shape to copy). The first merge sits behind one, default off, so the fixed order is the shipped behaviour until the roll is proven.
4. **Release freeze.** A running release freezes commits locally; this work waits for a gap.

## 4. Where it touches the code

Read on 30 Oct 2026; line numbers will drift.

| Place | What is there | What changes |
|---|---|---|
| `ProjectSubtitle.swift` | `SubtitleVariant` (includes `.preparingSignals`, landed), `resolve` and `resolveIdle` returning **one** variant; `glyphKind` and `glyphAction`, both exhaustive with no `default` | Add `rollPolicy` beside them, same convention. Add `resolveAll` **as a sibling. `resolve` is not changed** (§5 W1 says why). Add a case-only key for "same state". |
| `SidebarSubtitleText.swift` | `text(for:)`, `activityText`, `tooltip(for:)` (single variant) | `tooltip` takes all lines and lists them in rank order. Its own comment calls "a cycling departure-board line" the intended direction and says not to grow the tooltip; this is that direction. |
| `ProjectSidebarOutline.swift` | `subtitleVariant(for:)`; `projectTwoLineCell`, where the prefix glyph (an image or a `SubtitleActionButton`) and the subtitle element (a `ShimmerText` host, a text `SubtitleActionButton` or a plain field, chosen at build time) are **separate views**; `subtitleActionClicked`; `presentDiagnosticPopover`, which re-reads the crash off `subtitleVariant(for:)`; `cellRightSlot` (ring or antenna, whatever line shows); `heightOfRowByItem`; `shimmers(_:…)`, which already admits `.running` and `.preparingSignals`; `withTooltip`; `update()` calling a full `reloadData()` on every input change; the antenna's controller timer and per-project view map (`agentAntennaViews`) | The subtitle area becomes a rolling view that carries each line's glyph. The clock lives in the controller, and visible rows are diffed and refreshed in place. Click and popover resolve against the visible line's variant. |
| `ProjectRow.swift` | The SwiftUI flag-off path, also calls `resolve` | Untouched. The roll is the AppKit path only, as every new sidebar work is. |
| Tests | `ProjectSubtitleTests`, `SubtitleGlyphContractTests`, `SignalsPreparingTests` and siblings | New pure tests (section 7). Existing ones must stay green unchanged. |
| Locales | Strings for every state already exist | **No new keys for the roll itself.** |

## 5. Work packages, in order

**W0. Spike: reload churn. DONE 30 Oct 2026, verdict: go.** Run in a throwaway worktree through the real `SidebarOutlineController` (the same harness as `SidebarOutlineDropAndRevealTests`), with a prototype in-place refresh that was never committed. Results are in §11. In short: every `update()` rebuilds every cell (so any per-cell state is lost on each input change), the rebuild is cheap, and a visible row's subtitle can be refreshed in place, keeping the same cell and the same subtitle view. What W0 could not measure is how often the real app calls `update()`; §11 says what is known.

**W1. The model (pure, safe to land alone).**
- `SubtitleVariant.rollPolicy`: exhaustive, no `default`. Every case classified, including `.waitingForWhisper`, `.placeholder` and `.ready` (the first draft of the table left them out). Guidelines as in the mockup, with the two corrections in §2 (Queued, Stopped and Transcribed roll; the cloud batch holds).
- `SubtitleVariant.lineKey`: the case without its payload, so "Screens · 3 of 40" becoming "4 of 40" is the same line and never rolls. `==` compares the payload and would call it a new state.
- `resolveAll(...) -> SubtitleLines`: holders first (highest-ranked holder), then rollers in rank order, capped at three (above three, the top-ranked line holds).
- **`resolve` is not redefined as the head of `resolveAll`.** My first draft said it was, and a reviewer showed that cannot hold. Where a holder outranks a roller that today ranks higher, the two intentionally differ: Adding beats a partial completion (today the pipeline switch returns first), and a report crash beats Queued only because Queued now rolls. `resolve` stays exactly as it is, the SwiftUI flag-off row keeps calling it, and a **divergence table** lists every input where `resolveAll`'s first line differs from `resolve`, each with its reason, so a new divergence fails a test instead of arriving silently. Where there is no roller involved the two must agree, and that is the head-equality pin.
- `resolveAll` flattens `resolve`'s early returns into "collect everything that is true". That is the real work and the half-day I first allowed was light.

**W2. The clock (pure).** `SubtitleRollClock`: given the current line set, a dwell, and an injected time source, answers which line shows. Jump to the top-ranked line when a state starts (one roll). Settle on a survivor when the visible state ends, or do nothing when a hidden one ends. Text changes inside a state never roll. Hold a new state for at least 2 s: the 2 s floor needs memory (the clock keeps an ended line until its floor passes), so the clock is a small state machine with an injected time source, tested as sequences of (events, time) to visible line, not a pure function of the current set. Pause and resume. Reduce Motion returns the fixed answer. One clock per controller (so per window), keyed by project. Rule R4 jumps to the top-ranked state, so a new low-ranked state may start without being shown; it is still announced once (R9), and the tooltip lists it.

**W3. The view, and how it survives the reloads.** Two parts.
- *Surviving `update()`.* The outline rebuilds every cell on every input change (W0), and the representable observes `liveData` (every run event and stdout line), the Screens store and others, so a row is rebuilt about as often as the busiest of them publishes. So the roll must not live in the cell. The precedent is the antenna: one controller `Timer` (in `.common` run-loop mode), a per-project view map (`agentAntennaViews`) and no `reloadData`. The roll follows it: the clock and the line state live in the controller, and `update()` stops calling `reloadAndRestore()` for a change that only touches a visible row's subtitle. It diffs each visible row's displayed content; a row whose only change is its subtitle lines is refreshed in place (W0 proved this works), and any other change, or a change in tree shape, selection or expansion, still reloads as today. This diff is the largest single piece of the work (it generalises the rename-only `rowsToRefreshDuringRename`).
- *The view.* The cell is refactored so that a line owns its own glyph: a fixed-height clipping container holds the line views, each a glyph plus a text element of whichever type that line needs (plain field, text button or `ShimmerText` host). That replaces the three-way `subtitleField` branch and the several constraints that reference it. The roll is a push transition (`CATransition`, or `CABasicAnimation` on position). The trailing ring and the antenna stay row chrome. Shimmer starts after the line settles and never under Reduce Motion. Row height never changes. A `reloadData` that does still happen mid-transition snaps to the current line instead of tearing; that is acceptable and is tested.

**W4. Interaction.** A tracking area pauses the clock on hover and restarts a full dwell on exit; the clock also stops while the app is inactive, the window is not key, or the row is scrolled out of view. The tooltip lists every state running, in full, in rank order, built once from the line set so it stays correct across a roll. A click resolves against the line on screen **at mouse-down**, through a pure function `action(forVisibleLine:)`, and a roll that would begin inside the hover delay is cancelled. **The popover follows the line, not the head:** `presentDiagnosticPopover` today re-reads the crash off `subtitleVariant(for:)`, so with a rolling line it would open the wrong popover; it takes the clicked line's variant instead. The ring for a holding state sits with that state (the cloud batch holds, §2).

**W5. Accessibility.** The row's accessibility value lists every line once and is byte-identical across a roll, with each visible line a substring of it so Voice Control still resolves "click Partial completion". A line is announced when its state starts, never on a roll and never on a finish; start announcements are limited so a launch with many rows does not chatter. Announcement goes through an injected poster so a test can count posts. **Pausing is not hover-only** (WCAG 2.2.2, from the accessibility review): the roll also stops while the row has VoiceOver or keyboard focus. **Every door gets a named accessibility action** independent of the visible line, such as "Show partial completion details", so Switch Control and VoiceOver users reach a rolling warning without catching a moving element, and a test counts them. **The menu route:** the context menu offers Show Diagnostics only for `.failed`, `.failedWithDiagnostic` and `.completedPartial` (`isFailureState`); the report crash and missing files have no menu route at all, so W5 adds them, with the menu-bar twin dimmed when it does not apply (the house rule). New strings go in 21 locales. **Colours:** the build uses system colours; the mockup's stand-in amber is 2.8:1 on the row and fails WCAG 1.4.11. Consider one polite announcement when a state the researcher is waiting for becomes available (Signals ready), since "silent on finish" leaves a VoiceOver user with no cue.

**W6. Docs and flag.** Amend §5 of `design-desktop-project-status.md`: it keeps "never two conditions on one line" for every holder and is relaxed only for rollers, where two conditions share a line in time, not in space. Add the flag per `design-feature-flags.md`. Update the mockup register row, `TODO.md` and the changelog entry at release time (a user-visible change, so a minor bump under the house rule, owner's call).

## 6. Estimate

**About 4 to 5 working days, plausible range 3.5 to 6** (it was 3 to 4). W0 is spent. W1 about 1 (the model, the flattening of `resolve`, the divergence table), W2 0.5, W3 1.5 to 2 (the per-row diff and the cell refactor), W4 0.5, W5 1 (per-door actions, menu items and strings in 21 locales), W6 0.5, plus review (`/usual-suspects` on the Swift) and the by-hand walk. The roll would also sit behind two flags, since the AppKit sidebar flag (`appKitSidebar`) is itself off by default. For scale, the Signals "Picking up" variant took two commits and a review round; this is three to four times that.

## 7. How each part is proven

**Pure, table-driven, mutation-proved (the house standard):**
- `rollPolicy` pin: one row per `SubtitleVariant` case, so adding a case fails until it is classified.
- Head equality: `resolveAll(...).head == resolve(...)` over every existing `ProjectSubtitleTests` input where no roller is involved, **plus the divergence table**: every input where they differ is listed with its reason, because restricting the pin to inputs that already agree skips exactly the cases whose answer changes (a crash with Queued, a partial completion with Adding).
- Holders: an error, an acknowledgement or a run always yields one fixed line, whatever else is true.
- Rollers: two or three give a rank-ordered roll; four give the top-ranked held; the count falling back resumes.
- Clock: a start jumps once; the visible state ending settles once; a hidden state ending does nothing; a text change does nothing; the 2 s floor holds a short job; pause then resume gives a full dwell; Reduce Motion gives the fixed answer.
- Announcement decision: a function from the set before and after to "announce or not"; a roll tick yields none.
- Clock-independent text: the tooltip and the accessibility value are pure functions of the line set, not of the clock position, and a test asserts it (the VoiceOver invariant).
- Mouse-down resolution: `action(forVisibleLine:)` is pure; a clock tick between mouse-down and mouse-up must not change the action.
- "Same state": the clock compares by `lineKey`, and the test asserts on that key, not on the set, or it can pass while the clock still rolls.
- Row height: one assertion that the cell's fitting height is equal in every line state.
- **Reload survival (the integration test the first draft lacked).** The W0 harness is the template: build the real `SidebarOutlineController` headless as `SidebarOutlineDropAndRevealTests` does, republish with a changed Screens count and assert that the cell and the subtitle view are the same objects and show the new text, and that a republish that does change structure still reloads. No animation is involved.

**Seams, not UI:** inject the time source and the accessibility poster. Do not assert on animation, because AppKit animations stall when the display sleeps (a known trap in `desktop/CLAUDE.md`), and use `Task.sleep`, never `RunLoop.main.run`, in any async test.

**By hand (the only check for these):**
1. Walk the eight mockup scenarios on the real app.
2. VoiceOver: focus the row, wait three cycles and expect silence; start a job and expect exactly one utterance.
3. Click a rolling warning's glyph while the line is moving; the popover must belong to the line the pointer was on.
4. Reduce Motion on and off, light and dark, German at the narrow width.
5. Leave it running for an hour with Screens reading and watch CPU and wake-ups. Not measured so far. Pass means no sustained wake-ups beyond the one timer while the row is on screen and the app is active, and nothing when it is not.
6. Shimmer starts only after the line settles; hover pause with a held pointer (a tracking area cannot be unit-tested cheaply); keyboard focus pauses the roll.

## 8. Risks

Engineering, worst first: **the per-row diff in `update()`** (it must keep selection, expansion, the rename guard and the drop-animation guard intact while skipping the full reload for subtitle-only changes); **a click or popover landing on the wrong line** (mouse-down resolution and line-based popover routing); **rule collisions with existing precedence** (decision #2 and the Adding-versus-partial case, handled by the divergence table); **merge friction**, since `ProjectSidebarOutline.swift` is about 3,100 lines and other sessions edit it; **timer cost** (one controller timer, stopped when the app is inactive, the window is not key or the row is off screen); **the test-host animation trap**. Communication risks and the rule that answers each are in the mockup's commentary table. Still open: the unreachable second error (100 days), the shorter German Signals phrase (readiness doc), and the owner decisions in §2.

## 9. Out of scope

A popover listing several errors (100 days). Rolling the gesture acknowledgements (they hold by rule). A count, or any "finished" message. A detail pane listing the hidden states (the status doc's stated home for non-winners; not built, not needed for v1). Rolling in the SwiftUI flag-off row. Any change to what a state says.

## 10. First move

The owner decisions in §2 (items 1 to 4, one reply). Then W1, the model, which is pure and lands alone. The W0 test is kept as the template for the reload-survival test and its prototype is not to be committed as it stands.

## 11. W0 result and review findings (30 Oct 2026)

**W0, measured** (headless `SidebarOutlineController`, 18 visible rows at 600 pt and 62 at 2,000 pt; cells force-realised on both sides of each comparison, after a first run whose empty "after" set would have made the churn result an artefact):

| | 18 rows | 62 rows |
|---|---|---|
| Cells kept after a republish with a changed Screens count | 0 of 18 | 0 of 62 |
| Cost of one republish (200 runs, nothing changed) | 0.11 ms | 0.26 ms |
| In place: same cell and same subtitle view kept, text updated | 18 of 18 | 62 of 62 |
| Cost of one in-place refresh (200 runs) | 0.09 ms | 0.63 ms |

So the churn is lost identity, not CPU; the in-place route works on the real controller; and the "same subtitle view" check is the regression test W3 needs. **Not measured:** how often the live app calls `update()`. Known sources: the representable observes `PipelineLiveData` (published per run event and per stdout line), the Screens store (published on any change, and its progress carries seconds read, so about once per poll) and cloud and copy progress. About once a second during a run is the working figure, not a measurement.

**Four independent reviews** (code against the plan; Mac-native; accessibility; test placement). What changed because of them:
- **Code review.** Section 4 said the glyph and text were one control (they are separate views) and that shimmer needed extending to Signals (it already covers it): corrected. `resolve` cannot be "the head of `resolveAll`": corrected, with the divergence table. A report crash beats Queued, Stopped and a partial run (decision #2, pinned): Queued, Stopped and Transcribed now roll. The cloud batch's ring sits in the trailing slot whatever line shows: the batch now holds. The popover re-resolves the head: it now follows the clicked line. Equality on `SubtitleVariant` treats "3 of 40" and "4 of 40" as different states: `lineKey`. The antenna's timer and view map are the better precedent for the clock. No keyboard route for the crash or missing files: W5 adds them.
- **Mac-native review.** Could not verify any Apple app that rolls concurrent states in a sidebar row. The HIG says status should be passive, and Apple's accessibility text asks apps to reduce automatic, repetitive animation, which the cycle is. The suggested alternative, event-driven rolling with no cycle, is owner decision 3 in §2. Adopted regardless: stop when the app is inactive or the row is scrolled out of view; a menu route plus a menu-bar twin; check the roll against the selection highlight in both appearances.
- **Accessibility review.** Hover-only pause is not enough (2.2.2): also pause on VoiceOver or keyboard focus. Every door needs a named accessibility action. The mockup's amber stand-in fails 3:1 (use system colours in the build). The mockup's own HTML has minor faults (an `aria-label` on a generic element, state shown by fill alone, the catalogue loops with no non-hover pause): to fix when the mockup is next touched.
- **Test-placement review.** Added the reload-survival integration test, mouse-down resolution as a pure function, clock-independent text builders, and a row-height assertion, and gave the one-hour CPU check a pass condition. Not added: any assertion on animation or dwell values, an XCUITest, a snapshot of the transition, and (unless W5 grows a second call site) a counting accessibility poster beyond the pure announcement decision.

**Verdict on the plan.** Sound in shape and honest about its main risk, which W0 has now turned from a worry into a design: diff per row, clock in the controller, antenna as precedent. It was wrong in four places (two classification calls, "resolve is the head", and the one-control claim), all fixed above. It was light on W1 and W3, hence 4 to 5 days. It should not start until §2's four decisions are made, because decisions 1 and 2 change the mockup's classification table and card 6, and decision 3 could remove the cycle altogether.
