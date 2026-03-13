# Motion Design Brief: Perceived Quality Through Meaningful Physics

**Status:** Reference document and animation catalogue
**Date:** 12 Mar 2026

---

## 1. Why This Matters

The goal is not smoothness for its own sake. It's **the iPhone scrolling moment** — the instant someone touches the UI and feels it respond like a physical object with mass, momentum, and consequence. That feeling communicates three things simultaneously:

1. **"I caused this"** — the UI responded to *my* action, proportionally
2. **"This is real"** — the change has weight, it happened in space, it can't be accidental
3. **"I'm in control"** — if I can cause this, I can undo it; the system is predictable

The research backs this up:

- **Change blindness** (Rensink et al., 1997) — instant state changes are literally invisible to the human visual system. Without a transition, users must *search* for what changed. Animation removes that search cost entirely
- **Object permanence** (Bederson & Boltman, 1999) — users track UI elements spatially, like physical objects. A sidebar that slides left "lives" to the left. One that teleports has no home
- **Perceived performance** (Harrison et al., 2010) — animation during latency makes identical wait times feel 10-15% shorter. A 200ms fade-in *feels* faster than a 0ms instant-appear because the animation occupies attention during render latency
- **Aesthetic-usability effect** (Tractinsky et al., 2000) — polished transitions signal craftsmanship. Users unconsciously reason: "if they cared about *this*, they cared about everything"

### The premium-feel insight

A Moog synthesizer toggle doesn't click — it *clunks*. The clunk communicates mass, precision, and irreversibility. A Leica shutter doesn't snap — it *whispers*. Each communicates something different about the action taken. **The animation vocabulary must match the semantic vocabulary of the interaction.**

---

## 2. Core Principles

Ranked by priority. Every animation decision should be evaluated against this list.

**1. Causal.** Animation must show cause and effect. "I clicked this button, so this panel opened." If the connection is not obvious, the animation fails regardless of how smooth it is.

**2. Continuous.** Objects must not teleport. A sidebar that is "to the left" when closed must slide in from the left when opened. A dropdown that is "below the button" must expand downward. Spatial consistency reduces cognitive load.

**3. Interruptible.** Animations must never block interaction. If a user clicks a second time during a 300ms transition, the animation must either reverse immediately or skip to the end state. CSS transitions handle this naturally; JS-controlled animations need explicit cancellation. Escape key always closes instantly (no animation) — keyboard users expect immediate response.

**4. Proportional.** Duration must match the magnitude of change. A 2px colour shift on hover: 100-150ms. A sidebar sliding 280px: 75ms. Small changes with long animations feel sluggish; large changes with short animations feel jarring.

**5. Respectful of `prefers-reduced-motion`.** Users who set this media query have a medical or cognitive reason. All keyframe animations must stop; all transitions must reduce to 0ms or near-0ms. Both the CSS media query and the existing `.bn-no-animations` class must be supported.

**6. Consistent.** The same type of transition should use the same duration and easing everywhere. A dropdown opening in the toolbar should animate identically to a dropdown opening in the sidebar. This means defining a small set of motion tokens and using them uniformly.

---

## 3. Lessons from the Sidebar (The Test Case)

The LHS TOC sidebar was the first element to receive the full motion treatment. The iteration journey established timings, techniques, and perceptual thresholds that now inform all future animation work.

### 3.1 The iteration journey

| Version | Panel duration | Sub-animation | Hover delay | Verdict |
|---------|---------------|---------------|-------------|---------|
| v1 | 300ms | 150ms | 400ms | Felt academic and sluggish — based on iOS/Material guidelines but wrong for a lightweight sidebar reveal |
| v2 | 150ms | 75ms | 400ms | Better, but hover delay was the bottleneck — the *wait* felt slow, not the animation |
| v3 (shipped) | **75ms** | **40ms** | **200ms** | Snappy. Animations are almost subliminal — you perceive the panel appearing rather than watching it arrive |

**Key learning:** halving the duration twice was needed. Material Design's 200-300ms recommendations are tuned for full-page transitions and cards, not narrow sidebar reveals. The sidebar is a lightweight peek — it should feel like flicking a light switch, not opening a heavy door.

### 3.2 Perceptual thresholds discovered

**75ms is the sweet spot for a narrow sidebar reveal.**
- Below ~60ms: `clip-path` animation is invisible (wasted GPU work)
- Above ~120ms: the reveal feels slow for a narrow panel
- 75ms = 4-5 frames at 60fps — enough to perceive motion without waiting for it

**40ms sits at the perceptual threshold for sequential events** (Exner, 1875; modern estimates 30-50ms).
- The brain registers "something moved separately" without consciously tracking it
- Used for: icon depart (40ms), close × sneak-in (40ms delayed by 40ms), iOS content settle (65ms delayed by 10ms)
- Faster: invisible. Slower: creates a perceived pause

**200ms hover delay filters intent from accident.**
- Below 150ms: accidental hovers trigger the overlay when the mouse crosses the rail en route to the scrollbar
- At 200ms, the overlay opens so fast that any hover cue (background tint on the rail) reads as flicker — the hover cue idea was tried and removed

**80ms hover-intent filters traversal from acquisition on narrow targets.**
- The drag handle is 6px wide. At casual mousing speed (400-1500 px/s), the cursor crosses it in 4-15ms
- Deliberate acquisition slows to 100-200 px/s, dwelling 30-60ms+
- 80ms catches nearly all intentional hovers while filtering all casual traversals
- The `cursor: col-resize` change remains instant (CSS, no delay) — sufficient affordance for discovery. The accent highlight is reinforcement, not discovery
- Unlike the 200ms overlay hover delay (which was too fast for a hover cue), 80ms works for the accent highlight because the highlight is smaller and less visually disruptive

**400ms is the one timing that stays high** (TOC link close delay).
- Smooth scroll takes ~200-400ms, plus scroll-spy needs a frame to update the highlight
- 400ms lets the user see *both* the scroll *and* the highlight move before the panel closes
- Tried 100ms — too fast to register the highlight change
- This follows Nielsen's "visibility of system status" heuristic

### 3.3 The shipped sidebar timeline

| Element | Duration | Delay | Easing | Purpose |
|---------|----------|-------|--------|---------|
| Panel clip-path reveal | 75ms | 0 | `ease-out (0,0,0.2,1)` | TOC slides in from rail edge |
| Panel clip-path hide | 75ms | 0 | `ease-in (0.4,0,1,1)` | TOC slides back toward rail |
| Rail icon depart | 40ms | 0 | `ease-in` | Icon fades out + shifts left |
| Rail icon return | 40ms | 40ms | `ease-out` | Icon fades back in (after × departs) |
| Close × sneak in | 40ms | 40ms | `ease-out` | Close button appears (after icon departs) |
| Close × sneak out | 40ms | 0 | `ease-in` | Close button disappears |
| iOS content settle | 65ms | 10ms | `cubic-bezier(0.25,0.46,0.45,0.94)` | Content inertia effect |
| iOS content depart | 50ms | 0 | `ease-in` | Content leaves with iOS variant |
| Push mode grid transition | 75ms | 0 | `ease` | Grid column widths animate |
| Hover delay | 200ms | — | — | Timer before overlay opens |
| Leave grace | 100ms | — | — | Tolerance after mouse leaves rail |
| TOC link close delay | 400ms | — | — | Panel stays open for scroll confirmation |
| Drag handle hover-intent | 80ms | — | — | Delay before accent highlight on drag handles |

### 3.4 CSS techniques established

**Clip-path reveal** — GPU-composited, layout-free panel entry. `clip-path: inset(0 100% 0 0)` (hidden) → `inset(0 -100px 0 0)` (revealed). The negative right value gives the box-shadow room to paint beyond the element edge. Both clip and shadow reveal progressively.

**Cross-fade icon swap** — Rail icon fades out + shifts left (0-40ms, `ease-in`) while close × fades in at the same position (40-75ms, `ease-out`). Exploits Gestalt common fate + spatial proximity — the brain reads them as one object transforming. Both push and overlay modes share this header layout (`.sidebar-header` base class).

**iOS inertia variant** — Content `translateX(-20px→0)` with 10ms delay after panel reveals at 0ms. Creates "heavy object coming to rest" impression. The `cubic-bezier(0.25,0.46,0.45,0.94)` has gentle initial slope + long deceleration tail. A/B toggle in dev playground — the effect is subtle enough to need visual comparison.

**Deferred class pattern** — Adding an overlay class on `pointerdown` causes a ghost frame (border/shadow visible before content). Fix: defer the class to the first `pointermove` that produces width > 0. The element only appears once there's content to show. **Apply this pattern to any drag-to-reveal interaction.**

**Hover-intent via JS class** — Replace CSS `:hover` with a JS-managed `.hover-intent` class on narrow hit targets (≤10px). `mouseenter` starts an 80ms timeout; `mouseleave` clears it and removes the class. The base `cursor` declaration stays on the element (instant, no delay). The `.active` class (applied during drag) bypasses the delay entirely. **Apply this pattern to any narrow interactive zone where casual traversal would cause distracting flicker.**

### 3.5 Cognitive principles proven in practice

**1. Implied mass through velocity difference.** When content moves at a different velocity than its container, the visual system infers the content has its own physical mass. A rigid slide reads as a flat graphic being moved; a staggered slide reads as a physical drawer with things inside it.

**2. Easing curves encode force.** `ease-out` → friction (something slowed it down). `ease-in` → applied force (something pushed it). The human motor system maps these curves to physical experience. These aren't aesthetic choices — they're *semantic*.

**3. Cross-fade as identity preservation.** Two objects that occupy the same space and swap via overlapping fade are perceived as one object transforming. The 40ms overlap window is tight but sufficient.

**4. Matched speeds across interaction modes.** Push mode (grid transition) and overlay mode (clip-path) must both be 75ms. Mismatched speeds make one path feel broken. *Every path to the same visual state should take the same time.*

### 3.6 Three-element transition vocabulary

The sidebar established a general pattern for any compound transition:

| Phase | Element type | Timing | Easing | Example |
|-------|-------------|--------|--------|---------|
| First ~50% | **Departing** elements | Fast, starts at 0ms | `ease-in` (accelerate away) | Rail icon fades out (0-40ms) |
| Full duration | **Container** transformation | Full duration, starts at 0ms | `ease-out` (enter) or `ease-in` (exit) | Panel clip-path reveal (0-75ms) |
| Last ~50% | **Entering** elements | Fast, delayed until departing clears | `ease-out` (settle in) | Close × sneaks in (40-75ms) |

This vocabulary recurs in modals (overlay fades → card scales in), dropdowns (trigger pulses → menu floats down), and tab switches (old content fades → new content fades in).

---

## 4. A Taxonomy of State Changes (What Needs Communicating)

Every state transition in the UI falls into one of these **semantic categories**. Each category gets its own physical metaphor.

### 4.1 REVEAL / CONCEAL — "Opening a drawer"

**What it communicates:** Something was always there, behind/below/beside. You're pulling it into view or pushing it away. Spatial relationship is preserved.

**Physics:** Slide along the axis the object lives on. The object decelerates as it arrives (settling into place) and accelerates as it leaves (being pushed away).

**Easing:** Open: `ease-out` (decelerate to rest). Close: `ease-in` (accelerate away).

**Technique:** Use `clip-path: inset()` for GPU-composited, layout-free reveals. Use `grid-template-columns` transition for push-mode layout shifts. Both at 75ms.

| # | Element | States | Axis | Duration | Status |
|---|---------|--------|------|----------|--------|
| R1 | **LHS TOC sidebar (push)** | closed / open | X | 75ms | ✓ Done — grid column transition |
| R2 | **LHS TOC sidebar (overlay)** | closed / open / closing | X | 75ms | ✓ Done — clip-path reveal + icon cross-fade |
| R3 | **RHS tag sidebar** | closed / open | X | 75ms | ✓ Done — grid column transition |
| R4 | **Modal overlay + card** | hidden / visible | Z (scale + opacity) | 200ms | Partial — overlay fades, card is instant |
| R5 | **Dropdown menus** (tag filter, view switcher, hidden-quotes, counter) | closed / open | Y (drops down) | 150ms | **No — instant** |
| R6 | **Tag suggest dropdown** | closed / open | Y (drops down) | 120ms | **No — instant** |
| R7 | **Help modal** | hidden / visible | Z (scale + opacity) | 200ms | **Partial — card instant** |
| R8 | **Feedback modal** | hidden / visible | Z (scale + opacity) | 200ms | **Partial** |
| R9 | **Codebook group body** | collapsed / expanded | Y (content height) | 200ms | **No — native `<details>`** |
| R10 | **Hidden-quotes dropdown** | closed / open | Y (drops down) | 150ms | **No — instant** |
| R11 | **Moderator question pill** | hidden / revealed | Y (slides up) | 200ms | ✓ Done (mod-q-reveal) |

### 4.2 ACKNOWLEDGE / CONFIRM — "Pressing a key on a piano"

**What it communicates:** Your action was received. The thing you acted on *felt* your touch. Brief, immediate, proportional.

**Physics:** Momentary displacement + return. Scale, brightness, or colour pulse that peaks fast and decays slowly.

**Easing:** `ease-out` for the attack (fast peak), natural decay back to rest.

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| K1 | **Star toggle** | unstarred / starred | Icon fills + brief scale pulse (1→1.15→1) | 200ms | **No — instant icon swap** |
| K2 | **Badge accept** (proposed→confirmed) | proposed / accepted | Brightness flash (1→1.35→1) | 400ms | ✓ Done (badge-accept-flash) |
| K3 | **Badge bulk-apply** (quick-repeat `r`) | normal / flashing | Box-shadow ring pulse | 800ms | ✓ Done (badge-bulk-flash) |
| K4 | **Eye toggle** (hide/show badge group) | open / closed | Icon swap + brief opacity dip on affected badges | 150ms | **No — instant swap** |
| K5 | **Sidebar rail button click** | rest / pressed | Brief scale dip (1→0.92→1) | 120ms | **No** |
| K6 | **Export button** | rest / pressed / downloading | Scale dip on press, then activity indicator | 120ms + spinner | **No** |
| K7 | **Copy-to-clipboard** | rest / copied | Brief checkmark flash or colour pulse | 200ms | Partial (toast, but trigger has no feedback) |

### 4.3 ENABLE / DISABLE — "Flipping a power switch"

**What it communicates:** Something was off, now it's on. A capability changed. Nothing moves spatially — a *property* changes.

**Physics:** Snap with brief settle. Like a physical switch with a detent — fast through the middle, lands firmly. Brevity communicates decisiveness.

**Easing:** `ease` (symmetric, crisp).

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| S1 | **View mode toggle** (all / starred) | all / starred | Active segment background slides to new position | 200ms | **No — instant class swap** |
| S2 | **Appearance toggle** (light / dark) | light / dark | Cross-fade (opacity swap on data-theme) | 200ms | **No — instant** |
| S3 | **Sentiment filter buttons** | unselected / selected | Background + colour transition | 150ms | **No — instant** |
| S4 | **Checkbox** (settings, config) | unchecked / checked | Border + background transition + scale pulse on check icon | 150ms | Partial |
| S5 | **Toggle switch** (code+name / code-only) | off / on | Track + thumb slide | 200ms | Partial |

### 4.4 FOCUS / SELECT — "Picking up an object"

**What it communicates:** This item is now the subject of your attention. It's been lifted out of the crowd. Your *relationship* to it changes, not the item itself.

**Physics:** Elevation change. Shadow deepens, edges become more defined. Gentle lift and equally gentle set-down.

**Easing:** `ease` (symmetric).

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| F1 | **Quote focus** (j/k navigation) | unfocused / `.bn-focused` | Box-shadow deepens, background lightens | 150ms | **No — instant class toggle** |
| F2 | **Quote selection** (space / shift) | unselected / `.bn-selected` | Blue tint + left border colour | 150ms | **No — instant class toggle** |
| F3 | **TOC active item** (scroll-spy) | inactive / `.active` | Font-weight + background + colour | 150ms | Partial (colour transitions, font-weight instant) |
| F4 | **Nav tab active** | inactive / active | Border-bottom + colour | 150ms | ✓ Done (colour + border transition) |
| F5 | **Stat card hover** (dashboard) | rest / hover | Box-shadow + translateY(-1px) lift | 150ms | Partial (shadow, no lift) |

### 4.5 APPEAR / DISAPPEAR — "Materialising / dissolving"

**What it communicates:** Something new entered the scene, or left. No spatial origin — the item doesn't "live" anywhere when absent.

**Physics:** Fade + slight scale. Objects grow from ~95% to 100% while opacity rises. The slight scale implies "forming" rather than being switched on.

**Easing:** Enter: `ease-out`. Exit: `ease-in`.

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| M1 | **Badge appear** | absent / present | Scale(0.85→1) + opacity | 150ms | ✓ Done |
| M2 | **Badge remove** | present / absent | Scale(1→0.85) + opacity | 150ms | ✓ Done |
| M3 | **Toast notification** | absent / visible / dismissing | SlideY(-8px→0) + opacity | 250ms | ✓ Done |
| M4 | **Activity chip** | absent / present | SlideY + opacity | 200ms | ✓ Done |
| M5 | **Search highlight `<mark>`** | absent / present | Best left instant (typing latency) | N/A | Skip |
| M6 | **Error state text** | absent / present | Opacity fade-in + subtle red flash | 200ms | **No — instant** |
| M7 | **Empty→populated content** (API data load) | loading / loaded | Opacity fade-in on container | 200ms | **No — instant** |
| M8 | **Counter value change** (stat cards, tag counts) | N / N+1 | Brief scale pulse (1→1.05→1) | 150ms | **No — instant** |

### 4.6 REMOVE / UNDO — "Sweeping off the table"

**What it communicates:** This item is being taken away, but the action is reversible. The animation conveys both *departure* and *recoverability*.

**Physics:** Collapse with grace. Shrinks vertically while fading, as if folding into a pocket. Undo reverses — unfolds back into place.

**Easing:** Exit: `ease-in`. Re-enter: `ease-out`.

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| U1 | **Quote hide** | visible / `.bn-hiding` / `.bn-hidden` | Max-height collapse + opacity + margin shrink | 300ms | ✓ Done |
| U2 | **Quote unhide** | hidden / visible | Reverse collapse | 300ms | ✓ Done |
| U3 | **Bulk quote hide** (multi-select) | visible / hiding | Staggered collapse (150ms between cards) | 300ms + stagger | ✓ Done |
| U4 | **Quote filter-out** (search/tag filter) | visible / filtered-away | Opacity→0, then display:none | 100ms | **No — instant** |
| U5 | **Quote filter-in** (clearing filter) | filtered-away / visible | Opacity fade-in, staggered 30ms | 100ms + stagger | **No — instant** |

### 4.7 CONTINUOUS FEEDBACK — "Engine idle"

**What it communicates:** A process is running. The system is alive and working.

**Physics:** Rhythmic oscillation. Gentle, organic breathing cadence — sinusoidal, not mechanical.

**Easing:** `ease-in-out` for oscillations. `linear` for spinners.

| # | Element | States | Effect | Duration | Status |
|---|---------|--------|--------|----------|--------|
| L1 | **Proposed badge pulse** | idle / pulsing | Opacity oscillation | 3s infinite | ✓ Done |
| L2 | **Timecode glow** | idle / playing | Box-shadow pulse | 2s infinite | ✓ Done |
| L3 | **Timecode progress bar** | 0%→N% | Left-border scaleY fill | 250ms linear | ✓ Done |
| L4 | **AutoCode spinner** | idle / spinning | Rotation | 800ms linear infinite | ✓ Done |
| L5 | **Activity chip spinner** | idle / spinning | Rotation | linear infinite | ✓ Done |
| L6 | **Word-level highlight** (karaoke) | inactive / active | Background highlight | Instant (perf) | ✓ Done |

---

## 5. Existing Animation Inventory

### 5.1 Keyframe animations (22 total)

**Sidebar (8) — `organisms/sidebar.css`:**

| Animation | Category | Duration | Delay |
|---|---|---|---|
| `toc-reveal` | Reveal | 75ms ease-out | 0 |
| `toc-hide` | Conceal | 75ms ease-in | 0 |
| `toc-icon-depart` | Cross-fade | 40ms ease-in | 0 |
| `toc-icon-return` | Cross-fade | 40ms ease-out | 40ms |
| `toc-close-sneak-in` | Cross-fade | 40ms ease-out | 40ms |
| `toc-close-sneak-out` | Cross-fade | 40ms ease-in | 0 |
| `toc-ios-settle` | Inertia | 65ms custom | 10ms |
| `toc-ios-depart` | Inertia | 50ms ease-in | 0 |

**Badge (5) — `atoms/badge.css`:**

| Animation | Category | Duration |
|---|---|---|
| `bn-proposed-pulse` | Continuous | 3s infinite |
| `badge-accept-flash` | Acknowledge | 0.4s |
| `badge-fade-in` | Appear | 0.15s |
| `badge-fade-out` | Disappear | 0.15s |
| `badge-bulk-flash` | Acknowledge | 0.8s |

**Other (9):**

| Animation | File | Category | Duration |
|---|---|---|---|
| `bn-glow-pulse` | `atoms/timecode.css` | Continuous | 2s infinite |
| `autocode-spin` | `atoms/autocode-toast.css` | Continuous | 0.8s |
| `chip-slide-in` | `atoms/activity-chip.css` | Appear | 0.2s |
| `chip-spin` | `atoms/activity-chip.css` | Continuous | infinite |
| `bracket-fade-in` | `molecules/editable-text.css` | Reveal | 0.15s |
| `mod-q-reveal` | `atoms/moderator-question.css` | Reveal | 0.2s |
| `cell-tooltip-in` | `organisms/analysis.css` | Appear | 0.12s |
| `anchor-fade` | `templates/transcript.css` | Acknowledge | 5s |
| `content-settle` | `organisms/sidebar.css` | Inertia | 65ms (iOS variant only) |

### 5.2 Design tokens

```
--bn-transition-fast:   0.15s ease     (micro-interactions)
--bn-transition-normal: 0.2s ease      (standard transitions)
--bn-transition-slow:   0.3s ease      (larger layout changes)
--bn-overlay-duration:  0.075s         (sidebar overlay — playground-scalable)
--bn-overlay-shadow:    4px 0 16px rgba(0,0,0,0.08)
```

### 5.3 Accessibility state

**`prefers-reduced-motion` coverage:**
- ✓ Sidebar: all 8 keyframes + grid transition + overlay sub-animations (comprehensive block in `sidebar.css`)
- ✓ Timecode: glow pulse, progress bar, word highlight (3 blocks in `timecode.css`)
- ✗ Badges: 5 keyframes unguarded
- ✗ Activity chip: slide-in + spin unguarded
- ✗ Bracket fade-in, moderator reveal, analysis tooltip, anchor fade: unguarded
- ✗ ~100 transition declarations across theme: no guards
- **Recommendation:** add a single global rule in `tokens.css`

---

## 6. Duration & Easing Reference

### By semantic category

| Category | Physics | Entrance easing | Exit easing | Duration range |
|---|---|---|---|---|
| Reveal/Conceal | Slide along home axis | `ease-out (0,0,0.2,1)` | `ease-in (0.4,0,1,1)` | 75-200ms |
| Acknowledge | Momentary displacement | `ease-out` | Natural decay | 120-400ms |
| Enable/Disable | Snap with detent | `ease` | `ease` | 150-200ms |
| Focus/Select | Elevation change | `ease` | `ease` | 100-150ms |
| Appear/Disappear | Materialise/dissolve | `ease-out` | `ease-in` | 100-200ms |
| Remove/Undo | Collapse/unfold | `ease-in` | `ease-out` | 200-300ms |
| Continuous | Breathing/oscillation | `ease-in-out` | — | 800ms-3s per cycle |

### By size of change

| Magnitude | Duration | Examples |
|---|---|---|
| Micro (colour, opacity, icon swap) | 40-150ms | Hover states, focus rings, icon cross-fade (40ms) |
| Small (dropdown, badge, tooltip) | 75-200ms | Sidebar overlay (75ms), dropdown open, badge lifecycle |
| Medium (modal, quote, tab switch) | 200-350ms | Modal entrance, quote collapse, tab cross-fade |
| Sequence (multiple items) | Base + 30-50ms stagger | Filtered quotes, bulk badge apply |

### Named easing curves

| Name | Value | When to use |
|---|---|---|
| Standard enter | `cubic-bezier(0, 0, 0.2, 1)` | Panel reveals, content arriving |
| Standard exit | `cubic-bezier(0.4, 0, 1, 1)` | Panel conceals, content departing |
| Inertia settle | `cubic-bezier(0.25, 0.46, 0.45, 0.94)` | Heavy object coming to rest (iOS content) |
| Symmetric | `ease` | Toggle states, focus/blur |
| Linear | `linear` | Spinners, progress fills |

### Stagger formula

For N items animating: `stagger = min(50ms, 300ms / N)`. Cap total stagger at 300ms.

---

## 7. Implementation Notes (for future sessions)

### Quick wins (CSS-only, no JS changes)

- **Quote card base transition** — add `transition: background, border-left-color, box-shadow` to `.quote-card` in `organisms/blockquote.css`. Instantly animates F1 (focus) and F2 (selection) with zero JS changes
- **Modal card entrance** — `scale(0.96→1) + opacity` on `.bn-modal` when `.bn-overlay.visible` in `atoms/modal.css`. Use the three-element vocabulary: overlay fades (container), card scales in (entering element)
- **Global reduced-motion rule** — single catch-all in `tokens.css` covers all unguarded animations

### Pattern work (one pattern, applied everywhere)

- **Dropdown animation pattern** — convert 5 dropdown menus from `display:none` to `opacity + visibility + transform`. Consider using `clip-path: inset()` (proven technique from sidebar) instead of `transform: translateY()` for GPU compositing. Write the CSS once, apply to all 5

### Requires JS coordination

- **Star toggle pulse** (K1) — CSS class applied briefly on click, 200ms
- **View mode segment slide** (S1) — sliding background element positioned by JS
- **Quote filter stagger** (U4/U5) — stagger delay calculation when filter results change
- **Counter pulse** (M8) — detect value changes, apply transient class

### CSS techniques to reuse from sidebar

| Technique | When to use |
|---|---|
| `clip-path: inset()` reveal | Any panel or drawer reveal (GPU-composited, layout-free) |
| Negative inset for shadow | `inset(0 -100px 0 0)` — whenever shadow must paint beyond clip |
| Cross-fade icon swap | Any icon↔icon toggle at same position (depart 40ms → enter 40ms) |
| iOS inertia variant | Content settling into a container that arrived ahead of it |
| Deferred class on pointermove | Any drag-to-reveal where the reveal class would flash on pointerdown |
| `animationend` + fallback timeout | Any JS-coordinated animated close (120ms timeout catches edge cases) |

---

## 8. Key Files

| File | Relevance |
|---|---|
| `bristlenose/theme/tokens.css` | Motion tokens, global reduced-motion rule |
| `bristlenose/theme/organisms/sidebar.css` | Reference implementation: clip-path reveal, icon cross-fade, reduced-motion block |
| `bristlenose/theme/atoms/modal.css` | Modal card entrance/exit animation |
| `bristlenose/theme/organisms/blockquote.css` | Quote card base transition for focus/selection |
| `bristlenose/theme/molecules/tag-filter.css` | Dropdown animation pattern (template for all 5) |
| `bristlenose/theme/organisms/toolbar.css` | View switcher dropdown + view mode segment slide |
| `bristlenose/theme/molecules/hidden-quotes.css` | Hidden-quotes dropdown animation |
| `bristlenose/theme/molecules/tag-input.css` | Tag suggest dropdown animation |
| `bristlenose/theme/atoms/interactive.css` | `.bn-no-animations` kill switch |
| `bristlenose/theme/atoms/badge.css` | Reduced-motion guards for 5 badge animations |
| `frontend/src/components/SidebarLayout.tsx` | Reference implementation: overlay animation orchestration, deferred class pattern |
| `frontend/src/hooks/useDragResize.ts` | Drag-to-open, snap thresholds, pointer-event state machine |
| `frontend/src/hooks/useTocOverlay.ts` | Hover intent, safe zones, direction-aware close |

---

## 9. Verification Checklist (for any animation work)

- **Semantic match:** Does the animation match its category's physics? (Reveal slides, Acknowledge pulses, Focus lifts, etc.)
- **Duration proportionality:** Does the timing feel right relative to the sidebar's 75ms baseline? (Heavier changes = more time, not less)
- **Easing correctness:** Enter = ease-out (decelerate to rest). Exit = ease-in (accelerate away). Toggle = ease (symmetric)
- **Reduced motion:** Test with `prefers-reduced-motion: reduce` — no animation blocks interaction, elements reach final state instantly
- **Interruptibility:** Rapidly toggle the element — never stuck in intermediate state
- **Performance:** Chrome DevTools Performance tab — no jank (>16ms frames) during animation. Prefer compositor properties (`transform`, `opacity`, `clip-path`) over layout properties (`width`, `height`, `margin`)
- **Tests:** `cd frontend && npm test` + `.venv/bin/python -m pytest tests/` + `cd frontend && npm run build` (tsc)
- **E2E:** `cd e2e && npm test` — Playwright layers 1-3
