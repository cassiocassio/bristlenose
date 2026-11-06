# The run-finished banner: a design for approval

Status: proposal for owner approval, 6 Nov 2026. Nothing is built. Under the R114 UX gate (complete mockup, review and explicit approval before new UX is implemented) this is the review artefact; the mockup is `docs/mockups/perceived-wait-run-banner.html`. Why it exists, and the evidence behind it: `docs/design-perceived-wait.md`, candidate A. Earlier direction it builds on: `docs/design-desktop-nav-toolbar-rearrangement.md` § 10.4.

## What it is

When an analysis ends and the researcher is not in Bristlenose, the Mac raises one ordinary notification banner. That is the whole feature. It exists so a researcher can leave a 40-minute run and be told, truthfully, when to come back.

It stays on the Mac. Nothing here reaches an iPhone or Watch; that is a separate decision (`design-perceived-wait.md`, "Reaching the phone and Watch").

**The purpose of the banner (owner, 6 Nov 2026): "do I need to look at this?"** Every word is tested against that. The banner is a triage: it tells a researcher who has gone away whether something needs them, and how much. A finished run says *nothing needs you, open it when you like*; a failed or partly failed one says *it needs you*, and how bad it is (which stage, how many sessions are done). Anything that does not help that decision is a candidate to cut, and the system truncates a long body, so the order is by how much each fact helps the decision: the outcome first, then what says how bad (the reason, the sessions done), then facts that only inform (the duration last, so truncation drops it first).

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
| Completed (`run_completed`, no failed session) | yes | the project name | Analysis finished · N sessions |
| Completed with some sessions failed (`.completedPartial`) | yes | the project name | Analysis finished with failures · N of M sessions |
| Failed (`.failedWithDiagnostic`, or `.failed`) | yes | the project name | The analysis didn’t finish, plus the reason (from the run's cause category) and the sessions done |
| Stopped by the researcher | **no**: they just pressed Stop, and "Analysis stopped" is plain in the window | | |
| Ended because the app quit (`.stopped(interrupted: true)`) | **no**: nothing is alive to send it | | |

And only when **all** hold: the switch is on; macOS has allowed notifications; Bristlenose is **not** the frontmost app at the moment the run ends.

**Never:** a banner for a run that is still running, a progress banner, a reminder, a second banner for the same end, or a banner on app launch about a past run. The banner reports an end that happened while the researcher was away; it does not nag.

## The text

**Decided (owner, 6 Nov 2026):** the app's own sentence case, not Apple's title-style capitalization; fragments in the body are fine. **Real-life check:** the owner's own Notification Center (a screenshot, 6 Nov 2026) is full of notifications from Mac apps and scripts the same working audience uses, and none is title-cased. The pattern in every useful one is the same: the **title says what or where** (a project, a repo, a sender) and the **body says what happened**, often with counts and, on a failure, the detail (for example "N passed · M failed" followed by the first failing item). Researchers are used to this, so rich text is native, not intrusive.

So the proposal follows that pattern, and reverses my first draft (outcome in the title, project in the body). **It also reverses my first draft's length:** I wrote one short line, and the notifications in the screenshot run to two or three lines of real detail before the system truncates them. So the body leads with the outcome and then carries the facts the app already has at the end of a run.

| Case | Title | Body (proposed; what each fact is read from is in the next list) |
|---|---|---|
| Finished | the project's name | "Analysis finished · {{count}} sessions · {{duration}}" |
| Finished with some sessions failed | the project's name | "Analysis finished with failures · {{done}} of {{total}} sessions · sessions {{list}} didn’t finish" |
| Didn't finish, reason known | the project's name | "The analysis didn’t finish · {{reason}} · {{done}} of {{total}} sessions are done" |
| Didn't finish, reason not known | the project's name | "The analysis didn’t finish · {{done}} of {{total}} sessions are done" |

**What the app has at the end of a run (checked 6 Nov 2026 against a recorded run's end event and `events.py`):**
- **Sessions found, done and failed:** the end event's summary carries, per stage, how many were attempted and succeeded and which failed. The failed entries name sessions; turning them into session numbers is the implementer's job.
- **Duration:** the end event carries the start and end times, so "38 min" is a fact. It also lets the researcher see how the run compared with the time they were told.
- **The reason for a failure:** a failed run carries a structured cause category (the full list is in the next section). It is named for every category with a plain-words phrase.
- **Not in the end event:** quote counts and theme counts. The summary's "themes" figure counts calls, not themes. A quote or theme count would need a separate read and is **not proposed**.
- **Available but not proposed:** the token counts and the cost estimate are in the end event. Putting a cost in a banner is a different kind of statement (it is an estimate, and it is money); it is the owner's call, and I have left it out.

**On the numbers in "{{done}} of {{total}} sessions are done":** this is the one place the text makes a claim about work kept. It is true only if "done" is defined as a session that has finished the stages that the next Analyse would otherwise redo. Define it once, from the manifest, and test it against a run that stopped halfway. Until it is defined, the banner shows the session total and the reason and leaves the done count out.

- **The title is the project name alone (decided, owner, 6 Nov 2026).** On macOS 27 a notification shows the app's icon, the title, a relative time and the body, and no app name (the owner's Notification Center). The icon identifies Bristlenose; the title carries what matters, and a long project name is not cut short by a prefix. Apple's HIG also says not to repeat the app name. The title is the study's own name, which is Bristlenose's own and never follows the folder (ruling 10). The system supplies the icon and the relative time, so neither is in our text.
- **Put the outcome first in the body.** The system truncates a long body at a few lines with an ellipsis (visible in the screenshot), so what matters leads.
- **Counts are proposed, pending approval**, because the evidence on this audience is that counts and detail are normal.
- **Strings.** "The analysis didn’t finish" is **shipped** (`failedTitle`). "Analysis finished" and "Analysis finished with failures" are new (a shipped tooltip, "Analysis finished with failures for {{project}}", is the nearest). "{{count}} sessions" and "{{failed}} of {{total}} sessions" need plural keys (CLDR via the app's i18n, not the CLI `inflect`). All need the 21 full locales and an entry in `docs/platform-text-map.md`. Provider names are product names (Claude, ChatGPT).
- **Settings label:** "Notify when an analysis finishes or stops". New; a positive switch, on by default.
- **The failure reason** comes from the run's own cause category and is named whenever the category has a plain-words phrase (decided; the table below). It is never the raw cause message, which can hold file names and technical detail, and never an invented cause.
- **Plain words.** "Analysis", not "run" or "pipeline" (`docs/glossary.md`). No exclamation, no emoji. The failed banner says what is true and does not tell the researcher what to do.
- **When previews are hidden** the system shows only the icon and the word "Notification". Register one category per outcome with a generic placeholder with no project name ("Analysis finished" and "The analysis didn’t finish"). The placeholder is set when the categories are registered, so register them again if the researcher changes the app's language, or it stays in the old language.

### The failure reason, by category

Proposed English, for the owner's approval. The categories are the run's own (`CauseCategoryEnum` in `bristlenose/events.py`); I took their meanings from their names and comments, so each needs checking against what actually raises it. Provider names are product names (Claude, ChatGPT, Gemini, Azure OpenAI). All are new strings for the 21 locales. The reason follows "The analysis didn’t finish · ".

| Category | Proposed phrase |
|---|---|
| auth | {{provider}} rejected the key |
| out_of_credit | {{provider}} is out of credit |
| quota | {{provider}} is rate-limited |
| api_request | {{provider}} rejected the request |
| model_unavailable | The model isn’t available |
| api_server | {{provider}} had a server problem |
| network | No connection to {{provider}} |
| output_truncated | {{provider}}’s answer was cut short |
| whisper | Transcription failed |
| missing_input | A recording is missing |
| unusable_input | A recording couldn’t be read |
| cloud_fetch | A recording wasn’t downloaded in time |
| disk | Couldn’t write to disk |
| missing_dep, missing_binary | A required part is missing |
| unknown, deferred, user_signal | none: say nothing beyond "The analysis didn’t finish". **The banner never says "unknown" or "no reason given" (owner, 6 Nov 2026): the researcher goes to look.** |

Notes: the `cloud_fetch` phrase reuses the shape of an existing honest-failure string (the Screens lens already says a recording "wasn't downloaded to this Mac in time"); it is a plain statement of what happened, with no wait label, glyph or provider advice, which is what the settled cloud-files decision permits. `deferred` and `user_signal` are not failures the researcher needs told.

## The permission flow

macOS delivers nothing until the researcher has allowed it, so "on by default" means asking once, in context, not silently. **Checked against Apple's text on 6 Nov 2026** (sources at the end of this section); the first draft of this section was written from assumption and is replaced.

1. **When:** the first time an analysis starts after the feature ships. Apple's own developer guidance says to make the request "in a context that helps people understand why", gives the example of asking after a first reminder is scheduled, and says this is better than asking on first launch. The privacy guidance agrees: ask when the person uses a feature that needs it, not at launch unless the app cannot work without it.
2. **How:** the system's own prompt, from the standard authorization request for alert and sound (no badge: see below). **The system alert has no text of ours in it that I could find**, so the in-context moment is the only explanation the researcher gets. That is a real risk: a bare "Bristlenose would like to send you notifications" arriving as an analysis starts could be declined by reflex. I did not verify whether macOS lets an app supply any wording in this alert; for notifications it appears not to. Test it on a first run.
3. **A pre-alert screen of our own is allowed, but not needed, and not proposed.** Apple permits one "if it's essential to provide additional details", with strict rules: a single button called "Continue" or "Next" that opens the system alert, and no Cancel or Close. The privacy page names camera, microphone, location, contacts, calendar and tracking in that guidance, not notifications, so I am applying it by analogy. If the first-run test shows reflex declines, a one-line pre-alert is the fallback, built to those rules.
4. **If allowed:** nothing more to say.
5. **If declined:** nothing is asked again, and **the platform enforces this**: Apple's documentation says later authorization requests do not prompt. The app can only point the researcher to System Settings. The Settings row reads as unavailable with one line saying why, and an "Open Notification Settings…" button (see the observation below); it never re-asks.
6. **If never asked or declined, and a run ends:** no banner and no fallback chime. Check the authorization status before posting anything (Apple's guidance: people can change it at any time).

**Observed on this Mac, macOS 27.0 (6 Nov 2026), in the spike** (two screenshots from the owner, and the spike's log):
- **The permission request is a temporary banner, not a modal alert.** It reads "“SpikeSubject” Notifications — Notifications may include alerts, sounds and icon badges." That is the system's fixed text, which confirms the earlier worry: **no wording of ours can be in it.**
- **In the spike the request came back "not granted" 4.5 seconds after it started, and System Settings then showed Allow notifications switched off for the app.** I cannot tell from the screenshots whether the banner was clicked or expired unattended. If an unanswered banner resolves as a denial, then a researcher who clicks Analyse and looks away loses the feature **silently and for good**, because the app cannot ask again. Either way the design should not leave the one chance to the luck of where their eyes are.
- **Two responses, both small:** (a) reconsider the one-button pre-alert (Apple's "Continue" rules, above; **wording decided by the owner, 6 Nov 2026: title "Notify me when analysis finishes", body "macOS will ask next whether Bristlenose can send notifications. You can change this in Settings > General."**): it makes the researcher stop and look at the moment the system banner appears, so it is no longer "not needed", it is the thing that stops a missed banner becoming a permanent denial. (b) The Settings row, when notifications are off in System Settings, carries an **"Open Notification Settings…" button**. That is not a re-ask (it opens the system pane for the app, the one place a decision can be changed); my earlier line "no button" should have said "no button that re-asks".

**What System Settings gives the researcher, per app** (same screenshot): where it appears (desktop, Notification Centre, Lock Screen), **Alert style (Temporary or Persistent)**, sound, previews (Default), grouping (Automatic), and "Summarise notifications" **switched on by default for the app**. Three consequences for us:
- **A temporary banner goes away after a few seconds.** The whole case here is the researcher being away, so what they will actually find is the entry in the notification list (and the Lock Screen, if locked). The banner is a first nudge, not a sign that waits for them. Researchers who want it to stay can set Persistent; we cannot force that.
- **If a researcher uses Scheduled Summary, an ordinary notification can be held for the next summary**, which would delay "finished" by hours without any error. Apple's interruption levels are the lever: Time Sensitive overrides scheduled delivery and breaks through a Focus; the default does not. I proposed the default (respect the researcher's schedule). That is now an open decision, not a settled one (below).
- **Everything in that pane is the researcher's; we build none of it.** (Consistent with "what the platform already does for us".)

**Provisional ("quiet trial") authorization is confirmed unsuitable.** Apple's page says provisional notifications are delivered quietly: no sound, no banner, no lock screen, only an entry in Notification Center history, with Keep and Turn Off buttons. Its one real advantage is that it needs no up-front prompt. Its cost is that the first "your analysis finished" would arrive silently, which is exactly when the researcher has walked away. So it is not used, with the trade-off stated.

Sources opened 6 Nov 2026: Apple HIG, Notifications and Privacy; Apple developer documentation, "Asking permission to use notifications".

## What Apple's guidance says about the banner itself

From the HIG Notifications page (opened 6 Nov 2026). Where it bears on the proposal:

| Guidance (in my words) | What it means here |
|---|---|
| Notifications do not appear when the app is in front by default; show the information in the window instead (Mail adds the message to the list) | **Partly right, and I corrected it** after reading the developer documentation: see "What the platform already does for us" below. The default depends on a delegate being set. |
| Avoid several notifications for the same thing | One banner per end, as designed. |
| Avoid telling people to do a task in the app | The banner reports; it does not instruct. |
| Use an **alert**, not a notification, for an error message | Applies to errors shown to someone in the app. A background run that did not finish is a status the researcher is away from, so a notification is the only channel; the error detail still appears in the window on return, as today. Noted as a tension, not a conflict. |
| Avoid sensitive, personal or confidential information, because you cannot predict who sees it | The owner has decided the project name is in the banner by default. See the next row. |
| Provide generic body text for when previews are hidden; the system then shows only the icon and "Notification" | **Use it.** Set the hidden-previews placeholder to a generic line without the project name (for example "Analysis finished"), so a researcher who has hidden previews system-wide, or is sharing a screen with previews off, never exposes a client name. This honours the owner's decision and Apple's guidance together, at no cost. |
| Titles: short, title-style capitalization; bodies: complete sentences. Let the system show the app name (**it does not on macOS 27**; see the text section) | **Decided (owner): the app's own sentence case, and fragments in the body.** Apple's guidance is not followed here, knowingly; the owner's own Notification Center shows the working Mac audience's real notifications do not follow it either. |
| Consider a sound, but do not rely on it | System default sound; the text carries the meaning. |
| Badges only for unread notification counts, never the only signal | No badge, as designed. |
| Do not use an action that merely opens the app | No action button; clicking the banner opens the project, which is the expected default. |

## What the platform already does for us (checked 6 Nov 2026)

The aim is to use the system's notification behaviour and rebuild none of it. Sources opened: the UserNotifications documentation (`UNUserNotificationCenter`, `UNMutableNotificationContent`, the delegate's `willPresent`, handling notifications, `UNNotificationInterruptionLevel`, `hiddenPreviewsBodyPlaceholder`, `UNNotificationRequest`), the HIG Managing notifications page, and AppKit's `requestUserAttention`. "Verified" means that page says it; "inferred" means I am reading around what it says.

**Free, so do not build it:**

| The system gives us | Source and status | So we do not |
|---|---|---|
| The banner, the sound, the notification list entry, the relative time, the app icon | Notifications pages. Verified. | draw our own banner, chime, timestamp or icon |
| The researcher's per-app choices in System Settings (style, sound, previews, grouping) and the option to silence everything | HIG Managing notifications. Verified. | build our own sound picker, preview toggle or grouping control. Our one in-app switch is enough, and Apple says an app should offer an in-app way to change the choice. |
| Focus and scheduled summary: the default interruption level, "active", is delivered immediately but does **not** break through a Focus; the notification is still available the moment it arrives even if its alert is delayed | HIG and `UNNotificationInterruptionLevel`. Verified. | add any "do not disturb" logic of our own, or ask for Time Sensitive (which is for events relevant in the moment and breaks through Focus; a finished analysis does not justify that) |
| Grouping: a thread identifier visually groups related notifications | `UNMutableNotificationContent`. Verified that it exists and what it is for. | build a grouped-banner of our own. Use one thread per project. |
| The click: the researcher clicking a banner activates the app and calls our delegate with the notification's own data | Handling notifications. Verified for the delegate call; that it activates the app is the normal behaviour and I did not find the page stating it. | open the app ourselves. We only choose which project to show, from an id carried in the notification's data. |
| Removing a stale notification once the researcher has dealt with it | `removeDeliveredNotifications`. Verified that it exists. | leave a "finished" entry sitting in the list for a run the researcher has already opened. Clear it when they open that project (a small recommendation, not a requirement). |
| Hiding the preview when the researcher has chosen to | `hiddenPreviewsBodyPlaceholder`. Verified. | invent our own privacy mode. Set the placeholder (above). |
| Authorization state and a one-time prompt | Asking permission. Verified. | build a re-ask or our own consent screen |

**One correction to my earlier statement.** I had said the frontmost rule "is the platform's default, not code we must write." The developer documentation is more specific, and it matters:
- If a delegate is set and it does **not** implement `willPresent`, the system treats the notification as not to be shown while the app is in the foreground. Verified.
- If **no** delegate is set at all, the system uses the notification's own options and **would show a banner in the foreground**. Verified.
- The Mac app has no notification code today, so **no delegate exists**. A delegate must be assigned before any notification is posted, and it is needed anyway to handle the click.

So the platform-grain approach is: set the delegate, leave `willPresent` unimplemented (or return none), post the notification whenever a run ends, and let the system decide by its own idea of "foreground". That replaces the hand-rolled active-app check in the next section. **What I could not verify is that macOS's "foreground" matches the 99% case** (hidden, buried under other windows, another app in full screen, a different Space) or what it does for a minimised window. Whether "present none" also keeps the entry out of the notification list is not stated either. **A short spike on a real Mac settles all of it** (see "What decides"). Until then the explicit active-app check stays as the fallback.

**The Dock bounce is the one place we would be doing something the notification system does not.** The attention request is a separate channel from the notification: Apple's page says activating the app cancels it, that it does nothing for an app that is already active, and that a spoken notification occurs if spoken notifications are enabled. It does not say whether the researcher's Focus or notification settings apply to it, and I could not confirm the difference between the informational and critical types (the page I read describes only the two names). A bounce that ignores the researcher's Notification settings would go against the platform's grain. **Recommendation: leave it out of the first version.** The banner, the sound and Focus already own attention, and one channel is one thing the researcher can switch off. It is recorded in § 10.4 as direction, so this is the owner's call.

**Not following Apple on purpose:** Apple recommends localizing notification text with `localizedUserNotificationString` so the string is resolved at delivery. The app's strings come from its own locale files through the i18n layer, and the notification is delivered at once, so there is no gap for a language change to fall into. The one exception is the hidden-previews placeholder, above.

## The Settings switch

- **Where:** Settings ▸ General. The tab holds one row today ("Default location for new projects"), in a grouped Form; the switch is a second row in the same group, with no new section header.
- **Default:** on. **The trap:** `@AppStorage` defaults are not registered defaults, so any other code reading the same key (for example the code that decides whether to fire) must read it with the same default, or the two disagree on a fresh install. Read the preference through one accessor.
- **Reads positively.** A "mute alerts" label would make the on state the double negative.
- **System permission off:** the row is disabled and carries one line of secondary text pointing at System Settings. It does not duplicate the system toggle.

## Interactions

- **Click the banner:** opens Bristlenose with that project selected. The mechanism for selecting a project from outside (the project id, not the path: identity is never from a path) is for the implementer to confirm; I did not find an existing external route.
- **Sound:** the system default notification sound.
- **Dock:** nothing in the first version (see "What the platform already does for us"); the owner decides.
- **Grouping:** one thread identifier per project, so several ends close together stack under that project. Whether several projects finishing together should also group is still open.
- **One banner per end:** use the run's own id as the request identifier, so a re-delivered end cannot post twice. Whether a repeated identifier replaces the earlier entry is not stated on the pages I read; test it.
- **Mac asleep:** macOS shows the banner on wake. Nothing for us to do.
- **Focus modes and Do Not Disturb:** respected; we do not request Time Sensitive.
- **VoiceOver:** an announcement of the end when the app is frontmost and no banner is shown ("Analysis complete" is the recorded string in § 10.4); keep it to what is already announced today unless approved separately.

## What decides "not in the app"

The case this serves is the 99% one: the researcher has started a run and then **hidden Bristlenose, left it under a clutter of other windows, or gone full-screen in another app**. In all three, Bristlenose is not the app they are using, and the banner is how they find out.

**Measured, 6 Nov 2026 (the spike).** A throwaway two-app test, outside the repo: one app posted a notification in each state with a notification delegate set that logs when the system calls `willPresent` (which it does only when it considers the app foreground), and a second app went full screen to be the "other app". macOS 27.0 (26A428), one Mac, a development-signed app.

| State when the run ends | Did the system treat the app as foreground? (`willPresent` called) | In the notification list afterwards |
|---|---|---|
| 1. Active, in front | **Yes**, so the banner is suppressed | **Yes**, even though suppressed |
| 2. Hidden (⌘H) | No, so the system shows the banner | Yes |
| 3. Another app active, our window visible behind it | No, so the system shows the banner | Yes |
| 4. Our only window minimised, app still the active app | **Yes**, so **no banner** | Yes |
| 5. Another app in full screen on its own Space | No, so the system shows the banner | Yes |

What it shows:
- **The system's idea of foreground is "the app is active"** (cases 1 and 4), and it matches what the researcher is doing in cases 2, 3 and 5: hidden, buried and full-screen-elsewhere all get a banner. The 99% case works with no code of ours.
- **One gap, case 4:** a researcher who minimises Bristlenose's only window but leaves it as the active app (looking at the Dock or an empty desktop) gets no banner, because the system still counts it as foreground. It is a narrow case, not a common one: most people move to another app after minimising, which is case 3.
- **A suppressed notification still lands in the notification list** (case 1). So if we let the system suppress it, a researcher who was watching still gets a "finished" entry in Notification Centre for a run they already saw. That is the stale entry the design says to avoid.
- **Not observed:** I could not see a banner on screen in cases 2, 3 and 5; the inference is from the system not asking the app and from the list entry. Someone should look once on a real run.

**Correction after a re-test (6 Nov 2026).** I re-ran the minimised case with a delegate that tells the system to present the notification. This time the app was **not** active after it was minimised (`isActive=false`), the system did not ask the app at all, and so it would have presented the banner itself. In the first run the app was still active in that state, but my test code had re-activated it after minimising, so that run may have created the condition it measured. **Whether a real ⌘M leaves the app active is unverified, so the minimised case is unresolved, not a confirmed gap.** I also could not capture the screen to see a banner (the capture produced no file), so no banner has been seen on screen in any run.

What follows from that, and holds either way:
- The gate at posting (`NSApp.isActive && NSApp.occlusionState.contains(.visible)` means do not post) is right in both readings.
- If the gate decides to post while the system still counts the app as foreground, the system suppresses it unless the delegate says otherwise. So the delegate **implements `willPresent` and returns banner, list and sound**: our gate has already decided the researcher is not looking, so the delegate always presents. This part is untested visually.

**Decision (owner direction, 6 Nov 2026: minimising is a real habit among Mac users, so the minimised case is covered): gate at the point of posting, with one test, and use the delegate for the click.** Post the notification only if Bristlenose is **not** both active and showing a window: `NSApp.isActive && NSApp.occlusionState.contains(.visible)` means "the researcher is looking at it, update the window, post nothing". That covers case 4 and leaves no stale list entry in case 1, for one line of our code. It matches the system's own rule everywhere else, so it reinvents nothing. The delegate still has to exist, for the click and to present what the gate has decided to post (see the correction above). Do not use `scenePhase`.

**If the sidebar is closed but the researcher is in the app, no banner** (decided).

**Other things the spike did not settle:** whether a repeated request identifier replaces an earlier list entry; behaviour on macOS 15 and 26 (the floor is 15.0; the spike ran on 27.0 only); a release-signed, sandboxed build (the spike was a plain development-signed app, and a notifying app was refused until it sat in `~/Applications`, so a Debug build run from Xcode's build folder should be checked).

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
| With Bristlenose active and a window visible, nothing is posted; hidden, buried, behind a full-screen app, or active with its only window minimised, a banner is posted. A delegate exists before the first post. | The one-line gate reads the wrong signal (the minimised case is the one the system's own rule misses) |
| One request identifier per run | A re-attached or resumed run posting its end twice |
| Not fired when the switch is off; the default on a fresh install is on, read through the one accessor | The `@AppStorage` default trap |
| Not fired when the system permission is denied or undetermined | A banner raised through a back door |
| The hidden-previews placeholder carries no project name | The one place the project name could leak when the researcher has hidden previews |
| Every new key exists in all 21 full locales | The locale check |
| The decline path asks nothing a second time | A re-ask is needy |

Use the standard "prove each test can fail" discipline: mutate the gate and the switch default and see the tests redden.

## Not decided here

1. *(Decided, owner, 6 Nov 2026: several runs ending together each post their own banner and say their own thing. No grouping or summary logic of ours; the one thread identifier per project is the system's own grouping and costs nothing.)*
2. *(Decided, owner, 6 Nov 2026: the session count is in the body, because it is useful.)*
3. *(Decided, owner, 6 Nov 2026: name the failure reason whenever the run's cause category has a plain-words form, not only for the ones a researcher can act on. Where there is no reason to give (unknown, or the researcher's own signal), say nothing more.)*
4. The reason phrases: proposed in "The failure reason, by category"; the final wording and a check of each category against what actually raises it.
5. The minimised-window case in "What decides not in the app": confirm on a real Mac, and add a visible-window test if the active-app test alone misses it.

6. *(Decided provisionally, owner, 6 Nov 2026: the one-button pre-alert goes in the first version, and the owner will judge how it feels. They do not love it; it is there because notifications are off until allowed and the system's own request is a temporary banner that is easy to miss. Easy to remove: it is one screen in front of one system call. Watch for reflex declines and for the screen feeling like a hurdle.)*
7. The Dock bounce (recommended out of the first version).
8. The title/body order and the session count in the body (proposed above, following what the owner's own notifications look like).
9. *(Done 6 Nov: see "What decides". Gate at the point of posting; confirm.)*

10. *(Decided, owner, 6 Nov 2026: the default interruption level. It respects the researcher's Focus and Scheduled Summary, and Time Sensitive is not requested. A researcher who uses Scheduled Summary may therefore have the notice held, which is their own setting at work.)*
11. *(Decided, owner, 6 Nov 2026: accept it as the starting place. The banner is temporary by the system's default and the entry stays in the notification list; Persistent is the researcher's own setting. Revisit if researchers report missing it.)*

*Decided since the last draft (owner, 6 Nov):* each run's own banner when several end together; the session count; naming the failure reason; default interruption level; sentence case and fragments; no Dock bounce; duration in the finished banner; "N of M sessions are done" on a failure, once "done" is defined.

## What I could not verify

- **Spike (6 Nov), setup note:** a notifying app was refused ("Failed to find or validate client") while it sat in a temporary folder, ad-hoc or development-signed, and validated once copied into `~/Applications`. A Debug build run from Xcode's DerivedData folder should be checked for the same thing before anyone concludes notifications do not work in a dev build. The foreground cases then ran (see "What decides").
- That macOS's own foreground rule matches the hidden, buried, full-screen and other-Space cases, and its behaviour for a minimised window; whether suppression keeps the entry out of the notification list; whether a repeated request identifier replaces an earlier entry; what the Dock attention request does under Focus; that a nil trigger delivers at once (standard behaviour, not stated on the pages I read).
- The exact entitlement or capability a sandboxed Mac App Store build needs to post local notifications: believed to be none, from memory.
- Whether the system notification-permission alert on macOS can carry any wording of ours (it appears not to), and whether provisional authorization behaves the same on macOS as on iOS; the page I read describes it generally.
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
