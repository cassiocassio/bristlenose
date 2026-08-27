---
status: pending
last-trued: 2026-08-24
trued-against: HEAD@main on 2026-08-24
---

# People — who is in a study, and how the researcher fixes it

*Problem-first spec for person identity across Bristlenose: the jobs researchers
are trying to do, the UX that serves them, and — last, deliberately — the
functionality and data that fall out. Nothing here is built.*

## Changelog

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
| `SessionSpeaker` joins person↔session **per session**, carrying code, role and per-session stats | `server/models.py:265` |
| Two name fields exist and mean different things — `full_name` (the record) and `short_name` (what appears beside a quote) | `models.py` `PersonEditable` |
| Short-name derivation is genuinely careful — honorific stripping, family-name-first detection, 337 surnames, and collision handling that yields "Sarah J." / "Sarah K." | `people.py` `suggest_short_names` |
| `people.yaml` is canonical, the DB is a materialised view, and browser edits write through to both | `design-html-report.md` § People file |
| Speaker codes are the public identity; display names are a working tool | `SECURITY.md`, `docs/glossary.md` |
| **A name belongs to a code, and a code has one name — everywhere in the study.** `people.yaml` is keyed by code and holds one name per key | `people.py`, `models.py` `PeopleFile` |
| `p` codes are globally numbered across a study, so they never collide — one human returning gets several, which is normal | `s05b_identify_speakers.py:460` |
| `m`/`o` codes restart per session, which is the **right** answer whenever there is one moderator — about 95% of studies | `s05b_identify_speakers.py`, §E decision 1 |
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
  side. What is missing is entirely frontend: `bridge.ts` hard-codes
  `canUndo: false` and nothing ever posts `undo-state`. This is why §D prices the
  undo bridge as a **step-1 gate**.
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
| **No undo.** `NSUndoManager` used nowhere; the `undo-state` bridge channel is dead on both ends; `bridge.ts` hard-codes `canUndo: false` | `design-undo-catalog.md` § What exists today | all |
| **No recorded name origin**, so a confirmed guess and an unchecked guess are indistinguishable | `design-html-report.md` § Auto name/role extraction | J7 |
| **No `cleared` state** — a deleted name is refilled by the next run | roadmap; `people.py` `auto_populate_names` | J7 |
| **Anonymisation decides by code prefix**, not by person | `server/routes/export.py` `_anonymise_data` | J13 |
| **No read-time membership filter on the Quotes lens** — extraction is the only gate; a re-credited quote would stay visible wearing an `m` code | `routes/quotes.py` (verified: filters are project + quote-ids only) | J9 |
| **Observer speech is not excluded from quote extraction.** `s09` feeds `full_text()`, which tags every non-unknown role — so an observer's segments arrive marked `[OBSERVER]` — while the prompt's Rule 1 names only `[RESEARCHER]` and never mentions `[OBSERVER]`. Exclusion rests on the model generalising from "only extract participant speech" while being shown a tag it was never told about. `participant_text()` exists, filters to `PARTICIPANT`, and **is unused by `s09`** | `s09_quote_extraction.py:231`; `llm/prompts/quote-extraction.md:21`; `models.py:227-240` | J3 |
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
  only structural item here.

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
  why "I checked this" is unrepresentable today.
- **`cleared` must be sticky**, or deleting a name gets it refilled on the next
  run and the researcher is told they typed the name they deleted.
- Only **`guess`** invites action. The other five states are places to rest,
  which is why one italic treatment and one count line covers the whole machine.

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
| **1** | "m1 is me." · "That m1 is Steve." · "p4 is Jane Smith." · "Jane is an observer." | **Every session, every path** — 10–30 times a study | **Small — plus two real prerequisites, and one item that does not belong here (J1: role is a recode, so it belongs with step 4).** `PUT /people` exists; role needs one endpoint; "that's me" needs no typing. But **the bank has no store** — `Person` rows do not span projects today (§B4 spec), so it needs the instance DB of `design-multi-project.md` §2 first; and `NSFullUserName()` has zero uses in `desktop/`. But every step-1 act is drawn with an Undo, and the undo bridge is dead (`canUndo` hard-coded false, `NSUndoManager` used nowhere) — **the undo contract is a step-1 gate, not a parallel workstream** (§H, H4) |
| **2** | "Michel Hurlly is Mickael Hurley." · "Call him Mike." · "Yes, that guess is right." | Every study with raw audio | **Medium.** Name origin per field, a `cleared` state, a narrowed write payload, and a `full_name` editor |
| **3** | "That quote was Sarah, not Jane." | A few times a study — **and it is what gets published** | **Small-to-medium.** The speech moves (§B9): a whole-turn quote is one segment update; a fragment inside a longer turn is a turn split whose split point the quote's own timecodes supply. ⌘Z spans card and speech. Plus the lens needs the membership filter it currently lacks (§C4) |
| **4** | **What naming implies.** "p6 is the same Mary as p3." · "The moderator in s9 is Mike, not Martin" → Mike becomes `m2` | Follows from step 1 — **no separate UX, no blocking decision** | **Medium.** Speaker→person remap, moderator renumber, stats recompute. All bookkeeping behind an act the researcher has already performed |
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
(below, with the reasoning preserved); decision 2 is the one still owed.

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
  decision and is now free to ship. **But it does not yet do the other half of
  its job:** correcting `p → o` retags her segments `[OBSERVER]`, and the
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
   param and the dialog checkbox both default off.
2. `design-export-html.md:264` says "Role titles removed when anonymised";
   `routes/data.py:328` ships `role` untouched.
3. `grounding.py`'s `resolve_speaker_names` returns `{}` for *everyone* when
   anonymise is active, while `SECURITY.md:51` calls it "the same word and
   default as the export surfaces". Same word, different effect — and under
   decision 2 the MCP surface is now the one that is wrong.

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

**Held deliberately.** The dead `enums:speakerRole.*` block (4 keys × 21 locales)
is **not** deleted: verification found the census incomplete —
`design-i18n-wiring.md:76` instructs a future implementer to wire roles to those
very keys — and the near-homonym argument used to justify deleting it applies
equally to the proposed replacement. Reconcile the wiring doc first.

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
4. **"Someone New…" → "New Person…"?** Unshipped, so free to change; the
   indefinite pronoun forces masculine agreement in fr/ca/es. But §B4's warmth is
   deliberate and "New Person" reads as a create command rather than an escape.

Two more sit outside H1: whether an observer counts as research team for export
naming is **H3** (decision 2); and confirming ja **ターン** and zh-Hant **發言**
with native reviewers before they harden — 發言 deliberately assigns the same Han
characters the opposite role to ja, which a future consistency sweep will try to
undo. Both turn-nouns are marked *pending native review* in the CSV note.

---

## §I — The menu, enumerated (H5)

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
  in the field since 14 Jul remains valid input.

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
  large, and it is not yet settled.

### J5 · Free wins — defects that ship without waiting for any of this

Each is independent of every step above:

1. `_anonymise_data` blanking `role` (the job title) for `p*` — one line, and it
   closes a documented commitment the code has been violating.
2. ~~`/sessions`' top-level `moderator_names` / `observer_names`.~~ **Not a
   defect — struck 25 Aug 2026.** This was carried forward from a review written
   *before* decision 2 settled. Under decision 2 moderators and observers are
   named, so `_anonymise_data` leaving those lists alone is **correct**, and
   "fixing" it would have been a regression. Checked before touching: `/sessions`
   carries no top-level *participant* name list, and its per-session
   `speakers[].name` is already blanked for `p*`.
3. The export hint string, which names moderators and omits observers (§E
   decision 2 has the replacement copy).
4. The extraction prompt naming `[OBSERVER]` alongside `[RESEARCHER]`.
5. `test_anonymise_keeps_moderator_names`, whose body is a bare `pass`.
6. **A field-level allowlist test** asserting `/people`'s response key set
   *exactly equals* an allowlist. Ten lines, and it generically closes several of
   the above plus any future field added to the same dict — the export gate today
   is deny-by-default at route level and **allow-by-default at field level**.

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
