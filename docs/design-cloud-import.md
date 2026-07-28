# Cloud import — capturing originals from Teams, Zoom and Meet

**Status: designed 28 Jul 2026, nothing built. Post-TF, not cohort-blocking.**

Downloading recordings by hand, per file, is drudgery — and it is the thing Dovetail and Marvin remove by default. Bristlenose can too, and unlike them it needs no server.

**Scope note.** This doc is about *getting the bytes down*. What happens to media once Bristlenose has it — reading it when it's cloud-evicted, archiving, retention, why BN manages none of it — is **`docs/design-project-storage.md`**. The two meet at one point: import produces *captured originals*, and that is what the retention clock runs against.

---

## 1. Why, in priority order

1. **The video file.** Everything else is gravy. It is the irreplaceable asset and the annoying thing to obtain.
2. **Beat the expiry.** Teams recordings expire (120 days documented, commonly configured to 60); Zoom is org-set. A link can vanish at any moment, so BN must hold bytes, not pointers.
3. **Provenance.** Source, capture date, meeting, participants. This is what makes a retention lifecycle implementable at all — you cannot expire on a schedule without a start date.
4. **Roster.** Attendee names and emails from the invite. Could retire the pre-redaction speaker-ID LLM call (§6).
5. **Transcript and invite brief.** Gravy — see the caution in §6.

---

## 2. The mechanism — no server required

A *user-initiated* fetch is an OAuth **public client with PKCE**: `ASWebAuthenticationSession` opens a sign-in sheet, the redirect returns on loopback or a custom scheme, no client secret, refresh token into the Keychain. This is the shape already used for Miro.

A server is only needed for **always-on watching** (poll the tenant while the app is closed). That is not this feature and should not become it.

---

## 3. Gates, per platform

| | Search index | Fetch | Scopes | Gate |
|---|---|---|---|---|
| **Teams** | `/me/calendarView` — filter client-side; Graph cannot filter by attendee | `getAllRecordings`, or just list OneDrive `/Recordings` | `Files.Read` + `Calendars.Read` — delegated, own data | **None.** User-consentable; metering ended 25 Aug 2025 |
| **Zoom** | `/users/me/recordings` returns topic + date natively (1-month max range per call) | same call returns download URLs | `cloud_recording:read:list_user_recordings` | General app, submittable **Unlisted**; Zoom review |
| **Google Meet** | Calendar API `q=` searches attendee name and email server-side | Picker (`drive.file`) or Drive | `calendar.events.readonly` is **sensitive** | Verification: review + justification + demo video. Not CASA, no annual fee |

**Never reach for `Files.Read.All` or `Sites.Read.All`** — admin-consent-only since Aug 2025. That is the procurement gate the customer profile is defined by avoiding. It is the only thing standing between this feature and the team's SharePoint site, and the answer is to not want the SharePoint site.

`drive.readonly` is a **restricted** scope — CASA third-party assessment, $500–$4,500/year, re-verified annually. `drive.file` via the Picker is not. Never request the restricted one.

---

## 4. Why the Teams case is unusually clean

Non-channel meeting recordings land in the **organiser's own OneDrive** (`/Recordings`), and the researcher schedules the interview. So the only permission needed is one the user can grant themselves — which happens to align exactly with the customer profile: the individual purchaser with no procurement gate.

**Where it breaks:**

- **Someone else organised the session** — a client PM books the calls. The recording is in their OneDrive, shared with the researcher, and shared-with-me on a work account generally needs `Files.Read.All` (admin wall).
- **Freelancer as a guest in the client's tenant** — not the organiser, possibly no access at all.

Both are real for freelancers and indie consultants, who are explicitly in the customer profile. So **manual drag-drop import stays a first-class path forever** — not a fallback, and not something to deprecate once this ships.

---

## 5. Shape

- **v1** — `Files.Read` only. List `/Recordings`, parse title + date from the filename (`<Title>-<YYYYMMDD_HHMMSS>-Meeting Recording.mp4`), **single-select**, download into the selected project. No calendar, no verification, no meetings API. Store the `driveItem` id + account on the imported session: one record serving dedupe, retry, and provenance.
- **v1.1** — multi-select with per-row outcome. Reuse the existing `partial` vocabulary rather than inventing one. Resumable fetch (Range requests).
- **v2** — `Calendars.Read` for surname / `@domain` / description search plus the attendee roster.
- **Then** Zoom (review), then Google (sensitive-scope verification).

**Already-imported state belongs in v1, not v1.1.** It prevents duplicates at one-at-a-time, and it does most of v1.1's reliability work: a partial multi-fetch recovers by re-ticking what didn't land, with no transactional download, no rollback path, and no resume tokens. Without it the researcher reconciles two lists by hand — the exact drudgery the feature exists to remove.

---

## 6. Mechanics worth knowing before building

**The calendar is the index; the storage API is the fetch.** Graph cannot filter events by attendee — Microsoft's guidance is to pull `calendarView` over a range and filter client-side. For a desktop app that is better anyway: sub-millisecond type-ahead over surname, `@domain`, title and description, with no round-trip per keystroke.

**Read `expirationDateTime` off each file** rather than choosing a window. Sort soonest-expiring first and the import list becomes a triage queue — *"expires in 11 days"* next to the tick-box. Microsoft's expiry-warning emails are now a per-tenant setting, so researchers can no longer rely on being told. On expiry the file goes to the recycle bin, not a hard delete, so there is a grace period.

**Default window 30 days**, ceiling wherever the oldest surviving file sits. ~95% of what you want to import is recent — you cannot analyse what you cannot remember. Going further back is a *different intent* (you know what you're looking for): an explicit search with a term and a range, not a longer scroll.

**A calendar event is not proof a recording exists.** Resolve recordings for the window once and join locally, so the list only offers meetings that actually have something to fetch. Second effect: if BN retains only entries that matched a recording, it never holds the researcher's general diary — the correctness fix and the privacy fix are the same fix.

**Cadence is two-shaped, and one tick-list serves both:**

- **Usability** — 5 sessions in 2 days, all imported at once on day 3. Usually a *new* project.
- **Generative / longitudinal** — 2–3 at a time over weeks. Always *adding* to an existing project.

So destination is a picker ("New project…" plus the current project pre-selected), not a default. Select-all must operate on the **filtered** set, not the window.

**This rhythm is what incremental analysis was built for** (shipped 0.20.0): import 3 → analyse → import 3 more → re-analyse with curation surviving. Import closes the one manual gap left in the middle of a workflow that already exists.

**A roster from the invite could retire the pre-redaction speaker-ID LLM call.** Stage 5b sends raw transcript to the LLM *before* PII redaction because it must infer names and roles — the only pre-redaction egress in the pipeline, currently disclosed in `SECURITY.md`. Attendee lists make it ground truth instead of a guess.

**Never take the platform transcript in place of Whisper.** Teams and Zoom transcripts are real-time ASR with weak diarisation. Substituting them would be a quality regression precisely where attribution errors matter most. Second opinion or metadata only.

**The fetch reuses existing UI.** `CopyMachinery`'s determinate ring, hover-cancel and "Copying · N%" on the target row is the right surface; this needs a second source alongside drag-drop, not a new progress system.

---

## 7. Costs to be honest about

- Three OAuth app registrations to create, maintain, and keep through review.
- Three APIs that will change underneath us.
- A governance question: a researcher's employer may take a view on a personally-purchased tool authenticating to corporate M365, even at `Files.Read` on their own drive.

---

## 8. Related

- **`docs/design-project-storage.md`** — what happens to media once BN has it; the other half of this pair
- `docs/methodology/consent-gradient.md` — the governance model provenance and retention sit inside
- `docs/design-keychain.md` — token storage; the Miro flow is the precedent
- `SECURITY.md` — the stage-5b pre-redaction disclosure this feature could remove
