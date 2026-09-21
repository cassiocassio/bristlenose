# Bristlenose — Korean wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. I'm locking the Korean term set and would value your steer on a handful before they're fixed. Should take five minutes — most of it is just confirming.

## Where I'd really value your steer

### Participant  ·  genuine toss-up
- **What we use now:** mixed — the dashboard column, report header counts and prose say **참가자**, but the transcript role and the CSV export columns say **참여자**.
- **Also in play:** 참여자, 참가자 (and the formal/IRB register 연구대상자, which feels too clinical for a product).
- **The nuance:** OpenSurvey and Toss writing lean heavily on **참여자** (active involvement); **참가자** reads closer to "event attendee" — but right now the same people get both labels on adjacent screens.
- **My hunch:** Normalise everything to **참여자** — it matches our own transcript role and the UX-research register. (Note this deliberately diverges from the Japanese 参加者 cognate.)
- **You:** Is **참여자** right across the board, or does **참가자** read as more neutral for a results dashboard specifically?

### Theme  ·  genuine toss-up
- **What we use now:** the loanword **테마** for an emergent theme. We already use **주제** for the pipeline's "topic segmentation" stage, so 주제 is taken.
- **Also in play:** 주제 — which is the academic thematic-analysis term (주제분석).
- **The nuance:** Braun & Clarke "theme" is **주제** in Korean qualitative literature, but adopting it would force us to rename the "topic" pipeline strings to avoid a clash.
- **My hunch:** Keep **테마** — it's unambiguous against our "topic" usage and reads cleanly in a product. But I'd defer to you if 테마 feels too casual for a researcher.
- **You:** Does **테마** read correctly as an analysis theme, or is the academic **주제** worth the rename cost?

### Friction  ·  clear-cut, just confirm
- **What we use now:** the native **마찰** (마찰 지점 = friction point).
- **Also in play:** the loanword 프릭션, or 불편 (inconvenience).
- **The nuance:** 불편 loses the "resistance in the flow" sense; my only worry is whether **마찰** is misread as literal/physical friction.
- **My hunch:** Stay with **마찰** — IBM Korea and Korean UX writing use 마찰 지점, and it's better anchored than the Japanese loanword choice.
- **You:** Does **마찰** land as UX friction for a research audience, no physical-friction misread?

### Star (a flagged quote)  ·  clear-cut, just confirm
- **What we use now:** a split — **즐겨찾기** for the collection noun and help text, **별표** for the verb/menu/CSV column ("star this quote", 별표 인용문만).
- **Also in play:** picking one of the two as the single surface noun.
- **The nuance:** 별표 표시 reads naturally as the gesture, 즐겨찾기 names the resulting set — defensible, but the view switcher (즐겨찾기 인용문) and the desktop menu (별표 인용문) currently disagree about the same items.
- **My hunch:** Keep **별표** for the gesture but settle on one noun for the collection so the toolbar and menu match.
- **You:** Which single noun for the starred set — **즐겨찾기** or **별표**?

## Quick confirms (I think these are settled — just shout if not)

- **Speaker → 화자** — the speech-tech standard (화자 분리 = diarization); two stray **발화자** strings will be fixed to match.
- **Tags → 태그** — matches Apple Korea's Finder/Notes localisation; loanword over a native coinage.
- **Quote → 인용문** — our glossary anchor, used in 50+ places; I'll normalise the six **인용구** strings in the export/copy flow to match.

## Anything I've got wrong?

If any of these reads stiff, off-register, or just wrong to a native ear — or if there's a concept we're rendering awkwardly that I haven't flagged — please say. Your call wins over ours on any of them.


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
시그널 로드 중…
아직 시그널이 없습니다. 파이프라인을 실행하거나 코드북 태그를 적용하여 시그널을 생성하세요.
태그 시그널 오류: {{error}}
시그널은 보고서 섹션 내에서 통계적으로 주목할 만한 감정 집중입니다. 강한 시그널과 보통 시그널은 참가자 경험이 집중되는 곳을 강조합니다.
시그널은 보고서 섹션 내에서 감정 또는 코드북 태그의 통계적으로 주목할 만한 집중 현상입니다. 두 가지 유형의 시그널 카드가 있습니다.
```

## Where I'd value your steer

### 「시그널은 … 입니다」  ·  the copula is mine
- **What we use now:** 「시그널은 보고서 섹션 내에서 통계적으로 주목할 만한 감정
  집중입니다.」
- **The nuance:** defining the term under a heading that just says **시그널**.
  The previous wording was 「분석 페이지는 시그널을 표시합니다」 — a sentence about
  the page.
- **You:** does it read as a definition?

### A collision I hit and then removed  ·  worth knowing
- For a few hours this sentence read 「시그널 **보기**는 … 표시합니다」, using
  Apple's own noun for a *view*. A review caught that **보기** is the verb
  *view/show* in six other strings in this same file (*Finder에서 보기*, *제외된
  인용문 보기*, *보고서 보기*, *{{count}}개 인용문 모두 보기*), so the sentence
  first parsed as *"viewing signals displays…"* — a gerund in subject position.
- I rewrote it locatively with the name in quotes, and then the definition-first
  rewrite removed the construction altogether.
- **You:** nothing to fix, but if a future string has to name a lens in prose,
  is 「시그널」에서는 the right shape, or would you use something else?

### 참가자, deliberately left alone  ·  still your call
- These sentences say **참가자**. The transcript role enum says **참여자**, and
  that inconsistency is an open question from an earlier round — I did **not**
  quietly normalise it here, because picking one is your decision and doing it
  inside a rename would bury it.
- **You:** 참여자 everywhere, or is 참가자 right for a results surface?

## Quick confirms — all first-draft

- **Intensity tooltip** — «평균 감정 강도(1–3)». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
