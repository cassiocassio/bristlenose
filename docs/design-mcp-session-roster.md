# MCP session roster — "who was in which session?"

_Status: spec revised after three reviews (correctness, parsimony, privacy), then widened on 14 Nov 2026 to serve the owner's report-drafting scenario (§2a): three commits, the roster, quote timing and a clearer empty search. Written by Claude Sonnet 5.5; the owner has not yet ruled on §9. Nothing is built. Parent: [design-mcp-server.md](design-mcp-server.md) §3, §4. People model: [design-people.md](design-people.md) §H H9, §J8._

## 1. The problem

An agent connected over MCP cannot answer "who was in session s1?". It is the first thing a researcher asks, and how they check that a re-code, an import or a re-run did what they meant.

Found 14 Nov 2026 in use: a participant code showed as `p3`, had no quotes, and both sessions listed one speaker, `m1`, with no participant. The agent could neither see the mapping nor explain the gap.

### Cause (read from the code)

`_tool_get_project_overview` in `bristlenose/server/mcp_server.py` builds each session row's `speakers` from `grounding.session_team()`, which keeps only moderator and observer slots (`speaker_slots.is_team`). Participants never reach a session row. They appear only in the project-wide `participants.speakers` list, with no link to a session. Also:

- A session with no team slot gets **no `speakers` key at all** (`if team:`), so absence is silent.
- `participants.speakers` mixes in the researcher (`m1`) while `participants.count` counts only `p…` codes.
- Nothing says how many quotes a speaker has.

The data is not missing: `speaker_slots.project_slots()` already returns every slot of every session.

## 2. Goal

One call gives the full roster of every session: every speaker, role, identity code, a name when Anonymise allows, and how many visible quotes they have in that session. It must show the confusing cases: a participant with no quotes, a session with no participant, an unidentified moderator, and quotes that belong to no listed speaker.

## 2a. The scenario this brief serves

The owner's own example, 14 Nov 2026: _"Ask Bristlenose about project X, find the best three clips under 30 seconds where users are most frustrated with login, find the UX tags and the expert-codebook evidence for why, put the clips in a deck (who we interviewed, what we learned, example clips, what's causing this), then I'll draft recommendations; research the fixes and write user stories with acceptance criteria."_

Mapped to what the tools can do (checked against the code):

| Step | Today | In this brief |
|---|---|---|
| Find frustrated login quotes | Works: `search_quotes` by sentiment and text, `intensity` on each row | no change |
| Under 30 seconds | **Cannot be answered**: rows carry a start time only (`end_timecode` is stored but not sent) | **Commit 2** |
| Best three | Only `intensity`; the agent guesses silently | **Commit 2**: a stated opinion (the researcher's stars, then quotes carrying strong signals, then intensity) and a `sort` parameter that says what it sorted by (§4b) |
| UX tags and expert evidence | `get_framework` (stance, author, tag definitions); literature citations per tag not checked | no change |
| Who we interviewed | **Cannot be answered** | **Commit 1** |
| What we learned, what's causing this | Works: `get_signals`, framework | no change |
| The clips themselves in the deck | Not possible | Out of scope; the media spike (§7) |
| Fix research, user stories, ACs | The agent's own work | nothing needed |

So the brief is three small changes that unblock this scenario's two blocked text steps, plus a walk-through test (§8) that runs the scenario's tool calls against the smoke project. The media half is recorded, not built.

## 3. Decision: complete the overview, add no tool

**`get_project_overview` session rows list every speaker.** No new tool. The overview is already "call this first", sessions are few, and the tool budget is small ([design-mcp-server.md](design-mcp-server.md) §4). A `get_session` tool would sit beside the misleading `speakers` field without fixing it.

## 4. Contract

Each `sessions.items[]` entry keeps its fields; `speakers` becomes complete and is **always present** (an empty list if the session has no slots); a session total is added:

```json
{
  "session_id": "s1",
  "session_date": "2026-09-27T10:22:40+00:00",
  "duration_seconds": 3854,
  "visible_quotes": 31,
  "speakers": [
    {"code": "m1", "role": "researcher", "visible_quotes": 0},
    {"code": "p3", "role": "participant", "slot_code": "p1", "name": "Bettina", "visible_quotes": 31}
  ]
}
```

Rules:

1. **Every slot of the session is listed, in `project_slots` order** (by the transcript tag: moderators, participants, observers). The overview's current alphabetical re-sort is dropped. A recoded speaker keeps its place by tag but reports its current `role`. The three existing exact-equality assertions on session rows (`tests/test_mcp_server.py:1463`, `:1464`, `:1478`) change deliberately (§8).
2. **`code` is the identity code** (`Slot.code`), what the routes and transcripts show. **It is not always what quotes carry.** `search_quotes(participant=…)` and quote ids use the transcript tag (`Slot.slot_code`). They agree for a participant never recoded; they differ for identified moderators (`m2` over slot `m1`) and for recoded speakers. So a speaker carries **`slot_code` whenever it differs from `code`**, the same field `/sessions` already carries, so the agent can join a roster row to the quotes it sees.
3. **`role` is the slot's current role** (`researcher`, `participant`, `observer`).
4. **`name` appears only through the Anonymise gates**: team names from `resolve_session_speaker_names`, participant names from `resolve_speaker_names`. Never `slot.name` directly (it reads the persons table with no gate). Under Anonymise, no speaker has a `name` key. Both gates already read the desktop's global switch.
5. **`visible_quotes` per speaker is counted by `(session_id, slot_code)`**, case-insensitively, over the one set `search_quotes` uses: `speaker_slots.evidence_quotes` minus hidden, computed once in the overview. Do not rebuild it from "hidden excluded, recoded-out excluded" by hand; `evidence_out` also drops paragraph-moved quotes. Counting by `slot.code` is wrong and is the likeliest build mistake.
6. **The session's `visible_quotes` is the count of visible quotes with that `session_id`, not the sum of its speakers.** If it exceeds the sum, the difference is quotes credited to a tag with no slot in that session, which is exactly what an orphaned quote looks like. The tool description says so. No separate "orphaned" field.
7. **Per-speaker counts are visible-only.** Never extracted or hidden counts per speaker: which participant's quotes were hidden is a side channel to what the researcher found sensitive. The project-wide `hidden_by_researcher` total stays as it is.
8. **Unidentified moderators** keep reading `m?` / `mA?`.

`participants` (project-wide) keeps its shape. The tool description now says `participants.count` counts participants only, so the mismatch with a list that includes `m1` stops being a puzzle.

## 4a. Descriptions that must change together

- The `get_project_overview` docstring in `mcp_server.py`.
- The third copy in `desktop/mcpb/server/index.js:133` (the Node `.mcpb` proxy), which has already drifted ("participants" against "participants (codes only)"). `tests/test_mcpb_proxy.py` checks only that names match and descriptions exist, not their text, so the copy must be updated by hand and a text assertion added.

## 4b. Second change (separate commit): quote timing, so "under 30 seconds" can be asked

Quote rows carry `timecode` (the start) only. The database already stores `end_timecode` (`models.py`, `Quote`); it is simply not sent.

- Each `search_quotes` row gains **`end_timecode`** (same format as `timecode`) and **`duration_seconds`** (end minus start, rounded to one decimal, never negative).
- `search_quotes` gains **`max_duration_seconds`** (and `min_duration_seconds`), AND-combined with the other filters, validated as a positive number with a `ToolInputError` that teaches the unit.
- It describes the **quote's source speech**, which is what a clip of it would cover. A researcher's text edit does not change it. The tool description says so, and does not call it a clip length: where the clip starts and ends is decided by the clip work (§7), which may pad it.
- **"Best" gets a stated opinion (owner raised it, 14 Nov 2026; this reverses the earlier "no `sort`" ruling).** "Best three" is something people say to agents all the time, and left alone Claude will guess silently. Two layers, cheapest first:
  1. **A line in the MCP server instructions** (`build_instructions` in `mcp_server.py`, **not** the shared `grounding.INVARIANTS`: the chat lens's corpus lines carry `starred` but no intensity or duration, and the chat lens has no `sort`, so half the rule would point it at fields it never sees): when asked for the best quotes, **the owner's rule (14 Nov 2026): "best" is the researcher's stars plus quotes that carry strong signals**, a signal being strong by definition when several participants corroborate the same thing (what `get_signals` already ranks). So: prefer the researcher's **starred** quotes (their judgement beats any score), then quotes that support the strongest signals, then higher `intensity` to break ties; and **tell the user what "best" meant**. No code shape changes, and it works the day it ships.
  2. **A `sort` parameter with named keys**: `time` (today's default), `intensity`, `strength`. `strength` is documented as: starred first, then the quote's signal strength (the highest `composite_signal` among the curated signals it supports, over both lenses, from the same `load_signals` the tool already uses, so hidden quotes and unaccepted tags never count), then `intensity`, then time as the fixed tie-break. A quote supporting no signal ranks below one that does. Sorting happens **before** `limit` and `offset`, so "best three" is the best three of everything matched, not of the first page. Each result echoes `sorted_by` so the basis is never hidden. No LLM, no "clarity" score: Bristlenose cannot judge how well a quote reads, and says so in the description.
  Not added: a `max_per_participant` filter or a free-text "best for stakeholders" mode. Best depends on the audience, which only the researcher knows; the agent asks them when it matters.
- Quote ids and the citation currency are unchanged (`q-{participant}-{start}`), so existing cited ids stay valid.
- **Unknown length is `null`, never `0`.** A quote whose `end_timecode` is not greater than its start has `duration_seconds: null` (the importer writes `0.0` when a transcript has no timing, so "missing" cannot be told from zero, and untimed transcripts, docx or plain text, give every quote a null). Under `min_duration_seconds` or `max_duration_seconds` such quotes are **excluded**, and the result carries `duration_unknown_excluded` (a count) whenever a duration filter was used, so "under 30 seconds" returning nothing from an untimed project says why instead of looking like an empty study.

## 5. Third change (separate commit): say why a search is empty

`search_quotes(participant=X)` returns the same empty result for an unknown code and for a known code with no quotes. When `X` matches nothing, raise `ToolInputError` listing the valid codes, as `get_framework` does.

- **Valid set** = every slot's `code` and `slot_code`, including team codes and `m?`, plus the `participant_id` of every visible quote (so an orphaned tag whose quotes exist is never refused). Case-insensitive, matching the filter. Built from codes only, never from the gated name map (empty under Anonymise, which would say "no codes exist").
- **Message text** truncates and `repr`s the agent's value, as the sentiment error does (`{sentiment[:80]!r}`); `_run` logs only the class because the value can be text copied from a transcript.
- A recoded-out tag (`p1` now an observer) is not a slot code any more. It stays valid through its quotes' `participant_id` only while visible quotes carry it; the error otherwise says the code is unknown. Saying "recoded" in the message is a later improvement.
- Breaks one existing test (`tests/test_mcp_server.py:235`, `participant="p9"` expecting 0), which this change replaces.

## 6. Hard constraints (pinned today)

Read-only; no LLM call; no filesystem path in any input; names only through the two Anonymise gates; JSON primitives; bounded size (one row per slot); errors never leak `str(exc)`.

**The gate that proves the name rule is `test_no_names_in_any_tool_payload` (`tests/test_mcp_server.py:524-541`), not `tests/test_trust_mcp_name_map.py`.** The latter calls the resolver directly and cannot see the overview's own code, where a `slot.name` bypass would be written. Codes in a participant's session row are pseudonyms, not anonymity: with the recruitment calendar and the session date, a code can be matched to a person. That risk exists today through quote ids and session dates; this spec does not add to it and does not claim to remove it.

## 7. Out of scope (recorded so it is not lost)

- **The 14 Nov cause is not yet pinned.** It may be an app rename that orphans quotes, or the recode-in numbering rule (a team tag recoded as a participant becomes `p{max+1}` with no quotes, `speaker_slots.py:168-174`). Run the new roster against that project before scoping a fix: the session total against the speaker counts will say which.
- **Other judgement words, after "best" (owner, 14 Nov 2026: "best is one of many an agent will be asked, but high up there").** "Most frustrated", "most important", "most representative", "most surprising", "what should we fix first", "top themes" all invite the same silent guess. The principle: **Bristlenose defines what each common word means in terms of evidence it holds, once, in the server instructions, and the agent says which meaning it used.** Candidates to define when the time comes: _most frustrated_ (sentiment filter, then intensity); _most important_ (signal strength without the star bias); _representative_ (quotes from the largest theme, not the strongest signal); _what to fix first_ (not Bristlenose's call: it gives the evidence, the researcher decides). Added by the owner: _pain points_ and _things to fix_. **"Pain points" already means something in Bristlenose: it is a group in the UX Research codebook** (the overview lists it with its tag count), so the definition is the accepted tags in that group and the signals over them, and the instruction must say what to do when a project has not enabled that framework (say so, then fall back to the frustration and confusion sentiments, naming the fallback). _Things to fix_ is a pain point plus a judgement about fixability, which is the researcher's, so it resolves to the same evidence as _pain points_ and the agent says that. **The wider rule (owner, 14 Nov 2026): match the researcher's words to the codebook's language first.** A good researcher asks about "mental models", and Bristlenose already has a tag group by that name; a question in research vocabulary should become a tag or group lookup, not a text search, and the answer should be shaped like the report's signal cards (location, group, quote count, participants, confidence), which is what `get_signals` already returns. So the instruction says: read the overview's codebook groups and `get_framework`'s tag definitions to translate the question, filter by tag, say which tag or group it matched, and when nothing matches, say that and fall back to text. Today `search_quotes` takes one `tag` at a time and no group, so a "mental models" question is several calls; a `group` filter is the small code change (chunk C2). Build "best" first and write its instruction line so it is the first entry of a list, not a one-off; add the others only when a real session shows an agent guessing.
- **Participants list shape.** Splitting `participants.speakers` into researchers and participants is a shape change for the next contract revision.
- **A `session` filter on `search_quotes`**, reading a transcript, and a `curated_view_as_of` staleness stamp. Each its own small design.
- **`session_date` at day precision under Anonymise.** An owner decision about shape, not a blocker.
- **Thumbnails, clips and screens for the agent (owner's idea, 14 Nov 2026).** A quote so often refers to something on screen that the words alone are half the evidence. The owner's reframing: the main use is **building deliverables** (a report in Docs, a PowerPoint) where the clip, audio or screengrab goes into the output with its citation, so the agent needs a **file another tool can insert**, not a picture to look at. So the first slice is an export tool (quote id in; still, audio or video clip written out; location, quote text and citation returned), built on the existing clip export, with a link back into Bristlenose's Screens lens for the human researcher as the cheaper companion. It breaks today's "exposure is a text allowlist" and "no writes" rules; the Mac app is sandboxed, so the file lands in a researcher-chosen shared folder, never a path the agent supplies; and a clip carries a participant's voice and face, so the toggle (off by default, per project), Anonymise and the consent rules ([consent-gradient.md](methodology/consent-gradient.md)) are decided before any code. Needs its own spec; an inline still for the agent's own reasoning is the smaller, later feature.

  **Widened by the owner, 14 Nov 2026: the agent drafts the whole report.** With Claude Desktop's own Docs, Slides and Design, the agent will draft the report under the researcher's direction, wanting quotes, clips, audio, screens, the text of signals and tag counts. Two consequences. (1) The text half mostly exists already (`search_quotes`, `get_signals`, the codebook counts); what is missing is provenance in a form a report can print (a citation: participant code, session, timecode) and a way to reach the media for a quote. (2) **This undercuts the shared-folder idea above.** A Doc or Slides file hosted by Claude cannot read a file in a local folder; the bytes have to pass through the agent, which means through the MCP result itself (an image or embedded-resource content, size-capped), and what the client then lets the agent do with it is the client's business, which we do not observe. Audio and video clips are large, so a still may be the only media that can travel this way. **So the first step is a spike, not a design:** from Claude Desktop, can an MCP tool result carrying an image reach a Doc or a slide, and what is the size ceiling for audio? Only after that does the export-versus-inline question have an answer. The researcher stays in charge: these are evidence tools the agent calls on instruction, not a "write my report" tool.

  **Worked example from the owner (14 Nov 2026)**: "ask Bristlenose about project X, find the best 3 clips under 30 seconds where users are most frustrated with login, find the UX tags and the expert-codebook evidence for why, put the clips in a deck (who we interviewed, what we learned, example clips, what's causing this), then research fixes and write user stories with acceptance criteria." Checked against the code: finding frustrated login quotes works today (`search_quotes` by sentiment, text, `intensity`); the tags and framework stance work (`get_framework` carries author and bio; whether each tag carries a literature citation was not checked); "what we learned" works (`get_signals`). **Gaps:** (a) "who we interviewed" needs this roster; (b) **"under 30 seconds" cannot be answered: quote rows carry a start timecode only, no end or duration**, so a clip's length is unknown; (c) "best" has no ranking beyond `intensity`, so the agent will rank by its own judgement and should say so; (d) the clips themselves, the spike above; (e) the research and the user stories are the agent's own work and need nothing from Bristlenose. (b) is now in scope as §4b (end time and duration on a quote row), which the clip work needs anyway.

## 8. Tests

For the first commit (§4):

1. Through the protocol, not only by direct call: the smoke project's `s1` lists `m1` and `p1` with the right roles and counts.
2. A participant with zero visible quotes is listed with `visible_quotes: 0`; a session with no slots has `speakers: []`, never a missing key.
3. **Name gate.** Anonymise on by the project flag: no speaker has a `name`, and the whole-payload sweep passes. **Prove it can fail:** put `"name": slot.name` in the new builder and confirm the sweep goes red.
4. **Desktop switch.** `BRISTLENOSE_MCP_ANONYMISE=1` with the project flag off: no `name` key on any session-row speaker, and the sentinel name absent from the serialised overview. (Today's sweep sets only the flag, so a helper reading the flag directly would pass it and leak on the Mac.)
5. A hidden quote does not count; unhiding it does. A paragraph-moved quote does not count.
6. A speaker recoded to observer: listed under its new role, in both arms (named, giving `o<n>`; cleared, giving `o?`), `visible_quotes: 0`, `slot_code` carrying the old tag.
7. **Orphan arithmetic.** A visible quote credited to a tag with no slot: session `visible_quotes` exceeds the speaker sum by exactly that quote.
8. `slot_code` is present only when it differs from `code`. **A roster count equals the matching `search_quotes` rows for that session**: `search_quotes` has no session filter and a tag such as `m1` restarts in every session, so the test filters the returned rows by their `session_id` and compares; and hiding a quote moves the roster count and the search together. The per-speaker row has exactly the keys in §4 (no `hidden` or `extracted`), guarding the §4 rule 7 side channel.
9. The three exact-equality assertions at `tests/test_mcp_server.py:1463`, `:1464` and `:1478` are rewritten on purpose, in A1 and again in A2 (every speaker then gains `visible_quotes`). The `_two_moderators` fixture asserts nothing.
10. The `.mcpb` proxy description text matches the server's.

For the second commit (§4b): rows carry `end_timecode` and a `duration_seconds` that equals end minus start; `max_duration_seconds=30` returns only quotes of 30 seconds or less and combines with `sentiment` and `query`; a zero or reversed span reports `null`; an invalid value raises `ToolInputError`; through the protocol, not only by direct call; a text edit leaves the duration unchanged.

**No separate scenario walk-through test** (test review, 14 Nov 2026: it would be a shape snapshot that later scenarios copy, and the human QA step already walks it). Its two real assertions are folded into the existing sweeps: the duration and sort calls join the Anonymise sweep's payload list (`tests/test_mcp_server.py:527`), and a hidden quote's id must be absent from every payload. Further tests for this change: `sort` applies **before** `limit` and `offset` (`sort="strength", limit=3` over more than three matches returns the global best three); a hidden quote never ranks, even starred or high intensity; a quote whose sentiment badge was removed does not rank on stale intensity (the pattern at `mcp_server.py:251`); an invalid `sort`, or `min_duration_seconds` above `max_duration_seconds`, raises `ToolInputError`; `sorted_by` is always present (one assertion, not one per value).

For the third commit (§5): an unknown code raises with the valid codes and no sentinel name (add the call to the Anonymise sweep); a known code with no quotes returns empty; a case-insensitive match is accepted; an orphaned tag with visible quotes is not refused; the message truncates a long value; `tests/test_mcp_server.py:235` is replaced.

## 9. Rulings made in this draft, for the owner to confirm

- Order follows `project_slots` (by tag), not alphabetical (§4 rule 1).
- A speaker carries `slot_code` when it differs from `code`, accepting a second code on the roster because quotes cannot be joined to a roster row without it (§4 rule 2).
- Orphans are shown by arithmetic, not a field (§4 rule 6).
- Per-speaker counts are visible-only, for privacy and for the denominator (§4 rule 7).
- Quote timing ships as its own commit, before the empty-search error, because the scenario needs it (§4b).
- The `ToolInputError` change ships as its own, last commit (§5).

## 10. Build plan — eight small chunks

Each chunk is **one commit**, small enough to review at a glance, and green on its own: its own tests, then `tests/test_mcp_server.py`, `tests/test_trust_mcp_name_map.py`, `tests/test_mcpb_proxy.py`, `tests/test_mcp_helper_behaviour.py` and `tests/test_serve_heading_renames.py`, plus `ruff check .` and `mypy bristlenose/` (the mypy ratchet is held at 0, so a chunk that adds an error is not green). Tests are written first and seen red. Fix commits (A1, C1) carry `Found-by: own-use`. Nothing is pushed, tagged or released by this plan; the bump is a minor (house rule), made at release time.

```
Group A — the roster (who was in which session)
  A1 → A2          release together: A1 alone lists speakers but cannot yet show
                   the 14 Nov symptom, a participant with no quotes

Group B — quote timing, ranking and vocabulary (what the scenario needs)
  B1 → B2 → B3 → B4

Group C — optional, any time after A or B
  C1 (last in the spec's order, §5)    C2
```

**What the first draft got wrong, now fixed in the plan.** The old A1 (compute `project_slots` once) is **dropped**: it would change the signatures of the Anonymise gates (the most privacy-sensitive code in the module) for no new behaviour, and the repeated calls are cheap because sessions are few. If the repetition ever shows in a profile, do it then, with a snapshot test written first. The parameter-allowlist and proxy edits move into the chunk that adds the parameter, because `tests/test_mcp_server.py:822-828` (an exact allowed-names list) and `tests/test_mcpb_proxy.py:95-107` (proxy property names must equal the server's) both fail the moment a parameter appears.

**The Mac channel, stated once.** `desktop/mcpb/server/index.js` is the source of the tool list for both the Node `.mcpb` and the native helper (`desktop/mcp-helper/build-helper.sh` builds `TOOLS_JSON` from the `BN-TOOLS-JSON` block; `tests/test_mcp_helper_behaviour.py` reads the same block). Both answer `tools/list` **locally**, so a user's already-installed extension or helper will not advertise a new parameter until the helper is rebuilt and the extension reinstalled. Each chunk that adds a parameter edits `index.js`; the rebuild is one release step; "reinstall the extension to get the new inputs" is a release-note line and a human QA step.

### Group A — the roster

**A1. Every speaker on every session row.** `speakers` is always present (`[]` if none), lists every slot in `project_slots` order (the alphabetical re-sort goes), carries `slot_code` where it differs from `code`, and takes names only through the two Anonymise gates (never `slot.name`; and no `Person` string or annotation in `mcp_server.py`, which `tests/test_mcp_server.py:666` forbids). The model-facing text changes with it: `grounding.py:59-62` says "m1 is the same person in every session" and `build_instructions` (`mcp_server.py:111`) presents `p1, m1, o1` as the attribution codes, so both gain one sentence saying `slot_code` is the session-local transcript tag and `code` is the study-wide identity. The `get_project_overview` docstring, the matching sentence in `desktop/mcpb/server/index.js`, and a description assertion in `tests/test_mcpb_proxy.py` (comparing whitespace- and dash-normalised text, for the tools this plan touches only: the proxy's `search_quotes` and `get_signals` descriptions already differ from the server's, so a whole-file comparison would fail for old reasons). Tests, few and sharp (§8): **one roster test** over `s1`, an empty session and a recoded speaker (named and cleared arms, parametrised); the existing `TestNamesFollowTheSwitch` tests extended to cover session rows with the desktop environment switch on and the project flag off; the name sweep extended to the roster. **Mutation proof, done once by hand, not committed:** put `slot.name` in the builder, see the sweep red, remove it. The three exact-equality assertions are rewritten.

**A2. Visible-quote counts and the orphan arithmetic.** Per-speaker `visible_quotes` counted by `(session_id, slot_code)` over the one set `search_quotes` uses (`evidence_quotes` minus hidden, computed once), and the session's own `visible_quotes`. **One consistency test** (§8 item 8): for every roster row the count equals the matching `search_quotes` rows filtered by `session_id`; the session total equals the session's rows; an orphaned tag makes the session total exceed the speaker sum by exactly that quote (concrete numbers); hiding a quote moves both together; the speaker row has exactly the §4 keys. The three exact-equality assertions are rewritten again. Then **the real-project check**: call the overview against the 14 Nov project, read-only, and record in §7 which of the two causes it was. Release-note candidate: _Agents can now see who was in each session and how many quotes each speaker has._

### Group B — quote timing, ranking, vocabulary

**B1. Say where a quote starts and ends.** Rows gain `end_timecode` and `duration_seconds`, with the `null` rule of §4b (not greater than the start). Quote ids unchanged, with a test. The tool description calls it the quote's source speech, not a clip length. Tests: duration is end minus start; null for equal, reversed and zero spans; a text edit leaves it alone. Update `index.js`.

**B2. Filter by length.** `min_duration_seconds` and `max_duration_seconds` (with defaults, because `tests/test_serve_heading_renames.py:140,146` calls `_tool_search_quotes` with every keyword spelled out), the docstring, validation with a `ToolInputError` that names the unit, `min` above `max` raising, unknown-length quotes excluded and counted in `duration_unknown_excluded`. The allowed-names list at `tests/test_mcp_server.py:822-828` and `index.js` are updated in this chunk. Tests: boundary values 29.9, 30, 30.1; a combined call with `sentiment` and `query`; the null-duration quote under `max_duration_seconds=30`.

**B3. A stated opinion on "best".** `sort` (`time` default, `intensity`, `strength`, with a default so old callers work), `sorted_by` always echoed, `strength` = starred, then signal strength, then intensity, then time (§4b). **First check** that `get_signals`' `supporting_quotes` is not capped (if it is, build the quote-to-signal map from `load_signals` directly). The "when asked to rank" list goes into **`build_instructions`** (MCP only), with "best" as its first entry; the "no clarity score" note goes in the `sort` description. Allowlist test and `index.js` updated here. Tests (§8): starred beats an unstarred quote in a stronger signal; a quote in a stronger signal beats a higher-intensity quote in none; `sort="strength", limit=3` over more than three matches returns the global best three; a hidden quote never ranks; a removed sentiment badge does not rank on stale intensity; an invalid `sort` raises. `test_instructions_contain_every_invariant` is the only text pin, and a new instruction line breaks nothing; the "seven now" note in `design-mcp-server.md:41` is left alone because `INVARIANTS` is not changed.

**B4. The vocabulary lines.** In `build_instructions` only: the "pain points" and "things to fix" definitions with their fallback, the "match the researcher's words to the codebook, say which tag or group matched, fall back to text and say so" line, and the "answer in signal-card shape" line (§7). One test: each new line appears in the instructions. No behaviour change, so this chunk is cheap and can ship with B3 if the reviewer prefers.

### Group C — optional

**C1. A clearer empty search** (§5), last in the spec's order. The valid-code set, the truncated and `repr`d message, the error call added to the Anonymise sweep, `tests/test_mcp_server.py:235` replaced. If it lands after the description assertions, its docstring change edits `index.js` too.

**C2. Ask by codebook group.** A `group` filter on `search_quotes` (case-insensitive, accepted tags only, an unknown group raising `ToolInputError` that lists the project's group names), allowlist and `index.js` updated. Tests: the union of the group's tags' quotes and nothing from unaccepted proposals; it combines with `sentiment` and `max_duration_seconds`. Only after a real session shows an agent making several `tag` calls where one `group` would do.

### Around the chunks

- **Docs, in the chunk they belong to:** a changelog line in `design-mcp-server.md` (A2 and B3); the website's connect-an-agent page is owed if it describes the overview or the inputs (record in `TODO.md`, do not edit it from here).
- **Release-note candidates**, each added to `TODO.md` in its chunk: A2's line above; _Agents can find quotes by length, ask for the best ones, and see where each quote starts and ends. Reinstall the Claude extension to get the new inputs._ (B3).
- **Human QA after A2 and after B4**, not before: ask Claude "who was in each session?", recode a participant and ask again (names the recoded speaker, shows the gap); then the §2a scenario up to where the clips go in. Check the quotes are short, cited with participant, session and timecode, ranked as stated, with the basis named, and that nothing is hidden or named under Anonymise. Check an untimed project says why "under 30 seconds" is empty.
- **Not in this build:** everything in §7, including the clips and the media spike.
