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
