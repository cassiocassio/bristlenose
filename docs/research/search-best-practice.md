---
status: research
date: 4 Oct 2026
---

# Search: best practice against what Bristlenose does

A comparison of established search practice (standards, engine documentation,
QDA tools, Apple, NN/g) with the toolbar search as built on 4 Oct 2026, and a
proposed order for what comes next. The spec of what is built is
[`design-search.md`](../design-search.md); this is the survey around it.

Sources are listed at the end, and each was labelled primary, vendor or secondary
when gathered. Vendor claims are treated as claims.

## The frame: three different things are called "AI search"

| Need | Example | Right mechanism |
|---|---|---|
| **Resolving which person a name means** | "William" finds the participant called Will | An alias list on each person, filled by the pipeline's LLM pass ("call me Will") and editable in the people view. No embeddings. |
| **Concept match** | "price" finds "way too expensive" | Embeddings, shown as a separate, labelled *Related* tier below the exact matches |
| **Question** | "Which participant was motivated by free drinks?" | A cited answer: today through Claude or ChatGPT on the MCP extension; in the app, the chat lens |

The owner's point (4 Oct 2026): the obvious enhancements are AI ones, and the
best way to ask a question of a report *today* is Claude through the MCP
extension. That makes the MCP search tool the first thing to strengthen. An
agent can re-ask a question as many ways as it likes, but it cannot fix a
matcher that misses.

**The filter stays a filter.** Exact matches in report order are the
researcher's triage scaffold: they need every quote, and a count they can trust.
Anything fuzzy (word forms, typos, meaning) is a separate, labelled tier or an
explicit choice, never a silent widening. NVivo and MAXQDA make word forms
opt-in. Dovetail widens unquoted terms silently, which suits a repository being
browsed and does not suit a quote count.

## Comparison

**Status:** ✅ done · 🟡 partly · ⬜ not done. **Cost:** S (a day or less), M (days),
L (a week or more). **Value** is for a researcher using the report.

### Matching (lexical)

| Practice | Prior art | Status | Notes | Cost | Value |
|---|---|---|---|---|---|
| Case, width, accent folding | ICU folding, Elasticsearch `asciifolding`, `Intl.Collator` search | ✅ | Exceeds asciifolding; marks kept where they change the word (ja, th, hi); `deburr` for ø ł đ æ œ þ ı | — | — |
| Nordic and Turkish letters as letters (å ≠ a in Swedish) | ICU folding's `unicode_set_filter` exemption | ⬜ by choice | Folded for recall; over-matching is visible in a filter. Revisit only on a complaint: exempt per transcript language | S | Low |
| German ü ↔ ue | Lucene `GermanNormalizationFilter` (Snowball German2) | ⬜ known limit | Only for German-language quotes, or it merges English pairs (blue → blu). Needs the quote's spoken language | S | Narrow |
| Phrase as typed, prefix on the last word | FTS5 `"one two thr*"`, Typesense `prefix` | ✅ | A quoted term is exact text anywhere | — | — |
| Punctuation: separators vs meaning | UAX #29 word boundaries | ✅ | Dashes and sentence punctuation separate; `# @ % &` stay in the word; a finished word is not a prefix | — | — |
| Joined forms (covid19 ↔ COVID-19, 1000 ↔ 1,000, coop ↔ co-op) | Lucene `WordDelimiterGraphFilter` catenate | ✅ | Both directions. The thousands rule needs exactly three digits | — | — |
| Split ↔ join on zero results ("co op" finds "coop") | Typesense `split_join_tokens: fallback` | ⬜ | Only when nothing matched, so it never widens a working filter | S | Medium |
| Segmentation for unspaced scripts | ICU dictionary, Kuromoji + bigrams, `Intl.Segmenter` | ✅ match anywhere | Unigram substring: maximum recall, fine for a filter. Dictionary segmentation is a precision option only | — | — |
| Korean particles | Lucene Nori `KoreanPartOfSpeechStopFilter` (strips by default) | 🟡 | Done for whole-word name matching; not for free text | S–M | Medium for ko |
| Word forms (stemming or lemmas) | Snowball (16 of our languages), Simplemma (uk), NVivo and MAXQDA opt-in | ⬜ | Opt-in, keyed on the **spoken** language, not the UI language. Most valuable for fi, cs, pl, ru, uk, tr | M | Medium |
| Typo tolerance | Algolia 4/8, Meilisearch 5/9, Typesense 4/7 (characters for 1 and 2 typos) | ⬜ | Never inside the filter: it adds silent false positives (cost ≈ cast). Safe in people and tag suggestions, and as "did you mean" on zero results | S–M | Medium |
| Synonyms | NVivo thesaurus (7 languages); project-defined | ⬜ | Project-defined, proposed by the LLM, accepted by the researcher. Semantic search covers much of it | M | Low–Med |
| Boolean OR in text | Apple Mail AND/OR/NOT | 🟡 | Chips already give NOT and implicit AND; only OR is missing | S | Low |
| Ranking | BM25 (`fts5 bm25()`) | ⬜ by design | Not for the exact tier. Only for a Related tier, transcripts, cross-project | — | — |
| Same rules on every surface | Shared golden fixture | 🟡 | `tests/fixtures/search-match-contract.json` pins the rules, but **only TypeScript asserts it**. The MCP `search_quotes` tool uses a plain lower-case substring (`mcp_server.py:635`): no accent folding, no phrases, no joined forms | M | **High** |

### Search UX

| Practice | Prior art | Status | Notes | Cost | Value |
|---|---|---|---|---|---|
| Search as you type under 100 ms | NN/g response limits; Apple HIG | ✅ | p50 7.5 ms, p95 8.8 ms over 10,000 quotes | — | — |
| Suggestions combobox | WAI-ARIA APG (list, manual selection) | ✅ | Free text, people and tags, with counts; reviewed for WCAG 2.1 AA on 4 Oct | — | — |
| Suggestions that never lead to zero results | NN/g site-search suggestions | ✅ | Every row shows its count | — | — |
| Tokens with an editable meaning | Apple Mail, Apple HIG search tokens | ✅ | said by / mentions / not; tagged / text contains / not tagged | — | — |
| Screen-reader feedback | APG; WCAG 4.1.3 | ✅ | Match count; chip selected / removed; search cleared, in 21 languages | — | — |
| Zero-results state | NN/g: say so, offer ways forward, offer a wider scope | ⬜ | Name the scope; offer "remove *not tagged X* → 14 quotes" per chip; offer the transcripts | S–M | **High** |
| Scope label and one-click widening | NN/g scoped search | 🟡 | Search is the Quotes lens only; the field on other lenses does nothing yet | M | High |
| Recent searches on an empty, focused field | Apple HIG | ⬜ | Per viewer, browser storage | S | Medium |
| Saved searches | Mail smart mailboxes, Finder smart folders | ⬜ | Closer to a named, shareable view than to search | M | Low–Med |
| Find inside a transcript | ⌘F everywhere | ⬜ | Already a planning item; pairs with a transcript index | M | High |

### AI

| Practice | Prior art | Status | Notes | Cost | Value |
|---|---|---|---|---|---|
| Let the user's own agent reason | MCP; OpenAI deep research `search` + `fetch` | 🟡 | Shipped: the `.mcpb` extension for Claude, the plugin for ChatGPT, four read-only tools. No `fetch` tool, so ChatGPT deep research and company knowledge cannot use it as a source | S | High |
| Name resolution (William → Will) | Nickname datasets (English-only, biased); the LLM pass itself | ⬜ | Aliases on the person, from the transcript, editable; matched by search, suggestions and MCP. Ties into the people identity work | S–M | **High** |
| Ask the report from the search field | Dovetail (auto-detects questions), Marvin, MAXQDA AI Chat | ⬜ by decision | Parked 4 Oct 2026: MCP is the chat lens, so a question goes to the researcher's own agent. The chat lens prototype (whole corpus in context, server-checked citations, a support check) stays as grounding work | — | — |
| Scope a question by the active chips | Marvin, Delve, ATLAS.ti | ⬜ | Parked with the in-app question box; on MCP, the agent scopes with `search_quotes` filters | — | — |
| Quotes from participants only | Marvin "Respondents" | — check | Quotes are participant speech by construction; confirm before building anything | — | — |
| Citations as IDs, verbatim text from the store | Claude citations on custom-content blocks | ✅ in the chat lens | Server-constructed indices; a fabricated citation is an out-of-range number | — | — |
| Answer plus "show all N matching quotes" | NN/g: people fact-check AI with search | ⬜ | The research evidence is that omission is a bigger risk than invention; the handoff to the filter answers omission | S | Medium |
| Semantic *Related* tier | Hybrid BM25 + vectors (BEIR); RRF | ⬜ | Embeddings at analysis time, brute-force cosine (no vector index at quote scale). Changes the export (≈6 MB of vectors against a 1.55 MB file) | M–L | Med–High, unproven here |
| On-device embeddings | multilingual-e5, BGE-M3, EmbeddingGemma; Apple `NLEmbedding` (6 languages) | ⬜ | Apple's sentence embedding is unsuitable for 21 locales. Evaluate on our own transcribed speech; leaderboards do not transfer (BEIR) | L | — |

### Evaluation

| Practice | Status | Notes | Cost |
|---|---|---|---|
| Golden lexical fixture | 🟡 | Exists for TypeScript; Python must assert it when it matches | S once Python matches |
| Zero-result rate | ⬜ | Counts only, local: the queries themselves are participant data | S |
| Known-item recall for semantic and QA | ⬜ | 50–100 paraphrase queries per main language, human-approved once | M |
| Citation checks | 🟡 | Verbatim by construction; a support check exists in the chat lens | — |

## Proposed sequence

Ordered by the owner's emphasis (AI first, through the path that works today)
and by dependency. Each step is useful on its own.

**How users will behave (owner, 4 Oct 2026): Google is the minimum search
experience** they expect in any app — *Mike* finds *Michael*, *Alsatian* is a
kind of dog, a *hotdog* is food. A truth about expectations to design against,
not an engineering goal for today.

**Narrowed the same hour:** meaning (*Alsatian* is a dog) is an LLM problem,
not a quick-find one, so it belongs with the agent over MCP. The search field
is quick find: simple, but not stupid — punctuation, plurals, misspellings, the
classic lexical toolkit. Ship close to what exists.

**Decided 4 Oct 2026: for the foreseeable future, MCP is the chat lens.** No
in-app question box until Bristlenose adds more value than Claude inside the
app. So the AI steps below are about making the MCP tools better grounding for
the researcher's own agent; the in-app "Ask the report" row (step 4) is
withdrawn, and a question in the search field is the agent's job.

1. **MCP search on the contract.** A Python matcher that asserts
   `search-match-contract.json`, used by `search_quotes`. This is the path Claude
   and ChatGPT use today, and it currently misses "José" for "jose". It also
   delivers the TS ↔ Python half of the golden fixture. Add a `fetch` tool so
   ChatGPT deep research can use the report. **M.**
2. **Person aliases.** The pipeline's LLM pass emits `aliases[]` per speaker; the
   researcher edits them; search, suggestions and MCP match them. Typo-tolerant
   people and tag suggestions in the same step. This makes "William" work for the
   agent and the field alike. Sequence with the people identity work. **S–M.**
3. **Zero-results state.** Name the scope, relax-a-chip counts, and a "Search
   transcripts" way forward. Local zero-result counters
   (counts only). **S–M.**
4. ~~**"Ask the report" row → chat lens.**~~ Withdrawn 4 Oct 2026: MCP is the
   chat lens. Its MCP-side counterpart: **a transcript tool**, so the agent can
   answer "what did the moderator say?", which mostly is not in the quotes.
   **S–M.**
5. **Recent searches** on an empty, focused field. **S.**
6. **"Did you mean"** and split ↔ join, on zero results only. **S–M.**
7. **Transcript search and find-in-transcript.** The case for the FTS5 index:
   transcripts and cross-project, not the Quotes lens (a linear scan is fast at
   quote scale). Avoid FTS5's `trigram` tokenizer for Chinese and Japanese: it
   cannot match fewer than three characters, and most words are two. **M.**
8. **Opt-in word forms**, by spoken language; Korean particles for free text;
   German ü/ue for German quotes. Needs the quote's language stored. **M.**
9. **Semantic Related tier**, after an evaluation on our own speech. **M–L.**
10. Later, on demand: OR in text, saved views, project synonyms, Nordic letter
    exemption.

## Where the evidence is thin

- Whether auto-detecting a question beats an explicit "Ask" row: no primary study
  found.
- Which QDA search options researchers actually use (stemming, synonyms,
  questions): no published usage data. Treat claims of demand for AI search as
  hypotheses for the TestFlight cohort.
- Vendor accuracy claims (Looppanel's "85%", EmbeddingGemma's MTEB rank) are
  marketing.
- Apple `NLEmbedding` language coverage: one secondary source.

## Sources

- Unicode UAX #29 — https://www.unicode.org/reports/tr29/
- Elasticsearch ICU tokenizer, ICU folding, Nori — https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-icu-tokenizer.html, https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-icu-folding.html, https://www.elastic.co/guide/en/elasticsearch/plugins/current/analysis-nori-tokenizer.html
- Lucene `KoreanPartOfSpeechStopFilter`, `GermanNormalizationFilter`, `WordDelimiterGraphFilter` — https://lucene.apache.org/core/9_0_0/analysis/common/org/apache/lucene/analysis/de/GermanNormalizationFilter.html, https://lucene.apache.org/core/9_0_0/analysis/common/org/apache/lucene/analysis/miscellaneous/WordDelimiterGraphFilter.html
- Japanese full-text search in Elasticsearch (vendor engineering blog) — https://www.elastic.co/blog/how-to-implement-japanese-full-text-search-in-elasticsearch
- MDN `Intl.Segmenter`, `Intl.Collator` — https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter
- SQLite FTS5 — https://www.sqlite.org/fts5.html ; APSW text search — https://rogerbinns.github.io/apsw/textsearch.html
- Snowball — https://snowballstem.org/algorithms/ ; Simplemma — https://github.com/adbar/simplemma
- Typo tolerance: Algolia — https://www.algolia.com/doc/guides/managing-results/optimize-search-results/typo-tolerance/ ; Meilisearch — https://www.meilisearch.com/docs/learn/relevancy/typo_tolerance_settings ; Typesense — https://typesense.org/docs/latest/api/search.html
- BEIR (NeurIPS 2021) — https://arxiv.org/pdf/2104.08663 ; Reciprocal Rank Fusion (SIGIR 2009) — https://www.semanticscholar.org/paper/Reciprocal-rank-fusion-outperforms-condorcet-and-Cormack-Clarke/9e698010f9d8fa374e7f49f776af301dd200c548
- NN/g: response times, search suggestions, zero results, scoped search, AI and search behaviour, why repositories fail — https://www.nngroup.com/articles/response-times-3-important-limits/, https://www.nngroup.com/articles/site-search-suggestions/, https://www.nngroup.com/articles/search-no-results-serp/, https://www.nngroup.com/articles/scoped-search/, https://www.nngroup.com/articles/ai-changing-search-behaviors/, https://www.nngroup.com/articles/why-repositories-fail/
- WAI-ARIA APG combobox — https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
- Apple Mail search — https://support.apple.com/guide/mail/search-for-emails-mlhlp1003/mac
- OpenAI deep research and MCP — https://developers.openai.com/api/docs/guides/deep-research
- Claude citations — https://platform.claude.com/docs/en/build-with-claude/citations
- Embedding models: multilingual-e5-small — https://huggingface.co/intfloat/multilingual-e5-small ; BGE-M3 — https://huggingface.co/BAAI/bge-m3 ; EmbeddingGemma (vendor) — https://developers.googleblog.com/en/introducing-embeddinggemma/ ; sqlite-vec — https://github.com/asg017/sqlite-vec
- Nicknames dataset — https://github.com/carltonnorthern/nicknames
- QDA tools: NVivo text match settings — https://help-nv11.qsrinternational.com/desktop/deep_concepts/understand_text_match_settings.htm ; MAXQDA lexical search — https://www.maxqda.com/help-mx22/lexical-search/the-lexical-search-options-in-the-dialog-window ; MAXQDA AI Chat — https://www.maxqda.com/help/ai-assist/ai-chat-with-documents ; ATLAS.ti conversational AI — https://atlastihelp.helpscoutdocs.com/article/612-conversational-ai ; Dovetail search — https://docs.dovetail.com/help/search ; Marvin Ask AI — https://help.heymarvin.com/en/articles/10130400-how-do-i-use-ask-ai ; Condens (vendor) — https://condens.io/product-updates/analyze-research-data-with-ai-questions/ ; Looppanel (vendor) — https://www.looppanel.com/feature-pages/repository-search ; Delve (vendor) — https://delvetool.com/delve-ai
- Hallucination and omission in LLM-supplied quotes (secondary; follow its citations before quoting numbers) — https://www.uintent.com/case-studies-und-blog/the-hallucination-problem
