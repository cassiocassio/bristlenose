# Design: Codebook — Future Phases

**Status:** Phases 1–3 shipped (v0.8.1). This document covers what comes next.

**Last updated:** 7 Feb 2026

---

## What shipped vs what was discussed

The original blue-sky discussion imagined the codebook as a full qualitative-research tool: a `codebook.yaml` file format, LLM prompt integration, code definitions with examples, merge/split operations, and an "apply codebook" workflow that feeds researcher-defined codes back into the analysis pipeline.

What we actually built (Phases 1–3) was narrower and more practical:

### Shipped (Phases 1–3)

| Feature | Status |
|---------|--------|
| OKLCH v5 colour system (5 sets, 27 slots, light/dark mode) | Done |
| Client-side data model in localStorage | Done |
| Standalone `codebook.html` page (opens from toolbar) | Done |
| Drag-and-drop tag → group assignment | Done |
| Drag-and-drop tag → tag merge (with confirmation) | Done |
| Inline editing: group name, subtitle/description | Done |
| Group CRUD: create, delete, rename | Done |
| Tag CRUD: add to group, delete (removes from all quotes) | Done |
| Per-tag micro histogram bars with quote counts | Done |
| Cross-window sync (report ↔ codebook via localStorage events) | Done |
| Codebook colours applied to report badges and histogram bars | Done |

### Not shipped (from the original discussion)

| Feature | Original idea | Why it wasn't built |
|---------|---------------|---------------------|
| `codebook.yaml` file format | Persistent YAML file in output dir | Client-side localStorage was sufficient for the UI; file persistence is a separate concern |
| Code definitions with examples | Each code has a definition and illustrative quotes | Groups have subtitles but tags have no per-tag definitions |
| LLM prompt integration (stages 9–11) | Feed codebook into quote extraction, clustering, theming | Requires server-side codebook file; large prompt engineering effort |
| "Suggest codes" LLM feature | LLM reviews untagged quotes and proposes new codes | Requires LLM integration layer |
| "Review codebook" LLM feature | LLM suggests merges, splits, or new codes | Same |
| "Apply codebook" re-analysis | Re-run analysis with codebook as constraint | Requires `codebook.yaml` → pipeline integration |
| Split operation | Select a code, LLM suggests how to split it | Not needed until codebook-driven analysis exists |
| Codebook-first workflow (`bristlenose codebook <folder>`) | Generate codebook from quick LLM scan before full analysis | Premature without the file format |
| Sentiment codes as codebook entries | Make the 7 sentiments editable via codebook | Sentiments are currently hardcoded in the Sentiment enum |
| Screen labels as codebook entries | Make LLM-generated screen clusters editable | Screen clusters are LLM-generated per run |
| Theme groups as codebook entries | Make LLM-generated themes editable | Theme groups are LLM-generated per run |
| User tag → codebook promotion | "You've used 'follow-up' on 4 quotes. Add it to the codebook?" | User tags and codebook groups are already integrated — user tags appear in the codebook panel automatically |

### Key divergences from the original vision

1. **No file format.** The original discussion centred on `codebook.yaml` as a persistent, version-controllable, shareable artifact. We built a localStorage-only UI instead. This was the right call for Phase 1–3 — it let us ship the interactive UI fast — but it means the codebook is trapped in the browser. A researcher can't share their codebook with a colleague, version-control it, or use it across projects.

2. **User tags only, not analysis codes.** The shipped codebook organises *user-created tags* into colour-coded groups. It doesn't touch the AI-generated codes (sentiments, screen clusters, themes). The original discussion imagined making *all* codes — AI and human — visible and editable in one place. This is still the right goal but requires the pipeline integration work in Phases 5–6.

3. **No LLM assistance.** The shipped codebook is a manual organisation tool. The original discussion imagined LLM-assisted operations: suggest codes, review codebook, apply codebook. These are the most ambitious parts of the feature and depend on the file format (Phase 4) and prompt integration (Phase 5).

4. **Merge works, split doesn't exist.** Merge was straightforward (rename tag A to tag B in localStorage). Split requires LLM judgement ("which quotes should move to the new code?") and wasn't needed for the manual workflow.

5. **No codebook-first workflow.** The original discussion asked whether researchers should be able to define codes *before* analysis. This is the grounded-theory vs. framework-analysis divide. We shipped the grounded-theory workflow (codes emerge from data) and haven't built the framework-analysis workflow (codes defined upfront).

---

## Future phases

### Phase 4: Codebook file format (`codebook.yaml`)

**Goal:** Make the codebook a persistent, shareable file — not just browser state.

**What gets written:**

```yaml
version: 1
groups:
  - name: Friction
    subtitle: Pain points and obstacles
    colour_set: emo
    tags:
      - confusion
      - frustration
      - "can't find"

  - name: Delight
    subtitle: Positive moments
    colour_set: task
    tags:
      - satisfaction
      - "love this"

ungrouped:
  - follow-up
  - key-insight
```

**Design decisions:**

- **Location:** `codebook.yaml` in the output directory, alongside `people.yaml`. Same rationale — it's a research artifact produced by Bristlenose, not a configuration input (that comes in Phase 5).
- **No per-tag definitions yet.** The YAML captures group structure + tag assignments + colours. Definitions are Phase 6 (LLM-assisted).
- **No AI codes.** Sentiments, screen clusters, and themes are pipeline outputs, not codebook entries. The codebook is the researcher's taxonomy of user tags. AI codes become codebook-aware in Phase 5.
- **Merge strategy mirrors `people.yaml`.** On re-render: preserve human edits, add new tags that appeared in localStorage, remove tags that no longer exist. `bristlenose/codebook.py` (new module) handles load/merge/write.

**Implementation:**

- New `bristlenose/codebook.py` module — `CodebookFile` Pydantic model, `load_codebook()`, `write_codebook()`, `merge_codebook()` functions.
- `render_html.py` writes `codebook.yaml` alongside the report (like `people.yaml`).
- `render_html.py` reads `codebook.yaml` on render and bakes group/tag/colour data into the HTML as a `BN_CODEBOOK` JavaScript constant. The codebook page reads this on load and seeds localStorage if empty.
- **Bidirectional sync:** browser edits → localStorage → export YAML (clipboard, like names) → paste into `codebook.yaml` → `bristlenose render` → reconcile. Same pattern as `people.yaml`.
- **Future:** once `bristlenose serve` exists, the server writes `codebook.yaml` directly on save — no clipboard dance.

**Files touched:**

- New: `bristlenose/codebook.py`
- New: `bristlenose/models/codebook.py` (or extend `models.py`)
- Modified: `bristlenose/stages/render_html.py` (read/write codebook, bake into HTML)
- Modified: `bristlenose/theme/js/codebook.js` (read `BN_CODEBOOK`, YAML export button)
- Modified: `bristlenose/output_paths.py` (`codebook_yaml` property)

**Tests:** `tests/test_codebook.py` — load, write, merge strategy, edge cases.

---

### Phase 5: LLM prompt integration

**Goal:** Let the researcher's codebook influence what the LLM produces.

This is the feature that closes the qualitative-research loop: define codes → apply to data → review → refine → re-apply.

**How it works:**

When `codebook.yaml` exists in the output directory (or input directory — see open question), the pipeline reads it and modifies LLM prompts for stages 9–11:

**Stage 9 (quote extraction + sentiment tagging):**
- Current: hardcoded 7-sentiment `Sentiment` enum.
- With codebook: if the codebook defines a "sentiments" section (future extension to the YAML format), use those as the tag list instead. The LLM sees the researcher's taxonomy, not ours.
- Without codebook sentiment section: use the default 7. Backward-compatible.

**Stage 10 (screen clustering):**
- Current: LLM generates screen labels from scratch.
- With codebook: if the codebook defines screen labels (aliases, definitions), include them as seed labels. The LLM prefers matching existing labels but can create new ones (flagged as `[NEW]` in output).
- The `aliases` field helps normalisation: "home screen" and "main page" both map to "Dashboard".

**Stage 11 (thematic grouping):**
- Current: LLM generates theme groups from scratch.
- With codebook: if the codebook defines themes, include them as seed themes. LLM prefers existing themes, flags new ones.

**Prompt engineering approach:**

Add a `CODEBOOK_CONTEXT` section to each prompt template (in `bristlenose/llm/prompts.py`). When a codebook is present, this section is populated; when absent, it's omitted entirely (no behavioural change for codebook-free runs).

```
## Coding scheme (researcher-defined)

The researcher has defined the following codes. Use these as your primary
taxonomy. You may suggest new codes if the data clearly doesn't fit any
existing code, but prefer the researcher's taxonomy.

Sentiments: frustration, confusion, doubt, surprise, satisfaction, delight, confidence, resignation
Screen labels: Dashboard (aliases: home, overview), Settings, Checkout (aliases: payment, buy)
Themes: Trust and credibility, Learning curve, Navigation confusion
```

**Key constraint:** the prompts must not become rigid. The LLM should still be able to surprise the researcher with unexpected findings. The codebook is a preference, not a straitjacket.

**Extended YAML format for Phase 5:**

```yaml
version: 2
sentiments:
  - name: frustration
    definition: Participant expresses annoyance or anger at a specific obstacle
  - name: resignation
    definition: Participant has given up trying; learned helplessness

screens:
  - name: Dashboard
    definition: The main overview screen showing key metrics
    aliases: [home screen, main page, overview]

themes:
  - name: Trust and credibility
    definition: Participants questioning whether the system is reliable or secure

groups:
  # ... (same as Phase 4)
```

**Files touched:**

- Modified: `bristlenose/llm/prompts.py` (codebook context injection)
- Modified: `bristlenose/stages/quote_extraction.py` (pass codebook to prompt)
- Modified: `bristlenose/stages/quote_clustering.py` (pass codebook to prompt)
- Modified: `bristlenose/stages/thematic_grouping.py` (pass codebook to prompt)
- Modified: `bristlenose/pipeline.py` (load codebook, pass to stages)
- Modified: `bristlenose/config.py` (codebook path config)
- Modified: `bristlenose/codebook.py` (v2 schema support)
- Modified: `bristlenose/models.py` (dynamic Sentiment if codebook overrides)

**Open question:** Should the codebook live in the input directory (travels with raw data, applies to fresh runs) or output directory (produced by Bristlenose, edited by researcher)? Both have precedent. Recommendation: output directory by default (consistent with `people.yaml`), with a `--codebook path/to/codebook.yaml` CLI flag for the codebook-first workflow.

---

### Phase 6: LLM-assisted codebook operations

**Goal:** Let the LLM help the researcher build and refine their codebook.

**Features:**

**6a: "Suggest codes"**
- Button on the codebook page.
- Sends untagged quotes (or a sample) to the LLM with the current codebook.
- LLM returns suggested new tags with definitions.
- Researcher sees suggestions as a list with [Accept] / [Reject] buttons.
- Accepted tags are added to the codebook (ungrouped, ready to be dragged into groups).

**6b: "Review codebook"**
- Button on the codebook page.
- Sends the current codebook + sample quotes per code to the LLM.
- LLM returns recommendations: merge overlapping codes, split broad codes, flag unused codes.
- Researcher sees recommendations in a diff-like view.

**6c: "Split code"**
- Right-click or menu action on a tag in the codebook.
- LLM examines all quotes with that tag and suggests 2–3 sub-codes.
- Researcher approves the split; quotes are reassigned based on LLM classification.

**Implementation considerations:**

- These features require LLM calls from the browser. Two options:
  1. **`bristlenose serve`** — a local server handles the API call. This is the clean solution but requires the server infrastructure from the "Reactive UI architecture" roadmap item.
  2. **CLI command** — `bristlenose codebook suggest`, `bristlenose codebook review`. Writes suggestions to a file; researcher reviews in the codebook page on next render. Clunkier but works without a server.
- Recommendation: wait for `bristlenose serve` (or implement a minimal version of it just for codebook API calls). The interactive approve/reject UX is much better in-browser than via CLI.

**Dependency:** Phase 5 (prompt integration) should ship first so the codebook is already influencing analysis. Phase 6 adds the reverse direction — analysis informing the codebook.

---

### Phase 7: Per-tag definitions and examples

**Goal:** Each tag gets a definition and illustrative example quotes.

**What this enables:**

- **Codebook as documentation.** The codebook page becomes a research artifact you can print or share: "here's what we coded, here's what each code means, here's an example."
- **Better LLM prompts.** When definitions exist, Stage 9–11 prompts include them. The LLM understands not just the code name but its intended meaning. This improves consistency, especially for ambiguous codes.
- **Inter-coder reliability prep.** Definitions are a prerequisite for ICR metrics (out of scope, but the data structure should support it).

**UX on codebook page:**

Each tag row expands to show:
- **Definition** — editable text field (click to edit, like group subtitle).
- **Examples** — 1–3 quotes that exemplify this code. Auto-populated by picking the highest-confidence quotes from the LLM output, or manually assigned by the researcher.

**YAML extension:**

```yaml
groups:
  - name: Friction
    subtitle: Pain points and obstacles
    colour_set: emo
    tags:
      - name: confusion
        definition: >
          Participant doesn't understand what to do,
          what happened, or how something works.
        examples:
          - "Wait, where did that go? I just had it open"
      - name: frustration
        definition: >
          Participant expresses annoyance or anger
          at a specific obstacle or limitation.
```

Note: this changes the `tags` list from strings to objects. The loader must handle both formats (backward compat with Phase 4's string-only format).

---

### Phase 8: AI codes in the codebook

**Goal:** Make all codes — AI-generated and human-created — visible in one unified codebook.

This is the most ambitious remaining piece. Currently:

- **Sentiments** are a hardcoded enum (`Sentiment` in `models.py`), applied by Stage 9, rendered as AI badges.
- **Screen clusters** are LLM-generated strings, applied by Stage 10.
- **Theme groups** are LLM-generated strings, applied by Stage 11.
- **User tags** are researcher-created, managed in localStorage.

These four code types live in different systems with different lifecycles. The codebook page only shows user tags.

**What Phase 8 does:**

The codebook page shows four sections:

```
Sentiments (7)          — from pipeline (editable names/definitions)
Screen labels (5)       — from pipeline (editable names/aliases)
Themes (4)              — from pipeline (editable names/definitions)
User tags (12)          — from researcher (full CRUD, groups, colours)
```

AI codes become editable:
- **Rename a sentiment** → all quotes with that sentiment update (in intermediate JSON + rendered HTML).
- **Rename a screen label** → all quotes in that cluster update.
- **Merge two themes** → quotes reassigned, report sections merged.
- **Delete a sentiment** → quotes lose that tag (like AI badge delete, but permanent across re-renders).

**Key challenge:** AI codes live in intermediate JSON files on disk, not localStorage. Editing them requires either:
1. `bristlenose serve` (server writes files directly), or
2. Export → edit YAML → `bristlenose render` (clipboard dance, like names/people).

Recommendation: ship this after `bristlenose serve` exists. The clipboard dance would be too clunky for code management across four different taxonomies.

---

## Scope explicitly out (for now)

These were mentioned in the original discussion and remain out of scope:

| Feature | Why not now |
|---------|-------------|
| Inter-coder reliability (Cohen's kappa) | Requires multiple coders; Bristlenose is single-researcher |
| Codebook import from other tools (NVivo, Atlas.ti, Dedoose) | Niche; wait for user demand |
| Codebook templates ("e-commerce study", "onboarding study") | Premature; need more users first |
| Hierarchical code trees (multi-level nesting) | Groups are one level deep; sufficient for now |
| Real-time LLM re-coding (apply changes without `analyze`) | Requires streaming LLM integration; very complex |

---

## Recommended implementation order

```
Phase 4: codebook.yaml file format          — small, standalone
Phase 5: LLM prompt integration             — high value, moderate effort
Phase 7: Per-tag definitions and examples    — small, improves Phase 5
Phase 6: LLM-assisted operations            — requires bristlenose serve
Phase 8: AI codes in codebook               — requires bristlenose serve
```

Phases 4 and 5 can ship independently. Phase 7 is a small addition that makes Phase 5 significantly better (definitions in prompts improve LLM consistency). Phases 6 and 8 both depend on the local server infrastructure — defer until `bristlenose serve` exists.

---

## Related files

- `bristlenose/theme/js/codebook.js` — current codebook UI (1003 lines)
- `bristlenose/theme/organisms/codebook-panel.css` — codebook page styling (338 lines)
- `bristlenose/stages/render_html.py` — `_render_codebook_page()`, codebook toolbar button
- `bristlenose/output_paths.py` — `codebook_file` property
- `bristlenose/llm/prompts.py` — LLM prompt templates (Phases 5–6)
- `bristlenose/models.py` — `Sentiment` enum, `ExtractedQuote`, `ScreenCluster`, `ThemeGroup`
- `bristlenose/stages/quote_extraction.py` — Stage 9 (Phase 5)
- `bristlenose/stages/quote_clustering.py` — Stage 10 (Phase 5)
- `bristlenose/stages/thematic_grouping.py` — Stage 11 (Phase 5)
- `bristlenose/people.py` — `people.yaml` merge strategy (pattern for Phase 4)
- `docs/design-research-methodology.md` — analytical decisions behind current codes
- `docs/academic-sources.html` — theoretical foundations for sentiment taxonomy
