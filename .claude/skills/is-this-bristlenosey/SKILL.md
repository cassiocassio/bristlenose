---
name: is-this-bristlenosey
description: "Does this fit how Bristlenose already does it? Before designing or reviewing any feature, find its nearest shipped sibling in Bristlenose and check the proposal follows that sibling's mechanism (surface, precedence, data path, store, strings, tests), justifying every departure. Use when planning or reviewing a feature, when asked 'is this bristlenosey?', 'does this fit?', 'how does BN already do this?', and as the first step of /usual-suspects plan reviews. Not for genuinely new surfaces with no sibling — those go to the platform-taste reviewers."
---

# Is this Bristlenosey?

Most features are not new design problems. They are one more instance of something Bristlenose
already does: one more activity on a project's status line, one more lens, one more background job,
one more string, one more format. The Bristlenose answer is the one its nearest shipped sibling
already gives. Reviewing such a feature from first principles ("how would Photos do it?") produces
confident, well-argued, wrong advice: it re-litigates decisions the codebase has already taken.

Learned 14 Oct 2026, when a new feature was reviewed as a new UX by three reviewers who argued it
away from the surface its shipped siblings use; the owner's correction was to fit it into the
standard Bristlenose frameworks. (The case itself is kept out of this skill so it can serve as a
blind test.)

## The method (the same for every domain)

1. **Name the kind, in Bristlenose's terms.** Not "a progress indicator" but "an activity on one
   project, started automatically, run in the server". Read the domain file for the kinds it knows.
   **Set gating aside:** a Diagnostics gate, a feature flag, "rough, on main" — scaffolding, not
   identity. Review the feature as it will ship.
2. **Find the nearest shipped sibling(s)** in `domains/<domain>.md`, then **read the sibling's code**.
   The domain file points; the code is the evidence. If a governing design doc is named, read it: a
   decision may already be open or taken there.
3. **Map each part of the proposal onto the sibling**: surface, placement/precedence, data path and
   transport, store, wording and length, strings and locale enrolment, tests, export/privacy
   classification. Mark each part:
   - **follows** — same mechanism;
   - **departs** — with one sentence: "the sibling does X; we depart because Z" (if you cannot write
     Z, it follows);
   - **invents** — a new surface, vocabulary, transport or type with no sibling. Inventions are the
     findings.
4. **Carry the sibling's rules over** (the domain file lists them): what the glyph/ring/colour means
   there, what may never be shown, budgets, precedence, privacy.
5. **Where siblings disagree, do not choose.** Name both, say which the proposal follows, and list it
   as an open call for the owner. The domain file records the known disagreements.
6. **Verdict**: *Bristlenosey* / *mostly* / *not yet*, with the part-by-part table. Only the parts
   marked **invents** go to platform-taste review (what-would-gruber-say, ux-critique,
   mac-arsed-mac-app).

## Output

```
Kind: <one line, in BN terms>
Sibling(s): <feature — code symbol — governing doc>
| Part | Proposal | Sibling | follows / departs (why) / invents |
Open calls (siblings disagree): …
Verdict: …
```

## Domains

Read only the domains the question touches. A domain is added when a real case shows the knowledge
is scattered; where one canonical doc already rules, the domain file is a pointer plus a kinds table.

**Status key.** *built*: a domain file exists and has passed a blind test. *pointer*: one doc
already rules the domain; read it as the sibling register until a domain file is worth writing.
*inventory*: the knowledge is scattered across docs and code; inventory it before trusting an
answer (as was done for progress). *reverse-engineer*: no ruling doc, but a robust shipped
implementation; the code is the precedent, so derive the rules from it. *settle first*: siblings
disagree on fundamentals; a domain file would only list open calls until the owner rules.

### Domains it knows (docs paths under `docs/`)

| Domain | Typical question | Ruling doc(s) | Status |
|---|---|---|---|
| Progress, activity, waiting | "how do we show this work in flight?" | design-desktop-project-status, design-embedded-activity-routing | **built** (`domains/progress.md`) |
| Formats | "how do we render this duration / timecode / date?" | design-shared-formats | pointer |
| Gates | "flag, Diagnostics, `#if DEBUG`, env var?" | design-feature-flags | pointer |
| Strings and i18n | "is this surface translated? which namespace?" | design-i18n §"Which surfaces are targets", platform-text-map, glossary | pointer |
| Messages and errors | "a new error / refusal / warning" | design-pipeline-diagnostic-popover (`MessageKind`, budgets) | pointer |
| Credentials | "storing a key or token on the Mac" | design-keychain | pointer |
| Providers and model switching | "a new provider / model / picker" | design-cli-provider-selection, `bristlenose/llm/CLAUDE.md` | pointer |
| Lenses | "a new lens" | design-lens-template, the five shipped lenses | inventory |
| Sidebar and project navigation | "a new row, item, badge, nav element" | design-desktop-project-status, design-desktop-sidebar-appkit | inventory |
| Menus and commands | "a new command; which of the four routes?" | design-desktop-menu-actions | pointer |
| Keyboard | "a new shortcut or focus behaviour" | design-keyboard-shortcuts, design-keyboard-navigation | pointer |
| Edits to researcher data | "a new mutation on quotes / tags / names" | design-undo-catalog, design-undo-debt, the bulk store functions | inventory |
| Exports and privacy | "does this leave the machine? an export, MCP, the LLM?" | design-export-html, design-localhost-auth, consent-gradient | inventory |
| Cross-platform | "CLI vs Mac vs Windows; which channel ships it?" | design-modularity, design-platform-policy | pointer |
| Tests and gates | "what proves it, at which layer?" | design-test-philosophy, `docs/testing/` (ratchet, soft gates) | pointer |
| Analysis lifecycle | "a new way to start / re-run / resume analysis" | design-analysis-lifecycle, design-pipeline-resilience, design-lifecycle-failure-modes | pointer |
| Identity | "how is a project / recording / person identified?" | design-project-identity, design-people | pointer |
| Settings | "a new preference; env var or live?" | design-desktop-settings | pointer |
| Terminal output | "a new CLI line, count, or prompt" | design-cli-formatting, design-cli-just-works | pointer |
| Motion and visual tokens | "a new animation, colour, spacing" | design-motion, `bristlenose/theme/CLAUDE.md`, design-react-component-library | pointer |

### Domains to reverse-engineer from robust code (no ruling doc yet)

These are done well in shipped code but written down nowhere as a rule. The code is the precedent;
a domain file here is derived by reading the implementations, not by designing.

| Domain | Robust precedent(s) to read | Why it is worth a file |
|---|---|---|
| Background jobs in serve | `server/scene_strips.py` (`SceneStripJob`), `server/screen_text_job.py`, AutoCode's task set | Rules live only in code and gotchas: defer during a run, the rerun flag, failures recorded so polls don't loop, strong task refs, never cache a short read. Every new job re-derives them. |
| Server ↔ Mac data | `pollAgentPulse`, `/api/health`, the MCP handshake, the bridge, the events log, `PipelineLiveData` | No settled sibling: tonight's progress work needed a transport and found five candidates. Also *settle first* on polling cadence (1 Hz to 20 s across eight pollers). |
| Accessibility | `announce()` + `AnnounceRegion`, `useInert`, VoiceOver routing through subtitles, the a11y-review agent | Patterns are consistent in code (polite live region, inert behind modals, the ring hidden from VoiceOver) but only the agent knows them. |
| Empty and zero states | Schema E (a clean row is silent), BootView's wordless bar, the status page, lens empty states | "Absence is information" is a memory, not a doc; each lens invents its own empty copy. |
| Media playback | `PlayerContext`, the popout player, glow index, `/media` auth exemption | Rich gotchas in `frontend/CLAUDE.md` and desktop notes; no rule-of-the-road for a new playable surface. |
| Quote cards and the quote store | `QuoteCard`, `QuotesContext` bulk functions, the full-map PUT, undo entries | The Screens lens reused these correctly; a new surface showing quotes should find the rules in one place. |
| Confirmations and destructive acts | memories "Cancel is never the default", "confirm only for a real loss", `NSAlert` usage | Taste rules in memory only; easy to get wrong in a new dialog. |

### Domains to settle before writing (siblings disagree)

| Area | The disagreement |
|---|---|
| Spellings of counts and times | "2 of 3" / "(2/5 files)" / "48/72"; "~N min left" / "~8 min (±2 min)" / "1:48" by surface |
| Cancelled vs failed glyph | the chip's ✗ vs cloud import's skipped glyph |
| Web-view jobs on native surfaces | `design-embedded-activity-routing.md` is open (dock the chip vs route to the row) |
| Polling | eight independent pollers, cadences 1 s to 20 s, no shared rule |

### Possible later

Tone and copy (glossary covers terminology, not voice); onboarding and first run
(design-welcome-screen covers one window); research-method choices (design-research-methodology is
the spec; a domain file would add "which existing analysis does this resemble?").

## Rules for maintaining a domain file

- Anchor to symbols and docs, never line numbers.
- Every rule cites where it is ruled (doc, code comment) or the incident that made it.
- Record disagreements between siblings as open calls; resolve them only when the owner does.
- Worked cases stay few and real. Keep some known answers out of the file, to test it blind.
