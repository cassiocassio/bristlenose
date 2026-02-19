"""Pre-built codebook templates — static data, no DB.

Each template defines a framework codebook with groups and tags that can
be imported into a project. Templates are identified by a string ID
(e.g. "garrett") which is stored on CodebookGroup.framework_id after import.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TemplateTag:
    name: str


@dataclass(frozen=True)
class TemplateGroup:
    name: str
    subtitle: str
    colour_set: str  # "ux", "emo", "task", "trust", "opp"
    tags: list[TemplateTag] = field(default_factory=list)


@dataclass(frozen=True)
class CodebookTemplate:
    id: str
    title: str
    author: str
    description: str
    author_bio: str
    author_links: list[tuple[str, str]]  # [(label, url), ...]
    groups: list[TemplateGroup] = field(default_factory=list)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Garrett — The Elements of User Experience
# ---------------------------------------------------------------------------

_GARRETT = CodebookTemplate(
    id="garrett",
    title="The Elements of User Experience",
    author="Jesse James Garrett",
    description=(
        "Five mutually exclusive planes from abstract strategy to concrete"
        " surface design. A top-down framework for placing findings in the"
        " UX decision hierarchy. Each plane describes a different layer of"
        " product decisions \u2014 from why we build it (Strategy) to what"
        " it looks like (Surface)."
    ),
    author_bio=(
        "Co-founder of Adaptive Path. Coined the term \u201cAjax\u201d and"
        " created the five-plane model that became foundational to UX"
        " practice. Author of \u201cThe Elements of User Experience:"
        " User-Centered Design for the Web and Beyond\u201d (2002, 2nd"
        " edition 2010)."
    ),
    author_links=[
        ("jjg.net", "https://jjg.net"),
        ("Amazon US", "https://www.amazon.com/dp/0321683684"),
        ("Amazon UK", "https://www.amazon.co.uk/dp/0321683684"),
    ],
    groups=[
        TemplateGroup(
            name="Strategy",
            subtitle="Is the product solving the right problem for the right users?",
            colour_set="ux",
            tags=[
                TemplateTag("user need"),
                TemplateTag("business objective"),
                TemplateTag("success metric"),
                TemplateTag("value proposition"),
            ],
        ),
        TemplateGroup(
            name="Scope",
            subtitle="What features and content are included or excluded?",
            colour_set="emo",
            tags=[
                TemplateTag("feature requirement"),
                TemplateTag("content requirement"),
                TemplateTag("priority"),
                TemplateTag("scope creep"),
            ],
        ),
        TemplateGroup(
            name="Structure",
            subtitle="How is information organised conceptually?",
            colour_set="task",
            tags=[
                TemplateTag("interaction design"),
                TemplateTag("information architecture"),
                TemplateTag("navigation pattern"),
                TemplateTag("task flow"),
            ],
        ),
        TemplateGroup(
            name="Skeleton",
            subtitle="How are interface elements arranged?",
            colour_set="trust",
            tags=[
                TemplateTag("interface layout"),
                TemplateTag("wireframe issue"),
                TemplateTag("convention"),
                TemplateTag("component placement"),
            ],
        ),
        TemplateGroup(
            name="Surface",
            subtitle="What is the visual treatment?",
            colour_set="opp",
            tags=[
                TemplateTag("visual design"),
                TemplateTag("sensory experience"),
                TemplateTag("brand alignment"),
                TemplateTag("aesthetic reaction"),
            ],
        ),
    ],
    enabled=True,
)

# ---------------------------------------------------------------------------
# Norman — The Design of Everyday Things
# ---------------------------------------------------------------------------

_NORMAN = CodebookTemplate(
    id="norman",
    title="The Design of Everyday Things",
    author="Don Norman",
    description=(
        "Seven fundamental principles of interaction design that explain why"
        " products are easy or hard to use. A bottom-up framework for"
        " diagnosing why interactions succeed or fail \u2014 from whether"
        " users can discover what\u2019s possible (Discoverability) to"
        " whether the system communicates what happened (Feedback) to"
        " whether errors are slips or mistakes."
    ),
    author_bio=(
        "Director of the Design Lab at UC San Diego. Former VP of"
        " Apple\u2019s Advanced Technology Group. Coined the term"
        " \u201cuser experience\u201d in the 1990s. Author of \u201cThe"
        " Design of Everyday Things\u201d (originally published as"
        " \u201cThe Psychology of Everyday Things\u201d, 1988; revised and"
        " expanded edition 2013)."
    ),
    author_links=[
        ("jnd.org", "https://jnd.org"),
        ("Amazon US", "https://www.amazon.com/dp/0465050654"),
        ("Amazon UK", "https://www.amazon.co.uk/dp/0465050654"),
    ],
    groups=[
        TemplateGroup(
            name="Discoverability",
            subtitle="Can the user figure out what actions are possible?",
            colour_set="ux",
            tags=[
                TemplateTag("visible action"),
                TemplateTag("hidden feature"),
                TemplateTag("exploration"),
                TemplateTag("first-time use"),
            ],
        ),
        TemplateGroup(
            name="Feedback",
            subtitle="Does the system communicate results clearly?",
            colour_set="emo",
            tags=[
                TemplateTag("system response"),
                TemplateTag("delayed feedback"),
                TemplateTag("ambiguous feedback"),
                TemplateTag("confirmation"),
            ],
        ),
        TemplateGroup(
            name="Conceptual model",
            subtitle="Does user understanding match reality?",
            colour_set="task",
            tags=[
                TemplateTag("user mental model"),
                TemplateTag("system model"),
                TemplateTag("model mismatch"),
                TemplateTag("learned behaviour"),
            ],
        ),
        TemplateGroup(
            name="Signifiers",
            subtitle="Do visual cues correctly indicate how to interact?",
            colour_set="trust",
            tags=[
                TemplateTag("affordance"),
                TemplateTag("perceived affordance"),
                TemplateTag("false signifier"),
                TemplateTag("missing signifier"),
            ],
        ),
        TemplateGroup(
            name="Mapping",
            subtitle=(
                "Does the relationship between controls and outcomes feel"
                " natural?"
            ),
            colour_set="opp",
            tags=[
                TemplateTag("natural mapping"),
                TemplateTag("arbitrary mapping"),
                TemplateTag("spatial correspondence"),
                TemplateTag("logical layout"),
            ],
        ),
        TemplateGroup(
            name="Constraints",
            subtitle=(
                "Do designed limitations guide users toward correct actions?"
            ),
            colour_set="ux",
            tags=[
                TemplateTag("physical constraint"),
                TemplateTag("cultural constraint"),
                TemplateTag("semantic constraint"),
                TemplateTag("logical constraint"),
            ],
        ),
        TemplateGroup(
            name="Slips vs Mistakes",
            subtitle="Was the error execution-based or goal-based?",
            colour_set="emo",
            tags=[
                TemplateTag("action slip"),
                TemplateTag("memory lapse"),
                TemplateTag("rule-based mistake"),
                TemplateTag("knowledge-based mistake"),
            ],
        ),
    ],
    enabled=False,
)

# ---------------------------------------------------------------------------
# Bristlenose UXR — Domain-agnostic default codebook
# ---------------------------------------------------------------------------

_UXR = CodebookTemplate(
    id="uxr",
    title="Bristlenose UXR Codebook",
    author="",
    description=(
        "A domain-agnostic codebook for any user research study. Ten theme"
        " categories that emerge bottom-up from behavioural observation,"
        " emotional response, and contextual analysis. Works equally well"
        " whether the research is about fishkeeping, rock climbing, poodle"
        " grooming, or product evaluation \u2014 these are universal"
        " patterns of human experience, motivation, and interaction."
    ),
    author_bio=(
        "This is the default codebook \u2014 it provides a general-purpose"
        " qualitative coding framework that applies to any domain. Unlike"
        " the Research Leaders codebooks (Garrett, Norman, Morville), which"
        " focus on designed artefacts and UX-specific concepts, these ten"
        " categories capture the full range of human experience themes that"
        " emerge in qualitative research."
    ),
    author_links=[],
    groups=[
        TemplateGroup(
            name="Behavioural patterns",
            subtitle="What users do vs what they say",
            colour_set="ux",
            tags=[
                TemplateTag("workaround"),
                TemplateTag("say-do gap"),
                TemplateTag("error recovery"),
                TemplateTag("habit"),
                TemplateTag("avoidance"),
            ],
        ),
        TemplateGroup(
            name="Pain points and friction",
            subtitle="Confusion, hesitation, abandonment",
            colour_set="emo",
            tags=[
                TemplateTag("confusion"),
                TemplateTag("hesitation"),
                TemplateTag("abandonment"),
                TemplateTag("dead end"),
                TemplateTag("frustration trigger"),
            ],
        ),
        TemplateGroup(
            name="Unmet needs and latent desires",
            subtitle="Not explicitly requested but emerged from behaviour",
            colour_set="emo",
            tags=[
                TemplateTag("latent need"),
                TemplateTag("compensatory behaviour"),
                TemplateTag("feature gap"),
                TemplateTag("desire path"),
            ],
        ),
        TemplateGroup(
            name="Expectations and mental models",
            subtitle="How users conceptualise the system or domain",
            colour_set="task",
            tags=[
                TemplateTag("mental model"),
                TemplateTag("assumption"),
                TemplateTag("prior experience"),
                TemplateTag("conceptual mismatch"),
            ],
        ),
        TemplateGroup(
            name="Motivations and goals",
            subtitle="Underlying jobs-to-be-done",
            colour_set="task",
            tags=[
                TemplateTag("primary goal"),
                TemplateTag("secondary goal"),
                TemplateTag("job-to-be-done"),
                TemplateTag("trigger"),
                TemplateTag("barrier"),
            ],
        ),
        TemplateGroup(
            name="Trust, confidence, and emotional response",
            subtitle="Feelings at key decision points",
            colour_set="trust",
            tags=[
                TemplateTag("trust signal"),
                TemplateTag("anxiety moment"),
                TemplateTag("confidence builder"),
                TemplateTag("emotional peak"),
            ],
        ),
        TemplateGroup(
            name="Environmental and contextual factors",
            subtitle="Interruptions, device switching, social influence",
            colour_set="trust",
            tags=[
                TemplateTag("interruption"),
                TemplateTag("device switch"),
                TemplateTag("social influence"),
                TemplateTag("time pressure"),
            ],
        ),
        TemplateGroup(
            name="Learning and skill acquisition",
            subtitle="How people build competence",
            colour_set="opp",
            tags=[
                TemplateTag("learning curve"),
                TemplateTag("aha moment"),
                TemplateTag("skill plateau"),
                TemplateTag("self-teaching"),
            ],
        ),
        TemplateGroup(
            name="Community and social dynamics",
            subtitle="Knowledge sharing, identity through domain",
            colour_set="opp",
            tags=[
                TemplateTag("knowledge sharing"),
                TemplateTag("peer influence"),
                TemplateTag("community norm"),
                TemplateTag("identity signal"),
            ],
        ),
        TemplateGroup(
            name="Identity and self-concept",
            subtitle="How the activity relates to self-perception",
            colour_set="ux",
            tags=[
                TemplateTag("self-perception"),
                TemplateTag("aspiration"),
                TemplateTag("expertise identity"),
                TemplateTag("beginner mindset"),
            ],
        ),
    ],
    enabled=True,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

CODEBOOK_TEMPLATES: list[CodebookTemplate] = [_UXR, _GARRETT, _NORMAN]


def get_template(template_id: str) -> CodebookTemplate | None:
    """Return a template by ID, or None if not found."""
    for t in CODEBOOK_TEMPLATES:
        if t.id == template_id:
            return t
    return None
