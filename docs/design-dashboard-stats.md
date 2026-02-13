# Dashboard Stats Coverage — Future Improvements

Inventory of data available in the pipeline that the Project Dashboard tab does not currently show. Compiled Feb 2026.

## What the dashboard currently shows

Six stat cards (sessions, duration, words, quotes, themes/sections, AI tags, user tags), a simplified session table (ID, participants, date, duration, filename), three featured quote cards, and two navigation lists (sections, themes).

---

## Available but not shown

### Per-participant stats

All available in `PersonComputed` / `PersonEditable` / `SpeakerInfo`:

- **Words spoken** per person (only shown as aggregate total today)
- **% of total words** per person (`pct_words` — never shown in report)
- **% speaking time** per person (`pct_time_speaking` — never shown in report)
- **Job title / role** (`PersonEditable.role`, populated from LLM speaker identification — never shown in report)
- **Persona** (`PersonEditable.persona` — never shown)
- **Per-participant quote count** (not computed explicitly anywhere)

### Sentiment breakdown

- **Sentiment distribution** at project level (the Quotes tab has the histogram; dashboard only shows a count of tagged quotes)
- **Per-sentiment counts** (e.g. 14 friction, 9 delight, 6 surprise…)
- **Sentiment sparklines** per session (already computed for the Sessions tab table, omitted from dashboard session table)

### Top signals from Analysis

All computed in `bristlenose/analysis/`, only shown on the Analysis tab:

- **Top signals** — composite signal strength, concentration ratio, confidence level (strong/moderate/emerging)
- **N_eff (agreement breadth)** — Simpson's effective number of voices per signal
- **Mean intensity** per signal

### Coverage stats

Available in `CoverageStats`:

- **% of transcript in report** (`pct_in_report`)
- **% moderator talk** (`pct_moderator`)
- **% omitted** (`pct_omitted`)

### Session-level detail

Available but missing from dashboard session table:

- **User journey paths** per session (screen sequences like "Landing → Search → Cart" — already rendered on Sessions tab)
- **Video thumbnails** (Sessions tab has these, dashboard table doesn't)
- **Average session duration** (trivially computed, never shown)
- **Date range** of sessions (earliest to latest `session_date`)
- **Per-session quote count** (not computed anywhere currently)

### Section and theme detail

- **Section descriptions** (`ScreenCluster.description` — shown on Quotes tab, not dashboard)
- **Theme descriptions** (`ThemeGroup.description` — shown on Quotes tab, not dashboard)
- **Quote count per section** (implicit on Quotes tab, not shown as a number)
- **Quote count per theme** (same)

### Topic segmentation (completely unused in report UI)

Available in `SessionTopicMap` / `TopicBoundary`:

- **Topic labels** per segment
- **Transition types** (SCREEN_CHANGE, TOPIC_SHIFT, TASK_CHANGE, GENERAL_CONTEXT)
- **Topic boundary count** per session
- **Confidence** per boundary

### Pipeline / run metadata

Available in `PipelineResult`:

- **LLM model used** (`llm_model`)
- **LLM provider** (`llm_provider`)
- **Total LLM calls** (`llm_calls`)
- **Token usage** (input + output tokens)
- **Estimated cost** (computed in CLI via `estimate_cost()`, never in report)
- **Pipeline run time** (`elapsed_seconds`)
- **PII entities found** count (`PiiCleanTranscript.pii_entities_found` — only logged to console)

### Friction / rewatch

- **Friction point count** (quotes tagged frustration/confusion/doubt — the Quotes tab has a full rewatch list, dashboard has nothing)

---

## Implementation notes

The richest untapped areas, roughly in priority order:

1. **Sentiment breakdown** — a mini donut or bar showing the distribution across 7 sentiments, not just a raw count. Small effort, high insight density
2. **Per-participant stats** — words/time distribution as a small table or bar chart. Already computed in `PersonComputed`
3. **Top signals** — surface the top 2–3 analysis signals (name + confidence badge). Already computed, just needs rendering
4. **Coverage stats** — "82% of transcript in report" as a single stat card. Very small effort
5. **Section/theme quote counts** — append "(12 quotes)" to the existing section/theme nav lists
6. **Session sparklines and journeys** — already computed for Sessions tab; the dashboard table just doesn't include them
7. **Date range** — "14 Jan – 3 Feb 2026" in the stats row or header
8. **Friction point count** — stat card linking to the rewatch list
9. **Pipeline metadata** — "Analysed with Claude 3.5 Sonnet" footer line; run time; cost
10. **Topic segmentation** — least mature; would need a new UI concept to surface meaningfully
