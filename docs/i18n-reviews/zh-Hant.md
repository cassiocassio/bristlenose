# Bristlenose — Traditional Chinese (Taiwan) wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points, the lot. I'd value your steer on a handful of Traditional Chinese (Taiwan) terms before they're locked in. Should take five minutes.

## Where I'd really value your steer

### Code / Codebook (編碼 / 編碼簿 vs 代碼 / 代碼簿)  ·  genuine toss-up — measured 20 Sep 2026
- **What we use now:** the app everywhere says 編碼 (code) and 編碼簿 (codebook), and keeps 代碼 for identifiers (參與者代碼 p1, p2; exit codes).
- **Also in play:** the tools say otherwise. MAXQDA's own Traditional-Chinese guide uses 代碼 for a code-as-noun — 96 times, e.g. 「代碼系統或代碼樹是指以等級方式排列的代碼和子代碼的整體」 — and 編碼 only for the activity; NVivo's official Chinese tutorial does the same (預先創建代碼, 整理代碼); a 2021 台灣教育研究期刊 paper writes NVivo 代碼簿. On the other side, 國家教育研究院 renders codebook as 編碼簿, Academia Sinica's SRDA uses 過錄編碼簿 (the survey-statistics register), and some Taiwanese practitioner writing uses 編碼 for both senses.
- **The nuance:** 編碼 is unambiguously the coding-*activity* everywhere; the question is only the *noun*. 代碼 is what a researcher who learned on MAXQDA or NVivo has read on screen; 編碼 is what the academic vocabularies write. My earlier note that 代碼 "reads as an ID" was wrong for QDA prose — MAXQDA zh-TW uses it for codes throughout.
- **My hunch:** none — this one is yours. Keeping 編碼/編碼簿 costs nothing today; switching to 代碼/代碼簿 would change ~50 strings to match the tools.
- **You:** On a codebook lens, which pair do you expect — 代碼/代碼簿 (the MAXQDA/NVivo register) or 編碼/編碼簿 (the NAER/SRDA register)? And does 代碼簿 read as "the set of codes a researcher builds", or as a lookup table?

### Session (場次)  ·  clear-cut, just confirm
- **What we use now:** 場次 for one recorded interview sitting (the app uses it throughout the report).
- **Also in play:** two stray desktop/settings strings and our internal records say 工作階段; we'd bring those into line with 場次.
- **The nuance:** 工作階段 is the computing "session" calque (login / software session); 場次 reads as "一場訪談" — the research sitting.
- **My hunch:** 場次 everywhere; 工作階段 sounds like a server session for an interview tool.
- **You:** Does 場次 read right as "one interview session" — and are you happy we keep 訪談 as the separate word for Interview?

### Redaction / PII (編修 vs 遮蔽)  ·  genuine toss-up
- **What we use now:** split — web says PII 編修, desktop/settings say 遮蔽.
- **Also in play:** 去識別化 — the formal PDPA / data-governance term.
- **The nuance:** 編修 reads like copy-editing, which undersells a privacy feature; 遮蔽 ("mask/occlude") is closer to "redact"; 去識別化 is the legal register.
- **My hunch:** converge on 遮蔽 for the in-product action — accurate without being heavy.
- **You:** Is 遮蔽 the right everyday word for the act, with 去識別化 held back for formal/help copy — or would you reach for 去識別化 even in the UI?

### Star (標示 vs 標星)  ·  genuine toss-up
- **What we use now:** split — web says 標示, desktop says 標星.
- **Also in play:** 精選 ("featured") exists nearby but is a separate concept — leave it.
- **The nuance:** 標示 is generic "mark" and risks colliding with the tagging verb 標記; 標星 names the star outright and disambiguates.
- **My hunch:** converge on 標星 — the minority form is actually the clearer one here.
- **You:** For the action of starring a quote, does 標星 read naturally, or is it a touch literal for your ear?

### Speaker (發言者 vs 說話者)  ·  genuine toss-up
- **What we use now:** split — web/CLI say 發言者, desktop/settings say 說話者.
- **Also in play:** both are fine; we just want one across surfaces.
- **The nuance:** 發言者 leans formal / meeting-minutes; 說話者 leans linguistics / everyday (and is what Apple zh-TW dictation uses).
- **My hunch:** lean 發言者 for a transcript column header, but genuinely undecided.
- **You:** As the speaker column / role label in a transcript, which reads more natural — 發言者 or 說話者?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → 參與者** — broad enough to cover diary studies and focus groups, not only interviews; matches our role enum. (If you'd rather 受訪者 because we're interview-centric, say so.)
- **Tag → 標籤** — matches Apple's current macOS Finder term.
- **Theme → 主題** — the 主題分析 / Braun & Clarke term.
- **Friction → 阻力** — only ever an inline word inside the Frustration definition (困難、惱怒、阻力), never a label; flag if 摩擦 reads more natural in prose.
- **Framework → 架構** — the conceptual-structure sense for a coding framework; desktop menus should match this.

## Anything I've got wrong?

If any of these feels off, or a concept reads awkwardly in Traditional Chinese that I haven't even flagged, please call it — your ear wins over ours on every one of these.


---

# Round three — the Signals lens (21 Sep 2026)

Bristlenose turns a folder of user-interview recordings into a browsable report
— quotes, themes, sentiment. One of its five lenses was called **Analysis** and
is now called **Signals**, and that rename left five sentences describing the
old name in every language but English. They are fixed, and **everything below
is a first draft I wrote, not a translation anyone has checked.**

Two of the five are worth knowing the history of, because the English moved
twice in one day:

- **The definition came back.** Before the rename the sentence read *"the
  analysis page surfaces signals — statistically notable concentrations of
  sentiment within report sections"*, and that dash was the only place the
  product said **what a signal is**. The rename dropped it, so the next
  sentence talked about *strong and moderate signals* without the term ever
  being introduced. The English is now definition-first: *"Signals are
  statistically notable concentrations of sentiment within report sections."*
- **A pronoun was pointing at the wrong noun.** The empty state said *"apply
  codebook tags to generate **them**"* — and in thirteen languages the nearest
  candidate for *them* was **the tags**, which invites *apply tags to generate
  tags*. Your language was one of the five where the pronoun form matched the
  tags noun *exactly*, so the wrong reading was the easier one. It now names
  the noun.

Where your language's own earlier wording already carried the definition, I
reused it verbatim rather than re-translating — so the clause in the middle of
those sentences is the one a predecessor already wrote. The copula and the
subject at the front are mine, and they are what I would most like checked.

## The five new strings

```
正在載入訊號…
尚無訊號。請執行管線或套用編碼簿標籤以產生訊號。
標籤訊號錯誤：{{error}}
訊號是報告區段中統計上值得注意的情緒集中現象。強烈與中等的訊號會凸顯參與者經驗集中之處。
訊號是報告區段中統計上值得注意的情緒或編碼簿標籤集中現象。共有兩種訊號卡。
```

## Where I'd value your steer

### 「訊號是 …」  ·  the copula is mine
- **What we use now:** 「訊號是報告區段中統計上值得注意的情緒集中現象。」
- **The nuance:** defining the term under a heading that just says **訊號**. The
  previous wording was 「分析頁面會呈現訊號——…」, a sentence about the page, and
  the double dash went with it.
- **You:** does it read as a definition, or would you prefer 「訊號指的是…」?

### 訊號 vs 信號  ·  the live question, and it is measurable
- **What we use now:** **訊號** throughout, which the glossary anchors.
- **What Apple ships:** its single *Signal* string is **信號** in `zh_TW` and
  **訊號** in `zh_HK` — so the platform's Taiwan word is the one we do *not*
  use.
- **The nuance:** one string is not a convention, and 訊號 is common Taiwan usage
  (手機訊號). But this is our own coined product term, so if a Taiwanese
  researcher would read 訊號 as *reception bars* rather than as a finding, that
  matters.
- **You:** 訊號 or 信號 for a feature name?

### 「標籤訊號錯誤：」  ·  measured
- Fullwidth **：** with no following space, which is what Apple's zh-Hant ships
  (239 fullwidth against 0 halfwidth). Settled, not open — flagging so you know
  it was measured rather than guessed.

### 編碼簿 vs 代碼簿  ·  older and bigger than this round
- The files say **編碼簿** and the glossary was corrected to match on 20 Sep 2026
  — but that resolved a contradiction, not the question. Measured the same day:
  MAXQDA's zh-TW interface uses **代碼** for a code-as-noun (×96) and 編碼 for the
  activity, as do MAXQDA and NVivo in zh-CN; **NAER** and Academia Sinica's SRDA
  say **編碼簿**. So the tools and the terminology authorities disagree, and our
  files follow the authorities.
- **You:** 編碼簿 or 代碼簿 — which would a Taiwanese qualitative researcher
  expect?

## Quick confirms — all first-draft

- **Intensity tooltip** — «平均情緒強度（1–3）». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
