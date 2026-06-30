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
