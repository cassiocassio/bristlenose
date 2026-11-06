# The run-finished banner: a design for approval

Status: proposal for owner approval, 6 Nov 2026. Nothing is built. Under the R114 UX gate (complete mockup, review and explicit approval before new UX is implemented) this is the review artefact; the mockup is `docs/mockups/perceived-wait-run-banner.html`. Why it exists, and the evidence behind it: `docs/design-perceived-wait.md`, candidate A. Earlier direction it builds on: `docs/design-desktop-nav-toolbar-rearrangement.md` § 10.4.

## What it is

When an analysis ends and the researcher is not in Bristlenose, the Mac raises one ordinary notification banner. That is the whole feature. It exists so a researcher can leave a 40-minute run and be told, truthfully, when to come back.

It stays on the Mac. Nothing here reaches an iPhone or Watch; that is a separate decision (`design-perceived-wait.md`, "Reaching the phone and Watch").

## Decided by the owner (6 Nov 2026)

| Decision | Ruling |
|---|---|
| Text | Useful, not content-free: the project name is in it by default |
| Default | On, with a switch in **Settings ▸ General** to turn it off |
| Estimate | No "about N min" in any banner |
| Frontmost | If Bristlenose is the frontmost app, no banner, whichever project is on screen. A closed sidebar is a wrinkle for after it is built. |
| Phone and Watch | Out of scope here |
| Web report asking its platform | Parked |

## When it fires

The run's end kinds are the ones `PipelineRunner` already distinguishes. Seam names below are from reading the code and are for the implementer to confirm.

| The run ended as… | Banner? | Title | Body |
|---|---|---|---|
| Completed (`run_completed`, no failed session) | yes | Analysis finished | the project name |
| Completed with some sessions failed (`.completedPartial`) | yes | Analysis finished with failures | the project name |
| Failed (`.failedWithDiagnostic`, or `.failed`) | yes | The analysis didn't finish | the project name, plus the reason when the app already knows it |
| Stopped by the researcher | **no**: they just pressed Stop, and "Analysis stopped" is plain in the window | | |
| Ended because the app quit (`.stopped(interrupted: true)`) | **no**: nothing is alive to send it | | |

And only when **all** hold: the switch is on; macOS has allowed notifications; Bristlenose is **not** the frontmost app at the moment the run ends.

**Never:** a banner for a run that is still running, a progress banner, a reminder, a second banner for the same end, or a banner on app launch about a past run. The banner reports an end that happened while the researcher was away; it does not nag.

## The text

All strings are new except where marked. All need the 21 full locales and an entry in `docs/platform-text-map.md`. Provider names are product names (Claude, ChatGPT), as everywhere.

| Use | Proposed English | Notes |
|---|---|---|
| Title, finished | "Analysis finished" | New. The shipped tooltip "Analysis finished with failures for {{project}}" is a different case. |
| Title, finished with failures | "Analysis finished with failures" | New; mirrors that tooltip. |
| Title, failed | "The analysis didn’t finish" | **Shipped** (`failedTitle`). |
| Body, normal | "{{project}}" | The study's own name, which is Bristlenose's own and never follows the folder (ruling 10). |
| Body, failed with a known reason | "{{project}} · {{reason}}" | Reason short form, see below. |
| Settings label | "Notify when an analysis finishes or stops" | New; a positive switch, on by default. |

**Counts in the body ("8 sessions") are not in this proposal.** It is the same question as a "found so far" count and the owner has not decided it. The mockup shows one as an illustration only.

**The failure reason.** The app already classifies why a provider call failed ("{{provider}} is out of credit", "rejected this key", "is rate-limited", in `llmSettings.validation`). The banner uses only a reason from that existing set, in a short form ("Claude is out of credit"), and says nothing more when the cause is unknown. It does not invent a cause. The short forms are new strings; whether they can reuse the existing ones with a trimmed tail is for the implementer to find.

**Plain words.** "Analysis" not "run" or "pipeline" (`docs/glossary.md`). No exclamation, no emoji, no "success". The failed banner says what is true and nothing else; it does not tell the researcher what to do. A banner that stopped being news would be cut.

## The permission flow

macOS delivers nothing until the researcher has allowed it, so "on by default" means asking once, in context, not silently.

1. **When:** the first time an analysis starts after the feature ships (not at launch, not in Settings). That is the moment the banner becomes relevant and the researcher is already deciding about leaving.
2. **How:** the system's own prompt, through the standard authorization request, with no pre-prompt sheet of ours. Provisional (quiet) authorization exists on macOS but delivers silently to Notification Center, which defeats the purpose, so it is not used.
3. **If allowed:** nothing more to say.
4. **If declined:** the app says nothing and asks nothing again (not needy). The Settings switch stays as the researcher left it; when the system permission is off, the row reads as unavailable and says why in one line, with no button that re-asks. The researcher changes it in System Settings.
5. **If already declined or never asked, and a run ends:** no banner, no fallback chime.

Why not ask at first launch: a permission prompt before the researcher has any reason to want it is the worst-converting place to ask, and the first launch has enough else going on.

## The Settings switch

- **Where:** Settings ▸ General. The tab holds one row today ("Default location for new projects"), in a grouped Form; the switch is a second row in the same group, with no new section header.
- **Default:** on. **The trap:** `@AppStorage` defaults are not registered defaults, so any other code reading the same key (for example the code that decides whether to fire) must read it with the same default, or the two disagree on a fresh install. Read the preference through one accessor.
- **Reads positively.** A "mute alerts" label would make the on state the double negative.
- **System permission off:** the row is disabled and carries one line of secondary text pointing at System Settings. It does not duplicate the system toggle.

## Interactions

- **Click the banner:** opens Bristlenose with that project selected. The mechanism for selecting a project from outside (the project id, not the path: identity is never from a path) is for the implementer to confirm; I did not find an existing external route.
- **Sound:** the system default notification sound.
- **Dock:** one informational bounce, which stops by itself (`NSApp.requestUserAttention(.informationalRequest)`), as recorded in § 10.4. No badge, no sustained bounce.
- **Grouping:** one thread per project, so several ends close together stack under the project rather than flooding. Whether several projects finishing together should group is still open.
- **Mac asleep:** macOS shows the banner on wake. Nothing for us to do.
- **Focus modes and Do Not Disturb:** respected; we do not request Time Sensitive.
- **VoiceOver:** an announcement of the end when the app is frontmost and no banner is shown ("Analysis complete" is the recorded string in § 10.4); keep it to what is already announced today unless approved separately.

## What decides "not in the app"

The case this serves is the 99% one: the researcher has started a run and then **hidden Bristlenose, left it under a clutter of other windows, or gone full-screen in another app**. In all three, Bristlenose is not the app they are using, and the banner is how they find out.

So the gate is whether Bristlenose is the **active application** when the run ends: `NSApp.isActive`, with `didBecomeActive` and `didResignActive` as the notifications. Active-ness, not visibility, is the test, which is why a Bristlenose window sitting visible but buried under another app's windows still gets a banner, and why a different app in full screen does too. **Not `scenePhase`**, which is unreliable on macOS for this (the recorded trap in § 10.4). If the sidebar is closed but the researcher is in the app, no banner (decided).

One case to check when built: a researcher who minimises or hides Bristlenose's windows but leaves it as the active app (for example by minimising its only window to the Dock). If macOS keeps it active, the active-app test alone misses it, and the gate should also treat "no visible Bristlenose window" as not in the app (`NSApp.occlusionState` or the windows' own visibility). I have not verified how macOS behaves here.

This design does not address the app being quit. A run stops with the app (the 20 Oct 2026 decision), so there is nothing to alert about; that wider question has its own brief, `docs/brief-macos-background-run.md`.

## Honesty check

- Fires only on a terminal state that is true when sent, once.
- No estimate, no progress, no cheer, no promise.
- States only what the app knows: the end, the project, a failure reason it has already classified.
- Off in one switch; and when the system permission is off, it does nothing rather than working around it.

## Tests that should exist

| What | Why it can fail |
|---|---|
| Each end kind maps to exactly the right banner or none, including that Stop and Quit raise none | A new end kind that falls through to "banner" |
| Not fired while Bristlenose is active; fired when it is not | The gate reads the wrong signal |
| Not fired when the switch is off; the default on a fresh install is on, read through the one accessor | The `@AppStorage` default trap |
| Not fired when the system permission is denied or undetermined | A banner raised through a back door |
| One banner per end, never two for the same run | A completion event handled twice (a resumed or re-attached run) |
| Every new key exists in all 21 full locales | The locale check |
| The decline path asks nothing a second time | A re-ask is needy |

Use the standard "prove each test can fail" discipline: mutate the gate and the switch default and see the tests redden.

## Not decided here

1. Several runs ending close together: one banner each, grouped by project, or one summary.
2. A count in the finished body.
3. Whether the failed body names the reason when it is known (proposed: yes, only from the existing classified set).
4. The reason strings' final form.
5. The minimised-window case in "What decides not in the app": confirm on a real Mac, and add a visible-window test if the active-app test alone misses it.

## What I could not verify

- The exact entitlement or capability a sandboxed Mac App Store build needs to post local notifications: believed to be none, from memory; Apple's documentation page returned only a title when fetched.
- Behaviour of a notification across a quit of the app (not relevant to this proposal, since nothing fires after a quit).
- Any existing deep-link route into a project from outside the app.
- That the run-end seam is a single place; the end kinds exist in `PipelineRunner`, but I did not trace where a banner would hook in.

## To approve

1. The firing table above.
2. The text, or the changes you want.
3. First-ask on the first analysis start, and a silent decline.
4. The Settings row and its wording.
5. The open items, or which of them to decide now.

Nothing is implemented until these are approved.
