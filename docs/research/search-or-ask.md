---
status: research
date: 4 Oct 2026
---

# Search or ask: where Bristlenose's AI belongs, medium term

Speculation from a conversation with the owner on 4 Oct 2026, about the medium
future. It does not reopen today's decisions (MCP is the chat lens; the search
field is quick find; see [`search-best-practice.md`](search-best-practice.md)
§Proposed sequence). Quick fixes to search are that session's job.

## The deliverable is a meeting, not a report

The researcher's output is a choreographed meeting: six people, about 20
minutes of tight presentation, 20 of discussion, 10 of decisions. About 30
slides are prepared and roughly 10 are skipped in the room. There may be 10
minutes on a Miro board of finding clusters around a screenshot, and a
one-minute video to make a point.

So Bristlenose is almost never what stakeholders see directly. It is the
researcher's **workbench**: where the evidence and the speaking notes for each
piece are gathered (say, a two-slide piece on price elasticity). The HTML export
is a leave-behind for the stakeholder who wants to check, not a document to be
read.

The containers already fit:

- **Themes and sections** are the general-purpose contract. A slide piece is a
  theme: heading = the point, commentary = speaking notes, quotes = evidence.
- **Tags** are granular, and **signals** surface them ("6 of 9 participants").

## AI finds, filters and counts. It does not write the argument.

> "AIs are sending everyone 100,000 words a day of stuff that humans can't read."

Measured in the conversation that produced this note: the assistant wrote
3,073 words and the owner 307, in 419 seconds. The gaps in which the owner
could read totalled 298 seconds, which also had to cover typing 307 words.
Silent reading of non-fiction runs at about 238 words a minute (Brysbaert,
2019), and web readers read at most 28% of a page's words, 20% more
realistically (Nielsen, 2008). Most of the output was never read.

So Bristlenose should make the researcher read **less**, and every word they
do read should be checkable:

- **The AI reduces**: finds the 12 relevant quotes among 2,000, notices they
  come from 3 participants, surfaces the one that contradicts the point.
- **The researcher writes**: the heading, the 40 words of notes, the choice of
  quote. It stays short because a person wrote it, and they can defend it in
  the room.
- **Evidence is verbatim**: short, human, attributed, linked to the moment.

Structure the AI proposes (tags, groupings to accept or reject) is fine. Prose
someone then has to read is not.

## Researchers bring their own frames, immediately

A researcher wants to group the evidence by their own lens straight away, for
example pricing anxiety by price-perception theory. Today that happens in
Claude over MCP, and the frame stays in the chat.

The author-only rule applies to codebooks that carry someone else's name
(Norman, Garrett). A researcher's own frame is theirs and needs no hedging.
The medium-term shape: a conversation is the fastest way to *author a
codebook*. The researcher describes the frame, the agent drafts groups and tags
and applies them, signals appear. The provenance worth keeping is which tags
the agent applied, so they can be reviewed.

This implies an MCP write path: proposed **tags** and **themes**, with quote
IDs rather than quote text. Signals stay computed, never asserted by a model.

Open: if agent-built themes share the contract, quote exclusivity needs a
scope. A meeting's pieces look like a **separate set** over the same quotes,
exclusive within the set, so preparing a piece does not take quotes out of the
analysis.

## Every search box is "search or ask"

> "Every search box is a 'Search or ask' box in users' minds."

Intuitively we all do this all day now, or soon will, and user researchers
certainly will, even where the general public is slower. Google, browser address
bars and chat products have taught people that whatever they type is
understood. The bar in `search-best-practice.md` (Google is the minimum
experience) is the same observation.

Today, typing *how are users worried about prices?* and pressing Enter searches
for that exact phrase and returns "No quotes match current filters". That reads
as "the data has nothing on this", which is the worst answer.

Medium term: **one box, and the user never has to choose between searching and
asking.** What is distinctive is what an ask returns. Elsewhere it is a
paragraph; here it is **the evidence**, the relevant quotes, perhaps grouped
under a few short labels, landing in the lens where they can be starred, tagged
and turned into a slide piece. Search and ask lead to the same result screen and
differ only in how well the input is understood.

That is roughly what remains of the chat lens once the prose is removed, which is
why parking it costs little.

The split:

| Surface | Job | Output |
|---|---|---|
| The box (search or ask) | Find evidence | Quotes |
| The researcher's own agent, over MCP | Think: frames, arguments, the meeting | The researcher's slides, Markdown, notes |

Not settled:

- Whether understanding a question runs as an LLM call per search (cost,
  latency) or locally with embeddings.
- How this sits with today's narrowing, which put meaning with the agent and
  kept the field lexical. This note says the medium-term box understands; it
  does not say when.

## Three places the ask can happen

Information workers like user researchers will expect one of three things
(owner, 4 Oct 2026):

1. **The app does it.** The box understands (above).
2. **They skip the app** and ask their agent, which reaches Bristlenose over MCP.
3. **Their agent turns up inside other apps**, carrying Bristlenose with it.

Example of the third: in Figma Make, prompt *"make sample data for that table:
ask Claude to synthesise it from a mix of NHS data and what Bristlenose thinks
the practice managers meant when they talked about diabetes in the Thursday
sessions."* The Bristlenose surface there is not a page at all, just MCP answers
consumed in a designer's tool.

What that asks of the MCP tools:

- **Filters a researcher speaks in**: by participant role ("practice managers")
  and by topic ("interviews about diabetes"). Not by interview date (owner,
  4 Oct 2026). `search_quotes` takes participant, section, theme, tag and
  sentiment today. Participant role (owner's name for it, not "job title") is a People schema enhancement: `Person.role_title`
  exists as free text, extracted by the pipeline and never shown in the report;
  see [`design-people.md`](../design-people.md) §H owner call 3.
- **Meaning, still grounded**: "what they meant" is interpretation, so the answer
  should be quotes plus the themes and signals Bristlenose already computed, not
  a fresh summary.
- **Governance travels too**: participant words synthesised into sample data in
  another app leave the anonymisation boundary. Pseudonymised codes, redacted
  text and the consent gradient
  ([`consent-gradient.md`](../methodology/consent-gradient.md)) must hold in
  whatever the agent hands on, because Bristlenose cannot observe the client.

## MCP has to reach every format of the meeting

The agent helps choreograph across slides, Miro and video ("my strongest clip
for this point", "three quotes if I only get 40 seconds"). Quotes, attribution,
timecodes and signal counts are reachable over MCP today. Clips and Miro
clusters are not.

## Sources

- Brysbaert, M. (2019). How many words do we read per minute? A review and
  meta-analysis of reading rate. *Journal of Memory and Language*, 109.
- Nielsen, J. (2008). How little do users read? NN/g —
  https://www.nngroup.com/articles/how-little-do-users-read/
- NN/g on AI and search behaviour, cited in
  [`search-best-practice.md`](search-best-practice.md).
