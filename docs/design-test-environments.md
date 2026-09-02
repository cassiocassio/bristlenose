---
status: current
last-trued: 2026-09-02
trued-against: HEAD@main on 2026-09-02
---

## Changelog

- _2026-09-02_ — initial draft. Written when supporting three simultaneous
  macOS sidebar geometries (Sequoia 15 flat, Tahoe 26 inset plateau, Golden
  Gate 27 edge-anchored-again) made "which machine can actually prove this?"
  a question with no doc to answer it. The EULA VM clause and the deployment-
  target policy are quoted from source; the Metal-degradation caveat in §3.2 is
  explicitly marked unverified, with the check that settles it.

# Test environments — the instruments, and what each one is blind to

## What this is

The machines and OS versions Bristlenose can actually be tested on, and — the
point of the doc — **what each one can and cannot prove**. An environment is an
instrument. Every instrument has a blind spot, and a blind spot you have not
written down is one you will eventually mistake for a passing test.

Three neighbouring docs, deliberately not this one:

| Doc | Asks |
|---|---|
| [`design-deployment-targets.md`](design-deployment-targets.md) | Where is Bristlenose *expected to run*? (what users have) |
| [`testing/README.md`](testing/README.md) | What *kinds* of test exist? (CI · Playwright · acceptance · human walk) |
| **this doc** | What *hardware and OS* can run them, and what does each one lie about? |

## 1. Why this exists now

Three macOS sidebar geometries are live at once, and the deployment target says
we support the oldest of them:

| Host | Sidebar geometry | Our code path |
|---|---|---|
| **15 Sequoia** | edge-anchored, flat | current CSS — tuned for exactly this |
| **26 Tahoe** | inset floating plateau, rounded, shadowed | `backgroundExtensionEffect()` |
| **27 Golden Gate** | edge-anchored again, refraction continues beneath | same call; Apple owns the difference |

The deployment target is **macOS 15.0, project-level** — measured by walking
every `XCBuildConfiguration` in `project.pbxproj`, not by grepping it. The two
`26.1` hits belong to **`BristlenoseTests`** and nothing else, so
[`design-platform-policy.md:61`](design-platform-policy.md:61)'s *"26.1 for some
debug/feature schemes"* overstates it; `desktop/CLAUDE.md` names the same trap
(the `26.1` pair sorts before the `15.0` pair, so the first grep hit is the
wrong answer). [`design-platform-policy.md:96`](design-platform-policy.md:96)
sets the review trigger: *"When Sequoia becomes n-2 (autumn 2026 if macOS 27
ships on time)."* So the three-way support window is real, bounded, and already
has an agreed exit.

The hard part is not the code — it is two branches, and the Sequoia arm is
"change nothing". The hard part is that **the question the branches exist to
answer is a visual one**, and visual questions are the ones a virtual machine is
worst at.

## 2. The environments

| Environment | Have it? | Proves | Blind to |
|---|---|---|---|
| **macOS 26 Tahoe, Apple Silicon, bare metal** | ✅ daily driver | everything, at full fidelity | other OS versions |
| **macOS 15 Sequoia, VM** | ⬜ to build | geometry, behaviour, launch, regressions | Liquid Glass fidelity (§3.2); anything needing an Apple ID (§3.3) |
| **macOS 27, bare metal** | ⬜ when beta lands | the 27 rendering | — |
| **Linux x86_64, GitHub Actions** | ✅ | CI matrix, packaging, release pipeline | anything GUI; no LLM keys, no Ollama |
| **Claude Code Cloud VM** | ✅ | code/test/lint/frontend build | GUI; **not for pipeline runs on private interview data** |
| **Fedora 43 x86_64** | ✅ real Intel hardware | Copr packaging end to end | GUI |
| **`aella` amd64 boxes** | ✅ on demand | amd64 Linux behaviour | GUI |

## 3. macOS specifics

### 3.1 You may run two VMs, and it is licensed for exactly this

macOS EULA §2B(iii) permits installing and running **up to two additional
instances** of macOS in virtual environments per Mac you own, explicitly for
*"(a) software development; (b) testing during software development"*. Our use
is squarely inside the grant. The limit is not honour-system — it is enforced in
the kernel via `hv_apple_isa_vm_quota`.

**Host + 2 VMs = 3 macOS environments on one machine**, which happens to be
exactly the number of geometries we support. Tooling options all sit on
Virtualization.framework: `tart`, VirtualBuddy, UTM.

The grant excludes service-bureau / time-sharing use, so this covers a dev box
and not a rented CI fleet.

### 3.2 ⚠️ A VM may degrade the exact effect under test — UNVERIFIED

A macOS guest under Virtualization.framework gets a paravirtual GPU backed by
the host's. Reports indicate a stock Tahoe VM advertises a **conservative Metal
capability profile**, and both apps and the OS select rendering paths from those
capability reports. Liquid Glass, vibrancy, backdrop blur and refraction are
precisely the effects that would degrade.

If true, a VM can show a seam defect that is not in our code, or hide one that
is. Same shape as the pipe-vs-TTY trap in the root `CLAUDE.md`: **the instrument
suppresses the thing under test.**

**This is not verified on our hardware.** It rests on secondary sources, and it
is cheap to settle: build one Tahoe VM, open Diagnostics ▸ Seam Lab on both the
VM and the host against the same project, and compare the readouts and the
rendering. Do that before trusting any visual verdict from a VM. Record the
answer here.

### 3.3 Apple Silicon VMs cannot sign in to an Apple ID

No iCloud, no App Store, no TestFlight. Consequences for us:

- **Cloud grants are untestable in a VM** — they live in the iCloud Keychain
  (`synchronizable: true`), by decision.
- TestFlight install/update flows are untestable in a VM.
- A VM runs a locally-signed Debug build fine, which is what the Seam Lab needs.

### 3.4 A Mac cannot boot a macOS older than the build it shipped with

Which is why Sequoia is likely **VM-only** on current hardware, external boot
volume or not. Conveniently, Sequoia is also the version where the visual
question is trivial — the branch does nothing new there, so the test is
*absence of change*, and a degraded GPU profile cannot corrupt that verdict.

An external SSD with a second install does boot natively with full GPU, and is
the cheap path to real metal for a **newer** OS (27 when it lands) — an SSD
rather than a second Mac. Cost: a reboot to switch.

### 3.5 The split that falls out

| Question | Instrument |
|---|---|
| Safe-area insets, view-tree frames, corner radii, material names | VM is fine — numbers, not pixels |
| Does it launch, do the menus wire, non-visual regressions | VM is fine |
| **How the glass and the seam actually look** | bare metal only |
| Anything touching an Apple ID | bare metal only |

The reassuring shape: the OS where visual fidelity matters most (26, then 27) is
the one we run natively. The one that needs a VM (15) is the one where "nothing
changed" is the whole test.

## 4. The instrument for the seam question

**Diagnostics ▸ Seam Lab**
([`SeamLabView.swift`](../desktop/Bristlenose/Bristlenose/SeamLabView.swift),
DEBUG-only) exists because the numbers must be *read* on each host rather than
assumed once. It reports, for the running window:

- `webView.safeAreaInsets.top` — how far up a panel must bleed to reach the
  window top; the value `BridgeHandler.syncToolbarInset` computes and discards
- the window frame-minus-`contentLayoutRect` delta, and the `residual` the
  bridge actually posts
- every `NSVisualEffectView`'s frame, inset from each window edge, layer
  `cornerRadius` and material — i.e. whether this OS draws an inset plateau or
  an anchored panel, measured rather than eyeballed

Its **Copy metrics** button is the transport: one run per host turns three
opinions into three readouts, and the availability branch gets written against
measurements. Paste each host's readout into this doc as it is captured.

| Host | Readout captured |
|---|---|
| macOS 26.4.1 (dev machine) | ⬜ pending — lab built 2 Sep 2026, not yet run |
| macOS 15 Sequoia | ⬜ |
| macOS 27 | ⬜ |

## 5. Non-macOS

- **Linux CI** — Ubuntu runners, GNU userland, no API keys and no Ollama, so
  every environment-dependent test must mock. The v0.6.7–v0.6.13 release
  failures were all local-passes/CI-fails of exactly this kind.
- **Claude Code Cloud VM** — ephemeral Ubuntu x86_64, verified Apr 2026. Good
  for code, tests, lint and frontend builds. **Not** for pipeline runs on
  private interview data — the use-case boundary is in
  [`design-deployment-targets.md`](design-deployment-targets.md).
- **Fedora 43** — the Copr channel was proven on a clean F43 box before the docs
  went live; see [`design-fedora-packaging.md`](design-fedora-packaging.md) §7.
- **`aella` amd64 boxes** — on-demand amd64 Linux, brought up and torn down per
  use.

## 6. Open

1. **§3.2 is unverified.** Settle it before any VM-sourced visual verdict.
2. **No Sequoia environment exists yet.** Until one does, the macOS 15 arm of
   the availability branch is unexercised — it is "change nothing", which is the
   safest possible unexercised branch, but it is still unexercised.
3. **No macOS 27 environment**, and none possible until the beta is installable.
4. **Nothing here is automated.** These are instruments for the human walk and
   for one-off measurement, not a matrix that runs nightly. Whether any of it
   should join the mechanical tier is an
   [`testing/acceptance-matrix.md`](testing/acceptance-matrix.md) question,
   deliberately not answered here.

## See also

- [`design-platform-policy.md`](design-platform-policy.md) — the OS floor, its
  rationale, and the review trigger
- [`design-deployment-targets.md`](design-deployment-targets.md) — where the
  product is expected to run
- [`testing/README.md`](testing/README.md) — the three-tier model
- [`design-native-colour-alignment.md`](design-native-colour-alignment.md)
  §Principles — why OS-owned values are bridged and not sampled; the same logic
  that makes the Seam Lab measure rather than hardcode
- [`docs/mockups/sidebar-seam-window-edge.html`](mockups/sidebar-seam-window-edge.html)
  — the seam study the lab was built to settle empirically
- The by-hand walk lives in the maintainer's private QA notes, kept outside the
  public tree
