"""All LLM prompt templates for Bristlenose pipeline stages."""

# ---------------------------------------------------------------------------
# Stage 5b: Speaker Role Identification
# ---------------------------------------------------------------------------

SPEAKER_IDENTIFICATION_PROMPT = """\
Below is the first ~5 minutes of a user-research interview transcript.
The speakers have been labelled automatically (e.g. "Speaker A", "Speaker B", or by name).

Your task: identify the role of each speaker.

Roles:
- **researcher**: The person conducting the research session. They ask structured questions, give instructions, facilitate discussion, and guide the participant through tasks or screens.
- **participant**: The research subject. They respond to questions, share opinions, attempt tasks, and provide feedback.
- **observer**: A silent or near-silent attendee (e.g. note-taker, stakeholder). They speak very little or not at all.

Transcript sample:
{transcript_sample}

Speakers found: {speaker_list}

For each speaker, assign exactly one role and explain your reasoning briefly.
"""

# ---------------------------------------------------------------------------
# Stage 8: Topic Segmentation
# ---------------------------------------------------------------------------

TOPIC_SEGMENTATION_PROMPT = """\
You are analysing a user-research transcript. Your task is to identify every point \
where the discussion transitions to a new screen, topic, or task.

The transcript below contains timestamped dialogue from a research session. \
This may be a moderated interview (researcher + participant) or a solo think-aloud recording \
(participant narrating their own experience with no researcher present). \
Either way, the conversation naturally moves between specific screens being evaluated \
and more general contextual discussion.

For each transition you identify, provide:
- **timecode**: the timestamp where the transition occurs (HH:MM:SS format)
- **topic_label**: a concise 3-8 word label for the new topic or screen
- **transition_type**: one of:
  - `screen_change` — the participant is shown or navigates to a new screen/page
  - `topic_shift` — the discussion moves to a new subject within the same screen
  - `task_change` — the participant is asked to perform a new task
  - `general_context` — the discussion moves to general context (job role, daily workflow, \
general software habits, life context) not specific to any screen
- **confidence**: how confident you are (0.0 to 1.0)

Include a transition at the very start of the transcript (timecode 00:00:00) to label the opening topic.

Transcript:
{transcript_text}
"""

# ---------------------------------------------------------------------------
# Stage 9: Quote Extraction & Editorial Cleanup
# ---------------------------------------------------------------------------

QUOTE_EXTRACTION_PROMPT = """\
You are extracting verbatim quotes from a user-research interview transcript.

## CRITICAL RULES

1. **Only extract participant speech.** Never quote the researcher. If present, the researcher's \
segments are marked [RESEARCHER] in the transcript. In solo think-aloud recordings there is \
no researcher — all speech is participant speech.

2. **Preserve authentic expression.** We need the piss and vinegar of real human speech — \
emotion, frustration, enthusiasm, humour, sarcasm, strong opinions, colloquial language, \
and even swearing. Never flatten or sanitise the participant's voice.

3. **Never paraphrase or summarise.** The quote must remain recognisably the participant's \
own words. If you can't extract a coherent quote, skip it rather than rewrite it.

4. **Editorial cleanup — dignity without distortion:**
   - Remove filler words (um, uh, ah, er, hmm) and replace with `...`
   - Remove filler uses of "like", "you know", "sort of", "kind of" and replace with `...`
   - Do NOT remove "like" when used as comparison ("it looked like a dashboard")
   - Lightly fix grammar where the participant would look foolish otherwise, but NEVER change \
their meaning, tone, or emotional register
   - Insert clarifying words in [square brackets] where meaning would be lost without them. \
For example: "the thing where it goes to the other thing" → \
"the thing where it goes to the other [screen]"
   - Preserve self-corrections that reveal thought process: "no wait, I mean the other one"
   - Mark unclear speech as [inaudible]
   - Preserve meaningful non-verbal cues: [laughs], [sighs], [pause]

5. **Researcher context:** In moderated sessions, if a quote is unintelligible without knowing \
the researcher's question, add a brief context prefix. Example: \
researcher_context = "When asked about the settings page"
Any words not actually spoken by the participant MUST be in [square brackets]. \
In solo think-aloud recordings this is rarely needed since the participant provides their own context.

6. **Quote selection:** Extract every substantive quote — anything that reveals the \
participant's experience, opinion, behaviour, confusion, delight, or frustration. \
Skip trivial responses ("yes", "OK", "uh huh", "right") unless they carry clear emotional weight. \
**However, always retain think-aloud navigational narration** — when a participant reads out \
menu items, filter options, page titles, or describes clicks and actions ("Home textiles and rugs. \
Bedding. Duvets.", "Add to shopping bag", "Continue as guest"), this is valuable data that shows \
the user's journey through the interface. Bundle short navigational sequences into a single quote \
that captures the path taken. Only skip truly empty utterances like isolated "Okay" or "Right" \
that carry no navigational or emotional information.

7. **Quote boundaries:** Each quote should be a coherent thought — typically 1-5 sentences. \
Split long monologues into multiple quotes at natural thought boundaries. Don't let a quote \
run so long that it loses focus.

## Topic boundaries for this session

{topic_boundaries}

## Transcript

{transcript_text}

Extract all substantive quotes from the PARTICIPANT segments, applying the editorial rules above.

For each quote, provide:
- Which topic/screen it relates to, and whether it is screen-specific or general context
- **intent**: classify the utterance type — one of:
  - `narration` — describing actions, reading UI elements, navigating ("I'm clicking beds")
  - `confusion` — expressing uncertainty or not understanding ("Why is that not working?")
  - `judgment` — evaluating, comparing, appraising ("That's quite cheap", "the photos are good")
  - `frustration` — expressing annoyance or difficulty ("Something's up with this")
  - `delight` — positive surprise or pleasure ("Oh I like that")
  - `suggestion` — proposing alternatives or preferences ("Maybe brown and orange")
  - `task_management` — session admin, meta-commentary ("This is enough data")
- **emotion**: the emotional tone — one of: `neutral`, `frustrated`, `delighted`, \
`confused`, `amused`, `sarcastic`, `critical`
- **intensity**: how strong the reaction is — `1` (low/neutral), `2` (moderate), `3` (high/strong)
- **journey_stage**: where in the user journey this occurs — one of: `landing`, `browse`, \
`search`, `product_detail`, `cart`, `checkout`, `error_recovery`, `other`
"""

# ---------------------------------------------------------------------------
# Stage 10: Quote Clustering by Screen
# ---------------------------------------------------------------------------

QUOTE_CLUSTERING_PROMPT = """\
You have a set of screen-specific quotes extracted from multiple user-research interviews. \
Each quote is tagged with a topic label, but different participants may have described the \
same screen or task differently.

Your task:
1. Identify the distinct screens or tasks discussed across all interviews
2. Normalise the screen labels — give each screen a clear, consistent name
3. Assign each quote to exactly one screen cluster
4. Order the screen clusters in the logical flow of the product/prototype being tested \
(i.e. the order a user would encounter them)

Provide a short, punchy subtitle for each screen cluster (under 15 words, no filler).

## Quotes

{quotes_json}
"""

# ---------------------------------------------------------------------------
# Stage 11: Thematic Grouping
# ---------------------------------------------------------------------------

THEMATIC_GROUPING_PROMPT = """\
You have a set of general/contextual quotes from multiple user-research participants. \
These quotes are about the participant's job role, daily workflow, software habits, \
life context, or other topics not specific to a particular screen being tested.

Your task:
1. Identify emergent themes across these quotes — what patterns, commonalities, \
or shared experiences emerge?
2. Give each theme a clear, concise label (e.g. "Daily workflow challenges", \
"Tool adoption barriers", "Team collaboration patterns")
3. Assign each quote to one or more themes (a quote may appear in multiple themes \
if genuinely relevant)
4. Provide a short, punchy subtitle for each theme (under 15 words, no filler)

## Quotes

{quotes_json}
"""
