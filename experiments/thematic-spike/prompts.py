"""Prompts for the spike. Kept separate from prototypes for easy diffing.

The BASELINE_* prompts are derived from the current
bristlenose/llm/prompts/thematic-grouping.md but generalised slightly
to handle pooled (SS+GC) input rather than only general_context.
"""

# ---------- Baseline & Option D / E share these --------------------------

BASELINE_SYSTEM = (
    "You are an expert qualitative researcher. You identify emergent themes "
    "across participant quotes. You work in the spirit of Braun & Clarke's "
    "reflexive thematic analysis: themes are constructed from the data, "
    "named in the researcher's voice, and grounded in evidence."
)

BASELINE_USER = """You have a set of quotes from multiple participants in a study. \
The quotes are a mix of reactions to specific things they were doing and broader \
contextual observations. Treat them as one pool — don't separate them.

Your task:
1. Identify emergent themes across these quotes — what patterns, commonalities, \
or shared experiences emerge?
2. Give each theme a clear, concise label (3–6 words).
3. Write a short description (1–2 sentences) capturing what the theme is about.
4. Assign each quote to exactly one theme (pick the strongest fit; the researcher \
will reassign if needed).
5. Aim for between 5 and 12 themes — enough granularity to be useful, not so much \
that the researcher drowns.

Return JSON in this exact shape:
{
  "themes": [
    {
      "label": "...",
      "description": "...",
      "quote_indices": [0, 3, 7, ...]
    },
    ...
  ]
}

## Quotes

{quotes_json}
"""


# ---------- Permission variants (perm_a/b/c) -----------------------------
# Single-call variants of the baseline that grant the LLM one explicit
# permission today's prompt withholds. Each tests whether the model can
# do better when allowed.

PERM_A_USER = """You have a set of quotes from multiple participants in a study. \
The quotes are a mix of reactions to specific things they were doing and broader \
contextual observations. Treat them as one pool — don't separate them.

Your task:
1. Identify emergent themes across these quotes — what patterns, commonalities, \
or shared experiences emerge?
2. Give each theme a clear, concise label (3–6 words).
3. Write a short description (1–2 sentences) capturing what the theme is about.
4. Assign each quote to exactly one theme (pick the strongest fit; the researcher \
will reassign if needed).
5. Aim for between 5 and 12 themes — enough granularity to be useful, not so much \
that the researcher drowns.

Some quotes may not belong to any theme — filler, narration, off-topic asides, \
throat-clearing. Leave these in `unassigned` rather than straining to fit them \
into a theme. It is correct and expected to leave 15–25% of quotes unassigned.

Return JSON in this exact shape:
{
  "themes": [
    {
      "label": "...",
      "description": "...",
      "quote_indices": [0, 3, 7, ...]
    },
    ...
  ],
  "unassigned": [2, 5, ...]
}

## Quotes

{quotes_json}
"""


PERM_B_USER = """You have a set of quotes from multiple participants in a study. \
The quotes are a mix of reactions to specific things they were doing and broader \
contextual observations. Treat them as one pool — don't separate them.

Your task:
1. Identify emergent themes across these quotes — what patterns, commonalities, \
or shared experiences emerge?
2. Give each theme a clear, concise label (3–6 words).
3. Write a short description (1–2 sentences) capturing what the theme is about.
4. Assign each quote to exactly one theme (pick the strongest fit; the researcher \
will reassign if needed).
5. Produce as many or as few themes as the data warrants. Don't force a number. \
Some corpora have 6 distinct themes, others have 18 — let the data decide.

Return JSON in this exact shape:
{
  "themes": [
    {
      "label": "...",
      "description": "...",
      "quote_indices": [0, 3, 7, ...]
    },
    ...
  ]
}

## Quotes

{quotes_json}
"""


PERM_C_USER = """You have a set of quotes from multiple participants in a study. \
The quotes are a mix of reactions to specific things they were doing and broader \
contextual observations. Treat them as one pool — don't separate them.

Your task:
1. Identify emergent themes across these quotes — what patterns, commonalities, \
or shared experiences emerge?
2. Give each theme a clear, concise label (3–6 words).
3. Write a short description (1–2 sentences) capturing what the theme is about.
4. Assign each quote to exactly one theme (pick the strongest fit; the researcher \
will reassign if needed).
5. Aim for between 5 and 12 themes — enough granularity to be useful, not so much \
that the researcher drowns.

Critically: do NOT produce themes that just restate what the study was about. \
Theme labels like "Technology", "Open source", "Shopping", "Navigation", \
"Performance" are useless because the researcher already knows the brief. Theme \
labels must be specifically about what participants said and felt — not the \
topic they were asked about.

Return JSON in this exact shape:
{
  "themes": [
    {
      "label": "...",
      "description": "...",
      "quote_indices": [0, 3, 7, ...]
    },
    ...
  ]
}

## Quotes

{quotes_json}
"""


# ---------- Option B: per-quote code extraction --------------------------

CODE_EXTRACT_SYSTEM = (
    "You are a qualitative coder. You extract short conceptual codes from "
    "research quotes — the kind a researcher would write on a sticky note. "
    "Codes are short noun phrases capturing what the quote is *about*, not "
    "literal restatements."
)

CODE_EXTRACT_USER = """Read this quote and extract 1 to 3 short codes (1–4 words each) \
that capture what it's about conceptually.

Examples:
- "The page took ages to load" → ["performance frustration", "wait time"]
- "I always check Amazon first before buying" → ["comparison shopping", "default vendor"]
- "I just thought central London hospitals must be better" → ["geographic assumption", "trust by proxy"]

Quote:
[{participant_id} | {topic_label}] {text}

Return JSON: {{"codes": ["code one", "code two"]}}
"""


# ---------- Option B: name a code-cluster --------------------------------

NAME_CLUSTER_SYSTEM = (
    "You are a qualitative researcher naming a thematic cluster of codes. "
    "Your job is to give the cluster a clear, useful theme label and "
    "description in the researcher's voice."
)

NAME_CLUSTER_USER = """The following codes were grouped together by similarity. \
Give the cluster a theme label (3–6 words) and a short description (1–2 sentences) \
capturing what the cluster is about.

Codes:
{codes_list}

Sample quotes from the cluster:
{quotes_sample}

Return JSON: {{"label": "...", "description": "..."}}
"""


# ---------- Option C: per-participant theme draft -----------------------

PER_PARTICIPANT_SYSTEM = BASELINE_SYSTEM

PER_PARTICIPANT_USER = """You have all the quotes from one participant ({participant_id}). \
Identify the themes that emerge from this participant's quotes alone. Don't worry \
about how they fit with other participants — that's a later step.

Return between 2 and 6 themes in JSON:
{{
  "themes": [
    {{"label": "...", "description": "...", "quote_indices": [...]}},
    ...
  ]
}}

## Quotes

{quotes_json}
"""


# ---------- Option C: merge candidate themes into corpus themes ---------

MERGE_THEMES_SYSTEM = (
    "You are a qualitative researcher consolidating draft themes from "
    "multiple participants into a coherent theme set for the whole study."
)

MERGE_THEMES_USER = """Multiple participants were each independently themed. The \
candidate themes below come from those per-participant analyses. Many of them \
overlap or restate each other.

Your task: produce a consolidated theme set covering the whole study (5–12 themes). \
Merge restatements; promote patterns that appear across participants; drop themes \
that turned out to be one-off observations.

Return JSON:
{{
  "themes": [
    {{"label": "...", "description": "...", "source_drafts": [<indices into the candidate list>]}},
    ...
  ]
}}

## Candidate themes

{candidates_json}
"""


# ---------- Option C: re-assign quotes to merged themes -----------------

REASSIGN_SYSTEM = (
    "You are a qualitative researcher assigning quotes to a finalised theme set."
)

REASSIGN_USER = """Here is the finalised theme set for the study:

{themes_json}

Assign each of the following quotes to exactly one theme (pick strongest fit). \
If a quote really doesn't fit any theme, assign theme_index = -1.

Quotes:
{quotes_json}

Return JSON: {{"assignments": [{{"quote_index": 0, "theme_index": 2}}, ...]}}
"""


# ---------- Option D: review and refine -------------------------------

REVIEW_SYSTEM = BASELINE_SYSTEM

REVIEW_USER = """A first-pass thematic analysis was done over these quotes. Review \
the result against the full quote set with a critical eye:

- Are any themes too thin (only 1–2 quotes from 1 participant)?
- Are any themes too broad / a dumping ground?
- Are any quotes obviously mis-assigned?
- Are there patterns the first pass missed entirely?

Produce a *revised* theme set (5–12 themes) with quote re-assignments. You may \
merge, split, rename, or introduce new themes. Aim for themes that a researcher \
would find genuinely useful as a triage scaffold.

Return the same JSON shape as before:
{{
  "themes": [
    {{"label": "...", "description": "...", "quote_indices": [...]}},
    ...
  ]
}}

## First-pass result

{first_pass_json}

## All quotes

{quotes_json}
"""


# ---------- Option H: bottom-up mini-clusters (KJ-method shape) ---------

MINICLUSTER_SYSTEM = (
    "You are a qualitative researcher producing affinity-diagram-style mini-clusters "
    "from a pool of participant quotes. You work in the KJ-method tradition: many "
    "small, tight, conservatively-bounded clusters of quotes that say nearly the "
    "same thing. The researcher will group these mini-clusters into chapters "
    "themselves later — your job is the bottom layer only, not the top layer."
)

MINICLUSTER_USER = """You have a pool of {n_quotes} quotes from multiple participants. \
Produce many small, tight mini-clusters in the KJ-method / affinity-diagramming \
tradition. The researcher will group these into chapters themselves later — do not \
do that step.

Hard rules — read carefully, these override any habit you have toward chapter-grain themes:

1. **Many small clusters, not few large.** Aim for 20–40 mini-clusters. Each cluster \
contains **3–8 quotes** that say nearly the same thing. Do NOT produce 5–12 broad themes.

   **HARD FLOOR: every cluster must have at least 3 quotes.** If you cannot find at \
least 3 quotes that say nearly the same thing, do NOT create a cluster — put those \
quotes in `unassigned`. A 1-quote or 2-quote cluster is always wrong; better to leave \
the quote unassigned than to ship a singleton. Sanity check before returning: count \
the quote_indices on every cluster; if any has fewer than 3, either merge it into a \
related cluster or move its quotes to `unassigned`.

2. **Conservative membership.** When in doubt, exclude. A 4-quote tight cluster beats \
an 8-quote bloated one. Quotes that are merely related to the cluster's idea but not \
saying the same thing belong elsewhere or in `unassigned`.

   It is better to return 12 strong 4-quote clusters with 50% unassigned than 60 \
weak singletons. The corpus may simply not support 20–40 mini-clusters — that is a \
real finding, not a failure. Adapt the count to what the data actually supports.

3. **Cross-participant clusters are gold.** A 5-quote cluster from 5 different \
participants is the strongest possible signal. A 5-quote cluster from 1 participant \
is much weaker and should usually be split, dropped, or left mostly in `unassigned` — \
unless that one participant said something genuinely deviant-case worth surfacing on \
its own. Default to multi-participant clusters.

4. **No brief-restating labels.** The researcher already knows what the study was \
about. Do NOT use any of these words or close synonyms in cluster labels:
{corpus_banlist}
Cluster labels must be specifically about what participants said, felt, or did — \
never about the topic they were asked about.

5. **Terse labels (3–5 words).** Descriptive, not interpretive. \
*"Comparison anchors expectations"* not *"Participants frequently demonstrated \
comparative thinking patterns"*. *"Wait time triggers abandonment"* not *"Performance \
issues"*.

6. **No prose descriptions.** Labels stand alone — leave description empty.

7. **Best quote per cluster.** For each cluster, flag the single most articulate, \
concise, slide-ready quote as `best_quote_index`. Pick the one a researcher would \
put on a slide.

8. **Permission to leave unassigned.** Filler, narration, off-topic asides, and \
quotes that don't tightly fit any cluster belong in `unassigned`. Expect 15–25% \
of the corpus to end up unassigned. This is correct, not a failure.

9. **No chapter-grouping.** Return a flat list of mini-clusters. Do NOT group them \
into super-themes or chapters.

Return JSON in exactly this shape:
{{
  "clusters": [
    {{
      "label": "terse 3-5 word descriptor",
      "quote_indices": [12, 47, 88, 102],
      "best_quote_index": 47
    }},
    ...
  ],
  "unassigned": [3, 19, 22, ...]
}}

## Quotes

{quotes_json}
"""


# ---------- Option E: reconcile multiple runs --------------------------

RECONCILE_SYSTEM = (
    "You are a qualitative researcher consolidating themes from multiple "
    "independent passes over the same quote set. Your job is to identify "
    "which themes are genuinely stable across runs (high confidence) and "
    "which are unstable (interesting but provisional)."
)

RECONCILE_USER = """The same quote set was analysed {n_runs} times independently. \
Each run produced its own theme set. Reconcile these into a final theme set \
that flags stability:

- A theme that appears (in spirit, not necessarily by exact label) in 3+ runs \
is "stable" — high confidence
- A theme appearing in 2 runs is "tentative"
- A theme appearing in only 1 run is "single-run" and should usually be dropped \
unless it captures something genuinely important

Produce a final theme set (5–12 themes) with stability flags and quote assignments. \
Use the union of quote assignments across runs where they agree.

Return JSON:
{{
  "themes": [
    {{
      "label": "...",
      "description": "...",
      "stability": "stable" | "tentative" | "single-run",
      "appears_in_runs": <int>,
      "quote_indices": [...]
    }},
    ...
  ]
}}

## Runs

{runs_json}
"""
