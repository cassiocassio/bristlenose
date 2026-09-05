"""The six real stage prompts, filled the way the pipeline fills them.

WHY THIS REPLACED A HAND-WRITTEN PROMPT

`check-providers-live.py` used to ask one invented question: a two-line
transcript and "extract up to 2 quotes". It reproduced a Sonnet 5 double-encoding
that the *real* extraction prompt does not, and it could not see the failures
that actually stopped the Sonnet 5 move, which were at **quote-clustering** and
**thematic-grouping**. So it was simultaneously a false positive and blind to the
true ones — the worst combination a fixture can have, because both readings look
like signal.

Everything below is loaded from `bristlenose/llm/prompts/` through the same
`get_prompt_template` the stages call, wrapped with the same
`wrap_untrusted` envelope, and validated against the same Pydantic model. The
only thing invented is the *content* of the transcript, and it is deliberately
natural rather than terse — a schema is easy to satisfy on a clean two-line
sample and the failures show up on real phrasing.

WHAT THIS STILL CANNOT PROMISE

One pass is not a run. Clustering and grouping are the two stages whose output
varies most between identical calls, so a green pass here means "the shape came
back right once", not "the pipeline will complete". That is why the stability
corpus is a separate, still-owed piece of work and not something this replaces.

Cost: six calls per model. Roughly 4c per model per pass at 2026 prices, so a
full sweep of the seven shipped models is a few tens of pence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import (
    QuoteExtractionResult,
    ScreenClusteringResult,
    SpeakerRoleAssignment,
    SpeakerSplitAssignment,
    ThematicGroupingResult,
    TopicSegmentationResult,
)

# A short but naturally-phrased session. Hesitations, self-corrections and a
# trailing clause are all deliberate: the terse sample this replaced never
# produced the malformed output the pipeline sees.
TRANSCRIPT = """\
[00:00:02] SPEAKER_00: Right, so thanks for making the time. Could you walk me
through the last time you had to file one of these?
[00:00:11] SPEAKER_01: Sure. So it was — I think it was the Tuesday before last?
I'd got the email saying the renewal was due, and I clicked straight through
from that, which I now realise was the mistake.
[00:00:27] SPEAKER_01: It took me to the login, fine, but then after logging in
it just dumped me on the dashboard. Not the renewal. So I'm sat there going,
right, where's the thing I came for.
[00:00:44] SPEAKER_00: And what did you do at that point?
[00:00:47] SPEAKER_01: Hunted. There's a menu on the left, and honestly I went
through it twice before I found it, because it's called "Policy actions" and I
was looking for the word renew. Which, you know, is what the email said.
[00:01:09] SPEAKER_01: Once I was in the actual form it was fine. Genuinely,
that bit was quick, maybe two minutes. It's everything before it that I'd
change.
[00:01:21] SPEAKER_00: You mentioned the email — anything about that you'd
change?
[00:01:25] SPEAKER_01: Make the link go where it says it goes, really. That's
it. I don't need it to be clever.
"""

BOUNDARIES = """\
1. [00:00:02–00:00:44] Filing the renewal — recalling the last attempt
2. [00:00:44–00:01:21] Finding the action in the interface
3. [00:01:21–00:01:31] The notification email
"""

QUOTES = [
    {"id": "q1", "speaker": "P1", "timecode": "00:00:27",
     "text": "it just dumped me on the dashboard. Not the renewal."},
    {"id": "q2", "speaker": "P1", "timecode": "00:00:47",
     "text": "I went through it twice before I found it, because it's called "
             "\"Policy actions\" and I was looking for the word renew."},
    {"id": "q3", "speaker": "P1", "timecode": "00:01:09",
     "text": "Once I was in the actual form it was fine. Genuinely, that bit "
             "was quick, maybe two minutes."},
    {"id": "q4", "speaker": "P1", "timecode": "00:01:25",
     "text": "Make the link go where it says it goes, really. That's it."},
]

SPEAKERS = ["SPEAKER_00", "SPEAKER_01"]


@dataclass(frozen=True)
class Stage:
    """One real pipeline LLM call, reproduced."""

    key: str
    prompt_id: str
    model: type
    fields: dict[str, Any]
    #: What a *useful* answer contains, beyond validating. A model can satisfy
    #: the schema with an empty list, and an empty list is how a stage produces
    #: a report with nothing in it -- which is the failure a researcher sees.
    substantive: Any

    def prompts(self) -> tuple[str, str]:
        t = get_prompt_template(self.prompt_id)
        return t.system, t.user.format(**self.fields)

    def version(self) -> str:
        return get_prompt_template(self.prompt_id).version


_quotes_json = json.dumps(QUOTES, separators=(",", ":"))

# Ordered as the pipeline runs them, so a sweep reads like a run.
STAGES: list[Stage] = [
    Stage(
        key="s05b:split",
        prompt_id="speaker-splitting",
        model=SpeakerSplitAssignment,
        fields={
            "transcript_sample": wrap_untrusted("transcript", TRANSCRIPT),
            "segment_count": TRANSCRIPT.count("["),
        },
        substantive=lambda r: r.speaker_count >= 1,
    ),
    Stage(
        key="s05b:roles",
        prompt_id="speaker-identification",
        model=SpeakerRoleAssignment,
        fields={
            "transcript_sample": wrap_untrusted("transcript", TRANSCRIPT),
            "speaker_list": ", ".join(SPEAKERS),
        },
        substantive=lambda r: len(r.speakers) >= 1,
    ),
    Stage(
        key="s08:topics",
        prompt_id="topic-segmentation",
        model=TopicSegmentationResult,
        fields={"transcript_text": wrap_untrusted("transcript", TRANSCRIPT)},
        substantive=lambda r: len(r.boundaries) >= 1,
    ),
    Stage(
        key="s09:quotes",
        prompt_id="quote-extraction",
        model=QuoteExtractionResult,
        fields={
            "topic_boundaries": BOUNDARIES,
            "transcript_text": wrap_untrusted("transcript", TRANSCRIPT),
        },
        substantive=lambda r: len(r.quotes) >= 1,
    ),
    # The two that actually broke on Sonnet 5. Both take the whole quote set at
    # once and both nest a list inside each item, which is the shape the
    # double-encoding showed up on.
    Stage(
        key="s10:clusters",
        prompt_id="quote-clustering",
        model=ScreenClusteringResult,
        fields={"quotes_json": wrap_untrusted("quotes", _quotes_json)},
        substantive=lambda r: len(r.clusters) >= 1,
    ),
    Stage(
        key="s11:themes",
        prompt_id="thematic-grouping",
        model=ThematicGroupingResult,
        fields={"quotes_json": wrap_untrusted("quotes", _quotes_json)},
        substantive=lambda r: len(r.themes) >= 1,
    ),
]

BY_KEY = {s.key: s for s in STAGES}
