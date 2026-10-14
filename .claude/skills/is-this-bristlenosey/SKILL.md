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

Learned 14 Oct 2026: screen-reading progress was reviewed as a new UX and argued off the sidebar
status line by three reviewers. The owner: it is "simply an extra bit of progress on the same status
line as other activities for a project — fit into the standard bn frameworks".

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

| Domain | File | Canonical doc(s) |
|---|---|---|
| Progress, activity, waiting | `domains/progress.md` | design-desktop-project-status.md, design-embedded-activity-routing.md |
| (next) Lenses | — | design-lens-template.md |
| (next) Formats | — | design-shared-formats.md |
| (next) Gates | — | design-feature-flags.md |
| (next) Strings | — | design-i18n.md §"Which surfaces are targets" |
| (next) Credentials | — | design-keychain.md |
| (next) Providers / model switching | — | design-cli-provider-selection.md, llm/CLAUDE.md |

## Rules for maintaining a domain file

- Anchor to symbols and docs, never line numbers.
- Every rule cites where it is ruled (doc, code comment) or the incident that made it.
- Record disagreements between siblings as open calls; resolve them only when the owner does.
- Worked cases stay few and real. Keep some known answers out of the file, to test it blind.
