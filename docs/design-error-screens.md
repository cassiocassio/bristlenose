# Error screens

These rules apply to a main-content error or unavailable state: native pane,
web page, or a contained part of either. They are design guidance first. A
shared presentation contract comes later, after these choices have been made
and reviewed.

## The screen answers one question

1. **Headline:** what happened, in plain language.
2. **Body:** the reason, context, or prerequisite only when it changes what the
   researcher can do.
3. **Action:** the most useful next step, if there is one.

Do not put an exit code, stack trace, path, or raw CLI output in the main pane.
Those are diagnostic records, not explanation.

`Failed to start` may need no body at all. If the only known fact is that the
engine stopped, a made-up explanation is worse than a concise headline.

A contained view failure names the view (`Quotes couldn’t be shown`), rather
than saying “this view.” Its working navigation is already the way to leave;
do not add an instruction to use it. Use the broken-view glyph, not a severity
warning, for this unavailable part of an otherwise usable report.

For a genuinely small chrome fragment, use only the quiet broken-view glyph.
It follows the familiar failed-image pattern: the surrounding interface stays
usable, and refresh is an adequate implied remedy. Do not add copy, a button,
diagnostics, or a feedback door.

## Recovery before Retry

Offer Retry only when another attempt has a reasonable chance of succeeding.
The failure classification, not a generic UI habit, decides this.

| Situation | Main action |
| --- | --- |
| The user can fix something here | The fix: `Set Up Provider…`, `Locate…`, `Sign In Again` |
| An external condition can change | State that condition briefly; retry only when another attempt is meaningful |
| A temporary condition is known | `Retry`, with the relevant short context |
| A known limit or product defect has no credible new condition | No blind Retry |

Never make Retry the default action unless it is both safe and credible. A
button that repeats the same failure wastes a click and conceals the real
problem.

An unexpected render crash and a failed data read are not the same state. The
former has no blind Retry; the latter may offer Retry only after its request or
condition has been classified as transient.

## Diagnostics live in diagnostics

The main state is not a log viewer. The existing project diagnostic popover is
the place for concise diagnostic context, Copy details, and Show Log when a log
exists. A failure may remove its main-pane actions only after its useful record
is reachable there.

## Feedback is selective

Offer `Send Feedback…` for an unusual, obscure, or high-information failure
that Bristlenose may learn from. Do not offer it for routine, expected events.

The problem report should prefill a short human summary and attach the safe
technical record needed to investigate. Do not explain to the researcher why
we want their report.

## Actions must fit

An action label is never truncated. The action set must fit horizontally at
every plausible detail-pane width, including localised labels. If it does not,
change the action set, copy, or pane geometry; vertical stacking is not the
escape hatch for this pattern.

At most one action is primary/default. Secondary actions must still be fully
legible, and an action that opens another surface uses an ellipsis.

## Review checklist

For each state, decide the wording and glyph as a human judgement:

- Is the headline true and brief?
- Does each body sentence change the user's next move?
- Is the glyph the right semantic concept, rather than merely the severity?
- Is every offered action credible?
- Is the diagnostic record reachable without crowding the pane?
- Does feedback earn the user's effort?
- Do full action labels fit at every plausible width?
