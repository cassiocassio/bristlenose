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
