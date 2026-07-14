# Progress-ring estimate — honest tail

Diagnosed 13 Jul 2026 during hands-on desktop QA (Debug build, project-ikea, bundled sidecar). The
sidebar activity ring reaches near-full and sits there through the analysis tail — around
"Grouping themes" — well before the run is actually done. This documents the mechanism, why the
estimate under-counts the tail, the interim display stopgap (lands in the next release), and the
options for the proper stage-weighted fix (a near-term follow-up enhancement).

**Status (14 Jul 2026):** TF-1 has shipped, so the earlier "park until after TestFlight" framing no
longer applies. The interim creep stopgap is committed and lands in the next ordinary release; the
stage-weighted fix below is the follow-up enhancement, no longer release-gated.

Sibling doc: [`design-sidebar-activity-indicators.md`](design-sidebar-activity-indicators.md) (the
Phase 0b determinate-ring design this refines).

---

## The surface (how the ring is driven)

The ring fraction is **not** a percentage sent from Python. Python emits raw ingredients into an
append-only NDJSON file; Swift computes the fill locally and polls the file at 1 Hz.

Full chain:

1. **Python emits** `run_progress` events with `elapsed_seconds`, `predicted_total_seconds`,
   `eta_remaining_seconds`, `stage`, `sessions_complete/total`, and (transcription only)
   `stage_fraction`. Emit sites: `Pipeline._emit_remaining` ([`pipeline.py:471`](../bristlenose/pipeline.py)) after each stage,
   `_emit_stage_entry` ([`pipeline.py:531`](../bristlenose/pipeline.py)) on stage entry. There is **no `percent`/`fraction` field on the wire.**
2. **`predicted_total_seconds`** is computed as `elapsed_so_far + remaining_estimate`, where
   `remaining_estimate` comes from the Welford estimator `TimingEstimator.stage_completed`
   ([`timing.py:309`](../bristlenose/timing.py)) summing `mean_rate × input_size` over the not-yet-completed stages.
3. **Transport** is a file tail: `<output_dir>/.bristlenose/pipeline-events.jsonl`.
4. **Swift polls** at 1 Hz (`PipelineRunner.startProgressPoll` [`:564`](../desktop/Bristlenose/Bristlenose/PipelineRunner.swift),
   `applyEventProgress` [`:581`](../desktop/Bristlenose/Bristlenose/PipelineRunner.swift)) and folds the newest event into the ring via
   `RunProgressMath.apply` ([`RunProgressMath.swift`](../desktop/Bristlenose/Bristlenose/RunProgressMath.swift)).
5. **The fill** = `localElapsed / predictedTotal`, clamped monotonic to a hard `asymptoteCap = 0.92`.
   `localElapsed` is `now − startedAt` sampled fresh each poll, so the ring advances between events.
6. **Render**: `ProjectRowActivityIndicator` [`:47`](../desktop/Bristlenose/Bristlenose/ProjectRowActivityIndicator.swift) → `SidebarActivityRing` `strokeEnd` (the AppKit
   `NSOutlineView` sidebar is the shipped path).

The six estimator stages (`timing.py` `ALL_STAGES`): `transcribe, speakers, topics, quotes, cluster,
render`. "Grouping themes" is the verb for `cluster` — which spans **both** s10 clustering and s11
theming, run concurrently in one `asyncio.gather` ([`pipeline.py:1699`](../bristlenose/pipeline.py)).

---

## What's actually wrong

The fill is `elapsed / predicted`, and `predicted` systematically under-counts the tail, so the ratio
races to the `0.92` cap long before the run finishes. Four compounding causes:

1. **"Grouping themes" is the last substantial stage, has no intra-stage progress signal, and a
   small, high-variance estimate.** It's a single concurrent LLM call — no per-session ticks, no
   sub-steps — so during it the ring gets nothing but the 1 Hz local-clock advance against a fixed
   `predicted` anchored at stage entry. From the live desktop timing profile
   (`~/.config/bristlenose/timing.json`, `… | anthropic | claude-sonnet-4-6`): `quotes` dominates at
   ≈16 s/session while `cluster` is ≈4.15 s/session. So by the time grouping starts, `elapsed/predicted`
   is already ~87%, and grouping's own ~20 s estimate (5 sessions) runs out fast when the LLM actually
   takes 40–50 s → `elapsed` overruns `predicted` mid-grouping → cap.

2. **Untimed tail work.** The people-file merge ([`pipeline.py:1767`](../bristlenose/pipeline.py)) runs between grouping and
   render and is folded into **no** Welford stage — pure dead time the estimate never accounts for.

3. **The `remaining < 10 s` floor clears the estimate.** After grouping, only `render` (≈0.4 s/session)
   remains, so `stage_completed` returns `None` ([`timing.py:331`](../bristlenose/timing.py)) and `_last_predicted_total` is
   cleared; the render stage-entry then emits `predicted_total_seconds = null`. Swift falls back to the
   stored value (still evaluating), but there's no fresh signal to move the ring off the cap.

4. **LLM latency variance is intrinsic.** `quotes`/`cluster` Welford variance is large; even a
   well-calibrated mean will be ~2× off on a bad LLM day. No amount of estimator tuning removes this —
   the display must degrade gracefully when the estimate is wrong, not just when it's right.

Net effect: the ring hits the cap partway into the last big stage and sits there (frozen, pre-stopgap)
for the remainder — the "hung at ~99%" read the maintainer is sensitive to (MAAS waiting-psychology:
a bar that stops moving erodes trust in the estimate).

---

## Interim stopgap (already in the tree)

`RunProgressMath` was changed (13 Jul 2026) to stop the ring *freezing* at the cap:

- **Reserve headroom** — `expectedCompletionMark = 0.85`: the estimate's honest end-point is 0.85, not
  the `0.92` cap.
- **Overrun creep** — past the estimate the fill creeps asymptotically `0.85 → 0.92`
  (`1 − exp(−overrun/tau)`, `tau = 0.6`), so an over-running tail keeps visibly inching instead of
  sitting flat. Animated by the existing 1 Hz poll. Regression test:
  `RunProgressMathTests.applyRingKeepsMovingWhenRunOverrunsEstimate`.

**What it fixes:** the *frozen* read — a moving 85% over a stalled 99%.
**What it does NOT fix:** the ring still reaches the high-80s/low-90s too early, because the underlying
`predicted` still under-counts the tail. This is a display stopgap, not the root fix — but it removes
the "looks hung" read cheaply and honestly, so it lands in the next release. The stage-weighted fix
below then supersedes it (the overrun-creep is retained, applied per-slice rather than whole-run).

---

## Options for the proper fix

### A. Stage-weighted ring (recommended)

Stop driving the ring off whole-run `elapsed/predicted`. Instead give each stage a **slice of the ring
sized by its measured time-share** (from the Welford data we already persist), and fill *within the
current stage's slice* by that stage's own progress:

- Completed stages contribute their full expected share (not their actual time — so an over-running
  stage can't push the ring past its slice).
- The in-progress stage fills its slice by the best signal it has: session fraction for per-session
  stages (`speakers/topics/quotes`), audio fraction for `transcribe`, elapsed-vs-expected for
  `cluster/render` — with the overrun-creep applied *within the slice* so a long grouping inches
  toward its slice ceiling but cannot invade render's slice.

Result: "Grouping themes" can only ever fill grouping's slice; it structurally cannot race to the cap,
and a long grouping shows honest sub-slice motion. Self-correcting across projects (a project where
quotes is fast but grouping slow automatically gives grouping a bigger slice).

**Cost — cross-language.** Python emits the per-stage budget (`stage_base`, `stage_span`,
`stage_expected_seconds`); Swift records the local time at each stage change and interpolates the
current slice; `RunProgressMath` reworked; tests both sides. Also fold the people-file merge into a
timed stage (attach to `render` or its own) so the tail gap disappears. Estimator persisted-profile
semantics (`timing.json`) unchanged — this reads the same means, just as shares rather than a scalar
sum.

### B. Display tuning only (cheap)

Keep the stopgap; lower the resting mark (e.g. 0.75) and widen the creep window so a long tail climbs
from lower down. Swift-only, no estimator change. **Downside:** accurate runs top out lower, and the
ring position still doesn't track real remaining work — it just looks less parked. A knob-turn, not a
fix.

### C. Give grouping an intra-stage signal

Emit a `stage_fraction` for `cluster` (and `render`) — e.g. a time-based within-stage fraction, or
emit a sub-step when clustering completes and theming begins. Marginal on its own (the two calls are
concurrent, so 0.5 sub-steps don't decompose cleanly), but composes with A as the "current-slice fill"
signal.

**Recommendation:** A, with the people-file merge folded into a timed stage, and C's within-stage
time fraction as the slice-fill signal for `cluster`. B only if the beta window is too tight for A.

---

## Open questions / risks

- **Cold start / thin history.** With `< 4` runs of history the Welford means are absent or noisy; the
  slice weights degrade to something coarse (equal slices, or fall back to the current
  `elapsed/predicted`). Needs an explicit fallback ladder, mirroring the existing best-available ladder
  in [`design-sidebar-activity-indicators.md`](design-sidebar-activity-indicators.md).
- **CLI parity.** The same estimator drives the CLI's ETA prose. Stage-weighting is a display concern
  for the ring; confirm the CLI ETA text is unaffected (it consumes `eta_remaining_seconds`, not the
  ring fraction).
- **Analyze / skip-transcription paths.** Slice weights must renormalise when a stage is skipped
  (`--no-transcribe`, cached stages) — the existing `initial_estimate(skip_transcription=…)` already
  excludes skipped stages from the sum; the slice math must do the same.

---

## Related

- Interim stopgap: [`RunProgressMath.swift`](../desktop/Bristlenose/Bristlenose/RunProgressMath.swift), `RunProgressMathTests.swift`.
- Sibling parked item: the "glowing/shimmer alive-progress treatment" (ambient motion for a held
  determinate ring) — same progress-indicator honesty theme, same post-TF window.
- The stale "N of M" session count shown next to non-session stages (e.g. "Grouping themes · 4 of 5")
  is a separate, smaller wart tracked independently.
