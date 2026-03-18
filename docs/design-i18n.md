# Internationalisation — Codebook & Sentiment Translation

## Problem

Bristlenose processes interviews in any language — modern LLMs handle cross-lingual reasoning natively (English prompt + German transcript = fine). But the **display layer** should speak the researcher's language. A German ethnographer expects "Zitate" not "Quotes", and a Japanese UXR practitioner expects コード not "Codes".

Three layers, three strategies:

1. **UI chrome** (Codes, Codebook, Quotes, Sessions, Signals) → translate to UI language
2. **Sentiment tags** (7 values) and **built-in UXR codebook** (38 tags) → translate to UI language, verified by native UXR practitioners
3. **Third-party codebooks** (Don Norman, Morville, Garrett) → stay in author's language (future work)

## Strategy: why we don't translate prompts or transcripts

**Option rejected: translate prompts into target languages.** Would require maintaining N copies of every prompt for diminishing returns. Codebook concepts often originate in English — translating them adds a lossy step.

**Option rejected: translate transcripts to English.** Destroys nuance, idiom, and cultural context — exactly what UX researchers care about. "Das ist mir total egal" carries different weight than "I don't care at all". Adds a compounding-error pipeline stage.

**What works: cross-lingual LLM reasoning.** Send the LLM original-language transcripts with English codebook/prompts. The LLM tags in the codebook's language, extracts quotes verbatim in the original language, and generates summaries in the user's preferred language. Translation happens at the display layer only.

## Internal representation: English always

- `Sentiment.FRUSTRATION` enum — DB stores `"frustration"`
- Tags stored as English strings in DB (canonical)
- LLM prompts use English tag names, return English values
- Translation is display-only — tags are interoperable across languages
- A German user's tags are readable by an English user

## Terminology research — what researchers actually call things

Sources: ATLAS.ti and MAXQDA localized interfaces (both German-origin QDA tools), NVivo, academic textbooks (Flick, Mayring, Kuckartz), UXR industry usage.

### Recommended UI chrome translations

| Concept | English | German | French | Spanish | Japanese | Korean |
|---------|---------|--------|--------|---------|----------|--------|
| **Codes** | Codes | Kodes | Codes | Códigos | コード | 코드 |
| **Codebook** | Codebook | Codebuch | Grille de codage | Libro de códigos | コードブック | 코드북 |
| **Tags** | Tags | Tags | Tags | Etiquetas | タグ | 태그 |
| **Quotes** | Quotes | Zitate | Verbatim | Citas | 発言 | 인용문 |
| **Sessions** | Sessions | Interviews | Entretiens | Sesiones | セッション | 세션 |
| **Signals** | Signals | Signale | Signaux | Señales | シグナル | 시그널 |

### Rationale notes

**Codes — Kodes (de)**
ATLAS.ti germanizes to "Kodes" (with K); MAXQDA keeps "Codes". Kodes is more deliberately German. The process is always "Kodierung" / "Kodieren" (coding). Academic literature (Mayring, Kuckartz, Flick) uses both interchangeably.

**Codebook — Codebuch (de) / Grille de codage (fr)**
MAXQDA uses "Codebuch". Academic German prefers "Kategoriensystem" (category system) or "Codierleitfaden" (coding guide), but Codebuch is what tool users see. French academic research strongly prefers "grille de codage" (coding grid) — "livre de codes" exists but is a literal calque that sounds unnatural.

**Tags**
"Tags" is borrowed as an English loanword in all 5 target languages — no native QDA equivalent exists in any tradition. The Tags/Codes distinction doesn't exist in academic QDA anywhere; all languages treat them as synonyms or only use "codes".

**Quotes — Zitate (de) / Verbatim (fr) / 発言 (ja)**
ATLAS.ti uses "Zitate" (quotations). MAXQDA uses the more technical "Codierte Segmente" (coded segments). Zitate is warmer and matches how researchers think about participant words.

All research traditions know "verbatim" (it's Latin) but use it differently. In English and German it stays academic — a transcription method ("we did a verbatim transcription"). In French it has uniquely become the **everyday product-level noun** for participant quotes — "voici les verbatim". French researchers say "verbatim" daily; using "citations" would sound cold/academic. This is the standout finding.

German "Zitate" (ATLAS.ti's term) is the warm, natural choice. Germans understand "Verbatim" but wouldn't expect it in a tool UI. Spanish "Citas" is ATLAS.ti's term and feels natural; Spanish researchers know "verbatim" as a transcription descriptor, not a noun for the quotes themselves.

Japanese UXR practitioners use **発言** (hatsugen = utterance/statement) for participant quotes. The academic term 引用 (in'yō = quotation) exists but feels more literary/citation-like.

**Sessions — Interviews (de) / Entretiens (fr)**
Neither German nor French QDA uses "session" — interviews are interviews. German "Sitzung" and French "séance" exist but are uncommon in research contexts. Japanese and Korean simply transliterate (セッション, 세션).

**Signals**
"Signals" has **no equivalent in any language's QDA tradition** — it's a Bristlenose-specific concept. The closest academic terms are patterns (Muster / パターン / 패턴) or themes (Themen / テーマ / 주제). We recommend transliterating: Signale / Signaux / Señales / シグナル / 시그널 — since it's our concept, we name it.

### Cross-cutting observations

- **Japanese and Korean** transliterate nearly everything into katakana/Hangul — the research communities work in English-origin terminology
- **German, French, Spanish** have genuine native vocabulary — use it for academic credibility
- **French "verbatim"** is the single most important finding — it's the natural, warm term French researchers use. Getting this right signals "this tool was built for us"

## Third-party codebooks (future work)

### Don Norman — The Design of Everyday Things

Translated into 20+ languages. Key finding for Japanese: the community uses **katakana transliterations** rather than native Japanese terms:
- アフォーダンス (afōdansu) = affordance
- シグニファイア (shigunifiaia) = signifier
- マッピング (mappingu) = mapping

This means Don Norman tags should stay in their original English for now, but Japanese translations would use these established katakana terms, not invented Japanese words. The professional community already knows them.

### Morville Honeycomb / Garrett Elements / Nielsen Heuristics — don't translate

Amazon sales rank data (Mar 2026) confirms these frameworks have negligible international traction:

| Book | Japan (amazon.co.jp) | France (amazon.fr) |
|------|---------------------|-------------------|
| **Norman** | **#5,251** (155 ratings) | #212,175 (#1 in category, 54 ratings) |
| Garrett | #255,896 (24 ratings) | #879,506 (3 ratings) |
| Morville | #149,288 (41 ratings) | **No French translation exists** |
| Nielsen | #532,405 (4 ratings) | **No French translation exists** |

Norman at #5,251 in Japan is a genuinely popular book still actively selling 10+ years after the revised edition. Everything else is noise. Morville and Nielsen were never even translated into French.

**Locally-authored UX books massively outperform translated anglosphere ones** (except Norman): Amélie Boucher's "Ergonomie web" has 344 reviews on Amazon.fr vs Garrett's 3. Masaya Ando's UX textbook ranks #22,176 in Japan vs Garrett's #255,896.

**Decision:** Translate Norman's codebook when we do third-party i18n. Garrett, Morville, and Nielsen stay English — their audience learned these frameworks in English.

### Strategy for Norman translation (future)

- Japanese: use established katakana transliterations (アフォーダンス, シグニファイア, マッピング) — the community already uses these
- German/French/Spanish: research the official published translations for each concept term
- Cross-check with what the professional community actually says (may differ from the book)
- Korean: likely Hangul transliterations, same pattern as Japanese

## String audit — full scope

**Already in i18n (34 keys):** nav tabs, basic buttons (Save/Cancel/Export/Close), sentiment enum names, speaker roles, settings panel labels, footer.

**Hardcoded (~180+ strings) — not yet in i18n.** Grouped by priority:

### Tier 1 — Core research vocabulary
The words researchers see constantly. Getting these right determines whether the tool "speaks their language".

- **Report structure:** Section, Theme, Sections, Themes
- **Analysis:** Signal, Signals, Concentration, Agreement, Intensity, "Composite signal strength", "concentration ratio", "agreement breadth (Simpson's diversity index)"
- **Coding:** Codes, Codebook, Tags, Tag signals, Sentiment signals
- **Data:** Quotes, Sessions, Participants, Interviews, Duration, Speakers
- **Actions:** Star, Hide, Unhide, Add tag, Search quotes, Filter quotes
- **Quote card:** sentiment badge labels, moderator question, "Revert to original", "Restore tags"

### Tier 2 — Action chrome
Buttons, modals, keyboard shortcuts — functional UI that users interact with but don't "read".

- Modal headings: "Export report", "Keyboard Shortcuts", "How is Bristlenose working for you?"
- Modal content: "Download a self-contained HTML file...", "Anonymise participants", "Remove participant names, keep codes..."
- Search: "Filter quotes…" (placeholder), "Clear search", "Search tags…"
- Keyboard shortcut descriptions (15 strings): "Next quote", "Previous quote", "Toggle select", etc.
- Transcript: "Show previous/next transcript segment", "Copy folder path"
- Codebook: "Create new codebook", "Browse codebooks", "Your codebooks", "Import a framework..."
- Feedback: "Frustrating" / "Needs work" / "It's okay" / "Good" / "Excellent"

### Tier 3 — About, settings, dev tools
Low-frequency content. Researchers see it once.

- Sentiment definitions ("Frustration — difficulty, annoyance, friction" etc.)
- Configuration reference labels (LLM Provider, Transcription, Privacy, all env var names)
- About panel content, version info, links
- Playground labels (dev-only — arguably never translate)

### Scale

~34 strings already in i18n × 5 languages = manageable.
~180 hardcoded strings × 5 languages = ~900 translations total. Tier 1 (~40 strings) is the critical path.

## Implementation plan (future)

### Phase 1: UI chrome terminology
Add the 6 core terms to `common.json` for all 5 non-English locales.

Files: `bristlenose/locales/{de,fr,es,ja,ko}/common.json`, mirrored in `frontend/src/locales/`.

### Phase 2: Sentiment translations
Populate the 4 missing locale files (ja, fr, de, ko) with the 7 sentiment tag translations. (Spanish done in v0.13.7.)

Files: `bristlenose/locales/{locale}/enums.json`, mirrored in `frontend/src/locales/`.

### Phase 3: UXR codebook translation layer
- YAML stays English (single source of truth for IDs, definitions, `apply_when`, `not_this`)
- Add `bristlenose/locales/{locale}/codebook_uxr.json` mapping English tag name → translated display name + group name + subtitle
- Update codebook display components to use i18n lookup with English fallback
- Adding a new language = one JSON file per codebook

Key files: `bristlenose/server/codebook/__init__.py`, `bristlenose/server/codebook/uxr.yaml`, `frontend/src/islands/QuoteCard.tsx`, `frontend/src/components/TagInput.tsx`.

### Phase 4: Quality gate
- Machine-translate Phases 1–3 as draft
- Create review checklist for native-speaking UX researchers per language
- Track review status per locale (reviewed/unreviewed flag)

## Progress

### Spanish (es) — machine-translated, v0.13.7 (16 Mar 2026)

All 102 existing i18n strings machine-translated across 8 files (3 frontend, 5 backend). Cross-checked against the terminology table above — "Citas", "Libro de códigos", "Sesiones", "Señales" all match the recommended terms.

**Review status:** awaiting native-speaker review (Lidia, Sevilla).

**Open questions for reviewer:**
- "Delight" → "Entusiasmo" or "Deleite"? Machine translation chose "Entusiasmo" (enthusiasm); "Deleite" is closer to the UX/design sense of delight. Both are valid — needs a native UXR practitioner's judgement
- "Libro de códigos" — ATLAS.ti's term, recommended by our research. Confirm it feels natural vs alternatives like "Manual de códigos"
- "Investigador/a" for Researcher — gender-inclusive slash form. Confirm this is the convention Lidia prefers (vs "Investigador(a)" or just "Investigador")

### Not in scope
- Translating LLM prompts (not needed — cross-lingual works)
- Translating codebook `definition`/`apply_when`/`not_this` fields (LLM-facing, English performs best)
- `analysis_language` setting for LLM-generated summaries/themes (separate feature)
- New locales beyond the 6 already supported

## Mixed-language interview scenario

A German researcher using Don Norman's framework against mixed German/English interviews:
- Read Don Norman in English → thinks about "affordances" in English
- Interviews in German/English mix → participants code-switch naturally
- Wants tags like "affordance", "signifier" → already English, matching the framework
- Wants quotes in whatever language the participant used → preserved verbatim
- Wants UI chrome in German → "Zitate", "Codebuch", "Interviews"
- Wants theme summaries → configurable via `analysis_language` (future)

The LLM handles this natively. The display layer translates. No prompt or transcript translation needed.
