---
status: partial
last-trued: 2026-08-18 (sixth pass, `--topic accounts-pane-i18n` — §10's i18n bullet, reopened that morning and paid by the evening)
trued-against: HEAD@main on 2026-08-18 (d0478b15)
---

> **Truing status:** Partial — trued **twice** on 15 Aug 2026, and the second
> pass is the one that matters. The morning pass corrected pre-build claims by
> *reasoning*; this one corrects pre-tenant claims by *measurement*, after a
> live Microsoft 365 tenant was bought and Teams signed in.
>
> **Changed this pass:** §0's "nothing works" gate (Teams is registered and
> signs in; `CFBundleURLTypes` was never required and this doc said it was);
> §3's Q7 — **answered NO**, with the original inference preserved because it
> was a well-reasoned wrong guess; §6's "the timestamp is UTC" instruction,
> which is **wrong for the tier that ships** and is superseded in place.
>
> **Unchanged and still correct:** §1's priorities, §2, §4, §5's sequencing,
> §7's spine, §8, and §6's verification ladder.
>
> **Third pass, 16 Aug 2026 — a Google tenant, same lesson again.** A Business
> Standard Workspace was bought and a Meet recorded. Two claims met reality and
> one of them changed v1's scope: the Meet row in §3 had **no tier gate** where
> Zoom's said "Pro plan or higher", and Google's transcript turns out **not to
> be a file at all** — it is a tab inside a Gemini notes Doc, and every export
> flattens the two together. §5's "strongest artifact position" is corrected;
> §6 carries the Google specimens.
>
> **Zoom is parked, 16 Aug 2026 — a scheduling decision, not a design one.**
> `File ▸ Import ▸ Zoom` is withheld behind `BristlenoseFlags.cloudImportZoom`
> (default off) so Teams and Meet can reach releasable quality first. Everything
> in this document about Zoom still stands and still compiles; only the menu item
> is withheld. §5's Teams → Zoom → Meet *sequencing* is now overtaken by events
> in practice — Meet has a live tenant and Zoom has no account at all — but the
> reasoning behind that order is untouched and should be re-read, not re-derived,
> when Zoom is picked back up. Pick-up brief:
> `cloud-import-zoom-parked.md` in the maintainer's private handoffs.
>
> **Fifth pass, 18 Aug 2026 — the status block was the stalest thing in the
> file.** Four passes had trued individual sections while the block a cold reader
> reads *first* still said no Google client existed, no token persisted, no
> adapter derived row state and nothing had ever downloaded. All four were false,
> and each was contradicted by this same document elsewhere — the download by its
> own changelog, the persistence by §7. A section-by-section pass does not reach
> a summary, and a summary is what gets believed. Corrected from measurement;
> §9a still carries two claims of the same kind and is banner-flagged for its own
> pass.
>
> **No longer pre-contact.** The whole loop — tick, Picker, download, ingest —
> has run end to end on Meet, and Teams has downloaded from Graph. The transfer
> path is no longer the untested half; **third-party consent is**, and no amount
> of local testing can reach it.

## Changelog

- _2026-08-18 (fifth pass — the summary, which four section passes had missed)_ —
  trued up: rewrote the **status block** and truing banner, which carried four
  false load-bearing claims (no Google OAuth client; no token persisted; no
  adapter derives row state; nothing has ever downloaded) — each contradicted by
  this same document elsewhere, and the reason a cold reader would have concluded
  the feature did not work. Split the answered Picker probe from its still-open
  attendee sub-risk. Banner-flagged **§9a** as partially-trued and corrected its
  two flatly-false as-built claims ("there is no Settings ▸ Accounts pane"; "there
  are no `desktop.cloudImport.*` keys at all" — there are 120, seeded across 21
  locales since 16 Aug). §10: two of three registrations now exist, so the gate
  **moved to verification** rather than closing, with Google's sensitive-scope
  review named as the longer pole and the MSA precondition on Publisher
  Verification recorded. Preserved §9's sidebar prescription and recorded that
  reality answered it a third way (`importingBatch`, count-only, copy ring
  reused). Added the Scheduled column as-built with its three invariants; added
  the three-way Entra refusal taxonomy and `worthRetrying` to §6 req.5; added
  §7's new **"The grant's lifecycle"** subsection promoting four guards out of
  commit bodies; refreshed §9's test inventory and recorded that CI never
  compiles the Swift target. Anchors: `60321ec5`, `84d7c55e`, `d345cb56`,
  `357818b5`, `f8e78ae4`, `af9b38b4`, `d054b3d6`, `2cb58cf6`, `c837f8b5`,
  `49ec8a50`; `CloudImportOutline.swift:258`, `TeamsOAuth.swift:111-155`,
  `CloudImportStore.swift:23-52,165-171,683`, `ProjectSubtitle.swift:58-67`.

- _2026-08-18 — Settings ▸ Accounts, and the storage under it_ — three
  commits and a truing pass over the sections they contradicted.
  1. **One Keychain item per account** (`8901845f`). §7's diagnosis was exact and
     is now fixed: a second sign-in no longer overwrites the first in place.
     Keyed on a SHA-256 of the address — **not** on `oid`/`sub`, which was cut
     for v1. Enumeration, plus a one-shot migration off the old fixed key that
     **deletes** the legacy item.
  2. **The pane** (`d3b66642`) — a section per service, four states, and **no
     network call**: everything is derived from disk. That is what makes
     Microsoft's account-tier state still owed a writer while Google's is free.
     §9 said Mail Accounts; a sidebar-and-detail for four rows with one verb
     would be chrome around nothing, so it is sections. §2 of the mockup's
     "Can't reach it" state was **cut** on the same logic — it is a state of the
     network, not of the account.
  3. **A revoked sign-in stops vanishing** (`a27f85b4`). A refused refresh used
     to delete the grant, so the account disappeared from Settings —
     indistinguishable from having disconnected it yourself. It now keeps the
     row with the credential stripped, which preserves the reason the delete
     existed (a revoked refresh token fails identically forever) while giving
     "it just stopped working" somewhere to be answered.
  4. **iCloud sync reversed.** §7 and §10 both said non-synchronizable; cloud
     grants **stay synced**. The stolen Mac is the real loss event, iCloud
     Keychain is E2E regardless of ADP, and the timing was forced —
     `kSecAttrSynchronizable` cannot be flipped by `SecItemUpdate`, so the
     migration was the only cheap moment.

- _2026-08-18 (measured on a live account)_ — **the Picker grant survives a
  relaunch, and a file already granted is not asked for again.** Walked on a
  real Google account: quit, rebuild, reopen the window — signed in, no
  consent screen; then tick a recording granted in an earlier session and
  press Import — **no Picker at all**.
  Three things that were separately unproven now hold together:
  1. **Both halves of the grant round-trip the Keychain.** Google's is a *pair*
     — the listing token and the Picker's `drive.file` grant with its file ids
     — and `fetch` guards on the ids *before* it reads the media token, so a
     half-restore looks identical to a full one until an import is attempted.
     It is a full restore.
  2. **`MediaGrantPlan.decide` skips the round trip in practice**, not just in
     its unit tests.
  3. **The deep-research report's "cheapest possible win" is answered.** That
     report could only establish persistence as *documented*, and flagged
     explicitly that nobody in its corpus had tested whether a stored token
     also covers ids picked in an earlier batch. It does.
  Note what this does **not** yet prove: that the bytes then arrive. Skipping
  the Picker shows we did not *ask*; only a completed download shows the stored
  token is still good against Drive. Marked here so the distinction is not lost
  the next time someone reads "persistence works".
  Also settled the same day: **Google's Picker has a select-all**, so seeding
  it with the whole listing costs about one click rather than one per file —
  the measurement the listing-wide grant was committed pending, and it holds.
- _2026-08-17 (evening — the window stops being a dead end)_ — six fixes to
  the **shared** import window, so Teams inherits every one. Ordered by how
  badly each read to the researcher:
  1. **The sign-in could spin forever with no way out.** Measured:
     `import_phase signedOut -> signingIn` and then silence. The cause was
     mundane and invisible — a stack of Google sign-in and consent windows
     sitting behind Chrome, unseen. The flow was working the whole time. **The
     fix is not a timeout**: on macOS `ASWebAuthenticationSession` opens the
     *real* default browser, so nothing reports a cancellation when a tab is
     buried, and a genuine sign-in can take minutes — any deadline safe enough
     is useless, any deadline useful enough cancels people mid-password. It now
     names the platform, points at the browser, and offers Cancel.
  2. **"Queued" was a lie while the batch waited on the Picker.** Nothing was
     queued; we were waiting on a person. Its own state now, glyphless because
     the taxonomy says pending and running are status, not kinds.
  3. **Stop could not actually stop a browser round trip**, so a stopped batch
     could have its grant land minutes later and quietly start transferring.
     A generation counter makes a late return inert — same shape as (1).
  4. **Per-row cancel.** One stalled 465 MB transfer forced abandoning the four
     beside it. Each row now runs in its own cancellable `Task`; the transfer
     genuinely stops, because `URLSession.download(for:delegate:)` bridges task
     cancellation and `CloudDownloader` re-checks before anything reaches the
     project folder.
  5. **Stop becomes Done**, instead of falling back to a disabled "Import 0
     Recordings" — a dead end dressed as an action. And at zero the count is
     dropped entirely: a number inside a verb reads as a defect. A hidden
     sizing ghost — the real string in the real locale — stops the button
     growing under a stationary pointer when the first box is ticked.
  6. **New projects remember where studies live.** Both doors hardcoded
     `~/Documents`, the same decision written twice. One owner now
     (`ProjectFolderDefaults`), and it learns. A Settings row was asked for and
     deliberately not built: it would write the same value, so it can be added
     the moment remembering proves insufficient.
  Also measured, closing an item this doc flagged as decisive: **Google's
  Picker has a select-all**, so seeding it with the whole listing is nearly
  free and the listing-wide grant stays. And the one that cost the most:
  `KeychainHelper.serviceNames` is an **allowlist**, so the grant store shipped
  against an unregistered key and persisted nothing at all — no error, no
  crash, and a symptom that would have surfaced weeks later as "why am I
  signing in again?".
- _2026-08-17 (researched, 21 primary sources, adversarially verified)_ — what
  the platform actually permits, against Google's own current docs (most "Last
  updated 2026-07-22"). Four things that change what we do:
  1. **`prompt=consent` is documented Required, and so is `trigger_onepick`.**
     Google's parameter table marks both **Required** on the desktop Picker
     authorization URL — verified across en/it/ja renderings, and the same
     table marks four *other* params Optional, so the split is real. The
     Android sibling goes further: set Prompt to CONSENT "even if it was
     granted before", and `setOptOutIncludingGrantedScopes(true)`. So **the
     per-batch round trip is the design, not our misconfiguration** — the flow
     returns `picked_file_ids` *and* a fresh `code` you must exchange. Closes
     the open item: leaving `prompt=consent` alone was correct, and deleting it
     is not the free win it looked like. (Still unmeasured: what actually
     happens if `prompt` is omitted. Documented ≠ enforced.)
  2. **Which makes "ask over the whole listing" the right mitigation** — the
     round trip cannot be removed, only made rarer, and asking listing-wide is
     exactly how you make it rarer. Shipped in `dca4c1be`. Note the
     implementation trap the research flags: `setFileIds()` is the *JavaScript*
     Picker API and does **not** exist in the `trigger_onepick` desktop flow,
     which uses the `file_ids=` URL parameter. We use the URL parameter, which
     is correct. Google's wording for it is "pre-**navigated**", not
     pre-selected, and **that wording is exact**: the researcher still clicks
     each file. _(An earlier version of this entry claimed QA had measured
     pre-selection, from a screenshot reading "2 selected" with both files
     highlighted. That screenshot was taken **after** the clicks. The
     double-selection therefore costs one click per file, as originally
     counted — `file_ids` narrows what you are choosing among, it does not
     choose for you.)_
     - **Which makes the listing-wide grant a trade, not a pure win — open.**
       If every seeded file must be clicked, then asking over the whole listing
       front-loads *all* the clicking: a researcher importing 3 of 20 today
       faces 20 thumbnails instead of 3, in exchange for later batches asking
       nothing. Shipped that way in `dca4c1be` on the assumption that seeding
       was free. It isn't. Unmeasured and decisive: whether the Picker offers
       any multi-select affordance (shift-click, select-all) over a
       pre-navigated set — if it does, the trade is clearly worth it; if it
       does not, seeding the listing may be worse than a round trip per batch
       for anyone who imports selectively. **Measure before defending it.**
  3. **The client-only CASA exemption is NOT supported.** Three separate
     attempts to state the trigger as settled — in either direction — were
     voted down; only the claim that it is *genuinely ambiguous* survived
     unanimously. The page carries two inconsistent formulations, both
     **capability** tests ("has the ability to access", "or has the capability
     to access"), one of which drops "third-party" and says merely "a server";
     and the dedicated CASA support page states the requirement with **no
     server qualifier at all**. No page carves out native, desktop or
     backend-less apps. So the "we have no server, therefore we are exempt"
     reading is a hope, not a finding — still worth asking Google, but do not
     plan on the answer. Immaterial to us while we stay on `drive.file`, which
     is why we do.
  4. **A route to transcripts with no Drive scope at all, and it is shipped
     somewhere.** Meet REST API *enumeration* scopes — `meetings.space.created`
     / `meetings.space.readonly` — are only **Sensitive**, and
     `conferenceRecords.list`, `.recordings.list` and `.transcripts.list` all
     run on them. Mattermost's Google Meet plugin (read at source, the one
     genuinely *measured* finding in the report) pulls **full transcript text**
     via `conferenceRecords.transcripts/*/entries`, renders WebVTT locally, and
     holds **zero** Drive scopes anywhere in the repo — while deliberately
     *linking* recording media via `exportUri` rather than downloading it, so
     Drive's own ACLs gate the bytes. Bears directly on §8's open transcript
     question, since we already hold the Meet scope. **Two hard limits before
     anyone gets excited:** transcript entries are deleted **30 days** after
     the conference, so this cannot be the durable source for older studies;
     and a fileId obtained from the Meet API is **not** readable under
     `drive.file`, so this shortens nothing on the recording download.
  Flagged for honesty: the **$500–$4,500** assessment figure came in with the
  research brief and **no Google page read carries pricing** — it is unverified
  here, though one first-hand account of shelving an app over ~$540/year did
  surface. Do not let the well-verified "annual recurring obligation" launder
  the number. And the report's own biggest gap: the search budget ran out
  before first-hand indie-developer accounts could be swept, so what came back
  is a strong documentary map plus one code precedent, not a survey of practice.
- _2026-08-17 (first live QA of the whole loop, Meet)_ — the walk that found
  the two defects above, plus a queue of its own. **What worked end to end:**
  files present → rows held → delete them → rows fetchable again → tick →
  Picker → Queued → Imported; and switching the destination to another project
  re-offers every row, because "already imported" is a fact about *a folder*,
  not about the recording. Owed, in the order it hurts:
  1. **A batch can maroon in "Queued" forever.** `prepareBatch` awaits the
     media-grant session; if that session is dismissed oddly it never returns,
     `isFetching` stays true, and every row sits on "Queued" with no timeout
     and no way back except **Stop**. "Queued" is also a lie there — nothing is
     queued, we are waiting on a person. Wants its own state, *Waiting for
     permission*, and a deadline.
  2. **Stop → Import does not cleanly re-open the Picker** — observed
     re-opening the browser but not at the grant page, which suggests the
     consumed Picker session (`fid=`) is being reused rather than minted.
  3. **The media grant is re-asked far more often than Google requires.**
     Three causes, all ours: `pickMedia` hardcodes `prompt=consent`, which
     *forces* the consent screen even for files already granted;
     `requestMediaGrant` never consults `grantedFileIDs`, so it re-picks files
     it already holds; and `openLive` builds a fresh source per window open,
     discarding `grantedFileIDs` and `mediaToken` with it.
  4. **It cannot simply be folded into the first sign-in**, and that is not a
     bug: Google refuses a picker authorization carrying any other scope (the
     comment at `GoogleOAuth.pickMedia` records this), and the grant is bound
     to *specific file IDs*, which do not exist until the researcher has a
     list to pick from. Mocked up in
     `docs/mockups/cloud-import-scope-choice.html`, which counts the journey
     and settles the scope question. Three things came out of it:
     - **The ceremony is not the consent, it is the double selection.** The
       researcher picks the recordings in our list and then picks *the same
       set again* in Google's Picker. Twelve interviews is 29 clicks end to
       end, against 24–30 to download them by hand — so on this measure import
       is not yet easier than the thing it replaces, which was its whole
       premise.
     - **`drive.readonly` is off the table permanently.** Checked against
       Google's scope table 17 Aug 2026: `drive.meet.readonly` ("View Drive
       files created or edited by Google Meet") is **restricted**, the same
       tier as `drive.readonly` — so whatever verification and assessment
       burden one carries, the other carries identically, and one of them says
       "all your Drive". If we ever go restricted we go Meet-only; there is no
       argument for the broader one, and this holds whichever way the next
       bullet lands.
     - **Whether a CASA assessment applies to us at all is unresolved, and
       must be asked rather than inferred.** Google's condition is "requests
       access to restricted data *and has the ability to access data from or
       through a third-party server*". Bristlenose downloads Drive → the
       researcher's own Mac with no server of ours in the path, which reads
       like exemption; what muddies it is the pipeline's LLM call, since
       whether transcript text *derived from* a restricted-scope file counts
       as that data transiting a third-party server is an assessor's judgement.
       If it does apply, the developer engages a Google-empanelled assessor and
       pays directly (Google is not party to the fee) — commonly $500–$4,500
       for an app of this complexity, **repeated every 12 months**. Restricted-
       scope *verification* is required either way. _Recorded 17 Aug 2026 after
       an initial claim that the audit simply applied — it is conditional, and
       the condition is one this app might genuinely fall outside._
     - **Do the free fixes first and the scope question loses its urgency.**
       Seeding the Picker with the whole listing, honouring `grantedFileIDs`,
       and persisting the grant take the journey from 29 to 17 with no scope
       change and no audit — after which the restricted scope buys exactly one
       further click. Then the choice can be made on its merits.
     - **There IS a gate, and it is the free one — corrected.** An earlier
       version of this entry said that on `drive.file` there was no Google gate
       at all, having read only the Drive half. Import does not use
       `drive.file` alone: the listing needs `calendar.events.readonly` and the
       Meet conference-records scope, and **both are sensitive**
       (`GoogleScopes` says so in its own doc comments). Google requires
       verification for *sensitive **or** restricted* scopes, so verification
       applies to Bristlenose today regardless of what we do about Drive.
       What it costs is the point: sensitive-tier verification is review,
       written justification, a demo video and weeks of latency — **no security
       assessment, no assessor, no fee**. Time, not money. Accurately, then:
       `drive.file` is non-sensitive and **adds nothing** to the burden the
       calendar and Meet scopes already carry, while a restricted Drive scope
       would add the paid assessment on top. That delta is what the decision
       below turns on, and it survives the correction intact.
       **Google's one real lever is the OAuth client itself**, which it can
       restrict for policy violation; that is independent of Apple, who review
       the app but audit nobody's Google-API compliance. Small surface on a
       non-sensitive scope, and not nil, but not a process we have to pass.
       Note also that `GoogleOAuthConfig.resolve` reads the client ID from
       **UserDefaults before the Info.plist**, so a customer whose admin
       objects to our client can point the app at one they registered
       themselves — and an internal-only app is exempt from everything. Not
       exposed in the UI; worth remembering it exists.
     - **DECIDED: we stay on `drive.file`.** Bristlenose will not carry a
       recurring security assessment to save a click. That price is a footnote
       on an enterprise line item and a material share of an indie
       developer's income — the same number is not the same decision at the
       two scales. So the restricted scopes are **out, not deferred**, unless
       the exemption question above comes back "no assessment required", which
       costs nothing to ask and is the only thing that could revive them.
     Which makes the free fixes the whole answer rather than a first step. The
     steady state they reach: first import of a study asks once, covering every
     recording in the listing; later imports of those recordings ask **nothing**;
     recordings appearing afterwards ask once, for the new ones only. That is a
     good product on a non-sensitive scope with no verification and no annual
     anything. **It rests on one unmeasured fact — whether a `drive.file` grant
     persists server-side so a stored refresh token keeps reading a
     previously-picked file.** Measure that first; it decides whether the
     sentence above is a promise or a hope. Second unmeasured item, equally
     cheap: whether `prompt=consent` is genuinely required by the one-pick flow
     (the code comment lumps it in with `trigger_onepick`) — if not, deleting
     it is free. The two-way Settings radio stays drawn in the mockup as parked
     work, not next work.
  5. **Cancel is batch-only.** Wants a per-row cancel beside each progress bar,
     and the whole-batch cancel to be reachable from the sidebar ring once
     that exists (item 2 of the previous entry).
  6. **Zoom's tolerance is unmeasured** and parked — Meet and Teams ship first.
- _2026-08-17_ — **item 1 of the design session is built: already-in-this-project,
  by duration.** `ImportRowState.imported` has a producer for the first time —
  it was written, localised into 21 languages ("Already in this project."), and
  reachable from no code path since the day it was added. The cheap half only,
  as scoped: a pure matcher (`CloudImportLocalMatch.alreadyPresent`) plus one
  folder scan when the destination popup changes. No schema, no persistence, no
  privacy question.
  - **One file may satisfy at most one row**, and that rule is the design, not
    an optimisation. The two failure directions are not symmetric: missing a
    match costs a duplicate the researcher can delete, while inventing one
    marks a recording `.imported` — which offers no tick and no override, so it
    silently withholds a file they do not have. Ties go to the closest pair and
    every row that loses stays fetchable.
  - **Tolerance is per platform**, because the two quantities being compared
    are different measurements: a container's duration is media length, the
    API's is wall-clock between recording events. Teams ±2s (Graph serves the
    container's own duration in ms), Meet ±15s (`endTime − startTime`), Zoom
    ±90s — Zoom reports **whole minutes**, so nothing under 60s could ever
    match. Stated rather than papered over; sharpening it means reading
    `recording_end − recording_start` off the recordings endpoint, which waits
    until Zoom is unparked and can be measured rather than reasoned about.
  - **The split that was there.** `fetchOrder` read `listing.rows` while the
    outline drew a marked copy — harmless until the two disagree, at which
    point the window says "already in this project" and the batch fetches it
    anyway, producing exactly the duplicate the mark exists to prevent. Both
    now read one stored `rows`. Pinned by two tests that were each confirmed to
    **fail** with the split reintroduced.
  - Measured, not assumed: the scan was run against the ten real FOSSDA
    interview recordings held locally, measuring all ten — and excluding the
    manifest and the three output directories beside them — to within 0.5s of
    `mdls`'s `kMDItemDurationSeconds`.
  - Durations come from **AVFoundation**, not a shelled-out ffprobe — native,
    sandbox-clean, no subprocess. A dataless placeholder is never opened:
    reading a container header faults the file in, which is the case where the
    `FileManager` equivalent blocks indefinitely with no error and no
    cancellation. Two signals guard it (`ubiquitousItemDownloadingStatus`, and
    allocated-size-zero over a non-zero logical size, for providers that
    publish no status).
  - Not done, and deliberately: no rescan after a batch finishes (the outcome
    already reports the row), and no pruning of a tick that a scan later
    invalidates — `isSelectable` drops it from `fetchOrder`, so the Import
    button's count simply falls, which is the honest reading of "you already
    have two of these".
- _2026-08-17 (design session — **items 1 and 2 have since shipped**; see the 18 Aug entry)_ — a long design pass over what
  happens **after** the researcher presses Import. Two mockups carry it:
  `docs/mockups/cloud-import-sidebar-progress.html` (the closed-window case) and
  `docs/mockups/cloud-import-failure-states.html` (a pre-mortem over every
  state, enumerated from the shipped types). What shipped in code is the
  **destination popup**: preselects the frontmost window's project, offers
  *New Project…* first behind an `NSSavePanel`, renders folders as unselectable
  section headers, and preserves the researcher's own sidebar order. What is
  settled and unbuilt, in the order it should be done:
  1. **Already-in-this-project, by duration.** The 99.9% route is a *manual*
     download, renamed, dropped in the folder — so no record we mint can cover
     it and a folder scan is the whole answer, not a fallback. Feeds
     `ImportRowState.imported`, which is written, localised into 21 languages
     and **has never had a producer** (all three adapters hardcode
     `.notImported`; six of the fourteen row states are unreachable). The harm
     is not a wasted download: two copies of one interview become two
     participants whose identical quotes then *cluster together*, which reads as
     corroboration. A duplicate does not look like a mistake, it looks like a
     stronger result.
  2. **The sidebar ring**, reusing `Kind.copying(fraction:)` — which already
     means "a determinate, cancellable transfer into this project" — plus
     `beginAddingInterviews` and `RunProgressMath.clampedFraction`. Nothing new
     is drawn and no verb is invented; the subtitle is "3 of 4" because that is
     the question a closed window leaves. Sizes become measurable in the gap
     after `prepareBatch` returns and before the task group starts, which also
     un-blinds the free-space precheck.
  3. **Monitor mode.** Reopening stays in File ▸ Import with the other platforms
     dimmed and the verb swapped to *Show …*; four controls that are live-but-
     inert during a fetch become honestly disabled. Closes a reachable defect —
     `openLive` replaces `store` unconditionally, so starting a batch, closing
     the window and picking another platform leaves the first batch downloading
     invisibly with no way to see or stop it.
  4. **A per-project record** of what landed and what was asked for and never
     arrived — the only thing that can outlive the window. Largest item here:
     schema, migration, project-private.
  Measured rather than assumed: **Google writes no `creation_time` into its
  MP4s** (`encoder=Google` and nothing else); Teams does. Decided out of scope:
  trimmed files, and with them audio fingerprinting. Deferred: Zoom.
- _2026-08-17_ — **Meet's listing is inverted: conference records lead, the
  calendar joins onto them.** The adapter used to walk the calendar and ask
  Meet, per event, for records on that event's meeting code inside a ±15-hour
  window. Two costs came out of that shape. The visible one: a call started from
  the Meet home screen has no event to walk from, so it produced no row, no
  dimmed row and no footer count — on the live tenant, **two of five real
  recordings were invisible**. The subtle one: the window was doing work the key
  should have done. `spaces.get` returns each record's real `meetingCode`, which
  is the same string `conferenceData.conferenceId` carries, so the join is now an
  equality on a key both sides genuinely share (`ConferenceRecordJoin`). Time is
  used only to pick which instance of a recurring series a record belongs to —
  inside one room, where bookings cannot overlap — so the case that made a
  time-overlap join unsafe (accepting two clashing invitations, or hopping
  between calls) cannot arise. Three consequences worth stating: an unmatched
  record now becomes **its own row**, titled with the meeting code and marked
  *Instant meeting* (Meet's word), which is what makes the tighter one-hour
  early-join tolerance safe — the failure it produces is a recording filed under
  a code instead of a title, not one filed under the **wrong** title; a refused
  `conferenceRecords.list` is recorded as `ListOutcome.failed` and forces every
  unmatched row to *Unavailable*, because "we could not look" must never render
  as "nobody recorded"; and §4's organiser rule is now a **fallback explanation
  rather than a gate** on Meet — see the amendment there.
- _2026-08-16 (branding pass)_ — new **§9a Vendor branding**, read out of the
  three vendors' current guidelines. The reframe: brand here is **three**
  surfaces under three instruments, and the one the design was drifting toward —
  a Teams/Meet/Zoom product icon in the `File ▸ Import` submenu — is the one all
  three vendors forbid without an express licence. So `symbolName`'s "placeholder
  in every case" comment is inverted into a decision. Also corrected: this
  codebase's claim that **Zoom publishes a sign-in spec** (it does not, and its
  Marks licence reaches SDK Apps only, which we are not), and Google's ban on
  **monochrome** marks — which `provider-google.imageset` breaks today, one
  surface over. §9's Microsoft paragraph is verified and stands.
- _2026-08-16_ — **the first live Google tenant**, and the same shape of lesson
  one platform over. A Business Standard Workspace was bought and a Meet
  recorded, which settled the folder and naming grammar by measurement, and
  **repriced the transcript badly enough to change v1's scope: Google's
  transcript is now out of scope.** §3's Meet row gains the tier gate it lacked
  while Zoom's had one, plus a Google-mechanics block; §3's and §5's "strongest
  artifact position" claims are corrected in place; §6 carries the observed
  specimens. Two findings outrank the rest: the transcript is **not a file** —
  it is a tab inside a Gemini notes Doc, and every export flattens the two
  together — and a live defect in `s04_parse_docx.py` ingests that flattened
  export as speech, reachable today from drag-drop and owned by no adapter
  (recorded in `bristlenose/stages/CLAUDE.md`).
- _2026-08-15 (evening)_ — trued against the **first live tenant** (`8b8eafc9`).
  §0: Teams is registered and signs in; `CFBundleURLTypes` was never required
  and this doc claimed it was; the probe list re-cut (one answered, one now
  known unanswerable by us, two new one-listing probes). §3: **Q7 answered NO**
  — transcript is not a sibling file — with the original inference preserved
  under a superseded banner, plus the manual-`.vtt` fallback and the Stream-web
  "Speaker 1" trap. §6: the "timestamp is UTC" instruction superseded in place —
  business tenants omit the marker and write a server-side zone (measured UTC+2
  against the mp4's own `creation_time`), so the moment must come from
  `driveItem.createdDateTime`; both real specimens recorded; two invariants
  promoted out of the commit body (a parse refusal must produce a stated row;
  a filename grammar must be pinned by an observed specimen).
- _2026-08-15_ — trued up after three adapters shipped: corrected the status
  block (four open probes, not three; added the registration/persistence
  reality that makes every sign-in inert today); rewrote §7's "No `CallSource`
  protocol yet" — the rule was followed and the conclusion inverted; rewrote
  §6's Teams-only staircase for the three-platform spine; resolved four
  self-contradictions (§3 Zoom roster cell vs prose, §5 vs §6 on Google's
  conditionality, §6 vs §9 on the free-space precheck, "six states" over a
  seven-row table); replaced §9's testing paragraph, which named the wrong
  language stack. Anchors: `CloudImportSource.swift`, `CloudPlatform.swift`,
  `CloudDownloader.swift`, commit subjects "extract the spine before Zoom",
  "one download path, and it proves the bytes arrived", "Teams goes live".
- _2026-08-15_ — revised as Google, Zoom and Teams were researched and built.
- _2026-08-14_ — revised after a permissions/benchmark pass and a six-agent review.
- _2026-07-28_ — initial design.

# Cloud import — capturing originals from Teams, Zoom and Meet

**Status: designed 28 Jul 2026. Revised 14 Aug 2026 after a permissions/benchmark pass and a six-agent review. Revised again 15 Aug 2026, when Google, Zoom and Teams were researched and all three adapters were built. Status block corrected 18 Aug 2026 against measurement — it had drifted a full phase behind the code. Post-TF, not cohort-blocking.**

> **Zoom — built, flagged off, untested (4 Sep 2026).** The adapter exists behind `zoomEnabled`, off. It has not run against a real account because cloud recording needs Zoom Pro or higher and there is no Pro account to test on; the maintainer's estimate is October. "Deferred: Zoom" below means *sequenced after Teams*, not unbuilt — don't propose building it, and don't flip the flag without a real-world pass.

**What exists as of 15 Aug 2026.** All three platforms are live behind `File ▸ Import`, on one shared spine: `CloudImportSource` (the protocol), `CloudImportStore` (the state machine), `CloudImportWindow` (the surface), `CloudPlatform` (everything vendor-shaped the UI says), `CloudImportCoordinator` (which source the window holds), and `CloudDownloader` + `CloudDownloadVerification` (§6's "prove the bytes arrived", once, for all three). Per-platform adapters carry only what genuinely differs: the endpoints, the scope vocabulary, the error dialects, the OAuth ceremony, and each vendor's own way of failing quietly. A `FixtureCloudSource` drives every state from the Diagnostics menu without an account.

**What is not built.** _Rewritten 18 Aug 2026 from measurement. This block
previously opened "and the first item means nothing works yet" and then listed
four things that had shipped — see the changelog. The heading is kept short
deliberately: a status block that editorialises about its own worst item is how
this one stayed wrong through four passes._

- **Teams and Google are registered and both sign in. Zoom is not, and is parked.** A Microsoft 365 Business Basic tenant (`bristlenose.onmicrosoft.com`, £6.48/mo, **monthly**) and an Entra app registration were created 15 Aug 2026 — multitenant + personal accounts, redirect `msauth.app.bristlenose://auth` as a public client, public client flows on, delegated `Files.Read` / `Calendars.Read` / `offline_access` / `User.Read`. The client ID lives in the app's sandboxed `UserDefaults`, **not in this repo**. Zoom's config still reads a client ID and returns `nil`, so it cannot sign in — which costs nothing today, because Zoom is parked behind `BristlenoseFlags.cloudImportZoom` (default off, `c837f8b5`).
  - **A Google tenant now exists, and it is not the same thing as a Google registration.** _16 Aug 2026._ A Workspace **Business Standard** tenant was bought on a throwaway domain (Flexible/monthly, ~£11.80/user; the domain was taken at signup rather than pointed at `bristlenose.app`, whose MX carries live mail). It has recorded a real Meet, which is what §3's and §6's Google findings are measured against. ~~**No OAuth client is registered in any Google Cloud project**, so `GoogleMeetConfig` still returns `nil` and nothing can sign in.~~ **Superseded 18 Aug 2026 — a client exists and has completed a live sign-in** (`2cb58cf6`; the measurement is recorded in this doc's changelog). As with Microsoft, the client ID lives only in the app's sandboxed `UserDefaults` on the dev Mac and is **in no file in this repo** (`GoogleOAuth.swift:166-180` reads `UserDefaults` before `Info.plist`), so a clean checkout still reveals nothing and the claim above stayed plausible for two days. The placement rule below survives the correction and is the part that matters: it belongs in a Cloud project owned by an account that outlives the tenant — the throwaway domain is a *data source*, not the app's identity, and an OAuth client registered inside it dies with it.
  - **`CFBundleURLTypes` turned out not to be required, and this doc said it was.** Teams signed in with no URL type registered in the target: `ASWebAuthenticationSession(url:callbackURLScheme:)` has the OS route the callback to the initiating session directly, never through LaunchServices — which is the security property §2 chose it for in the first place. **Zoom's `associated-domains` entitlement and a deployed `apple-app-site-association` file are still genuinely required**, because Zoom refuses custom schemes and its callback is HTTPS.
- ~~**No token is persisted, and no refresh is wired.**~~ **Shipped — see §7.** One Keychain item per `(platform, account)` (`8901845f`), written through a single owner (`357818b5`), renewed before both the listing and the fetch (`342cb5c5`, `a10b45c8`), and exercised through the adapter's real entry point over a stubbed transport (`af9b38b4`). The hour-long access token this bullet warned about is the thing the renewal exists for. What is still true and worth keeping: a grant is only as durable as the refresh token behind it, and Google's expires weekly while the app sits in Testing status.
- **No *adapter* derives local row state — and none needs to.** The claim was literally true of the adapters and misleading as written: the derivation moved up into the store, where it belongs, because it is a fact about the *destination folder* rather than about any vendor. `CloudImportStore.rebuild()` marks rows already held by scanning the destination and matching on duration (`CloudImportStore.swift:165-171`, `CloudImportLocalMatch.swift:80`), so `.imported` has a live producer for every platform at once. **Unverified for Teams**: the 2s duration tolerance has never been checked against a real Graph pair, and the Google equivalent was wrong on first contact — it withheld a recording the researcher did not have, which is the failure direction with no override.
- **The batch now hands its files to the pipeline.** _18 Aug 2026._ Until this
  landed, a batch ended at the bytes: the recordings arrived in the destination
  folder, the sidebar ring cleared, and nothing started — one step short of this
  document's own one-sentence spec, *"download and ingest"*, and the half a
  researcher notices, because a folder of MP4s is the drudgery they were
  delegating. A settled batch now announces what it landed
  (`CloudImportStore.onBatchSettled`), a pure decision picks the action
  (`CloudImportHandoff.decide`), and the coordinator performs it. A folder-shaped
  project runs — fresh if new, incremental if already analysed, which is the
  pipeline's call and not ours; a file-subset project has the paths registered
  but starts nothing, because the CLI has no `--files` to scope a run with. Four
  states decline: nothing landed, a run already going, a previous run failed
  (re-running unbidden burns spend repeating a known failure), and the project
  unreachable. **Declines do not seed the folder watcher**, so the project row's
  existing new-files count pill is what says "these arrived and nothing read
  them" — which is why this path needed no new message anywhere. The fixture
  source is deliberately not wired: it simulates transfers and writes no bytes,
  so a Diagnostics scenario must never start a real, billable run.
- **Where the full list lives.** Done/undone in dependency order is kept in the `cloud-import-state-of-play` handoff, with the maintainer's private planning notes outside the public tree — so it is gitignored and a grep of a clean checkout will not find it. This status block is the public summary; that handoff is the working document.
- **Live acceptance — the whole loop has now run, on both live platforms.** On 15 Aug 2026 the shipped code signed in to a live Microsoft tenant, listed `/Recordings` over Graph and rendered the window; two parsers broke on first contact and are fixed (`8b8eafc9`) — see §6. On 17 Aug the Meet loop completed end to end — tick → Picker → download → **Imported** — and on 18 Aug the stored Picker grant was measured surviving a relaunch (`2cb58cf6`). ~~It has still never completed a download, on any platform.~~ **That sentence was false for a day before this pass caught it**, and it is the one most worth flagging: it sat in the summary while the changelog above it described the completed download, so the two halves of this file disagreed about whether the feature worked.
  Of the four open probes, one is answered and one is now known to be unanswerable by us:
  - ✅ **Is the transcript a sibling file in OneDrive?** **No** — see §3. §1, §3 and §5 stand unrevised.
  - 🔒 **Can a researcher self-consent in a real client tenant?** Still open, and **our own tenant can never answer it**: the owner is Global Administrator, so consent always succeeds and the org-wide consent checkbox only renders for admins. This needs a cohort member in a tenant we do not administer — see §5.
  - ✅ **Does the Google Picker surface a Meet recording?** **Yes — answered 17 Aug 2026**, by a completed round trip rather than by inspection.
  - ⬜ *The sub-risk survives the answer, and needs a second body.* The 16 Aug call was solo, so nothing has yet been observed about what an **attendee** sees in their own Drive after the July shortcut change. Invite a free `@gmail.com` to a recorded call. Split out because folding it into the row above is what let an answered probe keep reading as open.
  - ⬜ Does Graph serve `expirationDateTime` per driveItem? Untouched — but now cheaply answerable, and a captured response from the app's own listing may already contain it, since that listing sets no `$select`.
  - ⬜ *New, same cost:* does business OneDrive return `sha256Hash`, or only `quickXorHash`? One listing settles it, and §6's verification ladder degrades differently depending on the answer.

Downloading recordings by hand, per file, is drudgery — and it is the thing Dovetail and Marvin remove by default. Bristlenose can too, and unlike them it needs no server.

**The feature in one sentence, in the researcher's words:** *look at a list of last week's meetings, filter on "Interview", tick the obvious research calls, and click get-them-all — download and ingest.*

**Two decisions taken 14 Aug 2026, both narrowing scope deliberately:**

- **v1 is macOS-only** (§7). Not a compromise — it deletes the hardest problem in the design rather than solving it.
- **v1 fetches only meetings the researcher organised** (§4). A statable precondition, not a silent limitation — §6 requires the list to show what it *couldn't* offer.

**Scope note.** This doc is about *getting the bytes down*. What happens to media once Bristlenose has it — reading it when it's cloud-evicted, archiving, retention, why BN manages none of it — is **`docs/design-project-storage.md`**. The two meet at one point: import produces *captured originals*, and that is what the retention clock runs against.

---

## 1. Why, in priority order

1. **The video file.** The irreplaceable asset and the annoying thing to obtain.
2. **Beat the expiry.** Teams recordings expire (120 days documented, commonly configured to 60); Zoom is org-set. A link can vanish at any moment, so BN must hold bytes, not pointers.
3. **The attendee roster.** Real names, spelled the way the organisation spells them. **Promoted from #4 on 14 Aug 2026** — it is cheaper to obtain than the video (§3), reachable in cases where the video is not (§4), and removes a live manual step: the researcher currently copies names out of the Teams/Outlook UI into a spreadsheet by hand.
4. **Provenance.** Source, capture date, meeting. You cannot expire on a schedule without a start date.
5. **The transcript text.** Genuinely optional, and the quality question is **open, not settled** — see §8. On Teams it is also the single hardest thing to obtain (§3), which settles it there by other means.

**What the roster does *not* do.** An earlier draft claimed it retires the pipeline's pre-redaction speaker-ID LLM call. It does not, on three counts: there are **two** such calls in s05b (`identify_speaker_roles_llm` and `split_single_speaker_llm` — a roster does nothing for the latter); the roster supplies the candidate *set* while the call's job is the *mapping* `speaker_label → person AND role`; and it also extracts `job_title`, which is not in a calendar event. Add §9's *invited ≠ attended* and the roster is not ground truth for who spoke. It **constrains** the guess from open-ended to a short list — real and valuable — but the `SECURITY.md` disclosure stays. Retiring the call while the assignment is still a guess would trade a *disclosed* guess for an *undisclosed* one.

---

## 2. The mechanism

A *user-initiated* fetch is an OAuth **public client with PKCE**: `ASWebAuthenticationSession` opens a sign-in sheet, the redirect returns on a custom scheme, no client secret, refresh token into the Keychain.

**Zoom cannot use the custom scheme this section prefers, and that is a real architectural fork.** _Added 15 Aug 2026._ Zoom shipped a genuine public-client PKCE mode on 17 Apr 2026 — public client ID, no secret, no `Authorization` header, "mobile, native, and SPA applications without a backend" in their own words — so the *token dance* is the same as Google's. The **redirect** is not. Zoom's build flow accepts custom URL schemes only for Meeting SDK apps ("Wrong URL format" in the field, `errorCode 4700` at the server), and loopback is unsupported and was *further* broken in Jul 2026. Both escape hatches cost something: declaring Meeting SDK capability we do not use, purely to unlock a redirect format a reviewer will ask about; or an **HTTPS redirect with Associated Domains** (`ASWebAuthenticationSession.Callback.https(host:path:)`, macOS 14.4+), which needs only a static `apple-app-site-association` file on a domain we already own — static hosting, not a server, so §2's "no server needed" survives intact. The second is the honest answer for an App Store app and is what this design takes. Note it adds an **entitlement** and a **deploy step** that neither other platform needs.

> **Correction, 23 Aug 2026 — the loopback half of that paragraph is now false, and the conclusion survives it on different grounds.** Zoom's OAuth documentation today explicitly supports a loopback redirect **for PKCE-enabled apps**: `http://127.0.0.1:{port}/{path}`, *"Do not use `localhost`"*, matched *"while ignoring only the port"* (RFC 8252 §7.3's rule), and simple non-PKCE apps *"must continue to use HTTPS redirect URIs."* Whether the sentence above was wrong when written or Zoom shipped this since, it is wrong now — and left standing it invites the next reader to conclude the entitlement, the AASA file and the Mac App Store profile trip were all unnecessary, and to tear them out.
>
> **Keep the architecture. The real reasons it wins are these, and none of them is loopback's availability.** `ASWebAuthenticationSession` accepts exactly two callback forms — a custom scheme, or `.https(host:path:)`. A loopback `http://` callback is neither, so taking that door means abandoning the ephemeral in-app session for an `NSWorkspace.open` handoff to the default browser plus a local HTTP listener, which under App Sandbox needs `com.apple.security.network.server` and hands a reviewer a much harder question than an entitlement does. It is also a genuinely weaker posture: a loopback port is reachable by any local process, which is the code-interception attack PKCE *mitigates* rather than eliminates, whereas the OS routes an HTTPS callback straight back to the session that started it and never through LaunchServices.
>
> And Associated Domains is doing security work here that is easy to mistake for ceremony: `ZoomOAuthClient.presentConsent` validates only that the redirect is `https://` with a non-empty host — the **entitlement's domain list is the only thing** that stops a tampered `ZoomOAuthRedirectURI` default from sending the callback somewhere else, because `ASWebAuthenticationSession` refuses to deliver to an unlisted domain. Treat the entitlement as a control, not as dead weight.

Two Zoom token properties that are not Google's and must not be inherited by assumption. **Refresh tokens are single-use and rotate on every refresh**, with *no* documented grace window — an interrupted refresh (timeout after Zoom rotated, before we persisted) strands the user permanently, and re-authorising always shows the consent screen because public clients may not skip it (RFC 6819 §5.2.3.2). So the Keychain write must commit before the old token is discarded, and "reconnect" must be a graceful path rather than an error. And **Zoom appears to allow one live token per user per client ID**: authorising on a second Mac silently kills the first. A researcher with a laptop and a desktop cannot have both connected. That is a product constraint to state, not a bug to fix.

**Prefer a custom scheme over a loopback listener.** Both work under the sandbox (`ENABLE_INCOMING_NETWORK_CONNECTIONS` is already set), but a loopback listener is reachable by any same-UID process during the auth window, whereas `ASWebAuthenticationSession(url:callbackURLScheme:)` routes the callback to the initiating session only. Needs a `CFBundleURLTypes` entry the target does not yet have. Leave `prefersEphemeralWebBrowserSession` at `false` so an already-signed-in researcher gets one-click consent instead of a full MFA round trip.

**What is and isn't a from-scratch build.** The Swift consent sheet is new — `ASWebAuthenticationSession` appears nowhere in the tree. The **PKCE machinery is not**: `bristlenose/miro_client.py` already has `generate_pkce`, `build_authorize_url`, `exchange_code_for_tokens` and `refresh_access_token`, with a live authorization-code + loopback flow wired in `routes/miro.py`. That is the reference implementation for the token dance even though this feature's ceremony is Swift-side. **The read-back rule survives; the "before copying" framing does not.** _Trued 15 Aug 2026._ Nothing copies `miro_client.py` — all three ceremonies are hand-rolled in Swift — so the three platforms did not inherit the bug. But the bug itself is **still live and still shipping**: `bristlenose/server/routes/miro.py` reports "Connected to Miro ✓" on the path where the credential-store write failed, and unlike the sibling paste route it has no in-session fallback, so the token is genuinely lost. It is now simply a defect we own, unrelated to this feature. The rule it teaches is the load-bearing part and applies to all three adapters the moment they gain Keychain persistence: **a connect flow verifies by read-back — store, read back, *then* report connected.**

A server is only needed for **always-on watching** (poll the tenant while the app is closed). That is not this feature and should not become it.

---

## 3. Gates, per platform

Three artifacts, not one — and **they do not share a gate**. The 28 Jul version conflated them, which made Teams look worse and Google look better than they are.

| | List / index | Video | Roster | Transcript |
|---|---|---|---|---|
| **Teams** | Free: the title is in the recording filename (§6). `Calendars.Read` — **admin consent required since Nov 2025** ⚠️see below | `Files.Read` — no admin consent ✓verified | `Calendars.Read` — **admin consent required since Nov 2025** ⚠️see below | `OnlineMeetingTranscript.Read.All` — **admin consent required, even delegated** ✓verified |
| **Zoom** | `cloud_recording:read:list_user_recordings` — user-managed, no admin ✓verified. **Pro plan or higher** | same call returns `download_url`; **no download scope exists** — the same bearer authorises it ✓verified | **none ✓verified** — the list call carries no attendees at all; a roster needs a report endpoint behind an admin scope | **same call returns the VTT** ✓verified — speaker names as a `Name:` cue prefix, **English only, every plan** |
| **Meet** | `calendar.events.readonly` — sensitive ✓verified. **Business Standard or higher** ✓verified | `drive.file` + Picker — **non-sensitive** ✓verified. (`drive.meet.readonly` — restricted → CASA ✓verified, and refused) | `calendar.events.readonly` `attendees[]`, or `meetings.space.readonly` — sensitive ✓verified | **descoped from v1** ✓verified — not a file; a tab inside a Gemini Doc (below) |

> **⚠️ Correction, 17 Aug 2026 — `Calendars.Read` is admin-gated, and the ✓verified above was a false positive from our own tenant.**
>
> Microsoft's message centre `MC1163922` added **twenty Exchange and Teams permissions** to the **Microsoft-managed default app consent policy**, rolling out late Oct → late Nov 2025. **`Calendars.Read` is on that list. So is `Calendars.ReadBasic`.** `Files.Read` is **not** — the change is scoped to Exchange and Teams, not files. Tenants on a *custom* consent policy are unaffected.
>
> Status: **documented, not measured.** The enumerated permission list comes from trade write-ups of the message centre post; Microsoft's own text says only "Mail, Teams Chat and Meetings functionality".
>
> **How the ✓verified went wrong is the transferable part.** It came from a live Graph session against *our own tenant*, whose owner is Global Administrator — an account that consents to everything, always. `cloud-import-graph-probe.md` already names that as the trap which cannot say no, and the mark was applied anyway. **Any ✓ in this table established by signing into an account we control is a claim about that account, not about the permission.**
>
> **What it costs, and what it doesn't — but read §5's 16 Aug correction before taking comfort here.** In terms of *permission classification* the video import is untouched: `Files.Read` still reaches the recordings, and duration/date/time all come off the `driveItem`. What a default-policy tenant loses is the **roster, the Scheduled column, the un-recorded rows and two of the three footer numbers** — everything sourced from `calendarView`.
>
> **That is not the same as saying the video import works today.** §5 records, from the Entra UI itself on 16 Aug, that *"End users cannot grant consent to newly registered multitenant apps without verified publishers"* — so until **Publisher Verification** is done, a cohort researcher cannot self-consent to `Files.Read` either. Two independent gates, and they fail at the same screen: this one is ours to clear (MPN account, DNS-verified domain), the `Calendars.Read` one is the tenant's and we can never clear it. Fixing publisher verification restores the reduced window, **not** the full one. That window was reviewed 17 Aug and judged **a good product rather than a degraded one**: researchers recognise a session by person and day over a handful of sessions, and Teams bakes the meeting subject into the recording filename, so scheduling discipline pays off in the *filename* rather than in the calendar API.
>
> **Consequent decision: aim for the full window, fall back to the reduced one, and let the columns follow the data** — a column with no data anywhere is dropped, not ruled with em-dashes; the em-dash is for the row-level miss. Modelled in `docs/mockups/cloud-import-consent-reality.html`.
>
> **Shipped 18 Aug 2026** (`60321ec5`, `84d7c55e`): `CloudImportOutline.showsScheduledColumn(for:)` decides it, `syncScheduledColumn` owns the column, pinned by `CloudImportScheduledColumnTests.swift`. Three things about the as-built are not obvious from the decision above.
>
> **The rule is about the data, never the platform.** This section reaches it as a `Calendars.Read` consequence, but Meet arrives at the identical state by a different road — a month of instant meetings — and the two are indistinguishable at the row. One data-driven rule serves both; a permission-driven one would need to tell apart cases that carry no distinguishing evidence.
>
> **It is asked of the whole listing, not the filtered outline** the grid is built from. Otherwise a filter keystroke that happens to leave only instant meetings takes the column away mid-type.
>
> **An empty listing keeps it, and the column is *removed* rather than hidden.** Knowing there is no scheduled data requires having listed something. And `NSTableColumn.isHidden` is persisted by `autosaveTableColumns`, which this outline sets — so hiding would strand the column hidden after a tenant later granted the calendar. Removing carries no such memory. (AppKit offers no animated column insert either: rows have `withAnimation:` variants, columns have none, and `NSTableColumn` is not an animatable property container. The transition is unobservable anyway — the grid only mounts once rows exist, and sign-in happens in the researcher's real browser, in front of the window.)
>
> **The measurement this now hangs on**, and it needs a tenant we do not control: does a single authorize request carrying one admin-gated scope **fail as a whole**, or degrade and grant the rest? If it fails whole, the consent must be split into two calls so a refused calendar costs only the calendar. If it degrades, today's single call already does the right thing.

Cells are marked ✓verified or ⚠️unverified deliberately. **The two Google cells were resolved 15 Aug 2026, and the answer reprices §5's third slot rather than reordering it** — the sequence still runs Teams → Zoom → Meet; see below. The Zoom roster cell was resolved the same day and is now marked ✓verified in the table: the list call carries no attendees at all. _Zoom was previously described here as "the platform that could settle §8"; Meet's per-utterance transcript now makes it the better candidate — see §8._

**"No admin consent" is a property of the permission, not a guarantee about the tenant.** Whether a user *may* self-consent is an Entra policy setting. The modern default is "allow user consent for apps from **verified publishers**, for **selected permissions**", where the documented low-impact starting set is the OIDC scopes plus `User.Read` — and neither `Files.Read` nor `Calendars.Read` is in it. Enterprises routinely narrow further to no user consent at all. Microsoft **Publisher Verification** (Partner Center account + verified domain) may therefore be a prerequisite rather than a nicety — *probe this against a real client-shaped tenant, don't infer it from the docs*. This is the single most load-bearing claim in the doc and it decides §5's sequencing.

**Two doors to the same artifact, priced differently.** `OnlineMeetingTranscript.Read.All` and `OnlineMeetingRecording.Read.All` are *both* admin-consent-required (verified in the permissions list, 15 Aug 2026) — but reading the same recording **as a file in OneDrive** via `Files.Read` is user-consentable. That asymmetry is the whole reason this design takes the file door: Microsoft prices "read the meeting's artifacts" above "read the user's own files, some of which happen to be recordings."

> **Answered NO, 15 Aug 2026 — the original position stands, and §1, §3 and §5 need no revision.** On a live business tenant, `/Recordings` contained the `.mp4` **alone**. The transcript exists and is downloadable as `.vtt` or `.docx`, but from the **meeting object** (Stream), behind its own Download control — not as a file in the folder, and not reachable by `Files.Read`. The paragraph below is preserved because it was a correctly-reasoned wrong guess, and the shape of the error is the useful part: Microsoft's phrasing generalises from *channel* meetings, where recordings and transcripts do share a folder, to meetings in general, where they do not.

**⚠️ Open question that could overturn §1's priority 5: is the transcript also a file in OneDrive?** Microsoft's block-download documentation repeatedly says *"recording **and transcript** files from SharePoint or OneDrive"*, and for channel meetings that *"recordings **and transcripts** are saved to a Recordings folder."* If Teams drops the transcript beside the `.mp4` as a sibling file, `Files.Read` reaches it and **the transcript is not admin-walled at all** — making it free alongside the video rather than "the single hardest thing to obtain", and giving Teams the three-artifact coverage §5 currently credits only to Zoom. This is inference from phrasing, not observation. Settle it the moment a work tenant exists: list `/Recordings` and look for a transcript file beside the recording. If it is there, §1, §3 and §5 all need revising.

**What the researcher can still do by hand, and what it costs us.** The transcript is two clicks away in the Teams UI, and the downloaded `.vtt` is *good*: it carries real `<v Martin Storey>` voice tags, and Bristlenose's stage-3 parser reads it correctly (19 cues → 2 segments with real `speaker_label`). So "import the video from Teams, drop the transcript in yourself" is a real fallback that sidesteps an admin-walled scope entirely — at the cost of the appliance not coping, which §1 holds out against for good reasons. **One trap if anyone evaluates this in a browser:** Stream's *web* player renders every speaker as "Speaker 1". The file and the Teams desktop app both carry the real name; only the web view degrades. Judging transcript quality by clicking Play reaches the wrong conclusion.

**Zoom's mechanics, added 15 Aug 2026 — four traps, all of which return a plausible wrong answer rather than an error.**

- **The default date window is one day.** Omit `from`/`to` and Zoom answers for today, so an unparameterised call against a busy account returns `total_records: 0` — the single most reported confusion in Zoom's developer forum, and it reads exactly like "you have no recordings". **And the maximum range is one month**, silently: a 90-day request does not error, it answers for less. A quarter's look-back is three sequential calls.
- **A permission denial can arrive as HTTP 200 with `"code": 200` in the body** ("You do not have the right permissions"), as can the admin download block ("Download has been disabled by the administrator"). Any client branching on `response.ok` treats both as success, finds no files, and reports the session was never recorded. This is the Teams 401-that-means-no-licence one platform over, and it is worse, because the status line says everything is fine.
- **`recording_files[].status` cannot indicate "not ready" — its entire enum is `["completed"]`.** Transcripts are generated *after* the video, so a single-pass import systematically misses the VTT on recent meetings. Readiness comes from `GET /meetings/{id}/transcript`, whose `download_restriction_reason` distinguishes `NOT_READY` (retry) from `NO_TRANSCRIPT_DATA` (transcribe locally) — the exact branch a per-row UI needs.
- **`download_url` redirects to a pre-signed CDN URL that carries its own credentials.** `URLSession` re-attaches headers across redirects by default, and the signed URL has been reported to reject requests arriving with both. Follow the redirect by hand and strip `Authorization`. Related: `?access_token=` in the query string was removed in Feb 2023 — every pre-2023 snippet on the internet is wrong.

**§6's "prove the bytes arrived" has independent field confirmation, and it is brutal.** A developer ran the leading open-source Zoom downloader over ~2,000 recordings and **880 of them wrote a 59-byte JSON error body to disk as a `.mp4`** — every one logged as a successful download, because the failure arrives as HTTP 200 with an HTML or JSON body. The maintainer's fix was to compare bytes received against the API's own `file_size` and to **delete the completed-downloads log entirely**, because it "often erroneously classif[ied] recordings as successfully downloaded". The two leading downloaders converged on size-verification independently. That is strangers arriving at §6's rule from the other direction, which is the strongest evidence available that it is right — and a reason to build the verification *with* the first adapter rather than after it.

**Transcripts arrive later than video, and on long sessions may never arrive at all.** `recording.completed` carries MP4/M4A/TIMELINE; the VTT rides a separate `recording.transcript_completed` that can fire hours later, or seven milliseconds *earlier* — ordering is not guaranteed either way. Worse for this product specifically: a reported 198-minute session produced no transcript and no webhook, with the pattern "the ones that received a transcript were all short and ended cleanly". A research interview is exactly the long-session case. So a single-pass import systematically misses transcripts, a fixed delay does not fix it (the file list was already compiled), and the only correct shape is a **re-fetch**, branching on `GET /meetings/{id}/transcript`'s `download_restriction_reason` — `NOT_READY` means wait, `NO_TRANSCRIPT_DATA` means transcribe locally and stop asking.

**"Sign-in started and never came back" is a first-class state, and §6's honest-batch list needs a fifth entry for it.** Zoom's Marketplace pre-approval is enabled **by default on every multi-seat account**, and the block is enforced on Zoom's own consent screen *before any redirect* — so no code, no error and no callback reaches Bristlenose. The researcher clicks Sign In, reads a page telling them to ask their admin, and returns to an app that is still spinning. Teams has the same shape through Entra's user-consent policy ("Need admin approval"), which is §3's load-bearing question wearing different clothes.

From inside the app, "you closed the window" and "your organisation has to approve this first" are **indistinguishable**. So the state cannot be called *cancelled*: that word sends someone to try again, forever, against a wall only somebody else can remove. It names both possibilities, the researcher's own action first — they know whether they closed it — and the invisible one second. Google is deliberately excluded: a Workspace admin can restrict apps, but there is no equivalent default-on gate, so offering that theory there would be a guess dressed as help.

**Mark the recording scopes required, not optional.** Zoom's optional-scopes feature lets a user decline a scope and still install successfully — leaving us holding a valid token that cannot list or download, discovered only at call time as a scope error. That is a self-inflicted version of the partial-consent problem Google forces on us anyway.

**Two Zoom facts that are better than the other platforms, not worse.** `auto_delete` and `auto_delete_date` ride the *list* response per meeting, so §9's "expires in N days" countdown and the soonest-expiring-first fetch order are buildable exactly as designed — the thing Google could not give us. And organiser-only is **forced rather than chosen**: cloud recordings belong to the host, there is no API surface for recordings you merely attended, and sharing grants playback but never API access. §4's constraint is the platform's own shape here, which makes it easier to state honestly.

**Never reach for `Files.Read.All` or `Sites.Read.All`** — admin-consent-only since Aug 2025. That is the procurement gate the customer profile is defined by avoiding. It is the only thing standing between this feature and the team's SharePoint site, and the answer is to not want the SharePoint site.

**Take `Calendars.Read`, not `Calendars.ReadBasic` — the intuitive choice is the wrong one.** A 14 Aug draft of this doc specified `ReadBasic` on data-minimisation grounds: it returns `attendees[]`, the entire roster payload §1 promotes to priority 3, *without* `body`, `bodyPreview` or attachments, sparing Bristlenose every agenda, dial-in PIN and medical appointment in the researcher's diary. That reasoning is sound and the conclusion is still wrong, because **`Calendars.ReadBasic` requires admin consent and `Calendars.Read` does not** (verified 15 Aug 2026). "Less privileged" does not imply "easier to consent" — `ReadBasic` is a newer scope that simply isn't in the user-consentable set. Taking it would have moved Teams from *no gate at all* to admin-gated, destroying the single property §5's whole sequencing rests on.

So v1 takes `Calendars.Read` and **owes a compensating control instead**: request only the fields needed via `$select` (`subject,start,end,organizer,attendees`), never persist an event body, and let the in-memory index die with the window (§9). That is a weaker guarantee than not being granted the bodies at all — state it plainly rather than claim minimisation we don't have. Re-check `ReadBasic`'s consent status periodically; if Microsoft adds it to the user-consentable set, switching is a one-line change and a real improvement.

> **Superseded 17 Aug 2026 — the choice is now moot, and the compensating control is the only part still standing.** Both scopes went onto the Microsoft-managed default consent policy's blocked list in Nov 2025 (see the correction under §3's table), so "`ReadBasic` needs admin consent and `Read` does not" — the entire reason for the decision above — no longer distinguishes them. On current evidence **`ReadBasic` is now the better choice on the merits it was originally rejected for**: same gate, strictly less data. It has deliberately **not** been switched, because the scope set is about to be reopened anyway by the split-vs-single-call measurement, and changing it twice would churn the consent screen for no gain. The `$select` compensating control stays either way, now as defence in depth rather than as an apology.
>
> The paragraph above is preserved because its reasoning was sound on the evidence available and the delta is the lesson: **a scope's consent classification is a moving target set by the vendor's policy, not a property of the permission.** Re-check on a cadence, not once.

**Google was mispriced, and the error was mine — I costed one door and called it the platform.** The 14 Aug claim was that `drive.meet.readonly` is restricted, and that is **correct** (verified 15 Aug 2026 against Google's own scope table *and* the 11 Jul 2024 Drive release note announcing it as restricted on day one). What was wrong is the inference drawn from it. `drive.meet.readonly` is not the only door to a Meet recording, and it is not even the cheapest — it is the *most expensive* of three, and we should take neither of the other two by accident.

- **The Meet REST API is a separate, cheaper door.** `meetings.space.readonly` is **sensitive**, not restricted — no assessment, no fee, nothing admin-gated — and it serves `conferenceRecords.transcripts.entries`: per utterance, a `participant` reference, `startTime`, `endTime` and `text`, with `participants.get` resolving the reference to a display name. That is a **complete speaker-attributed, timecoded transcript on the cheap tier**, and it is the strongest artifact position of any of the three platforms (§8 revisits this). ⚠️ _Corrected 16 Aug 2026: this remains true of the **API** door and is why §8's experiment is still cheapest to run here — but it is no longer an argument for v1, which descoped Google's transcript entirely. It is also Workspace-only, so it is blind to the paying consumer accounts the file door reaches. See the Google-mechanics block below._
- **`drive.file` + Picker is non-sensitive and reaches the bytes.** The Meet API hands out a Drive `fileId` and an `exportUri` that is a *browser view link* (`drive.google.com/file/d/{id}/view`), never a byte stream — so downloading means the Drive API either way. `drive.file` covers "files the user shares with an app while using the Google Picker API", and Google actively recommends that pairing over broader scopes.
- **So Google can be built with zero restricted scopes.** The recurring cost that put it last does not have to be paid at all.

**Take `meetings.space.readonly`, never `meetings.space.created` — the same trap as `Calendars.ReadBasic`, one platform over.** `.created` reads like the modest, well-behaved choice and scopes to spaces *this app created*. An import tool wants meetings it did not create, so it gets an empty list and **no error**. Second time this doc has caught a "narrower-sounding scope is the wrong scope" — it is a pattern now, not a coincidence.

**The Picker objection was wrong, and it was wrong because we were looking at the wrong Picker.** This doc rejected `drive.file` on the grounds that it "means the user picks each file in Google's own Picker — not a filterable list, not one-click". That describes the **JavaScript** Picker, which is unusable here anyway: Google blocks OAuth in embedded webviews and names `WKWebView` explicitly (`disallowed_useragent`), so the token that library needs cannot be obtained inside our own web view at all.

The **desktop** Picker is a different mechanism and is not JavaScript. It is one OAuth request carrying `trigger_onepick=true`, which does authorisation *and* file selection in a single system-browser round trip and redirects back with `picked_file_ids` alongside the code. It takes parameters:

- **`file_ids`** — pre-scope the Picker to exactly the recordings the list already found. The researcher confirms a set; they do not go hunting in a folder tree.
- **`allow_multiple`** — one interaction for the whole batch, not one per file.
- **`mimetypes`** — filter to media.

So the list UX and the affordable scope are **not** mutually exclusive. Bristlenose builds the list from the sensitive grant, the researcher ticks rows, and the Picker is a **single consent step over the ticked set** — which is arguably better consent UX than a blanket "read every Meet file in your Drive", and costs nothing per year. The consequence for §6 is that the Google staircase gains one step the Teams one does not have, and it belongs in the design rather than being smuggled in as an implementation detail.

**What remains genuinely unverified, and it is narrower than it was:** nobody — not Google's docs, not any community report across two research passes — confirms that the Picker surfaces a **Meet recording** specifically. Mechanically it should; they are ordinary Drive MP4s. Two sub-risks are real: attendees now receive *shortcuts* rather than source files (see the folder change below), and there is an unread Google issue (365706547, Sep 2024) titled "new drive.meet.readonly scope seems unusable on the file picker" that hints at friction between Meet artifacts and the Picker. **One picked MP4 and one `files.get?alt=media` settles it in half an hour.** Until then, treat "Google needs no CASA" as well-evidenced but not proven — and note the fallback if it fails is `drive.meet.readonly` and the assessment, i.e. exactly the 14 Aug position, so the downside is bounded.

**A finding that outranks all of the above for this product specifically.** Google's current Drive and Gmail scope pages both state the assessment trigger as storing *or transmitting* restricted-scope data on servers. Bristlenose's analysis **is** an outbound cloud LLM call, so transcript text derived from a restricted scope would leave the device by design. The widely-repeated "local client application" exemption that would rescue this **could not be found on any live Google page** — it appears to be from a retired FAQ revision. So the restricted path is not merely expensive for us, it is expensive *and* on unsettled ground, while the non-restricted path avoids the question entirely. That asymmetry, not the fee, is the reason to take `drive.file`.

**Cost corrections, since the figure will be quoted.** "$500–4,500/year, re-verified annually" is substantially right, with three fixes: the tiers are now **AL1/AL2**, not Tier 2/3; **Google charges nothing** — one of nine App-Defense-Alliance-empanelled labs bills you directly, ~$540 (TAC Security AL1) to $4,500; and the **free self-scan everyone still cites was deprecated in Nov 2024** and now only checks readiness. Annual revalidation is real and confirmed.

**Microsoft's asymmetry is the mirror image, and that is the interesting part.** On Microsoft, reading a recording *as a meeting artifact* is admin-gated while the same bytes *as a file* are user-consentable — so we take the file door. On Google it inverts: the *artifact* door is the cheap one and nothing is admin-gated at all. Same feature, opposite doors, for opposite reasons. (Microsoft's nearest picker analogue, `Files.Read.Selected`, is *not* the counterpart it looks like — Preview, admin-consent, and its own docs say it "should not be used for directly calling Microsoft Graph APIs". Verified 15 Aug 2026.)

**Do not path-match `Meet Recordings` — that folder was renamed last month.** Google moved recordings into a **"Google Meet"** folder in the host's My Drive with a subfolder per meeting, rolling out 22–30 Jul 2026, renaming the old folder "Legacy Meet Recordings", and told admins to "audit any API scripts or automated workflows that rely on specific folder names or IDs". Resolve by file id from the API or by Picker selection, never by walking a named folder. The same change gives *attendees* shortcuts in their own Drive — which is a lead on §4's not-the-organiser case, and the reason the Picker sub-risk above matters.

**Google's mechanics, measured 16 Aug 2026 on a live Business Standard tenant — six findings, and one of them changed v1's scope.**

- **Recording is Business Standard or higher, and this table had no tier gate where Zoom's did.** Free personal accounts cannot record at all. Workspace **Business Starter cannot either, despite costing money** — so "the client is on Workspace" is not the question; the edition is. Transcripts sit behind the same gate. Getting this wrong does not produce an error, it produces an empty list, which is this feature's designed output *and* its failure output (§6, requirement 1).
- **Consumer accounts can record but cannot be listed, and the split runs straight through the two doors.** Google One Premium (2 TB) and AI Pro *do* grant Meet recording on an ordinary `@gmail.com`, saved to the same Drive folder — but the **Meet REST API serves only Workspace-hosted meetings**, so `conferenceRecords` is blind to them. A paying consumer researcher is reachable by `calendar.events.readonly` + `drive.file` + Picker and invisible to the artifact door. Freelancers are exactly this population, so the door choice is a coverage decision, not just a cost one.
- **Transcripts are on by default and have no admin toggle.** Google's own page says so for every Workspace edition, and the Meet page in Admin console carries no transcript switch at all — recording has one, transcription does not. The host starts it in-call (Activities → Transcripts). Anyone hunting Admin console for the setting will not find it; **its absence there is not evidence the edition lacks the feature**, and the in-call menu is where absence would actually mean something.
- **The transcript is not a file, and this is the finding that descoped it.** Google saves it as a **tab inside** a Doc named `<title> - <timestamp> - Notes by Gemini`, beside a Notes tab holding Gemini's summary. A Google Doc has no canonical byte form — `files.get?alt=media` fails on it outright, and every `files.export` rendering (`.docx`, `.txt`, `.md`) **flattens both tabs into one stream**. Measured on the specimen: 19 paragraphs, of which **one** is speech; the rest are Gemini's summary, Gemini's own UI chrome (*"Take a short survey to let us know your feedback"*), and — in paragraph 3 — **an attendee's email address**. On a real session, where Gemini has enough speech to summarise, those stub paragraphs are pages of confident AI prose about what participants said. The clean door does exist: `documents.get` with `includeTabsContent=true` returns tabs as addressable subtrees under `document.tabs[]`, so the transcript can be read without the Notes tab ever being touched. But that is a third API, possibly a fourth scope (unverified: whether `drive.file` alone authorises `documents.get`), and a document-tree walk. **Of the three platforms Google is the only one where "download the transcript" is not a well-defined operation** — Teams serves a `.vtt` from Stream, Zoom returns one on the same call as the video, Google returns whichever lossy projection you ask for.
- **Automatic Gemini note-taking is default-on for meetings with 3+ guests**, so a per-meeting folder can hold a third artifact nobody asked for. A two-person interview does not trigger it; a call with a client PM and a note-taker does — which is the common shape in agency work.
- **`capabilities.canDownload` is Google's answer to §4's block-download policy, and it is better than Teams'.** Drive surfaces "Security limitations" per item, and on Google download restriction is **owner-settable per recording**, not only an org-wide admin policy as on SharePoint. So §6's **view only** row state resolves directly from the listing rather than by inference — which is precisely what §6's requirement 1 demands and what Teams cannot supply. Note the consequence for copy: on Google that state can be the researcher's own past choice, so "your organisation blocks this" is the wrong sentence.

**The v1 decision that follows: Google's transcript is out of scope.** _Taken 16 Aug 2026._ Import the video; let Whisper do the words. This removes the Docs API, the tab walk, the `documents.readonly` question and the Gemini-contamination risk from the adapter in one move — and §8 has never established that a platform transcript beats our own transcription anyway, so nothing of proven value is being given up. **The consequence to take deliberately** is that dropping the transcript also removes the main argument for `meetings.space.readonly`, and v1 could then run on `calendar.events.readonly` + `drive.file` + Picker alone — which would additionally serve consumer accounts. What that costs is the pre-scoped Picker: without `conferenceRecords` there is no `driveDestination.file` id per meeting, so `file_ids` cannot be populated and the researcher browses the folder rather than confirming a ticked set. That is the §3 objection above, returning. Decide it on the list UX, not on the scope bill.

---

## 4. Organiser-only, and why that is fair for v1

> **Amended for Meet, 17 Aug 2026 — the organiser check is now a fallback
> explanation, not a gate.** This section is written from Teams, where listing
> the researcher's own `/Recordings` makes the constraint structural. Meet's
> adapter used to import that shape by *choice*: it looked up recordings only
> for events the researcher organised, so a colleague's meeting whose recording
> this account could plainly reach still read "Someone else" and drew no
> checkbox. With the listing inverted, the records are read first and the
> question is answered by data — a recording in hand outranks any reason we
> expected not to find one. `.notOrganiser` now fires only where we looked,
> found nothing, and cannot prove the absence: it names the person to ask, which
> is the paragraph below's point and its actual value.

Non-channel meeting recordings land in the **organiser's own OneDrive** (`/Recordings`), and the researcher schedules the interview. So the only permission needed is one the user can grant themselves.

**v1 fetches only what the researcher organised.** Where a client PM booked the calls, the recording is in *their* OneDrive and shared-with-me generally needs `Files.Read.All` — the admin wall. A freelancer as a guest in a client tenant may have no access at all. Both are real for the customer profile.

**But being the organiser is not sufficient, and this is the case that breaks the model.** An admin can turn on an org-wide policy — `Set-SPOTenant -BlockDownloadFileTypePolicy $true -BlockDownloadFileTypeIds TeamsMeetingRecording` — giving *browser-only* access with, verbatim, **"no ability to download or sync files or access them through apps."** That last clause is Graph: the API path is blocked, not merely the download button. It needs a **SharePoint Advanced Management (Syntex)** licence, so it is not universal — but it is precisely what a regulated client buys, which means it is likeliest exactly where the recordings matter most. Named security groups can be exempted (`-ExcludedBlockDownloadGroupIds`); app-only callers such as antivirus are exempt, which does not help a delegated app. It applies to new recordings only, and not to manually uploaded files. And for **channel** meetings under the Block policy, recordings land in a *View only* folder where even the meeting organiser is view-only unless they are also a channel owner.

Two consequences. **Availability must be resolved at list time**, per §7's per-item model — a row reading "your organisation blocks downloading recordings" is a usable answer; twenty ticked rows returning 403 at fetch time is not. And **there is no manual fallback here**: the researcher cannot download the file by hand either, so §4's usual "drag-drop still works" escape does not apply. For a tenant with this policy on, Bristlenose cannot obtain those recordings by any route. State that plainly rather than let a cohort call discover it.

Three things make the organiser requirement a fair v1 constraint rather than a silent limitation:

- **It is not a per-row failure.** Listing the researcher's own `/Recordings` means everything in the list is fetchable by construction. Other people's meetings don't 403 at fetch time — they simply aren't there.
- **But absence must be legible, and actionable.** That is exactly the trap §6 addresses: a shorter list is also what every join failure looks like. The list must state *"8 meetings in window · 4 recordings you can fetch · 4 organised by someone else"*, so "not yours" is distinguishable from "didn't record". **And revealing those rows must name the organiser**, because the real-world fix is to ping them and ask — a count is dead weight, a name is a workflow. The two unreachable cases take opposite messages and point at different people: a *view-only* recording is the researcher's own, blocked by their tenant, so the remedy is an IT exemption and naming the organiser would be absurd (it is them); a *not-yours* meeting needs its organiser, to share it or to download and hand over a copy. Honesty limit to hold: for someone else's meeting we know the event and the organiser but **not whether it was recorded** — that would need `Files.Read.All`. So the copy is "ask them", never "they have it", and length and expiry render as unknown. Surface this in the footer on row focus rather than a tooltip: keyboard-reachable, room for a sentence plus a Copy Email action, and the space already exists.
- **The roster survives the break.** The calendar event is in the *researcher's own* calendar because they were invited to it, so `Calendars.Read` still returns the attendee list even where `Files.Read` cannot reach the recording. The roster feature works for people the download feature cannot help.

**Manual drag-drop import stays a first-class path forever** — not a fallback, and not something to deprecate once this ships. It is the whole answer for the non-organiser case.

---

## 5. Sequence — Teams first, and why

**Teams → Zoom → Meet.** Same order the 28 Jul draft proposed, different and stronger reasons.

**Teams is the only one of the three with no third-party gate.** Video, roster and list are all delegated, own-data, user-consentable: no app review, no verification fee, no annual audit. It also wins on documentation depth, prior art, implementation simplicity, and on market share for the population that matters — *client organisations*, not researchers (§9). The costs are the transcript (admin-walled) and §4's organiser constraint.

**The one caveat that could reorder this is §3's tenant-policy question.** "It can ship to the cohort the day it is finished" holds only if the researcher can actually self-consent in a real tenant. If publisher verification turns out to be a prerequisite, Teams has a gate after all — a smaller one than Zoom's review, but not zero. Probe before committing.

**Zoom second, but start its review clock first — and the clock is longer than this doc claimed.** _Corrected 15 Aug 2026._ "One-time, unpaid, and mostly latency" is two-thirds right. One-time ✓ (no resubmission for scope *reductions*, and you may list/unlist freely afterwards). Unpaid ✓ (no submission fee anywhere in Zoom's docs). **"Mostly latency" ✗, and materially so:** Zoom's own App Review page opens with *"Public and unlisted apps undergo a dedicated review process"* — Unlisted is **not** a lighter tier. It carries a functionality review where they install and drive the app, and a **security review**: a mandatory Technical Design Document, scope minimisation (*"Developers may be asked to remove unused or inappropriate scopes"*), OWASP Top 10 testing, vulnerable-library checks and manual penetration testing, with remediation loops. Zoom publishes a 72-hour *first response* SLA and no end-to-end figure. EU availability additionally wants DSA trader disclosure — public business address and phone, and privately a bank account and an identification document.

So Zoom's gate is the largest of the three in *substance*, while Google's is the largest in *latency*. That does not reorder §5 — the two things that put Zoom second are unchanged and both still hold — but it does change what "start the clock early" means. It is not a form to file; it is a document to write.

**What is unchanged, and still decisive:** you can build and dogfood against your own account with **no review at all** (Local Test, or a Private app taking up to 100 user-level additions), because review gates *distribution*. And one call still returns list, video *and* VTT, which is why Zoom remains the platform where §8's question can be asked at all — though Meet's per-utterance transcript now makes it the platform where the answer would be most *useful*.

**Google last, but no longer conditional — and its ceiling is higher than Teams'.** _Revised 15 Aug 2026; the 14 Aug reasoning was priced off the wrong door (§3)._ The recurring cost and the annual re-audit were the whole argument for gating Google on demand, and on the `meetings.space.readonly` + `drive.file` path there is no recurring cost, no assessment and no admin gate. What remains is **sensitive-scope verification** — Google review, demo video, verified domain, roughly a week to ten days — which is latency, one-time, unpaid, and the same *kind* of gate as Zoom's review rather than a different order of thing.

So the order stands as **Teams → Zoom → Meet**, on unchanged reasoning — Teams has no third-party gate at all, and Zoom's clock should start early — but the reason for Google's position changes from *"it costs money forever"* to *"it is third in a queue"*. Start its verification clock alongside Zoom's; the queue is the cost now.

> **Corrected 16 Aug 2026 — the paragraph above prices Google's third door and never names the first two, and for the alpha cohort it is the wrong door.** Sensitive-scope verification gates **general availability**. It does not gate a cohort, and Google publishes two ways past it:
>
> - **Internal audience.** A Cloud project owned by a Workspace organisation may set its consent screen to Internal. Sensitive scopes work at once, for everyone in the org, with **no verification of any kind**. Nobody outside the org can sign in — which is the whole cost.
> - **External, publishing status Testing.** Up to **100 named test users**, sensitive scopes, no verification. The cost is that refresh tokens issued in this state expire after **7 days**, so a tester re-authenticates weekly.
>
> The alpha cohort is 5–10 people (§9). It fits the second door with ninety places spare, and the first door covers dogfooding today at zero cost. So "roughly a week to ten days" is a real gate on shipping and **not** a gate on the cohort, and the sentence above reads as though it were both.
>
> **This inverts the comparison the previous two days built, and that is the finding.** §3's load-bearing Microsoft question was answered on 16 Aug by the Entra UI itself: *"End users cannot grant consent to newly registered multitenant apps without verified publishers"* — so Teams, the platform chosen precisely because it had **no third-party gate**, cannot reach a cohort researcher until Publisher Verification is done (MPN account, DNS-verified domain). Meanwhile Google's cohort door opens by adding an email address to a list.
>
> **Teams → Zoom → Meet is not reordered by this**, because the order was chosen on ceiling and effort rather than on gate latency, and Teams' build is done while Google's has never made a live call. But the standing claim that Teams is the one that "can ship to the cohort the day it is finished" is now false, and Google is the one that could — a reversal worth holding in view if Publisher Verification stalls.

> **Inverted 16 Aug 2026 by a live tenant, and the inversion is the useful part.** The paragraph below is correct about the **API** door and wrong about the platform. It reasoned from `conferenceRecords` alone and never asked what the *file* door serves — which turned out to be a tab inside a Gemini notes Doc (§3). Both doors were real; only one had been priced.

**And one artifact where Google is the strongest of the three, not the weakest.** Teams' transcript is admin-walled (§3) and Zoom's rides the same call as the video; Google's is a **first-class, per-utterance, speaker-attributed, timecoded API resource on a sensitive scope**. If §8's open question is ever settled in favour of the platform transcript, Google is where that pays off most — which is an argument for building it *before* the answer arrives rather than after, since it is the platform that would make the experiment worth running.

**What replaces it: for v1, Google is the weakest of the three, and deliberately so.** With the transcript descoped (§3), Google delivers video and roster where Teams delivers video, roster and a hand-downloadable `.vtt`, and Zoom delivers all three from one call. That is a scope decision rather than a platform limitation, and it is reversible: the API door is untouched and still the cheapest place to run §8's experiment, because it is the only one of the three that hands over per-utterance speaker attribution without an admin gate. The claim to retire is "Google is where the artifacts are best" as a reason to **sequence** it earlier. The claim to keep is "Google is where the transcript experiment is cheapest to run" as a reason to **return** to it once §8 has an answer.

---

## 6. Shape — the staircase

- **v1** — _as designed: Teams only, `Files.Read` + `Calendars.Read`. **What shipped 15 Aug 2026 is v1 across all three platforms**, because the research that repriced Google and Zoom arrived before the Teams build did._ List the researcher's own recordings, join to a calendar window for the roster where the platform has one. **Multi-select with per-row outcome.** Download into a destination project. ⚠️ Still owed at v1: `(platform, remoteID, account)` provenance per imported session. ~~And the derived `stat`-based import state below — all three adapters currently hardcode `.notImported`.~~ _Corrected 18 Aug 2026: literally true of the adapters and misleading as written._ The derivation moved up into `CloudImportStore.rebuild()`, where it serves every platform at once, because already-held-ness is a fact about the destination folder rather than about any vendor. What **is** still owed is the Teams half of the measurement: the 2s duration tolerance has never been checked against a real Graph pair.
- **v1.1** — within-file resume (Range requests), and attendee/`@domain`/description search (which needs the `Calendars.Read` upgrade).
- **Then** Zoom (review already in flight per §5), then Google (only if asked).

**Three changes from the 28 Jul staircase**, all from the 14 Aug pass:

**Title filtering needs no calendar — and the title is the *only* thing the filename can be trusted for.** Teams puts the meeting title in the recording's filename, so filtering on "Interview" is free from `Files.Read` alone. The old v2 gate on search was right only for *attendee / `@domain` / description* search. Caveat to state in the UI rather than hide: title filtering rides on meeting-naming discipline, and "Chat with Sarah" will not match.

Two real specimens, both captured 15 Aug 2026 — **the format is tier-dependent**:

```
Meeting with Martin Storey-20260719_142007UTC-Meeting Recording.mp4   (personal)
Meeting with Martin Storey-20260815_200732-Meeting Recording.mp4      (business)
```

> **Superseded 15 Aug 2026 by a business-tier specimen.** The paragraph below was written from the personal specimen alone and its instruction — "parse it as UTC" — is **wrong for the tier that ships**. Preserved because the reasoning was sound on one specimen and the delta is the lesson: a filename grammar observed once is a guess.

**The timestamp is UTC, and the `UTC` suffix says so — parse it as such.** This removes one of the two timezone hazards in the join (§6.1), and the same observation demonstrates the other: that recording displayed as **16:20** in Teams while the filename read **14:20:07 UTC**, a two-hour gap consistent with the client rendering local time in a UTC+2 zone. Parse the filename as local and the 30-day window is wrong by the offset, silently dropping meetings at each edge. The remaining drift to measure in Q3 is therefore only *recording-start minus meeting-start* — how late everyone joined — not a timezone term.

**What replaces it: never take the moment from the filename.** A business tenant omits the `UTC` marker, and the timestamp it writes instead is in neither UTC nor the user's local time. Measured on the business specimen: the filename reads **20:07:32**, the mp4's own `format.tags.creation_time` reads **`2026-08-15T18:07:38Z`**, and the machine was in London on BST (UTC+1). The filename is therefore **UTC+2** — a server-side zone, set on the tenant or the mailbox, which the researcher never chose and cannot see from the filename. **No regex can resolve it**, so there is no correct pattern to write.

Take the moment from a source that carries its zone: `driveItem.createdDateTime` over Graph, or `format.tags.creation_time` from the file once it is local. `TeamsRecordingName.startedAtUTC` is deliberately **optional and nil** when the marker is absent, because returning a plausible-looking wrong `Date` is exactly how the 30-day window silently drops meetings at each edge. Commit *"teams filenames: the UTC marker is personal-tier only, and the business timestamp is unknowable"*.

**Two invariants this cost us, both worth stating once.**

- **A parse refusal must produce a stated row, never a silent drop.** The Swift parser required the `UTC` literal, so every business recording was dropped from the listing — and because a dropped row leaves `outcome` untouched, the window reported a folder *containing* a recording as "No recordings in the last 30 days", and the footer then read "1 organised by someone else" about a meeting the user had organised themselves. That is requirement 1 below failing in precisely the way it exists to prevent.
- **A filename grammar must be pinned by an observed specimen, never a constructed one.** Bristlenose's *pipeline* had the same bug independently: `_TEAMS_SUFFIX_RE` in `s01_ingest.py` required whitespace where both real formats use a hyphen, so it matched only the fixture invented alongside it in Feb 2026. A downloaded recording and its transcript therefore ingested as **two sessions** — the mp4 re-transcribed from scratch, the report gaining a duplicate participant — live in shipping code for six months with a green suite throughout. Both test suites now carry the real specimens, tagged with tier and capture date, behind a comment marking the line between constructed and observed.

**Google's specimens, captured 16 Aug 2026 on Business Standard, en-GB, BST — and its grammar is *derived*, which Teams' is not:**

```
folder      Banyalbufar discussion - 2026/08/15 22:45 BST
recording   Banyalbufar discussion - 2026/08/15 22:45 BST - Recording
notes doc   Banyalbufar discussion - 2026/08/15 23:02 BST - Notes by Gemini
downloaded  Banyalbufar discussion - 2026_08_15 23_02 BST - Notes by Gemini.docx
```

Four things follow, and only the first is good news.

**The file name is the folder name plus a suffix.** So one observed folder tells you the shape of everything inside it, where Teams required a specimen per tier. Drive's UI hides the extension; confirm separately what the API returns for `name`.

**Google names the zone inline — and you still must not parse it.** `BST` sits in the filename where the Teams business tier wrote a bare server-side timestamp, so the moment looks recoverable here in a way it genuinely was not there. It isn't. Zone abbreviations are globally ambiguous (`BST` is British Summer Time here and Bangladesh Standard Time elsewhere; `CST` is three separate zones), and this is presumably rendered in the organiser's locale rather than a fixed one. The Teams rule is unchanged and now holds for two platforms for two different reasons: **take the moment from a source that carries its offset** — `createdDateTime` over the Drive API. Note also minute resolution, no seconds, where Teams gave six digits.

**The recording and its Doc carry different timestamps for the same meeting** — `22:45` and `23:02`. The folder is stamped at conference start and the recording inherits the folder's name; the Doc is stamped when note-taking began. They are provably the same meeting because the Doc's own *Attachments* line names the recording file. So **any timestamp join between a recording and its transcript is dead on Google**, and that in-body cross-reference is the only name-level link there is — localised prose, not a join key. Resolve by id or by Picker selection, exactly as this section already says for folder names.

**The API `name` and the on-disk name are different strings.** Drive returns `2026/08/15 23:02`; the download sanitises `/` and `:` to `_`. This is the invariant above arriving in a new shape — not "one specimen is a guess" but **"one *observation point* is a guess"**. A parser pinned against a downloaded file will not match a listing, and the drag-drop path and the adapter path see different names for the same artifact.

**Do not assume `/Recordings` exists.** That convention is work/school-tier. On a **personal Teams account the recording is attached to the meeting chat** with a Download button — nothing lands in OneDrive, which is why a Graph probe of `/me/drive/root:/Recordings:` returns `itemNotFound` on such an account. The adapter needs a tier check beside the `driveType` check, and a legible refusal rather than an empty list.

**The Teams Graph surface is licence-gated, and it says so.** `GET /me/chats` on an unlicensed account returns **401** with `"Invoked API requires a valid license. No valid license found."` (observed 15 Aug 2026). Useful twice over: it names the missing thing precisely enough to tell a researcher what to do, and it means the gate is a licence rather than a fundamental account-type incompatibility. **But note the hazard — that is a 401, and so is an expired token, with opposite remedies.** An adapter that treats every 401 as refresh-and-retry will loop forever against an unlicensed account, re-authenticating endlessly and never explaining itself. Branch on the error body, not the status code. Same family as the 401-vs-403 split in §4.

**Teams shows time remaining, not the policy — copy that.** A recording made 19 July read *"Expires in 4 days"* on 15 August, i.e. roughly a 30-day retention observed as a live countdown. Two things follow. The countdown, not the retention figure, is what belongs next to the tick-box (§9) — Microsoft's own product renders exactly the affordance this doc proposes, on exactly this data. And personal-tier retention (~30 days observed) is shorter than the work-tier figures in §1 (120 documented, commonly 60), so the clock the retention argument rests on is tier-dependent and should not be quoted as one number.

**Calendar access moved from v2 to v1.** Not for search — for the roster (§1, §4).

**Multi-select moved from v1.1 to v1**, because the feature as the researcher describes it *is* multi-select; a single-select v1 would ship something nobody asked for.

### The five things that make a batch honest

_Four when written; a fifth was promised in §3 on 15 Aug and is added below._

These are v1 requirements, not polish. Each closes a failure that would otherwise be **invisible** — and this feature's designed output and its failure output are both "a shorter list", which is the worst possible property for a feature whose justification is beating an expiry clock.

**1. Show the join's arithmetic.** The calendar↔recording join is an inner join over two independently-paginated, independently-windowed lists. Its intended output is "shorter than your calendar" — and so is an unfollowed `@odata.nextLink` (which returns HTTP 200 with a partial page), a UTC-vs-local window shift at the edges, a fuzzy `(title, timestamp)` join key where the title is user-mutable and the timestamp is recording-start not meeting-start, or `/events` returning series masters where `/calendarView` would expand occurrences. Every one produces a short list the researcher reads as "it didn't record". So: display `N in window · M you can fetch · N−M unmatched` permanently, make the unmatched count a **disclosure rather than an inline list** (on a busy calendar, listing them buries eight real recordings under ninety stand-ups — the count is what has to be always-visible, not the rows), pin the timezone, and make paginator terminal state explicit (`exhausted` / `page_cap_hit` / `error`) so a truncated listing fails loudly instead of looking complete.

**Timezone is load-bearing twice.** Internally, `calendarView` honours `Prefer: outlook.timezone` and a UTC-vs-local mismatch shifts the window boundary by up to a day at each edge — silently dropping a 9am Monday interview out of "last 30 days". Externally, the list needs a **time** column, not just a date: UR batches sessions, so two or three interviews on one Wednesday is the normal case and the date disambiguates nothing. State the zone once in the column header rather than on every row, and render in the researcher's current local zone as Calendar.app does. §9's privacy argument is satisfied by not *persisting* unmatched entries; it does not require hiding them in-session.

**2. Prove the bytes arrived.** A `fetch` whose only success signal is not-throwing will happily write a 401 body into a `.mp4`, or half a file. The loud version fails hours later at stage 2; the quiet version is a **truncated-but-valid MP4** that ffprobe accepts, Whisper transcribes for 40 of 60 minutes, and the report presents as a confident analysis of a complete session. Write to `.part`, check status *before* opening the destination, compare bytes written against both `content-length` and the listing's own file size (an independent second source that catches a redirect), check magic bytes, then `os.replace`. **Better: the listing carries hashes** — observed live 14 Aug 2026, a `driveItem` returns `hashes: {quickXorHash, sha1Hash, sha256Hash}` alongside `size`, *before* the download — so verification can be exact rather than heuristic. Caveat to confirm on a work tenant: personal OneDrive returns all three, while business OneDrive/SharePoint has historically returned only `quickXorHash` (documented and implementable, so the check survives either way — only the algorithm changes).

**The download URL is itself a credential — confirmed, not inferred.** A live listing returns `@microsoft.graph.downloadUrl` with `tempauth=v1e.eyJ…` in the query string: an expiring bearer token, in the URL, in the listing response. So the no-logging rule in §9 is a hard requirement, not a precaution, and the `exp` claim it carries is why §9 says to re-resolve the URL immediately before each fetch rather than at list time. Nothing half-written is ever visible — **which also hands this section the rollback path it used to say did not exist.**

**3. Derive already-imported state; never store it as a boolean.** This record is load-bearing for partial-failure recovery, and every plausible write point but one biases toward under-reporting what needs re-fetching — the direction that loses data. Deriving dissolves the question. You can **see** a file; you must **trust** a flag.

But "did we import it" and "can we read it now" are different questions, and the obvious check answers the wrong one. **`fileExists()` returns true for a cloud placeholder** — that is exactly why `.inCloud` is currently unreachable (`design-project-storage.md` §3) — so an existence test reports *imported and present* for a file that raises `EDEADLK` on read. **Resolve from `stat` alone, never by reading bytes**: materialising placeholders to verify them would fire N multi-gigabyte downloads just to open the window. `stat` yields existence, logical size and `SF_DATALESS` on a placeholder without faulting it in, and size-against-the-byte-count-recorded-at-import *is* the truncation check — no hashing needed.

Seven states, resolved per row at list time (`ImportRowState`):

| State | Tick | Means | Fix path |
|---|---|---|---|
| **not imported** | empty, enabled | no local file | fetch from the platform |
| **imported** | checked, disabled | present, resident, size matches | none — say nothing |
| **not downloaded** | checked, disabled | present but `SF_DATALESS` | the *destination* provider, named |
| **drive not connected** | checked, disabled | volume unmounted | reconnect the volume, named |
| **damaged** | empty, **enabled** | size ≠ recorded | re-fetch from the platform |
| **view only** | **none** | tenant blocks download (§4) | none — and no manual route either |
| **no longer on the platform** | none | absent from the listing | none — unrecoverable if not imported |

Four confusions this vocabulary exists to prevent, each of which has a cheaper wrong version:

- **A placeholder is not damaged.** It is a healthy file that needs fetching. Colouring it as an error repeats the exact defect `design-project-storage.md` §3 reproduced — *"ffprobe timed out"* read as "my video is broken" when it meant "still downloading". Neutral, not warning.
- **Not-downloaded must never look like not-imported.** If a placeholder shows as fetchable, the researcher re-pulls 1.3 GB from Teams for a file they already own — spending an expiry-limited remote fetch on a local problem. This is the expensive confusion and the reason the tick stays checked-and-disabled.
- **Two clouds, two fixes.** A placeholder needs fetching from the *destination* store (Dropbox, OneDrive, iCloud); a not-imported row needs fetching from *Teams*. Name the provider — the storage doc's rule — or the researcher has nowhere to go.
- **An unmounted volume is not a missing file.** `ProjectAvailability` already models `.cantFind(.unmountedVolume(name:))`; reuse it. "On *T7*, not connected" is actionable; "missing" is not.

Note the collapse: **the remote axis mostly does not produce states.** An expired recording simply stops appearing in the listing, so "gone from Teams *and* imported" is the feature working (say nothing) and "gone *and* not imported" cannot be shown at all — which is §6's arithmetic problem, not a row state. Teams moves expirations to a recycle bin rather than hard-deleting, so a grace-period surface is conceivable later; not v1.

**4. A terminus carrying arithmetic the user cannot miss** — `20 requested · 18 imported · 2 failed` — and the failure count must survive the surface closing. Partial failure is not only a list-reconciliation problem: stages 10 and 11 cluster and theme *across* sessions, so analysing 19 of 20 does not produce "the report minus one session", it produces **different themes**, in a report that looks internally consistent and complete. If a project holds failed import rows, Analyse should say so before running — state it, don't block. New states go through the five-kind `MessageKind` taxonomy (`docs/design-pipeline-diagnostic-popover.md`), not new glyphs.

⚠️ Neither half of requirement 4 shipped: `CloudImportStore.terminus` is in-memory and dies with the window, and no Analyse-time check reads failed import rows. The arithmetic renders correctly *while the window is open*, which is the easy half.

**5. A sign-in that never returns must be its own state.** On Zoom, Marketplace pre-approval is enabled **by default** on every multi-seat account, and the block is enforced on the vendor's own consent screen *before any redirect* — so no code, no error and no callback reaches Bristlenose. Teams has the same shape through Entra's user-consent policy. The researcher clicks Sign In, reads a page telling them to ask their admin, and returns to an app that is still spinning.

From inside the app, "you closed the window" and "your organisation has to approve this first" are **indistinguishable** — `ASWebAuthenticationSession` reports plain cancellation for both. So the state must not be called *cancelled*: that word sends someone to retry, forever, against a wall only somebody else can remove. It names both possibilities, the researcher's own action first, and it is the one requirement here that shipped complete (`CloudImportStore.Phase.signInIncomplete`, `CloudPlatform.signInMayAwaitAdminApproval`, and a Diagnostics fixture, since a tenant whose admin has not approved us cannot be conjured).

**Its sibling state, and the three refusals it tells apart.** _Added 18 Aug 2026 (`7da5f42b`, landed `d345cb56`)._ The paragraph above is right that *cancellation* and *awaiting approval* are indistinguishable — but Entra's own error codes distinguish three refusals that arrive on the same screen, and only one is worth retrying. `MicrosoftSignInRefusal` classifies them (`TeamsOAuth.swift:111-155`):

| Code | Meaning | Retry? |
|---|---|---|
| `AADSTS65004` | They read the consent screen and said no | **Yes** — the one case where the button is right |
| `AADSTS90094` / `65001` | The tenant requires an administrator | No — only their IT can lift it |
| `AADSTS53003` | Conditional Access; the sign-in *succeeded* and the token was refused anyway | No — not fixable by anyone in the conversation |

So `.failed` carries `worthRetrying:` (`CloudImportStore.swift:23-52`) and the window shows Try Again only when a second attempt could differ. Anything unclassifiable is presumed retryable: an unnecessary button wastes a click, a withheld one strands someone a retry would have rescued.

Two corrections came with it, both of the same shape — an affordance that could not work. **Cancelling a Teams sign-in now reaches `signInIncomplete`**; there were catches for Zoom and Google and none for Microsoft, so abandoning a Teams sign-in landed on the error screen while the same act on the other two landed on the calm one. And **Try Again retries the sign-in, not the listing** — it called `load()` with no token, because `.failed`'s doc comment said "listing failed outright" while its only construction site was the sign-in catch. The wrong comment is what propagated the bug.

**One rule worth promoting out of the code comment: match the full `AADSTSnnnnn`, never the bare number.** Entra's descriptions carry correlation IDs and timestamps, so `contains("65001")` can be satisfied by a digit run inside an unrelated failure — and misclassify it as an admin gate, which is exactly the verdict that removes the retry button.

**The unit of recovery is the file, not the batch.** `.part` plus derived already-imported state means an interrupted batch loses at most one file's progress, so within-file Range resume can stay at v1.1 without v1 shipping a batch that can't recover.

**Built 15 Aug 2026 — one download path, three platforms** (`CloudDownloadVerification`, `CloudDownloader`). The sequence is the design, and every step exists because of a failure the previous step cannot catch:

1. **Free space, before a byte moves.** All three carry size in the listing, so this is free — Google confirmed 16 Aug 2026 on a live tenant.
2. **The response head, before the destination exists.** An HTML login page or a 59-byte JSON error arriving with a 200 is refused here, so no file is ever created for it.
3. **Transfer to the system temp dir**, via a `URLSession` *download task* — not `URLSession.bytes`, which reads pleasantly and spends an 800 MB transfer in Swift array bookkeeping.
4. **Size, then magic bytes, then hash** — increasing cost, so a file failing the free check never pays for the expensive one. Size catches truncation; magic bytes catch the case size cannot, where a redirect served something else of coincidentally similar length; the hash makes Microsoft exact rather than heuristic, since Graph is the only one of the three that publishes one before the download.
5. **Two moves to publish.** The temp dir is often on a different volume, and a cross-volume move is a copy — not atomic. So the copy lands under `.part`, where a crash leaves something obviously unfinished, and only the final same-volume rename makes the real name appear. **The destination path never names a partial file, for any instant.**

Three per-platform differences are all that vary, and they live in one `CloudTransferPolicy`: Graph sends **no header** (its URL carries `tempauth=`, which is why §9 forbids logging it), Zoom **strips** the header across its CDN redirect, Google keeps it. The row deliberately carries no download URL at all — those are credentials, and a value type that reaches the view layer is how one ends up in a log line or a screenshot; the adapters hold them.

**Google needs one extra step, and it belongs to the batch rather than the row.** `drive.file` grants access per file through a Picker round trip, and the desktop Picker permits that scope and no other — so it cannot ride the sign-in. `prepareBatch` runs the Picker once over the ticked set; a declined grant fails the batch before any transfer starts, because none of the rows would be reachable. Teams and Zoom implement it as a no-op.

---

## 7. Architecture — macOS-only, Swift end to end

**v1 is a macOS feature. The CLI does not get cloud import.** This is the decision that makes the rest of the design tractable, and it is worth being explicit about why, because an earlier draft assumed CLI parity and paid heavily for it.

**It deletes the hardest problem rather than solving it.** With a Swift/Python split, the refresh token has to cross a process boundary, and the LLM-key pattern cannot carry it: `childEnvironment` builds the environment once at spawn so it cannot rotate; every forked grandchild inherits it (the sidecar forks ffmpeg, ffprobe and `pip`, so a client's tenant credential would sit in pip's environment while pip talks to the network); and persisting a rotated refresh token needs a Keychain write Python cannot make under App Sandbox — which is the entire reason that pattern exists. Swift-owns-everything makes the question moot: the token never leaves the process that can refresh it.

**It hands us the right engine for free.** `URLSession` background download tasks give 401-retry-with-fresh-token, resume data, and survival across lid-close and network changes — one primitive answering token refresh, resumability and "the researcher got on a train" together. `OllamaDownloadModel.swift` is the in-tree precedent for a large network download with streaming progress and cooperative cancel; **`CopyMachinery` is not.** Its ring, hover-cancel and subtitle slot are reusable; its engine is single-in-flight, local `FileManager.copyItem` transport, and `rollback(written:)` deletes every already-written file on cancel — which would destroy the recovery path §6 is built on.

**The destination picker is inherently multi-project, and multi-project lives natively.** The SPA is scoped to one project by construction (`serve` opens a folder), so an import surface offering "New project… or this one" wants to be where projects are.

**This is not a fork.** `docs/design-modularity.md` protects the *pipeline* from forking. Drag-drop import is already macOS-only and nobody calls that a fork — cloud import is drag-drop with a different source. The CLI's import story exists and is the filesystem: point `bristlenose run` at a synced OneDrive folder. Linux users lose an accelerant, not a capability.

**The spine was extracted on the second implementation, exactly as this section instructed** — `CloudImportSource`, 15 Aug 2026. _This paragraph previously read "No `CallSource` protocol yet… extract the interface when Zoom is a real second implementation." The rule was followed; the conclusion is now history, and the timing is the part worth keeping._

The extraction commit sits **between** Google and Zoom, not after both — Google 02:31, extraction 02:39, Zoom 02:57 — which is the "at n=2, not n=1" discipline working rather than being remembered afterwards. The Speculative-Generality argument is why the timing was right, and it stands.

What is interesting is that the three specific blockers this section named to justify waiting did not persist — they **dissolved**, and each dissolved into a design improvement rather than a compromise:

- *"Google's Picker path returns a selection from a foreign UI and does not fit a `listCalls(window:)` shape at all"* → absorbed as `prepareBatch(rowIDs:)`, a protocol method with a default no-op extension. Google runs its Picker once per batch; the other two implement nothing.
- *"Zoom returns download URLs from the list call while Teams needs a second"* → dissolved by deciding the row carries **no** download URL at all. Those are credentials (§9), so the adapters hold them and the shared type never sees one. A privacy rule removed an abstraction problem.
- *"the sketch carried no cancel, no progress"* → `fetch(row:destination:progress:)` plus `FetchOutcome.cancelled`.

Only *no resume token* survives, and it is still v1.1 per the staircase above.

The 80/20 split held, and is now observable rather than estimated — **shared spine** (the protocol, the state machine, the window, the vendor vocabulary in `CloudPlatform`, the whole download-and-verify path) versus **per-platform adapter** (endpoints, scopes, pagination, date-windowing, record mapping, error dialect, OAuth ceremony). The pre-contact estimate said platform #1 costs roughly five times platform #2. ⚠️ That ratio is now measurable and has **not** been measured; three platforms landed the same day, but the second and third were each preceded by a research pass whose cost dwarfed the coding, so the naive wall-clock comparison would flatter the spine. Treat the 5× figure as the sequencing argument it always was, not as a retrospective finding.

**Model artifact availability per item, not per platform.** "Available" is the conjunction of what the platform can serve, what the granted scopes allow, and whether *this* item is reachable — resolve it at list time from the listing response, so a row can say "roster — needs calendar access" rather than silently having none.

**Do not take the vendor SDKs — that call stands, and the prior-art pass confirmed why.** MSAL wants its own keychain access group (`com.microsoft.universalstorage`), which is precisely the token-storage conflict with `KeychainHelper` this doc anticipated; it is an Objective-C library distributed CocoaPods-first; and **Microsoft's own macOS Swift + Graph sample was archived on 15 June 2026**, which is a maintenance signal rather than a recommendation. There is also **no Swift Graph SDK at all** — only the Objective-C one, whose iOS sibling is likewise archived. So the vendor path is worse-supported than it looks.

**But "hand-roll it" is not the only alternative, and the prior-art pass found the third option.** [AppAuth](https://github.com/openid/AppAuth-iOS) is the OpenID Foundation's client: macOS 10.9+, built on `ASWebAuthenticationSession` (the same primitive we would hand-roll on), Swift Package Manager, and it supports **both** the custom-scheme and loopback redirect styles §2 weighs up. Critically it is **vendor-neutral**, so one dependency serves Teams, Zoom *and* Google rather than three vendor SDKs with three sets of opinions — which fits the spine/adapter split far better than anything Microsoft ships.

**This is an open decision, not a settled one.** Against AppAuth: a nested Mach-O in a sandboxed App Store binary, and an Objective-C dependency. For it: PKCE, `state` validation, token refresh and error handling are exactly the security-sensitive infrastructure where a hand-rolled subtle bug *is* a vulnerability, and the house rule is to defer that class of work to battle-tested implementations rather than re-derive it. Weigh it properly before writing the ceremony — and note that `URLSession` still carries the *fetch* either way; this decision is only about the token dance.

**Key the credential on `(platform, account)`. Shipped 18 Aug 2026** (`8901845f`), and this paragraph's diagnosis was exact: `KeychainHelper` keyed every item on a fixed account string, so a second sign-in hit `errSecDuplicateItem`, took the `SecItemUpdate` path and **overwrote the first account's token in place** — no error, `set` returned `true`, and the first account stopped working at its next refresh with nothing anywhere saying why. It is now one Keychain item per account, `kSecAttrAccount` a SHA-256 hash, following `MCPTokenStore` as prescribed, plus a `kSecMatchLimitAll` enumeration this helper had no equivalent of and a one-shot migration off the old fixed key.

### The grant's lifecycle — four guards, all bought by a real loss

_Added 18 Aug 2026._ Keying was the first bug in this seam and not the last.
Every credential-loss defect found since went through **one function**,
`onGrantChanged` — the callback an adapter fires when its tokens move — which is
why these belong together rather than as four scattered notes.

**One owner for the write** (`357818b5`). Per-adapter `Task.detached` publishes
have no relative ordering, so a refusal could land *after* a successful
re-sign-in and tombstone a working grant. A serial `CloudGrantWriter` owns both
the key and the write, holding no lock across the Keychain call. The contract
that falls out: `onGrantChanged` must not block.

**A tombstone only on a 4xx from the token endpoint** (`f8e78ae4`, `af9b38b4`).
`try? await client.refresh()` made a dropped connection indistinguishable from
an authoritative refusal, and `revoked()` strips the refresh token — so **one
wifi blip permanently destroyed a working sign-in**, on the aged-out-token path,
which is the ordinary next-morning case rather than an exotic one.

**A passive read keeps what it cannot parse; only the restore path discards**
(`d054b3d6`). `connections()` decoded every grant just to draw a Settings row,
so *opening the pane* deleted blobs it could not read — and with iCloud sync on,
an older Mac propagates that deletion everywhere. Chesterton's fence moved to
where the discarding is intended, not removed.

**The account key never goes backwards** (`f8e78ae4`). A transient `/me` failure
nil-ing a known-good address re-derived the anonymous key and let the rekey
delete the correctly-keyed item. Rekeying now only ever leaves the anonymous
slot.

Two testing rules came out of the same work and generalise past this feature.
`StubURLProtocol` registers **process-wide**, so grant-lifecycle suites must be
`.serialized` or they see each other's stubs. And **a fake that cannot fail can
only prove the happy path**: `InMemoryKeychain` had no refusal mode, so every
failure branch was unreachable by any test — including `-34018` on every write,
which is the *ordinary* state of an ad-hoc-signed local build. Sibling to the
lesson §9's Testing paragraph already carries.

Two departures from the prescription above, both deliberate.

**The stable identifier is the signed-in address, not an id claim.** Microsoft's `oid`+`tid` and Google's `sub` would survive a rename; parsing them was cut for v1 because the only failure they prevent is a researcher who renames their account, signs in again, and acquires a second row for the same account — a row that is visible, labelled with its address, and removable. The hashing survives untouched and for exactly the reason stated: `kSecAttrAccount` is unencrypted metadata, and a client's email address readable in Keychain Access is the leak this project cares about.

**Non-synchronizable was reversed — cloud grants stay in iCloud Keychain.** _Settled 18 Aug 2026; this sentence used to say the opposite, and so does §10's cost line, which is corrected there._ The realistic loss event is the Mac being stolen, and iCloud Keychain is what recovers from it; the alternatives are paper, a USB stick, or a paid password manager. It is end-to-end encrypted regardless of Advanced Data Protection, so this is not plaintext-to-Apple, and the grant permits downloading a limited set of recordings from an account the researcher is signed into on the same devices all day. `MCPTokenStore` remains non-synchronizable for a reason that does not transfer: that token names a server on *this* machine and is meaningless on another Mac. **The timing was forced rather than chosen** — `kSecAttrSynchronizable` cannot be flipped on an existing item by `SecItemUpdate`, so the migration was the one cheap moment the answer could ever have changed.

**Before writing the Teams adapter, spend an hour in Graph Explorer** — against a real client-shaped tenant, not just your own, because §3's consent-policy question is answered by watching whether the prompt appears or bounces to "Need admin approval". The other unknowns are cheap to see and expensive to design around: how external participants render in `attendees[]`, and how reliable the filename format is.

---

## 8. The transcript question is open — measure it properly, or not at all

The 28 Jul draft said: *never take the platform transcript in place of Whisper — real-time ASR with weak diarisation.* **The conclusion survives as a default; the stated reason does not.**

- **On word accuracy, Whisper's advantage is not established for this audio.** Whisper large-v3 is usually reported near 1.8% WER on LibriSpeech test-clean, but that is clean read speech. On the **AMI meeting corpus** it rises into double figures — and the mic condition matters more than the headline: AMI-IHM (a headset per participant) and AMI-SDM (one distant mic) differ by roughly 2×, and a platform recording, where each participant is on their own device mic before mixing, sits far closer to IHM. Quote the condition or the comparison is unfalsifiable.
- **On diarisation the old claim is probably backwards.** The platform transcribes the **per-participant stream, pre-mix**, so speaker attribution is stream-derived ground truth with a real name attached. Whisper carries no notion of who is talking; any pipeline returning labelled dialogue is joining it to a separate diarisation model inferring speakers from mixed-down audio. The platform is likely the **stronger** side here.
- **The platform also transcribes better source audio than BN will ever receive** — pre-mix, pre-compression. Structural; no model choice closes it.
- **And on Google the diarisation argument stops being theoretical** (verified 15 Aug 2026). `conferenceRecords.transcripts.entries` returns one entry per utterance carrying `participant`, `startTime`, `endTime` and `text`, and `participants.get` resolves the reference to a display name — so the "named speaker turns as an attribution scaffold, Whisper for the words" merge this section calls the shape worth testing is **directly constructible on Google**, on a sensitive scope, without the restricted tier. Google is therefore the platform on which the experiment is cheapest to run and the merge cheapest to build. Two cautions before anyone treats those entries as ground truth: Google itself warns the API entries "might not match the transcription found in the Google Docs transcript file", and a developer report (unanswered by Google) has the `fileGenerated` event firing with **4** entries where the same call held ~**500** days later. A silent truncation, not an error — so any importer must re-fetch and compare counts rather than trust the completion signal. That trap is a reason to build the merge carefully, not a reason to disbelieve the position.

There is no published head-to-head, and there probably cannot easily be one: vendors do not publish, and you cannot batch-feed a corpus through live transcription.

**So the honest position is "unknown, and the priors point the other way than we assumed" — not "the platform wins". Do not act on it yet.**

**And do not run the casual version of the experiment.** An earlier draft called this "a one-afternoon experiment: run a study both ways and look at where they disagree". That cannot produce a trustworthy answer — disagreement shows they differ, not which is right; there is no reference truth; this very section states the expected direction, so an unblinded adjudicator will read every disagreement as Whisper erring; and N=1 with no pre-registered decision rule concludes whatever the reader arrived believing. In a medical-UR context, a false "take the platform transcript" is the most expensive wrong conclusion in this doc. If it is worth doing it needs: a hand-corrected reference on a bounded sample, blind A/B adjudication, a pre-registered metric and decision rule, **diarisation scored separately from words** (since the argument above is that they point in opposite directions), and "no result" kept available as an outcome. `experiments/thematic-spike/` is the in-tree precedent for that shape. There is also a consent question in reusing participant recordings for a methodology comparison (`docs/methodology/consent-gradient.md`).

**The plumbing for the cheap version already exists** — BN parses subtitle files and `analyze` skips transcription — which is a reason to be careful, not a reason to proceed. The shape worth testing eventually is a **merge**: the platform's named speaker turns as the attribution scaffold, Whisper for the words.

---

## 9. Mechanics worth knowing before building

**Where the user starts, and how they get back.** `File ▸ Import from Teams…` as a sibling to the existing `File ▸ Add Files… ⇧⌘A` (whose own comment calls it "the menu twin of drag-drop") — **flat while there is one platform, a submenu at three**: a one-item submenu is a Mac smell, so this becomes `File ▸ Import ▸ Microsoft Teams… / Zoom… / Google Meet…` when the second lands, and takes the fuller product name there for parallelism. Also a project context-menu twin following the Agent Access pattern (context menu *hides* when unavailable, menu-bar twin *dims*), and `Bristlenose ▸ Accounts…` mirroring `Connect an Agent…`. Account lifecycle — sign in, sign out, "Connected as…", the scope disclosure — belongs in a **Settings ▸ Accounts** pane; the import surface shows a read-only account line only. One place to disconnect, not two. _Shipped 18 Aug 2026 (`d3b66642`), and **not** on the Mail Accounts pattern this sentence named._ Sidebar-and-detail is right when there is a detail worth showing; with a small fixed catalogue, one account each and a single verb, it would be chrome around nothing. What shipped is a **section per service**, each carrying one row in one of four states — unavailable, not connected, connected, needs attention. Two things about it are load-bearing. **The pane makes no network call**: every state is derived from the Keychain, the OAuth config and the address stored beside the tokens, so anything knowable only from a call has to be persisted when that call happens (Google's account tier falls out of the address domain and is free; Microsoft's `DriveTier` does not and is still owed a writer). And **connecting stays at the point of intent** — Connect… posts the same notification the File menu does and opens the import window, so there is one sign-in flow rather than a second one in Settings. Full state engine and the reasoning: `docs/mockups/settings-accounts-generalised.html`.

Two decisions the pane settled that are easy to re-propose, so they are recorded
here rather than only in commit bodies:

**One account per service, for v1.** The storage holds several — that is the
whole of the keying change — but the pane renders the first, because nothing yet
offers a way to connect a second. The long-term shape is named and is *not* this
pane grown a bit: an Internet-Accounts-style console holding arbitrary N accounts
across M services, with its own Add Account. macOS System Settings ▸ Internet
Accounts is the reference. Consequence to know: a second account reachable by
iCloud sync from another Mac is currently stored, invisible, and un-removable.

**A parked service is not listed at all.** `AccountService.all` reads
`CloudPlatform.shipping`, so Zoom is absent rather than present-and-inert. This
reversed a deliberate earlier call to list all four — the argument for listing
was that a catalogue hiding what is not ready cannot answer "what can this thing
talk to?", and it was wrong about the reader: a permanent row saying Bristlenose
cannot sign in to Zoom answers a question nobody asked and spends a quarter of
the pane doing it. Safe **only** because a parked platform cannot hold a grant;
re-check that before parking a service that has ever stored a sign-in.

**And no vendor glyphs in the pane or in `File ▸ Import`.** A generic SF Symbol
is *lawful* but was never the argument for having one — beside a vendor's name it
reads as their mark. `CloudPlatform.symbolName` is deleted.

> **Corrected the same day.** This bullet first read "no vendor glyphs
> **anywhere**", which is false, and it conflated two rows of §9a's table. The
> licences settled against are for the **product icon** (§9a row 3 — forbidden
> without one, and we do not need one). The **sign-in button** is row 1, where the
> vendor's mark is *required, specified and granted* — a different instrument.
> Settling against a licence we do not need cannot settle the surface where the
> vendor requires their mark.
>
> **Open, and a decision rather than wording:** `VendorMark`
> (`CloudImportWindow.swift:746`) still draws **letter glyphs** — `m.square`,
> `g.circle`, `z.square` — on that button, and its own comment calls them "a
> stand-in until it is". So the button is neither compliant (not the real mark)
> nor glyph-free. Either it takes the official assets, or it loses the mark and
> §9a's "required beside it, unaltered" has to be reckoned with. §9 and §9a cannot
> both be true as written.

**One window, globally, with the destination pre-selected by how you opened it.** Opening from a project's context menu pre-selects that project; opening from the File menu pre-selects the current one. Re-opening after a close is the **File** menu's job, not the Window menu's — HIG is explicit that the Window menu lists *currently open* windows (alphabetically) and that reopening belongs in File. Two consequences: the scene takes **`.commandsRemoved()`**, since a titled SwiftUI `Window` otherwise auto-contributes a Window-menu reopen entry that HIG says shouldn't be there — the project's existing rule for auxiliary windows, now with a second reason — while the window still appears in the open-windows list *while open*, because that listing is AppKit enumerating real `NSWindow`s rather than the scene contributing a command (verify on device). And note HIG's *"avoid listing panels or other modal views"* is a third independent argument for this being a window rather than a sheet. **Double-click on a project row is not available** as a door — `project_sidebar_rename_gestures_decided` already reserves it for opening the project itself.

**The fetch's progress belongs on the project's sidebar row, in the existing ring and subtitle.** Per-file state stays in the import window; the project's aggregate rides its row, so closing the window loses nothing. Prose stays minimal — the `RunProgressSubtitle` ladder (`stage · N of M · ETA`) is the vocabulary to extend, **not** `ProjectSubtitle.copying(fraction:)`, which carries a single 0–1 number with no item identity, count or ETA and therefore cannot say "Fetching 3 of 7 · 12 min left". Note `SubtitleVariant.isDiagnostic` is deliberately exhaustive with no `default`, so a new case forces an explicit decision — budget for that rather than being surprised by it.

> **Shipped 18 Aug 2026 (`d345cb56`), and reality answered a third way.** The
> prescription above is preserved because the reasoning is sound and the
> conclusion was wrong in an instructive direction: it argued *up* the ladder,
> toward more prose, when the right move was *down*. What shipped is a new
> `SubtitleVariant.importingBatch(done:total:)` rendering **"3 of 4" and nothing
> else** — no verb, no ETA — because the download phase needs no verb at all and
> a count is the whole question a closed window leaves: not how fast, not which
> file, but how many are still to wait for. And the **copy ring is reused as-is**
> rather than extended, because `Kind.ring` already means "a determinate,
> cancellable transfer into this project" and a download is exactly that; hover
> still gives the cancel, now wired to `stopFetch`.
>
> Two invariants that came with it and are checkable: progress counts rows that
> have **settled**, whatever the outcome, since a ring stalled at 3 because the
> fourth failed is a ring saying nothing; and `batch = nil` is generation-guarded
> (`CloudImportStore.swift:683`) so a superseded batch cannot blank its
> replacement's indicator. The `isDiagnostic` warning above was accurate — the
> new case did force the explicit decision it predicted.

**Microsoft owns the sign-in vocabulary — look it up, don't write it.** Their branding guidelines permit exactly two strings on the button: **"Sign in with Microsoft"**, or **"Sign in"** if space is tight. "Sign in *to* Microsoft" is not a variant. The Microsoft logo is required beside it, unaltered, and ships as official light/dark SVG and PNG assets to download rather than redraw. The account noun is **"work or school account"** — mandatory alongside the button so users recognise whether it applies to them — and "enterprise account", "business account" and "corporate account" are explicitly forbidden, as are *Azure* and *Active Directory* anywhere an end user can see them (fine in this doc and with IT admins). Once signed in, prefer the organisation's own name over a generic. Two consequences worth carrying: their guidelines **require a way to sign out and switch account** ("people are often associated with more than one organization"), which independently confirms §7's `(platform, account)` keying — today's single-slot storage would let a second client tenant silently overwrite the first. And Microsoft publishes a **Terminology Search and a UI String Search** so localised apps match their own products, which is the same trick as the `TCC.loctable` lift for the macOS prompt: the 20 translations of this button are *looked up*, not machine-translated.

_Extended by §9a (16 Aug 2026), which adds Google and Zoom, separates the
sign-in button from product-icon use, and records that neither product icon may
be used at all. This paragraph is verified and unchanged._

**The surface is a window, not a sheet.** Image Capture is the system analogue and it is a window; Photos import is a view. Mechanically a sheet cannot work here: it is window-modal, so keeping it up hides the sidebar-row progress behind a modal, and dismissing it destroys the per-row outcomes §6's recovery depends on. **Do not model it on `NewFilesSheet`** — that file carries its own retirement notice and is the codebase's worked example of a data view wrongly living in native chrome.

**Checkboxes carry the intent; there is no multi-selection.** Image Capture and Photos use selection alone, but those are *transient* — pick and immediately import. This list has durable per-row state (§6) and a filter step, and under selection semantics a tick made under one filter, then revisited under another, is fragile and invisible. So: checkboxes are intent, one focus row for keyboard navigation, and the button names the tick count (`Import 4 Recordings`). One model, no ambiguity, and no heavy blue over rows that already carry state.

**Shift-click a checkbox to tick a range — the gesture that actually pays.** Sorted by date, a study's sessions are adjacent, so tick Monday's and shift-click Wednesday's. Also owed: `space` toggles the focused row, arrows move focus, type-select jumps by title (`SessionsPopoverSpec.typeSelectString` exists — note type-select and the filter field compete for the keyboard, and the system apps resolve it by focus), Return commits, double-click fetches one row, column-header sorting, and a row context menu carrying the rare *Import Again*. The whole task must complete without a mouse. **Edit ▸ Select All exists but is not promoted**: the list is *recordings you organised*, mixing research calls with workshops and readouts, so ticking the whole window is close to always wrong. It is coherent only post-filter — narrow enough to be a menu item honouring the convention rather than a button.

**Display order is the user's; fetch order is expiry's.** Default the *list* to most-recent-first — the doc's own "last week's meetings" framing is what the researcher opened it for, and an 88-day-old call above yesterday's interview is wrong. Make expiry a sortable column plus an "expiring soon" filter, and earn the red: a countdown on every row is a wall of countdowns, so only rows inside the danger window get warning colour. But **execute** the batch soonest-expiring-first regardless of display sort, or an interrupted batch loses exactly the files closest to the recycle bin. Select-all operates on the **filtered** set, not the window.

**Bound the concurrency at 3–4** (the project's existing `asyncio.Semaphore` figure). The benefit is resilience — one stalled file doesn't block the batch — not throughput; a single 1.3 GB transfer already saturates a modest uplink.

**Check free space before a byte moves.** A 6–20 GB batch is the paradigm case for the "free-space precheck; legible `ENOSPC`" that `design-project-storage.md` already decided YES. **Wired 15 Aug 2026** — `CloudDownloader` runs the check before a byte moves, reusing `CopyMachinery.availableBytes()`, and refuses with a named `insufficientSpace` rather than a generic failure. The two pre-existing halves it draws on: `CopyMachinery.availableBytes()`/`insufficientDiskSpace` gates local drag-drop, and `doctor.check_disk_space()` runs only under `bristlenose doctor` — the pipeline run still has no precheck of its own. All three carry file size in the listing, so this is free — and worse than the local case if skipped, since a network fetch hitting `ENOSPC` mid-batch has burned real transfer time.

**Read `expirationDateTime` off each file** rather than choosing a window. Microsoft's expiry-warning emails are now a per-tenant setting, so researchers can no longer rely on being told. On expiry the file goes to the recycle bin, not a hard delete, so there is a grace period. Re-resolve the download URL immediately before each fetch, not at list time — they are short-lived by design, and a 404 on a soon-expiring item deserves its own message rather than a generic failure.

**Default window 30 days**, ceiling wherever the oldest surviving file sits. ~95% of what you want is recent. Going further back is a *different intent*: an explicit search with a term and a range, not a longer scroll.

**Persist only the attendees the researcher promotes to participants.** The attendee list also contains the client PM, the note-taker and the stakeholder observer — never recruited, never consented, not research subjects. Present the list, persist the promoted ones, discard the rest without writing them to disk. This is the correctness fix and the privacy fix being the same fix, again — and it costs nothing, because the selection UI is already there.

**Check whether the promotion step already has a home before drawing one.** _Added 15 Aug 2026._ The "who is p1?" step is the piece carrying the actual payoff — where emails finally earn their place and the manual spreadsheet dies — and it is still undrawn. But there is a decent chance this is *feeding candidates into UI that already exists* rather than a new surface: read [docs/design-speaker-editing.md](design-speaker-editing.md) and [docs/design-transcript-speaker-editing-roadmap.md](design-transcript-speaker-editing-roadmap.md) first. Related and easy to get wrong: **"you" is the organiser, not necessarily the moderator** — a colleague can run a call the researcher booked — so the promotion step must not auto-assign the signed-in user as moderator.

**Roster names are provisional until something links them to a speaker.** `people.auto_populate_names` only fills empty fields and never overwrites, so the first name written **wins permanently** — a roster-derived name is not corrected by a later LLM pass, a re-run, or re-analysis, and it reads as *more* authoritative than the guess it replaced because it came from the org directory. Land roster names in a candidate field, and make the mapping an explicit researcher act ("who is p1?") against the attendee list — which is also the cheapest v1 and is precisely the manual spreadsheet step §1 wants gone.

**Participant contact details are a re-identification key.** If email is captured at all it belongs in the class BN already has — `.bristlenose/`, `0o600`, `O_NOFOLLOW`, named in `SECURITY.md` beside `pii_summary.txt` and `llm-calls.jsonl`, never in any export or support bundle. The default implementation path does the opposite: a field on `PersonEditable` flows to `Person` → `GET /people` → `EMBED_PATH_TEMPLATES` → embedded in every exported HTML, past an `_anonymise_data` that clears only `full_name`/`short_name`. That is an anonymised report with participant contact details in it. If any part reaches `/people`, extend `_anonymise_data` in the same commit with a regression test asserting no `@` survives.

**Every remote-sourced string is untrusted.** §4 says the researcher is often not the organiser, so a third party controls meeting titles and attendee display names. `safe_filename()` for anything becoming a path component — the intuitive "keep the remote name" implementation skips it — and `wrap_untrusted()` for anything reaching a prompt, noting `tests/test_prompt_boundary.py` enforces only the variables already enumerated.

**Download URLs are credentials.** Graph's `@microsoft.graph.downloadUrl` is pre-authenticated and Zoom's is commonly used with `?access_token=`; `httpx` and friends log full URLs at INFO, and BN's log file defaults to INFO inside the project folder a researcher may hand to a client. No OAuth-bearing URL is ever passed to a logging call. The Swift redactor covers only Anthropic/OpenAI/Google-API key shapes today — Microsoft, Google and Zoom token shapes need adding before this ships.

**The calendar is the index; the storage API is the fetch.** Graph cannot filter events by attendee, so pull `calendarView` over a range and filter client-side. Better anyway: sub-millisecond type-ahead with no round-trip per keystroke. Keep the index in memory and let it die with the window, and `$select` only the fields the list needs so bodies are never fetched in the first place (§3 — this is the compensating control for taking `Calendars.Read`).

**The roster is `attendees[].emailAddress.{name, address}`, plus `type` and response status.** Two limits to design for rather than paper over: *invited ≠ attended*, and an external participant not in the org directory may come back as a bare address or whatever the organiser typed — which matters, because UR participants are usually external. Actual-attendance data (`attendanceReports`) is a separate artifact permission behind admin consent; not worth chasing. **Response status is worth using**, though: a declined invitee is strong evidence they were not in the recording, so dropping them is an accuracy improvement, not just a space saving.

**The attendee line is one line, always, and degrades in a fixed order.** A realistic session is a moderator, two observers and three participants with names that do not fit; wrapping gives variable row heights and destroys scanning, and silent truncation loses the count. Geometry is fixed, content bends. The ladder follows from what the line is *for* — identifying which call this is, which means the **participant**, never the moderator (always the researcher) and rarely the observers (often the same client faces weekly). So: drop yourself; drop anyone who declined; order by *externality* — an attendee whose email domain differs from the researcher's is probably the participant, colleagues are probably observers, so the useful name survives truncation — then a **count rather than an ellipsis** ("Sarah Chen · J. Whitfield +4" tells you there are six; a trailing "…" tells you nothing). Externality is an ordering hint, not a claim; when it is wrong the only cost is seeing a different name first.

**"You" is known, from `/me`** — the token is scoped to the signed-in account, and since v1 lists only meetings the researcher organised, the event's `organizer` is them by construction. One read supplies both the address to drop and the domain externality compares against. Two caveats: an alias can defeat a naive address match, which degrades harmlessly (you appear in your own attendee line) and does not justify alias resolution in v1; and **"you" is the organiser, not necessarily the moderator** — a colleague can run a call the researcher booked, so the promotion step must not auto-assign the signed-in user as moderator.

**Names in the list, emails never.** Emails are a re-identification key, and are also unscannable — a column of `firstname.lastname@clientco.com` is uniform noise carrying no recognition signal. They earn their place at the "who is p1?" promotion step, where telling two Sarahs apart genuinely needs one. Full attendee list on hover; the real disclosure, with roles and addresses, belongs to that promotion step.

**The researcher does not choose the platform — the client does.** So the relevant market share is client-organisation penetration weighted toward enterprise. No UR-specific tooling survey covers this: the obvious source (*State of User Research 2025*, n=485) does not ask about video conferencing at all, and the widely-quoted "Zoom mentioned 130+ times" is a vendor blog's gloss on free-text. Do not plan against it.

**This rhythm is what incremental analysis was built for** (shipped 0.20.0): import 3 → analyse → import 3 more → re-analyse with curation surviving. Destination is a picker ("New project…" plus the current project pre-selected), not a default — and `New Project…` should create with a provisional name and let the researcher rename in place in the sidebar, rather than stacking a naming dialog on the import window.

**Testing.** _Rewritten 15 Aug 2026: this paragraph named the wrong language. It proposed `httpx.MockTransport` in `tests/`, but §7 put the whole feature in Swift, so the Python fake-transport plan never applied._

What shipped: seven Swift test files — `CloudDownloadTests`, `GoogleMeetImportTests`, `ZoomImportTests`, `TeamsSourceTests`, `CloudImportModelTests`, `OAuthPKCETests`, `TeamsRecordingNameTests` — covering the pure-value layer, which is where the classification decisions live. Three of them caught real defects in the commits that introduced them, which is the argument for writing them at that layer.

**The transport layer is now tested** (`CloudTransportTests.swift`, 15 Aug 2026). A `URLProtocol` stub answers from a queue and — the part that matters — **records the requests**, because the whole of `CloudTransferPolicy` is a claim about which headers survive a redirect, and that claim is unfalsifiable without seeing the second request. Eleven tests drive the real `CloudDownloader` and the real adapters over a fake network:

- Zoom's `Authorization` is dropped across a cross-host CDN redirect; Teams sends none at all; a same-host redirect still lands.
- An HTML page with a 200, a truncated body, and a hash mismatch each leave **nothing on disk** — no `.mp4` and no orphan `.part`. The happy path leaves exactly one file under its final name.
- An unlicensed 401 requests no URL twice — the retry loop the classifier exists to prevent.
- An endless `@odata.nextLink` reports `pageCapHit`, never `exhausted`.
- A 90-day Zoom window issues **three** requests, each carrying explicit `from`/`to` — omitting them makes Zoom answer for today only, which reads as an empty account.

Two things this cost, both worth recording. The adapters gained a `restoredTokens:` initialiser parameter — not a test hook but the Keychain-restore seam §2 already owed, since an adapter must be constructible already-authenticated. And an early draft of these tests **passed for the wrong reason**: with no token injected, the adapters' guard short-circuited before the network, so assertions about request counts were satisfied by zero requests. A test that cannot fail on the bug it names is worse than no test, and it took injecting a token to make them honest.

_Inventory refreshed 18 Aug 2026._ Five files have joined since this paragraph
was written: `GrantLifecycleTests.swift` (three tests through the adapter's real
entry point over the stubbed transport, verified honest by reverting
`renewedTokenIfNeeded` and watching them fail), `CloudAccountKeyTests.swift`,
`CloudDisconnectTests.swift`, `CloudImportScheduledColumnTests.swift` and
`TeamsSignInFailureTests.swift`. See §7's lifecycle subsection for the two
constraints they imposed.

**And one thing no test caught, because nothing runs it.** `c837f8b5` records
that `main` did not build the Mac app: `CloudPlatform.swift:52` read a flag from
a file that was never committed. ~~**CI does not compile the Swift target at
all**, so a green suite says nothing about whether the desktop app builds~~ — it
was found only by building in a throwaway worktree at HEAD. Worth knowing before
trusting a green run on anything desktop-shaped.

> **Corrected 21 Aug 2026 — the gate exists, and the true statement is
> narrower.** `.github/workflows/mac-build.yml` has run
> `xcodebuild build -scheme Bristlenose` on push and PR to `main` since 20 May
> 2026; it is active and its last three runs are green. So a *pytest* run says
> nothing about the desktop build, but CI as a whole does compile it. Two real
> caveats survive and are the reason the episode still happened: the workflow is
> **path-filtered to `desktop/**`**, so a commit that breaks the app from
> outside that tree is not built; and it **runs no tests**, only a build. The
> claim as written would send a reader to add a gate that has been there for
> three months.

The live `ASWebAuthenticationSession` round trip against a real tenant categorically is not unit-testable; the internal TF cohort covers what CI cannot. Cloud import is a new **ingest** surface — network-sourced, unlike the 16 file-shaped ones — and its section in `docs/testing/coverage-inventory.md` was owed *before* the build and is now owed *after* it.

---

## 9a. Vendor branding — three surfaces, three rule sets

> **Partially trued, 18 Aug 2026 — two as-built claims corrected below, the rest
> of this section is NOT trued and wants its own pass.** It carries a fresh
> 16 Aug header and was skipped by the 18 Aug pass whose commit says "true §7,
> §9 and §10 against the pane that shipped" — so both the front-matter and that
> commit message imply this section is current, and it was not. Known remaining:
> line anchors have drifted (`CloudPlatform.swift#L104` now lands on
> `mandatesAccountNoun`; `CloudImportWindow.swift#L571` → `VendorMark` moved to
> `:746`), and Order-of-work item 1 is genuinely still open
> (`CloudPlatform.swift:12` "Zoom has its own" is uncorrected). Folding a full
> §9a pass into a §7/§9/§10 sweep is precisely what missed it the first time.

_Written 16 Aug 2026, from the vendors' own current guidelines. Extends §9's
"Microsoft owns the sign-in vocabulary" paragraph, which is verified and stands;
this section adds the two platforms it never covered and the two surfaces it
never separated. Nothing here is implemented — it is a brief._

**The mistake this section exists to prevent is treating brand as one problem.**
It is three, and they are governed by three different instruments:

| Surface | Instrument | Answer |
| --- | --- | --- |
| The **sign-in button** | The vendor's identity-branding programme | Required, specified, granted |
| The product **name** in menus, titles, prose | Nominative (referential) trademark use | Permitted, with naming rules |
| The product **icon** in menus and rows | A trademark licence | **Forbidden without an express grant — all three** |

That third row is the finding. The instinct is to put a Teams glyph beside
`Microsoft Teams…` in `File ▸ Import`, and all three vendors independently
prohibit exactly that. Microsoft: *"our logos, app and product icons… can never
be used without an express license."* Google: product icons require a Partner
Marketing Hub account and per-use approval. Zoom: the Zoom Marks licence in the
Marketplace ToS reaches **SDK Apps only**, and this is a REST/OAuth app, so it
confers nothing at all.

So `CloudPlatform.symbolName` currently documents itself as *"a placeholder in
every case… each vendor requires its own unaltered mark"*
([CloudPlatform.swift:104](../desktop/Bristlenose/Bristlenose/CloudPlatform.swift#L104)).
**That is backwards.** The generic SF Symbols there are not a placeholder
awaiting a real asset — they are the only lawful answer, and the comment should
be inverted from an apology into a decision.

### The rule

**The vendor's mark appears exactly once per flow — at the authorisation moment
— and nowhere else.**

That is where the mark is required, where it does real work (recognition: *"that
is the account I have"*), and where an explicit permission grant covers it.
Everywhere else the *name* already carries the meaning and the mark adds only
licence exposure. It is also the native answer: Apple's own Internet Accounts
shows vendor marks in the account-add picker and plain text everywhere after.

One rule settles all three surfaces — **button: the official asset, unaltered;
menus and titles: the name and a generic glyph; product icons: never.**

### What shipped, and why it isn't a bug

The mockup's Microsoft four-square was never dropped by accident. It is a
hand-drawn stand-in that says so in its own note
([cloud-import-states.html:240](mockups/cloud-import-states.html)), and
`VendorMark` carries the same honesty forward, rendering `m.square` / `g.circle`
/ `z.square` with a comment arguing that an obvious placeholder is easier to
notice and remove than an almost-right imitation
([CloudImportWindow.swift:571](../desktop/Bristlenose/Bristlenose/CloudImportWindow.swift#L571)).
That reasoning was right and should be preserved in the commit that replaces it.
The debt is unpaid, not unrecorded.

(For the avoidance of a recurring mix-up: the mark on the sign-in button is the
**Microsoft** logo — four coloured squares. The Windows flag is a different mark
denoting the OS, and would be wrong here.)

### Surface 1 — the button, per vendor

**Microsoft.** The strings are already correct: `signInTitle` returns one of the
two permitted forms and `accountNoun` returns "work or school account" with the
three forbidden synonyms avoided. Owed: the real asset. Microsoft ships the
standalone logo (`ms-symbollockup_mssymbol_19.svg`) *and* four full-button
lockups (light/dark × long/short). Take the standalone — see "the lockup trap"
below. Also owed, and this one is a missing **feature** rather than a wrong
pixel: *"DO provide a way for users to sign out and switch to another user
account."* ~~There is no Settings ▸ Accounts pane.~~ **Shipped — corrected
18 Aug 2026.** Settings ▸ Accounts exists (`d3b66642`), lists every connected
service with a Disconnect whose confirmation states plainly that it is *not*
revocation at the provider, survives a revoked credential rather than making the
row vanish (`a27f85b4`), and keeps one Keychain item per account (`8901845f`).
[CloudImportSource.swift:55](../desktop/Bristlenose/Bristlenose/CloudImportSource.swift#L55)
cites §9's "one place to disconnect, not two" — **the place now exists**, and §9
at the Accounts-pane subsection has said so since the fourth pass. That this
paragraph and that one disagreed inside a single file is the tell this section
was never read during it.
This is the same requirement §7's `(platform, account)` keying arrives at from
the other direction, so it is one piece of work, not two.

**Google.** Stricter than the code assumes, and one rule we break elsewhere
today: **monochrome versions of the G are explicitly forbidden**, as is changing
its size or colour. It must be the standard colour-gradient mark. Permitted
strings are "Sign in with Google" / "Sign up with Google" / "Continue with
Google" — ours is fine. Custom buttons **are** permitted, and the enforced spec
is: fills `#FFFFFF` (light) / `#131314` (dark) / `#F2F2F2` (neutral); strokes
`#747775` / `#8E918F` / none; text `#1F1F1F` / `#E3E3E3` / `#1F1F1F`; Google Sans
Medium 14/20; iOS padding 16 before the logo, 12 after it, 16 after the text.

**Zoom.** This doc's own `CloudPlatform` comment asserts *"Zoom has its own"*
branding spec ([CloudPlatform.swift:12](../desktop/Bristlenose/Bristlenose/CloudPlatform.swift#L12)).
**It does not.** No published "Sign in with Zoom" button specification could be
found, and the trademark position is worse than absent: the Marks licence covers
SDK Apps, all other uses require Zoom's prior written agreement, and everything
must comply with a Brand Guidelines and Partner Guide obtained from
`brand@zoom.us`. Today's exposure is nil — the menu item is withheld behind
`BristlenoseFlags.cloudImportZoom` — but the claim should be corrected before
anyone builds on it. **Do not build a Zoom sign-in button on the assumption that
a spec exists to comply with.** Either ask Zoom in writing or ship a
vendor-neutral button with the name in text.

### The lockup trap

Both Microsoft and Google ship whole-button *images*. Do not use them. They are
web and Android artefacts: they cannot be localised into 21 languages, they do
not respond to Increase Contrast or Reduce Transparency, they carry no VoiceOver
text, and a bitmap button is not a Mac control. Build the button natively and
place the **standalone mark** inside it — structurally what
`CloudImportWindow.signedOutView` already does, with a real asset instead of an
SF Symbol.

Microsoft's binding rules are *don't alter the logo*, *use one of two strings*,
*name the account type*; a native button with the unaltered SVG satisfies all
three, and their redlines are framed as *recommended*. Google explicitly permits
custom buttons, so honour the three things they enforce — full-colour G at the
sanctioned size, a permitted string, a permitted fill — and **deviate on typeface
only**, SF instead of Google Sans. That is one written deviation in the house
form ("the system primitive is X; we depart because Z"), and typography is the
one axis where platform convention should win.

### Two mechanical safeguards

**Rendering intent is a live trap, not a hypothetical.** An asset-catalog
imageset set to `template` renders as a monochrome tint. That would silently
convert the full-colour Google G into precisely the forbidden monochrome mark —
a compliance failure delivered by an Xcode default rather than any design
decision, and invisible in code review. Every vendor imageset pins
`"template-rendering-intent": "original"` explicitly.

**A `desktop/scripts/check-vendor-marks.sh` gate**, alongside
`check-appearance-seam.sh` and `check-mcpb.sh`, asserting the SHA-256 of each
mark still matches the downloaded original and that rendering intent has not
drifted — plus a `PROVENANCE.md` recording source URL, download date, hash and
licence basis per asset. The failure this prevents is specific and likely: a
future tidying pass recolours the marks to match the palette, or makes them
monochrome "for dark mode", and creates a violation while believing it is
housekeeping.

### Localisation

Both vendors mandate localised button text, and both publish official
translations — Microsoft's Terminology Search and UI String Search, and Google's
encouragement to localise. ~~The window is hardcoded English throughout (§10
already books this as realised debt): there are no `desktop.cloudImport.*` keys
at all.~~ **False since 16 Aug 2026 (`49ec8a50`) — corrected 18 Aug.** There are
**120** `desktop.cloudImport.*` keys in `bristlenose/locales/en/desktop.json`,
seeded across all 21 full locales (`ja`/`ko`/`zh-Hant` correctly omit the 16
`_one` plural forms; `zh-Hant-HK` correctly inherits), reached from 36
`i18n.t("desktop.cloudImport…")` call sites in `CloudImportWindow.swift`. Note
the date: the keys landed *before* the pass that left this claim standing.
**Still genuinely owed:** the two vendor-mandated button strings, which is the
part the paragraph below is actually about.
For the two vendor-mandated strings specifically, **look the translations up
rather than machine-translating them** — the same move as the `TCC.loctable` lift
for the macOS permission prompt, where recognition is the whole mechanism.
Settle the English first, per the house order.

### What is not verified

Microsoft's redlines live in a PNG diagram that could not be machine-read. The
`41px` height, `Segoe UI 15`, and `#8c8c8c` border in the mockup's `.msbtn` CSS
came from whoever wrote the mockup, not from the guidelines directly — measure
from the downloaded asset before building. Google's published spec gave fills,
strokes, typography and padding but no explicit button height.

### Adjacent, and already shipping

The same decision, one surface over, and live today rather than pending:
`Assets.xcassets/provider-google.imageset` is a flat-black Gemini spark — a
monochrome Google mark, the explicitly forbidden case — and
`provider-azure.imageset` is the Azure logo redrawn, against Microsoft's
"never without an express license". Both render in Settings ▸ LLM Provider and
on the welcome screen. Out of this feature's scope, same fix, and it ships now
whereas this one does not.

### Order of work

1. Correct the two false claims in code — `symbolName`'s comment and
   `CloudPlatform`'s "Zoom has its own". Costs nothing, prevents building on sand.
2. Download Microsoft's and Google's official marks; add provenance, pin
   rendering intent, add the gate.
3. Replace `VendorMark` for Teams and Meet. Leave Zoom on the neutral glyph.
4. Settle the English strings, then look up the vendor-mandated translations.
5. Settings ▸ Accounts (sign out / switch account) — the only Microsoft
   requirement that is a missing feature, and shared with §7's account keying.

**Sources.** Microsoft: *Sign in with Microsoft branding guidelines*
(`learn.microsoft.com/entra/identity-platform/howto-add-branding-in-apps`) and
the Microsoft Trademark and Brand Guidelines. Google: *Sign in with Google
Branding Guidelines* (`developers.google.com/identity/branding-guidelines`) and
the Partner Marketing Hub brand guidance. Zoom: the App Marketplace Terms of
Service (Zoom Marks clause) and `brand.zoom.com`.

---

## 10. Costs to be honest about

- One OAuth app registration before any third party has to say yes; three by the end. ~~**None of the three exists yet**~~ — **two of three now exist** (Entra 15 Aug, Google Cloud 18 Aug `2cb58cf6`); Zoom's is unstarted and parked. **The gate moved rather than closing.** Registration is no longer what stands between us and a third party saying yes — *verification* is, and it is a different, slower animal on each platform:
  - **Microsoft Publisher Verification** — free, and "verified in minutes" once the business-identity check clears; that check is the slow part. It gates consent from tenants other than our own, so Teams import is not broken today, it is un-shippable to anyone else.
  - **Google sensitive-scope verification** — also free (no assessment, no assessor, no fee) but **weeks** of review, justification and a demo video, because the listing needs `calendar.events.readonly` and the Meet conference-records scope and both are sensitive (`5cf82309`).

  So they are one item to start, not two — and **Google sets the date**, being the longer pole by an order of magnitude. Neither is started.
- **Microsoft Publisher Verification is a prerequisite** (§3) — a Partner Center account and a verified domain, not just a form. **One precondition worth checking before starting rather than after:** Microsoft's own requirements say apps registered *using a Microsoft account* cannot be publisher-verified. If our Entra registration was made with an MSA rather than a work account in the tenant, it must be re-registered with a **new client ID** — free today, since no client ID is baked into anything in `desktop/`, and expensive the moment a cohort tester holds a stored grant.
- Three APIs that will change underneath us.
- ~~**i18n — now realised debt, not a future cost.** The shipped window is hardcoded English throughout.~~ **Paid, 16 Aug 2026 (`49ec8a50`)** — 120 `desktop.cloudImport.*` keys across the 21 full locale directories, CLDR plurals on the count-bearing strings, `zh-Hant-HK` inheriting rather than pinned. Two vendor-mandated button strings remain, and §9a says to look those up rather than machine-translate them. _**Reopened and closed the same day, 18 Aug 2026.** Settings ▸ Accounts shipped hardcoded English throughout — 20 strings plus the pane title, the only one of six Settings tabs not reading `i18n.t` — and was paid by `d0478b15`: 21 `desktop.accounts.*` keys across all 21 full locales. [i18n-defects.md](i18n-defects.md) rows 1–2 struck._

**The warning below fired in 48 hours, and the recurrence was worse than the warning.** As written it said `check-locales.py` only warns, so a skipped run ships the gap silently — which implies `--strict` is the fix. **For this class it is not.** The script flattens `en` and diffs each locale *against* it, so a surface never enrolled in English has nothing to be reported missing **from**: the Accounts pane was invisible by construction, and `--strict` would have run green. Two distinct holes and only one is closable by a flag — `CLAUDE.md:230-231` now carries both. Compounding it, ~~**CI does not compile the Swift target at all** (§9)~~ — **corrected 21 Aug 2026: it does** (`mac-build.yml`, since 20 May), but it only *builds*, and a build cannot notice that a view has no `i18n.t` call sites — so no gate of any kind was ever going to read that pane, which is the point that survives intact. The rule that replaced the warning is therefore not a stronger script but a habit: **a new user-facing view is read for `i18n.t` call sites at the point it lands**, because afterwards nothing mechanical asks again.
- **A corporate tenant credential in the Keychain is a different class from a personal LLM key.** The iCloud-sync decision for API keys is settled and disclosed and is not reopened here; the question this raised was whether a *client's* IT policy permits their tenant credential to leave the managed device. ~~Non-synchronizable is the answer for this one (§7).~~ **Answered the other way, 18 Aug 2026: cloud grants sync, like every other secret this app holds.** iCloud Keychain is end-to-end encrypted regardless of ADP, so the exposure is not to Apple; and the credential is a scoped, revocable grant to download recordings from an account the researcher is signed into on those same devices anyway. Weighed against a stolen Mac with no recovery path, the sync is the safer default. The governance question is real but belongs in disclosure, not in storage — see the consent line below. Reasoning in full at §7.
- **The destination is often itself a cloud folder.** On a Mac, project folders frequently live under `~/Library/CloudStorage/`, so the feature's default behaviour is to pull media out of the client's tenant and write it into whatever cloud that folder syncs to — a second vendor, unasked, and per `design-project-storage.md` plausibly outside the team's governance boundary. Detect with `cloud_provider_for(destination)` and disclose before the fetch. Secondary effects: the reverse sync competes for the same uplink, and the provider may later evict the file, so the retention clock runs against bytes BN cannot read without coordination.
- ~~No disconnect, revoke or multi-account story exists yet (§7, §9).~~ **Two of the three now exist** (18 Aug 2026). Disconnect shipped in Settings ▸ Accounts, and it reaches an open import window rather than only the Keychain — removing the stored copy while a live adapter holds tokens in memory would leave a control that appears to work and does not. Multi-account *storage* shipped; multi-account *choosing* is deferred by decision, because nothing yet offers a way to connect a second account. **Revocation is still the gap, and the honest sentence is that Bristlenose cannot do it**: the disconnect confirmation says so in as many words and points the researcher at their account settings. An Entra admin can revoke tenant-wide from Enterprise Applications — worth stating, because it is a strong answer.
- A researcher's employer may take a view on a personally-purchased tool authenticating to corporate M365, even at `Files.Read` on their own drive. This is the scenario enterprise consent machinery exists to govern, which is a better answer than most SaaS can give.
- ✅ **~~Consent is owed now~~ — RESOLVED 22 Aug 2026, and the AIConsentView half was wrong.** Cloud import is **ingress**: it downloads the researcher's own recordings from their own account onto their own Mac. It transmits nothing. §5.1.2(i)'s "obtain explicit permission before sharing personal data with third parties, including third-party AI" governs data going *out*, which is precisely what `AIConsentView` covers — transcript text to Claude/ChatGPT/Azure/Gemini. **The two surfaces answer different questions and must not be merged.** The vendor-name overlap is coincidental: the Gemini *API key* and the Google Meet *OAuth client* are different consoles, different credentials, different flows. Where a researcher gets their recordings from is their business, and the consent they give is on Microsoft's or Google's own screen, listing scopes in the vendor's words. Nor is the dialog's *"Raw audio and video recordings — always stays on your device"* falsified: import's whole job is to put recordings **on** the device, and nothing uploads them. **So `AIConsentView.currentVersion` stays at 2 and no per-connection consent dialog is owed.** What §5.1.1 *does* require — disclosure of the third-party data source and what happens to the data after — is the privacy policy's job, and it shipped 22 Aug at `https://bristlenose.app/privacy.html` (canonical; all three consoles point there). §4.8 does not apply either: its "client for a specific third-party service" exception covers us twice over, since Bristlenose has no account system at all. Checked against the published App Store Review Guidelines, not recalled; encoded in `.claude/agents/app-store-police.md` §4.8 and §5.1.1/5.1.2. _Original entry, retained because its urgency was right about the website and wrong about the dialog:_
- ⚠️ **Consent is owed now, not "when this ships".** The feature has shipped behind `File ▸ Import` with three live adapters while `AIConsentView.currentVersion` is still 2. The v2 dialog's stays-local box becomes false by omission, and a per-connection disclosure listing the scopes in plain English belongs at the OAuth moment. **The escape clause this paragraph used to carry is gone.** It read "the practical urgency is gated by the registration gap — no sign-in can complete until a client ID exists, so nothing has leaked". A client ID exists as of 15 Aug 2026, and a live Graph session has read a real corporate calendar and a real OneDrive. Fix both before the first cohort tester touches it — and note the consent screen the researcher actually sees says "unverified" and "the publisher has not provided links to their terms", which is our own disclosure gap showing through Microsoft's UI.

---

## 11. Related

- **`docs/design-project-storage.md`** — what happens to media once BN has it; the other half of this pair
- The review log for this doc lives with the maintainer's private review notes, kept outside the public tree. **Correction, 18 Aug 2026:** this line used to say it held "32 findings from the 14 Aug six-agent pass". It does not, and they are not recoverable — the log's own pass index now records the gap and the five findings rescued from a handoff. The 18 Aug pass is in there in full.
- `docs/methodology/consent-gradient.md` — the governance model provenance and retention sit inside
- `docs/design-pipeline-diagnostic-popover.md` — read before adding any new error/status message
- `docs/design-keychain.md` · `docs/design-modularity.md` · `docs/testing/coverage-inventory.md`
- `SECURITY.md` — the stage-5b pre-redaction disclosure the roster constrains but does not remove
