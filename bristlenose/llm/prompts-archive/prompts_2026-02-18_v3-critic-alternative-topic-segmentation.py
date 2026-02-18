"""
Archived prompt variant: v3 — critic's suggested alternative for TOPIC_SEGMENTATION_PROMPT.

This is the full rewrite proposed by the external critique. It differs from v2 in that it:
  - Adds a ui_area_type field (page, tab, modal, component, feature, workflow_stage, general_context)
  - Front-loads UX vocabulary and a UI area hierarchy
  - Uses more prescriptive segmentation guidelines
  - Drops the explanatory preamble about moderated vs think-aloud sessions

Note: This version requires a matching change to the structured output model
(TopicBoundaryItem in structured.py) to add the ui_area_type field.

This file is for testing/comparison only — not used by the application.
"""

# ---------------------------------------------------------------------------
# Stage 8: Topic Segmentation — v3 (critic's alternative)
# ---------------------------------------------------------------------------

TOPIC_SEGMENTATION_PROMPT = """\
You are analysing a user-research transcript. Your primary goal is to segment \
the transcript according to the "geographical" area of the product being discussed \
(screen, page, tab, modal, component, feature, or workflow stage). \
Focus on identifying meaningful boundaries where the primary UI focus changes.

The transcript below contains timestamped dialogue from a research session. \
This may be a moderated interview or a solo think-aloud session.

## Segmentation guidelines

- Prioritize movement between product areas over conversational nuance.
- Do NOT create transitions for minor clarifications or follow-up questions \
about the same screen or feature.
- A "UI area" may include:
    - Full page (Dashboard, Settings, Reports)
    - Tab within a page
    - Modal or overlay
    - Specific component (Filter panel, Chart widget, Sidebar)
    - Clearly bounded feature (Search, Export, Onboarding flow)
- Mark a task_change only when the participant begins a new goal-oriented task.
- Use consistent naming if the same screen or area reappears.
- Transitions may be explicit or implicit — infer them if necessary.

For each transition you identify, provide:

- **timecode**: timestamp in HH:MM:SS format
- **topic_label**: concise 3-8 word label describing the UI area
- **ui_area_type**: one of:
    - `page` — a full page or top-level view
    - `tab` — a tab within a page
    - `modal` — a modal, overlay, or dialog
    - `component` — a specific UI component (filter panel, sidebar, widget)
    - `feature` — a clearly bounded feature (search, export, notifications)
    - `workflow_stage` — a stage in a multi-step flow (checkout step 2, onboarding)
    - `general_context` — general discussion not tied to a specific UI area
- **transition_type**: one of:
    - `screen_change` — the participant is shown or navigates to a new screen/page
    - `task_change` — the participant is asked to perform a new goal-oriented task
    - `topic_shift` — the discussion moves to a new subject within the same screen
    - `general_context` — the discussion moves to general context (job role, daily \
workflow, general software habits, life context) not specific to any screen
- **confidence**: float from 0.0 to 1.0

Include a transition at 00:00:00 labeling the opening UI focus.

Transcript:
{transcript_text}
"""
