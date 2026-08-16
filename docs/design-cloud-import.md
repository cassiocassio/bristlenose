---
status: partial
last-trued: 2026-08-16 (third pass, post-Google-tenant)
trued-against: HEAD@main on 2026-08-16 (ffdd0eef)
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
> **Still pre-contact:** nothing has completed a **download** on any platform.
> Treat every claim about the transfer path as untested — the three claims about
> the *listing* path that met reality this week were all wrong.

## Changelog

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

**Status: designed 28 Jul 2026. Revised 14 Aug 2026 after a permissions/benchmark pass and a six-agent review. Revised again 15 Aug 2026, when Google, Zoom and Teams were researched and all three adapters were built. Post-TF, not cohort-blocking.**

**What exists as of 15 Aug 2026.** All three platforms are live behind `File ▸ Import`, on one shared spine: `CloudImportSource` (the protocol), `CloudImportStore` (the state machine), `CloudImportWindow` (the surface), `CloudPlatform` (everything vendor-shaped the UI says), `CloudImportCoordinator` (which source the window holds), and `CloudDownloader` + `CloudDownloadVerification` (§6's "prove the bytes arrived", once, for all three). Per-platform adapters carry only what genuinely differs: the endpoints, the scope vocabulary, the error dialects, the OAuth ceremony, and each vendor's own way of failing quietly. A `FixtureCloudSource` drives every state from the Diagnostics menu without an account.

**What is not built — and the first item means nothing works yet.**

- **Teams is registered and signs in. Google and Zoom are not.** A Microsoft 365 Business Basic tenant (`bristlenose.onmicrosoft.com`, £6.48/mo, **monthly**) and an Entra app registration were created 15 Aug 2026 — multitenant + personal accounts, redirect `msauth.app.bristlenose://auth` as a public client, public client flows on, delegated `Files.Read` / `Calendars.Read` / `offline_access` / `User.Read`. The client ID lives in the app's sandboxed `UserDefaults`, **not in this repo**. Google's and Zoom's configs still read a client ID and return `nil`, so neither can sign in.
  - **A Google tenant now exists, and it is not the same thing as a Google registration.** _16 Aug 2026._ A Workspace **Business Standard** tenant was bought on a throwaway domain (Flexible/monthly, ~£11.80/user; the domain was taken at signup rather than pointed at `bristlenose.app`, whose MX carries live mail). It has recorded a real Meet, which is what §3's and §6's Google findings are measured against. **No OAuth client is registered in any Google Cloud project**, so `GoogleMeetConfig` still returns `nil` and nothing can sign in. When one is created it belongs in a Cloud project owned by an account that outlives the tenant — the throwaway domain is a *data source*, not the app's identity, and an OAuth client registered inside it dies with it.
  - **`CFBundleURLTypes` turned out not to be required, and this doc said it was.** Teams signed in with no URL type registered in the target: `ASWebAuthenticationSession(url:callbackURLScheme:)` has the OS route the callback to the initiating session directly, never through LaunchServices — which is the security property §2 chose it for in the first place. **Zoom's `associated-domains` entitlement and a deployed `apple-app-site-association` file are still genuinely required**, because Zoom refuses custom schemes and its callback is HTTPS.
- **No token is persisted, and no refresh is wired.** §2 and §7 describe a Keychain refresh token keyed on `(platform, account)`; nothing writes to the Keychain, and `refresh` is never called. Access tokens last about an hour on all three, so even once registration lands, a long batch can 401 mid-flight and every launch will re-prompt.
- **No adapter derives local row state.** §6's `stat`-based six/seven-state model is implemented in `ImportRowState` and exercised only by `FixtureCloudSource`; all three live adapters hardcode `.notImported`.
- **Where the full list lives.** Done/undone in dependency order is kept in the `cloud-import-state-of-play` handoff, with the maintainer's private planning notes outside the public tree — so it is gitignored and a grep of a clean checkout will not find it. This status block is the public summary; that handoff is the working document.
- **Live acceptance — Teams has now met a real recording; nothing has been fetched.** On 15 Aug 2026 the shipped code signed in to a live tenant, listed `/Recordings` over Graph and rendered the window. It has still never completed a **download**, on any platform. Two parsers broke on first contact and are fixed (`8b8eafc9`) — see §6.
  Of the four open probes, one is answered and one is now known to be unanswerable by us:
  - ✅ **Is the transcript a sibling file in OneDrive?** **No** — see §3. §1, §3 and §5 stand unrevised.
  - 🔒 **Can a researcher self-consent in a real client tenant?** Still open, and **our own tenant can never answer it**: the owner is Global Administrator, so consent always succeeds and the org-wide consent checkbox only renders for admins. This needs a cohort member in a tenant we do not administer — see §5.
  - ⬜ Does the Google Picker surface a Meet recording? **Still untouched, but now cheap** — a Google tenant exists with a real recording in it (below). The sub-risk is *also* still open and needs a second body: the 16 Aug call was solo, so nothing has yet been observed about what an **attendee** sees in their own Drive after the July shortcut change. Invite a free `@gmail.com` to a recorded call and both questions close together.
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

Two Zoom token properties that are not Google's and must not be inherited by assumption. **Refresh tokens are single-use and rotate on every refresh**, with *no* documented grace window — an interrupted refresh (timeout after Zoom rotated, before we persisted) strands the user permanently, and re-authorising always shows the consent screen because public clients may not skip it (RFC 6819 §5.2.3.2). So the Keychain write must commit before the old token is discarded, and "reconnect" must be a graceful path rather than an error. And **Zoom appears to allow one live token per user per client ID**: authorising on a second Mac silently kills the first. A researcher with a laptop and a desktop cannot have both connected. That is a product constraint to state, not a bug to fix.

**Prefer a custom scheme over a loopback listener.** Both work under the sandbox (`ENABLE_INCOMING_NETWORK_CONNECTIONS` is already set), but a loopback listener is reachable by any same-UID process during the auth window, whereas `ASWebAuthenticationSession(url:callbackURLScheme:)` routes the callback to the initiating session only. Needs a `CFBundleURLTypes` entry the target does not yet have. Leave `prefersEphemeralWebBrowserSession` at `false` so an already-signed-in researcher gets one-click consent instead of a full MFA round trip.

**What is and isn't a from-scratch build.** The Swift consent sheet is new — `ASWebAuthenticationSession` appears nowhere in the tree. The **PKCE machinery is not**: `bristlenose/miro_client.py` already has `generate_pkce`, `build_authorize_url`, `exchange_code_for_tokens` and `refresh_access_token`, with a live authorization-code + loopback flow wired in `routes/miro.py`. That is the reference implementation for the token dance even though this feature's ceremony is Swift-side. **The read-back rule survives; the "before copying" framing does not.** _Trued 15 Aug 2026._ Nothing copies `miro_client.py` — all three ceremonies are hand-rolled in Swift — so the three platforms did not inherit the bug. But the bug itself is **still live and still shipping**: `bristlenose/server/routes/miro.py` reports "Connected to Miro ✓" on the path where the credential-store write failed, and unlike the sibling paste route it has no in-session fallback, so the token is genuinely lost. It is now simply a defect we own, unrelated to this feature. The rule it teaches is the load-bearing part and applies to all three adapters the moment they gain Keychain persistence: **a connect flow verifies by read-back — store, read back, *then* report connected.**

A server is only needed for **always-on watching** (poll the tenant while the app is closed). That is not this feature and should not become it.

---

## 3. Gates, per platform

Three artifacts, not one — and **they do not share a gate**. The 28 Jul version conflated them, which made Teams look worse and Google look better than they are.

| | List / index | Video | Roster | Transcript |
|---|---|---|---|---|
| **Teams** | `Calendars.Read` — no admin consent ✓verified. Or free: the title is in the recording filename (§6) | `Files.Read` — no admin consent ✓verified | `Calendars.Read` — no admin consent ✓verified | `OnlineMeetingTranscript.Read.All` — **admin consent required, even delegated** ✓verified |
| **Zoom** | `cloud_recording:read:list_user_recordings` — user-managed, no admin ✓verified. **Pro plan or higher** | same call returns `download_url`; **no download scope exists** — the same bearer authorises it ✓verified | **none ✓verified** — the list call carries no attendees at all; a roster needs a report endpoint behind an admin scope | **same call returns the VTT** ✓verified — speaker names as a `Name:` cue prefix, **English only, every plan** |
| **Meet** | `calendar.events.readonly` — sensitive ✓verified. **Business Standard or higher** ✓verified | `drive.file` + Picker — **non-sensitive** ✓verified. (`drive.meet.readonly` — restricted → CASA ✓verified, and refused) | `calendar.events.readonly` `attendees[]`, or `meetings.space.readonly` — sensitive ✓verified | **descoped from v1** ✓verified — not a file; a tab inside a Gemini Doc (below) |

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

> **Inverted 16 Aug 2026 by a live tenant, and the inversion is the useful part.** The paragraph below is correct about the **API** door and wrong about the platform. It reasoned from `conferenceRecords` alone and never asked what the *file* door serves — which turned out to be a tab inside a Gemini notes Doc (§3). Both doors were real; only one had been priced.

**And one artifact where Google is the strongest of the three, not the weakest.** Teams' transcript is admin-walled (§3) and Zoom's rides the same call as the video; Google's is a **first-class, per-utterance, speaker-attributed, timecoded API resource on a sensitive scope**. If §8's open question is ever settled in favour of the platform transcript, Google is where that pays off most — which is an argument for building it *before* the answer arrives rather than after, since it is the platform that would make the experiment worth running.

**What replaces it: for v1, Google is the weakest of the three, and deliberately so.** With the transcript descoped (§3), Google delivers video and roster where Teams delivers video, roster and a hand-downloadable `.vtt`, and Zoom delivers all three from one call. That is a scope decision rather than a platform limitation, and it is reversible: the API door is untouched and still the cheapest place to run §8's experiment, because it is the only one of the three that hands over per-utterance speaker attribution without an admin gate. The claim to retire is "Google is where the artifacts are best" as a reason to **sequence** it earlier. The claim to keep is "Google is where the transcript experiment is cheapest to run" as a reason to **return** to it once §8 has an answer.

---

## 6. Shape — the staircase

- **v1** — _as designed: Teams only, `Files.Read` + `Calendars.Read`. **What shipped 15 Aug 2026 is v1 across all three platforms**, because the research that repriced Google and Zoom arrived before the Teams build did._ List the researcher's own recordings, join to a calendar window for the roster where the platform has one. **Multi-select with per-row outcome.** Download into a destination project. ⚠️ Still owed at v1: `(platform, remoteID, account)` provenance per imported session, and the derived `stat`-based import state below — all three adapters currently hardcode `.notImported`.
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

**Key the credential on `(platform, account)`.** `KeychainHelper` is currently one service name per provider with a fixed account, so a freelancer's second client tenant would **silently overwrite** the first. Follow `MCPTokenStore`'s shape instead: own service name, account key hashed from a stable identifier (never the raw UPN — that is a client email address sitting readable as Keychain item metadata), and non-synchronizable.

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

**Where the user starts, and how they get back.** `File ▸ Import from Teams…` as a sibling to the existing `File ▸ Add Files… ⇧⌘A` (whose own comment calls it "the menu twin of drag-drop") — **flat while there is one platform, a submenu at three**: a one-item submenu is a Mac smell, so this becomes `File ▸ Import ▸ Microsoft Teams… / Zoom… / Google Meet…` when the second lands, and takes the fuller product name there for parallelism. Also a project context-menu twin following the Agent Access pattern (context menu *hides* when unavailable, menu-bar twin *dims*), and `Bristlenose ▸ Accounts…` mirroring `Connect an Agent…`. Account lifecycle — sign in, sign out, "Connected as…", the scope disclosure — belongs in a **Settings ▸ Accounts** pane on the Mail Accounts pattern the app already uses twice; the import surface shows a read-only account line only. One place to disconnect, not two.

**One window, globally, with the destination pre-selected by how you opened it.** Opening from a project's context menu pre-selects that project; opening from the File menu pre-selects the current one. Re-opening after a close is the **File** menu's job, not the Window menu's — HIG is explicit that the Window menu lists *currently open* windows (alphabetically) and that reopening belongs in File. Two consequences: the scene takes **`.commandsRemoved()`**, since a titled SwiftUI `Window` otherwise auto-contributes a Window-menu reopen entry that HIG says shouldn't be there — the project's existing rule for auxiliary windows, now with a second reason — while the window still appears in the open-windows list *while open*, because that listing is AppKit enumerating real `NSWindow`s rather than the scene contributing a command (verify on device). And note HIG's *"avoid listing panels or other modal views"* is a third independent argument for this being a window rather than a sheet. **Double-click on a project row is not available** as a door — `project_sidebar_rename_gestures_decided` already reserves it for opening the project itself.

**The fetch's progress belongs on the project's sidebar row, in the existing ring and subtitle.** Per-file state stays in the import window; the project's aggregate rides its row, so closing the window loses nothing. Prose stays minimal — the `RunProgressSubtitle` ladder (`stage · N of M · ETA`) is the vocabulary to extend, **not** `ProjectSubtitle.copying(fraction:)`, which carries a single 0–1 number with no item identity, count or ETA and therefore cannot say "Fetching 3 of 7 · 12 min left". Note `SubtitleVariant.isDiagnostic` is deliberately exhaustive with no `default`, so a new case forces an explicit decision — budget for that rather than being surprised by it.

**Microsoft owns the sign-in vocabulary — look it up, don't write it.** Their branding guidelines permit exactly two strings on the button: **"Sign in with Microsoft"**, or **"Sign in"** if space is tight. "Sign in *to* Microsoft" is not a variant. The Microsoft logo is required beside it, unaltered, and ships as official light/dark SVG and PNG assets to download rather than redraw. The account noun is **"work or school account"** — mandatory alongside the button so users recognise whether it applies to them — and "enterprise account", "business account" and "corporate account" are explicitly forbidden, as are *Azure* and *Active Directory* anywhere an end user can see them (fine in this doc and with IT admins). Once signed in, prefer the organisation's own name over a generic. Two consequences worth carrying: their guidelines **require a way to sign out and switch account** ("people are often associated with more than one organization"), which independently confirms §7's `(platform, account)` keying — today's single-slot storage would let a second client tenant silently overwrite the first. And Microsoft publishes a **Terminology Search and a UI String Search** so localised apps match their own products, which is the same trick as the `TCC.loctable` lift for the macOS prompt: the 20 translations of this button are *looked up*, not machine-translated.

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

The live `ASWebAuthenticationSession` round trip against a real tenant categorically is not unit-testable; the internal TF cohort covers what CI cannot. Cloud import is a new **ingest** surface — network-sourced, unlike the 16 file-shaped ones — and its section in `docs/testing/coverage-inventory.md` was owed *before* the build and is now owed *after* it.

---

## 10. Costs to be honest about

- One OAuth app registration before any third party has to say yes; three by the end. **None of the three exists yet** — see the status block; this is now the gate on everything else in this doc.
- **Microsoft Publisher Verification may be a prerequisite** (§3) — a Partner Center account and a verified domain, not just a form.
- Three APIs that will change underneath us.
- **i18n — now realised debt, not a future cost.** The shipped window is hardcoded English throughout ("Import 1 Recording", "Filter", the plan-refusal sentences). A window with this many states needs `desktop.*` keys across the **21** full locale directories (plus the `zh-Hant-HK` override fork), CLDR plurals on every count-bearing string, and `scripts/check-locales.py` only warns — nothing fails if it is skipped.
- **A corporate tenant credential in the Keychain is a different class from a personal LLM key.** The iCloud-sync decision for API keys is settled and disclosed and is not reopened here; the new question is whether a *client's* IT policy permits their tenant credential to leave the managed device. Non-synchronizable is the answer for this one (§7).
- **The destination is often itself a cloud folder.** On a Mac, project folders frequently live under `~/Library/CloudStorage/`, so the feature's default behaviour is to pull media out of the client's tenant and write it into whatever cloud that folder syncs to — a second vendor, unasked, and per `design-project-storage.md` plausibly outside the team's governance boundary. Detect with `cloud_provider_for(destination)` and disclose before the fetch. Secondary effects: the reverse sync competes for the same uplink, and the provider may later evict the file, so the retention clock runs against bytes BN cannot read without coordination.
- No disconnect, revoke or multi-account story exists yet (§7, §9). An Entra admin can revoke tenant-wide from Enterprise Applications — worth stating, because it is a strong answer.
- A researcher's employer may take a view on a personally-purchased tool authenticating to corporate M365, even at `Files.Read` on their own drive. This is the scenario enterprise consent machinery exists to govern, which is a better answer than most SaaS can give.
- ⚠️ **Consent is owed now, not "when this ships".** The feature has shipped behind `File ▸ Import` with three live adapters while `AIConsentView.currentVersion` is still 2. The v2 dialog's stays-local box becomes false by omission, and a per-connection disclosure listing the scopes in plain English belongs at the OAuth moment. **The escape clause this paragraph used to carry is gone.** It read "the practical urgency is gated by the registration gap — no sign-in can complete until a client ID exists, so nothing has leaked". A client ID exists as of 15 Aug 2026, and a live Graph session has read a real corporate calendar and a real OneDrive. Fix both before the first cohort tester touches it — and note the consent screen the researcher actually sees says "unverified" and "the publisher has not provided links to their terms", which is our own disclosure gap showing through Microsoft's UI.

---

## 11. Related

- **`docs/design-project-storage.md`** — what happens to media once BN has it; the other half of this pair
- The review log for this doc — 32 findings from the 14 Aug six-agent pass — lives with the maintainer's private review notes, kept outside the public tree
- `docs/methodology/consent-gradient.md` — the governance model provenance and retention sit inside
- `docs/design-pipeline-diagnostic-popover.md` — read before adding any new error/status message
- `docs/design-keychain.md` · `docs/design-modularity.md` · `docs/testing/coverage-inventory.md`
- `SECURITY.md` — the stage-5b pre-redaction disclosure the roster constrains but does not remove
