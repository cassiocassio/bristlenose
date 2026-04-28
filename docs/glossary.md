# Glossary — Terminology & Tone Guide

Single source of truth for vocabulary, voice, and writing mechanics across all user-facing text: locale files, help modal, man page, README, SECURITY.md, CLI `--help`, and the future website.

Consumers: human writers, translators (Weblate glossary seed), user-documentation-review agent, Vale linter (future).

---

## Tone guide

**Voice.** Conversational expert. Second person ("you") preferred over passive or third person. Active voice. Sound like a knowledgeable colleague explaining something useful — not a professor lecturing, not a marketer selling, not a developer documenting an API.

**Register.** Explain *why* before *how*. Name the research principle, then show the button. Cite frameworks on first use ("thematic analysis (Braun & Clarke, 2006)"). No jargon without inline explanation — "Presidio" always needs "(an open-source text scanner)" on first mention. Researchers need to understand the research logic, not just the button sequence.

**Anti-patterns.** No superlatives ("best", "powerful", "revolutionary"). No minimisers ("simply", "just", "easily" — these dismiss real complexity researchers face). No marketing language. No exclamation marks in help text. No "click here" link text — describe the destination. No idioms or cultural references that don't translate across our six languages.

---

## Core research concepts

| Canonical | Forbidden | Why | Cross-ref |
|---|---|---|---|
| **quote** | snippet, excerpt, verbatim (in English) | Honours the participant's voice — their words, not an extract from a document. French exception: "verbatim" is the natural product-level noun in French research. | `design-i18n.md` lines 55–63 |
| **codebook** | code book, coding scheme, coding framework | One word, no hyphen. Matches ATLAS.ti/MAXQDA convention. A codebook is the container; codes are the items inside it. | `design-i18n.md` lines 49–50 |
| **code** | category, label (when referring to codebook entries) | A code is a named concept in a codebook that can be applied to quotes. Distinct from "tag" (see below). | `design-i18n.md` lines 46–47 |
| **tag** | code (when referring to user-applied labels on quotes) | A tag is a label applied to a specific quote — either manually ("human") or by AI proposal ("autocode"). Tags come from codebook codes, but "tag" is the applied instance, "code" is the definition. This distinction doesn't exist in academic QDA; it's a Bristlenose UX choice. | `design-i18n.md` line 53 |
| **session** | interview, recording | A session is one research encounter (one recording, one transcript). "Interview" is the German/French UI term (Interviews/Entretiens) but English uses "session" to cover non-interview formats (diary studies, usability tests). | `design-i18n.md` lines 64–65 |
| **theme** | category, cluster, group | An emergent pattern requiring at least two quotes. A single quote is an observation, not a theme. Follows Braun & Clarke (2006) thematic analysis. | `design-research-methodology.md` lines 150–175 |
| **signal** | pattern, insight, finding | A Bristlenose-specific concept: statistically notable concentration of sentiment or codebook tags within a report section. No equivalent in any QDA tradition — we coined it. | `design-research-methodology.md`; `design-i18n.md` lines 67–68 |
| **sentiment** | emotion, feeling, affect | One of seven UX-specific categories (see below). "Sentiment" was chosen over "emotion" because it maps to actionable UX insights, not universal affect theory. | `design-research-methodology.md` lines 94–133 |

### The seven sentiments

Fixed taxonomy. Do not add new categories without research justification.

| Sentiment | Definition | Design problem it points to |
|---|---|---|
| **frustration** | Difficulty, annoyance, friction | Performance or interaction problems |
| **confusion** | Not understanding, uncertainty | Information architecture or labelling |
| **doubt** | Scepticism, worry, distrust | Credibility or trust problems |
| **surprise** | Expectation mismatch (neutral valence) | Researcher judges positive/negative from context |
| **satisfaction** | Met expectations, task success | Validation that something works |
| **delight** | Exceeded expectations, pleasure | Opportunities to replicate |
| **confidence** | Trust, feeling in control | Evidence of good UX |

**Doubt != confusion.** Confusion means "I don't understand"; doubt means "I understand but don't trust". They require different design responses. This is the most common conflation to watch for.

---

## Identity & privacy

| Canonical | Forbidden | Why | Cross-ref |
|---|---|---|---|
| **speaker code** | participant ID, anonymous ID, anon code | The system-assigned identity (p1, p2, m1, o1). Immutable. Public-facing in quotes, exports, CSV. | `SECURITY.md` lines 65–83 |
| **display name** | real name, actual name, first name | Editable short name visible to the research team only. Never appears in exports. A working tool, not an identity. | `design-html-report.md` lines 156–169 |
| **PII redaction** | anonymisation (when meaning Presidio), data masking, scrubbing | Opt-in automated detection of personal data (names, emails, phone numbers) using Microsoft Presidio. Applied before LLM analysis. Distinct from anonymisation. | `SECURITY.md` lines 21–63 |
| **anonymisation** | PII redaction (when meaning export control), de-identification | Researcher-controlled removal of participant names from exports. Speaker codes remain. A narrative/export control choice, not a safety mechanism. | `design-export-html.md` lines 213–274 |
| **auth token** | API key, access token, session token | Short-lived bearer token protecting the localhost `bristlenose serve` API. Generated per-process at startup (random by default); may be pinned via `_BRISTLENOSE_AUTH_TOKEN` for CI fixtures and uvicorn `--reload` continuity. Not a user-visible concept — researchers never see it. | `SECURITY.md` "Serve mode API access control", `design-localhost-auth.md` |
| **CI test mode** | debug mode, dev mode (in this context) | The pinned-token path used by CI fixtures, activated today by setting `_BRISTLENOSE_AUTH_TOKEN` in the environment. A future hardening task will gate this behind `BRISTLENOSE_DEV_MODE=test`. Distinct from the CLI `--dev` flag (which starts Vite + enables live reload). | `SECURITY.md`, `docs/private/100days.md` §6 Risk |

**The distinction matters.** PII redaction is safety/compliance (automated, before LLM). Anonymisation is researcher choice (manual, at export time). Using one word for both causes real confusion in compliance contexts.

---

## Product & provider names

| Canonical (user-facing) | Forbidden (in user text) | Internal code value | Why |
|---|---|---|---|
| **Bristlenose** | BRISTLENOSE, bristlenose (in prose) | — | Product brand. Lowercase only in code identifiers and file paths. |
| **Claude** | Anthropic | `"anthropic"` | Researchers know products, not companies. "Anthropic" is fine in developer docs and code. |
| **ChatGPT** | OpenAI | `"openai"` | Same reasoning. "OpenAI" is the company, "ChatGPT" is what researchers signed up for. |
| **Azure OpenAI** | Azure, Microsoft AI | `"azure"` | The full product name. Researchers using it know it's Azure-specific. |
| **Gemini** | Google, Google AI | `"gemini"` | Product name. |
| **Ollama** | Local, local models (as a proper noun) | `"ollama"` / `"local"` | "Ollama" when referring to the tool. "Local models" or "local (Ollama)" when describing the mode. |

---

## Actions & UI

| Canonical | Forbidden | Why |
|---|---|---|
| **star** / **unstar** | favourite, favorite, bookmark | Star is the visual metaphor (icon). Avoids US/UK spelling debate. |
| **hide** / **unhide** | archive, delete, remove | Hide is reversible and explicit. "Archive" implies a destination; "delete" implies permanence. |
| **export** | download, share, save as | Export is the action. "Download" is a browser mechanic. "Share" implies sending to someone. |
| **add tag** | tag (as a verb without "add"), code (for the action) | "Add tag" is the explicit UI label. "Tag this quote" is acceptable in prose. Never "code this quote" (confuses code/tag distinction). |

---

## Export & file naming

| Context | Use | Not | Why | Code |
|---|---|---|---|---|
| Internal filenames, config keys | `slugify()` | `safe_filename()` | Lowercase, hyphens, max 50 chars. Machine-readable. | `bristlenose/utils/text.py` |
| Human-facing export artifacts | `safe_filename()` | `slugify()` | Preserves spaces, case, accents. Readable in Finder. | `bristlenose/utils/text.py` |
| Report HTML filename | `bristlenose-{slug}-report.html` | — | Includes project slug so multiple reports in Downloads are distinguishable. | — |

---

## Analysis

| Canonical | Definition | Notes |
|---|---|---|
| **concentration** | Observed rate of a sentiment/tag in a section divided by its expected rate across the whole study. A ratio of 2x means it appears twice as often as you'd expect. | |
| **agreement** | How many participants share a signal. Simpson's diversity index distinguishes group consensus from one person's repeated reaction. | Also called "agreement breadth". |
| **intensity** | Average strength on the 1–3 sentiment scale within a signal. | |
| **signal score** | Composite of concentration, agreement, and intensity (normalised and multiplied). | |
| **pattern type** | Classification of a signal's direction: **success** (positive), **gap** (negative), **tension** (mixed), **recovery** (negative then positive). | `design-signal-elaboration.md` |

---

## Spelling & mechanics

- **British English**: analyse, colour, organisation, behaviour, licence (noun), categorise
- **Oxford comma**: yes ("quotes, themes, and signals")
- **Headings**: sentence case ("What PII redaction catches"), not title case ("What PII Redaction Catches")
- **Numbers**: spell out one–nine, digits for 10+. Exception: technical values ("0.7 threshold", "3 participants")
- **Dashes**: em dash (—) for parenthetical asides, no spaces. En dash (–) for ranges ("1–3 scale"). Never hyphens for either.
- **Dates**: `D Mon YYYY` (7 Feb 2026). No leading zero on day. No hyphens. Bold version, italic date in changelog: `**0.14.2** — _7 Feb 2026_`
- **Lists**: parallel structure. If first item starts with a verb, all items start with a verb.
- **Links**: descriptive text, never "click here" or bare URLs. "See the [contributing guide](url)" not "[click here](url) for the contributing guide".

---

## Cross-language terminology

For translated terms (Codes→Kodes, Quotes→Verbatim, Sessions→Entretiens, etc.), see the authoritative table in [`docs/design-i18n.md`](design-i18n.md) lines 35–42. This glossary covers English canonical forms only.

Key cross-language notes:
- **French "verbatim"** is the single most important translation choice — it's the warm, natural term French researchers use daily for participant quotes
- **Japanese and Korean** transliterate nearly everything into katakana/Hangul
- **German, French, Spanish** have genuine native vocabulary — use it for academic credibility
- **"Tags"** is borrowed as an English loanword in all target languages; no native QDA equivalent exists
- **"Signals"** is a Bristlenose-coined concept; transliterate in all languages (Signale, Signaux, etc.)
