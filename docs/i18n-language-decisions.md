# Per-language localisation decisions

The durable record of *what was decided* for each language — register, plural rules,
fallback, reviewer ownership, and the agreed taxonomy — so that anyone adding a new UI
surface can honour those decisions instead of re-deriving them.

**Companions** (don't duplicate them here):
- `docs/design-i18n.md` — i18n *mechanics* and implementation gotchas.
- `docs/adding-a-language.md` — the *how-to* for enrolling a new locale (the 10 registration sites).
- `bristlenose/locales/glossary.csv` — the **single source of truth** for agreed terminology. This
  doc summarises and explains it; the CSV is authoritative and is what Weblate shows translators.
- [i18n-glossary-proposals.md](i18n-glossary-proposals.md) — **proposed** glossary rows for the
  currently-unanchored terms (Participant/Speaker/Tags/Theme/Friction) + drift normalizations, with
  cited research and per-language native-reviewer questions. Pending native steer; nothing applied.

Strategic/commercial rationale (market framing, reviewer identities) lives in private
memory, not here — this doc is the shareable engineering + linguistic record.

---

## Using this when you add UI surface

1. **Every new `t()` key ships in all locale files** (en, es, fr, de, ko, ja, cs, it,
   pt-BR, pt-PT, zh-Hant, and zh-Hant-HK *only if* the term diverges for HK — see below).
2. **If the string contains a taxonomy term** (Quote, Session, Codebook, Code, Signal,
   Tag, Theme, Participant, Speaker, Friction, sentiment names…), look it up in
   `glossary.csv` and use the agreed target. Do not invent a synonym — synonym drift is
   the most common defect this project has (see Audit log).
3. **Respect each locale's register** (table below) — formal vs informal address,
   imperative vs infinitive for commands.
4. **Sentiment/enum display names are authoritative.** The chip label in `enums.json` is
   what the user sees and filters by; any explanatory prose (`help.*Body`) must use the
   *same* word, not a synonym.
5. **Don't translate data, brands, or format tokens.** Brand/product names (Bristlenose,
   Miro, Claude, ChatGPT, Azure, Gemini, Ollama), format tokens (CSV, HTML, JSON, PII),
   and interpolation tokens (`{{count}}`, `{name}`, `%@`, `%d`) pass through verbatim.

---

## Locale roster & architecture

`en` is the reference. Twelve target locales:

| Code | Language | CLDR plural categories | Fallback | Notes |
|------|----------|------------------------|----------|-------|
| `cs` | Czech | one / few / many / other | en | Volunteer-originated ("gold standard" demand signal) |
| `de` | German | one / other | en | Formal *Sie*; typographic-quote („…") JSON-escaping gotcha |
| `es` | Spanish | one / many / other | en | Informal *tú*; Apple-HIG (Ajustes, Citas) |
| `fr` | French | one / many / other | en | Apple-HIG imperative |
| `it` | Italian | one / many / other | en | Apple-HIG imperative (Salva ≠ Salvare); formal IA register; native reviewer in loop |
| `ja` | Japanese | other only | en | `発言` not `引用` for Quotes; most complete glossary; native review pending |
| `ko` | Korean | other only | en | Native review pending; Korean-plural gotcha (design-i18n.md) |
| `pt-BR` | Portuguese (Brazil) | one / many / other | en | **No cross-borrow** with pt-PT |
| `pt-PT` | Portuguese (Portugal) | one / many / other | en | **No cross-borrow** with pt-BR; *Acerca* not *Sobre* |
| `zh-Hant` | Chinese Traditional (Taiwan) | other only | en | Primary Chinese locale; Taiwan-native reviewer **not yet secured** |
| `zh-Hant-HK` | Chinese Traditional (Hong Kong) | other only | **zh-Hant** | **Thin override fork** — see below |

**`zh-Hant-HK` is a deliberate thin override, not a full locale.** It overrides only the
keys whose vocabulary genuinely diverges between Hong Kong and Taiwan Traditional Chinese
(`軟件`/`網絡`/`質素`/`手提電腦`/`網際網絡` vs TW `軟體`/`網路`/`品質`/`筆記型電腦`) and **falls back to
`zh-Hant`** for everything else — the two are mutually intelligible. This is *unlike* the
pt-PT/pt-BR pair, which deliberately do **not** cross-borrow. So a low key count for HK is
correct by design; the test is override *coverage* (does it catch every divergent term?),
not completeness.

**Swift plural fall-through:** `I18n.swift`'s `pluralCategory` defaults to `one`/`other`
when a language isn't handled explicitly — correct for it/es/de, and ja/ko/zh resolve to
`other`. Check CLDR before assuming for any new language.

---

## Cross-cutting conventions

- **`glossary.csv` is the taxonomy SSOT.** Where the *code* and the *glossary* disagree,
  one of them is wrong — resolve it deliberately (fix the value, or consciously update the
  glossary row), never leave them contradicting. Example caught in the 30 Jun audit:
  zh-Hant glossary says `Codebook→代碼簿` but the code shipped `編碼簿`.
- **Drift clusters on *un-anchored* terms.** `ja` is the only locale whose glossary covers
  Tags/Theme/Participant/Speaker/Friction, and it's the only locale that *didn't* split
  those terms. ko's `참여자`/`참가자` (participant) and `화자`/`발화자` (speaker) splits exist
  precisely because there's no glossary row to anchor them. **Bringing every locale's
  glossary up to ja-level coverage is the highest-leverage way to prevent future drift.**
- **`_comment_` markers = deliberate English.** A `_comment_<key>` sibling holding
  "…keep English pending native review" (present in ja/ko/zh-Hant, e.g. the LLM
  `temperatureLabel`) means the adjacent English value is *intentional*, not a leak. Use
  the same convention if you defer a translation.
- **`preflight.json` is English-only in alpha.** The Python CLI preflight surface
  (`bristlenose/locales/preflight.json`) has no CLDR-plural support yet and is English-only
  for alpha; every locale's `preflight.json` is a byte-identical mirror of `en`. **Decision
  owed:** add a `_comment_` marker to each so audits stop re-flagging it — *unless* these
  strings surface in the desktop/GUI first-run flow, in which case they need translating
  (only de's reviewer judged this a genuine GUI-facing gap).

---

## Register & reviewer ownership

| Locale | Address register | Command form | Native reviewer status |
|--------|------------------|--------------|------------------------|
| cs | — | Apple-HIG | none yet (volunteer-originated) |
| de | formal *Sie* | Apple-HIG | none named |
| es | informal *tú* | Apple-HIG | none named |
| fr | — | Apple-HIG imperative | none named |
| it | — | imperative (Salva, not Salvare) | **in loop** — Italian, formal IA register |
| ja | — | Apple-JA imperative | **pending** |
| ko | — | Apple-KO; prefer Apple's standard menu strings | **pending** |
| pt-BR | — | infinitive for menus | TBD (Brazil) |
| pt-PT | — | infinitive for menus | European-PT channel |
| zh-Hant | — | Apple-TW (輸出/輸入, 重設) | **pending — blocks shipping to primary market** |
| zh-Hant-HK | — | inherits zh-Hant | HK-diaspora (London) |

Register is a *per-locale* decision: keep address and command form consistent across **all**
surfaces of one locale (web report, desktop menus, settings, CLI). The most common slip is
the desktop/native surface diverging from the web surface for the same concept.

---

## Per-language notes

- **cs** — High quality. Watch Quotes `citát` (glossary) vs stray `citace`. CLDR
  few/many forms are correctly present (don't "fix" them to match en's one/other).
- **de** — Formal *Sie* throughout; a few desktop/settings strings slip to *du*. Sessions
  is `Interview(s)` per glossary (not `Sitzung`). Typographic quotes must be JSON-escaped.
- **es** — Informal *tú* throughout; the AI-consent modal is the known slip to *usted*.
  `Pipeline` should not be literalised to `Tubería`.
- **fr** — Apple-HIG imperative. Quotes = `Verbatim` (QDA term, invariant plural: *les
  verbatim*), not `citation`. Sessions = `Entretien(s)`, not the borrowed `session`.
- **it** — Apple-HIG imperative buttons (a reviewer will immediately clock `Salvare` where
  `Salva` belongs). Formal IA register for body text. Reconcile cross-surface Miro
  `board`/`bacheca` and the Star action `stella`/`contrassegna` to one term each.
- **ja** — Quotes is `発言` (utterance), explicitly **not** `引用`; the glossary enforces
  this. Most complete glossary (Tags/Theme/Participant/Speaker/Friction all anchored) —
  use it as the template for the other locales.
- **ko** — Signals = `시그널` (not `신호`), Accept = `승인` (not `수락`). Prefer Apple's
  standard macOS Korean menu strings (e.g. `다시 실행` for Redo). Participant/Speaker are
  **not** yet in the glossary — anchor them to stop the `참여자`/`참가자`, `화자`/`발화자` drift.
- **pt-BR** — No cross-borrow from pt-PT. `framework` rendering (loanword vs `Estrutura`)
  needs a native call; record it in the glossary once chosen.
- **pt-PT** — No cross-borrow from pt-BR. `Acerca` (not the BR `Sobre`) for About.
  PII-redaction has drifted to three verbs (remoção/redação/ocultação) — settle on one.
- **zh-Hant** — Taiwan Traditional, the primary Chinese market. QDA taxonomy needs a
  Taiwan-native ratification pass: Codebook `代碼簿` vs shipped `編碼簿`; the `代碼`/`編碼`
  code-vs-codes collision; Sessions `工作階段` vs `場次`; Export `輸出` (Apple-TW) vs `匯出`.
- **zh-Hant-HK** — Thin override; keep it to genuinely HK-divergent vocabulary. Add HK
  rows to `glossary.csv` (`質素`/`網絡`/`軟件`/`手提電腦`/`網際網絡`) so Weblate re-translation
  of the override surfaces can't drift back toward TW forms.

---

## Settled core taxonomy (from `glossary.csv`)

The load-bearing terms. Blank = no glossary row yet (anchor these to prevent drift).

| Term | cs | de | es | fr | it | ja | ko | pt-BR | pt-PT | zh-Hant |
|------|----|----|----|----|----|----|----|-------|-------|---------|
| Codebook | Kniha kódů | Codebuch | Libro de códigos | Grille de codage | Libro dei codici | コードブック | 코드북 | Livro de códigos | Livro de códigos | 代碼簿 |
| Codes | Kódy | Kodes | Códigos | Codes | Codici | コード | 코드 | Códigos | Códigos | 代碼 |
| Quotes | Citáty | Zitate | Citas | Verbatim | Citazioni | 発言 | 인용문 | Citações | Citações | 引述 |
| Sessions | Sezení | Interviews | Sesiones | Entretiens | Sessioni | セッション | 세션 | Sessões | Sessões | 工作階段 |
| Signals | Signály | Signale | Señales | Signaux | Segnali | シグナル | 시그널 | Sinais | Sinais | 訊號 |
| Tags | — | — | — | — | — | タグ | — | — | — | — |
| Theme | — | — | — | — | — | テーマ | — | — | — | — |
| Participant | — | — | — | — | — | 参加者 | — | — | — | — |
| Speaker | — | — | — | — | — | 話者 | — | — | — | — |
| Friction | — | — | — | — | — | フリクション | — | — | — | — |

---

## Audit log

- **2026-06-30** — First full multi-locale quality audit (12 locales, fanned out one agent
  per locale + synthesis). Structural parity is clean (the only real gaps:
  `desktop:menu.view.moveFocusToProjects` absent in 6 pre-wave locales;
  `server:statusPage.*` absent in it + zh-Hant; `cs` absent from the `LocaleStore.test.ts`
  mock). Quality findings clustered on **synonym drift** of un-anchored or
  cross-surface-inconsistent taxonomy terms (Quotes, Sessions, framework, PII-redaction)
  and a handful of register slips. One genuine typo: ko `왔곡` → `왜곡`
  (`common.json` quoteEthicsBody). zh-Hant QDA taxonomy needs native ratification before
  it ships to the primary market. Full findings: this session's transcript.
