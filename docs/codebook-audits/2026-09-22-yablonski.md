# Audit: `yablonski.yaml` against *Laws of UX* and lawsofux.com

_22 Sep 2026. Read-only; nothing applied. File created `2a822d11` 19 Mar 2026; bio trimmed `3b2bc4ed` 21 Sep; one Norman cross-ref repointed `a19ae5a6` 22 Sep. No `version:`, no `renamed_from:`. No test pins its counts and no other codebook names a Yablonski tag, so renames orphan nothing outside the file — but must still carry `renamed_from:` for `codebook_sync`. Sources: lawsofux.com raw HTML (30 entries: 23 `theory`, 7 `psychology`), each law's page, Google Books for the 2020 edition, the author's own site and 2nd-edition post, Amazon/Blackwell's for the 2024 ISBN. O'Reilly and Medium block automated fetches._

## 1. Header claims

| Field | Claim | Verdict |
|---|---|---|
| `title` / `author` | Laws of UX / Jon Yablonski | VERIFIED |
| `author_bio` | "Product designer at Google" | **WRONG.** 2020 book bio: senior product designer at General Motors. His site today: Senior Product Designer at Mixpanel. No source places him at Google; the pre-trim bio said it too — wrong from origin. |
| | "based in Detroit" | VERIFIED |
| | "Created lawsofux.com in 2017" | UNVERIFIABLE — no source states a year; drop it |
| | "O'Reilly, 2020; 2nd edition 2024" | VERIFIED (21 Apr 2020, ISBN 9781492055280; 2nd ed. March 2024) |
| | "Each law originates with a named researcher… curation" | VERIFIED — every page has an Origins section |
| `author_links[0]` | lawsofux.com | VERIFIED |
| `[1]`,`[2]` | Amazon `dp/1098146964` 2nd ed. | VERIFIED (ISBN-13 9781098146962) |
| `[3]` | O'Reilly `…/9781098146948/` | UNVERIFIABLE (403s); the URL search engines index for the 2nd-ed book page is `…/9781098146955/`; label lacks the edition |
| `description` | "Hick's Law (choice paralysis)" | **MISSTATES.** Hick's: decision *time* rises with number and complexity of choices. Being overwhelmed and abandoning is a separate entry, **Choice Overload**. |
| `preamble` | "Not all 21 laws from the book" | **WRONG on both counts.** The *book* has **10** law chapters in both editions (the 2nd deepened chapters and added sections, not law chapters). "21" is a *website* count from an earlier snapshot. The codebook's own arithmetic reaches 21 only by counting **Cognitive Load** (a later Psychology entry, not in the 21) and silently omitting **Paradox of the Active User** and **Pareto**. Site today: **30** entries. |
| | Occam, Parkinson, Serial Position omitted as "design advice or analytical constructs" | INFERRED reasonable for Occam/Parkinson; Serial Position ("I only remember the first one") is arguably articulable — defensible omission, overstated reason |
| | "grouped by the cognitive mechanism they describe" | ours, not his (§3) |

## 2. Tag-by-tag

(a) his law, his sense · (b) his concept, our label · (c) not his. Definitions from lawsofux.com pages fetched 22 Sep 2026.

| # | Tag | Class | Yablonski vs ours |
|---|---|---|---|
| 1 | Hick: choice paralysis | **(b) mis-housed** | His Hick's is decision *time*. Ours ("overwhelmed… freeze, hesitate, or abandon") is his **Choice Overload** (Toffler 1970). Real law, wrong name. |
| 2 | Hick: decision simplicity | (b) | Positive pole; "Minimize choices when response times are critical". |
| 3 | Von Restorff: option salience | (b) drift | His: the differing item "is most likely to be remembered" — memory. Ours makes it attention→choice. |
| 4 | Thaler: default acceptance | **(c)** | Not on the site (30-card index). Default effect / Nudge (Thaler & Sunstein 2008). Padding. Nielsen `helpful default` / `risky default` already own the behaviour. |
| 5 | Jakob: convention expectation | (b) | Matches. |
| 6 | Jakob: transfer confusion | (b) | Matches his takeaway on transferred expectations. |
| 7 | Postel: input intolerance | (b) narrowed | His Postel covers "input, access, and capabilities"; ours is format strictness only. Say so. |
| 8 | Postel: input forgiveness | (b) | Fine. |
| 9 | Kahneman: peak moment | (b) | Matches. |
| 10 | Kahneman: ending effect | (b) | Fine. `not_this` calls it "Ending colours everything" — stale pre-rename name. |
| 11 | Zeigarnik: unfinished pull | (b) drift | His: uncompleted tasks are *remembered* better; ours is motivational tension. Minor. |
| 12 | Hull: completion momentum | (b) | Goal-Gradient; Hull attribution matches Origins. |
| 13 | Miller: memory overload | (b) misuses | Definition rests on 7±2; his first takeaway is *don't* use "the magical number seven" to justify limits. His **Working Memory** entry is the right parent. |
| 14 | Kurosu: beauty trust | (b) | Aesthetic-Usability. `not_this` calls it "beauty-trust transfer" — stale name. |
| 15 | Kurosu: aesthetic forgiveness | (b) | Fine. |
| 16 | Gestalt: grouping confusion | (b) collapsed | Five laws folded into one. **Prägnanz is not a grouping law** ("simplest form possible") — listed as if it were. |
| 17 | Gestalt: grouping clarity | (b) | As above. |
| 18 | Tesler: complexity burden | (b) | Fine. `not_this` "Complexity on user" — stale name. |
| 19 | Tesler: complexity absorbed | (b) | Fine. |
| 20 | Fitts: target difficulty | (b) | Covers size, distance and spacing — matches his three takeaways. |
| 21 | Sweller: cognitive overload | (a) but off-list | Real entry (Psychology; Sweller 1988) — not one of the "21" or in the book, contradicting the preamble. |
| 22 | Doherty: instant response | (b) | "<400ms" matches. |
| 23 | Doherty: waiting frustration | (b) | Fine. |

**His laws absent that participants do articulate:** Choice Overload (present under the wrong name), **Paradox of the Active User** ("I didn't read that, I just clicked" — `not_this` needed against UXR `self-taught`/`exploration`), **Selective Attention** ("I thought that was an ad"), Flow (optional). Rightly absent: Pareto, Parkinson, Occam, Chunking, Cognitive Bias, Mental Model (Norman owns it).

**The `Surname:` prefix convention is ours.** The site names laws in full; no page uses "Kurosu:", "Hull:", "Sweller:". A reader of the index would not recognise "Kurosu: beauty trust".

## 3. Structure

The six groups (Choice and decision / Expectation and convention / Memory and experience / Perception and aesthetics / Effort and complexity / Speed and responsiveness) are **ours**. lawsofux.com today has exactly two categories, `theory` (23) and `psychology` (7: Chunking, Cognitive Bias, Cognitive Load, Flow, Mental Model, Selective Attention, Working Memory). The earlier four-way Heuristic / Gestalt / Cognitive Bias / Principle taxonomy is INFERRED from third-party write-ups. Neither resembles our six; nothing on the site says "grouped by cognitive mechanism". The book has no grouping — one chapter per law. A site reader would also not recognise the "Thaler" tag, the Gestalt collapse, or "Speed and responsiveness" as a category of one law.

## 4. Cross-references (all inside this file; none inbound)

- `discoverability (Norman → Affordances and signifiers)` (l. 522, repointed 22 Sep) — Norman's group is **Discoverability**; should be `hidden feature (Norman → Discoverability)` or `missing signifier (Norman → Affordances and signifiers)`.
- `error situation (Nielsen H9)` (l. 205) — no such tag.
- `loss-of-control issue (Nielsen H3)` (l. 224) — no such tag.
- `error recovery issue (Nielsen H9)` (l. 276) — no such tag; `error recovery` is a **UXR** tag.
- `findability (Morville)` (l. 425, 522) — Morville's group is `Findable`.
- Three stale self-names: `beauty-trust transfer` (l. 380, 401), `Complexity on user` (l. 480), `Ending colours everything` (l. 279).
- Intact: `jargon barrier`, `model mismatch`, `ease of use` / `efficiency` / `aesthetic quality (Morville)`, `helpful default`, `risky default`, `internal inconsistency`, `cryptic error`, `progress indication` / `clear status` / `opaque status`, `metaphor fit` / `natural language`, `repetitive task`, `focused design` / `information overload`. None of the 22 Sep Norman renames is referenced.

## 5. Proposed patch — `version: "2.0"` (tags change)

**R (required)**
1. `author_bio`: drop "at Google" → "Senior product designer, based in Detroit" (don't pin an employer that moves). Drop "in 2017".
2. `preamble`: replace "Not all 21 laws from the book" with a true sentence: the book covers ten laws; lawsofux.com lists thirty; this codebook takes the ones participants narrate. Name Paradox of the Active User and Selective Attention as adopted or as deliberate omissions.
3. `description`: "Hick's Law (choice paralysis)" → "Choice Overload (choice paralysis), Hick's Law (decision time)".
4. **REMOVE** `Thaler: default acceptance` — not his; behaviour already coded by Nielsen H6/H5.
5. **Rename** `Hick: choice paralysis` → `Choice overload` (lawsofux.com/choice-overload), `renamed_from`; leave `Hick: decision simplicity` as the Hick's pole; add mutual `not_this`.
6. **Rename/reword** `Miller: memory overload` → `Working memory: overload` (lawsofux.com/working-memory), drop the 7±2 sentence.
7. Fix the four dangling cross-refs and the three stale self-names.
8. `discoverability (Norman → Affordances and signifiers)` → `hidden feature (Norman → Discoverability)`.
9. `author_links[3]` → `…/9781098146955/`, label "O'Reilly — Laws of UX, 2nd edition" (confirm in a browser).

**A (advisory)**
10. Add `Paradox of the Active User` and `Selective Attention` (both his; codeable).
11. `Von Restorff: option salience` — reword to "noticed and remembered".
12. `Gestalt: grouping confusion/clarity` — drop Prägnanz from the list or add "Prägnanz: ambiguous shape" separately.
13. Preamble: say the six groups are Bristlenose's and the site files entries only as Theory/Psychology.
14. Consider the law name in place of the `Surname:` prefix (`Hick's Law: decision simplicity`); if kept, note it is a house convention.
15. Header block and a register doc like Norman's.

Label summary: header wrongs (Google, 21-from-the-book, Hick=paralysis) VERIFIED against primary sources; the earlier four-category taxonomy and 2nd-edition chapter identity INFERRED from third-party write-ups; the site's current 30 entries and two categories read from raw HTML.
