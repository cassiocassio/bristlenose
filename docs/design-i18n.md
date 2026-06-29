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

**Localised defaults vs English-canonical defaults.** A placeholder *name* the user
immediately renames (a "rename seed") IS localised: `codebook.newGroup` / `codebook.newCode`
resolve in the active UI language at creation time, because nothing downstream keys off the
string — it exists to be typed over. The English-always rule above governs *canonical* values
only (enum keys, tags, LLM-facing strings, anything matched / joined / fed to a prompt). The
test when adding a defaulted field: **does anything downstream match, join, or feed this
string to an LLM?** If yes → store English. If it's a freeform field the user overwrites →
localise the default. (Contrast `project_name = "Untitled"` in `server/importer.py`, an
identifier-ish fallback that deliberately stays English.)

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

~180 keys across 8 namespaces × 7 languages = ~1,260 translation strings total.

## Architecture: single source of truth (implemented, Mar 2026)

### Canonical locale directory

**`bristlenose/locales/{locale}/{namespace}.json`** — the only place translations live. Three codebases consume them:

| Consumer | How it reads locale files |
|----------|-------------------------|
| **Python** (`bristlenose/i18n.py`) | Direct filesystem read at runtime. `t("namespace.key")` |
| **React** (`frontend/src/i18n/`) | Vite `resolve.alias` (`@locales`) at build time. English bundled inline; other locales lazy-loaded via dynamic `import()` |
| **macOS desktop** (`desktop/.../I18n.swift`) | `I18n` class loads JSON from disk. `findLocalesDirectory()` priority (top wins): (1) `#filePath`-derived path relative to `I18n.swift` itself — resolves to the worktree's own `bristlenose/locales/` so each git worktree reads its own files, not the main repo's; (2) `~/Code/bristlenose/bristlenose/locales` legacy fallback; (3) bundled `.app` (`Bundle.main.resourceURL/sidecar/_internal/.../locales`); (4) Homebrew / pipx site-packages. Worktree-aware fallback added 2026-05-01 (commit `816ab65`) — without it, locale keys added in a worktree silently fail to resolve at runtime |

### Namespace inventory

| Namespace | Used by | Keys |
|-----------|---------|------|
| `common.json` | React + Desktop | ~34 (nav tabs, buttons, labels, footer) |
| `settings.json` | React + Desktop | ~15 panel labels + `pipeline.alternatives.*`, `pipeline.reasons.*`, `pipeline.backends.*` (v1.5 Pipeline-view keys; ~25 leaves) |
| `enums.json` | React + Python + Desktop | ~11 (sentiments, speaker roles) |
| `cli.json` | Python only | ~15 (CLI output) |
| `pipeline.json` | Python only | 4 (stage progress: `start`, `stageStart`, `stageComplete`, `done`). **Note:** the Pipeline-view editorial keys (`pipeline.reasons.*`, `pipeline.backends.*`, `pipeline.alternatives.*`, and v1.9's `pipeline.quality.*`) currently colocate under `settings.json`, not `pipeline.json`. Eventual housekeeping question — consolidate under one file or split semantically — tracked separately. |
| `server.json` | Python only | ~5 (API errors) |
| `doctor.json` | Python only | ~5 (health checks) |
| `desktop.json` | Desktop only | ~95 (menu bar, toolbar, native chrome, `boot.*` and `welcome.*` blocks added 2026-05-01) |

### Desktop locale flow

**Canonical design:** `docs/design-locale-negotiation.md` — covers desktop-vs-web split, why we delegate to System Settings → Apps, and the `UIPrefersShowingLanguageSettings` Info.plist key.

1. **macOS picks the locale.** `I18n.swift` reads `Bundle.preferredLocalizations(from: supportedLocales, forPreferences: nil).first ?? "en"` on every launch. Apple's BCP 47 lookup matcher reads `AppleLanguages` (set globally by System Settings → General → Language & Region, or per-app by System Settings → Apps → Bristlenose → Language).
2. `I18n.setLocale()` reloads JSON from disk → `@Published` triggers SwiftUI re-render. The setter is now used only for runtime locale propagation, not user choice.
3. `BridgeHandler.syncLocale()` pushes locale to web via `callAsyncJavaScript`.
4. Startup flash prevention: locale injected as `?locale=es` URL query param on WKWebView load → `LocaleStore.ts` detects synchronously before first render.
5. In embedded mode, the web language picker is hidden — System Settings is the single control point. The web picker remains visible and usable in real-browser CLI serve mode (no per-site language override exists in browsers, so the in-app picker is the only escape hatch there).
6. **No in-app language picker on desktop.** Settings → Appearance contains a hint paragraph pointing users to System Settings → Apps → Bristlenose. `INFOPLIST_KEY_UIPrefersShowingLanguageSettings = YES` (in `project.pbxproj`) forces that section to appear in System Settings even for users with only one preferred language configured globally.

### `CommandMenu` titles stay in English

SwiftUI's `CommandMenu("Project")` takes `LocalizedStringKey` which resolves from `.lproj` bundles, not runtime JSON. Rather than maintaining a second localisation format for 4 strings, menu titles ("Project", "Codes", "Quotes", "Video") stay in English. Menu *items* inside are translated via `I18n.t()`. This matches ATLAS.ti and MAXQDA precedent — both keep English menu titles even in localised UIs.

### Toolbar overflow: `_short` keys

"Libro de códigos" (es) and "Grille de codage" (fr) are ~2× wider than "Codebook". The toolbar segmented control uses `common.nav.{tab}Short` keys where available, falling back to the full `common.nav.{tab}` key. Only add `_short` variants where the full label exceeds ~10 characters.

| Tab | Full (View menu) | Short (toolbar) |
|-----|-----------------|-----------------|
| codebook (es) | Libro de códigos | Códigos |
| codebook (fr) | Grille de codage | Codage |

## Terminology standards

### Per-namespace key convention

Two conventions coexist in the locale tree, applied per surface:

- **camelCase flat / shallow-nested** — short, sentence-ish action / progress strings authored fresh in JSON. Examples: `pipeline.json`'s `stageStart` / `stageComplete`; `common.json`'s `nav.codebook`; `enums.json`'s `speakerRole.participant`.
- **`<category>.<snake_case_leaf>`** — keys that map 1-to-1 to Python identifiers (predicate explainers, backend ids, quality note keys). Examples from `settings.json`: `pipeline.reasons.mlx_whisper_not_installed`, `pipeline.backends.local_ollama`, and v1.9's `pipeline.quality.local_quote_extraction_miss_rate`. The snake_case leaf preserves grep parity between the Python identifier and the i18n key — `grep miss_rate locales/` finds the locale entry; `grep miss_rate bristlenose/` finds the catalogue cell that references it.

The rule is **convention-by-origin, not convention-by-file**. New keys derived from Python identifiers (catalogue cells, requirement names, enum-like predicates) use snake_case leaves under their category. New keys authored fresh for UI chrome (button labels, panel titles, action verbs) use camelCase. When in doubt, look at the sibling keys in the same category block; consistency within a block matters more than uniformity across the file.

See [design-pipeline-view.md](design-pipeline-view.md) §Locale convention for the v1.9 instantiation of this rule.

### The "Cancel button problem"

Every language has a standard word for common UI actions. Getting it wrong makes the tool feel alien. Two authoritative databases exist:

- **[applelocalization.com](https://applelocalization.com/)** — searchable Apple glossary from official bilingual glossaries for macOS/iOS. Since Bristlenose is a macOS app, this is the primary reference. Also available as [DMG downloads](https://developer.apple.com/localization/resources/) from Apple Developer.
- **[termic.me](https://termic.me/)** — indexes Microsoft Terminology + 10,000 VS Code strings. Cross-reference when Apple's glossary doesn't cover a term. [Open source](https://github.com/Spidersouris/termic).

**Rule: for standard UI verbs (Save, Cancel, Delete, Close, Undo, Export, Search), always use Apple's term for the target platform.** Cross-check against Microsoft for general IT terms. If both agree, it's definitive. If they differ (rare for basics), prefer Apple since we're a macOS-native app.

### Process for adding a new language

#### Step 1: Machine-translate as draft
Machine-translate all 8 namespace files. Use the English files as source. This gives you a working baseline that's ~80% correct for standard UI terms.

#### Step 2: Apple glossary cross-check (mandatory)

The canonical source for how Apple translates standard UI terms on macOS is `support.apple.com` in the target language — specifically the keyboard shortcuts page (e.g. `support.apple.com/es-lamr/102650` for Latin American Spanish). This page uses Apple's actual menu labels.

**Check every standard UI button/action against Apple's term.** The terms that matter most:

| English | What to look up |
|---------|----------------|
| Save, Cancel, Close, Delete, Undo, Redo | File/Edit menu terms |
| Copy, Cut, Paste, Select All | Edit menu terms |
| Find, Find Next, Find Previous | Edit > Find menu terms |
| Print, Export | File menu terms |
| Zoom In, Zoom Out, Fullscreen | View menu terms |
| Hide, Show, Settings/Preferences | App menu terms |
| Search | Toolbar/Spotlight terms |
| New, Open, Quit | File menu terms |

**Gotcha: Apple's shortcuts page uses informal descriptions, not menu labels.** The shortcuts page might say "Buscar otra vez" (search again) where the actual Edit menu says "Buscar siguiente" (Find Next). When in doubt, the menu label wins — open a Mac app (Safari, Finder, TextEdit) in the target locale and look at the actual menu text. Or use [applelocalization.com](https://applelocalization.com/) which indexes the actual `.strings` files.

**Gotcha: "Delete" has two senses in Apple's terminology.** "Suprimir" is the keyboard Delete key; "Eliminar" is the destructive action (delete a file, remove an item). Bristlenose uses Delete as an action → use the action form, not the key name.

**Gotcha: Apple changed "Preferencias" to "Ajustes" in macOS Ventura (2022)**, matching iOS. Old documentation may still say "Preferencias". Use "Ajustes" for macOS 13+.

#### Step 3: Cross-check domain vocabulary

Check our research terminology table (earlier in this document) for the target language. The domain terms (Quotes, Codebook, Sessions, Signals, Codes) were researched from ATLAS.ti, MAXQDA, and academic QDA literature — they override any machine translation.

#### Step 4: Toolbar overflow check

Check whether `common.nav.codebook` exceeds ~10 characters in the target language. If so, add a `common.nav.codebookShort` key. Check other tab labels too — `sessions` is "Interviews" (10 chars) in German and "Entretiens" (10 chars) in French, both borderline.

#### Step 5: Native-speaker review

Send the draft to a native-speaking UXR practitioner. Key review questions:
- Do the domain terms (Codebook, Quotes, Sessions) match what this community actually says?
- Are button labels natural or stilted?
- Gender conventions: inclusive slash form ("Investigador/a") vs parenthetical ("Investigador(a)") vs neutral
- Formality: formal "usted" vs informal "tú" (varies by country for Spanish; Japanese has even more registers)

#### Step 6: Machine translation QA — domain term grep

Machine translation reliably handles standard UI verbs but **frequently leaves domain-specific nouns as English loanwords** in the middle of otherwise-translated sentences. The v0.14.1 batch left "codebook" untranslated in ~15 keys per language (es/fr) while correctly translating the same term in nav labels and headings.

**After every machine translation batch, run this check:**

```bash
# For each domain term, grep for the English word in every non-English locale
for lang in es fr de ko; do
  echo "=== $lang ==="
  for term in codebook quotes sessions signals codes tags sentiment; do
    hits=$(grep -i "\"[^\"]*\b${term}\b[^\"]*\"" bristlenose/locales/$lang/*.json \
           | grep -v "\"${term}\":" | wc -l)
    [ "$hits" -gt 0 ] && echo "  $term: $hits untranslated values"
  done
done
```

Any English domain term appearing in a **value** (not a key) is a miss. Keys like `"codebookTags"` are internal identifiers and should stay English.

**Common failure patterns to watch for:**

1. **Loanword in modifier position** — "codebook tags", "browse codebooks" get half-translated ("Explorar codebooks" instead of "Explorar libros de códigos"). The machine translates the verb but leaves the noun as English
2. **Inconsistency across namespace files** — desktop.json may get the correct translation while common.json doesn't (different translation passes or prompts)
3. **Article gender cascades** — when the translated term changes grammatical gender, articles and adjectives throughout the sentence must change too. French: "un nouveau codebook" → "une nouvelle grille de codage" (grille is feminine). Spanish: "de codebook" → "del libro de códigos" (de + el contracts)
4. **Preposition contractions** — Spanish "de + el" = "del", "a + el" = "al". French doesn't contract with feminine articles. Getting these wrong sounds jarring to native speakers
5. **Singular/plural form mismatch** — the glossary should include both forms: "libro de códigos" / "libros de códigos" (es), "grille de codage" / "grilles de codage" (fr), "Codebuch" / "Codebücher" (de)

**Prevention: build a glossary before translating.** Give the machine translator a term table (English → target language, singular + plural) and instruct it to use these terms exclusively. Then grep to verify.

#### Step 7: Track review status

Add a progress entry to the "Progress" section below with: language, date, reviewer name/location, review status, open questions.

### Spanish cross-check results (23 Mar 2026)

All Spanish translations verified against [Apple's macOS keyboard shortcuts page (es-lamr)](https://support.apple.com/es-lamr/102650). Results:

| English | Ours | Apple | Verdict |
|---------|------|-------|---------|
| Save | Guardar | Guardar | ✓ |
| Cancel | Cancelar | Cancelar | ✓ |
| Close | Cerrar | Cerrar | ✓ |
| Copy | Copiar | Copiar | ✓ |
| Delete | Eliminar | Suprimir (key) / Eliminar (action) | ✓ action sense correct |
| Undo | Deshacer | Deshacer | ✓ |
| Redo | Rehacer | Rehacer | ✓ |
| Search/Find | Buscar | Buscar | ✓ |
| Find Next | Buscar siguiente | Buscar otra vez (informal) | ✓ menu label is "Buscar siguiente" |
| Print | Imprimir | Imprimir | ✓ |
| Hide | Ocultar | Ocultar | ✓ |
| Open | Abrir | Abrir | ✓ |
| Fullscreen | Pantalla completa | Pantalla completa | ✓ |
| Settings | Ajustes | Ajustes (post-Ventura) | ✓ |
| Export | Exportar | Exportar | ✓ |
| Zoom In | Ampliar | Aumentar el tamaño (informal) | ✓ short form used in actual menus |
| Zoom Out | Reducir | Reducir el tamaño (informal) | ✓ short form used in actual menus |
| Accept | Aceptar | Aceptar | ✓ |
| Apply | Aplicar | Aplicar | ✓ |
| Reset | Restablecer | Restablecer | ✓ |

**No changes needed.** All translations match Apple's canonical menu-level terms.

## Community translation: Weblate

### Why Weblate

[Weblate](https://weblate.org/) is a libre (GPLv3) translation platform. The hosted instance at `hosted.weblate.org` is **free for libre/FOSS projects** — equivalent to the 160k strings tier (€114/month value). Unlimited projects, components, translators. All features included.

Bristlenose qualifies (AGPL-3.0) and was approved for the Libre plan on 29 Apr 2026 after a multi-week trial-and-merge-conflict saga (see `project_weblate_ticket_2013688.md` memory for the operational history). **This is the path forward for the foreseeable future** — the alternatives below were considered and ruled out, the merge-conflict failure modes are now understood, and the gratis hosting unlocks community translation without ongoing cost.

The Libre plan carries one condition: attribution. Mention Weblate in the README (done — see translation section) and on bristlenose.app (outstanding). Content for both can be pulled verbatim from the Community menu of the Weblate project.

### How it works

1. Weblate connects to the GitHub repo, reads `bristlenose/locales/` (i18next JSON v4 format — [first-class support](https://docs.weblate.org/en/latest/formats/i18next.html))
2. Contributors get a URL like `hosted.weblate.org/projects/bristlenose/`
3. They see each English string with context, suggestions, and a text box — no JSON, no Git
4. Weblate commits translations to a branch and opens PRs
5. We review and merge

### What contributors see

- Source string (English)
- Localization comment (what the string is for, what variables mean)
- Screenshot or context description
- Glossary entries (Apple/Microsoft standard terms loaded as a Weblate glossary)
- Machine translation suggestions (DeepL, Google, etc.)
- Other translations of the same string in other projects

### Setup steps

1. Create project at `hosted.weblate.org` ✓
2. Add 8 components (one per namespace), file mask `bristlenose/locales/*/{ns}.json`, monolingual base `bristlenose/locales/en/{ns}.json` ✓
3. Upload Apple + QDA glossary (`bristlenose/locales/glossary.csv`) as Weblate glossary ✓
4. Add "Help translate Bristlenose" link to About panel + README + CONTRIBUTING ✓
5. CI validation (`scripts/check-locales.py`) runs on PRs touching locale files ✓
6. Japanese (ja) stub files created for community translation ✓
7. Translator guide: `TRANSLATING.md` ✓

**Implemented 24 Mar 2026.** Weblate submits translations as pull requests; all PRs require human review.

### Live configuration

**Project URL:** [hosted.weblate.org/projects/bristlenose/](https://hosted.weblate.org/projects/bristlenose/)

**Hosting:** Libre plan (160k strings, 0 EUR) — **approved 29 Apr 2026**. Attribution required (mention Weblate in README and on bristlenose.app); README already links Weblate from the translation section, website mention pending.

**Components (8):**

| Component | File format | File mask | Strings |
|-----------|------------|-----------|---------|
| common | JSON nested structure | `bristlenose/locales/*/common.json` | ~275 |
| settings | JSON nested structure | `bristlenose/locales/*/settings.json` | ~28 |
| enums | JSON nested structure | `bristlenose/locales/*/enums.json` | ~13 |
| cli | JSON nested structure | `bristlenose/locales/*/cli.json` | ~22 |
| pipeline | JSON nested structure | `bristlenose/locales/*/pipeline.json` | ~4 |
| server | JSON nested structure | `bristlenose/locales/*/server.json` | ~7 |
| doctor | JSON nested structure | `bristlenose/locales/*/doctor.json` | ~7 |
| desktop | JSON nested structure | `bristlenose/locales/*/desktop.json` | ~115 |

**VCS integration:**
- Version control system: GitHub pull request (Weblate forks and opens PRs)
- Repository branch: `main`
- Push branch: empty (Weblate manages its own fork)
- GitHub webhook: `https://hosted.weblate.org/hooks/github/` (push events only, no secret)

**Format settings:**
- JSON indentation: 2 spaces
- Monolingual base: `bristlenose/locales/en/{ns}.json` for each component
- Components share the same repo clone via `weblate://bristlenose/common`

**Glossary:** uploaded from `bristlenose/locales/glossary.csv` — Apple HIG terms + QDA domain terms (Codebook, Quotes, Sessions, etc.) across es/fr/de/ko/ja/cs.

**Translation instructions:** linked to `TRANSLATING.md` in project settings.

**Languages discovered:** en (source), es, fr, de, ko (100% translated), ja (0% — empty stubs, manually added as language since Weblate skips all-empty files).

**Gotchas learned during setup:**
- Weblate auto-discovers files from the repo but ignores locales where every value is an empty string (Japanese stubs). Must add the language manually via the + button on the component's Languages page
- The "Source code repository" field on the create-component form pre-fills with a label prefix (`Source code repository: https://...`) — this must be cleared to just the bare URL or git clone fails with "protocol not supported"
- JSON indentation defaults to 4 — must change to 2 to match our files, otherwise Weblate reformats every file on first commit
- Second+ components should use "From an existing component" tab and select `common` to share the repo clone

### Czech (`cs`) — community-initiated

**Language code, not country code.** The locale is ISO 639-1 `cs` (the Czech _language_),
**not** `cz` (the ISO 3166-1 country code for Czechia — what's on Praha number plates). The
`cz` git branch is a label only; every locale dir, `SUPPORTED_LOCALES` entry, `glossary.csv`
row, and language-picker tag uses `cs`. (Slovak, which split from Czech administratively in
1993, is the separate language code `sk`; `cs` is unambiguously Czech.)

Czech is the first locale Bristlenose didn't plan. A volunteer signed up on Weblate and
started a `cs` translation _before_ we'd added the language to the product — the first
_organic_ demand signal for a locale we've had, and evidence of at least one Czech-speaking
researcher in the wild. We treated it as a delight opportunity rather than a backlog item:
instead of handing the volunteer a blank slate, we machine-seeded a complete Czech baseline
across all eight namespaces (+ `preflight`), with proper Czech four-form CLDR plurals
(`one`/`few`/`many`/`other`), for them to react to and correct.

**Fill-empty-only invariant.** The MT seed is additive: for each English key it writes a
Czech value _only_ where `cs` is currently empty or missing — it never overwrites a
non-empty value, because that value may be a human contribution. The guarantee is structural
(file-level) and re-runnable. On Weblate's side, its database is authoritative for any string
translated in its UI, so on the next sync a human translation wins over our machine seed (the
conflict self-heals in the right direction: human > MT). Before the final Weblate pull,
trigger **Commit + Push** in Weblate so any not-yet-committed UI translations land in the repo
first; fill-empty then skips them.

#### Czech plurals — the pernickety one/few/many/other rule

Czech is the first locale Bristlenose ships that inflects nouns by count beyond a
singular/plural binary, and the wrong form is **immediately wrong-sounding** to a
native speaker. The same trap exists for every Slavic language we might add later
(Polish, Russian, Ukrainian, Slovak — each with its own boundary rules); the
mechanism described here is generic, the seeded values are Czech-specific.

**The four CLDR categories for Czech**, with the noun _rozhovor_ ("interview") as
the worked example. The boundary rules use CLDR's `i` (integer part) and `v` (number
of visible fraction digits):

| Category | Rule (CLDR) | Integer counts | Example string |
|----------|-------------|----------------|----------------|
| `one`   | `i = 1 ∧ v = 0`        | `1`         | `1 rozhovor` |
| `few`   | `i ∈ {2,3,4} ∧ v = 0`  | `2, 3, 4`   | `3 rozhovory` |
| `many`  | `v ≠ 0`                | _(none)_    | `1,5 rozhovoru` _(fractional)_ |
| `other` | everything else        | `0, 5, 6, …` | `7 rozhovorů` |

The single-letter ending changes are the whole point — _rozhovor_ → _rozhovory_
→ _rozhovoru_ → _rozhovorů_ is the **same word in four cases**, not four
different words. Machine translation routinely picks the wrong one (the genitive
plural `-ů` is the most common machine error in `few` contexts), which is why
every machine-seeded `_few` value needs native review.

**Why `many` is in the locale files but never actually rendered.** Bristlenose's
UI displays integer counts only — interview counts, hidden-quote counts, etc. —
so the `many` form (decimals) is never selected at runtime; `pluralCategory` for
Czech only ever returns `one` / `few` / `other`. We seed `_many` anyway because
(a) CLDR considers the four-form set canonical and Weblate / glossary tooling
expect it, (b) it documents the rule for anyone reading the locale file, and
(c) it's a zero-cost guard against a future Decimal-aware call site.

**The mechanism.** `I18n.pluralCategory(_ count: Int) -> String`
(`desktop/Bristlenose/Bristlenose/I18n.swift`) returns the CLDR category for the
active locale. Call sites resolve `<base>_<category>` and fall back to
`<base>_other` if the form is missing — so a half-translated locale renders
"plain plural" rather than the raw key. The two reference implementations are
`ProjectDiagnosticPopover.localisedOverflowText` and `ProjectRow.deltaText`; copy
one of them when you add a new pluralised desktop string. (Pattern reference:
§ Process philosophy, item 3 above.)

**Inventory of Czech four-form values, as of `bc72b7a` (cz branch, 8 Jun 2026) —
machine-seeded, awaiting native review.** Every entry below is a best-effort
Czech form generated mechanically and **may be wrong in a way that's invisible
to anyone who doesn't speak Czech**. A native-speaker pass is the gate, not
the seed.

| Key prefix (under `chrome.` or `pipeline.diagnostic.`) | English source | Seeded cs forms |
|--------|----------------|------------------|
| `interviewCount` | `{{count}} interview(s)` | `1 rozhovor` / `{{count}} rozhovory` / `{{count}} rozhovoru` / `{{count}} rozhovorů` |
| `unanalysedSubtitle` | `+{{count}} unanalysed` | `+1 neanalyzovaný` / `+{{count}} neanalyzované` / `+{{count}} neanalyzovaných` / `+{{count}} neanalyzovaných` |
| `missingSubtitle` | `{{count}} missing` | `1 chybí` / `{{count}} chybí` / `{{count}} chybí` / `{{count}} chybí` _(verb-final; invariant)_ |
| `overflow` (diagnostic) | `… and {{count}} more failures truncated` | `… a {{count}} další chyba skryta` / `… a {{count}} další chyby skryty` / `… a {{count}} další chyby skryto` / `… a {{count}} dalších chyb skryto` |

Note that `missingSubtitle` uses the verb `chybí` ("is/are missing") which doesn't
inflect for count, so all four forms are deliberately identical. `interviewCount`
and `unanalysedSubtitle` are the entries where a native reviewer will most likely
correct an ending; `overflow` involves a full sentence and is the most likely to
need wording revision beyond endings. The current cs overflow seed also translates
"truncated" as `skryta/skryty/skryto` (literally _hidden_), which is a small
semantic drift from the English — flag for the reviewer.

**For the native-speaker reviewer (Pavel and successors).** The forms above were
generated to satisfy CLDR's grammar shape, not to read naturally. Likely areas
to correct: (a) the `-ý` / `-é` / `-ých` adjective endings on
`neanalyzovaný / -é / -ých` (these agree with the noun's gender + case + number,
and the seed assumes a default that may not match how the UI reads — Bristlenose
displays these strings without an explicit noun, so the form choice is doing
double duty); (b) word order and the elided noun in `unanalysedSubtitle` —
you may want to make the noun explicit, e.g. _neanalyzovaných souborů_; (c) the
participle choice in `overflow` (`skryta` / `skryty` / `skryto`), and whether
_hidden_ is the right translation of _truncated_ in this UI. Edit in Weblate or
directly in `bristlenose/locales/cs/desktop.json` — chrome counts are top-level
`chrome.*` keys; overflow lives under `pipeline.diagnostic.*` in the same file.
**You don't need to touch `_many` unless you want to** — it's CLDR-canonical
shape, never rendered in our UI.

**For future Slavic locales (Polish, Russian, Ukrainian, Slovak).** The
mechanism extends — add a `case "pl":` (etc.) branch to `pluralCategory` with
that language's CLDR rules and seed the four-form set across all keys carrying
`_few`. The boundary rules differ (Polish has its own; Russian/Ukrainian distinguish
`many` from `other` for integers, unlike Czech). The Python test
`test_four_form_locales_carry_all_forms` and `test_chrome_count_four_form_locales_carry_all_forms`
already gate on presence of `_few` — so any new four-form locale auto-acquires
coverage without a test edit. The Swift `@Test` (`localisedOverflowText_czech_selectsFewForm`)
should be mirrored per language; the assertion shape is generic.

### Future locales (deferred)

Breadcrumbs so the analysis isn't re-derived. Neither is started.

**Portuguese (`pt-PT` + `pt-BR`) — light; a later-summer-weekend seed.** Romance, Latin
script (no script subtag), `one`/`other` plurals — same shape as `es`/`fr`/`de`, so MT-seed
quality is high and mechanical cost is low. Two locales though: lexical divergence
(`ecrã`/`utilizador` PT vs `tela`/`usuário` BR) → two native reviews eventually. `pt-BR`
(Brazil) is the larger market (reach); `pt-PT` is more completeness. Normal App Store
regions, providers reachable.

**Decided: two full locales, not `pt` base + `pt-BR` override.** Every controlled-vocabulary
exemplar ships two independent variants; none ships a neutral `pt` base with deltas. (1) **CLDR**
makes `pt-BR` the *default-content locale* for `pt` — bare `pt` has no data of its own and
resolves to Brazilian content, so a "neutral base" doesn't exist; "`pt` base + override" would
really be "`pt`(=BR) + `pt-PT` override" under a misleading name. (2) **Apple**: *"use `pt` …
for Portuguese as it is used in Brazil and `pt-PT` … as it is used in Portugal"* — no neutral
Portuguese; best practice is shipping both, and because both share the language code `pt`, a
half-populated shared locale can serve *pt-PT strings to a pt-BR user* instead of falling back to
English (QA1828). (3) **Microsoft** maintains two separate style guides + terminology sets
(`por-bra-StyleGuide.pdf` / `por-prt-StyleGuide.pdf`). (4) **Mozilla** runs `pt-BR` and `pt-PT`
as fully independent Pontoon teams — no `pt` team, no base+override. The Acordo Ortográfico (1990)
harmonised some *spelling* but the load-bearing UI divergence (`ficheiro`/`arquivo`,
`utilizador`/`usuário`, `ecrã`/`tela`) is *lexical*, untouched — and it lands on exactly the
high-frequency words in every menu. **Implications:** two locale artifacts + two native reviewers,
but production is still delta-driven (MT-seed `pt-BR`, fork the `pt-PT` deltas — ~1.2× not 2×);
bare-`pt` fallback resolves to `pt-BR` (answers the handoff's region-subtag audit Q6); never let
one variant borrow the other's strings at runtime — gate each to "reviewed" independently.

**Chinese — don't touch before autumn/winter 2026. The commercial unit is a Traditional
*pair*: `zh-Hant` (Taiwan) + `zh-Hant-HK` (Hong Kong).** Both ship in the App Store `.app`
and the CLI package (PyPI / Homebrew → `serve` + SPA), targeting the two ordinary
international storefronts (no mainland ICP / firewall / hosting friction; Claude/ChatGPT/Gemini
all resolve). Simplified (`zh-Hans`) is **parked** — see below. Decision: two Traditional
variants (resolved 29 Jun 2026, deep-research-backed — HK and Taiwan Traditional diverge in
high-frequency UI vocabulary and the l10n industry treats `zh-TW`/`zh-HK` as separate locales:
`軟體/軟件`, `網路/互聯網`, `解析度/解像度`, `論壇/討論區`, `筆記型電腦/手提電腦`).

- **`zh-Hant` (Traditional, Taiwan) — the primary, full-weight locale.** CLDR's default region
  for `zh-Hant` is TW, so bare `zh-Hant` = Taiwan content. This is the commercial bet and the
  heavyweight translation: MT-seed + a **Taiwan-native** reviewer (gating dependency). Recruit
  via **UXTW** (台灣使用者經驗設計協會), **HPX / 悠識 (UserXper)**, or the gated FB UR group
  **使用者經驗研究分析**. An auto-convert from Simplified gets glyphs but not idiom — must be a
  Taiwan native.
- **`zh-Hant-HK` (Traditional, Hong Kong) — a thin override fork off `zh-Hant`.** Machine-seed
  from the Taiwan locale with **OpenCC** (`t2hk` / phrase-aware configs auto-swap most regional
  vocabulary — no script conversion, both are Traditional), then an HK reviewer catches the
  rest via a curated TW→HK term table + one full read. **The London HK diaspora is the *right*
  reviewer here** (they produce HK idiom, which is exactly what `zh-Hant-HK` wants — the
  convenience/correctness conflict that ruled them out for Taiwan reverses for HK); backed by
  **UXHK** / **IxDF Hong Kong**. Cheaper than a Hant↔Hans fork (no one-to-many glyph
  ambiguity): the pair ≈ **1.25–1.3×** a single Traditional locale. **Accepted risk:** HK is
  English-fluent (Dovetail serves HK in English today) and may treat its localisation as a
  curiosity — done *because* it's a near-free delta, not because HK demands it.
- **Fallback policy — deliberately *unlike* the `pt` rule.** Allow `zh-Hant-HK` → `zh-Hant` →
  `zh` to fall through: a missing HK string resolving to the Taiwan one is acceptable because
  TW/HK Traditional are **mutually intelligible** (same script, vocab-only delta), far better
  than dropping to English. This is what makes `zh-Hant-HK` an override layer, not a full
  independent locale — the opposite of `pt-PT`/`pt-BR`, which must never cross-borrow because
  they read foreign to each other.
- **Simplified (`zh-Hans`) is parked, not killed.** No longer in the commercial critical path.
  Fork it later via OpenCC `t2s` off whichever Traditional variant is most mature, when a
  Singapore / Malaysia / diaspora reviewer appears (reachable e.g. via **Design Research SG**,
  English-operating — no mainland engagement). It carries the local-model product-fit story
  (Ollama runs DeepSeek/Qwen/GLM/Kimi for in-language analysis) and serves Singapore/diaspora
  + passive mainland GitHub-finders, but mainland stays **out of scope as a target** (no App
  Store, no ICP, no mainland build/mirror/reviewer).
- **First locales with *script + region* subtags.** `zh-Hant` / `zh-Hant-HK` force the flat
  two-letter registry (hand-duplicated across React `LOCALE_LABELS`, Swift `supportedLocales`,
  Python `_ALL_LOCALES`) to learn both a script (`Hant`) and a region (`HK`) subtag, plus
  matching `.lproj` names (`zh-Hant.lproj`, `zh-Hant-HK.lproj`) and App Store Connect
  localisations. More plumbing than a flat-locale copy-paste. Plurals are trivial
  (`other`-only, like `ja`/`ko`); CJK typography mostly rides existing `ja`/`ko` handling.
- **CLI terminal chrome is English-only in alpha**, so the localised Chinese experience appears
  via `bristlenose serve` + the SPA (shipped inside both the CLI package and the `.app`).

### Alternatives considered

| Platform | Why not |
|----------|---------|
| **Crowdin** | Proprietary SaaS. Free for OSS but requires 3+ month old project + OSI licence. Good in-context editing. Would work but not FOSS-aligned |
| **Transifex** | Free tier requires "no funding, revenue, or commercialisation model" — would disqualify us if Bristlenose ever has a paid tier |
| **Tolgee** | Best in-context editing (ALT+click). Newer, smaller community. Worth revisiting if we want that UX |
| **Pontoon** | Mozilla's tool. Primarily Fluent format, heavy to self-host |

## Testing: pseudo-localisation

### What it is

Replace every translated character with an accented equivalent and wrap in brackets: `"Settings"` → `"[Ṡëëttîîñgṡ]"`. Expand strings by 30–40% to simulate German/Finnish length. Any text on screen without brackets = a hardcoded string that was never extracted for translation.

Reference: [Google's canonical explanation](https://opensource.googleblog.com/2011/06/pseudolocalization-to-catch-i18n-errors.html) (2011, still definitive).

### Implementation

Add [`i18next-pseudo`](https://www.npmjs.com/package/i18next-pseudo) as a dev dependency. Register as an i18next postProcessor. Add a pseudo-locale (`qps`) selectable in the dev playground. Run it before every new language launch to catch missed strings.

### String length testing

German is typically 30% longer than English. Finnish even more. Japanese/Korean are typically shorter in character count but may need different font metrics. The pseudo-locale's 40% expansion catches overflow before real translations arrive.

## Process philosophy (from Mozilla, Shopify, and others)

Key lessons from [Mozilla's L10N best practices](https://mozilla-l10n.github.io/documentation/localization/dev_best_practices.html) and [Shopify's linguistics guide](https://shopify.engineering/internationalization-i18n-best-practices-front-end-developers):

1. **Every string gets a localization comment** — explain what variables mean, where the string appears, and any length constraints. Even if it seems obvious. Translators work in a spreadsheet-like UI without seeing the app.

2. **Same English word ≠ same translation key** — "Post" (noun: a blog post) and "Post" (verb: to submit) need different keys because they translate differently in most languages. If a word is ambiguous, split the key.

3. **Never concatenate fragments** — `"You have " + count + " items"` breaks word order in German, Japanese, Arabic. Always use full-sentence interpolation: `t("items.count", { count })` with i18next's plural rules.

   - **Desktop (Swift `I18n.swift`) uses CLDR plural categories — `_one` / `_few` / `_many` / `_other` snake_case suffix keys selected via `I18n.pluralCategory(_ count:)`.** React uses the same i18next suffix convention (CLDR auto-suffix). The Swift selector returns the category for the active locale — cs: one=1, few=2–4, other=0/5+; fr: 0,1=one else other; ja/ko: always other; en/es/de (and any unmapped locale): one=1 else other. Call sites resolve `<base>_<category>` with an `_other` fallback. Reference implementations: `ProjectDiagnosticPopover.localisedOverflowText` (diagnostic overflow text) and `ProjectRow.deltaText` (sidebar chrome counts).
     - **Historical note (closed).** Before 8 Jun 2026 the desktop count strings used a Swift `count == 1` ternary on camelCase `One` / `Other` keys (e.g. `chrome.interviewCountOne` / `chrome.interviewCountOther`, captured 15 May 2026 in `multi-project-folder-watcher`). That binary split rendered Czech counts 2–4 in the `Other` form — `"2 rozhovorů"` where Czech grammar wants the `few` form `"2 rozhovory"`. Finding 1 introduced `pluralCategory` for the diagnostic overflow (8 Jun 2026); Finding 14 (`bc72b7a`, cz branch) migrated the three remaining chrome prefixes (`interviewCount`, `unanalysedSubtitle`, `missingSubtitle`). There are now **no `*One` / `*Other` camelCase keys anywhere** in `bristlenose/locales/`. The earlier chrome guidance ("don't introduce `_one` / `_other` suffixes") is **superseded** — snake_case CLDR forms are the only correct path.
     - **Adding a new desktop count string:** seed `<base>_one` + `<base>_other` for en/es/fr/de (one+other), `<base>_other` only for ja/ko (single-form), and the full `<base>_one` / `_few` / `_many` / `_other` for cs (four-form — see the "Czech plurals" subsection above for what each form means). Route the Swift call site through `i18n.pluralCategory(count)` → `<base>_<category>` with `_other` fallback. The parametrised tests in `tests/test_pipeline_diagnostic_locale_keys.py` (chrome-count and overflow blocks — derive the four-form requirement from presence of `_few`) auto-extend to any new prefix that follows this shape; mirror the existing Swift `@Test` (`chromeInterviewCount_czech_selectsCldrForm` / `localisedOverflowText_czech_selectsFewForm`) for the cs end-to-end assertion.

4. **Respect grammatical gender** — "1 item selected" vs "1 photo selected" may need different adjective forms in French/German/Spanish. Use i18next's `context` feature when the noun changes the sentence.

5. **Don't hardcode punctuation** — French puts a space before `:` and `?`. Japanese uses full-width punctuation (`。` not `.`). Let the translation include its own punctuation.

6. **Descriptive string IDs** — `desktop.menu.file.exportReport` not `str_47`. The ID is documentation for the translator.

## Implementation plan

### Phase 1: UI chrome terminology
Add the 6 core terms to `common.json` for all 5 non-English locales.

Files: `bristlenose/locales/{de,fr,es,ja,ko}/common.json`.

### Phase 2: Sentiment translations
Populate the 4 missing locale files (ja, fr, de, ko) with the 7 sentiment tag translations. (Spanish done in v0.13.7.)

Files: `bristlenose/locales/{locale}/enums.json`.

### Phase 3: UXR codebook translation layer
- YAML stays English (single source of truth for IDs, definitions, `apply_when`, `not_this`)
- Add `bristlenose/locales/{locale}/codebook_uxr.json` mapping English tag name → translated display name + group name + subtitle
- Update codebook display components to use i18n lookup with English fallback
- Adding a new language = one JSON file per codebook

Key files: `bristlenose/server/codebook/__init__.py`, `bristlenose/server/codebook/uxr.yaml`, `frontend/src/islands/QuoteCard.tsx`, `frontend/src/components/TagInput.tsx`.

### Phase 4: Quality gate
- Machine-translate Phases 1–3 as draft
- Cross-check standard UI terms against applelocalization.com (mandatory)
- Create review checklist for native-speaking UX researchers per language
- Track review status per locale (reviewed/unreviewed flag)

### Phase 5: Weblate setup ✓
Complete. Project live at [hosted.weblate.org/projects/bristlenose/](https://hosted.weblate.org/projects/bristlenose/), Libre plan approved 29 Apr 2026, glossary uploaded, translator guide at `TRANSLATING.md`, README links it. See "Live configuration" section above for component breakdown and lessons from setup. **Outstanding:** Weblate attribution mention on bristlenose.app website (Libre plan condition).

### Phase 6: Pseudo-localisation QA
- Add `i18next-pseudo` to dev dependencies
- Add `qps` pseudo-locale to playground
- Run visual scan to catch remaining hardcoded strings
- Extract missed strings to locale files

## Progress

### Spanish (es) — machine-translated, v0.13.7 (16 Mar 2026)

All 102 existing i18n strings machine-translated across 8 files (3 frontend, 5 backend). Cross-checked against the terminology table above — "Citas", "Libro de códigos", "Sesiones", "Señales" all match the recommended terms.

**Review status:** awaiting native-speaker review (Lidia, Sevilla).

**Open questions for reviewer:**
- "Delight" → "Entusiasmo" or "Deleite"? Machine translation chose "Entusiasmo" (enthusiasm); "Deleite" is closer to the UX/design sense of delight. Both are valid — needs a native UXR practitioner's judgement
- "Libro de códigos" — ATLAS.ti's term, recommended by our research. Confirm it feels natural vs alternatives like "Manual de códigos"
- "Investigador/a" for Researcher — gender-inclusive slash form. Confirm this is the convention Lidia prefers (vs "Investigador(a)" or just "Investigador")

### Korean (ko) — machine-translated, v0.14.x (23 Mar 2026)

All 8 namespace files (common, settings, enums, cli, pipeline, server, doctor, desktop) machine-translated. First CJK locale. Cross-checked against the terminology table above — "인용문", "코드북", "세션", "시그널" all match the recommended terms. Apple Korean glossary cross-checked (see table below).

**Speech register:** formal 합쇼체 (-습니다/-ㅂ니다) for sentences, noun forms for buttons/actions. Matches Apple Korean and professional tool conventions.

**No `_short` keys needed.** All Korean tab labels are 2–5 syllable blocks — much shorter than their English equivalents.

**Apple Korean cross-check results:**

| English | Ours | Apple KO | Verdict |
|---------|------|----------|---------|
| Save | 저장 | 저장 | ✓ |
| Cancel | 취소 | 취소 | ✓ |
| Close | 닫기 | 닫기 | ✓ |
| Copy | 복사 | 복사 | ✓ |
| Delete | 삭제 | 삭제 (action) | ✓ action sense correct |
| Undo | 실행 취소 | 실행 취소 | ✓ |
| Redo | 실행 복귀 | 실행 복귀 | ✓ |
| Search/Find | 검색/찾기 | 검색/찾기 | ✓ |
| Find Next | 다음 찾기 | 다음 찾기 (menu label) | ✓ page says "다시 찾기" (informal) |
| Find Previous | 이전 찾기 | 이전 찾기 | ✓ |
| Print | 프린트 | 프린트 | ✓ |
| Fullscreen | 전체 화면 | 전체 화면 | ✓ |
| Settings | 설정 | 설정 (post-Ventura) | ✓ |
| Export | 내보내기 | 내보내기 | ✓ |
| Zoom In | 확대 | 확대 | ✓ |
| Zoom Out | 축소 | 축소 | ✓ |
| Accept | 승인 | 승인 | ✓ |
| Apply | 적용 | 적용 | ✓ |
| Reset | 재설정 | 재설정 | ✓ |

**No changes needed.** All translations match Apple's canonical Korean terms.

**Review status:** awaiting native-speaker review (no reviewer identified yet — need Korean UXR practitioner, ideally in Seoul).

**Open questions for reviewer:**
- "Quotes" → 인용문 or 발언? 인용문 (quotation text) is more academic; 발언 (utterance) is closer to how UXR practitioners talk about participant words. Which feels more natural in a research tool?
- "Delight" → 기쁨 or 감동? 기쁨 is general joy/delight; 감동 is being moved/touched (deeper resonance). In UX sentiment tagging, which better captures "product delight"?
- "Confidence" → 확신 or 자신감? 확신 is conviction about something external; 자신감 is self-confidence. Which is more appropriate for a participant expressing confidence in a product?
- "Frustration" → 좌절감 or 답답함? 좌절감 is defeat/setback (strong); 답답함 is feeling stifled/stuck (more UX-appropriate?). Which maps better to user-research friction?
- Speech register: confirm formal 합쇼체 (-습니다) is appropriate, or whether polite 해요체 (-해요) would feel more natural. Modern Korean tech companies (Toss, Kakao) sometimes use 해요체 for a warmer tone

**CJK-specific CSS tasks (separate from translation):**
- Add `word-break: keep-all` for Korean text — browsers break mid-syllable-block without it
- Audit `max-width` constraints against full-width character widths (56px analysis cells will truncate)
- Test line-height with Korean glyphs (may need adjustment from Latin 1.3–1.5)

### Unified architecture — v0.14.x (23 Mar 2026)

Single source of truth implemented. `frontend/src/locales/` deleted — all imports now point to `bristlenose/locales/` via Vite alias. Desktop `I18n.swift` reads the same JSON files. Desktop `desktop.json` namespace added (en + es) with ~75 native-only strings (menu bar, toolbar, chrome). Bridge locale sync with startup flash prevention (URL query param). Web language picker hidden in embedded mode.

**TODO:** cross-check all Spanish UI terms against applelocalization.com before next release.

### Translation quality gotchas — lessons from the v0.14.1 review

Seven patterns that machine translation gets wrong. Use this list as a pre-flight checklist before shipping a new language.

1. **False cognates in semantic fields.** "길이" (length) was used for time duration — it literally means physical length/distance. Machine translation picked the most common English→Korean mapping without distinguishing temporal from spatial meaning. *Fix:* flag column headers and data labels for domain-specific review. Maintain a glossary of measurement terms per language (time, distance, count, size)

2. **Keyboard hint strings need grammatical context.** English "for Help" is a sentence fragment that reads naturally after `<kbd>?</kbd>`. Korean "도움말" (just "help" as a noun) drops the grammatical connector, producing "? Help" instead of "? for Help". *Fix:* annotate locale keys with rendering context — e.g. `// rendered as: <kbd>?</kbd> {this}`. Translators can't produce correct fragments without knowing the surrounding UI

3. **Identical translations for different concepts are sometimes correct.** French `buttons.cancel` and `buttons.undo` are both "Annuler". This looks like an error but is standard macOS French — Apple's Edit → Undo is "Annuler". *Fix:* before "fixing" apparent duplicates, cross-check against the platform's native localisation (applelocalization.com). Document known-correct duplicates in the review notes

4. **Gender-inclusive language is a style choice, not a bug.** German "Teilnehmer" vs "Teilnehmer:innen" — Apple/Microsoft German localisations consistently use the masculine generic for data labels. *Fix:* establish a gendering policy per language up front and document it in the review template. Don't let it be ad-hoc per string

5. **Column headers need brevity constraints.** Korean "소요 시간" (3 syllable blocks) is wider than "길이" (2). Column headers have strict width budgets. *Fix:* add a max character count annotation to column header keys. Use `_short` variants (already used for `codebookShort`) for languages where translations overflow

6. **Machine translation doesn't know platform conventions.** Multiple issues stem from machine translation ignoring macOS/Apple localisation conventions — the "Annuler" duplicate, "Teilnehmer" gendering, "Réglages" vs "Préférences". *Fix:* enforce the Apple glossary cross-check as a gate — no language ships without a completed review doc in `docs/locales/`

7. **Duplicate keys across namespaces drift independently.** `sessions.colDuration` and `dashboard.colDuration` both had "길이" — fixing one without the other creates inconsistency. *Fix:* grep for all occurrences of a concept before fixing. Consider extracting shared column labels into a `columns` sub-namespace

8. **CLDR plural categories ≠ "missing translations".** Korean and Japanese have a single plural category (`other`) per CLDR. i18next emits `_one` / `_other` variants from English source, so a diff against EN reports the `_one` keys as missing for ko/ja — but those keys are not translatable strings in those languages. As of 30 Apr 2026 this accounts for ~3% of the apparent ko gap on Weblate (19 of 26 "missing" keys are `_one` plurals; the remaining 7 are deliberate identicals — brand name `bristlenose`, acronym `LLM`, `ID`, and pure-placeholder strings like `"{label}"`). *Fix:* if Weblate's component config exposes plural-rule overrides, set ko/ja to skip `_one` form-counting. Otherwise, document the floor and stop chasing it

## Frontend extraction lessons (24 Mar 2026)

Lessons from wiring ~200 hardcoded strings across ~35 React components to i18next.

### What went well

- **Test-setup-first**: adding `import "./i18n"` to `test-setup.ts` meant `t("nav.project")` returned `"Project"` in all tests — zero test rewrites needed for the basic wiring
- **Batched approach**: 11 batches from outside-in (NavBar/Header/Footer shell first, then content, then modals, then accessibility) meant intermediate states were never jarring
- **`Intl.DateTimeFormat` migration**: replacing hardcoded `MONTH_ABBR`/`DAY_ABBR` arrays with `Intl.DateTimeFormat(locale)` was cleaner than adding 60 month/day keys to locale files
- **Sentiment translation in Badge**: a single `t("enums:sentiment.${text}", { defaultValue: text })` in `Badge.tsx` translates all sentiment labels everywhere — quotes, codebook, analysis, dashboard

### What we got wrong

1. **Incomplete string audit upfront** — missed SettingsModal (separate component from SettingsPanel), CodebookSidebar headings, AnalysisSidebar headings, SidebarLayout "Contents" title, "Browse codebooks" button. Each required a QA cycle to discover. A `grep -r '"[A-Z][a-z]' --include='*.tsx' frontend/src/` upfront would have caught them

2. **`useMemo([t])` doesn't work** — the `t` function reference doesn't change on locale switch. Arrays built with `useMemo(() => [...], [t])` go stale. Fix: `[t, i18n.language]` as dependency, or skip `useMemo` for small arrays

3. **Terminology inconsistency in machine-translated keys** — agent-generated translations used "codebook" as an English loanword in es/fr browse/import/restore keys while the heading used the localised term ("Libro de códigos" / "Grille de codage"). The terminology table in this doc existed but wasn't enforced during generation

4. **`en` vs `en-GB` date order** — `Intl.DateTimeFormat("en")` gives US order ("Feb 12"), breaking tests that expected British order ("12 Feb"). Default is now `en-GB`

5. **Capitalization in sentiment enums** — `enums.json` has `"frustration": "Frustration"` (capitalised). Tests that expected lowercase API values (`"frustration"`) broke when Badge started translating

### Patterns established

| Pattern | When to use | Example |
|---------|-------------|---------|
| `useTranslation()` hook | Inside React component functions | NavBar, Header, Footer |
| `import i18n` + `i18n.t()` | Stores, announce calls, non-component code | QuotesContext, AppLayout |
| Inline array (no memo) | 2–5 items with translated labels | ViewSwitcher options |
| `useMemo([t, i18n.language])` | 8+ items passed as props | HelpModal nav items |
| `enums` namespace lookup | Sentiment/role labels from API data | Badge, CodebookPanel |
| `colour_set === "sentiment"` | Identifying built-in sentiment group | CodebookPanel group translation |
| `name === "Uncategorised"` | Identifying default codebook group | CodebookPanel group translation |
| `Intl.DateTimeFormat(locale)` | Date/time formatting | format.ts |
| `toLocaleString(i18n.language)` | Number formatting | Dashboard stat cards |

### Process for future extraction passes

1. Grep all `.tsx` for hardcoded English strings — build complete inventory
2. Cross-reference inventory against locale file keys — identify gaps
3. Define terminology glossary upfront (this doc's table) — enforce during translation
4. Add `import "./i18n"` to test-setup if not already present
5. Wire components in outside-in order (shell → content → modals → accessibility)
6. Add keys to ALL 5 locale files in the same edit — never leave gaps
7. Run `npm test && npm run build` after each batch
8. Review agent-generated translations against terminology table before committing
9. QA with language switching in full browser — preview tools don't work for Bristlenose

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

## i18n Implementation Gotchas (from CLAUDE.md)

Reference material moved from root `CLAUDE.md` to reduce CLAUDE.md bloat. Core i18n rules still live there; these are the detail-level gotchas.

- **Toolbar `_short` keys** — `common.nav.codebookShort` exists for languages where the full label overflows the segmented control (es: "Códigos" instead of "Libro de códigos"). `Tab.localizedLabel()` checks `_short` first
- **Apple glossary cross-check is mandatory** before shipping a new language — use [applelocalization.com](https://applelocalization.com/) or the macOS keyboard shortcuts page in the target locale. See Spanish cross-check results elsewhere in this doc for the process
- **`useMemo` deps for translated arrays** — `t` function identity doesn't change on locale switch. Use `[t, i18n.language]` as dependency, or skip `useMemo` entirely for small arrays (2–5 items). See `ViewSwitcher.tsx` (inline) vs `HelpModal.tsx` (useMemo with language dep)
- **`i18n/index.ts` initialises test-setup** — `frontend/src/test-setup.ts` imports `"./i18n"` so all tests get English translations by default. `t("nav.project")` returns `"Project"` in tests — no test rewrites needed for i18n wiring
- **Sentiment tag translation in Badge** — `Badge.tsx` looks up `enums:sentiment.${text}` when `sentiment` prop is truthy. This translates API-returned lowercase sentiment names ("frustration") to locale-correct labels ("Frustration" / "Verwirrung"). Tests must expect capitalised forms
- **Built-in codebook groups translate client-side** — sentiment group (`colour_set === "sentiment"`) and uncategorised group (`name === "Uncategorised"`) have their names/subtitles translated in `CodebookPanel.tsx` using locale keys. Other codebook names are user data and stay untranslated
- **`format.ts` uses `Intl.DateTimeFormat`** — `formatFinderDate` and `formatCompactDate` accept an optional `locale` param. Callers pass `i18n.language`. Internally, any `en*` locale (including bare `"en"` from i18next and `"en-US"` from jsdom in tests) is mapped to `"en-GB"` to preserve day-month order ("12 Feb" not "Feb 12"). Non-English locales pass through unchanged. `formatFinderDate` uses `Intl.RelativeTimeFormat` for "today"/"yesterday"
- **`<html lang>` tracking** — `i18n.on("languageChanged")` in `i18n/index.ts` sets `document.documentElement.lang`. Required for screen reader pronunciation
- **Korean has no plural forms** — only `_other` keys needed in locale files (no `_one`). i18next CLDR rules handle this automatically
- **Data-level vs chrome-level translation** — UI chrome (buttons, headings, labels) translates via `t()`. API data (codebook names, quote text, section labels) stays in the original language. Exceptions: sentiment group name/subtitle and uncategorised group are server constants that get client-side translation
- **German typographic quotes break JSON** — `„"` (U+201E / U+201C) look like JSON string delimiters to parsers. Escape as `\u201e` / `\u201c` in locale JSON files. Caught in `de/desktop.json` during platform text fork work
- **Tests that mock `../utils/platform` must include `isDesktop`** — `HelpModal.test.tsx` mocked only `isMac`, which broke when `ContributingSection` started importing `dt()` (which imports `isDesktop`). Always mock `{ isMac, isDesktop, _resetPlatformCache }` together
