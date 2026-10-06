---
status: partial
last-trued: 2026-10-04
trued-against: HEAD@main on 2026-10-04
---

# People — who is in a study, and how the researcher fixes it

*Problem-first spec for person identity across Bristlenose: the jobs researchers
are trying to do, the UX that serves them, and — last, deliberately — the
functionality and data that fall out. Most of the UX in this document is not
built. **Built on `main` as of 4 Oct 2026:** per-session moderator and observer
names, the name-confirmed state (migration 012), the person picker on the
Sessions grid on both channels (speaker ID v1.1 — §H H9, UX iteration 3), and
undo on speaker naming (§B10). Route C Phase 1, project-wide identities, is
on `main` since 6 Oct 2026 (unreleased; `git log -S'speaker_slots' --oneline`). The people *file* and its endpoints
predate all of it — `get_people` / `put_people` in `server/routes/data.py`,
`PeopleFile` in `models.py`, and `/people` in the export embed.*

## Changelog

- _2026-10-06_ — **The owner answered the Phase 1 and §J7 calls (§J8).** Four answers, three
  of which change the design. **(1)** A self-introduction proposes a name and creates a
  person, overriding §C5's "a heard name is never a proposal". **(2)** A person is unique and
  names can clash. Picking a name means "this speaker is that person". Editing a name, from
  any surface, fixes that person's spelling everywhere they appear. This contradicts the
  Phase 1 branch, where a typed name on a shared person creates a new person. **(3)**
  Deleting a person waits for the People lens. The picker gains a way back to
  *unknown*. **(4)** Codes per person and role are confirmed, under a stated principle: people
  are unique, and roles are what they perform in a session. Also confirmed: the two
  §J7 prerequisites, and `people.yaml` can go whenever the architecture allows.
- _2026-10-04, evening_ — **Trued for 0.33.0, and the summary caught up with the body.** The
  intro said none of the UX was built; the picker (web and Mac), `name_confirmed` (012) and undo
  on speaker naming all shipped today, so the intro, §0, §C1, §C5, §D step 1, the H9 phase rows,
  the string plan and the measures now say so — each with a dated note, the original kept. §J5's
  free wins were already done on 27 Aug (`deb62808`) and are struck, bar the hint in 20 locales.
  The picker's accessible proposed state (`03efebb5`), the native anchor inset and the "moderated
  by" line are recorded under UX iteration 3; the undo interaction with the sidebar removal store
  under §B10. **Still open and not touched:** whether iteration 2's `/usual-suspects` pass ever
  ran (its row says pending; no artefact shows it), and the MCP anonymise defect (H2–H4 #3).
- _2026-10-06_ — **H9 Phase 1 landed on `main`**, squashed from `route-c-phase1` after a
  conflict-free rebase (pytest 6216 passed, vitest 2378). Owed before it is released (§J8):
  the three name intents, keeping people with no sessions, and the `mA?`/`mB?` letters.
- _2026-10-04_ — **H9 Phase 1, the data layer, is built on a branch (`route-c-phase1`) and waits for 0.33.0.**
  One `Person` per identity; `session_speakers.person_id` nullable with `state` and `evidence`
  (migration 013, which absorbs 012's `name_confirmed`); every route emits the identity's code,
  so session 2's moderator reads `m2` and an unidentified one `m?`. All four measured findings
  are folded in, and five departures from the row are recorded under H9's table with the calls
  they leave for the owner.
- _2026-10-04_ — **Undo on speaker naming is built — the step-1 gate is open.** A pick, a
  confirm or a typed name from the person picker, and the Sessions grid's inline rename, push one
  entry on the report's undo stack (`contexts/UndoStore.ts`); Edit ▸ Undo on the Mac and ⌘Z /
  Ctrl+Z in the browser pop it, putting back both stored names and the confirmed flag. The
  `undo-state` channel is live end to end. Details under §B10.
- _2026-10-04_ — **The cross-role recode is planned (§J7), and its premise corrected.** A
  speaker's kind is held on the slot in the serve DB and never reaches the pipeline by itself:
  the transcript fingerprint hashes roles and codes, so a recode stamped into the registry would
  re-analyse the session for money, against §C5's "does not re-extract". Moderator ↔ observer
  first (R1), changing no number and no quote; into or out of participant relabels and *offers*
  re-analysis (R2, R3). Seven calls for the owner. Found on the way and fixed: the registry
  reissued a participant number once its speaker was re-identified as another kind.
- _2026-10-03_ — **Per-session moderator names shipped as the weekend fix — not Phase 1.** Measuring
  Phase 1 before building it found its row unsound (see the second dated block under H9's table), so
  the owner chose the smaller fix: each session's moderator and observer are named from that
  session (`.bristlenose/intermediate/session-speakers.json` → the importer), renamed one session
  at a time (`PUT …/sessions/{sid}/speakers/{code}`), and `PUT /people` no longer touches `m*`/`o*`.
  Badges still read `m1`; no identities, no `m?`. The serve app, the export and the MCP overview
  stop colliding; the CLI's markdown and sealed static HTML still do.
- _2026-10-03_ — **H9 Phase 0 landed, and two upgrade obligations dropped by the owner.** Sessions
  and speakers now keep their numbers across runs (`bristlenose/session_registry.py`,
  `.bristlenose/sessions.json`): an older recording arriving late is numbered last instead of
  renumbering the study. The owner's call the same day: **existing projects are not migrated** —
  a researcher re-runs them — and **names typed into an old `people.yaml` are not carried
  forward**. So Phase 1 does not read a legacy file and Phase 5 does not prove an upgrade path;
  see the dated block under H9's table.
- _2026-10-01_ — **Route C decided: unknown is stored as unknown, and `people.yaml` is retired
  as a store.** Twelve calls taken with the owner against the storyboard in
  [`mockups/moderator-identity-failure-states.html`](mockups/moderator-identity-failure-states.html)
  Part 5b (frames E1–E8). The `m`/`o` half of **§E decision 1 is corrected**: a session's moderator
  slot is `null` · `proposed` · `confirmed`, rendered `m?` when null; identities are minted on
  platform evidence or a pick and numbered as they appear; the renumber-on-rename mechanism is
  replaced by a per-session map, which is `session_speakers.person_id` made nullable plus `state`
  and `evidence`. **Nothing infers and nothing asks** — no "looks like you" line, no confirm prompt;
  a proposed slot wears the shipped AutoCode `.badge-proposed` treatment in the app and reads plain
  in the export. Name-only platform labels mint one identity per distinct name within a study — a
  recorded carve-out from "never auto-merge on name equality" for that evidence class. Default
  reach for a moderator pick is **narrow**; §B3's wide default is scoped to surfaces where rows
  genuinely arrive together. Keyed by the transcripts plan's 0b stable session identity, which
  lands first. Migration: inherited-proposed on every session. Me is seeded from the account name
  with no settings UI. The importer runs at the end of every pipeline run; a legacy `people.yaml`
  is read once and then ignored. The markdown report and the sealed static HTML get no investment.
  Observers share the engine; the count line counts moderators only. Sections touched: §0, §B3,
  §B4, §B6, §C2, §C5, §D, §E decision 1, §G, §H (H9), §J2, §J4. **Later the same day: §H H9 is
  the delivery plan** — six phases, each shippable and gated, with UX iteration 2 and a review
  pass between the data layer and the web UX — and
  [`mockups/moderator-identity-iteration-2.html`](mockups/moderator-identity-iteration-2.html)
  redraws route C in the shipped stylesheet with only shipped strings, superseding the
  storyboard's E-frames for anything about pixels. Drawing it found one consequence the
  storyboard could not: the shipped action pill overhangs onto the name in the Sessions grid.
- _2026-08-25_ — **H8 done — §J, the concrete deltas.** Headline finding: **the role endpoint is not a
  step-1 operation.** Because `kind` *is* role, `p4 → observer` is a recode touching seven things — the
  unique constraint, N segments, quote attribution, the stable key, a `people.yaml` path that cannot
  express a rekey, the bracket tokens on disk — so role belongs with step 4; what ships in step 1 is role
  as a recorded override. Also: the bank needs a *new* instance database (`bristlenose.db` is occupied);
  every new `people.yaml` block carries a **downgrade hazard**, because `write_people_file` does a
  `model_dump()` and an older binary silently drops what it does not know; and §J5 lists six defects that
  ship free of the whole design. The code-truth pass refuted eleven claims and corrected a dozen line
  citations, so §J cites files, not lines. One of my own over-claims corrected too: the extraction prompt
  says "participant" twice, so the observer guard is weakened, not absent.
- _2026-08-25_ — **H6 and H7 landed as specs** (7-agent workflow, compliance + anchor verification). §B4
  gains the bank spec — **moderators and observers only, never participants**, two lists split on decision
  2's line (prevention where picking is safe; reconciliation where it is not), **no group header ever**,
  and a measured blocker: `Person` rows do not span projects, so the bank needs the instance DB before it
  can hold anything. §B5 reframed — the row is one record and the scope switch changes the *population*,
  not the meaning. Two of my own errors corrected. The cast sweep and the old-mockup edits are written,
  verified, and **deliberately not applied** — the sweep would leave `p1` belonging to nobody.
- _2026-08-25_ — **vocabulary adjudicated: there is no collective noun, and the product does not need
  one.** Ship the rule (*participants are anonymised; moderators and observers are named*) and enumerate
  where a label is structurally required. Unanimous across the governing codes — MRS, the MRS Observers
  guide and ICC/ESOMAR all define the participant side precisely and *enumerate* the other, with zero
  uses of any superset; MRS's own definition ("any individual or organisation from or about whom data is
  collected") is very nearly this document's, arrived at independently. **`insider` is retired** — it is
  an established term of art in qualitative methods for a researcher who shares the community being
  studied, so it already means something else. Also killed with reasons: *collaborator* (ja 研究協力者 /
  ko 연구 협력자 are the ethics-committee terms for research **participants** — it inverts the line),
  *investigator* and *facilitator* (byte-identical to shipped es/ca/de/ko strings), *contributor*,
  *back room*. `non-participant` held in reserve as a label-only fallback.
- _2026-08-25_ — **§B7a added: classification is not the product, and the correction is compound.** An
  enthusiastic observer is linguistically a participant and no classifier wins that — so the product's job
  is the repair, not the inference. The everyday correction carries *who* and *what* together ("that's
  Steve, and he's an observer"), which makes the grouped picker's role-by-grouping property load-bearing
  on the sessions-grid speaker entry too, not just in attribution. And since `kind` **is** role, a role
  change *changes the code* — `p4` ceases to exist and an `o` code appears — so it inherits the whole
  renumber path and finishes the J3 story by membership rather than by hiding.
- _2026-08-25_ — **observers characterised, and a live defect fell out of it.** They are *never* a data
  source; most are near-silent and many never enter the transcript, so the ones the product can see are
  the minority; and when they do speak they speak as collaborators of the moderator, which makes their
  words moderator-class speech. Checking that against the pipeline: **`s09` feeds `full_text()` and the
  extraction prompt names only `[RESEARCHER]`**, so observer speech is excluded only by the model
  generalising — and correcting a mis-filed observer `p → o` may hand their comments straight back to
  the next extraction. Recorded in §C1 and against decision 2's J3 note. S13 reframed.
- _2026-08-25_ — **the participant test articulated** by the product owner and recorded in §E decision 2
  and the glossary: a participant is **the source of the data, the subject of the study**, held up by a
  knowledge asymmetry (the other side has the objectives and the guide) and a control asymmetry
  (participants respond, they do not direct) — and explicitly **not** by commercial relationship, since
  incentives, salaries, contracts and volunteering cut across the line in every direction. The word for
  the second category is **not** settled; *insider* is internal shorthand only, and whether a collective
  noun is needed at all is under adjudication.
- _2026-08-25_ — **H5 executed** (7-agent workflow, two adversarial verifications). Added **§I**, the menu
  enumerated: the domain collapses to nine inputs — `kind` IS role, and §C5's six name states collapse
  3:1 because only `guess` invites action. Three conventions settled: **a bare `Role ▸` is never
  correct** (generated from §0 + §C5, not chosen); the me-item is `That's Me (Name)` / `Name (Me)`,
  measured 3–0 off shipped Apple `.loctable` files; bench 3's propagation sheet leaves the naming path,
  because the document already contradicted its own frame. String plan: 141 seedable keys in one
  `common.people` block, ~9.7% growth, zh-Hant-HK zero. Decision 2's deletion of membership also killed
  the bank's `Your team` header — recorded as open, not invented.
- _2026-08-25_ — **H2, H3 and H4 executed** (6-agent workflow, adversarially verified; privacy check on the
  measurement passed — metadata only, no participant content). **Decision 2 settled by reframing**: the
  boundary is the *participant* line, not the team line, so the prefix mechanism stays and the rationale
  changes; moderators and observers are named and are instance-wide and singular, while
  *participants* get the three nested scopes — which is what §B5's scope switch is actually for. J3's
  observer sweep unblocked. §D claim 2 now carries measured numbers and the reason the ordering was
  held. §B10 records the menu host and the undo contract. §F has no untriaged row.
- _2026-08-25_ — **H0 and H1 executed** (8-agent workflow, anchors and recommendations independently
  verified). H0: eleven edits truing four neighbour docs to the settled decisions. H1: five glossary
  rows, nine pinned turn-nouns, the ja Observer drift corrected; the dead-enums delete held because
  verification found the census incomplete; four owner calls recorded in §H rather than guessed.
- _2026-08-25_ — **ten-agent review + verification pass** (6 lenses, an independent planner, adversarial
  verify: 57 confirmed / 3 refuted). Fixed same-day: the **membership claim was false** — no read-time
  filter exists on the Quotes lens, membership is extraction-time only, so §B9's "falls out of the
  lens" is a capability to build (§C4 corrected, §C1 gains the gap); **segment provenance is flattened
  at import** (§D claim 2 now says measure the intermediates); **`p3 Is Actually ▸` renamed
  `All of p3's Turns Are ▸`** and classified attribution — the lexical rule now holds with no
  exceptions; §B2 gains the localisation contract (pinned turn-nouns; label-plus-chooser); hide/withdraw
  survivors purged; §E preamble, §D step-1/step-3 costs, state counts, surface counts, changelog
  attribution trued. Added **§H**: eight sequenced work packages plus the pinned cast. Larger findings
  (cast sweep, old-mockup reconciliation, corpus truing, vocabulary adjudication) live in §H, not here.
- _2026-08-24_ — added **§C4 (quote↔person)** and **§C5 (the person state machine)**. Measured: there
  is *no* modelled quote→person relationship — `Quote.participant_id` and
  `TranscriptSegment.speaker_code` are plain strings, and the only FK to `persons` in the schema is
  `SessionSpeaker.person_id`. That denormalisation is why one-name-per-code is free, why the `m1`
  collision is possible, and why segment→quote cascade is the expensive part. The state machine is
  three independent lifecycles (name · identity · role) plus per-person membership; collapsing them
  into one status enum is the trap.
- _2026-08-24_ — sharpened again: **nothing is withdrawn**. The Quotes lens has two orthogonal
  axes — *membership* (is this a participant quote — a fact, derived, no state of its own) and
  *emphasis* (star promotes, hide demotes — a researcher judgement, explicit state). Re-attributing a
  speaker moves a quote on the first and never touches the second, which is why the hidden count
  stays meaningful: it counts judgements, not facts. Removes the "withdrawn" state an earlier draft
  invented.
- _2026-08-24_ — **a quote is a view onto speech, not a copy of it**: re-attributing a quote changes
  the underlying speech, so the transcript agrees afterwards, and the card's disappearance is a
  consequence rather than the action. Corrects the same day's earlier claim that the destination was
  the existing hide verb — **withdrawn is not hidden**, because the hidden count is a curation signal
  and a correction must not pollute it. Also: the quote's own timecode range supplies the split point,
  which makes this flavour of step 5 much cheaper than the rest.
- _2026-08-24_ — **the quote-card picker means something different**: quotes exist only for
  participants, so the current value is always `pN` and picking an `m`/`o` target means the quote is
  *not a finding* — the outcome is withdrawal via the existing hide verb, with the reason recorded,
  not a moderator-authored quote. Named the reconciling pattern: **do the narrow thing, then offer
  the wide one in a sentence.**
- _2026-08-24_ — **corrected the namespace model**: `m`/`o` codes over-*fragment* as well as
  over-collide, because the number comes from within-session ordering (Jane is `o1` alone in s1 and
  `o2` beside Tom in s3). An earlier draft claimed they never fragment. All three namespaces need the
  join; only `m`/`o` need the split. Added **default reach follows the working mode** to §B3 —
  sweeping surfaces default wide, reading surfaces default narrow, widening is a menu item and
  narrowing is navigation.
- _2026-08-24_ — §B3 extended with **the same menu across four surfaces**, expressed as a function of
  (where you clicked, what state the object is in) plus four generating rules — so a new verb lands
  everywhere it is meaningful and a later surface inherits the vocabulary rather than a subset.
- _2026-08-24_ — **one name per code, everywhere** recorded as a §0 invariant, which makes the
  moderator renumber *forced* rather than chosen and retires the `(session, code)` rekey as an option
  that would have broken it. Attribution split into three grains (§A tier 3): whole-speaker (common,
  cheap, and the same operation as a merge), single-quote (occasional, must be possible), per-turn
  (rare, expensive). Added §B9, the grouped and creatable attribution picker.
- _2026-08-24_ — **added the stance and the scale table**, which govern the rest — *make the common case
  trivial and the edge cases possible*: BN goes with the
  typical case and makes wrinkles easy to see and fix, rather than inferring harder. Typical study is
  <20 participants (usually ≤12), 3–4 colleagues, one moderator, and the extra person in a session is
  an observer ~95% of the time — so observer mis-filing is the dominant repair and the `m1` collision
  is a tail case. §B6's rationale corrected for small N.
- _2026-08-24_ — **§E decision 1 settled**, and reframed: the person-or-slot question was the wrong
  one. Codes are globally-numbered speaker slots; identity is a layer above them; `p` over-fragments
  and `m`/`o` over-collide, and each needs one escape, both reached by naming. `m1` being the same
  moderator across sessions is the ~95% case, so the reset is usually correct. Renumbering is a
  consequence of renaming in a session, not a separate verb. §D steps 4 and 5 collapsed accordingly;
  §0, §A J10 and §F S4/S14 corrected.
- _2026-08-24_ — §F triaged by the product owner: S3 already handled; S2/S4/S9/S10/S15 need no new
  mechanism; S5 is workflow, not product; S6/S7/S10/S15 (and S14 in part) generated the constraints in
  §B8; S1/S16/S18/S14(full) deferred; S17 accepted with an open question, answered in §F. S8, S11,
  S12 and S13 were not reached and stay untriaged. Added §B8 and the "spoke on behalf of" non-goal.
- _2026-08-24_ — created, problem-first, from a design conversation. Companion
  mockups: [`docs/mockups/person-actions-everywhere.html`](mockups/person-actions-everywhere.html)
  (the affordance, nine benches) and
  [`docs/mockups/people-lens-scopes.html`](mockups/people-lens-scopes.html)
  (the aggregated view at three scopes).

---

## What this is, and what it is not

This is a **zoom-out**, not a rewrite. Most of the machinery is already fit for
purpose; what has been missing is a viewing distance at which certain defects
become visible, and a vocabulary the researcher can reach from wherever they
noticed one.

It is deliberately ordered **problems → UX → implementation**. The data
structures at the end are consequences, not premises.

**It does not restate the moderator-code collision.** That analysis, its
eight-reader list, and the reason it was not fixed in place already live in
[`design-transcript-speaker-editing-roadmap.md`](design-transcript-speaker-editing-roadmap.md)
§11c. Two documents describing one collision will drift; this one points.

### The stance

> **Make the common case trivial and the edge cases possible.**
>
> It is not Bristlenose's job to work all this out. It is Bristlenose's job to go
> with the typical case, and make it easy to see and fix the wrinkles as they
> come.

That sentence governs everything below it, and it is a different goal from the
one most of this problem invites. The invitation is to infer harder — detect two
moderators, match names across studies, classify an observer correctly, get
Vietnamese name order right. The stance declines all of it. **Pick the typical
case confidently, render the result so a wrinkle is obvious to a researcher who
knows the study, and make the fix cost one action.**

Two consequences worth stating plainly, because they cut work rather than add it:

- **Detection is not the product; legibility and repair are.** Every place this
  document reaches for a heuristic, the cheaper answer is usually to render the
  situation honestly and put a verb next to it. The researcher was in the room.
  They know who Mary is.
- **Being wrong is acceptable; being wrong *invisibly* is not.** A guessed name
  in italic that the researcher fixes in one click is a good outcome. A guessed
  name that looks like a fact is not, however sophisticated the guess.

### Scale — what "typical" actually means

These numbers licence real simplifications, and they were the missing input for
several judgements earlier in this document.

| | Typical | Consequence |
|---|---|---|
| Participants in a study | **fewer than 20, rarely more than 12** | The People lens is a **short list**. No virtualisation, no pagination, no search-first UI. Everything can be on screen at once |
| Colleagues you work with | **3 or 4, maximum** | The bank is a handful of names. A submenu always fits, never scrolls, and needs no search field |
| The extra person in a session | **an observer, in ~95% of cases** — not a second moderator | Observer mis-filing (J3) is the dominant non-naming correction. The `m1` collision is a genuine tail case |
| Moderators per study | **one**, in ~95% of studies | The per-session moderator counter produces the right answer nearly always — see §E decision 1 |

The last two rows are the same fact from two directions, and together they
re-rank the work: **the common repair is "that person was observing", not "that
was a different moderator."**

### §0 — What is already fit for purpose

Worth stating first, because it bounds the work and prevents re-derivation:

| Already right | Where |
|---|---|
| `Person` rows are **instance-scoped** — no `project_id`, deliberately, so a person can outlive a project | `server/models.py` `Person` |
| `SessionSpeaker` joins person↔session **per session**, carrying code, role and per-session stats | `server/models.py` `SessionSpeaker` |
| Two name fields exist and mean different things — `full_name` (the record) and `short_name` (what appears beside a quote) | `models.py` `PersonEditable` |
| Short-name derivation is genuinely careful — honorific stripping, family-name-first detection, 337 surnames, and collision handling that yields "Sarah J." / "Sarah K." | `people.py` `suggest_short_names` |
| `people.yaml` is canonical, the DB is a materialised view, and browser edits write through to both. *4 Oct 2026: for participants only — since 3 Oct a moderator's or observer's name is per session, in the DB and `session-speakers.json`, and `PUT /people` no longer writes `m*`/`o*`* | `design-html-report.md` § People file |
| Speaker codes are the public identity; display names are a working tool | `SECURITY.md`, `docs/glossary.md` |
| **A name belongs to a code, and a code has one name — everywhere in the study.** `people.yaml` is keyed by code and holds one name per key. *Corrected 1 Oct 2026: a name belongs to a **person**; a code is the derived label of an identity, and a session's `m`/`o` slot may hold no identity at all (`m?`). The invariant survives one level up — a person has one name everywhere — and `people.yaml` is retired as the store (§C2)* | `people.py`, `models.py` `PeopleFile` |
| `p` codes are globally numbered across a study, so they never collide — one human returning gets several, which is normal. *Since 3 Oct 2026 they also stay put across runs and are never reissued (`session_registry.py`)* | `s05b_identify_speakers.py` `assign_speaker_codes` |
| `m`/`o` codes restart per session, which is the **right** answer whenever there is one moderator — about 95% of studies. *Corrected 1 Oct 2026: the per-session `[m1]` token stays and becomes a within-session tag; the identity shown on the badge is minted on evidence or a pick, and absent until then (§E decision 1, corrected)* | `s05b_identify_speakers.py`, §E decision 1 |
| Role detection is format-agnostic since Apr 2026 — word-count asymmetry plus a generalised prompt | `design-speaker-role-detection.md` |

The gaps are narrower than the surface area suggests, and are named in §C.

---

## §A — Jobs to be done

Ranked by how often a researcher hits them, not by how interesting they are.
Each names the evidence it rests on.

### Tier 1 — every study, every session

> **J1 · Talk about people by name.**
> *When I open a report my team will read, I want the people in it to have the
> names we use for them, so I can discuss findings without translating codes in
> my head.*
> The atom of the whole document: **"p4 is a human called Jane Smith."**

> **J2 · Say that one of them is me — once, ever.**
> *When I run a study, I want to say "that moderator is me" without typing, so I
> never enter my own name again.*
> The researcher is in every study they will ever run: the most recurrent person
> in the corpus, and the only identity the app never has to guess, because the
> person asserting it is the person. The Mac already knows the name
> (`NSFullUserName()`). Profile connection stays **opt-in** — the researcher may
> say "I'm m1"; the system may not decide it
> ([`design-multi-project.md`](design-multi-project.md) §2, principle 4).

> **J3 · Say that someone was observing, not participating.**
> *When a colleague or client sat in to watch, I want to record that, so their
> side comments stop being mined as findings.*
> **This is systematic, not bad luck.** Role identification samples roughly the
> first five minutes (`s05b_identify_speakers.py`, `seg.start_time > 300`), so an
> observer who first speaks at 31:40 is not in the sample at all; the heuristic
> that covers the rest scores question ratio and moderator phrases, neither of
> which an observer fires; and code assignment maps `PARTICIPANT` **and**
> `UNKNOWN` to a `p` code, so "could not tell" and "is a participant" produce
> identical output. Observers are the default, not the exception.

> **J4 · Pick a colleague from a list instead of retyping them.**
> *When my team of three or four moderates everything, I want to say "that m1 is
> Steve" by choosing, so I never type a colleague's name twice.*
> Recurrence is wildly lopsided: researchers appear in every study, participants
> appear once. A bank of known people is short, high-hit-rate, and — see §B — it
> converts the hardest job (J12) into a by-product of the easiest.

### Tier 2 — every study with raw audio

> **J5 · Correct a name I know is wrong.**
> *When the transcript has misspelled a participant, I want to fix it from what I
> know, so the report doesn't publish a name wrong.*
> "Michel Hurlly" is Whisper hearing **Mickael Hurley**. The researcher recruited
> him; the screener has the spelling. This is the one class where the human is
> not probably right but **definitely** right — and the misspelling is also in
> the transcript body, not just the label.

> **J6 · Record the formal name, but talk about them by the name we use.**
> *When Teams gives me "Michael J. Hurley-Okonkwo", I want to keep that for my
> records and call him Mike everywhere it matters.*

> **J7 · Say whether a guess is right.**
> *When the app guessed a name, I want to confirm or clear it, so I can tell
> later what has been checked and what has not.*
> Includes clearing a name that should never have been there — a platform label
> that is an email address is the highest-confidence and most sensitive name in
> any study.

### Tier 3 — attribution, at two grains

Attribution errors come in **three** grains, and the two that matter are the
cheap ones. Only the third needs segment surgery, and it is the rarest.

> **J8 · Fix a whole speaker in one transcript. — the common one.**
> *When everything attributed to `p3` here is actually the moderator — or when
> diarisation split one nurse into Speaker A and Speaker C — I want to say so
> once, so I am not fixing it turn by turn.*
> **This is the same operation as merging two codes that are one person**,
> approached from the speech side rather than the identity side, and the
> researcher's own framing is *"all the places they are actually `oN` or `pN` or
> `mN`"*. Cheap: one bulk update within a session. No word-timing division, no
> split, no merge of turns.

> **J9 · Fix a single quote.**
> *When two people talked over each other, I want to re-credit that one quote,
> so I don't publish someone else's words against their name.*
> Occasional, and it **has to be possible**: crosstalk may never be separable
> upstream — two voices genuinely occupy the same three seconds — and **a quote
> is published where a transcript is not.**

> *The third grain — "that one paragraph, mid-transcript, but not the rest" — is
> rarer than both and much more expensive. It is the only one that needs segment
> endpoints, word-timing division and a quote cascade. §D step 5.*

**Both cheap grains use the same picker**, and it is not a flat list of names —
see §B9.

### Tier 4 — rare, and expensive when missed

> **J10 · Separate one code that is two people.**
> *When "m1" covers me for eight sessions and Mike for one, I want to open that
> session, say "the moderator here is Mike, not Martin", and have him become
> `m2` — so nobody is credited with sessions they didn't run.*
> The trigger is a **rename in a session**, not a separate verb — see §E
> decision 1.
> **Genuine tail case** — one moderator in ~95% of studies, and the extra person
> in a session is almost always an observer, not a second moderator. High
> consequence when it does happen: it is the one
> defect in this document that **travels into an export**, where the recipient
> cannot detect it.

> **J11 · See everyone at once.**
> *When I'm checking a whole study, I want every person in one list, so I can
> spot what's wrong without opening twelve sessions.*
> Some defects are **only** visible when the person is the row: a moderator
> credited with 12 sessions and 4,210 words; a "participant" who appears in all
> ten sessions holding 47 quotes that are all interviewer questions. Both are
> arithmetic across sessions, and no per-session surface can show them.

> **J12 · Know I have met this person before.**
> *When I work with the same client repeatedly, I want to recognise a returning
> participant, so I can see a longitudinal picture.*

### Running underneath all of them

> **J13 · Be sure whose names travel.**
> *When I share a report outside, I want to know exactly which names are in it,
> so I don't disclose someone I didn't mean to.*
> Currently decided by the letter at the front of a speaker code — see §E,
> decision 2.

---

## §B — The UX

Drawn in full, with sample data, in
[`person-actions-everywhere.html`](mockups/person-actions-everywhere.html) and
[`people-lens-scopes.html`](mockups/people-lens-scopes.html). This section is the
argument; the mockups are the pixels.

### B1 · One object, one vocabulary, five altitudes — and every altitude reads *and* writes

A person reference is rendered on five surfaces today — a segment badge, a
session's speaker entry, a quote attribution, the "Moderated by…" line, the
sessions sidebar — plus the proposed People lens row as a sixth. They are the
same object. (§C3 holds the canonical *component* inventory; this list is the
*surface* one — don't extend either without the other.)
The researcher should not have to know which surface owns a fix — **they act
where they noticed the problem**, which is already the stated principle in
[`design-speaker-editing.md`](design-speaker-editing.md): *fix in context, not up
front.*

The lens is not a read-only roll-up and the badge is not a write-only control.
What differs by altitude is **what you can see** and **what scope your action
carries by default** — never whether you can act.

| Altitude | What only this altitude shows | What only this altitude does |
|---|---|---|
| A turn | who is speaking *here*, against the words | fix one boundary; split or merge turns |
| A quote | the extract as it will be published | re-credit the thing that actually ships |
| A speaker in a session | this person's share of this session | merge or separate codes; role in this session |
| A person in a study | arithmetic across sessions — the tells | separate a collided code; confirm names in bulk |
| A person across studies | the same human in more than one study | link, or record that two are different |

### B2 · Two families of correction, and they must never share a menu section

This is the load-bearing distinction.

| | **Attribution** | **Identity** |
|---|---|---|
| The sentence | "That was Sarah, not Jane." | "p4 is a human called Jane Smith." |
| What is wrong | the wrong person is credited with these words | the words are credited correctly; what we think the speaker *is* is wrong |
| Object | transcript segments → `speaker_code` | speaker → person, name, role |
| The fix moves | **words** | **nothing** — it relabels |
| Frequency | high on raw audio, **near zero on platform transcripts** | every study, every path |

Conflating them is how a relabel silently becomes a word-move: "This Turn Is ▸
Jane" and "This Speaker Is ▸ Jane" read almost identically and do wildly
different things, and the researcher would not find out for weeks.

**The rule is lexical, not visual.** *The item names the object it acts on.*
An item naming a **piece of speech** — **Turn**, **Quote** — is attribution: the
researcher is pointing at some words and saying they belong to someone else. An
item naming a **speaker** — `p3`, `m1`, **Name**, **Role** — is identity. One
sentence a researcher can hold, it survives translation better than a colour or
an icon, and it costs no vertical space.

An earlier draft allowed one exception — an identity item that "moves words as a
consequence", spelled `p3 Is Actually ▸`. The review killed it: that item is a
41-turn word-move distinguishable from the pure relabel `m1 Is ▸` only by a
conversational adverb, which is precisely the one-menu-slip the rule exists to
prevent. It is renamed **`All of p3's Turns Are ▸`** and classified attribution,
where its effect belongs. The rule therefore holds with **no exceptions**: *if
the item names speech, words move; if it names a speaker, nothing moves but
labels and numbers.* (Renumbering `m1 → m2` moves no words; joining two codes to
one person moves no words; both stay identity.)

**Localisation contract for the rule** (full string plan: §H, H5). The rule
survives translation only with two supports that must exist before any locale
work: a **pinned turn-noun per locale** in `glossary.csv` — ja **ターン** (the
ratified Quotes term 発言 would otherwise collapse Turn and Quote onto one word),
fr **tour de parole** and ca **torn de paraula** (never shortened to the bare
ambiguous noun), de **Redebeitrag** — and a **translator-facing note** on every
attribution-family key stating the invariant, since Weblate shows one string at a
time. And the trailing-copula items (`m1 Is ▸`, `This Turn Is ▸`) are English
cloze sentences a submenu completes — Korean's enclitic copula and Japanese's
sentence-final copula cannot close them, so the localisation contract is
**label-plus-chooser**, not sentence-plus-completion: locales render them as noun
phrases (ja 「このターンの発言者: ▸」) and the English sentence form is a happy
accident of English.

### B3 · The menu is short because the anchor already carries the scope

> **Status, 6 Oct 2026 — half overtaken, half standing.** What was built for *who a
> speaker is* is not this menu but the **person picker** (§H9 UX iteration 3, §J8): a
> popover with role segments, a per-role list and a new-person row, on the Sessions
> grid, the transcript and probably the dashboard (§J8.7). The `Set Name…` / `m1 Is ▸` /
> `That's Me` / `Role in Session 4 ▸` items of the Sessions-grid row below are that
> picker now. **Still standing, and needed next:** the attribution half — `This Turn
> Is ▸`, `These N Turns Are ▸`, `This Quote Is ▸`, split and merge — and the reach
> rule (a reading surface acts on the thing under the cursor). Those are the
> owner's top-priority jobs (a paragraph credited to the wrong speaker; a moderator
> quote shown as the participant's). Re-check this table against the picker before
> building them. Pixels: `mockups/person-picker-decided-states.html`.

Zones in a fixed order — **name · identity · role · membership · go to** — of
which only the first two vary. Contents are a function of *(what you clicked,
what state it is in)*, so an unnamed participant gets three items and a contested
moderator gets six. A menu that shows six disabled items to advertise a roadmap
is a menu nobody reads.

Because the researcher cannot see the anchor, **wide-reaching items name their
scope in their own text**: `Role in Session 4` versus `Role in All 12 Sessions`;
`This Turn Is` versus `All of p3's Turns Are`. Four words, and it replaces a
confirmation dialog.

#### The same menu, four surfaces

"Adapts to the context" is buildable as a function of two inputs — **where you
clicked** and **what state that object is in** — not as four hand-written menus
that will drift apart.

| Surface | What you clicked | Scope it carries | What it offers |
|---|---|---|---|
| **Transcript** — a segment's badge | one turn, by one speaker | this turn · this speaker in this transcript | `This Turn Is ▸` · `These N Turns Are ▸` (with a selection) · `All of p3's Turns Are ▸` · `Split Turn Here` · `Merge with Turn Above` · name · role · `Not a Speaker` |
| **Quote card** | one published extract | this quote | `This Quote Is ▸` · `Trim Quote…` · `Hide Quote` · `Show in Transcript` |
| **Sessions grid** — a speaker entry | this speaker in this session | this session | `Set Name…` / `m1 Is ▸` / `That's Me` · `Role in Session 4 ▸` · `All of p3's Turns Are ▸` · `Not a Speaker` |
| **People lens** — a row, project scope | this person in this study | the whole study | name · `Role in All 12 Sessions ▸` · `Separate…` *(when contested)* · `Same Person As ▸` · `Part of My Research Team` · `Show All Their Sessions` |
| **People lens** — a row, folder or everyone | this person across studies | across projects | name · `Same Person As ▸` · `Not the Same Person` · `Unlink…` · `Part of My Research Team` |

#### Default reach follows the working mode, not only the anchor

This is the subtle half, and the four-surface table above understates it. The
anchor bounds what is *possible*; the surface says what the researcher is
probably *doing*.

Working down the Sessions grid or the People lens is **sweeping** — housekeeping,
one row after another, expecting each fix to ripple. Sitting inside a transcript
is **reading** — analysis, in the flow of a conversation, noticing one local
thing. Same object, same verb, different default:

| Where you are | What you are doing | Default reach | Worked example |
|---|---|---|---|
| Sessions grid · People lens | sweeping | **the widest meaningful scope** | *"`o2` in s3 is the same Jane as `o1` in s1"* — joins the codes and ripples into every quote in that transcript |
| Transcript · quote card | reading | **the thing under the cursor** | *"that one quote is Sarah"* — this quote, nothing else |

The other reach stays reachable and is never the default. The asymmetry in how
you get there is deliberate:

- **Widening from a narrow surface is a menu item.** Inside the s3 transcript you
  can still say `All of p3's Turns Are m1` — one item down, with its scope in the
  label.
- **Narrowing from a wide surface is navigation.** You do not fix one quote from
  the People lens; you go to the quote. A row that stands for twelve sessions has
  no business offering an action that touches one paragraph.

> **Scoped 1 Oct 2026, for moderator identity.** The wide default was written for
> housekeeping across rows that arrive together. Moderator rows do not: sessions
> land one to three at a time over weeks, and "who moderated this one?" is a
> one-click part of looking at the new session. So a moderator pick defaults
> **narrow on every surface**, the Sessions grid included; the wide case is
> multi-select plus one pick, later, if batches ever hurt. No sweep line offers
> the sweep, because nothing asks (decision 1, corrected).

**And the pattern that reconciles the two**, used everywhere in this design: *do
the narrow thing, then offer the wide one in a sentence.* Fix the spelling, then
"it appears 6 times in the transcript — fix those too?". Name the moderator in
s9, then "Mike is now m2; Martin stays m1 in 1–8". Re-attribute one quote to the
moderator, then "5 more quotes in this session are still credited to p4 — look at
those too?" (the app claims nothing about them; it invites review). The researcher
gets the precise act they asked for, and the app — which has just been handed
strong evidence — offers the sweep without ever performing it uninvited. That is
how a reading surface can default narrow while the underlying error is usually
study-wide.

Four rules generate every cell:

1. **Offer what is meaningful at that anchor; do not disable what is not.** A
   `Turn` item on a sessions-grid entry has no turn in scope, so it is absent —
   not greyed. A contextual menu shows what applies; a menu bar keeps its shape.
2. **One verb, many anchors, scope in the label.** `Role in Session 4` and `Role
   in All 12 Sessions` are the same verb at two altitudes. The researcher cannot
   see the anchor, so the item says it.
3. **State picks within a zone.** Unnamed → `Set Name…`. Guessed → `Confirm
   "Danny"` plus `Change Name…`. Contested → `Separate…`. The zones are fixed;
   their contents are not.
4. **Never offer a no-op.** `Not a Speaker` does not appear on the moderator you
   have just confirmed is you.

The payoff of writing it as a function rather than four menus is that a new verb
lands everywhere it is meaningful at once, and a surface added later inherits the
whole vocabulary instead of re-implementing a subset of it.

### B4 · The bank is the keystone

Naming a moderator should be a **pick, not a keystroke**: *"oh yes, that m1 is
Steve."* The bank is not a new store — `Person` rows are already
instance-scoped — it is a query over rows that exist, ordered by use, with
**Me** seeded from `NSFullUserName()` at the top.

*1 Oct 2026: in v1 there is no bank and no settings UI. **Me** is seeded from the
account name (`NSFullUserName` on the Mac, the GECOS field on the CLI — *not built: v1.1
has no That's Me row in the browser*) and appears
in the picker as `That's Me (Martin Storey)`; it is never applied by inference and
never offered as a match. Settings ▸ General and Contacts are later.*

**Picking a name from the bank is a link, not a copy.** Choosing "Steve
Nakamura" asserts that this `m1` *is* the Steve who already exists — which is
exactly J12's cross-study identity link, obtained at tier 1 as a side effect of
not retyping.

> **Prevention beats reconciliation.** Cross-project linking as previously
> designed is a reconciliation engine: import everything, generate duplicates,
> match names within a folder, propose, confirm, handle transitive chains. The
> bank stops the duplicates being created. What is left is a back-fill for people
> named before it existed — a much smaller feature with no matching algorithm in
> it at all.

The failure mode is picking the wrong Steve, so: never pre-select, never
auto-complete on a keystroke, show a study count beside each name, and keep
**Someone New…** as the visible escape and the safe default.

#### B4 spec — settled by H6, 25 Aug 2026

**The bank holds moderators and observers only. Never participants.** Three
arguments, ascending: hit rate (three or four colleagues recur; a participant
appears once, so every participant row is one to scroll past and one to
mis-pick); §B9 already assumes it (`New Participant…` is a blank field *by
design* while `New Moderator…` offers the bank — an asymmetry that is only
coherent if the bank has no participants); and §B5 forbids it outright — a bank
containing participants *is* the app proposing cross-folder participant matches,
unprompted, in a menu, with no evidence on screen, which is exactly the feature
Everyone scope refuses.

So there are **two lists, and the split is decision 2's line**. The bank is a
**prevention** mechanism for a population where picking is safe — you recognise
your own colleagues. The lens's three scopes are a **reconciliation** mechanism
for a population where picking is *unsafe*: this study alone holds Mary A., Mary
O. and Marrian. Prevention is not even available at participant-naming time —
you are typing off a screener, not recognising a face, and you cannot know the
p-code in front of you was in last quarter's study. (An earlier draft of §E
decision 1 said the returning-Mary join is done "from the bank". That was
imprecise and is corrected above: it is done from the participants already in
the study.)

**Membership is one row per human satisfying all three:** has at least one
`SessionSpeaker` row on this Mac whose role is moderator or observer — the
*union* across projects, never the intersection; has a non-empty name (a nameless
`o2` is a thing you fix, not a thing you choose); and was named by a human or
inherited a platform label — **nothing enters the bank that only a model
believes.** Plus **Me**, pinned above a separator and outside the ordering.

**Bank membership is never a disclosure fact.** Anonymisation stays exactly where
decision 2 left it — the per-session code prefix. The moment bank membership
gates a name in an export, the deleted "research team" flag has grown back
through the side door.

**No group header, ever — and no reserve string held for later.** §I5's proposal
to reuse `Moderators` / `Observers` is rejected on four counts: the grouping key
does not exist per-person (decision 2 names the moderates-some/observes-others
case explicitly, so any derived "most frequent role" is invisible and unstable —
a row silently changing group between two openings of the same menu); it
structurally performs the role-based suggestion decision 2's obligation 2
forbids; it puts a role noun in front of an identity pick, which §B2's rule
forbids; and at four colleagues it is more chrome than content. The deeper reason
is the same one the vocabulary adjudication reached independently: **the set's
only true name is its definition, and a set whose only true name is its
definition should not be labelled.**

**The write path is naming, and only naming.** No manage-people screen in v1, no
"add to bank" affordance, no import. The acceptance test is Jane: name `o1` in
s1 "Jane Smith"; open `o2 Is ▸` in s3; Jane is there showing 1 study; pick her;
the codes join. That requires the bank to be **written through at name time**,
not at project completion.

> **Measured blocker — the bank has no store today, and §D priced it as though
> it did.** `server/db.py:27` gives every project its own SQLite file. `Person`
> is instance-scoped only in the sense of carrying no `project_id` *inside that
> file* — **`Person` rows do not span projects.** `_default_db_url()`'s
> `~/.config/bristlenose/bristlenose.db` exists and is unused. So "a query over
> rows that already exist" is true of the schema and false of the deployment:
> the bank needs the instance DB of [`design-multi-project.md`](design-multi-project.md)
> §2, with its UUID requirement, before it can hold anything. Build it as a
> **write-through instance table**, not a fan-out over per-project DBs — a menu
> must open in one frame, and a freelancer's projects live on drives that come
> and go. Write-through also makes the study counts complete by construction, so
> §B5's "say what it could not see" caveat applies to the lens and not to the
> bank.

### B5 · The lens is the same object, aggregated — at three scopes

Not three filters. The scopes change what a row *is*, and what the app is
**willing to propose**.

| Scope | The question | What the app may propose |
|---|---|---|
| This project | Are these the right people, named and roled correctly? | names and roles — it already guessed them |
| This client (a folder) | Have I met any of them before? | matches, **within this folder only** |
| Everyone | Who do I work with? | **nothing** — cross-folder matching is refused by design |

A consequence worth designing to: **the identity anchor inverts with altitude.**
`p3` identifies a person inside a project and nobody above one, so the People
grid's degradation ladder drops the *code* column first — where the sessions grid
drops the *name* first and keeps the badge.

At Everyone scope the default view is the **roster** (people who recur), not the
table: a lens that opens on fifty-eight rows of one-session participants is a
lens that gets opened once. And any total at that scope must say what it could
not see — half a freelancer's projects live on drives that come and go.

#### B5 spec — reframed by H7 for decision 2, 25 Aug 2026

**The row is one `Person` record, and the scope switch changes which population
is on screen — not what a row means.** Read the middle column downwards and it
never changes. That is decision 2 rendered rather than restated: a moderator or
observer is instance-wide and singular, so their row is *the same object* at
project, folder and everyone scope; only participants are re-populated as the
scope widens, because only for them is "the same Jane, or a coincidence?" a live
question.

Which means the scope control is **not a filter**. A filter narrows one
population; this changes which population you are looking at, and — the part
with teeth — **what the app is willing to propose**: names and roles at project
scope, matches within a folder, and at Everyone scope **nothing at all**.

**The tells table** — the defects only a person-shaped row can show, and every
one rides a mechanism that already exists rather than adding geometry (§B6): a
moderator credited with every session at an impossible word count; a
"participant" appearing in all ten sessions holding 47 quotes; two rows with the
same name and *identical word counts*, which is the double-import tell (§F S17)
and which nothing else in the product can surface. None of them adds a chip, a
dot, a colour or a glyph.

**The degradation ladder inverts, and keeps inverting.** The code column drops
first here where the sessions grid drops the name first — and at Everyone scope
the floor keeps *two* columns, because the anchor widens as the altitude does.

**Everyone scope opens on the roster, not the table**, and the roster is *every*
moderator and observer plus participants who recur — the long tail sits behind a
plain count. Any total there must say what it could not see: half a freelancer's
projects live on drives that come and go.

**The lens does not ship in the export**, and not merely because export mode is
read-only. Read-only is about *verbs*; this is about *rows*. An un-clickable
control is not an unpublished one, and the instance simply is not in the file.

### B6 · Zero-geometry states, and one sweep line

A guessed name is **italic** and nothing else. An unnamed row is empty. Counts
live in a single **absent-when-zero** line under the heading — *"2 people barely
spoke and were never asked a question. Were they observing?"*

*1 Oct 2026, two additions, neither new geometry.* A moderator slot with no identity
renders its code lozenge as **`m?`**, and the lozenge is the control. A slot proposed
by a platform label reuses the shipped AutoCode proposed-badge treatment verbatim
(`atoms/badge.css` `.badge-proposed` + `.badge-action-pill`: dashed border, slow
pulse, the ✗ | ✓ pill on hover); confirmed slots are plain. The count line under the
heading states "N not identified", counts moderators only, is absent when zero, and
asks for nothing. The export carries neither the treatment nor the pill: a proposed
name reads plain there, a null slot reads "Moderator not identified".

No chips, no dots, no per-row marks. With a dozen rows the argument is **not**
that marks are unaffordable — at this scale they would fit. It is that they are
*redundant*: a list a researcher can take in at a glance does not need every row
annotated to make two exceptions findable, and one count line is one translated
string instead of five. Four review agents converged on this independently, on a
larger assumed N; the small-N reasoning reaches the same place by a shorter
route.

### B7 · Say what it cannot do

- Changing a role does **not** re-extract quotes. Extraction has already run; the
  surface offers *Analyse again* and lets the researcher decide, rather than
  silently spending a cloud call and discarding edits.
- A link never moves data between projects. Export is project-scoped whatever the
  links say — and the sheet should say so *before* asking, because the
  researcher's real fear is "will this client see the other client's material?"
- Every question the lens asks needs a recorded **negative** — *Keep as One
  Person*, *Different People*. A prompt that can only be satisfied or postponed
  returns every run and gets ignored, taking the true positives with it.

### B7a · The correction is compound, and classification is not the product

**A non-goal, stated so nobody builds toward it.** An enthusiastic observer — a
senior product person without research training, say — may jump in, ask a run of
questions and state a lot of truths. **From the words alone they are
indistinguishable from a participant**, and no prompt, heuristic or model
improvement changes that: they are behaving like a participant. Bristlenose does
not try to win this, and effort spent making the classifier cleverer here is
effort spent in the wrong place. What the product owes is the *repair*: that the
researcher can say **"that's actually Steve, and he's an observer, not a
participant"** — or, more rarely, "that's a moderator who went rogue" — and have
it stick, in the transcript and in the quotes.

**Which means the everyday correction is compound.** The realisation is one
thought and the fix is two facts: *who* (Steve) and *what* (an observer). A menu
that puts naming in one zone and role in another makes that two trips for the
single most common real correction there is.

**§B9's grouped picker already solves it, and this is the argument for extending
it.** Picking inside **Observers** sets an `o` code; picking `New Moderator…`
mints an `m` — *"grouping is the role"*, so role and identity are chosen in one
gesture. That property was specified for the attribution picker; the **sessions-grid
speaker entry needs it too**, as a single `p4 Is ▸` item opening the same grouped
list, rather than a name zone and a role zone the researcher must visit in turn.

**And the consequence runs deeper than the menu.** §I settled that `kind` **is**
role — the code prefix is role's derived label, not an independent fact. So
changing a role *changes the code*: `p4` does not become "an observer named p4",
it ceases to exist and an `o` code appears. That is decision 1's
renumber-as-a-consequence-of-naming, generalised — and it touches everything a
renumber touches: quote attribution (her quotes were keyed `p4`), the importer's
stable key, and the bracket token in `transcripts-raw/`. It also completes the
J3 story: once she is an `o` code, her comments fall out of the Quotes lens by
membership (§B9) rather than by anyone remembering to hide them.

### B8 · Constraints that came out of triage

Four of the §F verdicts change the design rather than just the backlog. Each is
a rule, not a feature.

- **Spelling propagation must be safe, or it must not be offered.** A name that
  is also a common word — Mark, April, Bill, Summer — turns "fix all 6" into a
  find-and-replace over ordinary prose. So: match on **word boundaries**,
  **show the matches before applying**, let the researcher deselect any, and
  **suppress the offer entirely** when the old name is a common word. This is a
  bug in the first draft of J5's design, caught by triage.

- **Never second-guess a name the researcher set.** No "we heard *Michel*, did
  you mean *Michel*?", no re-derivation over the top, no refill on the next run.
  This is what serves a deliberate pseudonym **without a pseudonym feature** —
  the app has no business knowing the difference, and the honest way to respect
  one is to stop having opinions once a human has typed.

- **Role override has to work in every direction, including down.** The case
  nobody tests is `mN` → `oN`: a client stakeholder who asks leading questions
  gets classified as research team, and the researcher needs to demote them.
  Under §E decision 2 that demotion is also what stops their name being
  published as a team member's.

- **Short-name derivation is best-effort; noticing is the product.** The
  heuristic will get Hungarian, Vietnamese, Icelandic patronymics and Spanish
  double surnames wrong, and v1 does not have to fix that. What v1 owes is that
  a native speaker can **see** the wrong form at a glance and correct it in one
  action. Ambition belongs in the affordance, not the algorithm.

**And one explicit non-goal.** There is no concept of "spoke on behalf of". An
interpreter, a carer, an advocate and a second participant all get their own
participant code, and **the researcher does the interpretation** — that is
analysis, and analysis is theirs. Closing this door is what keeps S1, S2 and S3
from turning into a data-model feature.

### B9 · The attribution picker — grouped, and creatable

> **Status, 6 Oct 2026 — the cast-list shape is overtaken for naming; the quote-card
> half stands.** The picker that shipped for *who a speaker is* does not group
> `p`/`m`/`o` in one list. It has **role segments** that only browse, a list per role
> with each person's own code, and a **new-person row** carrying the next free code,
> which an unknown speaker opens on (§J8.8, §J8.10; built 6 Oct). "Picking a group
> *is* setting a role" is replaced by "a role segment browses; a name picked under
> another role recodes the speaker" (§J7, §J8.10), and `New Moderator…` offering the
> bank is replaced by a plain field that refuses a name someone else already goes by
> (§J8.11) until a type-ahead exists. **What still stands is everything below
> "On a quote card the picker means something different":** a quote is a view onto
> speech, membership is a fact while star and hide are judgements, and moving a
> moderator's words out of a quote takes the card out of the lens. That is the design
> for the owner's two top-priority jobs, and none of it is built. When it is, the
> quote card's picker carries no role segments, because what is wrong there is who
> said the words, not what role the speaker has (§J8.7).

Choosing who speech belongs to is a **cast list**, not a text field, and it is
grouped by kind:

```
Participants
  p1   Sarah Chen
  p3   Mary A.
  p5   Mary O.
Moderators
  m1   Martin Storey — me
Observers
  o1   Jane Smith
  ───────────────────────
  New Participant…
  New Moderator…
  New Observer…
```

Four things this shape buys, none of them decorative:

- **Grouping by `p` / `m` / `o` puts the role in the structure**, so picking a
  group *is* setting a role. Groups run in code order — the order the codes are
  read in everywhere else in the product — rather than by guessed frequency;
  consistency beats a marginal win, and at this scale (§Scale) the whole cast is
  visible at once without scrolling or searching.
- **Code first, then name**, matching the split badge everywhere else. The
  researcher is reconciling against a transcript that speaks in codes.
- **A speaker the system has never noticed must be creatable.** This is the
  inverse of `Not a Speaker` and a genuine gap: diarisation merges two people
  into one code and the second person ends up with **no code at all**, so there
  is nobody to reattribute *to*. `New Participant…` mints `p7` on the spot.
- **Create and name in one action.** The new-speaker step asks for a name
  immediately — a nameless `p7` is a second chore, and the researcher knows the
  name at exactly the moment they are creating them. For `New Moderator…` and
  `New Observer…` the field offers **the bank** (§B4), because a new colleague is
  usually a known colleague; for `New Participant…` it is a blank field, because
  they usually are new.

#### On a quote card the picker means something different

Quotes only exist for participants — extraction skips anything tagged researcher
— so **every quote card carries a `p` code, and there are no `m` or `o` quotes to
pick between.** But the error being fixed is very often exactly that: a quote
attributed to `pN` that was really `m1` or `o4` talking, because the speaker was
mis-filed as a participant (J3) and their asides were mined as findings.

So the targets fall into two kinds with two different outcomes:

| Target | What it means | What happens |
|---|---|---|
| another participant — `p3` → `p5` | genuine crosstalk; the words are a finding, credited wrongly | **re-credit.** The quote survives under a new name |
| a moderator or observer — `p4` → `m1` | **this is not a participant quote** — it is the moderator talking | **the speech is re-attributed, and the card falls out of the lens.** Nothing is withdrawn — see below |

Picking `m1` must not produce "a quote by the moderator", which is a thing that
cannot exist. The group header should say what will happen, at the point of
action rather than in a tooltip afterwards:

```
Participants
  p3   Sarah Chen
  p5   Mary O.
Not a participant quote — re-attributes the speech
  m1   Martin Storey — me
  o1   Jane Smith
  ───────────────────────
  New Participant…
```

#### A quote is a view onto speech, not a copy of it

(A precondition, measured: **no read-time membership filter exists today** —
the lens's participant-only membership is enforced at extraction time alone, so
"the card falls out" is behaviour this work adds, not behaviour it inherits.
§C4 has the evidence.)

If re-attributing a quote only changed the card, the two surfaces would disagree:
the quote would vanish from the Quotes lens while **the transcript went on
showing those words under `p4`**. So fixing attribution on a quote changes the
*speech*, and the disappearance is a consequence rather than the action. Go and
look at session 3 afterwards and the words are the moderator's, which is what
makes the whole thing true.

Three requirements follow:

- **Say it, and offer the way back.** *"Now credited to Martin (m1). This lens
  only shows participant quotes."* plus **Show in transcript** — because the quote
  has not been destroyed, it has moved to where it belongs. Note the sentence
  avoids the word *hidden*: borrowing the curation verb for a membership fact is
  the exact confusion this section exists to prevent.
- **⌘Z restores both halves** — the card and the speech — as one act.
- **Nothing is withdrawn, and no new state is created.** *(Correcting two
  earlier drafts of this section — first that the destination was the existing
  hide verb, then that this was a "withdrawal" with a reason recorded. Both added
  machinery that is not needed.)* The Quotes lens shows **participant** quotes.
  Re-attribute the speech to `m1` and the card is simply no longer in that set.
  There is no flag, no reason field, no pile it moves to — and it is reversible
  for free, because putting the speech back puts the card back.

The Quotes lens has **two orthogonal axes**, and this is the whole point:

| Axis | What it is | Who sets it | State |
|---|---|---|---|
| **Membership** — is this a participant quote? | a **fact** about who spoke | derived from speaker identity | none of its own |
| **Emphasis** — star promotes, hide demotes | a **judgement** about evidence quality | the researcher, deliberately | explicit, and theirs |

Star and hide are one spectrum: the researcher picking and choosing the best
evidence. Speaker identity is not on that spectrum at all. Which is exactly why
the hidden count stays meaningful — **it counts judgements, not facts** — and why
a correction must never be expressed through it.

**The boundary case, and a cost it lowers.** Where the quote spans whole turns,
re-attribution is the same cheap bulk update as the whole-speaker grain. Where
the quote is a fragment inside a longer `p4` turn, moving it means splitting that
turn — but **the quote's own timecode range supplies the split point**, so this
is a mechanical consequence, not the cursor-placement interaction that makes
general turn-splitting expensive. Worth noting because it means the one flavour
of §D step 5 that arrives from a reading surface is markedly cheaper than the
rest of step 5.

**The cast list and the bank are different lists**, and conflating them would be
a mistake. The cast is *speakers in this session* and answers "who could this
speech belong to". The bank is *people across studies* and answers "who is this
person". They meet in exactly one place: creating a new moderator or observer,
where the answer is usually already in the bank.

### B10 · Mechanism prerequisites — decided 25 Aug 2026 (H4)

Two architecture questions the menu could not be specced without. Both are now
answered; neither was decidable from taste.

**Menu host — the vocabulary lives in TypeScript, AppKit renders it.** §B3's
function stays in `frontend/src` and returns a **menu model** (ordered items
carrying label, kind, enabled, action id + payload) — that model is what makes
"a new verb lands everywhere at once" true. Three renderings consume it:

> **Superseded for the picker, 4 Oct 2026** — the owner chose a native popover, not an
> `NSMenu`, because the picker holds a field and a segmented control (§H H9, UX iteration 3).
> What shipped is a `person-picker` message → a transient `NSPopover` → `personPickerChoose`.
> The reasoning below still holds for a menu with no field.

- **In the app**, `onContextMenu` → `preventDefault()` → one new `person-menu`
  bridge message carrying the click point and the model; Swift converts CSS px to
  view px and calls `NSMenu.popUp(positioning:at:in:)`. Picks return through the
  existing `menuAction(_:payload:)` route, so there is **no new reply plumbing**.
  Precedent exists and was verified: `BridgeHandler.swift` already routes
  `open-settings` and `open-feedback` from the web view into native UI.
- **In the browser**, the *same model* rendered as an HTML popover reached by the
  pencil and a keystroke — **not** a context menu, so the user's own right-click
  is never suppressed, which is the genuinely un-native act.
- **A menu-bar mirror**, if wanted, is a third rendering. Note it must be
  hand-mirrored: `MenuCommands.swift` is SwiftUI `Commands` and
  `ProjectSidebarOutline.swift` builds AppKit `NSMenu` — they are already a
  deliberate hand-written mirror, so "one function feeds both" is not available.

Why not a pure HTML menu: it would have to rebuild keyboard traversal,
type-select, submenu hover timing, Escape and focus return, and VoiceOver menu
semantics — and it **cannot escape the web view's bounds**, which bites on a
12-row grouped picker at the app's 700×500 minimum. Also measured:
`NSMenuItem.sectionHeader` has zero uses in the tree today, so the grouped picker
is new work either way — but native it is a property, not an implementation.

**Undo — one stack, and the inline link is a second button for the top of it.**
The sweep-line "Undo" is never a pointer at a past action: it fires the same
top-of-stack undo as ⌘Z and **disappears the instant it stops being the top**.
Out-of-order undo therefore cannot arise, and there is no stale link to reason
about — the hazard is dissolved by the mechanism rather than managed by a rule.
The precedent is Mail's Undo Send banner; it is not a toast, which the house
rules ban outright.

Three consequences worth carrying:

- **Several person verbs are compound and must undo as one act**, because the
  researcher performed one act: naming from the bank both names *and* links;
  renaming a moderator in a session both renames *and* renumbers `m1 → m2`;
  re-attributing a quote moves the speech *and* removes the card from the lens.
  Edit ▸ Undo carries the action name (`Undo Rename Moderator`), never a bare
  "Undo".
- **The mechanism is the `undo-state` bridge channel, not `NSUndoManager`.** The
  Swift half already ships — `MenuCommands.swift` ORs `removalStore.hasPending`
  with `bridgeHandler.canUndo` and already takes its Edit-menu label from the web
  side. What was missing was entirely frontend: `bridge.ts` hard-coded
  `canUndo: false` and nothing posted `undo-state`. This is why §D priced the
  undo bridge as a **step-1 gate**. *Built 4 Oct 2026 — the paragraph below.*

  **Built, 4 Oct 2026.** One stack, page-scoped: `contexts/UndoStore.ts` holds it,
  `components/UndoSync.tsx` posts `undo-state` with whole per-language labels
  (`undo.undo.<action>` / `undo.redo.<action>` — Apple's own "Undo Rename" is not
  a template plus a noun in Spanish, Russian or Norwegian), answers the menu's
  `undo`/`redo`, and in the browser takes ⌘Z / ⇧⌘Z / Ctrl+Z / Ctrl+Y outside a
  text field. On the Mac `BristlenoseWebView` hands ⌘Z to the Edit menu, as it
  does ⌘,. Speaker naming is the first client: `utils/speakerNames.ts`'s
  `nameSpeaker` writes a slot and records its before-state (`full_name`,
  `short_name`, `confirmed` — `/sessions` now reports both names), so undoing a
  confirm returns the name to proposed. A moderator or observer is one
  per-session `PUT`; a participant is `PUT /people` (for `people.yaml`) then the
  flag on the slot, sequenced through one write queue. The stack ends with the
  page — a reload, a Mac project switch (the web view remounts), or a new run.
  The inline sweep-line link is not built.
  One interaction found while truing the undo catalog, open and not fixed in
  0.33.0: the Mac's sidebar removal store (`UndoableRemovalStore`, app-wide)
  outranks the report stack in Edit ▸ Undo, and since 19 Aug a pending removal
  never expires. After any sidebar removal, ⌘Z and Edit ▸ Undo in every window
  undo that removal, and the report's entries cannot be reached from the menu
  or the key until it is undone or superseded. Recorded in
  [`design-undo-catalog.md`](design-undo-catalog.md), the divide's point 2.

  **Star, hide and tag joined the stack the same day** (`QuotesContext.tsx`):
  star, unstar, hide, unhide, add tag, remove tag — one entry per gesture,
  however many quotes it covered. The inverse is the same store call with
  `record` off, over only the quotes the gesture changed: a delta, never a
  snapshot, so a tag an AutoCode accept added since survives the undo. Text
  edits followed: a quote's text (and the card's revert), a section or theme
  title, a description — each records the edits-map entry's previous value, and
  a first edit's undo removes the key. Not on the stack: badge deletes,
  proposal accept/deny, codebook changes.
- **Re-attribution breaks the quote stable key.** The importer's key is
  `(project_id, session_id, participant_id, start_timecode)` and re-attribution
  is not one of `_pinned_quote_ids`' arms — so a re-attributed quote does not
  currently survive a re-import. Either the predicate gains an arm or the key
  stops carrying `participant_id`; §D step 3 owns it.

---

## §C — What falls out

Implementation last, and smaller than it looks. Grouped by the job it serves.

### C1 · Gaps in what exists

| Gap | Evidence | Serves |
|---|---|---|
| **No editor for `full_name` anywhere in the SPA.** The Sessions pencil edits `short_name`; `full_name` appears only as a hover tooltip when it differs | `SessionsTable.tsx:439`, `:192`; comment at `:9` | J6 |
| **No role endpoint.** `SessionSpeaker.speaker_role` is mutable in the DB; nothing exposes it | `design-speaker-editing.md` § What exists today | J3 |
| **No contextual-menu machinery at all.** Zero `onContextMenu` handlers in `frontend/src` | grep | all |
| ~~**No undo.** `NSUndoManager` used nowhere; the `undo-state` bridge channel is dead on both ends; `bridge.ts` hard-codes `canUndo: false`~~ — the channel is live and speaker naming is on the stack (4 Oct 2026, §B10) | `design-undo-catalog.md` § What exists today | all |
| **No recorded name origin**, so a confirmed guess and an unchecked guess are indistinguishable. *4 Oct 2026: the second half is fixed — `session_speakers.name_confirmed` (012) tells them apart; per-field origin is still unrecorded* | `design-html-report.md` § Auto name/role extraction | J7 |
| **No `cleared` state** — a deleted name is refilled by the next run | roadmap; `people.py` `auto_populate_names` | J7 |
| **Anonymisation decides by code prefix**, not by person | `server/routes/export.py` `_anonymise_data` | J13 |
| **No read-time membership filter on the Quotes lens** — extraction is the only gate; a re-credited quote would stay visible wearing an `m` code | `routes/quotes.py` (verified: filters are project + quote-ids only) | J9 |
| **Observer speech is not excluded from quote extraction.** `s09` feeds `full_text()`, which tags every non-unknown role — so an observer's segments arrive marked `[OBSERVER]` — while the prompt's Rule 1 names only `[RESEARCHER]` and never mentions `[OBSERVER]` *(fixed 27 Aug 2026, `deb62808`: Rule 1 names both)*. Exclusion rests on the model generalising from "only extract participant speech" while being shown a tag it was never told about. `participant_text()` exists, filters to `PARTICIPANT`, and **is unused by `s09`** | `s09_quote_extraction.py:231`; `llm/prompts/quote-extraction.md:21`; `models.py:227-240` | J3 |
| **Segment provenance is flattened at import** — intermediates carry `srt`/`vtt`/`docx`/`mlx-whisper`; the importer writes the constant `transcript` on every DB row | `server/importer.py:548` | §D claim 2 |

### C2 · Data that would need to exist

Stated as consequences of §A/§B, not as a schema proposal.

- **Name origin, per field.** One flag cannot carry it: "derived" describes how
  `short_name` was made *from* `full_name`, which is a different axis from where
  `full_name` came from — and the two functions run back to back, so a single
  field ends up reading "derived" for nearly everyone. Needs a value per field,
  plus an explicit sentinel for *never recorded* (every `people.yaml` in the
  field since 14 Jul) and one for *deliberately cleared*.
- **Person-level team membership.** One value per human, governing whose name
  survives an export — as against per-session role, which governs quote
  eligibility and is already modelled correctly. See §E decision 2. One flag
  does two jobs: it also populates the bank's "Your team" group.
- **A use count per person**, to order the bank. Derivable, not stored.
- **A links table** — only for the back-fill, and only after the bank has stopped
  new duplicates being created. Shape, folder scoping, transitivity rules and
  the UUID requirement are already specified in
  [`design-multi-project.md`](design-multi-project.md) §2; do not re-derive them.
- **The code becomes a derived label, recomputed from the speaker→person map**,
  rather than a stored identity — the settled outcome of §E decision 1, and the
  only structural item here. *Made concrete 1 Oct 2026: the map is
  `session_speakers.person_id`, made **nullable** (null is `m?`), plus `state`
  (`proposed` · `confirmed`) and `evidence` (`platform-id` · `platform-name` ·
  `inherited` · `pick`); `persons` gain a per-project `code`, a `uuid`, an
  `origin` and `me`. One Alembic revision on tables that exist; one `Person` per
  identity instead of one per session.*
- ***`people.yaml` is retired as a store (1 Oct 2026).*** Names, identities, the
  per-session map and origin live in the project database like stars and tags,
  which never had a file twin. The pipeline carries *evidence* forward in its
  intermediates (platform labels, heard names, the per-session speaker tags) and
  writes computed stats to an intermediate JSON; **the importer runs at the end of
  every pipeline run**, turns evidence into proposals, and never overwrites a
  confirmed row. A legacy `people.yaml` is read once on the first import after
  upgrade (its `m`/`o` names become inherited-proposed on every session that
  carried the code; participant names come across the same way), then ignored and
  never deleted. The user-facing surfaces that promise an editable file (README,
  the man page, the website's CLI doc, `server/CLAUDE.md` § Names architecture,
  the file's own header) change in the same release. The markdown report and the
  sealed static HTML get no investment: with no file to read they fall back to
  codes, as their missing-file path already does.

### C3 · Surfaces that would need the same component

A person reference is rendered five ways today — `PersonBadge`, the
`bn-speaker-editable-name` cell, the `.speaker-link` in quotes, the
"Moderated by…" prose line, and `theme/js/names.js` in the frozen vanilla tree.
If the affordance is universal, these must become **one component with one
menu**, or the vocabulary will exist on some surfaces and not others. Same class
of problem as the shared-format register in `CLAUDE.md`: one stem, one
implementation, every surface.

### C4 · Quote ↔ person — there is no modelled relationship, only a resolvable path

Measured, not assumed. `Quote.participant_id` is a plain `String(50)` holding a
speaker code, and `Quote.session_id` is a plain `String(50)` holding `"s1"`.
Neither is a foreign key. `TranscriptSegment.speaker_code` is the same. **The
only foreign key to `persons` in the entire schema is
`SessionSpeaker.person_id`.**

```
Person                 (instance-scoped, no project_id)
  ▲ person_id  FK
SessionSpeaker         (session FK · speaker_code · speaker_role · stats)
  ▼ session_id FK
Session
  ▲                                   ▲
  │ session_id: str "s1"              │ session_id FK
Quote                              TranscriptSegment
  participant_id: str "p4"  ──▶ ?     speaker_code: str "p4"  ──▶ ?
       (no FK — resolved by convention)
```

So a quote reaches a person only by `(session_id, speaker_code) → SessionSpeaker
→ Person`, **by convention rather than by the schema**. Four consequences, and
they are not all bad:

- **It is why one-name-per-code is free.** The name lives on the code and
  everything references the code, so renaming propagates to every quote,
  transcript and export without touching a single row that mentions a quote.
  The denormalisation buys the invariant.
- **It is why the `m1` collision can exist at all.** The join key is a string
  that is not unique per person, so nothing in the schema can object.
- **It is why re-attribution is cheap and the "cascade" is not.** Changing who a
  quote belongs to is one `UPDATE` of a string. But changing a *segment's*
  speaker cannot propagate to quotes, because nothing links them — the only
  available answer is timecode overlap, which is why §D step 5 is the expensive
  one and why quote-level and segment-level fixes stayed independent.
- **There is no membership rule at read time at all** — measured, correcting an
  earlier draft that claimed a prefix test. The lens shows every `Quote` row:
  nothing in the read path filters by `participant_id` (verified across
  `routes/quotes.py` — its filters are project and quote-ids only — and all of
  `frontend/src`). Membership is enforced **once, at extraction time**: the
  prompt's "never quote the researcher" rule plus s09's crediting. Consequence:
  §B9's "the card falls out of the lens" is a capability the lens must **gain**,
  not one it has — today, re-crediting a quote to `m1` would leave it visible,
  wearing a moderator's code. The filter is cheap, and its correct key is
  per-session role via `SessionSpeaker`, not a string prefix — which also
  clarifies §E decision 2: **lens membership is a per-session role question**
  ("is this evidence?"), **anonymisation a per-person one** ("whose name may
  travel?"). Different questions, different altitudes, already separable in the
  schema.

### C5 · The person state machine — three lifecycles, deliberately independent

There is none today. Written here as a consequence of §A and §B, and the
load-bearing claim is that **these are separate machines on one object.**
Collapsing them into a single status enum is the trap: a person can be
confidently named and identity-provisional, or a guess and already joined.

**Name — per code.**

```
                    ┌── platform label ──▶  from file
   unnamed ─────────┤
      │             └── model heard it ──▶  guess ──┬── confirm ──▶ confirmed
      │                                             └── change ───▶ typed
      └── researcher types ────────────────────────────────────────▶ typed

   any named ── clear ──▶ cleared        (the pipeline must not refill)
```

Rules the transitions imply:

- **The pipeline may only write into `unnamed`.** It must never overwrite
  `typed`, `confirmed` or `cleared`. This is what serves a deliberate pseudonym
  without a pseudonym feature (§B8).
- **`confirm` changes no value and is still a real transition** — which is
  precisely why the write payload has to narrow to one entry. A whole-map `PUT`
  cannot tell "I read this and it is right" from "nothing changed", and that is
  why "I checked this" was unrepresentable until 4 Oct 2026, when migration 012
  gave each slot `name_confirmed`.
- **`cleared` must be sticky**, or deleting a name gets it refilled on the next
  run and the researcher is told they typed the name they deleted.
- Only **`guess`** invites action. The other five states are places to rest,
  which is why one italic treatment and one count line covers the whole machine.

**The moderator slot — per session (added 1 Oct 2026).** Separate from, and
beneath, the identity machine: it answers "who moderated *this* session", and only
a platform or a person may answer it.

```
   null ── platform label · inherited by migration ──▶ proposed ── ✓ · pick · That's Me ──▶ confirmed
    ▲                                                     │                                    │
    └──────────── ✗ · Not Identified ─────────────────────┘        re-pick (change of mind) ◀──┘
   null ─────────────────── pick · Someone New… ────────────────────────────────────────▶ confirmed
```

Rules: `null` renders as `m?` and is a legitimate resting state (moderators hold no
quotes, so the findings are untouched and the export says "not identified"). A
**heard** name is a hint on a null slot, never a proposal — Whisper's "Kerri" is
exactly the error the researcher corrects in the Someone New… field before an
identity exists. A platform label proposes; a label with a participant id, or a
distinct display name within one study, mints the identity it proposes. Absent on
purpose: null → anything by inference, proposed by a hearing, any transition from
the signed-in account, a re-run touching a non-null slot. Observers share the
machine (`o?`).

*Superseded in part 6 Oct 2026 (§J8, answer 1): a speaker who plainly introduces
themselves ("hello, I'm Mike Jones, an assistant manager at Foo") now proposes a
name and creates a person, shown dotted until a human says yes. A name that is
merely heard elsewhere in the conversation stays a hint.*

**Identity — per code, relative to other codes.**

```
   provisional ──┬── named from the bank ─────▶ joined to an existing person
                 ├── named with a new name ───▶ its own person
                 └── "different people" ──────▶ not-same edge recorded

   joined ── unlink ──▶ provisional

   one code, two names heard ── rename in a session ──▶ split: a new code minted
```

Both escapes are entered by **naming** (§E decision 1), and both negatives —
`not-same`, `keep as one person` — are recorded states rather than dismissals,
or the prompt returns every run.

**Role — per session, not per person.** `participant ⇄ moderator ⇄ observer`,
freely, no terminal state, and it must work in the demoting direction (§B8). Its
one consequence is that changing it does **not** re-extract quotes.

**Membership — per person.** `team ⇄ not team`. Set once, rarely changed,
governs whose name survives an export (§E decision 2). Deliberately *not* derived
from role, because a client-side observer is not team and a colleague interviewed
in session 9 still is.

---

## §D — Sequencing

Ranked by how often a researcher needs it. Nothing here is a big bang; each step
is independently useful and independently shippable.

| Step | The sentence | How often | Cost |
|---|---|---|---|
| **1** | "m1 is me." · "That m1 is Steve." · "p4 is Jane Smith." · "Jane is an observer." | **Every session, every path** — 10–30 times a study | **Small — plus two real prerequisites, and one item that does not belong here (J1: role is a recode, so it belongs with step 4).** `PUT /people` exists; role needs one endpoint; "that's me" needs no typing. But **the bank has no store** — `Person` rows do not span projects today (§B4 spec), so it needs the instance DB of `design-multi-project.md` §2 first; and `NSFullUserName()` has zero uses in `desktop/`. But every step-1 act is drawn with an Undo, and the undo bridge is dead (`canUndo` hard-coded false, `NSUndoManager` used nowhere) — **the undo contract is a step-1 gate, not a parallel workstream** (§H, H4). *4 Oct 2026: both done — the Mac picker's That's Me reads `NSFullUserName()`, and undo on speaker naming is built (§B10); the bank is still unbuilt* |
| **2** | "Michel Hurlly is Mickael Hurley." · "Call him Mike." · "Yes, that guess is right." | Every study with raw audio | **Medium.** Name origin per field, a `cleared` state, a narrowed write payload, and a `full_name` editor |
| **3** | "That quote was Sarah, not Jane." | A few times a study — **and it is what gets published** | **Small-to-medium.** The speech moves (§B9): a whole-turn quote is one segment update; a fragment inside a longer turn is a turn split whose split point the quote's own timecodes supply. ⌘Z spans card and speech. Plus the lens needs the membership filter it currently lacks (§C4) |
| **4** | **What naming implies.** "p6 is the same Mary as p3." · "The moderator in s9 is Mike, not Martin" → Mike becomes `m2` | Follows from step 1 — **no separate UX, no blocking decision** | **Medium.** Speaker→person remap, moderator renumber, stats recompute. All bookkeeping behind an act the researcher has already performed. *1 Oct 2026: for `m`/`o` the renumber is gone — "the moderator in s9 is Mike" is one row (`session_speakers(s9).person_id`), and the v1 package in §H H9 ships it with step 1* |
| **5** | "That whole paragraph was Sarah." | Concentrated on raw audio | **Largest.** Batch segment endpoints, split/merge, word-timing division, stats recompute, the unsolved quote cascade |
| — | "This is the same ward sister from round 1." | Mostly **prevented** by step 1's bank | Shrinks to a back-fill |

Three claims this ordering makes, each falsifiable:

1. **Step 1 is most of the value and almost none of the cost.** Naming,
   self-identification and role are relabels: no typing beyond a name, no data
   moved, no consequence beyond the next analysis.
2. **Attribution is deliberately late** — and this was the claim most likely to
   be wrong, so it was measured (25 Aug 2026, H2). **The ordering stands; the
   confidence in it does not.**

   Measured over 34 project output directories on the maintainer's machine
   (169 sessions, 28,979 segments), reading `TranscriptSegment.source` from
   `<output>/.bristlenose/intermediate/session_segments.json` — *not* the serve
   DB, which carries no provenance at all (`importer.py:548` writes the constant
   `source="transcript"` on every row). Script:
   `scripts/measure-transcript-sources.py`, metadata only.

   | | by segment | by session |
   |---|---|---|
   | platform-diarised (`vtt`) | 1,876 · **6.5%** | 33 · **21.4%** |
   | locally transcribed (`mlx-whisper`) | 27,103 · **93.5%** | 121 · **78.6%** |

   Deduped to one project per distinct corpus, by session it is 42% / 58%. **Use
   the session denominator** — one session is one recording is one attribution
   problem — and note a platform `.vtt` yields far coarser segments than Whisper
   does for the same audio, so the segment share overstates the local side.

   Two findings sharper than the ratio. **Every platform segment on disk carries
   a speaker label and every local one does not** (`vtt` 1,876 labelled;
   `mlx-whisper` 23,056 unlabelled) — which is the real proof the buckets mean
   what they claim. And **there is not one `docx` segment anywhere**: the Teams
   and Meet path this claim rests on has never produced a saved project run, so
   this corpus can neither confirm nor refute it on its own terms.

   **The ordering is held, deliberately.** The corpus is the maintainer's own
   trial runs, demos and acceptance fixtures — raw media is the harder path, so
   it gets tested more, and nothing here separates *researchers mostly hand us
   recordings* from *the maintainer mostly tested recordings*. The right next
   move is instrumentation, not inference: emit the per-run source distribution
   into the pipeline summary so every future run reports its own mix without
   anyone opening a project folder, and decide the ordering on cohort data.
3. **Naming is the mechanism; the rest is bookkeeping that follows from it.**
   What began as three separate features — cross-study linking, merging two codes
   that are one person, and separating one code that is two people — are all
   consequences of a single act, if that act is built as an **identity
   assertion** rather than a string edit. Pick "Mary" from the bank for `p6` and
   the codes join; rename session 9's `m1` to "Mike" and he becomes `m2`; pick
   "Steve" and the cross-study link exists. Build naming as a `setString`, and
   all three come back later as features.

---

## §E — Decisions: one settled, one owed

Neither was a coding problem; both are product calls. Decision 1 is **settled**
(below, with the reasoning preserved); decision 2 is the one still owed. *(Settled 25 Aug 2026 — below.)*

### Decision 1 — **settled 24 Aug 2026.** Identity lives above codes, and the two namespaces fail in opposite directions

The question as originally posed — *does a code name a person or a slot?* — was
the wrong question, and the answer is neither. A speaker code is a
**globally-numbered speaker slot**, sessions are `s1`, `s2`…, speakers are `p1`,
`p2`, `m1`… , and **identity is a layer above both**. Neither namespace needs
re-specifying, because each is already right for its own common case:

- **`p` codes never collide, and over-fragment.** The pipeline threads a counter
  across sessions, so `p3` and `p6` are always different codes — but the same
  human returning for a second session on a different aspect gets both.
  **One human, several codes, and that is normal.** `p3` Mary, `p4` Marrian,
  `p5` a *different* Mary, `p6` the first Mary again: all fine and reasonable
  scenarios, none of them a defect.
- **`m` and `o` codes do both**, because the number comes from *within-session
  ordering*, which has nothing to do with identity. They **over-collide** — the
  counter restarts each session, so `m1` is `m1` everywhere, which is **the right
  answer in about 95% of studies** because there is usually one moderator, and
  wrong only when there are two. And they **over-fragment** — Jane observes
  session 1 alone and is `o1`; she observes session 3 alongside Tom, who speaks
  first, and she is `o2`. *Same person, two codes, and nothing about her
  changed.* (An earlier draft of this section said `m`/`o` never fragment. That
  was wrong; the ordering-based numbering makes both failures available.)

So what is owed is **one escape per direction**, and both are reached by the same
act — **naming**:

| Direction | Symptom | What the researcher does | What the app does |
|---|---|---|---|
| over-fragmented (`p`) | `p3` and `p6` are the same Mary | names `p6` by picking Mary from **the participants already in this study** | joins the two codes to one person |
| over-fragmented (`o`) | `o1` in s1 and `o2` in s3 are both Jane | names `o2` by picking Jane **from the bank** | joins them; Jane is one code across the study |
| over-collided (`m`) | `m1` is Martin in s1–s8 and Mike in s9 | opens s9 and renames its `m1` — **"Mike, not Martin"** | **`m1` in s9 becomes `m2` Mike** |

So **all three namespaces need the join, and only `m`/`o` need the split** — and
every row of that table is the same gesture: name the person in front of you.

**The renumber is not a design choice — it is the only representable outcome.**
A name belongs to a code and a code has one name everywhere (§0). So "session 9's
moderator is Mike" *cannot* mean "`m1` is Mike in session 9 and Martin
elsewhere" — that sentence has nowhere to live. The only way the system can
express it is to make Mike a different code. Renumbering falls out of the name
model; nobody has to decide it.

The same reading disposes of the rejected alternative. **The `m1` collision is
not a bug in the name model — it is the name model working correctly on a code
that names two people.** Rekeying `people.yaml` by `(session, code)` would have
fixed the symptom by *breaking the invariant*, allowing one code to carry two
names and quietly making "what is p4 called?" a question with more than one
answer. Fix the code, and the name model is already right.

Two consequences that change the plan:

1. **Renumbering is a consequence of naming, not a separate verb.** The
   researcher does not think "separate m1 into two people" — they think "the
   moderator in session 2 is Mike". The app notices that `m1` is Martin
   elsewhere, concludes this is a different person, and renumbers. The
   `Separate…` sheet stays for the case noticed at the aggregate level, but it is
   the secondary path, not the primary one.
2. **Never auto-merge on name equality, even inside one study.** `p3` Mary and
   `p5` Mary are routinely two different people. Name equality is not evidence
   at any altitude — which is the same rule already applied across folders, now
   confirmed to hold within a single study too.

Codes stay study-unique and get renumbered when identity diverges, which is
Option A of the original fork — reached by a much cheaper route than the sheet
it was first drawn with.

> **Corrected 1 Oct 2026 — the `m`/`o` half.** The reading above kept the
> per-session `m1` slot and made the escape a renumber. The owner's objection,
> argued through the storyboard
> ([`mockups/moderator-identity-failure-states.html`](mockups/moderator-identity-failure-states.html)
> Part 5b), is that a code on screen is a claim: `m1` on every session says
> "these are one human", `m1 m2 m3` says "these are different humans", and with
> no evidence both are unwarranted. The honest third rendering is **no claim**:
> a session's moderator slot is **`null`** until a platform label proposes an
> identity or a person picks one, and renders as **`m?`**. Identities are
> minted on that evidence or that pick, numbered in identification order, never
> reused. The per-session `[m1]` token in `transcripts-raw/` stays as written and
> becomes a within-session tag, which answers §J4's render-time question for
> `m`/`o`. The participant half of this decision is unchanged: `p` codes are
> per-session slots joined by naming, because the quote stable key carries
> `participant_id`.
>
> Three rules follow. **Nothing infers and nothing asks**: no "looks like you"
> offer, no confirmation prompt; `That's Me` is a menu item, and a proposed
> badge that is never touched reads correctly for ever. **Evidence tiers**: a
> platform participant id mints; a platform display name mints one identity per
> distinct name within a study (a recorded carve-out from "never auto-merge on
> name equality", because a tenant's account label is not a name the model
> heard); a researcher's pick asserts; an LLM hearing is a hint and never mints.
> **Reach is narrow**: a pick names one session; the common case costs one click
> per new session on the day it lands, which is cheaper than the habit a wide
> default breeds. The renumber path, the `Separate…` sheet as a primary verb and
> the `(session, code)` rekey are all gone; the rekey's rejection stands for the
> reason it always had, since the file it would have reshaped is itself retired
> (§C2).

### Decision 2 — **settled 25 Aug 2026.** The line is the participant line, not the team line

Today `_anonymise_data` blanks `p*` and preserves `m*` and `o*`. **That mechanism
is correct and stays.** What was wrong was the *rationale* written around it, and
the rationale is what the three consequences hung on.

> **The ethics of anonymisation apply to participants, not to colleagues and
> collaborators.** A **participant is the source of the data — the subject of
> the study**, and that is the whole test. Everyone else — moderators,
> observers, client-side product managers, agency contractors, designers,
> note-takers — is *doing or collaborating on* the study. They are named.
> Participants are not. That boundary is binary, it is the only non-porous line
> in the model, and a speaker code's prefix already encodes exactly it.

Two asymmetries hold the line up, and they are what the test is really reading:

- **Knowledge.** The study-conducting side knows the objectives, the discussion
  guide, and often all of the data. A participant knows what has been shared
  with them.
- **Control.** Participants *respond* to questions from moderators and
  observers. They do not direct the session.

**And observers are never a data source — categorically.** Most say very little;
many are **completely silent and never enter the transcript at all**, so the
observers the product can see are the minority of the observers who were
actually there. When one does speak — a question, a statement, a comment — they
speak **as a collaborator of the moderator**, with the goals of the project in
hand. Their words are therefore moderator-class speech: never evidence, never a
quote.

And one thing the line explicitly does **not** read: **commercial relationship.**
A participant may be paid an incentive; a moderator may be salaried or on
contract; an observer may be a volunteer; the work may sit in an agency, a
university or a company. None of it bears on the classification. Anyone reaching
for "who is on our side" or "who is paid by whom" has picked up the wrong test —
which is precisely how the rejected "research team" framing went wrong.

> **Settled 25 Aug 2026: there is no collective noun, and the product does not
> need one.** Ship the rule — *"participants are anonymised; moderators and
> observers are named"* — and where a surface structurally needs a label rather
> than a sentence, **enumerate**: two headings, **Moderators** and **Observers**,
> the same pair §B9's picker already uses.

The evidence, and it is unanimous. **Every governing framework names the subject
side precisely and enumerates the other side; not one has a collective noun for
it.** Measured across the MRS Code of Conduct (23pp), the MRS Observers guide
(21pp) and the ICC/ESOMAR International Code (18pp): *research team* 0/0/0,
*insider* 0/0/0, *investigator* 0/0/0 — against *participant* 63/91/1. That is
structural rather than an oversight: the subject side is the side carrying
protections, so it is the side that needs defining; the other side is defined by
*responsibilities*, which differ per role, so the codes list the roles instead.

The MRS definition, arrived at independently, is very nearly this document's:
**"A participant is any individual or organisation from or about whom data is
collected."** The data-source test, with commercials excluded by construction.
And the MRS Observers guide corroborates the `o` prefix being broader than "our
side" — it explicitly requires client-side observers to be presented as clients,
refusing to collapse them into the practitioner category.

The category is also a **closed set of exactly two members**, which a collective
noun is dominated by naming. Under this repo's own "no jargon without inline
explanation" rule, a coined noun would have to carry the gloss *"moderators and
observers"* at every first use — costing its own definition *plus* the
enumeration it was meant to replace, in all 21 locales.

**Candidates killed, so nobody re-proposes them.** *insider* — an established
term of art in qualitative methods meaning a researcher who *shares the community
being studied*, so it already means something else. *investigator* — a
regulatory status a client-side observer does not hold, and the identical string
to the shipped `researcher` value in es and ca. *facilitator* — byte-identical
to the shipped Moderator string in de and ko. *collaborator* — ja 研究協力者 and
ko 연구 협력자 are the standard ethics-committee terms for research
**participants**, so it inverts the line in the two locales where that is hardest
to spot. *contributor* — Dovetail ships it for a team seat and UserTesting for
the person being studied. *study team / staff / personnel* — encode employment,
which the test explicitly excludes. *back room / front room* — genuine
practitioner vocabulary for exactly this set, and rejected anyway: spatial,
excludes the moderator, untranslatable.

**Held in reserve: `non-participant`,** as a label only and never in prose, if a
fourth non-participant role ever forces a single word. It is collision-impossible
by construction and natural in all eight locales screened. Rejected as the
primary answer because it defines by negation — which is exactly what the
definition above declines to do. One prerequisite if it is ever taken up: **ko
currently ships two participant nouns** (참여자 and 참가자, split across
`enums.json` and `common.json`), and any derived form would inherit and surface
that split. Worth fixing regardless.

So the proposal to move naming onto a person-level "research team" flag is
**rejected**, and the reason is that it named the wrong distinction. A
client-side observer is emphatically *not* on the research team — and is
*still named*, because they are not a subject. "Team" was never the operative
category; **not-a-participant** is.

What follows, and what the three consequences become:

- **Correcting a role no longer changes who is published.** `p → o` moves Jane
  across the participant line, which is precisely what the correction *asserts*:
  she was never a subject. The disclosure change is the point, not a side
  effect. **J3's observer sweep is therefore unblocked** — it was gated on this
  decision and is now free to ship. **But it did not yet do the other half of
  its job** *(closed 27 Aug 2026, `deb62808` — the prompt now names `[OBSERVER]`)*: correcting `p → o` retags her segments `[OBSERVER]`, and the
  extraction prompt handles only `[RESEARCHER]` (§C1), so on the next analysis
  her collaborator-comments may be mined as findings again. The prompt does say
  "participant" twice, so this is a weakened guard rather than an absent one —
  but `[OBSERVER]` is a tag it never names. The cheap fix is naming it alongside
  `[RESEARCHER]`; swapping `s09` to `participant_text()` is the structural one
  but drops the role tags Rule 5 needs for `researcher_context`.
- **The client-side observer is named, deliberately.** In an exported report you
  may see an observer's clarifying questions attributed in the transcript, and
  see them in the people list. That is correct: they are a colleague or a client
  colleague, not a research subject.
- **You will never see them in the Quotes lens**, because they are not a
  participant. This is §B9's membership rule, and it is the same fact doing both
  jobs — one boundary, two consequences.
- **A person with two roles across sessions is no longer treated two ways**,
  because both of their roles sit on the study-conducting side. A researcher who moderates
  some sessions and observes others is named throughout.

Two obligations this creates rather than removes:

1. **The participant leaks still need closing.** `role` (the LLM-extracted job
   title) survives anonymisation on `p*` entries today, against
   `design-export-html.md:264`'s explicit "Role titles removed when anonymised";
   and `/sessions`' top-level `moderator_names` / `observer_names` lists are
   never touched by `_anonymise_data` at all. Those are participant-side and
   doc-contradicting respectively — both in scope, neither settled by this
   decision.

   **And the hint the researcher actually reads is wrong at HEAD**, independently
   of anything decided here: `export.anonymiseHint` says *"Moderator names are
   preserved"* — naming moderators and silently omitting observers, who are
   equally preserved. A researcher ticking the box is told less than the truth
   about whose names travel. The replacement, which introduces no new term and
   reuses two nouns already translated and native-reviewed across the locale set:

   > **"Strips participant names from metadata, filenames, and speaker labels,
   > leaving codes (p1, p2). Moderators and observers keep their names. Names
   > spoken inside quotes are NOT removed."**

   The checkbox label above it — "Remove participant names from labels" — is
   already correct and needs no change: it names the participant side alone,
   which is the whole pattern.
2. **Being named is not being a moderator.** An observer is named, but when the researcher
   sets a role to *moderator* the bank must not auto-prompt observers at the top
   of the list. Which side of the participant line you are on governs *disclosure*; moderating history governs
   *suggestion order* (§B4).

### One list of them, three scopes for participants

Settled in the same pass, and it is what §B5's three scopes are actually for.

**Moderators and observers are instance-wide and singular.** Everyone who is not a participant —
across every project on this Mac — is one set, modelled as one record per human. *That* Jim Smith either is or is not *this* Jim Smith, and that
is a real-world truth the product represents once. Bristlenose deliberately does
**not** model which observer was on which project for which client: a researcher
may wear a moderator hat in some sessions and an observer hat in others, and
contractors may be agency-side or client-side. None of that changes the
disclosure answer, so none of it is modelled. Folder proximity stays available as
a *UX clue* later — surfacing the observers and moderators from a client's
earlier projects nearer the top of a list — but that is ordering, not identity,
and it is a future concern.

**Participants get three nested sets**, because the identity question is real at
each altitude and nowhere else:

| Set | Why it exists |
|---|---|
| the participants in **this project** | a study is a thing; this is the cast |
| the participants across **this folder** (a client, or a product) | the same Jane Smith may be re-recruited across a client's studies — is it her, or a coincidence? |
| the participants **ever** | a great participant re-used across different clients raises the same question, one altitude up |

That is the *whole* justification for the People lens's three scopes, and it
applies to participants only. Moderators and observers need no scope switch:
there is one list of them, always.

---

## §F — Speculative register

Triaged 24 Aug 2026. **Verdict is the product owner's; the rest is the original
speculation, kept so the reasoning behind a "no" stays visible.** Four rows were
not reached and are flagged as such rather than silently assumed.

Status vocabulary: **v1** (in scope) · **v1 — no new mechanism** (served by
something already planned) · **already handled** · **deferred** · **not ours**
(workflow, not product) · **split** (different answers either side of the
participant line). No row now reads *untriaged*.

| # | Scenario | Verdict | What was decided |
|---|---|---|---|
| S1 | An **interpreter or signer** is present | deferred | Not v1. When it comes, S2's mechanism serves it |
| S2 | A **carer, advocate or family member** answers for the participant | **v1 — no new mechanism** | They get their own participant code, separate from the person they are advocating for. **The researcher does the interpretation** — the app does not need a concept for "spoke on behalf of" |
| S3 | **Two participants in one session** — a dyad | **already handled** | Separate participant codes, correctly, today |
| S4 | The **same participant in two sessions** of one study | **v1 — no new mechanism** | **Normal, not a defect.** `p3` and `p6` are both the first Mary, back to talk about a different aspect. Resolved by naming `p6` from the bank — see §E decision 1 |
| S5 | A **pilot or dry run** with a colleague | **not ours** | Researchers already solve this by workflow: a dummy project, or code them `pN` and simply not draw on their quotes. Often deleted after initial processing so they do not skew metrics. **No product verb needed** |
| S6 | A **name that is also a common word** — Mark, April, Bill | **v1** | "Quite likely." Changes the design of step 2's spelling propagation — see §B8 |
| S7 | **Name order beyond CJK** — Hungarian, Vietnamese, Icelandic, Spanish | **v1 — lowered ambition** | Do not try to be perfect automatically in v1. **Make it easy for a native speaker to notice and fix** — the affordance matters, the derivation does not have to be right |
| S8 | A person's **name changes between waves** | **split — settled 25 Aug 2026** | **Participants: not ours.** A participant who renames themselves *chose* to break that identity; reconnecting it is not Bristlenose's call, and it is not material to most findings. No name history, no auto-reconnection — they are simply two people, and the researcher may link them by hand if they want (whereupon the current name shows everywhere). **Moderators and observers: yes, retroactively.** A colleague who marries and wants to be known by their married name gets the edit, and it changes their representation in historical studies — because they are *one instance-wide record*, so there is one current name and it propagates. Rendered surfaces update; `transcripts-raw/` keeps what the platform supplied, as provenance |
| S9 | An **AI notetaker bot** appears as a speaker | **v1 — no new mechanism** | Expected to be common, and **usually silent**. Sufficient that the bot is *named*, so a human notices it; `Not a Speaker` removes it |
| S10 | A **stakeholder who behaves like a moderator** | **v1 — no new mechanism** | "Occupational hazard, not our responsibility." They are correctly an observer, so the app must support **overriding `mN` → `oN`** — the role change in the demoting direction. Its disclosure consequence lands on §E decision 2 |
| S11 | **Two moderators in one session** — lead plus apprentice | **already handled** | `assign_speaker_codes` (`s05b:450-456`) increments `mod_counter`, so `m1` + `m2` in one session works today and is pinned by `test_two_researchers` (`tests/test_moderator_identification.py:87-89`). Both sit on the same side of the participant line, so decision 2 treats them identically. The only residue is the "Moderated by …" prose line, which dedupes by *name* — a known-wrong render that §11c already owns |
| S12 | Someone **joins late, or leaves and returns** | **v1 — no new mechanism, but a real bug found** | The identity half is already the settled over-fragmentation case: a returning speaker gets a second code and naming from the bank joins them (§E decision 1). **But the measurement surfaced a genuine defect**: the LLM splitter samples at most ~8 minutes (`s05b:235`) and the boundary loop (`:282-292`) leaves `current_label` unchanged past the final boundary — so on Whisper audio, *everyone who first speaks after the sample window is credited to whoever spoke last in it*. A late joiner is not merely mis-coded; their speech is attributed to someone else. That is attribution, not identity, and it belongs with §D step 5 |
| S13 | A **silent observer or note-taker** — present, never speaks | **deferred, and commoner than it looks** | Not an edge case: most observers say very little and many never enter the transcript at all, so the observer rows the product shows are the minority of the observers who were there. Confirmed unrepresentable: speakers are the only people the model has, and `routes/data.py` exposes only `GET`/`PUT` on `/people` — there is no create-a-person endpoint, so a non-speaker cannot exist. They sit on the study-conducting side under decision 2 and so raise no disclosure question; what they raise is a *consent record* question, which `design-cloud-import.md:1107` already names. Out of scope until something needs to record presence rather than speech |
| S14 | **Two participants with the same name** | **v1 / deferred** | **Two different Marys in one study is normal and needs no resolution** — different people, different codes, correct as-is. The only work is telling them apart on screen: manual override of the short name, **v1**. Two *completely* identical names: **deferred**. And the standing rule — **never auto-merge on name equality, at any altitude** |
| S15 | A **deliberate pseudonym** in sensitive research | **v1 — no new mechanism** | "Just go with it, respect it." No special state. The constraint this implies is in §B8 |
| S16 | A **focus group** — six to eight speakers | deferred | "Not v1, but yes" |
| S17 | The **same recording imported twice** | **v1 — open question** | "This will happen — how to flag?" A proposal follows |
| S18 | **Two people sharing a project folder** over Dropbox | deferred | Not a v1 problem |

### S17 — flagging a double import

The likely path is now the common one: download the meeting from Teams *and*
have the local recording, or import a folder twice. It is a **session** duplicate
that the researcher notices as **duplicate people**, which is why it surfaced
here.

**Detect at import, not later** — before duplicate person rows exist. Ranked by
signal against cost:

1. **Start time plus duration.** Two sessions starting within a couple of minutes
   of each other and running to within a few seconds are the same meeting. Both
   values are already recorded, the check is free, and it catches the
   cross-source case that a file hash cannot — a Teams download and a local
   recording of one meeting are never byte-identical.
2. **Platform meeting id**, where cloud import supplies one. Certain when
   present, absent for local recordings.
3. **File content hash.** Only catches the same file copied twice. Cheap enough
   to keep as a confirmation, useless on its own.

The affordance is one sentence at import: *"This looks like a session you already
have — Ward handover #3, 14 Jan, 42:10."* with **Import Anyway** and **Skip**.
Two answers, no dialog chain.

The fallback, when one slips through: at project scope the People lens shows two
rows with the same name and **identical word counts**, which is a tell nothing
else produces. Worth surfacing, but it is a repair, not a guard.

**This design belongs in session management, not here** —
[`design-session-management.md`](design-session-management.md) owns import
identity. Recorded in this register because the symptom is a people symptom;
the mechanism is not.

## §G — Related docs

Pointers, not summaries — each of these owns its material and this doc must not
restate it.

- [`design-transcript-speaker-editing-roadmap.md`](design-transcript-speaker-editing-roadmap.md)
  — the eleven layers, and **§11c owns the moderator-code collision**, its
  eight-reader list, and why it was not fixed in place
- [`design-speaker-editing.md`](design-speaker-editing.md) — the four transcript
  operations, the Dovetail model, and the quote-cascade options
- [`design-speaker-role-detection.md`](design-speaker-role-detection.md) — why
  role detection fails on non-UXR formats, and what was done about it
- [`design-multi-project.md`](design-multi-project.md) §2 — the person identity
  model: links table shape, UUID requirement, folder scoping, transitivity
- [`design-export-html.md`](design-export-html.md) — the anonymisation boundary
- [`design-undo-catalog.md`](design-undo-catalog.md) — the five ownership domains
  and why ⌘Z does not work here yet
- [`glossary.md`](glossary.md) — **adjudicated 25 Aug 2026 (H1)**: rows now exist
  for *moderator*, *participant*, *observer*, *speaker* (Identity & privacy) and
  *turn* (Core research concepts). The sense boundary is recorded rather than
  merged — **moderator** is the person who ran the session, **researcher** stays
  correct for the tool's user, and the stored enum value `researcher` is
  internal-only (renaming it would break the `[RESEARCHER]` transcript
  round-trip). [`glossary.csv`](../bristlenose/locales/glossary.csv) pins a
  turn-noun in nine locales and the ja *Observer* drift is corrected. Still owed:
  the wording for person-level team membership and the job-title field's label —
  both owner calls, §H
- [`mockups/moderator-identity-failure-states.html`](mockups/moderator-identity-failure-states.html)
  — **1 Oct 2026, a code-truth report and, in Part 5b, the decision record**: the
  `m1`/`o1` collision drawn frame by frame as it ships (sessions grid, the pencil
  that opens twelve editors, the export, the MCP roster, the re-run that spreads a
  correction); D1–D4 draw the rename-renumbers mechanism this doc carried until
  1 Oct; E1–E8 draw route C as decided (the slot states with the shipped
  proposed-badge treatment, the six-session study, the pick, Someone New…, change
  of mind and rename, the export and MCP with a null slot, the migrated study, the
  two machines); a gap register measured against this doc, and the challenges

---

## §H — Work packages, sequenced

*The continuation plan: planning, architecture and UX only — implementation
stays last, per this doc's own principle. Each package is sized for one focused
session and executable from its row plus the named reads; H0–H3 have no
dependencies and can run in any order or in parallel. Derived from a ten-agent
review pass (25 Aug 2026: 57 confirmed findings, the mechanical ones fixed the
same day — see changelog) merged with an independent decomposition.*

| # | Package | Goal | Closes | Produces | Depends on |
|---|---|---|---|---|---|
| **H0** ✅ | **True the neighbours** *(done 25 Aug 2026)* | Remove the head-on contradictions the settled decisions created in older docs | — | [`design-transcript-speaker-editing-roadmap.md`](design-transcript-speaker-editing-roadmap.md) §11c gains a dated superseded note — the `(session, code)` rekey was considered and **rejected** by §E decision 1 (renumber-on-rename needs no `people.yaml` reshape; the eight-reader list was enumerated for the rekey and mostly dissolves); its Layer 4 drops "without touching the transcript" and defers to §B9; [`design-speaker-editing.md`](design-speaker-editing.md)'s "B first" recommendation gains the §B9 two-outcome semantics; [`design-multi-project.md`](design-multi-project.md) §2 gains a status note demoting suggestion-driven linking to the back-fill; [`design-undo-debt.md`](design-undo-debt.md) gains a forward pointer | — |
| **H1** ◑ | **Vocabulary adjudication** *(mostly done 25 Aug 2026; four owner calls open — see below)* | Settle every word the design will put in front of a user, before any string exists | Is the user-facing word moderator or researcher (four senses of "role" coexist); the per-locale **turn-noun** pair (ja ターン vs 発言, fr *tour de parole*, ca *torn de paraula*, de *Redebeitrag* — §B2's rule dies without them); the live drifts: fr shipped *Animateur* unratified, ja observer 観察者 (glossary) vs オブザーバー (shipped); "Someone New…" gender-marking in fr/ca/es; reuse-or-delete for the dead `enums:speakerRole.*` block (84 strings, zero call sites) | New `glossary.md` rows (moderator, participant, observer, speaker, turn, research team, someone-new) + `glossary.csv` term blocks with the lexical-rule invariant in the note column; §G's glossary flag cleared | — |
| **H2** ✅ | **Evidence pass** *(done 25 Aug 2026)* | Test §D's most-likely-wrong claim and finish the register | The measured attribution mix — from the **pipeline intermediates**, not the DB (the importer flattens `source` to `"transcript"`, §C1); verdicts for the four untriaged rows S8 / S11 / S12 / S13 (product owner in the loop) | A measured-numbers note under §D claim 2 with the query recorded; §F with no `untriaged` row | — |
| **H3** ✅ | **Decision 2** *(settled 25 Aug 2026 — the participant line)* | Close whose name survives an export | Does person-level membership govern export naming; default membership per code class at first sight (m team-by-default? o **not**?); what the export dialog hint then says; whether observer names in existing exports get a release-notes mention | §E decision 2 rewritten as settled, in decision 1's register; a role × membership → (quote eligibility, export naming) table; then the export/`SECURITY.md` truing that depends on it. **Gates bench 11's observer sweep** — shipping the sweep first does net harm (§B8) | — |
| **H4** ✅ | **Menu prerequisites** *(decided 25 Aug 2026 — §B10)* | Resolve the two architecture questions the menu cannot be specced without | The menu host per surface — the review's recommendation, recorded not assumed: WKWebView reports (anchor, state) over the bridge, AppKit raises a real `NSMenu` from the same function that will feed the menu-bar menus; browser serve keeps pencil + toolbar paths, accepted as the `CommandMenu` precedent. And the **undo contract**: one stack; the inline sweep-line link fires top-of-stack only and vanishes when superseded (Mail's Undo-Send precedent); Edit ▸ Undo carries the action name; the dead bridge is a **step-1 gate** (§D) | A §B10 "mechanism prerequisites — decided" section; a verb × undo table covering every §B3 item; cross-note in [`design-undo-catalog.md`](design-undo-catalog.md) | — |
| **H5** ✅ | **The menu as the function** *(done 25 Aug 2026 — §I)* | Turn §B3's claim into the actual function: the full (surface × object-state) enumeration and the string plan | The state vocabulary the function takes (§C5's machines × me/not-me), unreachable cells struck; the bare-`Role ▸`-vs-scoped question (one drawn frame in six carries the scope label today); the me-item convention (three renderings live — settle on "That's Me (Name)" top-level, "Name (Me)" in lists); bench 3's propagation sheet redrawn to obey its own pattern **and** §B8 (offer in a sentence; sheet lists matches with checkboxes) | A decision-table appendix, each row citing its generating rule; the complete string inventory as ICU templates under the **label-plus-chooser** localisation contract (§B2) | H1 H3 H4 |
| **H6** ◑ | **Bank + picker** *(spec landed 25 Aug 2026; two control conflicts open)* | Spec the two lists (§B4 people-across-studies, §B9 cast-in-session) to buildable fidelity | Presentation per H4's host; create-and-name inline flow; bank composition/order; the quote-card variant's follow-up line; the wrong-Steve failure path | §B4/§B9 expanded from argument to spec; mockup benches redrawn **against the pinned cast** (below) — the p4 double-booking, Sarah's two codes, Jane's o1/o2-vs-p4 timeline, and the three-Mikes collision all resolve to it | H1 H5 |
| **H7** ◑ | **People lens + old-mockup** *(lens reframed 25 Aug 2026; mockup judged UPDATE, edits pending)* | Spec the lens at three scopes; bring [`people-lens-scopes.html`](mockups/people-lens-scopes.html) to the settled model or visibly supersede it | Whether the old mockup is updated or banner-superseded (it predates the stance: its Separate sheet is primary, its folder scope is a suggestion engine, its decision-1 framing is open — all now wrong); the roster-not-table default; the drives-come-and-go caveat; whether "Everyone" belongs in a report lens at all | §B5/§B6 expanded to full spec with the tells table; one coherent mockup story across both files | H1 H2 H3 H5 |
| **H9** | **Route C, v1** *(decided 1 Oct 2026; partly built — plan below)* | Ship the moderator slot engine, project-scoped, on both channels | **Six phases, each shippable and gated** — [H9 · the delivery plan](#h9--route-c--the-delivery-plan-decided-1-oct-2026-partly-built) below: 0 session identity (the transcripts plan's 0b, lifted out), 1 the data layer with no UI, 2 the web UX, 3 the native twin, 4 platform evidence, 5 migration, docs and release. UX iteration 2 and a `/usual-suspects` pass sit between 1 and 2. **Not in v1:** the bank, cross-study links, folder scope, Settings ▸ General, Contacts, the markdown report, the sealed static HTML | [`mockups/moderator-identity-iteration-2.html`](mockups/moderator-identity-iteration-2.html) (R1–R14, real pixels) and the storyboard's E1–E8 (the argument); the pinned-limitation test re-homed as the map's own; the sidebar's impossible MULTI_MODERATOR fixture replaced | 0b first |
| **H8** ✅ | **Schema + API deltas** *(done 25 Aug 2026 — §J)* | Make §C concrete — implementation-last, now reachable | Name-origin representation per field + the two sentinels; the narrowed write payload; the role endpoint; the renumber/remap operations; **the Quotes-lens membership filter that does not exist today** (§C4) keyed on `SessionSpeaker` role; the importer `source` fix; membership storage per H3 | A final appendix: one table per §D step mapping capability → schema delta → endpoint delta → migration note, citing settled decisions rather than re-arguing them | all of H2–H7 |

### The pinned cast

One fictional corpus serves every mockup; several early benches predate it and
disagree (H6 sweeps them). **Ward handover app — round 2**, 12 sessions,
Jan 2026:

| Code | Person | Notes |
|---|---|---|
| m1 | **Martin Storey** — you | moderates every session except 9 |
| m2 | **Mike Alvarez** — colleague | covered session 9; arrived as `m1`, renumbered on rename (bench 9) |
| o1 | **Jane Smith** — product manager, Meridian Health (client-side, **not** team) | observes s1 alone; observes s3 beside Tom Blake (fragment: `o2` there until joined); sat into s4 and was mis-filed as a participant — the J3 thread |
| o3 | **Tom Blake** — Meridian Health | observes s3 only |
| p1 | **Sarah Chen** — ward sister | one code, one person — never also p3 |
| p2 | **Dr Amara Nwosu** — registrar | |
| p3 / p6 | **Mary Adeyemi** ("Mary A.") | interviewed twice — the returning-participant thread |
| p4 | **Marrian Boateng** — healthcare assistant | p4 belongs to her alone; Jane's mis-filing is *within* s4's speaker set, not a second p4 |
| p5 | **Mary Okafor** ("Mary O.") — night charge nurse | the different-Mary thread |
| p7 | **Mickael Hurley** | Whisper heard "Michel Hurlly" — the spelling thread |
| p8 | **Femi J. Adenuga-Price** ("Femi") | the Teams-formal-name thread (renamed from a third Mike to keep the cast scannable) |
| bank | Martin · Steve Nakamura · Rachel Okonjo · Mike Alvarez | **Jane is not in it** — she is the decision-2 argument |

The older mockup's *other* studies (round 1 under Rachel, the oral-history set,
Kestrel Bank) stand; H7 decides whether its round-2 frames adopt this cast or
take the superseded banner.

### H0 · done, 25 Aug 2026

Eleven edits across four docs, every anchor verified unique before application.
[`design-transcript-speaker-editing-roadmap.md`](design-transcript-speaker-editing-roadmap.md):
§11c's `(session, code)` rekey recommendation carries a dated superseded note —
the collision mechanics, the WARNING, the pinned test and the migration-risk
argument all kept, the last re-framed as part of *why* the rekey was rejected;
the eight-reader list re-labelled as enumerated-for-the-rekey; Layer 11's "the
prerequisite" framing dropped and 11a/11b demoted to a back-fill; Layer 4's
"without touching the transcript" and flat session list replaced by a pointer to
§B9; Layer 3a gains the creatable-picker shape.
[`design-speaker-editing.md`](design-speaker-editing.md): the A/B/C cascade
analysis stands, option B's semantics superseded; Operation 1 gains the
bank-not-free-text correction. [`design-multi-project.md`](design-multi-project.md)
§2 keeps the links table, UUID requirement, folder scoping and transitivity as
canonical — only sequencing changes. [`design-undo-debt.md`](design-undo-debt.md)
gains the forward pointer and the step-1 gating.

### H6 · H7 — 25 Aug 2026, and what deliberately did not land

**Landed.** The bank spec (§B4) and the reframed lens (§B5). The old mockup is
judged **UPDATE, not supersede** — in the house form `mcp-extension-ux.html`
already uses (in-place tags plus a delta box), because the judgement is measured
rather than cheap: most of that file survives the reframing, and an honestly
dated half-trued mockup is worse than either horn of the dichotomy the brief
offered.

**Held back on purpose, with reasons.**

- **The cast sweep is written and verified but not applied.** All 41 anchors are
  byte-for-byte unique and the edit set is order-safe — but the *content* check
  found it **moves three collisions rather than fixing them**. After all 41
  edits, **`p1` would belong to nobody**: Sarah Chen drops to zero occurrences
  while six prose lines still name a bare "Sarah" with no referent, and two
  "ward sister" lines lose their subject. One row also still reads "Michael J.
  Hurley-Okonkwo… call him Mike". The sweep needs those additions before it is
  applied; applying it as-is would trade a known inconsistency for a subtler one.
- **The old mockup's edit anchors are off** — three are wrong and one would put a
  banner on bench 10's heading while claiming bench 9. The judgement stands; the
  edits need re-deriving against the file.
- **Two H6 specs contradict each other on the same control** and cannot both
  ship: `New Moderator…` as an anchored popover with a text field over the bank
  (bank spec) versus a pure `NSMenu` submenu with no text field (picker spec),
  plus three smaller divergences. This is a real design fork, not a drafting slip
  — the text field is what makes create-and-name one action, and a text field is
  what an `NSMenu` cannot host.

**Two corrections to text I had already written.**

1. §E decision 1's escapes table said the returning-Mary join is done "by picking
   Mary from the bank". Wrong: the bank is moderators and observers only, and the
   participant join is done from the participants already in the study. Corrected
   in place — it was imprecision in my own wording, and the bank spec caught it.
2. §D priced step 1's bank as "a query over rows that already exist". True of the
   schema, false of the deployment: `Person` rows do not span projects, so the
   bank needs the instance DB first. Step 1's cost line now says so.

### H2 · H3 · H4 — done, 25 Aug 2026

**H2.** The attribution mix measured over 34 projects (§D claim 2), and all four
untriaged §F rows closed — S8 split by which side of the line, S11 already handled,
S12 v1 with a real defect found, S13 deferred. **The ordering was held on purpose**:
the numbers are sound, but a maintainer's own trial runs cannot separate
researcher behaviour from test behaviour, and there is not one `docx` segment on
disk. Instrumentation is the next move, not inference.

**H3 — the decision reframed rather than taken.** The A/B/C/D options were all
built on "team membership", and the answer was that team was the wrong category.
The line is **participant / not-participant**, the existing prefix mechanism
already encodes exactly it, and the rationale around it was what needed fixing.
Consequences: J3's observer sweep is **unblocked**; the participant-side leaks
(job title, the `/sessions` name lists) remain in scope; and *being named is not
being a moderator* becomes a §B4 ordering rule.

**H4.** Both prerequisites answered in §B10 — the menu model lives in TypeScript
and AppKit renders it (with a browser popover reached by pencil and keystroke,
never by suppressing the user's right-click), and undo is one stack whose inline
link is a second button for its top. Three findings came out of it that no one
was looking for: the compound verbs, the dead frontend half of an already-shipped
Swift undo channel, and that **a re-attributed quote does not survive a
re-import** because the stable key carries `participant_id`.

**Three defects found in passing, all doc-vs-code:**

1. `SECURITY.md` states the HTML export "strips display names by default, making
   this the safe path for external distribution." **It does not** — the query
   param and the dialog checkbox both default off. *Corrected in SECURITY.md,
   25 Aug 2026.*
2. `design-export-html.md:264` says "Role titles removed when anonymised";
   `routes/data.py:328` ships `role` untouched. *Fixed 27 Aug 2026, `deb62808`.*
3. `grounding.py`'s `resolve_speaker_names` returns `{}` for *everyone* when
   anonymise is active, while `SECURITY.md:51` calls it "the same word and
   default as the export surfaces". Same word, different effect — and under
   decision 2 the MCP surface is now the one that is wrong. *Still live on
   4 Oct 2026: with the per-project Anonymise switch on, `resolve_speaker_names`
   returns `{}`, so moderators lose their names too.*

### H1 · done, with four calls left for the owner

**Landed.** Five glossary rows (above). Nine turn-nouns pinned in
`glossary.csv` — ja **ターン** (the ratified Quotes term 発言 would otherwise
collapse Turn and Quote), ko 말차례, de *Redebeitrag*, fr *tour de parole*, es
*turno de habla*, ca *torn de parla* (TERMCAT's form — the earlier brief said
*torn de paraula*, which is the queue sense), it *turno di parola*, pt-BR *turno
de fala*, zh-Hant **發言** — each with a translator note carrying the lexical
invariant, since Weblate shows one string at a time. The ja **Observer** drift is
corrected: `glossary.csv` said 観察者 against four live keys shipping オブザーバー,
so the glossary was the outlier, not the product.

**Held deliberately.** The ~~dead~~ `enums:speakerRole.*` block (4 keys × 21 locales)
is **not** deleted: verification found the census incomplete —
~~`design-i18n-wiring.md:76`~~ (now `docs/archive/design-i18n-wiring.md`)
instructs a future implementer to wire roles to those
very keys — and the near-homonym argument used to justify deleting it applies
equally to the proposed replacement. ~~Reconcile the wiring doc first.~~

> **The "dead" premise is wrong in one of four, measured 22 Sep 2026.**
> `speakerRole.participant` has **three live callers** —
> `WelcomeIllustrations.swift:570`, `:631`, `:662`, which `i18n.t` it into the
> rendered illustration data, and Swift's `I18n.namespaces` does load `enums`
> (`I18n.swift:43`), so it resolves rather than falling through to the raw key.
> They arrived with the native-illustration enrolment on 22 Sep (`i18n-defects.md`
> row 48), *after* this paragraph was written. `researcher`, `observer` and
> `unknown` still have none. **The conclusion is unchanged and the reason is now
> stronger: deleting the block would break the welcome illustrations in 21
> locales**, which is a live regression rather than a lost future. Note also that
> the sessions grid does *not* read this family — `speakerRolePlaceholder`
> (`SessionsTable.tsx:49`) resolves `sessions.speakerPlaceholder.*`, a separate
> set, so a census that greps for the rendered *word* rather than the key will
> keep finding the wrong one.
>
> **Reconciled 22 Sep 2026 — the hold is lifted for three of the four.** The
> wiring doc was archived (`docs/archive/design-i18n-wiring.md`) as a plan whose
> every item shipped in March; its §10 was the *only* thing asking anyone to wire
> `enums:speakerRole.*`, and it was wrong to — the SPA keys on the badge-code
> prefix because an m-code speaker's stored role is `researcher`, never
> `moderator`, so these were a vocabulary spelled somewhere else. That removes
> the reason this paragraph was waiting. The repo's own register had already
> reached the same place from the other side:
> `tests/test_locale_key_readers.py:397` tags `enums.speakerRole.` **DEAD** with
> leaves `observer researcher unknown` — three, not four — and its note records
> that *"`participant` left this set on 22 Sep 2026"*.
>
> So: `participant` **stays** and is live; `observer` / `researcher` / `unknown`
> are deletable, 3 × 21 = 63 values. Left undone deliberately — it is a deletion,
> the gate already excuses the keys so nothing is red while it waits, and the
> near-homonym question above is still an owner call.

**Owner calls, none of them safely inferable:**

1. **French moderator word.** `fr` ships *Animateur* / *Animé par* on the sessions
   grid and *Modérateur* on the transcript — the same person, named two ways in
   one report. Both are attested in French practice (*animateur* is the research
   register; *modérateur* skews to forum moderation). Either way, live strings
   change. Entangled with (5).
2. **Person-level membership.** What is the noun, and what does the menu item
   say? *research team* has exactly one live English precedent
   (`pii_summary.txt`) and no translated precedent; "Part of My Research Team"
   mixes a possessive into a per-person state.
3. **The job-title field's user-facing label.** `role_title` already exists in
   code, but `people.yaml`'s key is `role` and is a documented hand-editable
   surface — renaming it is a file-format change for studies in the field. It
   collides with the incoming Role submenu either way.
   **Reopened 4 Oct 2026, wider: "role" names three different things.**
   Not "job title" (owner). But "role" is already doing three jobs, and
   engineers read it as a fourth (permissions, ARIA):

   | Concept | What it is | When it is set | Example |
   |---|---|---|---|
   | Kind of speaker | Who is talking in the transcript | Pipeline guesses, researcher corrects | moderator · participant · observer |
   | Recruit spec | What the person was recruited as; a fact about them | Before fieldwork | practice manager, GP, receptionist |
   | Persona | The archetype synthesised from many participants | After analysis | "the overstretched practice manager" |

   The recruit spec is what a researcher filters by ("the practice managers"),
   so it is expected to become a structured, filterable attribute rather than a
   display string (`docs/research/search-or-ask.md`); `role_title` is its seed.
   Persona is a first-class category the researcher assigns participants to.
   Leaning: keep `role` as an internal name and never show the bare word; the
   transcript surfaces say "speaker". **Open:** the user-facing name for the
   recruit spec, whether persona is in scope for this work, and the
   `people.yaml` key.
4. **"Someone New…" → "New Person…"?** Unshipped, so free to change; the
   indefinite pronoun forces masculine agreement in fr/ca/es. But §B4's warmth is
   deliberate and "New Person" reads as a create command rather than an escape.
   *4 Oct 2026: shipped as one hint per kind — `sessions.picker.newModerator`,
   `newObserver`, `newNameFor` — so no indefinite pronoun has to agree.*

Two more sit outside H1: whether an observer counts as research team for export
naming is **H3** (decision 2); and confirming ja **ターン** and zh-Hant **發言**
with native reviewers before they harden — 發言 deliberately assigns the same Han
characters the opposite role to ja, which a future consistency sweep will try to
undo. Both turn-nouns are marked *pending native review* in the CSV note.

### H9 · Route C — the delivery plan (decided 1 Oct 2026; partly built)

*The twelve decisions are in the changelog entry of that date, in the storyboard's
Part 5b, and in the sections they touched (§B3, §B4, §B6, §C2, §C5, §E decision 1,
§J2, §J4). This section is the order of work, what each step ships, and how we
know it worked. Written before any of it exists; a step that turns out to be
wrong is corrected here, with the date, not silently in code.*

**Three principles the sequence follows.** Each phase is shippable on its own
and leaves the product no worse than it found it — Phase 1 in particular changes
nothing a researcher can see except that two moderators' names stop overwriting
each other. Each phase has a gate that is mechanical where it can be and named
as human where it cannot. And the UX is iterated once more on paper, in the
shipped stylesheet, *before* the first pixel is wired — because the two things
most likely to be wrong are the ones nobody can see until they are drawn with
real tokens (the pill overhang below was the first proof).

#### The six phases

| Phase | Ships | Gate — how we know | Needs |
|---|---|---|---|
| **0 · Session identity** ✅ *(landed 3 Oct 2026)* | The transcripts plan's 0b, lifted out as its own package: a stable per-session identity that survives re-import, re-ordering and the arrival of an older recording; the existing `sessions` rows migrated onto it. Nothing else — this is a prerequisite, not a feature | A test adds an older recording to a fixture study and every `session_speakers` row keeps its session; the smoke fixture carries the identity; `bristlenose status` reads the same session count before and after | — |
| **1 · The data layer, no UI** *(built 4 Oct 2026, landed on `main` 6 Oct 2026 — see the dated block below the table)* | One Alembic revision: `session_speakers.person_id` nullable, plus `state` (`null` · `proposed` · `confirmed`) and `evidence`; `persons` gain the per-project `code`, a `uuid`, `origin` and `me`. One `Person` per identity instead of one per (session, code). The importer runs at the end of every pipeline run, proposes from the intermediates (platform labels → one identity per distinct label, P2), and never overwrites a confirmed row. The pipeline stops writing `people.yaml` and writes the computed stats to an intermediate. A legacy `people.yaml` is read once on the first run after upgrade — inherited-proposed on every session that carried the code — then ignored, never deleted. `GET /people` keeps its shape (code → name, nulls omitted) so every surface renders unchanged; `PUT /people` narrows to the fields it may write; `resolve_speaker_names` reads identities. The WARNING in `compute_participant_stats` retires with the YAML write it describes | The pinned-limitation test (two sessions, two moderators) re-homed as the map's own: both names survive. The sidebar's impossible MULTI_MODERATOR fixture replaced by one the importer can now produce. `tests/test_serve_export_coverage.py` green — no new GET without a classification. `check-locales.py --strict` untouched (no strings yet). The one visible change — two moderators' names no longer overwrite — pinned by a test that fails on `main` today | 0 |
| **UX iteration 2 + review** *(between 1 and 2; done 1 Oct 2026, review pending)* | [`mockups/moderator-identity-iteration-2.html`](mockups/moderator-identity-iteration-2.html): route C drawn with the shipped stylesheet inlined verbatim and only shipped strings and idioms — see below | A `/usual-suspects` pass on the mockup and this section, with `ux-critique`, `what-would-gruber-say` (the native twin), `i18n-review` (four keys, gender-marking in fr/ca/es) and `silent-failure-hunter` (Phase 1's "never overwrites a confirmed row" and "read once") the personas that matter most. Its findings are folded into Phase 2's scope before Phase 2 starts | 1 |
| **2 · The web UX** *(built in part 4 Oct 2026 as the v1.1 picker, reshaped by UX iteration 3: no ✓/✗ pill, `.bn-person-proposed` rather than `.badge-proposed`, a per-kind New row instead of *New Moderator…*, the Sessions grid only; `m?` and the MCP `moderator` field wait for Phase 1 — see the picker paragraph below)* | `m?` on the split badge; the proposed treatment — three lines of composition CSS in `molecules/person-badge.css` so `.badge-proposed` dashes the halves instead of ringing the pair; the pill wired: ✓ confirms, ✗ returns the slot to `null`; the picker as a popover from the badge, rows per §B9 (identities as split badges, *That's Me (Name)*, *New Moderator…*), opened by click or right-click; the inline name field on a null slot is the Someone-New path (commit mints and assigns); the four strings seeded into the 21 full locales; the sidebar's "multiple moderators" test counts identities with `null` as one of them; `export.css` and `isExportMode()` drop the class, the pill and the pencil in the leave-behind; the exported roles line reads the one sentence on a null slot; the MCP overview carries `"moderator": <code or null>` on each session item plus one `INVARIANTS` line | vitest on `SessionsTable`, `TranscriptPage` and `SessionsSidebar` asserting **the payload each pick sends** — the 0.29.1 lesson: a test that proves the switch renders is not a test of the wire. `tests/test_export_css_selectors.py` green on the new selectors. `check-locales.py --strict`. One E2E spec: pick on session 4 in the grid → the roles line on transcript 4 shows `m1`. The MCP contract test covers a null session | 1, review |
| **3 · The native twin** *(built 4 Oct 2026 as a `person-picker` message → a transient `NSPopover`, not `person-menu` → `NSMenu`; Edit ▸ Undo carries the pick; both directions pinned by the bridge contract fixture — see the picker paragraph below)* | A `person-menu` bridge message (anchor, slot state, the identities, Me) → an `NSMenu` built from the same keys, raised by the host for a right-click on any person badge; selecting *New Moderator…* tells the webview to open the inline editor; Edit ▸ Undo carries the pick (the `undo-state` frontend half §B10 already specified); a Diagnostics fixture that renders the web popover and the native menu side by side over one payload, for the visual-parity pass that comes *after* the wiring | Swift tests build the menu from a fixture payload and assert items, order and the checked row; a `test_menu_title_keys.py`-style pin that the native menu reads the same four keys the popover does; the human check: on the Mac, open the picker from the grid and from the transcript header in one session — same items, same order | 2 |
| **4 · Platform evidence** | Participant ids in the VTT `NOTE` (the transcripts plan §4's `participants:` display-name → id map); the importer prefers an id over a display name; identities join across sessions on the id; when an id arrives for an identity that was minted from a name, the id attaches to it (same name) or wins (different name — the name is then the researcher's to fix) | Fixture pairs with and without ids; the P2 carve-out pinned both ways: one display name across files → one identity, two ids with one display name → two; the attach-or-win rule pinned | 1 (independent of 2 and 3; may land before them) |
| **5 · Migration, docs, release** | The upgrade path proved on a 0.31.x project folder: the legacy read, inherited-proposed everywhere, the file left in place. README, `man/bristlenose.1`, the website's `docs-src/cli.md` and `server/CLAUDE.md` stop promising an editable `people.yaml`; §C2 and §J here trued; `SECURITY.md`'s export line re-read against decision 2. CHANGELOG under **New** — a minor bump | `scripts/check-doc-surfaces.sh`; a release-notes sentence for studies in the field, written by the owner, saying that moderator names are now tentative until confirmed and that nothing was lost | all |

> **Corrected 3 Oct 2026 — two obligations dropped, and Phase 0 as built.** The owner ruled that
> existing projects need no migration (a researcher re-runs them) and that names typed into an old
> `people.yaml` need not survive. So Phase 1's "a legacy `people.yaml` is read once … then ignored"
> and Phase 5's "upgrade path proved on a 0.31.x project folder" are **withdrawn**, along with the
> transcripts plan's "migrate by seeding from the `# Source:` headers". Phase 0 shipped as a
> pipeline-side registry, `.bristlenose/sessions.json`: session grouping key → sid, and per sid
> speaker label → code. A known key keeps its sid; a new one takes the next number ever issued; a
> label keeps its code while its role matches; participant numbers are never reused. A project
> without the file numbers exactly as before. The serve DB needs no change for it — its `sessions`
> rows were always keyed by the sid string, which is now stable — so the row's "existing
> `sessions` rows migrated onto it" and "the smoke fixture carries the identity" did not arise.
> Gate as built: `tests/test_session_registry.py` and `TestStickySessions` in
> `tests/test_pipeline_platform_transcripts.py` (an older recording through the real
> `Pipeline.run`: transcripts, quote keys and participant codes all stay put; each test fails
> with the registry disabled). The file holds speaker labels beside codes, so it is a
> re-identification key like `pii_summary.txt`: written `0600`, inside `.bristlenose/`, which serve's
> dot-directory guard already refuses.

> **Corrected 3 Oct 2026 — Phase 1's row, measured before building, and the step taken instead.**
> A read-only inventory of every reader of names and codes found three things the row does not say.
> **(1) "`GET /people` keeps its shape so every surface renders unchanged" is false:** the Sessions
> table looks names up in `/people` by the raw per-session code, so once moderators are identities
> with per-project codes, routes must emit the identity's code (session 2's moderator reads `m2`) —
> a visible change across ~10 server routes. **(2) Four sites inner-join `session_speakers` to
> `persons`** (`routes/transcript.py`, `grounding.resolve_speaker_names`, `export_core._load_speakers`,
> `routes/clips_export._load_speaker_names`): a nullable `person_id` drops an unidentified moderator
> from those surfaces instead of rendering `m?`. **(3) The importer never sets per-session stats**
> (`words_spoken`, `pct_*`, `source_file` stay at their defaults), so "stats to an intermediate" needs
> an importer half. Also unstated: under "an LLM hearing never mints", Whisper-only sessions lose the
> moderator name they show today until someone picks one. Phase 1 stands as decided and needs these
> four folded in before it is built. **What shipped instead** (owner's call, same day): the serve DB
> already held one speaker row per (session, code), and the collision entered only because the
> importer seeded every `m1` from the one `people.yaml` entry. The pipeline now writes each session's
> moderator/observer names (platform label > the LLM's `person_name` in that session > a real label);
> the importer names `m*`/`o*` from them, and on re-import replaces a name still equal to the shared
> `people.yaml` value (the collision) while keeping a per-session rename. The Sessions table edits one
> session's moderator (`${session}:${code}` editing key, which also ended the one-click-opens-every-`m1`
> bug); the MCP overview names moderators on each session row, and `INVARIANTS` says `m1` in two
> sessions can be two people. This is forward-compatible with Phase 1: the per-session rows are the
> slots route C keys on, and the evidence file is the importer input it planned. Gates:
> `tests/test_serve_per_session_moderators.py`, `TestPerSessionModeratorNames` in
> `tests/test_pipeline_platform_transcripts.py`, `TestModeratorsAreNamedPerSession` in
> `tests/test_mcp_server.py`, and the payload tests in `SessionsTable.test.tsx` — each proved red
> against the old behaviour.

> **Built 4 Oct 2026 — Phase 1, as built, and where it departs from the row.** Built on a local
> branch (`route-c-phase1`) and landed on `main` on 6 Oct 2026, after 0.33.0 was cut. **Schema (013):** `session_speakers.person_id` nullable, `state` (`NULL` ·
> `proposed` · `confirmed`, migrated from 012's `name_confirmed`, which is dropped; the API's
> `name_confirmed` is now `state == "confirmed"`), `evidence`; `persons.code`, `uuid`, `origin`,
> `me`. No `persons.project_id`: the database is per project, and an identity no slot uses is
> released (deleted) rather than kept, until the bank gives it somewhere to live. **The four
> findings, folded in.** (1) Every route emits the identity's code — `/sessions`, `/transcripts`
> (speakers and segments), `/dashboard`, `/people`, the moderator-question route, the MCP overview
> and the dev sessions table — and `/sessions` adds `slot_code`; `GET /people` is keyed by identity,
> which ends the cross-session lookup by construction. (2) One resolver,
> `bristlenose/server/speaker_slots.py`, outer-joins; the five inner joins are gone (the 3 Oct
> block counted four: `grounding.py` had two, `resolve_speaker_names` and `resolve_session_speaker_names`). (3) The pipeline
> writes per-session stats into `session-speakers.json` (now version 2, which also records each
> name's evidence class), and the importer copies them onto each slot, so the per-session stats
> reach the DB (the export reads `source_file`; `words_spoken` and the `pct_*` fields are stored
> but unread for now). The dashboard's Words card is main's read-time count from transcript words
> (`69c9c569`), which the branch keeps — it also works for output from before v2. (4) **A heard name proposes** (see call 1 below), so
> Whisper-only sessions keep the name they show today. **Codes are derived**, recomputed after every
> import and every pick: moderators number in order of first appearance, so the session registry
> keeps them stable and a code moves only when the map does.
>
> **Departures, each the owner's to confirm.** *(a) A heard name proposes and mints* — one identity
> per distinct name within the study, as P2 does for platform names — where §C5 says a hearing
> never mints. Owner's 4 Oct build of 012 already treated the speaker-identification pass's name as
> a proposal, and the alternative leaves every raw-audio study's moderators at `m?` until Phase 2
> ships a picker that can name them: the phase would leave the product worse than it found it,
> which the plan's first principle forbids. The rule is one branch in `_import_speakers`.
> *(b) `people.yaml` is not retired in Phase 1.* The pipeline still writes it and serve still names
> participants from it (moderators never), and the `compute_participant_stats` WARNING stays with
> it. Retiring it here would leave README, the man page and the website promising an editable file
> for a release; Phase 5 retires it with those docs. *(c) A name on the per-session route says who
> this session's speaker is, never who someone else is*: another identity's name (the 0.33.0
> picker picks by name) points the slot at that person; a new name renames an identity no other
> session shares, and otherwise mints someone new for this slot. So a spelling fix to a moderator
> who ran five sessions changes one — the open question "where does a spelling fix live" stays
> Phase 2's. The route also takes `person` (an identity code) for Phase 2's picker. *(d) No
> evidence file means unidentified.* Output from before 3 Oct 2026 has no `session-speakers.json`;
> its existing serve rows keep what they hold, but a fresh import shows `m?`, and `people.yaml`'s
> one `m1` names nobody — consistent with the owner's "re-run, not migrated". The smoke fixture is
> exactly this case, so its moderator now reads `m?` in every test that pinned `m1`. *(e) The
> per-session route takes the slot code only.* Identity and slot codes are both `mN` and a pick
> renumbers identities, so a route accepting either let a stale grid's code land on a different
> slot — an undo renaming the wrong person, silently. The web grid now addresses every write, and
> its undo, by `slot_code` (`slotOf` in `SessionsTable.tsx`; the native picker's answer, which
> carries the badge's code, is mapped back through the grid). The grid draws a pick optimistically
> and does not refetch, so after a pick that joins two identities its badge codes are stale until
> reload — cosmetic, since no write uses them; Phase 2's `person` pick is the place to refetch.
>
> Gates as built: `tests/test_serve_moderator_identities.py` (23 tests: identity codes, P2, the
> unidentified slot through all four ex-inner-join sites, re-run, pick, stats, the 013 migration
> including the fresh-DB path that 012 had made inconsistent) — 22 of them red on `main` before it
> (measured at `a0b84fca`), the 23rd a guard that holds on both (`/people` has no entry an
> unidentified slot's lookup could hit); the pinned limitation re-homed as `test_people_names_both_moderators_by_their_own_code`; the
> sidebar's MULTI_MODERATOR fixture (`m1` in s1, `m2` in s2) is now what the importer produces,
> unchanged but for its comment; the pipeline's evidence and stats in
> `TestPerSessionModeratorNames`; `tests/test_serve_export_coverage.py` green (no new GET); no
> strings. mypy: 146 → 143.

**What this deliberately does not ship** (unchanged from the row above): the bank,
cross-study links, folder scope, Settings ▸ General, Contacts, the markdown
report and the sealed static HTML — the last two fall back to codes when
`people.yaml` is gone, which their existing missing-file path already does.

#### UX iteration 3 — the owner's review, 3 Oct 2026

Drawn in [`mockups/moderator-identity-picker-v3.html`](mockups/moderator-identity-picker-v3.html)
(web picker and a native Mac popover side by side). Decided by the owner
reviewing iteration 2; these supersede it where they differ.

- **No ✗ | ✓ pill, and no ticks in the grid.** Borrowing the proposed-tag
  accept/deny was the problem: after *deny* the system has learnt nothing and has
  no way to ask who it was. In the grid a name the system is not sure of wears
  the **dotted surround round the whole badge**, as a proposed tag does, with the
  name in grey (hover darkens it); confirmed is a plain badge in solid ink.
- **Yes is said in the picker.** Clicking a name or badge opens it. The **menu's
  own tick** marks the current answer — AppKit's menu checkmark in label colour
  on the Mac, the shipped `✓` in the Export menu's check gutter on the web
  (revised 3 Oct 2026 from a green tick, which got lost on the grey selection in
  Picker Lab): the dotted most-likely name, or the name already chosen. The
  **selection opens on the ticked row**, so yes is click, Enter. Other names are
  possibles. **Dotted only until the first yes:** picking the dotted name
  confirms it (solid); after that, whichever name is picked is simply the current
  answer, solid and ticked next time. Ticks never appear outside the picker —
  this is harder than a tag's yes/no, so the yes lives with the alternatives.
- **Keyboard:** typing `m2` or a name jumps the selection to it (type-select;
  nothing is filtered in v1); Tab reaches the field for someone new; Enter chooses.
- **The picker's first line is the role**: Moderator | Participant | Observer, on
  the shipped `.dimension-toggle`. It opens on the speaker's current role; when the
  pipeline got the role right — nearly always — nobody switches. The segments exist
  for misidentification.
- **Each segment lists the known people of that role, all of them, in a plain
  list.** A v1 study has fewer than ten names and fewer than three moderators.
  Search-as-you-type for thousands of people (Dovetail's picker) is a later
  extension of the same box.
- **That's Me carries a symbol** (SF Symbols on the Mac; an in-house glyph on the
  web, which cannot use SF Symbols).
- **New person: the next badge.** The list's next row is the code they will get
  (`p7` after `p1`–`p6`) with the name half as the field, hint following the
  segment — *New moderator / New participant / New observer* (one key per role,
  for languages that inflect it). Same column, same type as the badges above,
  growing as you type, so it reads as making another badge (revised 3 Oct 2026
  from a separate field under the list). Arrowing onto it puts the cursor in the
  name; Return creates; the arrows leave it.
- **A new person arrives through the picker's field**, replacing iteration 2's
  *New Moderator…* item (R6). (The earlier "click any name in the grid to edit"
  note is superseded: a click now opens the picker; where spelling fixes live is
  open.)
- **Unknown speakers keep the shipped grey italic role word** beside `m?`.
  Unchanged on purpose.

**Decided by the owner, 4 Oct 2026: native on the Mac, web in the browser, and
the native picker is Small.** "Every non-Mac pull-down menu is a giveaway, and
we've done the work." The Mac app opens the AppKit popover built in Picker Lab
(the hybrid below: pull-down menu metrics at the small size — 11 pt menu type,
the small segmented control, 24 pt rows — with the house `SpeakerBadgeView`);
the browser report and the CLI SPA open the web picker. This reverses the
mockup's "web first, everywhere" recommendation. The mockup was right that
`NSMenu` is the wrong primitive for a field plus a segmented control, which is
why the native one is a popover that behaves as a menu rather than an `NSMenu`.

**What goes wrong most, by frequency (owner, 4 Oct 2026).** A *single quote*
attributed to the wrong speaker when people talk over each other — moderator
speech filed as the participant's, or the reverse — is really common; that is
per-quote reattribution, on the quote card and in the transcript, not the
speaker picker (the moderator-quote speaker-detection work owns it). Moderator
versus observer is a genuinely tricky whole-speaker call — where the role
segments, and the §J recode behind them, earn their place. "This was Sarah, not
Mike" between two participants is rare in a mostly 1:1 study, so the picker's
participant list matters less than its moderator list. Sequence the remaining
work by this, not by the order the picker draws its rows.

**Built, 4 Oct 2026 — the confirmed flag.** `session_speakers.name_confirmed`
(migration 012): a pipeline name is a proposal; a typed or picked name, or the
picker's confirm (`PUT …/sessions/{sid}/speakers/{code}` with
`{"confirmed": true}`), says yes. `PUT /people` confirms only a participant
whose name actually changed, because it receives the whole map on every write.
Every name that predates 012 reads as proposed, accepted by the owner. A
re-import never repairs a confirmed slot: equal to the shared people.yaml value
is then a yes to it, not the pre-per-session collision.

**Built, 4 Oct 2026 — the picker (speaker ID v1.1).** Both pickers, on the
Sessions grid, deciding with one model (`utils/personPicker.ts`:
`personPickerRows` for what is offered, `personPickerChoice` for what a pick
means), so they cannot disagree.

- **Web** (`components/PersonPicker.tsx`): opened by the badge (a
  `<button aria-haspopup="menu">`) or the name. Loaded lazily — the grid is
  first paint, the picker a click away — and its strings are built inside the
  lazy chunk for the same reason. Keys it handles stop there (the page's
  Escape also clears the search); Escape or a choice returns focus to the badge.
  The proposed ring is `.bn-person-proposed` in `molecules/person-badge.css`,
  its own class: borrowing AutoCode's `.badge-proposed` drew two rings and a
  pulse. An exported report draws every name plain and opens no picker.
  A name row has no key handler of its own, on purpose: the list's handler
  owns arrows, Enter, Space and type-to-jump, and a row handler as well chose
  twice on Space (a scoped eslint-disable says so).
- **Accessible proposed state** (`03efebb5`): a proposed name is announced
  "m1, proposed name Sarah" on the grid badge (`aria-label`), on the web
  picker's row and on the native popover's row — key
  `sessions.picker.proposedName`, all 21 locales. The native popover uses the
  wording the SPA sends as `labels.proposed`, so the bridge contract fixture is
  version 2. "Proposed name" rather than "…, proposed" was confirmed by the owner, 4 Oct 2026: the
  bare adjective has to agree with a noun in most locales.
- **"Moderated by"** (`c30a4b33`): the Sessions grid's moderator and observer
  lines come from the grid's own speakers — the same names the picker offers —
  not from the payload's `moderator_names`, which is read once, so after a
  picker rename the line named a moderator the grid no longer showed.
- **Native** (`PersonPickerPopover.swift`): the SPA sends `person-picker`
  (slot, rows, anchor, every string localised) and the host shows a transient
  `NSPopover` at the badge, Small. It sends back the bare name picked
  (`personPickerChoose`); the SPA resolves it against the slot as the grid holds
  it then, so a yes, a rename and a no-op are decided in one place. The popover
  sizes to its widest row and never below its role segments (231 pt in English
  at Small, 281 in Russian). A project switch closes it, because a pick names a
  session and a code but no project. The web opens the native one only when the
  host sets `__BRISTLENOSE_NATIVE_PERSON_PICKER__`, so an app build without it
  falls back to the web picker rather than sending a message nothing answers.
  The anchor rect is moved down by the web view's top safe-area inset
  (`PersonPickerPresenter.viewRect(zoom:viewportTop:boundsHeight:flipped:)`,
  tested): the layout viewport starts below the toolbar and
  `getBoundingClientRect` counts from it, so without the inset the popover
  pointed a toolbar's height above the badge.
  Both directions are pinned by `tests/fixtures/person-picker-bridge-contract.json`,
  read by vitest and by Swift.
- **v1.1 rules, the owner's (4 Oct 2026):** the role segments show all three
  roles with only the speaker's own enabled; moderator and observer rows are
  every name known for that role in the study, each carrying this slot's own
  code; a participant's picker holds only that participant; an unknown slot
  pre-selects nothing, so Return cannot confirm a guess *(superseded 6 Oct
  2026: it opens in the new-person field, where an empty Return does nothing,
  §J8.10; and every row now shows its own person's code, the new row the next
  free one, §J8.8)*; That's Me is the Mac
  account's name (`NSFullUserName`) and the browser has no such row; a spelling
  fix is the pencil, a click is the picker; undo is ⌘Z (§B10), and picking
  again also works.

*Answered 6 Oct 2026 (§J8):* the "don't know who" row is the hover ✕ back to unknown
(§J8.8); the Participant segment ships after moderator ↔ observer (§J7 R2, owner's
call 10); the moderator list offers only people confirmed at least once (§J8.10);
one tick, not two (§J8.8); light-dismiss discards a half-typed name and keyboard
stays in the list, as recommended and not overruled. Still open as of that date:
right-click as a second native surface.

Still open (as written 4 Oct): whether a "don't know who" row is needed; whether the Participant
segment (a real recode, §J) ships with the first picker or after it, with its
undo (planned in §J7: after it, as R2, with moderator ↔ observer first as R1);
right-click as a second native surface; whether the keyboard lives in the list
(v1) or the field (search later); what a light-dismiss does to a half-typed
name; and four questions from the 4 Oct code review — a moderator pick copies
the display name into both name fields, dropping a source slot's surname; the
moderator list offers other sessions' unconfirmed guesses; That's Me and a
matching name are both ticked; and a participant's write is two requests, so a failed
second leaves the name restored but still confirmed on undo.

**Judge web against native in the app, not in the mockup.** The mockup's Mac
column is CSS, and checking it against a real AppKit render (its *Calibration*
bench, 3 Oct 2026) found it wrong in three places: list selection is
`selectedContentBackgroundColor` (#0064E1 / #0059D1), not the accent; macOS 27's
selected segment is a grey pill, not a raised white one; and the field's bezel
is 22 pt with ~5 pt corners. Its type tokens were right (212 of 212 match the
tree; the Mac column runs on the calibrated `tokens-desktop.css` ladder). For
the decision itself use **Diagnostics ▸ Picker Lab** (DEBUG builds,
`PickerLabView.swift` + `/report/picker-specimen`): the picker in stock AppKit
in a real `NSPopover` beside the SPA's version on the fronted sidecar, one
scenario control driving both. Both halves follow the Sessions switcher's
chooser model (`docs/design-sessions-popover-navigation.md` §Interaction): one
click commits, arrows move the highlight, Return commits, Escape dismisses, and
the native list is that switcher's table.

**The Mac popover is a hybrid (owner, 3 Oct 2026).** Inside the popover it is a
pull-down menu — the system menu font in label colour, the menu's own
checkmark, 24 pt rows (measured from `NSMenu` on macOS 27, the same at both
sizes; Small only drops the type to 11 pt and the segmented control to 20 pt),
the source-list capsule — while the person stays the person: the house native
badge, `SpeakerBadgeView`, the same entity the Sessions switcher draws, in a
column pinned to the widest code so names line up and a new row's `m3` never
gives way to what is typed. A menu of full split badges read oddly inside a Mac
menu; a menu with no badge loses the entity. The web report and the CLI SPA are
unchanged: the hybrid is the native popover's alone. (An earlier lab painted the
native badges from styles the web half measured; that path fell back to grey
text whenever the web half had not posted, so the native half now needs nothing
from it.)

#### UX iteration 2 — what it is, and what it found

The storyboard's Part 5b (E1–E8) made the argument and recorded the decisions,
but its frames approximated the type and drew two things the product would never
say: origin chips ("heard …", "inherited") and a hand-rolled menu. The owner's
rule for the next pass was explicit — real tokens, existing UX, no invented
copy, both renderings. So iteration 2 is built the other way round: the shipped
theme CSS is inlined **verbatim** (index.css order, each block headed by its
source path and line range, diffable against the tree), every frame is a shipped
class in a new *state*, and every string is one that ships today or one of the
four below. Frames are derived, not chosen: slot state (`null` · `proposed` ·
`confirmed`) × surface (Sessions grid, picker, inline editor, transcript header
and roles line, session sidebar, Project lens line, export, MCP overview, a
migrated study, the Mac). Four shipped switches sit on the page — appearance,
palette, `data-platform="desktop"` for the SF Pro ladder, and the
`data-person-display="code"` mode — because a state that survives all four is
a state that will survive the product.

What drawing it with real pixels found, none of which the storyboard could:

- **The shipped pill overhangs onto the name in the grid** (R3). `.badge-action-pill`
  hangs 1 rem past the badge's right edge; on a quote card that is whitespace, in
  the decomposed speakers cell it is the first letter of the name. One rule fixes
  it — hang the pill left inside `.bn-session-speaker-entry` — and it goes in
  Phase 2's scope.
- **The proposed treatment needs three lines, not zero** (R1). `.badge-proposed`
  adds a dashed border; on the split badge that is a ring around two solid
  boxes. The composition rule moves the dash onto the halves.
- **The roles line needs no new string** (R8): it already reads "Moderator"
  followed by a badge, so a null slot renders *Moderator m?* as it stands.
- **The sidebar would hide the gap** (R9) under its current "multiple
  moderators" test, which counts distinct names; it must count identities with
  `null` as one of them.
- **That's Me on a proposed slot should adopt, not duplicate** (R5): mark the
  proposed identity as Me, keep its heard spelling, confirm the slot. Anywhere
  else it assigns the Me identity, minting it on first use. Recorded as a
  recommendation for the review, not a decision.
- **Everything else was already there**: the unnamed placeholder word, the
  editing tint, the dropdown idiom, the export gate, the display mode.

#### The string plan

> **As built, 4 Oct 2026:** the picker shipped with `sessions.picker.{role, newModerator,
> newObserver, newNameFor, thatsMe, proposedName}`; there is no `people` block, and
> `people.me` and `export.moderatorNotIdentified` wait for Phase 1's `m?`. That's Me is the Mac
> account's name only — the browser has no such row, so the GECOS half below is not built. The
> plan is kept as written.

Four keys, housed in the `people` block §I4 reserves, seeded into the 21 full
locales (zh-Hant-HK gets none). The English is the owner's; the mockup carries
placeholders and says so in its chrome bars.

| Key | Placeholder | Where | Notes |
|---|---|---|---|
| `people.thatsMe` | That's Me ({{name}}) | picker, top level; the `NSMenu` | §I3's settled form; name from `NSFullUserName` on the Mac and the GECOS field on the CLI; `That's Me…` when the account has no name |
| `people.me` | {{name}} (Me) | picker rows, once Me has a code | §I3's list form, rendered in the badge's name half; the top-level item is not offered once its row is in the list |
| `people.newModerator` | New Moderator… | picker, after the separator; the `NSMenu` | §B9's spelling. The storyboard used *Someone New…*; H1 carries the choice. One key either way; fr/ca/es gender-marking per H1 |
| `export.moderatorNotIdentified` | Moderator not identified | the exported transcript's roles line; the `m?` lozenge's aria-label | the 1 Oct default. Delete it and the export reads *Moderator m?* like the app |

#### Human-only checks, and what to measure

Three checks nothing in pytest or vitest can see, to be walked once Phase 2 is
on a branch: whether a proposed lozenge in the grid reads as the same thing as a
proposed tag on a quote card to someone who has used AutoCode (watch one person
meet it cold); whether `m?` beside the placeholder word reads as *unknown* or as
*broken* — if broken, the export's sentence may need to come into the app too;
and, on the Mac, whether the picker from the grid and from the transcript header
are indistinguishable in one session.

Three numbers, from the telemetry the product already keeps and the rows this
adds: the share of sessions with a confirmed moderator thirty days after
upgrade (the honest-data claim — a study that stays at zero is fine, a study
stuck at *proposed* everywhere means the pill is not being found — *4 Oct 2026: the
pill is gone; read it as the picker's confirm*); identities
per study against distinct platform labels (never more — P2 says one per label);
and the count of ✗ on platform proposals (*since iteration 3, a re-pick away from a
proposal*), because every one is a study where the
carve-out guessed wrong, and that is the number that decides whether P2 holds.

---

## §I — The menu, enumerated (H5)

> **Status, 6 Oct 2026.** This enumerates the §B3 menu as `items = f(surface,
> state)`. The Sessions-grid naming items are now the person picker (§B3's status
> note, §J8); the transcript-turn, quote-card and People-lens rows are not built and
> remain the reference for them. The domain table's inputs (`kind` is role,
> `nameClass` collapsing 3:1, `cleared` sticky in storage) still hold.

*The function §B3 asserts, written out. Produced 25 Aug 2026 by a seven-agent
pass with two adversarial verifications; the contradictions they found between
each other are adjudicated here rather than papered over, and what remains open
is listed at the end rather than invented.*

### I1 · The domain

`items = f(surface, state)` — and the domain is far smaller than §C5's three
lifecycles suggest, because most of §C5 is invisible to a menu.

| Input | Values | Notes |
|---|---|---|
| `surface` | `transcript.segmentBadge` · `quote.card` · `sessions.speakerEntry` · `lens.row.project` · `lens.row.crossProject` | Declared by the calling component, not looked up. Carries §B3's default reach implicitly |
| `kind` | `p` · `m` · `o` · `mixed` | **`kind` IS role.** `SessionSpeaker.speaker_role` is the value; the code prefix is its derived label (§E decision 1). Modelling both invites them to disagree — the exact defect class decision 1 closed. `mixed` occurs at `lens.row.project` only, after a join |
| `nameClass` | `needs-name` · `guessed` · `named` | §C5's six name states **collapse 3:1**, exactly and not approximately: §C5 already says only `guess` invites action. `unnamed`+`cleared` → needs-name; `from-file`+`confirmed`+`typed` → named. All six stay distinct in *storage* — `cleared` must be sticky or the pipeline refills a deliberately deleted name — but the menu cannot see the difference |
| `isMe` | boolean | Never inferred; true only after the researcher asserted it (§B4 forbids pre-selection) |
| `multiSelect` | absent · `{count: N≥2}` | Transcript only. Additive: inserts one item and supplies its count |
| `contested` | boolean | `lens.row.project` only. Additive: inserts the **secondary** `Separate…` |
| `joined` | boolean | `lens.row.crossProject` only. Additive: inserts `Unlink…` |
| `hidden` | boolean | Quote card only. A **label toggle**, not a dimension — swaps `Hide Quote`/`Show Quote` |
| `operands` | code, displayName, sessionRef, counts… | **Label data only. Never gates an item.** This is why §B2's label-plus-chooser contract works: the model carries keys plus operands, never assembled sentences |

**Not inputs, deliberately:** `role` (same fact as `kind`), the full six-state
name machine, and the provisional-vs-own-person half of the identity machine —
`Same Person As ▸` is offered either way, so those two states are menu-identical.

**Reachability, adjudicated.** Two agents disagreed on three cells; the resolution
is *reachable* in each case, because a concrete path exists:

- **`isMe` + `needs-name`** — reachable: the researcher dismisses the `That's Me…`
  fallback, or clears their own name.
- **a moderator or observer at `lens.row.crossProject`** — reachable, and it follows
  directly from decision 2: they are instance-wide and singular, so such a row exists at
  folder and everyone scope. Their menu is simply shorter (no scope-varying
  identity zone, because there is nothing to resolve).
- **`cleared` + `joined`** — reachable: clearing a code's name does not dissolve a
  link the researcher asserted.

Genuinely struck: **`contested` on a `p` code** (participants are numbered from a
threaded counter, so two `p` codes are always two slots — verified in
`s05b_identify_speakers.py`), and **`m`/`o` at `quote.card`** — which is struck
*by intent and not at HEAD*, since §C4 measured that no read-time membership
filter exists yet.

### I2 · The four surfaces

Zone order is fixed — **name · identity · role · go-to** — with a mandatory hard
separator between the attribution and identity families (§B2: they must never
share a section). **There is no membership zone**: decision 2 deleted it.

**Transcript segment badge** (reading, narrow default). `This Turn Is ▸` first;
`All of p3's Turns Are ▸` one group down with its scope in its name; `Split Turn
Here` / `Merge with Turn Above`; then name, role, `Not a Speaker`; then go-to.
With a selection, `These N Turns Are ▸` is inserted. Largest enumerated menu in
the system: **10 items and 4 separators** — within the stance.

**Quote card** (reading, narrow). `This Quote Is ▸` (the two-outcome picker),
`Trim Quote…`, `Hide Quote`/`Show Quote`, go-to. It also gains name, identity and
role zones that §B3 does not list — generated by rule 1 and §B1's "every altitude
reads and writes".

**Sessions-grid speaker entry** (sweeping, wide). Name zone by `nameClass`; the
bank item and `That's Me` on `m`/`o`; `Role in Session N ▸`; the whole-speaker
remap; `Not a Speaker`.

**People-lens row** — at project scope the join cases, `Not a Speaker`, and the
secondary `Separate…` when contested; at folder/everyone scope, `Same Person As ▸`
and `Unlink…` for **participants**, and a shorter menu for moderators and observers, who need no
scope switch.

### I3 · Three conventions, settled

**Role always names its scope.** *A menu item names its scope whenever the verb
reaches less far than the object the item names.* Name reaches exactly as far as
its object (a code has one name everywhere, §0) so `Change Name…` stays bare;
role reaches one session out of N, so every role item carries its scope —
`Role in Session 4 ▸`, `Role in All 8 Sessions ▸`. **A bare `Role ▸` is never
correct.** Generated from §0 + §C5, not chosen, so it needs no per-frame
judgement. Five drawn frames must change.

**The me-item, measured off shipped macOS rather than argued.** Apple's
`.loctable` files answer it 3–0: `%@ (Me)` in CloudSharingUI, PhotosUICore and
FinderKit; ContactsUI ships the bare badge `Me`. So: **`That's Me (Martin
Storey)`** at top level, **`Martin Storey (Me)`** in any people list, and
`That's Me…` — correctly keeping its ellipsis — as the no-name fallback. The
three live renderings (including a lowercase trailing `— me`) all go.

**Bench 3's propagation sheet leaves the naming path.** The document already
contradicted its own frame: its pattern table records bench 3 as a sweep line
with a link, its commentary demands "no dialog, no modal, nothing to dismiss",
and its pricing commentary calls a dialog in the naming path the cardinal sin —
while the drawn frame is a modal. So the rename **commits immediately** (name,
state `typed`, one undo entry, and nothing in any transcript or quote text), and
the sweep line offers the sweep. Opening it shows the matches with checkboxes,
per §B8 — which the drawn sheet never did.

### I4 · The string plan

**141 seedable keys + 3 blocked**, housed as one `people` block inside
`common.json` (`I18n.swift` splits the first dotted segment as the namespace, so
`common.people.*` resolves natively and no tenth namespace is needed). 17 plural
stems. ~9.7% growth on the measured 1,454-leaf `en` tree. zh-Hant-HK gets **zero**
— it is an override fork.

Four mechanical constraints, each verified against the tree:

- **`_one`/`_other` suffixes carrying `{{count}}`**, matching
  `desktop.menu.quotes.starCount_*` and `common.export.copyQuotesCount_*`.
- **ru/uk `_one` must carry `{{count}}` when `_other` does** —
  `check-locales.py`'s `RECURRING_ONE_LOCALES` makes this an **error**, not a
  warning.
- **The possessive lives inside the localisable unit**: `"All of {{code}}'s Turns
  Are"`, never concatenated. It survives a no-clitic language (de *Alle
  Redebeiträge von {{code}}*).
- **The label-plus-chooser note has nowhere to live on the key.** i18next JSON v4
  has no per-unit comment field, so the note travels in `glossary.csv`'s `note`
  column (already done for the nine `Turn` rows) plus the `_comment_*`
  pseudo-key convention — *not* on the key itself, as an earlier draft assumed.

### I5 · What H5 could not close

- ~~**The bank's group header.**~~ **Closed 25 Aug 2026 — no header at all.**
  `Your team` died with decision 2, and the replacement proposal (reuse
  `Moderators` / `Observers`) was rejected on its own merits by H6 and by the
  vocabulary adjudication independently: the grouping key does not exist
  per-person, it performs the role-suggestion decision 2 forbids, and a set whose
  only true name is its definition should not be labelled. See the §B4 spec.
- **`Not a Speaker`** — what happens to the code's turns, and whether it confirms.
  Two agents specified two different items and neither §B nor §C settles it. It
  is the one place the lexical rule is genuinely ambiguous: the item names a
  speaker, but removing one has to do *something* with their words.
- **`Not the Same Person`** — a menu item behind a right-click, or a control on
  the row beside `Keep as One Person`? If it moves to the row, two domain inputs
  disappear.
- **`Role in All {n} Sessions ▸` on a `mixed` row** — a person whose roles
  genuinely differ across sessions. Flatten, per-session, or omit-and-navigate.
- **Three new chrome nouns with zero precedent** in 1,453 `en` leaves: *lens*,
  *client*, *study* (the last appears six times, all in body prose, never as
  chrome). Adjudicate or cut before seeding.
- **Common-word suppression** (§B8) needs a definition of "common word". The
  proposal that came back — a shipped per-language frequency corpus plus a build
  step — is out of proportion to H5 and unresolved on licensing.
- **Two surfaces have no cells yet**: the "Moderated by…" prose line and the
  quote card's moderator-question pill. §C3 names both as renderings that must
  become one component with one menu.
- Carried unchanged: the French moderator word, the job-title field's label, and
  `Someone New…` vs `New Person…`.

---

## §J — Concrete deltas (H8)

*Implementation last, and now reachable. Produced 25 Aug 2026 by a six-agent pass
with a completeness check and an adversarial code-truth check — the second
refuted eleven claims and corrected a dozen line citations, so **this section
cites files, not line numbers**: the citations drifted faster than they could be
verified, which is itself the finding. Nothing here re-argues a settled decision.*

### J1 · The role endpoint is not a step-1 operation

**§D prices step 1 as "role needs one endpoint". That pricing is wrong**, and it
follows from §B7a taken one step further than §B7a takes it. Because `kind` *is*
role, `p4 → observer` is a **recode**: `p4` ceases to exist and an `o` code
appears. Measured, that touches seven things, and only the first is a field
update:

| What is keyed by the code | Cost |
|---|---|
| `SessionSpeaker.speaker_code` | one row — but under `UNIQUE(session_id, speaker_code)`, so the old code must be freed before the new one is taken or the constraint fires mid-transaction |
| `TranscriptSegment.speaker_code` | N rows in that session, one `UPDATE` (plain string, no FK) |
| `Quote.participant_id` | one `UPDATE` — cheap, and this is §C4's denormalisation paying off |
| **The quote stable key** `(project_id, session_id, participant_id, start_timecode)` | **broken by the recode.** Re-attribution is not one of `_pinned_quote_ids`' four arms, so an unpinned re-coded quote is not matched on re-import |
| `people.yaml`'s participant key | `_write_through_people_yaml` has **no create, delete or rekey path** — it cannot express a recode today |
| `transcripts-raw/*.txt` bracket tokens | written at merge time; the reader regex is `\d{1,2}` |
| Any already-distributed export | unreachable by construction |

So **role belongs with §D step 4** (what naming implies), not step 1 — it is the
same renumber machinery reached by a different verb. What *can* ship in step 1 is
role as a **recorded override** that the pipeline honours on the next run, which
needs no recode and no cascade.

*4 Oct 2026: route C removes the cascade — the tag is provenance and the recode is
one slot row. The plan, and why it does not reach the pipeline, is §J7.*

### J2 · Step 1 — name, that's me, the bank

- **`persons.uuid`** — one new column, one Alembic revision plus the head-pin
  bump in `tests/test_migrations.py`. It is the link between a per-project
  `Person` row and its instance-bank row.
- **The narrowed payload.** `PersonData` fields go `str = ""` → `str | None =
  None`, and `put_people` assigns only non-`None` fields. Back-compatible: a
  client sending all three keys behaves exactly as today; one sending a single
  key stops blanking the other two. This closes the stale-snapshot race and is a
  prerequisite for step 2's `confirm`, which changes no value.
- **The bank needs a new database**, at `~/.config/bristlenose/instance.db` —
  **not** `bristlenose.db`, which is already occupied. Two tables: the person
  record, and a person↔project use record that yields the study count.
  `person_links` from `design-multi-project.md` §2 is *reserved, not created* —
  the bank is prevention, and links are the back-fill.
- **"Which person is Me" is instance-scoped and must never be written into a
  study folder.** It is not a per-project fact, and a file that travels with a
  study should not carry it.
- **Role as an override** rides in a **new additive top-level block** in
  `people.yaml`, keyed `(session, code)` — legal because §0 constrains *names*,
  and role is per-session by §C5. `participants:` keeps its shape, so every file
  in the field since 14 Jul remains valid input. *Superseded 1 Oct 2026: there is
  no new block, because there is no file. Role, like the moderator slot, is a
  column on `session_speakers` (§C2); the downgrade hazard below applies to the
  one-time legacy import and to nothing after it.*

> **The downgrade hazard, which applies to every new block.**
> `write_people_file` does a `model_dump()`, so an **older binary that rewrites
> the file silently drops any field it does not know** — and the next run un-does
> every role correction. If a mixed-version window is possible on one Mac (a
> `.dmg` alongside a PyPI install), the field declarations must ship a release
> ahead of the endpoints that write them.

### J3 · Step 2 — name origin, and the two sentinels

Name origin is **per field** (`full_name` and `short_name` separately): §C2's
point is that "derived" describes how the short name was made *from* the full
one, which is a different axis from where the full one came from, and the two
functions run back-to-back so one flag reads "derived" for nearly everyone.

Two sentinels must be decided **before the field ships**, because after it ships
the ambiguity is baked into every file on disk: one for **never recorded** (the
state of every `people.yaml` in the field today, where absence is the only
signal) and one for **cleared** (§C5's sticky state, which the pipeline must
refuse to overwrite).

**Origin is response-only and server-derived — never accepted in a request
body.** A governance field the server cannot vouch for invites `researcher` being
asserted for a name no human reviewed.

### J4 · Steps 3 and 4 — the two hard ones

- **The Quotes-lens membership filter does not exist** (§C4) and must be built.
  Its correct key is per-session role via `SessionSpeaker`, not a string prefix.
- **The stable key must change** or re-attribution does not survive a re-import:
  either `_pinned_quote_ids` gains an arm, or the key stops carrying
  `participant_id`. The second is cleaner and larger.
- **Codes as derived labels** is the structural heart of decision 1, and it is
  the place a spec most wants to hand-wave. The honest question is whether
  derivation can be **render-time only** — in which case the bracket tokens in
  `transcripts-raw/` are provenance and stay as written — or whether a recode
  must rewrite those files. The answer determines whether §D step 4 is medium or
  large, and it is not yet settled. *Settled for `m`/`o` on 1 Oct 2026:
  render-time only — the bracket tokens are within-session tags and provenance,
  and every reader resolves `(session, tag) → person` through
  `session_speakers`. Still open for `p` recodes, where the quote stable key
  carries `participant_id`.*

### J5 · Free wins — defects that ship without waiting for any of this

Each is independent of every step above:

1. ~~`_anonymise_data` blanking `role` (the job title) for `p*` — one line, and it
   closes a documented commitment the code has been violating.~~ **Done 27 Aug
   2026, `deb62808`.**
2. ~~`/sessions`' top-level `moderator_names` / `observer_names`.~~ **Not a
   defect — struck 25 Aug 2026.** This was carried forward from a review written
   *before* decision 2 settled. Under decision 2 moderators and observers are
   named, so `_anonymise_data` leaving those lists alone is **correct**, and
   "fixing" it would have been a regression. Checked before touching: `/sessions`
   carries no top-level *participant* name list, and its per-session
   `speakers[].name` is already blanked for `p*`.
3. The export hint string, which names moderators and omits observers (§E
   decision 2 has the replacement copy). *4 Oct 2026: done in `en`; the other 20
   locales still name moderators only — the value pins postdate the reword, so no
   gate sees it.*
4. ~~The extraction prompt naming `[OBSERVER]` alongside `[RESEARCHER]`.~~ **Done 27 Aug 2026, `deb62808`.**
5. ~~`test_anonymise_keeps_moderator_names`, whose body is a bare `pass`.~~ **Replaced by
   `test_anonymise_keeps_moderator_and_observer_names`, 27 Aug 2026.**
6. **A field-level allowlist test** asserting `/people`'s response key set
   *exactly equals* an allowlist. Ten lines, and it generically closes several of
   the above plus any future field added to the same dict — the export gate today
   is deny-by-default at route level and **allow-by-default at field level**.
   *Done 27 Aug 2026 (`test_person_field_set_is_exactly_the_allowlist`). It guards
   `/people` only: on 4 Oct a new field on `/sessions` speakers shipped names in an
   anonymised export until `c11b986a`, whose test walks the whole embed.*

### J6 · What the verification changed

The code-truth pass refuted eleven claims from the delta specs. Two mattered:
**`_default_db_url()` is reachable** (a register entry claimed no shipped caller
reaches it, and contradicted itself), and **the importer does not "lose
`speaker_role`"** — `TranscriptSegment` has no such column, and role is captured
per `(session, code)` on `SessionSpeaker`, which is the right grain. A dozen line
citations were wrong by two to twenty lines. That is why this section cites files
rather than lines, and why anyone building from it should re-derive the anchors
first — the repo's own gotcha about a bug report describing the tree its author
read applies to design docs too.

### J7 · The cross-role recode — plan (4 Oct 2026; R1, R2 and R3 built 6 Oct 2026)

> **Status, 6 Oct 2026: R1 (moderator ↔ observer) and R2 (into and out of participant,
> relabel only) are built on all three surfaces — see
> [§J8 points 19 and 20](#j8--the-owners-answers--6-oct-2026) for what shipped and where it
> departs from the rows below** (no `/kind` route: the slot's existing `speaker_role` holds the
> kind, and the speaker PUT takes `kind`). R2's *Swap with m1* row (call 4) is built too
> ([§J8 point 21](#j8--the-owners-answers--6-oct-2026)), and so is R3, *Re-analyse this
> session* ([§J8 point 22](#j8--the-owners-answers--6-oct-2026)) — whose pins live in the
> registry, now version 2, as planned below.

*Written to unblock the picker's disabled segments (UX iteration 3: Moderator |
Participant | Observer, only the current one enabled until this exists). Builds on
route C Phase 1, which has not landed; nothing here starts before it and before
0.33.0 ships. Cites files, not lines, for J's reason. Scope: one speaker, in one
session, changes kind — `m1` was really an observer, `p3` was really the
moderator. **Not** in scope: a single quote misattributed in crosstalk (per-quote
reattribution, owned by the moderator-quote speaker-detection work), `p3` is
really `p5` (an identity merge, §D step 4), and part of a turn belonging to
someone else (§D step 5).*

**J1 priced the recode as a cascade over seven things keyed by the code. Route C
removes the cascade.** Once a slot is a `session_speakers` row with a person behind
it, the speaker code in the transcript is a within-session tag — provenance, as
§J4 settled for `m`/`o` on 1 Oct — and the code a researcher sees is emitted by
the server from the slot's kind and its identity. So a recode rewrites nothing
keyed by the tag: `TranscriptSegment.speaker_code`, `Quote.participant_id`, the
quote stable key, the bracket tokens in `transcripts-raw/` and the registry entry
all keep `m1`. It writes one slot row.

> **Corrected 4 Oct 2026, same day — the review found the model's precondition false.** A
> `/usual-suspects` pass (six lanes, a compose check and a parsimony pass; findings in the
> maintainer's private review log for this doc) measured what this section assumed:
> **`(session, tag)` is not bound to one human across runs.** `assign_speaker_codes` gives a fresh
> code whenever detection disagrees with a known code's prefix, and `m`/`o` numbers restart per
> session, so a freed `m1` goes to the next label detected as a researcher — an override on slot
> `m1` would then sit on someone else. And **the importer freezes slots at first import** (it
> `continue`s when a session has any speaker row) while it replaces segments every time: a re-run
> that moves a tag leaves a ghost slot, still named and still "Moderated by", and a tag with no
> slot. Measured on the smoke fixture; live today, independent of this plan. So before R1:
> tags are never reissued within a session (the `participants_issued` shape, for `m`/`o`), and the
> importer reconciles slots against the tags present — creating, never deleting a named slot.
> Also corrected by the review: the raw-tag list below misses `routes/quotes.py` (two
> `like("m%")`, the moderator-question pill — an R1 defect), `routes/data.py`, `mcp_server.py`
> (reads the DB, not emitted codes) and `clips_export`'s subtitle primary; the stored
> `SessionSpeaker.speaker_role` column is a second kind the model ignores; writes are addressed by
> the tag, so routes must emit it beside the displayed code; R3's pin *does* change the tag; R3
> loses curation on every unpinned quote of the session and re-clusters the whole study; call 6
> contradicts call 1 (with no pin, the guide never changes); and `UndoStore.ts` exists
> (`74c71a06`) and now carries speaker naming (§B10). Fixed since, 4 Oct: participant numbers
> are never reissued, a participant-less session no longer takes a real participant's code,
> the registry file is validated, and `bristlenose transcribe` codes its speakers; still live
> are the importer's frozen slots and `m`/`o` reuse within a session. The sequence and calls below stand
> until the owner triages; read them with this block.

#### What the brief assumed, and what the code says

The brief for this plan said a recode must be written into the pipeline-side
registry (`.bristlenose/sessions.json`), because the registry keeps a label's
code "while its role matches" and a re-run would otherwise revert it. Measured,
that is half right, and the wrong half is expensive.

- **The registry cannot hold a recode as it stands.** It stores label → code, and
  `assign_speaker_codes` keeps a known code only while its prefix matches the
  role the pipeline *detected this run*; a mismatch gets a fresh code. That is the
  intended contract, pinned by `test_a_role_change_gets_a_fresh_code` in
  `tests/test_session_registry.py`. Writing `o1` into the map would be thrown away
  on the next run. Holding a recode there needs a new field — a role pin that
  overrides the detected role and re-stamps `seg.speaker_role`.
- **A role pin that reaches the segments re-analyses the session, and is paid
  for.** `_transcript_fingerprint` (`pipeline.py`) hashes the transcript "as the
  stage sees it — text, roles and codes", and the per-session caches of both
  topic segmentation and quote extraction key on it. A pinned recode changes the
  fingerprint, so the next run sends that session to the LLM twice, and the quotes
  that come back can land on different start timecodes than the ones the
  researcher starred and tagged. §C5 states the opposite as a rule: changing a
  speaker's kind "does **not** re-extract quotes".
- **And for `m` ↔ `o` there is nothing to re-extract for.** Quotes are credited
  to the session's primary participant (`transcript.participant_id` in s09), not
  to the speaker of each segment, and the extraction prompt treats `[RESEARCHER]`
  and `[OBSERVER]` identically: never a quote. Coverage puts `m` and `o` in one
  bucket (`coverage.py`, `routes/dashboard.py`), and the `pct_words` denominator
  in `people.py` counts `p` only. A moderator ↔ observer recode changes no number
  and no quote.

So the plan splits the store by what the recode changes. **Kind is held on the
slot, in the serve DB, for every recode, and never reaches the pipeline on its own.**
A recode into or out of participant — which does make the session's evidence
wrong — reaches the pipeline only through an explicit, priced *Re-analyse this
session*, and that is the one place a registry pin is written (R3 below).

#### The model

- **The slot gains a nullable `speaker_role_override`.** Null means the kind the
  tag says (the importer's prefix rule, `importer.py`); a value means a person
  said otherwise. The effective kind is `override ?? kind(tag)`. Internal name
  only: per H1 call 3 the bare word "role" is never shown, and the transcript
  surfaces say "speaker".
- **The importer never writes it and never overwrites it.** That is the whole of
  "a re-run does not revert it": the registry keeps the label's tag, so on
  re-import `(session, tag)` names the same slot, and the slot keeps its kind and
  its person. Same rule, same test shape, as Phase 1's "never overwrites a
  confirmed row".
- **A recode is two writes in one transaction:** the kind, and the slot's person —
  an identity of the new kind, picked from that segment's list or minted by its
  *New observer / New moderator / New participant* field. The name's confirmed
  state follows the pick, as it does today (`put_session_speaker`).
- **The code shown is the identity's code in that kind.** This needs Phase 1 to
  answer a question its row does not ask: what code does an identity show in a
  kind it has not held? Mike moderates s1 (`m2`) and observes s4. Owner's call 3
  below.
- **The rule that keeps the blast radius small: no consumer outside the server
  ever reads a raw tag.** Every route emits the displayed code. Then every prefix
  test downstream stays correct as written, because the prefix of an emitted code
  *is* the effective kind — the frontend (`badgeStyle.ts`, `api.ts`,
  `SessionsTable.tsx`, `SessionsSidebar.tsx`, `SearchBox.tsx`,
  `TranscriptPage.tsx`), export anonymisation (`_anonymise_data` in
  `routes/export.py`, which blanks by `p` prefix), the MCP overview's participant
  count (`mcp_server.py`) and the Mac (`SessionsAPI.swift`). Phase 1 already owes
  this emission for `m`/`o` (the second dated block under H9's table); the recode
  extends it to every kind. What must change is the **server-side** set that reads
  raw tags: `routes/transcript.py` (`is_moderator`, and the participant list),
  `routes/sessions.py`, `routes/dashboard.py` (coverage and the participant
  filter), `grounding.py` (participants counted from quotes),
  `export_core._load_speakers`, `routes/clips_export._load_speaker_names`,
  `routes/tapestry.py` (the Sessions-grid timeline builds its speaker turns from
  `TranscriptSegment.speaker_code`; added 6 Oct 2026 — it sends a per-turn `team`
  flag from the slot's role, and the frontend picks the track from that, else from
  the displayed code) and `resolve_speaker_names`. One resolver, `(session, tag) → (kind, code, person)`,
  in one module, used by all of them. *4 Oct 2026: Phase 1 builds that resolver on
  its branch (`bristlenose/server/speaker_slots.py`), and its `PUT
  …/sessions/{sid}/speakers/{code}` takes the slot code; a recode that changes a
  slot's prefix goes through `speaker_slots.point` and `renumber`. Not on `main`.*

#### What a recode changes

| | `m` ↔ `o` (R1) | out of `p` (R2) | into `p` (R2) |
|---|---|---|---|
| Badge, kind word, picker list | yes | yes | yes |
| Sidebar "multiple moderators", MCP `moderator` field, export roles line | yes | yes | yes |
| Name in an anonymised export (§E decision 2) | no change — both named | **now named** | **now blanked** — the privacy gate below |
| `words_spoken`, `pct_time_speaking` (per slot) | no | no | no |
| `pct_words` — share of *participant* words, study-wide | no | **every participant's** | **every participant's** |
| Coverage buckets | no — one bucket | words move to moderator | words move to participant |
| Quotes in the lens | no — credited to the session's participant | if this slot is the credited one, **every quote of the session leaves the lens** | none until the session is re-analysed |
| Extraction prompt tags | irrelevant | wrong until re-analysed | wrong until re-analysed |
| Discussion guide (moderator questions, `discussion/moderator.py`) | an observer's questions stay in the guide until re-analysed | — | — |
| Tag, transcript files, quote stable key, registry | untouched | untouched | untouched |
| Markdown report, sealed static HTML | keep the tag — not trued | same | same |

Three consequences for the build:

- **`pct_words` and coverage become read-time projections.** Both are stored or
  computed from prefixes today; one `p` recode changes every participant's share
  in the study, so a stored value is wrong the moment the recode commits.
- **The Quotes-lens membership filter (§C4) is R2's spine, and it must be one
  predicate**, keyed on the credited slot's effective kind, applied in the lens,
  `search_quotes`, the dashboard's featured quotes, signals counts and every
  export. A quote leaving is hidden, never deleted — the recode's undo brings it
  back with its stars.
- **The extraction is wrong after any `p` recode, and only re-analysis fixes it.**
  `p3` was really the moderator: the quotes are the moderator's words, and the
  real participant, tagged `[RESEARCHER]`, was never quoted. Relabelling hides the
  wrong quotes; it cannot produce the right ones.

#### Undo

- **`m` ↔ `o` and the relabel half of a `p` recode: the inverse is the same act.**
  The endpoint returns the slot's previous `(override, person, confirmed)`, so the
  client can put it back exactly — including the identity a re-pick would not
  restore by itself. ⌘Z can carry it: the undo store landed on 4 Oct 2026
  (§B10) — push an entry whose undo replays that previous state. Not gated on
  it: the act is cheap and fully reversible.
- **Re-analysis is not undoable.** It spends, and curation on the session's quotes
  that do not come back at the same start timecode is lost (pinned quotes excepted,
  `_pinned_quote_ids` in `importer.py`). So it is its own act, behind a confirm
  whose Cancel is the default, saying what it costs and what may be lost.

#### Re-analysis, and the registry pin (R3)

- *Re-analyse this session* writes the pin, and starts the run. The pin is not
  written at recode time: serve and a running pipeline would both rewrite
  `sessions.json`, and the registry is load–mutate–save.
- **The pin is keyed by label and carries the evidence it was set on** — the start
  times of that label's segments at pin time. On a bare recording the labels are
  *Speaker A/B* from an LLM text split that a voice pass may re-label
  (`s05b_identify_speakers.py`, `s05b_voice.py`), so a re-run of speaker
  identification can hand *Speaker A* to the other human. A pin whose evidence no
  longer matches is dropped and reported in the pipeline summary, never applied to
  whoever now holds the label. (The same hazard already carries names and
  `name_confirmed` on the tag today; this plan does not widen it for `m` ↔ `o`.)
- `assign_speaker_codes` honours a pin over the detected kind and re-stamps
  `seg.speaker_role`, so the prompt tags change and the fingerprint does too —
  which is now the point.
- **Participant numbers are never reissued.** Fixed 4 Oct 2026 (`git log -S'participants_issued'`):
  a speaker re-identified as another kind on a re-run left the registry's map, and
  its number was handed to the next new participant with the name typed for the
  first. Measured before the fix: `s2`'s `p2` re-identified as an observer, then a
  new session's participant got `p2`. A `p` recode retires a number the same way,
  so this was a prerequisite.
- **File format.** The pin is a new key. The registry is unreleased (3 Oct), so a
  key added before 0.33.0 ships is additive and free; added after, an older
  binary's `save()` would drop it silently (the J2 downgrade hazard), and it needs
  `REGISTRY_VERSION = 2` — which older binaries refuse loudly, the right failure.

#### Sequence

| Step | Ships | Gate | Needs |
|---|---|---|---|
| **R1 · moderator ↔ observer** | `speaker_role_override` (one Alembic revision + the head pin in `tests/test_migrations.py`); `PUT …/sessions/{sid}/speakers/{tag}/kind` taking the kind and the person (an id, or a new name), returning the previous slot; the importer rule; the resolver and the server-side raw-tag sites; the web picker's Moderator and Observer segments enabled on `m`/`o` slots (Participant stays disabled); the native picker the same | vitest asserting **the payload each segment pick sends** (the 0.29.1 lesson); a re-import test — recode, re-run the importer on the same intermediates, the slot keeps its kind and person, red without the rule; a route walk over `app.openapi()` GETs, in the shape of `test_serve_export_coverage.py`, asserting no emitted speaker code's prefix disagrees with its slot's effective kind; Swift: the popover's segment pick sends the same payload | Phase 1, 0.33.0 |
| **R2 · into and out of participant, relabel only** | The §C4 membership predicate in one place; `pct_words` and coverage at read time; the Participant segment enabled; the *Re-analyse this session* prompt offered after a `p` recode, not taken | **The privacy gate:** recode `m1` → participant in a fixture, export anonymised, assert the name appears nowhere — proved red against prefix-only anonymisation. Out of `p`: the session's quotes leave the lens, `search_quotes` and the export, and come back on undo with their stars | R1 |
| **R3 · re-analyse this session** | The pin, its evidence check, the confirm | A pinned run re-stamps the kind and re-extracts that session only; a pin whose label moved is dropped and reported; numbers never reissued (shipped) | R2 |

#### Calls for the owner

1. **`m` ↔ `o` never touches the pipeline** — held on the slot, nothing re-extracted.
   *Recommended*, against the brief's "write it to the registry": the fingerprint
   evidence above, §C5's own rule, and that nothing about the evidence changes.
2. **A recode into or out of participant relabels at once and *offers* re-analysis;
   it never starts it.** *Recommended.* The alternative — re-analyse automatically —
   spends on a click and loses curation without a confirm.
3. **The code an identity shows in a kind it has not held** (Phase 1's code scheme).
   *Recommended:* per identity *and* kind — Mike is `m2` where he moderates and
   `o1` where he observes; the name joins them. A code that disagrees with the
   badge's kind breaks every prefix reader at once, which is the property R1 relies on.
4. **The swap.** The common participant error is an inversion in a two-speaker
   session: the pipeline called the moderator `p3` and the participant `m1`. Two
   separate recodes leave a moment with no participant and two undo steps.
   *Recommended:* when the only participant is recoded to moderator in a session
   whose only moderator would then be the only candidate, the picker offers
   *Swap with m1* as the act. R2, not R1.
5. **The pin's key before 0.33.0?** *Recommended: no.* R3 is distant and a field
   with no reader is speculation; take the version bump when R3 lands.
6. **An observer's questions stay in the Discussion guide until re-analysis** after
   an `m` → `o` recode. *Recommended: accept* — the guide is a pipeline artefact,
   and re-analysis is the honest way to change it.
7. **Recoding `p` → moderator names that person in an anonymised export** (decision
   2 names moderators). *Recommended: accept, without a warning* — decision 2 is the
   rule, and the recode says they were never a participant.

### J8 · The owner's answers — 6 Oct 2026

*Answers to the Phase 1 landing brief's calls and to §J7, given in conversation and
recorded here as the owner put them. Where an answer contradicts something already
written or built, it is named, and the earlier text is left standing with a pointer.*

**The principle under all of them.** People are unique in the world, and their names
can clash. Roles are a convenience for the researcher, and the way Bristlenose keeps
moderator and observer speech out of the evidence. A role is something a person
*performs in a session*, not something they *are*. One person can moderate one session,
observe another, and be a participant in an internal study. That is fine, and treating
people as unique and roles as per-session is the People lens's long-term goal.

1. **A self-introduction creates a person.** "Hello, I'm Martin, a user researcher."
   "I'm Steve, a designer at X." "I'm Mike Jones, an assistant manager at Foo, responsible
   for donuts." These are normal openings. When there is only audio, the owner wants them
   to populate the names, proposed, even if the spelling then needs fixing. The job title
   in the same sentence fills the participant role field. This overrides §C5's 1 Oct rule
   that a heard name is only a hint (dated note added there), and agrees with the Phase 1
   brief's call 1.
   - **Already half there.** `speaker-identification.md` asks for `person_name` and
     `job_title` when a speaker introduces themselves.
   - **Open:** the same prompt also takes a name a speaker is merely *addressed by*
     ("thanks, Steve"), which is weaker than the plain self-introduction the owner
     described. Whether that also proposes is undecided.
   - Introductions happen at the start, so the five-minute sample is not a limit here.

2. **A typed name is a person; editing a name fixes that person everywhere.**
   - Naming the unknown `p3` in session 3 "Mike Smith" creates Mike Smith as a person, and
     every `p3` quote in that session reads Mike Smith.
   - Mike Smith may turn up again later, as `p7` or `o2` in session 5. That may be the same
     person or a different Mike Smith. Never merge two people because their names match.
   - **The picker's list is a convenience, scoped to the project.** In v1 it earns its place
     for "this is the same moderator or the same observer". Whether v1 models every
     person in the world is not decided.
   - **An edit to a name is always a spelling fix, applied wherever that person is
     assigned.** It is a correction to the label, never a fork. Fixing "Mat Smith" to "Matt
     Smith" on the Sessions grid, or on a paragraph in a transcript, fixes it everywhere.
   - **This contradicts the `route-c-phase1` branch.** On the branch, a typed name on a
     slot whose person no other session shares renames that person; on a shared person it
     creates a new person for this slot. Under this answer those are two different intents
     and need two payloads:
     - *rename this person*: the pencil, from any surface;
     - *this slot is a new person*: the picker's new-person row.

     The branch currently decides between them from whether the person is shared. Reconcile
     this before or while landing Phase 1. The brief's call 3, "keep until Phase 2 decides
     where a spelling fix lives", is answered by this.

3. **Removing a person, and going back to unknown.**
   - When the People lens exists, it will offer deleting a person.
   - The picker may gain a way to return a slot to unknown: `p3` Matt Smith back to `p3`,
     unknown participant. That answers the open "don't know who" row in UX iteration 3, and
     needs Phase 1's null slot.
   - **Open:** what the picker lists before the lens exists, when a person no longer
     appears in any session. The brief's call 5 releases such a moderator; the owner did not
     rule on that interim.

4. **`people.yaml`** can be dropped whenever the architecture makes it sensible. It is no
   longer tied to Phase 5.

5. **§J7's two prerequisites are confirmed:** the importer reconciles speaker slots instead
   of freezing them at first import, and `m`/`o` codes are never reissued within a session.

6. **§J7 call 3 is confirmed.** Codes are per person and per role: Steve is `m2` where he
   moderates and `o1` where he observes, and his name joins the two.

7. **Where the picker goes first: the Sessions grid, the transcript, and probably the
   dashboard.** The owner accepts the picker as live and editable on these three surfaces as
   the first steps. Quote cards and signal cards wait. Their fix moves speech, which is
   attribution work (§D step 3) behind the re-import wall.

   **Which badges, measured 6 Oct 2026.** Each of these surfaces draws badges of two
   different scopes:

   | Surface | Badge | Scope | First step? |
   |---|---|---|---|
   | Sessions grid | the speakers cell | a speaker in a session | yes (built) |
   | Transcript | the sticky header's participants (`TranscriptPage.tsx`, `transcript-header-people`) | a speaker in a session | yes |
   | Transcript | the moderator and observer roles line (`bn-transcript-roles`) | a speaker in a session | yes |
   | Transcript | each paragraph's badge (`segment-speaker`) | **a paragraph** | see below |
   | Dashboard | the sessions table's speakers cell (`bn-session-speakers`) | a speaker in a session | probably |
   | Dashboard | the featured quote's attribution | a quote | no: attribution |
   | Dashboard | the coverage list's paragraph badges | a paragraph | no: attribution |

   **Recommended, not yet ruled on:** the paragraph badge in the transcript is where U4
   starts (`p1` is Wylie E. Coyote), so it should open the picker too. But only the *name*
   half of a pick is unambiguous from a paragraph: naming `p1` names that speaker wherever
   they speak. A *role* change from a paragraph badge reads as "this paragraph was the
   participant", which is attribution (Layer 3), and would apply to the whole speaker. So
   from a paragraph badge, the picker offers names and hides its role segments. Role
   changes are made from the header and the roles line. When Layer 3 arrives, the paragraph
   badge gains a "this paragraph only" scope, without the same click changing meaning under
   the researcher.

8. **The picker, from the owner's look at the Mac popover (6 Oct 2026).**
   - **Click the name to fix its spelling.** This is answer 2 at work: the edit renames the
     person everywhere. *Proposed, not ruled on:* on a proposed (dotted) row, the first
     click or Enter still confirms; on a confirmed current row, clicking the name text
     makes it a field, the Finder idiom. Whether the grid keeps its pencil as well is open.
   - **"New moderator" shows the next free code** (`m2` when Martin is `m1`). Offering a
     new moderator implies `m1` is a real moderator, just not this one. This replaces the
     v1.1 rule that every row carries the slot's own code. Under Phase 1's codes per
     person and role, each row shows its person's code.
   - **A hover ✕ on the current named row** removes the name and returns the slot to
     unknown: the role word in grey italic, `m?` once Phase 1 lands. It means "not this
     person", not "delete Martin"; deleting a person waits for the People lens (answer 3),
     so the ✕ is on the current row only. It needs the sticky `cleared` state from §C5, or
     the next run proposes the platform label again. Also Delete or Backspace on the
     selected row, a VoiceOver action, and ⌘Z.
   - **Grey italic means unknown, and only unknown.** `.bn-speaker-editable-name.edited`
     lost its italic (done 6 Oct 2026). The native popover's new-person placeholder,
     upright as AppKit draws it, is held until the owner has seen it upright and italic
     side by side: the web half in `mockups/person-picker-tick-options.html`, the native
     half owed in Picker Lab.
   - **The tick is too big and ugly.** Web candidates in
     `mockups/person-picker-tick-options.html`. The native popover already uses AppKit's
     menu checkmark (`NSImage.menuOnStateTemplateName`) but leaves it at the image's own
     size, unconstrained, so it renders larger than a menu draws it. That is a sizing
     defect to fix against a real `NSMenu` in Picker Lab.
     *Built 6 Oct 2026:* the Mac draws the SF Symbol `checkmark` at the menu font's point
     size (regular weight, still to be checked against a real `NSMenu` in Picker Lab). The
     web draws `components/Icon.tsx`'s `check`, the first glyph of a shared house-icon
     component (16-unit grid, 1.4 non-scaling stroke, round caps, `currentColor`), sized
     by `atoms/icon.css`'s `.bn-icon--menu`. The person picker, Export's *Burn subtitles*
     and the search token menu all use it, so the web app has one tick.
   - **One tick, not two.** That's Me and the matching name were both ticked in the
     owner's screenshot (the 4 Oct code review's question). One tick: on That's Me when
     this person is the account holder, otherwise on the name.

9. **Two or more unknown speakers of one role in a session are lettered (6 Oct 2026).**
   - **The problem.** Phase 1 shows every unidentified moderator as `m?`. The transcript's
     paragraph badges show only the code, so a session with two unknown moderators shows
     two different people as the same `m?`. The owner found this by naming one `m?`: the
     other half stayed `m?`, which revealed the voice pass had split one moderator into
     two.
   - **The rule.** One unknown of a role in a session stays `m?`, with the grey italic role
     word *Moderator*. Two or more become `mA?`, `mB?` on every badge, grid and
     transcript alike, with *Moderator A*, *Moderator B* in the grey italic name half.
     Observers likewise: `oA?`, `oB?`. Letters, never numbers, so an unknown can't be read
     as `m1` or `m2`; they also echo diarisation's *Speaker A / B*. Letters follow the
     speakers' order in the session, and a named speaker leaves the others' letters
     unchanged.
   - **Participants are untouched.** Their codes are numbered across the study, never
     reused, and anchor quotes, so two unknown participants are already `p3` and `p4`.
   - **Merging is a pick.** Naming the second unknown the same person as the first
     points both slots at that person, an identity-level merge with no transcript edit.
     The second slot's picker should list the person just named in this session at the top.
   - **Rare, measured.** Of 211 sessions in 57 local trial-run projects (speaker codes
     only), 0 of 162 audio sessions and 1 of 49 platform-transcript sessions had two
     moderators. That corpus is the maintainer's own runs, not cohort data, and most of it
     predates the 0.33 voice pass.
   - **Cost.** A read-time display rule on Phase 1's `m?`, with no new data: count a
     session's unknown slots per role and letter them. It applies wherever an unknown
     code is emitted: the grid, the transcript, the export's "not identified" line, the
     MCP overview. Two new strings, the role word with a letter for moderator and
     observer, in the 21 full locales.

10. **Second round of answers (6 Oct 2026).**
    - **Land Phase 1 now**, with answer 2's three intents built in: point this slot at an
      existing person, make a new person for this slot, or rename a person everywhere.
    - **People left with no sessions are hidden from the picker, and their records are
      kept.** Keep the names learned along the way: a later type-ahead on an unknown
      speaker may offer them again.
    - **A role-segment click only browses.** A researcher can look at the moderator list of
      a participant's picker and nothing changes. A recode happens only when they click a
      name under another role.
    - **The transcript's picker is the same picker.** The owner's call, against the
      names-only recommendation in point 7. It opens on the speaker's current role, which is
      the role the pipeline assigned from how they spoke (questions, moderator phrases),
      or the role the researcher has set since. Because a segment click only browses, a
      look from a paragraph badge changes nothing. A name picked under another role recodes
      the whole speaker in this session, not that paragraph. *Open:* whether the picker
      needs to say so when it opens from a paragraph.
    - **An unknown speaker opens with the cursor in the new-person field** (proposed, under
      discussion). An unknown speaker is one with no name, as opposed to a proposed name or
      one from a platform label. There is nothing to confirm, and typing is the likely act;
      the grey italic hint already says what the field is for. The hazard is a duplicate:
      typing "Martin" when Martin already exists makes a second Martin (answer 2: never merge
      on a name). So the field has to surface the existing match as the default as the
      researcher types. That is the type-ahead the previous bullet anticipates, and it turns
      the field into a combobox.
    - **Only people confirmed at least once are offered from other sessions**, plus this
      speaker's own guess. For now.
    - **Being addressed by name is a good clue.** "Thanks, Steve" in reply to the previous
      turn names the previous turn's speaker. It proposes, dotted like any other guess,
      because a human still says yes. The prompt must attribute the name to the person
      addressed, not the one speaking; with three or more speakers, who was addressed can
      be ambiguous.

11. **One name, one person, in the picker's list (6 Oct 2026).** Creating a second
    moderator or observer with the name another already goes by is refused, case
    insensitively: "{{name}} is already in the list. Pick them, or add something to tell
    the two apart." Either there really are two Martins in a small study, who need
    telling apart ("Martin S"), or the researcher meant to pick Martin. A rename that
    would take someone else's name is refused for the same reason. Scope: moderators and
    observers, the people the picker lists; a person no session points at any more is
    hidden and never blocks a name. Whether two *participants* may share a name is open.
    This is also what lets the Mac picker keep answering with a name: within a role, a
    name now names one person.

12. **Built 6 Oct 2026 — the three acts, end to end.**
    - **Server** (`PUT …/sessions/{sid}/speakers/{slot}`): `person` (a uuid, or an
      identity code) points the slot at that person; with `create`, a client-made uuid
      makes someone new, so a redo finds the same person; a bare name renames the slot's
      person everywhere, or makes someone new on `m?`; `clear` returns the slot to
      unknown; an explicit `confirmed` always wins, so an undo can put a proposal back.
      The name-guessing (`named`, `shared`) is gone. A taken name is a 409 with
      `{"reason": "name-taken", "name": …}`. `release()` keeps people, so they are
      hidden rather than deleted (answer 3).
    - **`/sessions`** reports `person` (the uuid) for moderators and observers only —
      never for a participant, whose uuid would link them across studies in an
      anonymised export.
    - **Web picker**: rows are people, each with their own code; the new row shows the
      next free code; an unknown speaker opens in the field; a taken name is refused in
      the picker, which stays open. The grid's pencil refuses it too, and reloads
      `/sessions` only when a write points a slot at a different person, since only that
      can renumber codes.
    - **Mac picker**: draws each row's code and the next code; replies with the kind of
      row (`name`, `new`, `me`), so a typed name is never read as a pick. Bridge contract
      version 3.
    - **Undo**: records the person, so undoing a pick points back, undoing a new person
      returns the slot to unknown, and redo points at the same new person.
    - **Not yet built:** ~~the hover ✕~~ and ~~the `mA?`/`mB?` letters~~ (both built the
      same day, point 14), ~~rename in place on the picker's row~~ (point 16), ~~the picker on the
      transcript and dashboard~~ (built the same day, point 15),
      ~~and the list offering only people confirmed at least once~~ (point 17).

13. **Priority once attribution starts (owner, 6 Oct 2026):** a paragraph credited to the
    wrong speaker, and a moderator's words shown as the participant's quote (in the Quotes
    lens or on a signal card). Both need transcript edits that survive a re-run (roadmap
    Layer 9); §B9's quote-card half is the design for the second.

14. **Built 6 Oct 2026 — the ✕ and the letters.**
    - **Not this person.** The current row's ✕ (on hover in the web picker and the Mac
      popover; Delete or Backspace on the selected current row in both) sends `clear`.
      The slot returns to unknown with state `cleared`, which the importer treats like
      `confirmed`: a re-run does not propose the refused name again (§C5's sticky
      `cleared`, at last). Undo points the slot back at the person; Edit ▸ Undo says
      *Undo Clear Name*. Only a moderator or observer the slot points at can be cleared;
      a participant's code is never unknown. The Mac reply is `{"kind": "clear"}`,
      naming nobody (bridge contract version 4).
    - **`mA?` / `mB?`.** Lettered in the one resolver (`speaker_slots.lettered`), so every
      route — grid, transcript, export, MCP overview — reads the same code. The grid's
      grey italic name follows: *Moderator A*, *Observer B*. **One refinement to point 9,
      forced by its own rule:** "a named speaker leaves the others' letters unchanged"
      only holds if the letter is the slot's place among *all* that role's speakers in
      the session, not among the unknown ones. So letters appear whenever a session has
      two or more speakers of a role, on whichever of them are unknown: a Teams-named
      `m1` beside an unidentified second moderator reads `mB?`, not `m?`. One speaker of
      a role is still plain `m?`.

15. **Built 6 Oct 2026 — the picker on the transcript and the dashboard.**
    - **Where:** the transcript's sticky header (participants), its moderator and observer
      line, and every paragraph's badge; the project dashboard's sessions table. Each is
      the same picker, opening on the speaker's current role; an unknown speaker opens in
      the field. Paragraph badges are click targets but not Tab stops — a long transcript
      would otherwise be hundreds of them; the header and roles line are reachable by Tab.
      An exported report draws the badges plain.
    - **How:** `components/SpeakerPickerTrigger.tsx` reads the speaker fresh from
      `/sessions` when it opens (the transcript and dashboard payloads name a speaker but
      carry no slot address, person or flag), and applies the choice through the same
      rule the grid uses (`utils/speakerPicking.ts`: `stateAfter`, the duplicate-name
      refusal, `nameSpeaker`). The surface re-reads its own data once the write, or its
      undo, has landed (`hooks/useSpeakersChanged.ts`) — it does not draw optimistically,
      because a pick can renumber codes.
    - **The Mac picker answers whoever opened it.** Native replies used to go to the
      Sessions grid's own listener; with three surfaces that would have answered the wrong
      one, or none. `openNativePicker` keeps the one open request and hands the reply to
      its opener; a reply nobody asked for is ignored. The grid uses it too.
    - **Still open:** whether opening the picker from a paragraph should say it changes
      the speaker, not the paragraph (point 10). Nothing in the picker says so yet.

16. **Built 6 Oct 2026 — rename in place.** On the current, confirmed row, a click or
    Return turns the name into a field (Finder's rename; the row had nothing to choose,
    so no existing meaning is lost). Return sends a new spelling for that person,
    wherever they appear; Escape goes back to the list with the picker still open; an
    unchanged name does nothing; a name someone else goes by is refused in place. A
    proposed (dotted) row is not renamed: its click or Return is the yes, and a rename
    comes after. Web and Mac; the Mac replies `{"kind": "rename", "name": …}`, which the
    SPA resolves by the same rules (bridge contract version 5). The grid's pencil is
    unchanged and now does the same act; whether to keep both is still open (point 8).

17. **Built 6 Oct 2026 — only confirmed people are offered.** A moderator or observer
    appears in another speaker's picker only once someone has said yes to them in some
    session; a pipeline guess appears only on its own speaker, so one wrong guess does
    not spread across the study. The filter sits in `personPickerRows`, so the web
    picker, the Mac picker (whose rows arrive over the bridge) and every surface get it
    at once. **An unoffered guess still holds its name:** the duplicate-name check reads
    every person known for the role, not only the rows offered, because the server's
    refusal does too — otherwise a second "Kerri" could be typed beside a hidden one and
    fail as a save error instead of the plain refusal. The "Moderated by" line still
    names every moderator, guesses included: it reports, it does not offer.

18. **Fixed 6 Oct 2026 — §J7's two prerequisites.** (a) **A moderator or observer code is
    never reissued within a session.** Code assignment reserves every `m`/`o` code the
    session's registry map holds, including speakers not heard this run, and a code a
    role flip takes from its label is kept under `session_registry.retired_label`, a label
    no speaker can have (`NO_PARTICIPANT_LABEL`'s trick), so it survives later runs with
    no change to the file's format. (b) **A re-run leaves no ghost slot.** The importer
    removes a moderator or observer slot whose code the run no longer produces, unless a
    person confirmed it; participants are left to their own stale-session cleanup. With
    Phase 1's half (a moved tag gets its slot), the importer now reconciles slots in both
    directions. The recode itself (R1) is next; the owner's "good — onward" on 6 Oct is
    read as yes to §J7 calls 1, 2, 4 and 5.

19. **Built 6 Oct 2026 — §J7 R1, moderator ↔ observer, on the server, the web picker and
    the Mac picker** (job 7 in the speaker jobs map). It departs from the R1 row of the
    §J7 sequence in two places, both simpler. **The kind is held on the slot's existing
    `speaker_role` column**, which the slot already carried from its tag; there is no
    `speaker_role_override` and no Alembic revision. **The write is the speaker PUT
    everyone already uses**, with `kind: "moderator" | "observer"` beside `person`, so a
    recode and its undo are one write each; a participant is refused (409), that being R2.
    **Codes are worked out on read** (`speaker_slots._derive_codes`), per person and role
    in order of first appearance, so one person can be `m1` where they moderate and `o1`
    where they observe (call 3); `Person.code` is kept as a record only, and nothing stores
    a per-(person, role) code — a table for that waits for the People lens, which may need
    one. The pipeline is never touched (call 1): the transcript's `is_moderator` and both
    moderator-question queries now read the slot, not the tag's letter. **The picker:**
    Moderator and Observer are both enabled on a moderator or observer; switching shows
    that role's people, the speaker first under the code they would carry there, and a pick
    or a typed name recodes them. Nothing under the other role is ticked, renamed or ✕'d —
    the speaker has no answer there yet. Participant stays off, and a participant's picker
    keeps its other segments off. On the Mac the rows for each open role arrive over the
    bridge (contract v6, `roles`) and the reply carries `role`; the SPA resolves it, as it
    resolves every pick. **Gates:** a walk over every project GET in the app's OpenAPI fails
    if any read calls a recoded speaker by their old code (red with the role ignored); a
    re-run keeps the recode; undo puts the role back; vitest pins each segment pick's
    payload; the Swift contract tests decode the v6 rows and send the same payloads.

20. **Built 6 Oct 2026 — §J7 R2, into and out of participant, relabel only** (job 8 in the
    speaker jobs map, without its swap). Every segment is open on every speaker.
    **Out of participant** — `p3` was really the moderator: the researcher picks the moderator
    (or types someone new); a participant carries no uuid to the client, so their own row is
    not offered there. The session's quotes are then the moderator's words, and they leave
    every evidence surface — the Quotes lens, the dashboard and its counts, signals, search
    and the MCP tools, the Discussion lens, the tapestry, clips, CSV/XLSX and the HTML
    export — through one predicate, `speaker_slots.evidence_out` / `evidence_quotes`.
    Hidden, never deleted: the undo brings them back with their stars and tags. AutoCode
    still reads them, so their tags survive the round trip. The write must say who they were
    (a person, or `clear`); a role alone is refused, since it would leave the participant's
    own record on a named moderator slot. The slot remembers the participant it held
    (`session_speakers.participant_person_id`, migration 014, a plain integer), so the undo
    points back at exactly that person without their uuid ever reaching the client — the
    3 Oct rule that `/sessions` never carries a participant's uuid stands. **Into
    participant** — a moderator or observer was really the participant: only the speaker is
    offered, numbered after every participant in the study (`p3` when there are two);
    another participant is never offered, since picking one would join two people. The
    participant side always gets a record of its own, named the same, so no person is both
    a research subject and a member of the team: an anonymised export blanks the one and
    names the other, and the team identity stays free to moderate elsewhere. **The privacy
    gate** holds because every route emits the code of what a speaker *is*: Kerri recoded
    into participant reads `p3` everywhere, and `_anonymise_data`, which blanks by the
    emitted prefix, removes her name from `/people`, `/sessions`, `/dashboard`, `/quotes` and
    the transcripts (a test, proved red with recoded-in slots keeping their tag's code).
    Coverage and the participant count follow the slot's role; `/tapestry` carries a `team`
    flag per turn for the timeline's tracks. **Reviewed the same day** (code review and a
    privacy review; their fixes are in): the two refusals above, the undo of a recode out of
    participant (the first build sent `clear`), and picking the moderator under the
    Participant segment of a recoded-out slot, which now means "back to who they were".
    **Open, owner's calls:** (a) a recoded-in participant's number is worked out on read from
    the highest participant tag present, so it moves when a new session brings that number,
    and can land on a deleted session's retired number — reserving it needs the registry or
    a stored code; (b) the Participant segment of a recoded-out slot shows the moderator's
    name although picking it restores the participant, because the client cannot know the
    participant's name without being told it; (c) the *Re-analyse this session* offer
    (the *Swap with m1* row is built: point 21).

21. **Built 6 Oct 2026 — the swap (§J7 call 4).** In a session of exactly one participant and
    one moderator, each one's picker offers *Swap with m1* (or *p3*) under their own role,
    between the people and the new-person field; observers do not count. One write — the
    speaker PUT with `swap_with`, the other slot's code — exchanges the two slots' roles,
    people and states, so there is never a moment with no participant, and the swap undoes
    itself: ⌘Z sends the same write again (*Undo Swap Roles*). The tags stay put, so the
    session's quotes, credited to the participant's tag, leave the evidence as any recode
    out of participant does, and the participant's own record moves to the other slot, named
    and anonymised there (a test). Two of the team are not swapped (409). On the Mac the
    message carries `swap` (contract v8) and the reply `{"kind": "swap"}`, applied only where
    the SPA offered one. Strings: `sessions.picker.swapWith`, `undo.{undo,redo}.swapRoles`,
    in all 21 locales. Not offered yet: the *Re-analyse this session* prompt that should
    follow, which waits for R3. **Reviewed the same day**, fixed: the swap keeps each tag's
    remembered participant, so an earlier recode's undo still finds its way home after the
    swap is undone (a test unwinds recode-out, recode-in and swap back to the start); the undo
    is recorded only once the swap lands, since a refused one would otherwise be performed by
    ⌘Z; and the grid re-reads after every queued write. **Open, owner's calls:** (a) the
    participant takes the recoded-in number (`p3` becomes `p8` in a study of seven), the same
    question as point 20(a); (b) an edit made outside the undo stack between a swap and its
    undo (a re-analyse, another window) is exchanged too — the server could refuse a stale
    undo if the write carried the roles it expects; (c) the server accepts any participant ↔
    moderator-or-observer pair in a session, looser than the picker's offer.

22. **Built 6 Oct 2026 — §J7 R3, re-analyse this session.** The owner's calls, 6 Oct: pins in
    the registry (no backward compatibility owed — the reference studies are re-run); the
    study-wide regroup accepted and said in the confirm; the Mac runs it and a browser shows
    the command; curation follows the existing importer rules, said in the confirm. **What a
    re-analysis redoes**, in the owner's words: switching a moderator to participant asks for
    new data to be read as evidence, so it asks for new topics and quotes for that session and
    new sections, themes, Discussion guide, tagging and signal cards for the study — and
    nothing else: no transcription, no speaker identification (the pin overrides the guess, no
    LLM call), no PII pass, no other session's topics or quotes. **How:** a session whose
    speaker moved into or out of participant reads `needs_reanalysis` on `/sessions`, and the
    Sessions grid row offers **Re-analyse…**. The sheet says what changes, what is kept and,
    from the pipeline's own estimator, about what it costs; Cancel leads and the act takes the
    default (the house rule from the re-analyse and uninstall sheets, not the Cancel-default
    this section once proposed). Confirming `POST`s `…/sessions/{sid}/reanalyse`, which writes a
    **role pin** per recoded speaker into `sessions.json` (`REGISTRY_VERSION = 2`; version 1
    still reads): the label, the role, the start times of its turns as evidence, the code it
    had and the person the researcher picked. Refused (409) while a run owns the project — the
    registry is load–mutate–save on both sides. The Mac then starts its ordinary resume run
    (bridge `project-action` `reanalyse-session`); a browser shows `bristlenose run <folder>`.
    **The run** applies the pins before codes are assigned (`apply_role_pins`), so codes follow
    roles and the fingerprint changes for that session only; a pin whose label now covers other
    turns is dropped, logged and said on the terminal, never applied to whoever holds the label.
    **The importer** carries each pick to the new code (`_carry_pinned_picks`) and lets the old
    slot go; the moderator's words still credited to the old participant code are **hidden**,
    their stars and tags kept — found while building: with the slot gone, a kept quote would
    otherwise come back as evidence. **Open:** the dropped-pin notice reaches the terminal and
    the log, not the Mac's pipeline popover (a `PipelineSummary` field is a two-file change);
    whether a transcript paragraph's badge should speak for the paragraph (job 10) rather than
    the whole speaker — the owner's 6 Oct reading of the picker — is the next design question.
    **Reviewed the same day; four fixes.** (1) The pin's evidence could never match a real
    recording: serve took starts from the DB (whole seconds, stage 6's merged paragraphs, and
    any split halves) while the run compared stage 5's raw fractional segments, so every pin was
    dropped and a paid re-analysis changed nothing; the fixture's integer, unmerged starts hid it.
    Both sides now read the same thing — serve the transcript file's timecodes
    (`importer.turn_starts`), the run its raw segments merged by stage 6's rule and floored
    (`pipeline._paragraph_starts`), pinned by a test that writes the file through stage 6.
    (2) A carried pin re-applied on every import, reverting a later pick on the new slot; the
    importer now records the code it landed on. (3) A pin outlived an undone recode — the next
    run would have applied it; the speaker PUT now takes it away (`drop_withdrawn_pins`).
    (4) The Mac's "pipeline busy" refusal, the missing cost estimate and an unreadable registry
    now log instead of returning silently.

23. **Built 6 Oct 2026 — the picker opens on the name, ready to overtype** (owner, the same
    day; web and Mac). A click on the current name always edits it, proposed or confirmed —
    Return on a proposed name left as it is is the yes, which replaces the first-click confirm of
    point 16. The picker opens with that name as a field, selected, so typing replaces it; Tab or
    an arrow goes to the list, Escape abandons the edit and the picker; the ✕ stays beside the
    field. A named participant has one field, their own name: no "New name for p3" row, since a
    participant record is one speaker's and typing over it is the rename. Moderators and
    observers keep the new-person field, because renaming Martin changes him everywhere. **The
    swap row is parked** (owner, 6 Oct 2026, `featureFlags.speakerSwap`, web and Mac): it does
    two things at once, and the need it answered was narrower — one paragraph credited to m1
    that was really p1, which is §K's paragraph question, not a whole-session exchange. Swapping
    every turn of both speakers is rare. The server's `swap_with` and its undo stay live and
    tested. Still open: §K, the paragraph question.

## §K — Paragraph and quote attribution: unsolved, and needed

*Recorded 6 Oct 2026, from a design conversation with the owner. Nothing here is decided
except where it says built. The speaker-level work above (§J7 R1–R3) fixes **who a speaker
is**; this part is about **who said a particular paragraph or quote**, which it does not fix.*

### K1 · Two questions that the transcript badge conflates

- **Naming is always speaker-wide.** Renaming from a paragraph means "this voice is Simon",
  never "only this paragraph". Every tool surveyed renames globally without asking.
- **Reassigning has a scope.** A whole speaker can be wrong (the pipeline inverted moderator and
  participant), or one paragraph (the transcription glued a question onto an answer). On the
  Sessions grid only the speaker question makes sense; in the transcript both are live, and
  the owner's first reading of the picker on a paragraph badge — *"this quote was actually
  from m1"* — is the paragraph question, which the picker as built answers as the speaker one.
- Three ways to draw the difference are in `docs/mockups/person-picker-decided-states.html`
  §5, marked speculative: (A) the paragraph asks "who said this?" and then offers the wider
  fix; (B) a this-paragraph / all-of-p1's toggle in the picker; (C) the speaker picker on a
  speaker strip, the paragraph badge for the paragraph only. Undecided. Until then the
  paragraph badge keeps opening the speaker-wide picker.

### K2 · Prior art (6 Oct 2026, from each product's own help pages)

- **Rename is global, unasked:** Otter, Descript, Dovetail, Trint, Looppanel.
- **Reassignment with a scope choice is one control plus a binary choice at the act:** Marvin
  ("one instance or across the transcript", plus a *Swap* of two speakers' dialogue), Grain
  ("this speaker block / all speaker blocks"), Rev (a "Change all [label] to:" checkbox).
  Nobody offers the wider fix afterwards, and nobody uses two places.
- **Microsoft Teams is not prior art for this** — corrected the same day by the owner. It knows
  who spoke from each person's login and microphone; its transcript text can be edited but a
  paragraph cannot be split or reassigned. Its "Just this one / Update all" belongs only to a
  Teams Room, where several people share one microphone and one claims their own lines.
- **Split is Enter in the text, then assign the new paragraph:** Dovetail (which refuses
  reassignment until every speaker is named), Trint, Condens. Descript's reassignment
  reportedly changes a whole consecutive run by default, and users have asked for it to
  change only the selected paragraph.
- **None of the research tools has roles that affect evidence** (Dovetail, Marvin, Condens,
  Looppanel treat "Interviewer" as a name). Excluding the moderator's words from evidence is
  Bristlenose's own; there is nothing to borrow.
- Where the problem lives: platform transcripts (Teams, Zoom) carry reliable attribution, so
  paragraph errors come mostly from recordings Bristlenose transcribes itself, plus shared room
  microphones.

### K3 · How quotes meet paragraphs today (read from the code, 6 Oct 2026)

- A quote stores the session, `participant_id` — **the session's first participant code, not
  the speaker of the paragraph it came from** (`s09_quote_extraction.py`) — start and end
  times, the verbatim excerpt, and a `segment_index` (the paragraph whose start is at or
  before the quote's, or −1 without timings).
- The transcript marks a quote by matching at read time: a paragraph whose start falls inside
  the quote's window and whose speaker code equals the quote's `participant_id`; moderator
  paragraphs are never marked (`routes/transcript.py`). No stored link; `segment_index` is not
  used there.
- Two suspected weaknesses, unmeasured: a quote starting partway into a paragraph may not mark
  it (the match wants the paragraph's start inside the window); and transcripts without timings
  put every paragraph at 0:00, where a time match means nothing.
- Consequence: moving one paragraph to the moderator would unmark it in the transcript but leave
  the quote in the evidence, credited to the participant (job 11). Evidence would have to become
  paragraph-aware — the speakers of the paragraphs a quote's window covers — or quotes credited
  per speaker at extraction.
- The same gap shows after a speaker-level recode out of participant (§J7 R2): a lecturing
  project manager recoded to observer leaves their lecture quotes in the evidence until the
  session is re-analysed — or hides every quote of the session, if they held the first
  participant code. Re-analysis (R3) puts both right.

### K4 · Split and join — stage 1 built, stage 2 not

- **Built 6 Oct 2026** (`design-transcript-editing.md` §"Split and join, stage 1"): Return at a
  caret splits a paragraph, same speaker; Backspace at a paragraph's start joins it to the one
  above; ⌘Z undoes. Recorded and replayed on every import. Quotes are not split.
- **Stage 2, reassign the second half**, is the paragraph question of K1 and waits on it.
  Drawn speculative in the mockup's §6.
- **Direct editing of a paragraph's words** is a distinct later piece (owner, 6 Oct 2026):
  connected to quote editing with revert but not the same, and wanted simpler; reuse that
  logic and UX if it fits. Not started; tracked with the live-editable-transcript item.

### K5 · What it needs

1. A decision on K1's scope options.
2. A reassignment the importer replays, like a split — keyed by paragraph, not by speaker label,
   since a paragraph has no label of its own to pin (R3's pins are per label).
3. Evidence that knows which paragraphs a quote spans, or quotes credited per speaker.
4. A decision on whether a paragraph reassignment re-extracts (paid, like R3) or relabels and
   leaves the evidence to a read-time rule.

Tracked in the maintainer's private planning notes as three items: per-paragraph
reassignment, per-quote reassignment, and what each means for re-analysis.

### K6 · Paragraph scope — built 6 Oct 2026

The answers to K5, as built. **1:** the owner's sticky switch, *Session | Paragraph*,
transcript only to start with (mockup §7). **2:** a third layout edit, `kind = "speaker"`, beside
split and join (migration 016): the paragraph's position and first words, and the **slot** it
moves to. Replayed on every import, undone by forgetting it, as a split is. **3:** evidence
reads which paragraphs a quote overlaps, but only in sessions where a paragraph was moved.
**4:** it relabels and does not re-extract. Nothing is paid for.

- **The switch.** Two words above the role toggle: semibold ink for the chosen one, regular
  grey for the other (`--bn-weight-semibold`, added for it). Session is today's picker
  unchanged. Paragraph asks "who said this one?" from **this session's speakers**, by role.
  It offers no rename (a name is the person's, everywhere) and no ✕. Under Moderator its last
  row is **New moderator** (owner, 6 Oct 2026): an unknown moderator the move makes, for a
  call collapsed into one voice, named afterwards from the paragraph's badge like any
  unknown speaker. The
  choice sticks for a run of paragraphs and goes back to Session on leaving the transcript
  (`utils/paragraphScope.ts`). On the Mac the same request carries `scope`, and a paragraph
  pick replies `{kind: "paragraph", slot}` (bridge contract version 9).
- **Evidence** (`speaker_slots.evidence_out` → `EvidenceOut.quotes`). A quote leaves when a
  paragraph its window overlaps was moved off its credited tag (`transcript_segments.moved_from`)
  and no paragraph it overlaps is still that tag's. A quote that spans a moved half and a kept
  half stays. Overlap is strict, so a paragraph that only touches the window does not count.
  Every evidence surface reads it through `counts`, so the Quotes lens, signals, dashboard,
  search, exports and the agent endpoint agree. The transcript stops marking the paragraph,
  because a quote marks only paragraphs credited to its own tag.
- **What it does not do.** A paragraph moved *into* the participant brings no quotes with it;
  only a re-analysis would find them, and R3's pins are per speaker label, not per paragraph.
  A move whose target slot has gone after a re-analysis (R3 renumbers) is refused at replay and
  logged, like a split whose words changed.

**Tested on real data** (6 Oct 2026, a copy of the "IKEA with uxfriends" trial run, through
serve's own API):

- The case it exists for is real. In session 1 the moderator's think-aloud instruction ("if
  you could think aloud… give me some first impressions") was credited to p1 and was a quote,
  `q-p1-431`, counted as the participant's evidence. Moving that one paragraph to the moderator
  took exactly that quote out (28 → 27 quotes) and left the neighbouring paragraphs and every
  other session alone. It survived a re-import, and undoing it out of order brought the quote
  back while the later edits stood.
- **Mixed paragraphs are common, so split then move is the everyday path.** The same session
  has the moderator's "…you told me you would go straight to search" and p1's "Yes. Well…" in
  one paragraph. Split at "yes", move the first half: works. The quote over both halves stays,
  correctly by the rule, but its verbatim still begins with the moderator's words. Fixing that
  is quote editing, not attribution.
- **A session with no moderator has nobody to move a paragraph to.** In 17 of 69 real sessions
  across the trial runs no moderator was heard. Most of these are solo think-alouds, where
  that is right. But one (`IKEA with uxfriends` s4) is a two-person call collapsed into one
  voice ("No, that's good. And have you been travelling at all?"). Hence the **new moderator**
  row, built the same day: split at "And", move the question to New moderator, and the
  session gains an unknown moderator, `m?`. Named "Kerri" from that paragraph's badge, it
  reads `m1 Kerri`, and both the move and the name survive a re-import. Mechanics: the server
  numbers the slot above every code the session has had (slots and the registry's issued
  codes), and records the edit as having made it (`token = 1`). The importer drops an
  unconfirmed moderator slot the transcript does not use, so the replay makes it again —
  unless the pipeline's own transcript now uses that code, when the move is refused rather
  than landed on a real speaker. Undo removes the slot if nothing else uses it.
- **Splitting a timed paragraph rewrote its text from Whisper's words**, lower-cased and
  unpunctuated ("(Speaker B) Interesting that you clicked…" became "told me you would go
  straight to search um"). Stage 1's split, found here; **fixed the same day**: the cut is
  still counted in the drawn words, which are aligned to the text's own words
  (`transcript_layout.text_cut`), and the text is cut where the chosen word landed, so both
  halves keep their case, punctuation and "(Speaker B)".
- **Word timings and paragraph text can disagree at the edges.** The moderator's opening words
  of that paragraph sat in the previous paragraph's word list. A cut counted in drawn words is
  consistent with what the researcher sees, which is the point, but the two sources are not
  the same text.
- Rough rate: short participant paragraphs ending in a question are 1–4% of participant
  paragraphs across four real projects. That is a noisy upper bound, since focus-group
  participants ask each other questions.

**Reviewed the same day; three fixes.** A moved paragraph is not joined to one that was not
(a join would lose `moved_from`, and the quote would count again); a move is replayed after the
import's speakers, since it checks its target against them; and on the scope words Escape
closes the picker and an arrow keeps focus on the words.

**Open, and each a decision:**

1. A new *observer* under Paragraph: not offered; the moderator row is the case seen.
2. Two rules for which paragraph a quote belongs to. The transcript marks paragraphs whose
   *start* falls in the quote's window; evidence uses *overlap*. A quote that starts partway
   into a kept paragraph and runs into a moved one counts and is marked nowhere. `segment_index`
   is an exact key both could use, and would cover untimed transcripts too.
3. A move the server refuses (the words changed, or the target speaker is gone after a
   re-analysis) is silent: the menu closes and nothing happens. Saying so needs a string.
4. Undoing a move out of order, then redoing it, puts it after a later join that depended on
   it, and that join stays refused on every replay. Splits and joins already have this
   property; a move is the first edit that creates a join's precondition.
5. Stickiness differs: on the web the switch itself sets it, on the Mac only a pick does.
6. Whether Paragraph opens on the person last picked, so a run is click then Return
   (mockup §7), and whether the switch spreads beyond the transcript.
7. `EvidenceOut` is a set subclass so every caller kept working; `bool(out)` no longer means
   "nothing is excluded" (`evidence_quotes` checks `.quotes` too). A dataclass would break
   callers loudly now instead.
