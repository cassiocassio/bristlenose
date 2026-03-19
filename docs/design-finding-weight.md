# Finding Weight — Signal Direction and Finding Character

_Last updated: 19 Mar 2026_

Design exploration. Not an implementation plan.

---

## Problem

The Analysis tab shows **signal strength** (concentration x agreement x intensity) but not **signal direction**. A researcher looking at the top-ranked signal cards can't immediately see whether a strong signal is a success to protect or a problem to fix.

Research debriefs typically need to distinguish:

1. Things that are going well (protect these, celebrate them)
2. A primary issue (the headline finding)
3. Secondary concerns (important but less urgent)
4. Neutral patterns (worth discussing, not clearly good or bad)
5. Minor friction (laundry list of niggles)

Bristlenose's signal cards have enough data to support this distinction, but don't currently surface it.

Separately: successes are genuine findings, not just absence of problems. A cluster of satisfaction/delight/confidence quotes around a specific feature is actionable — it tells the team what to protect and what to double down on. The current ranked list buries these among problems.

---

## What we already have

Each `Signal` dataclass (`bristlenose/analysis/models.py`) contains:

- **`sentiment`** — which of the 7 sentiment categories this signal is about (e.g. "frustration", "delight")
- **`count`** — how many quotes
- **`participants`** / **`n_eff`** — breadth across participants
- **`mean_intensity`** — how strongly felt (1–3 scale)
- **`concentration`** — how over-represented vs expected
- **`composite_signal`** — the combined strength score

The 7 sentiment categories (`bristlenose/models.py`) have inherent valence:

| Sentiment | Valence |
|---|---|
| frustration | negative |
| confusion | negative |
| doubt | negative |
| surprise | neutral (expectation mismatch — flag for investigation) |
| satisfaction | positive |
| delight | positive |
| confidence | positive |

So **every signal card already carries valence information** via its `sentiment` field. The composite formula just doesn't use it, and the UI doesn't surface it.

---

## Tag interpretability tiers

Beyond the sentiment system, tags from codebooks carry varying degrees of interpretable valence:

**Tier 1 — Sentiment codebook.** Valence is definitional. "frustration" IS negative. No inference needed. This is what signal cards already use.

**Tier 2 — Framework codebooks (UXR, Norman, Morville, Garrett, Plato).** Tags here describe *what* the finding is about, not whether it's good or bad. "discoverability", "affordance", "learnability" are neutral subjects. The valence comes from the quote's sentiment: "frustration + discoverability" = can't find the thing; "delight + affordance" = the button worked beautifully. No need to separately classify these tags — the sentiment × tag combination already tells the story. Parked for now; revisit only if quote-level sentiment proves insufficient.

**Tier 3 — User-created tags.** Valence is opaque. "homepage", "version 2", "chosen by Sarah" — no AI can determine if these are positive or negative without human context. Some user tags ARE judgemental ("is expensive", "is profitable") but Bristlenose can't know which.

---

## Why a single positive/negative axis is too simplistic for tags

Tags aren't inherently positive or negative. The valence lives in the **intersection** of a tag and a specific quote, not in the tag itself:

- **"workaround"** — positive (resourcefulness) AND negative (system failure). Both simultaneously
- **"trust signal"** — present = good, absent = bad. The absence is often the interesting finding
- **"visible action"** (Norman) — neutral descriptor. Whether it's positive or negative depends on whether the action matched the user's mental model
- **"learnability"** (Morville) — being learnable is good, but a quote about learnability might say "I could never figure this out"

This is why the current architecture — sentiment on quotes, semantic categories on tags — is actually right. The two are orthogonal dimensions. Finding weight emerges from their combination, not from classifying tags.

---

## Finding weight dimensions

Four dimensions, all derivable from existing data:

**Volume** — how many quotes cluster around this signal. Already captured as `Signal.count`.

**Intensity** — how strongly felt. Already captured as `Signal.mean_intensity` (1–3 scale).

**Consistency** — do participants agree? Already partially captured as `Signal.n_eff` (effective participant count). A signal with high n_eff relative to total participants means broad agreement.

**Valence clarity** — is this clearly positive, clearly negative, or mixed? Currently NOT computed, but derivable:

- Signal card sentiment is one of the 7 categories, each with known valence (see table above)
- For the current signal system (one sentiment per card), valence clarity is trivially known
- For future tag-based signals (where a cluster might span multiple sentiments), clarity would measure how consistent the sentiment direction is across the quotes

---

## Finding flags

Single-word labels. Descriptive, not judgemental — the tool flags the shape of the data, the researcher decides what it means.

| Flag | Volume | Intensity | Consistency | Valence | Example |
|---|---|---|---|---|---|
| **Win** | high | any | broad (high n_eff) | positive | "Satisfaction with onboarding" — 15 quotes, 7 participants |
| **Problem** | high | high | broad | negative | "Frustration with settings" — 20 quotes, 8 participants, intensity 2.5 |
| **Pattern** | high | mixed | broad | mixed or neutral | Lots of signal around pricing but not consistently positive or negative |
| **Niggle** | low | moderate | narrow (1–2 people) | negative | "Confusion with date picker" — 3 quotes, 1 participant |
| **Success** | low | any | narrow | positive | "Delight with keyboard shortcuts" — 2 quotes, 1 participant. Small but positive |
| **Surprising** | any | any | any | neutral (surprise sentiment) | Users found this unexpected — worth the researcher's attention, not a value judgement |

These are flags for the researcher to work with, not conclusions. A "Win" might be a well-established function that people like, not a breakthrough. A "Problem" might be a known trade-off the team has already accepted. The tool surfaces the shape; the researcher applies judgement.

Successes and wins are currently underserved — signal ranking treats them identically to problems. Surfacing them distinctly gives researchers something to report beyond "here's what's broken."

---

## How much the existing system already does

Honest assessment: the composite signal formula already captures most of finding weight. Concentration handles "is this notable?", n_eff handles "is this broad?", intensity handles "is this strongly felt?"

The main gap is the **direction label**. The signal card for "Satisfaction with Onboarding" and "Frustration with Settings" are ranked by the same composite score, and the researcher has to read the sentiment badge to know which is positive and which is negative.

The delta might be as small as:

1. Classifying each signal card's sentiment as positive/negative/neutral (trivial lookup from the 7-category enum)
2. Surfacing that classification visually (colour, icon, grouping)
3. Optionally allowing researchers to filter/sort by direction

Whether that small delta is worth the UI complexity is an open question.

---

## Classification logic

**One flag per signal card, mutually exclusive.** Each signal card is about one sentiment in one location — it has one valence direction, one breadth, one intensity. The decision tree is a simple waterfall:

```
VALENCE_MAP = {
    "frustration": "negative",
    "confusion":   "negative",
    "doubt":       "negative",
    "surprise":    "neutral",
    "satisfaction": "positive",
    "delight":     "positive",
    "confidence":  "positive",
}

valence  = VALENCE_MAP[signal.sentiment]
breadth  = signal.n_eff / total_participants

if signal.composite_signal < MIN_SIGNAL_THRESHOLD:
    flag = None  # not enough signal to claim anything
elif valence == "neutral":
    flag = "Surprising"
elif valence == "positive" and breadth >= BREADTH_THRESHOLD:
    flag = "Win"
elif valence == "positive" and signal.composite_signal >= SMALL_SIGNAL_THRESHOLD:
    flag = "Success"
elif valence == "negative" and breadth >= BREADTH_THRESHOLD
        and signal.mean_intensity >= INTENSITY_THRESHOLD:
    flag = "Problem"
elif valence == "negative" and signal.composite_signal >= SMALL_SIGNAL_THRESHOLD:
    flag = "Niggle"
else:
    flag = None  # signal exists but not confident enough to flag
```

**Flags are optional.** A signal card can have zero or one flag (`flag: str | None`). Better to leave a card unflagged than to claim significance for something a researcher would glance past. The thresholds should err on the side of silence — only flag when the data is clearly saying something. Unflagged cards are just "here's some signal, make of it what you will."

**"Pattern"** is the fallback for mixed-valence signals — currently only reachable if a future mixed-valence cluster feature produces signals with no single sentiment. For now every signal has a sentiment, so Pattern won't fire. Keep it in the enum for when mixed-valence clusters arrive.

### Tuning thresholds

Four tunables:
- **`MIN_SIGNAL_THRESHOLD`** — minimum composite signal to flag at all. Below this, card stays unflagged. Starting guess: TBD from real data
- **`SMALL_SIGNAL_THRESHOLD`** — minimum composite signal for Success/Niggle (the narrow flags). Starting guess: TBD from real data
- **`BREADTH_THRESHOLD`** — what fraction of participants makes a signal "broad" (Win/Problem)? Starting guess: `0.3` (30%)
- **`INTENSITY_THRESHOLD`** — minimum mean intensity for a negative signal to be a Problem rather than a Niggle? Starting guess: `2.0` (out of 3)

These need a **dev-only HUD with threshold sliders** — drag and watch flags re-classify in real time on actual study data. Same pattern as the sidebar playground. Fastest way to find good defaults.

---

## Decisions

1. **UI design comes later.** Calculate the flags, test with real data, see if the classifications make sense. How and where to surface them is a separate question.

2. **Grouping/filtering by direction — later.** Get the calculation right first.

3. **Surprise is its own flag.** A concentration of surprise from multiple users is worth flagging. Don't try to sub-classify it as positive-surprising or negative-surprising — "users found this unexpected" is enough for the researcher to investigate.

4. **Skip tag-level valence classification.** The signal cards already carry a sentiment field (frustration, delight, etc.) — that's the valence signal. Codebook tags tell you what a finding is *about*, not whether it's good or bad. No need to also infer valence from tag definitions. The sentiment × tag combination already tells the story: "frustration + discoverability" = can't find the thing; "delight + affordance" = the button worked.

5. **Mixed-valence clusters — later.** Current system treats them as separate cards; revisit if that proves wrong on real data.

6. **Augments composite signal, doesn't replace it.** Finding flags are a new dimension alongside signal strength.

7. **Two-pane integration — later.** Depends on which Phase 4 features prove valuable.

8. **Zero or one flag per signal card.** Flags are optional — better unflagged than noisy. The waterfall assigns at most one flag; cards that don't clear the thresholds stay unflagged.

## Open questions

1. Does the flag assignment feel right on real study data? Do the thresholds need tuning?
2. Are six flags the right set, or do some collapse in practice?
3. Is "Surprising" useful as a distinct flag, or does it just mean "look at this"?
4. Where should the HUD live — alongside the existing playground, or its own dev-mode panel on the Analysis tab?
