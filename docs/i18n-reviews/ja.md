# Bristlenose — Japanese wording check

Bristlenose turns user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. The Japanese terms are nearly all in place; I'd just like your steer on one wording call and a sign-off on a fix before they're locked in. Should take five minutes.

## Where I'd really value your steer

### Friction (the friction-point finding)  ·  genuine toss-up
- **What we use now:** フリクション
- **Also in play:** 摩擦, or the paired form フリクション（摩擦）
- **The nuance:** UX TIMES uses フリクション on its own, but practitioner press (e.g. productzine) often writes 摩擦 or glosses 摩擦（フリクション） — so the loanword reads "industry-glossary", the kanji reads "plain Japanese".
- **My hunch:** keep フリクション as the standing term, but gloss it フリクション（摩擦） on first appearance so it lands for readers who don't live in the loanword. It's a finding label, not body text, so I'd lean loanword-first.
- **You:** does カタカナ フリクション read naturally as a heading, or would 摩擦 (or the paired form) feel less foreign? And is フリクション kept clearly distinct from the emotion フラストレーション?

### PII redaction — one menu string is wrong  ·  clear-cut, just confirm
- **What we use now:** 個人情報の削除 (削除 throughout the user-facing prose)
- **Also in play:** 墨消し (in the settings reference), and 編集 in one desktop string — which is the bug: 「PII編集はオフです」 reads "PII *editing* is off", not "redaction is off".
- **The nuance:** 削除 (remove/delete) carries the bulk of the prose; 墨消し is the precise legal redaction term but collides with 削除 and sits awkwardly next to 匿名化 (anonymisation).
- **My hunch:** fix 編集 → 削除 now (it's plainly wrong), and standardise on 削除 everywhere for consistency rather than promoting 墨消し.
- **You:** happy with 「個人情報の削除はオフです」 as the fix? And — 削除 or 墨消し as the one standing redaction verb, kept separate from 匿名化?

## Quick confirms (I think these are settled — just shout if not)
- **Participant → 参加者** — the HCD-Net / NN/g JP register; avoids the dehumanising 被験者.
- **Speaker → 話者** — the speaker-diarization standard (話者1・話者2); 話者 not スピーカー (which is the audio device).
- **Tags → タグ** — matches Apple's Finder タグ.
- **Theme → テーマ** — the Braun & Clarke テーマ分析 term; kept distinct from トピック.
- **Transcript → トランスクリプト** for the document you open; 文字起こし for the act of transcribing — a deliberate noun/process split.

## Anything I've got wrong?
If any of these feels off in real Japanese UX writing — too foreign, too academic, or just not how you'd say it — please flag it. Your call wins over ours every time.


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
シグナルを読み込み中…
シグナルはまだありません。パイプラインを実行するか、コードブックタグを適用して生成してください。
タグシグナルのエラー: {{error}}
シグナルとは、レポートの各セクション内で統計的に目立つ感情の集中です。強いシグナルと中程度のシグナルが、参加者の体験がどこに集まっているかを示します。
シグナルとは、レポートの各セクション内で統計的に目立つ感情やコードブックタグの集中です。シグナルカードは 2 種類あります。
```

## Where I'd value your steer

### 「シグナルとは、…です」  ·  the definition form is mine
- **What we use now:** 「シグナルとは、レポートの各セクション内で統計的に目立つ感情の集中です。」
- **Also in play:** 「シグナルは、…」 without *とは*
- **The nuance:** I used **とは** because the sentence is defining the term under
  a heading that just says **シグナル**, and *とは…です* is the ordinary shape for
  that. Plain *は* would make it a statement about signals rather than a
  definition. The previous wording was 「分析ページではシグナルが表示されます」 — a
  sentence about the page, which is what the rename removed.
- **You:** *とは* as it stands, or plain *は*?

### The em dash is gone  ·  deliberate
- The old strings carried an ASCII **" — "** in mid-sentence, copied from the
  English apposition. That is not Japanese punctuation, and the definition-first
  rewrite removed the need for it; the clause is now a plain 連体修飾 before 集中.
- **You:** confirm the sentences read cleanly without it.

### 「タグシグナルのエラー:」  ·  measured, sanity-check me
- The colon is **halfwidth** with a following space, which is what Apple's
  Japanese ships for a label (measured: 431 halfwidth against 2 fullwidth across
  246 system files; Apple's own Save dialog is 名前:). The fullwidth ： is kept
  for prose lead-ins like 注：. This was got backwards once and reverted, so it
  is settled rather than open — but shout if it looks wrong on screen.
- Also: I added **の** (*タグシグナルのエラー*) where the old string had none
  (*タグ分析エラー*). Four nouns in a row felt heavy.
- **You:** with *の*, or back to the bare compound?

## Quick confirms — all first-draft

- **Intensity tooltip** — «感情強度の平均 (1〜3)». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
