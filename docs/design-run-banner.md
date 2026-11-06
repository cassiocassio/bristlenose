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
| Completed (`run_completed`, no failed session) | yes | the project name | Analysis finished · N sessions |
| Completed with some sessions failed (`.completedPartial`) | yes | the project name | Analysis finished with failures · N of M sessions |
| Failed (`.failedWithDiagnostic`, or `.failed`) | yes | the project name | The analysis didn’t finish, plus the reason when the app already knows it |
| Stopped by the researcher | **no**: they just pressed Stop, and "Analysis stopped" is plain in the window | | |
| Ended because the app quit (`.stopped(interrupted: true)`) | **no**: nothing is alive to send it | | |

And only when **all** hold: the switch is on; macOS has allowed notifications; Bristlenose is **not** the frontmost app at the moment the run ends.

**Never:** a banner for a run that is still running, a progress banner, a reminder, a second banner for the same end, or a banner on app launch about a past run. The banner reports an end that happened while the researcher was away; it does not nag.

## The text

**Decided (owner, 6 Nov 2026):** the app's own sentence case, not Apple's title-style capitalization; fragments in the body are fine. **Real-life check:** the owner's own Notification Center (a screenshot, 6 Nov 2026) is full of notifications from Mac apps and scripts the same working audience uses, and none is title-cased. The pattern in every useful one is the same: the **title says what or where** (a project, a repo, a sender) and the **body says what happened**, often with counts and, on a failure, the detail (for example "N passed · M failed" followed by the first failing item). Researchers are used to this, so rich text is native, not intrusive.

So the proposal follows that pattern, and reverses my first draft (outcome in the title, project in the body):

| Case | Title | Body |
|---|---|---|
| Finished | the project's name | "Analysis finished · {{count}} sessions" |
| Finished with some sessions failed | the project's name | "Analysis finished with failures · {{failed}} of {{total}} sessions" |
| Didn't finish, reason known | the project's name | "The analysis didn’t finish · {{reason}}" |
| Didn't finish, reason not known | the project's name | "The analysis didn’t finish" |

- **The title is the study's own name**, which is Bristlenose's own and never follows the folder (ruling 10). The system supplies the app icon and a relative time ("52m ago" in the screenshot), so neither is in our text, and Apple's HIG says not to repeat the app name.
- **Put the outcome first in the body.** The system truncates a long body at a few lines with an ellipsis (visible in the screenshot), so what matters leads.
- **Counts are now proposed, pending approval**, because the evidence on this audience is that counts are normal ("3094 passed"). The session count is a fact the app already has. A quote count is a separate question (the same as a "found so far" count) and stays out.
- **Strings.** "The analysis didn’t finish" is **shipped** (`failedTitle`). "Analysis finished" and "Analysis finished with failures" are new (a shipped tooltip, "Analysis finished with failures for {{project}}", is the nearest). "{{count}} sessions" and "{{failed}} of {{total}} sessions" need plural keys (CLDR via the app's i18n, not the CLI `inflect`). All need the 21 full locales and an entry in `docs/platform-text-map.md`. Provider names are product names (Claude, ChatGPT).
- **Settings label:** "Notify when an analysis finishes or stops". New; a positive switch, on by default.
- **The failure reason.** The app already classifies why a provider call failed ("{{provider}} is out of credit", "rejected this key", "is rate-limited", in `llmSettings.validation`). The banner uses only a reason from that existing set, in a short form ("Claude is out of credit"), and says nothing more when the cause is unknown. It does not invent a cause. The short forms are new strings.
- **Plain words.** "Analysis", not "run" or "pipeline" (`docs/glossary.md`). No exclamation, no emoji. The failed banner says what is true and does not tell the researcher what to do.
- **When previews are hidden** the system shows only the icon and the word "Notification". Register one category per outcome with a generic placeholder with no project name ("Analysis finished" and "The analysis didn’t finish"). The placeholder is set when the categories are registered, so register them again if the researcher changes the app's language, or it stays in the old language.

## The permission flow

macOS delivers nothing until the researcher has allowed it, so "on by default" means asking once, in context, not silently. **Checked against Apple's text on 6 Nov 2026** (sources at the end of this section); the first draft of this section was written from assumption and is replaced.

1. **When:** the first time an analysis starts after the feature ships. Apple's own developer guidance says to make the request "in a context that helps people understand why", gives the example of asking after a first reminder is scheduled, and says this is better than asking on first launch. The privacy guidance agrees: ask when the person uses a feature that needs it, not at launch unless the app cannot work without it.
2. **How:** the system's own prompt, from the standard authorization request for alert and sound (no badge: see below). **The system alert has no text of ours in it that I could find**, so the in-context moment is the only explanation the researcher gets. That is a real risk: a bare "Bristlenose would like to send you notifications" arriving as an analysis starts could be declined by reflex. I did not verify whether macOS lets an app supply any wording in this alert; for notifications it appears not to. Test it on a first run.
3. **A pre-alert screen of our own is allowed, but not needed, and not proposed.** Apple permits one "if it's essential to provide additional details", with strict rules: a single button called "Continue" or "Next" that opens the system alert, and no Cancel or Close. The privacy page names camera, microphone, location, contacts, calendar and tracking in that guidance, not notifications, so I am applying it by analogy. If the first-run test shows reflex declines, a one-line pre-alert is the fallback, built to those rules.
4. **If allowed:** nothing more to say.
5. **If declined:** nothing is asked again, and **the platform enforces this**: Apple's documentation says later authorization requests do not prompt. The app can only point the researcher to System Settings. The Settings row reads as unavailable with one line saying why, and has no button that re-asks.
6. **If never asked or declined, and a run ends:** no banner and no fallback chime. Check the authorization status before posting anything (Apple's guidance: people can change it at any time).

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
| Titles: short, title-style capitalization; bodies: complete sentences. Let the system show the app name | **Decided (owner): the app's own sentence case, and fragments in the body.** Apple's guidance is not followed here, knowingly; the owner's own Notification Center shows the working Mac audience's real notifications do not follow it either. |
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

**Preferred (platform grain):** post the notification whenever a run ends, with a delegate set and no `willPresent`, and let the system suppress it while Bristlenose is in the foreground. No gate of ours.

**Fallback, if the spike shows the system's idea of foreground is wrong for any of the cases:** an explicit test of whether Bristlenose is the **active application** when the run ends, `NSApp.isActive`, with `didBecomeActive` and `didResignActive`. Active-ness, not visibility, is the test, so a Bristlenose window visible but buried under another app's windows still gets a banner, and so does a different app in full screen. **Not `scenePhase`**, which is unreliable on macOS for this (the recorded trap in § 10.4). If a researcher has minimised Bristlenose's only window but the app is still active, the active-app test alone misses it, and the gate should also treat "no visible Bristlenose window" as not in the app.

**If the sidebar is closed but the researcher is in the app, no banner** (decided).

**The spike** (Debug build, a few lines, on the owner's Mac): post a notification from a button, then check whether it shows when the app is (1) active in front, (2) hidden with ⌘H, (3) behind another app's window, (4) behind another app in full screen, (5) on a different Space, (6) minimised; and whether it still appears in the notification list when it is suppressed. It also settles whether a repeated identifier replaces an earlier entry.

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
| A delegate exists before the first post, and with Bristlenose in the foreground nothing is shown; with it hidden, buried or behind a full-screen app, a banner is | No delegate would show the banner in the foreground, the opposite of intent |
| One request identifier per run | A re-attached or resumed run posting its end twice |
| Not fired when the switch is off; the default on a fresh install is on, read through the one accessor | The `@AppStorage` default trap |
| Not fired when the system permission is denied or undetermined | A banner raised through a back door |
| The hidden-previews placeholder carries no project name | The one place the project name could leak when the researcher has hidden previews |
| Every new key exists in all 21 full locales | The locale check |
| The decline path asks nothing a second time | A re-ask is needy |

Use the standard "prove each test can fail" discipline: mutate the gate and the switch default and see the tests redden.

## Not decided here

1. Several runs ending close together: one banner each, grouped by project, or one summary.
2. A count in the finished body.
3. Whether the failed body names the reason when it is known (proposed: yes, only from the existing classified set).
4. The reason strings' final form.
5. The minimised-window case in "What decides not in the app": confirm on a real Mac, and add a visible-window test if the active-app test alone misses it.

6. Whether to test a one-line pre-alert if first runs show reflex declines.
7. The Dock bounce (recommended out of the first version).
8. The title/body order and the session count in the body (proposed above, following what the owner's own notifications look like).
9. Run the foreground spike before the gate is fixed.

*Decided since the last draft:* sentence case and fragments (owner, 6 Nov).

## What I could not verify

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
