---
status: proposed
updated: 3 Oct 2026
---

# Voice diarization: telling speakers apart by how they sound

Companion to [design-speaker-splitting.md](design-speaker-splitting.md), which
chose text-only LLM splitting in April 2026 and listed acoustic diarization as
"Future". This doc is the research for that future: what tools exist, what each
costs Bristlenose to ship, and how voice turns would join the existing
stage 5 / 5b data flow. Everything marked **MEASURED** was run on the
Talismanic project on 3 Oct 2026. **PUBLISHED** means a benchmark someone else
ran. **INFERRED** is reasoning, not measurement.

## TL;DR

**4 Oct 2026, scored against a Teams transcript's named turns:** voice plus the shipped text splitter gets about 45% fewer segments wrong than the text splitter alone (22 → 12 of 286), and on lines long enough to quote, 12 → 4 (§ Measured against platform ground truth). The points below predate that measurement.

1. **Voice beats the shipped splitter on our own data, without hand labels.**
   On the 36-minute Talismanic session (s2), the shipped opening-sample
   splitter gives the moderator **86 %** of talk time. A local voice method
   (pyannote segmentation + TitaNet embeddings, no torch) gives **33 %**. The
   whole-transcript LLM, a different method on a different signal, gives
   **37 %**. Two independent methods agree; the shipped one is the outlier.
   (MEASURED)
2. **Voice and text fail differently, so they combine well.** Voice mislabels
   short utterances and segments that contain both people. Text mislabels
   flat back-and-forth with no cues. Reading 30 random voice-vs-text
   disagreements on s2, voice was right on most of the clear ones, and the
   unclear ones were mostly segments holding both voices. (INFERRED from a
   read, not hand labels)
3. **Whisper segments do contain both voices.** 14–43 of 377 segments on s2,
   and 19 of 238 on s1, carry two or more words attributed to the other voice.
   Only word timings plus audio can re-cut those; no text method can. (MEASURED)
4. **The embedding model matters more than anything else.** Same pipeline,
   same audio: WeSpeaker and 3D-Speaker collapsed s2 to a 97/3 and 92/8 split.
   TitaNet-small separated it 62/38. (MEASURED)
5. **It is cheap.** Embedding each Whisper segment and clustering takes
   **~0.005× real time on CPU**: about 11 s for 36 minutes of audio. The code
   (sherpa-onnx) is 37 MB with its own onnxruntime, with no torch, no numba
   and no subprocess. The models are 6 MB + ~40 MB. (MEASURED) _The shipped
   pass runs on onnxruntime + kaldi-native-fbank instead, since 4 Oct 2026
   (§ Licence)._

**Recommendation:** run the first experiment below (free, local, ~1 hour of
labelling). If it confirms the agreement figures against hand labels, build
**Option A**: an ONNX voice pass in Python, on every channel, feeding the
existing LLM role pass. Keep **Option B** (FluidAudio, CoreML in the Swift
host) as the Mac quality upgrade, and **Option E** (pyannoteAI hosted
diarization) as an opt-in for researchers who already send audio to the
cloud. Do not take torch back into the sidecar for this.

## Where we are

- Bare audio/video → Whisper (`s05_transcribe.py`), which yields text,
  segment timings and **word timings on both backends**
  (`word_timestamps=True` at `s05_transcribe.py:457` and `:607`), but no
  speaker identity.
- `split_gate()` → `split_single_speaker_llm()` guesses speaker changes from
  the text: the whole transcript, in parts, since 3 Oct 2026. Before that it
  read the first 5–8 minutes and carried the last label to the end.
- `identify_speaker_roles_heuristic()` then `identify_speaker_roles_llm()`
  assign roles and names, then `assign_speaker_codes()` runs, then
  `s06_merge_transcript` merges adjacent same-speaker segments.
- Words survive until stage 7, which clears them (`s07_pii_removal.py:388`).
  So a voice pass at 5b has everything it needs. The speaker-info cache
  already stores words: 4,003 words on s2.
- Platform transcripts (Teams/Zoom/Meet) skip the splitter. The
  one-account-two-people-in-a-room case arrives as `SplitGate.NOT_SEPARATED`,
  and platform cues carry **no word timings**. Voice could relabel whole cues
  there, but could not re-cut them without re-transcribing the audio. That
  is a second, later case. This doc is about the Whisper path first.
- No diarization model is bundled anywhere. `grep diariz|pyannote` finds only
  the April doc.

## What we measured (3 Oct 2026, Talismanic s1 and s2)

The scripts and per-segment output are kept locally, gitignored, beside the
30 Sep labelling run; they contain transcript text. Ground truth was not
available, so the comparison is against the two LLM methods from that 30 Sep
run. The role mapping for voice clusters is the better of the two
permutations (an oracle mapping). In the product, the LLM role pass would
make that call.

**Moderator share of talk time**

| Session | Shipped (opening sample) | Whole-transcript LLM | Voice (TitaNet, per segment) |
|---|---|---|---|
| s1, 18 min, Teams recording (by filename) | 7 % | 21 % | 23 % |
| s2, 36 min, Meet recording (by filename) | **86 %** | 37 % | 33 % |

**Agreement with the whole-transcript LLM (share of segment time)**

| Method | s1 | s2 | Time for s2 (36 min audio, 4 CPU threads) |
|---|---|---|---|
| A1: sherpa-onnx full diarizer, WeSpeaker, k=2 | 87 % | 62 % (collapsed 97/3) | 271 s |
| A1: …3D-Speaker ERes2Net, k=2 | n/a | 63 % (collapsed 92/8) | 277 s |
| A1: …TitaNet-small, k=2 | n/a | 72 % (62/38) | 132 s |
| **A2: embed each Whisper segment, TitaNet, 2-means** | **92 %** | **75 %** | **~11 s** |
| A2: …WeSpeaker | 79 % | 61 % | ~25 s |

What the numbers say:

- **The collapse is a known weakness of plain agglomerative clustering.** With
  a fixed k=2, the "other speaker" became 50 blips of 0.3–2 s (backchannels,
  noise), and every moderator turn landed with the participant. pyannote's
  community-1 adds VBx clustering for exactly this reason.
- **Clustering Whisper segments avoids it.** Fitting only on segments ≥ 2 s
  and assigning shorter ones to the nearest centroid avoids the outlier trap.
  It is also 25× faster, because it embeds ~350 spans instead of sliding
  windows.
- **The model can report its own confidence:**
  - The cosine between the two centroids was 0.41 (s2) and 0.62 (s1) for
    TitaNet, and 0.95 for WeSpeaker on s2. Near 1 means "I found one voice",
    which is a usable gate for "don't trust me here".
  - The per-segment margin (difference in cosine to the two centroids) had a
    median of 0.41 on disagreements against 0.56 on agreements. The
    low-margin disagreements were mostly segments containing both voices.
- **A Meet recording is harder than a Teams one.** That is consistent with
  both voices passing through the same codec and the same room-less mix, but
  it is one session each. (INFERRED)

Not measured: overlap handling, 3-speaker sessions, in-room single-mic
recordings, non-English audio, Apple Silicon ANE speed, pyannote community-1
itself. The first experiment below covers the ones that matter most.

## Options, ranked

### A. ONNX voice pass in Python, every channel (recommended first build)

**Runtime since 4 Oct 2026 (later the same day): onnxruntime + kaldi-native-fbank,
not sherpa-onnx** — the owner's call from § Licence, because sherpa's published
wheels statically link espeak-ng (GPL-3.0-or-later). `s05b_voice._TitaNet` runs the
same TitaNet-small file through the `onnxruntime` package with sherpa's NeMo front
end (kaldi-native-fbank features, per-feature normalisation, no padding). Through
the shipped code it matches sherpa on every 3 s window of two public FOSSDA
interviews — 794/794 and 788/788 verdicts, worst embedding cosine 1.000000 — and is
slightly faster (15.1 s against 17.0 s); `experiments/voice_onnx_equivalence/`
re-runs that check. `VOICE_VERSION` stays `1`: the output did not change. The `voice`
extra is now `onnxruntime` (already core through faster-whisper) and
`kaldi-native-fbank`; the Mac sidecar ships onnxruntime's Python binding and drops
its unused 33 MB C library — measured in a built sidecar: 39 MB of onnxruntime
where sherpa's 37 MB was, plus 0.56 MB of kaldi-native-fbank, no sherpa and no
`libonnxruntime.*.dylib`; `doctor --self-test` in the frozen bundle printed
`✓ Bundle: voice  onnxruntime 1.30.0 and kaldi-native-fbank 1.22.3 load`, and a
real `run` through the frozen binary (a 4-minute FOSSDA cut, Homebrew ffmpeg via
`BRISTLENOSE_FFMPEG` because the bundled one is sandbox-signed) logged
`voice_pass | method=voice+text`, 39 of 41 segments judged, 1 relabelled, centroid
cosine 0.104, 1.7 s. **Linux, measured the same day** in a throwaway Ubuntu 24.04
arm64 VM (Multipass, Python 3.12): a wheel built from the commit installed with
`[voice]` pulls `onnxruntime` 1.30.0 and `kaldi-native-fbank` 1.22.3 and no sherpa;
`check_bundle_voice` passes; `compare.py` against sherpa 1.13.8 on the 4-minute cut gave
80/80 verdicts, worst cosine 1.000000, 5.1 s against sherpa's 9.6 s; and
`nm -D --defined-only` over all 208 shared objects in that install found **0**
`espeak_` symbols, where sherpa's own extension in the same VM shows 50. The Snap
and the Copr RPM carry one onnxruntime instead of two. As packages: the arm64 snap is
re-proven (below), and the Copr RPM end to end on Fedora 43 x86_64 (offline `mock`,
`dnf install`, 0 espeak, the voice pass on real audio 80/80; `design-fedora-packaging.md`
changelog). **Only an amd64 snap build stays owed** (`TODO.md`).

**Hardened after review (4 Oct 2026, a code review and a silent-failure hunt):**
- **The model is loaded once, before any session** (`load_voice_model`, called after
  `resolve_voice_model`). A model or runtime that will not load is now one visible
  `Voice pass skipped: …` warning and the reason in every session's record, where
  before it failed quietly in each session.
- **The front end's options come from one builder,** `fbank_options()`, shared by the
  pass and `doctor`. It refuses an unknown window type and implausible frame sizes
  before kaldi-native-fbank sees them. Given an unknown window, kaldi-native-fbank
  1.22.3 prints an error and exits the *process* with status 255, past every
  `except` (measured). Only the unverified `BRISTLENOSE_VOICE_MODEL` override could
  reach that path.
- **`tests/fixtures/voice-fbank-golden.json`** pins the features of a seeded signal,
  with no model needed. Mutating pre-emphasis, librosa mel, high frequency, DC removal
  or the power-of-two FFT each fails it, and all five were run.
- **`doctor --self-test` opens a real onnxruntime session** on an embedded 67-byte
  Identity graph. The sidecar drops onnxruntime's C library on purpose, and an import
  alone would not have caught a broken session. `bristlenose doctor`'s Voice pass row
  now loads the cached model instead of only noting its size.
- **onnxruntime runs at ERROR log level,** as sherpa did.
- **The RPM's `%check` and the snap's build hook assert the runtime is present before
  the self-test,** using explicit exits rather than `assert`.
- **Snap, re-proven as a package the same day:** an arm64 snap built from
  `2dc70a74` (`snapcraft pack --destructive-mode`, throwaway Multipass VM, 319 s,
  340 MB), the first arm64 build. Its build hook printed the self-test line. It
  installed strict-confined. Across all 478 shared objects it carries 0 `espeak_`
  symbols and 0 espeak strings, where sherpa's extension in the same VM shows 66
  strings (one `hf_xet` hit is `used_bytes`+`peak_used_bytes`). Inside
  `snap run --shell`, the pass ran on the 4-minute cut with the model from
  `$SNAP_USER_COMMON/models/`: 80/80 windows judged, centroid cosine 0.0842, the
  same value as outside the snap. **Pre-existing and cosmetic:** under strict
  confinement `import onnxruntime` itself prints one yellow `GPU device discovery
  failed … Permission denied … /sys/bus/pci/devices` warning (AppArmor). No API or
  environment variable runs early enough to silence it, and faster-whisper's Silero
  VAD (`vad_filter=True`) already triggers it in stage 5 of every snap
  transcription. The `hardware-observe` plug would remove it, which is a store
  interface decision. The pass's own session logs no thread-affinity errors,
  because it sets its thread count; a default pool does log them.
- **Behaviour change worth knowing:** `voice_runtime_available()` is true whenever
  kaldi-native-fbank imports, since onnxruntime is a core dependency. A pip user who
  has that library for another reason gets the voice pass without asking. Before, the
  trigger was sherpa-onnx, the same shape. Paragraphs below that name sherpa describe the build as it was.

**Built on the CLI, 4 Oct 2026** — the per-segment variant measured above, in `bristlenose/stages/s05b_voice.py`, behind the optional `voice` extra; through the shipped stage 5b code it scores 12–13 wrong of 286 against 22 for the text split alone. A real `bristlenose run` on the same 38-minute Teams recording (4 Oct 2026, `bd37eba1`) printed `Identified speakers (voice-checked: 1 session)` in 47.9 s for the stage: the text split as three sequential parts (12,665 input / 2,956 output tokens, about $0.08), the voice pass 12.7 s with no tokens (401 of 429 segments judged, 43 relabelled, centroid cosine 0.24), the role pass about $0.01. The report credits the moderator with 25% of the words; the Teams transcript says 30%. The session's speaker cache carries the `speaker_split` record and the log a `voice_pass |` line, so start, finish, time, cost and outcome are all on disk. **In the Mac app since 4 Oct 2026:** `build-sidecar.sh` installs the `voice` extra and the spec `collect_all`s `sherpa_onnx` (its vendored `libonnxruntime.dylib` signs with every other dylib; `doctor --self-test` gains `Bundle: voice`, which fails the build if the native runtime does not load). The model is **not** bundled: it downloads on first use into the app container, hash-verified, exactly as on the CLI — the same runtime-fetch shape as the Whisper model, keeping the pinned-hash path (a bundled copy would come in through the unverified override) and needing no Swift change. The Health window shows a Voice pass row. **In the Fedora Copr package since 4 Oct 2026 (on `main`, unreleased):** `rpm/make-srpm.sh` vendors the extra (`BN_EXTRAS="serve,voice"`) and the spec installs `bristlenose[serve,voice]`; the model is fetched on first use into `~/.cache/bristlenose/models/`, as on the CLI. Proven on a clean Fedora 43 x86_64 box (2 vCPU) with an SRPM built from a local dist, then `mock` offline (exit 0), then `dnf install`: a real `bristlenose run` on a public 21.7-minute two-speaker oral history (FOSSDA) printed `Identified speakers (voice-checked: 1 session)` and recorded `method=voice+text` — 145 of 152 segments judged, 6 relabelled, centroid cosine 0.21, **14.4 s on CPU** — and the run went on to finish end to end (`Done in 14m 48s`, 15 quotes, about $0.26 of LLM). Linux is the one channel that loads **two** onnxruntimes into one process — faster-whisper's Silero VAD uses the `onnxruntime` package (1.30.0) in stage 5, and sherpa-onnx carries its own 1.28.2 — which the Mac never does, since the sidecar excludes the package. They cannot collide: the package links its runtime statically into its pybind module and needs no `libonnxruntime.so` soname, while sherpa's extension resolves its own copy through an `$ORIGIN` rpath (`readelf`/`ldd` on the installed RPM). `%check` now loads them in that order. Packaging detail and the CVE obligation: `design-fedora-packaging.md` §4 and §7. It reaches Copr users with the **next release**: PyPI's 0.32.0 does not declare the `voice` extra, so a Copr build of 0.32.0 refuses at the SRPM step by design. **In the Snap since 4 Oct 2026 (on `main`, unreleased; edge picks it up at the next dispatch):** `snap/snapcraft.yaml` installs `.[serve,voice]` (cp312 manylinux wheels, amd64 and arm64, nothing built from source), and `override-build` fails the pack if `sherpa_onnx` is absent or will not load. No new interface: the model comes over the existing `network` plug into `$SNAP_USER_COMMON/models/` (writable, survives refreshes). Measured on a strict-confined amd64 install (Ubuntu 24.04, 2 vCPU), built with `snapcraft pack --destructive-mode`: `readelf`/`ldd` show `_sherpa_onnx*.so` resolving `libonnxruntime.so` and the vendored `libasound` through its `$ORIGIN` rpath, all inside `/snap`; `doctor --self-test` gives `Bundle: voice … load`; and a real `bristlenose run` on a synthetic 2.3-minute two-voice interview (macOS `say`, two voices) printed `Identified speakers (voice-checked: 1 session)`, fetched the model (40,257,283 bytes, mode 0600) and recorded `method=voice+text`: 21 of 23 segments judged, 7 relabelled, centroid cosine 0.62, **3.9 s**, run done in 3 m 39 s for about $0.11. That run proves the channel, not the quality: on TTS audio Whisper's segments straddle turns, so most of them hold both voices (the re-cut below). As on Copr, faster-whisper's onnxruntime and sherpa's own load into one process without collision. Cost: **+12.3 MB** to the download (xz squashfs of the two directories; the snap is 401 MB) and +44.7 MB installed. One AppArmor denial falls in the pass's window, a read of `/sys/bus/pci/devices/` (onnxruntime's device discovery). It is harmless, and faster-whisper's onnxruntime already raised the same one before this change. The espeak-ng finding (the licence bullet below) applies to the snap's wheel too, which is fine under AGPL. arm64 is declared in `snapcraft.yaml` and its wheel exists, but only amd64 was built and run (CI builds amd64 alone). **Not yet built:** the word-level re-cut of segments that hold both voices.


pyannote segmentation-3.0 (ONNX) + a speaker-embedding ONNX model, run through
sherpa-onnx or directly through onnxruntime, with our own clustering of
Whisper segments.

- **Accuracy:**
  - sherpa-onnx publishes no DER (PUBLISHED: none found). Ours is the
    agreement table above.
  - Expect it to trail pyannote community-1, which publishes 11.2 % on
    VoxConverse and 17.0 % on AMI-IHM with no collar and overlap included.
  - It is probably adequate for 2 speakers. A 3-speaker session needs k
    chosen per session, either from the LLM's speaker count or by an
    eigengap.
- **Licences:**

  | Component | Licence |
  |---|---|
  | sherpa-onnx code | Apache-2.0 |
  | segmentation-3.0 weights | MIT, redistributed ungated by sherpa-onnx |
  | TitaNet-large | CC-BY-4.0, ungated on HF |
  | TitaNet-small | Apache-2.0 — NVIDIA's NGC model card says it is "covered by the license of the NeMo Toolkit", which is Apache-2.0 (both read 4 Oct 2026; this row said "not verified" until then) |
  | WeSpeaker VoxCeleb models | CC-BY-4.0 |

  All are compatible with AGPL-3.0 + CLA, with attribution. Avoid
  reverb-diarization (Rev licence, gated).
- **Dependencies:**
  - sherpa-onnx 1.13.8 has wheels for cp310–cp314 on macOS arm64 and
    manylinux x86_64, so it covers the Copr Python 3.14 pin. Installed size
    is 37 MB, of which 29 MB is its own `libonnxruntime.dylib`. It brings no
    torch, numba, librosa or subprocess calls.
  - **Licence, measured 4 Oct 2026, not in any metadata:** the published wheels
    statically link **espeak-ng (GPL-3.0-or-later)** into the extension, from
    sherpa-onnx's TTS code, which the speaker-embedding use never calls (50
    exported `espeak_*` symbols on both the darwin and the Linux cp314 builds).
    Also linked: piper-phonemize (MIT), kaldifst/OpenFst (Apache-2.0), Eigen
    (MPL-2.0), and in the vendored onnxruntime Abseil, Protobuf and the rest of
    its `ThirdPartyNotices.txt`. Fine alongside AGPL-3.0 on the CLI channels
    (section 13 of each licence); for the Mac App Store build it is an open
    question (`TODO.md`). A sherpa-onnx built with `SHERPA_ONNX_ENABLE_TTS=OFF`
    would carry none of it, at the cost of building the wheel ourselves.
  - Alternative: drive onnxruntime directly. It is already a core dependency
    on the CLI through faster-whisper, so that costs 0 MB there, but needs
    ~200 lines of segmentation post-processing that sherpa-onnx already
    provides. _(The per-segment pass needs no segmentation, and this is what
    shipped: about 100 lines, § Licence.)_
- **Mac sidecar cost (INFERRED, to verify in a build):**
  - About 37 MB of code into a 425 MB bundle. The sidecar currently
    **excludes** `onnxruntime` (58 MB, S3 trim, 4 May 2026). sherpa-onnx
    vendors a smaller copy as a dylib. Dylibs carry no entitlements, so the
    nested-signing posture is unchanged.
  - The new dylib needs a `check-bundle-integrity.py` pass and a
    `--self-test` import check like every other native library.
  - It needs no JIT, so no new Hardened Runtime exception.
  - The models (~45 MB) are data: deliver them with the Whisper model by
    Background Assets on TestFlight/MAS and over plain HTTPS on the `.dmg`,
    following the `en_core_web_lg` pattern (`docs/design-redact-pii.md`
    §"Delivery architecture"). They are small enough to bundle outright if
    that is simpler; that is a size call, not a policy one.
- **CLI channels:**
  - PyPI: an optional `[diarize]` extra, or core, since it is small.
  - Homebrew: a pip dependency in `post_install`, like the rest.
  - Snap (strict): no shellouts, and the model cache goes to
    `$SNAP_USER_COMMON` like Whisper's. **Done 4 Oct 2026**: +12.3 MB to
    the download, no new interface (§ A above has the run).
  - Copr: a manylinux x86_64 wheel joins the vendored wheelhouse. That adds
    one more native library to the CVE-tracking obligation
    (`design-fedora-packaging.md` §7). **Done 4 Oct 2026** — measured: 2
    wheels / 15 MB in the wheelhouse, +43 MB installed (38 MB `sherpa_onnx` + 5 MB
    the bundled `libasound`); the obligation is in §7.
- **Risk:** low. It is the same packaging class as presidio/spaCy (native
  bundles, no executables).

### B. FluidAudio in the Swift host, Mac only (quality upgrade)

FluidAudio (Apache-2.0, v0.17.5, 1 Oct 2026) runs pyannote community-1 with
VBx, Sortformer, and Nemotron-3-Diarization on CoreML/ANE.

- PUBLISHED: community-1 at 323× real time on an M5 Pro. Its AMI-SDM 10.6 %
  uses a 0.25 s collar and ignores overlap, so it is **not comparable** to the
  table above.
- Runs in the host app, not the sidecar, so there is no Python packaging
  risk.
- **Costs:**
  - A Swift→sidecar hand-off. The host writes turns to the project's
    intermediate dir before the run, or the sidecar asks the host.
  - Two diarizers to keep honest across channels. That cuts against "CLI ≡
    macOS Python code" (`design-modularity.md`). The modularity doc does
    allow platform-native acquisition and APIs (it lists SpeechAnalyzer as
    one), so it is a choice, not a violation.
  - Do this only if A's accuracy proves the limit.

### C. pyannote.audio 4 + community-1, CLI extra only

The best-documented open pipeline.

- PUBLISHED: AMI-IHM 17.0, VoxConverse 11.2, DIHARD3 20.2. Argmax's
  OpenBench puts CallHome (2-speaker) at 0.30 DER.
- **Costs:**
  - torch ≥ 2.8, torchaudio, and torchcodec, which needs FFmpeg shared
    libraries; plus lightning, optuna and opentelemetry.
  - That is everything the sidecar trim removed, so **not for the Mac
    app**.
  - Weights are CC-BY-4.0 and gated on HF, but redistributable with
    attribution. 4.x supports offline pipelines, so no user token is needed
    if we ship the 34 MB ourselves.
- **Telemetry is on by default** (`metrics_enabled: true`, posting to
  `otel.pyannote.ai`). Any integration must set
  `PYANNOTE_METRICS_ENABLED=false` before import, and a test must pin that.
  Silent outbound telemetry from a tool handling interview audio is a
  procurement finding waiting to happen.
- **Use:** a `bristlenose[diarize-pyannote]` extra for CLI users with
  torch already installed. It is also the reference implementation to score
  A against in the experiment.

### D. Nemotron-3-Diarization (watch)

NVIDIA, 23 Sep 2026, OpenMDW-1.1, 100M parameters, up to 8 speakers with
overlap.

- PUBLISHED: AMI-SDM 11.1, CALLHOME-2 9.1, DIHARD3 12.7. It also tops
  Voice Arena's far-field benchmark (14.7 %).
- Runs through NeMo-Speech.cpp (Apache-2.0, ggml CPU/Metal): a CLI with no
  Python bindings, i.e. a subprocess, which is a sandbox and Snap hazard.
  It also runs through FluidAudio (option B).
- The Python NeMo path requires numba on Darwin, so it is a non-starter for
  the sidecar.
- Revisit when an ONNX export or Python bindings exist.

### E. Hosted diarization only: pyannoteAI (opt-in)

Since the analysis already makes a cloud call, a diarization-only service
aligned by time to our own Whisper words is the cheapest and most accurate
cloud route.

- **Price:** €0.035/h for community-1, €0.112/h for Precision-3.
  PUBLISHED, OpenBench average DER: Precision-3 0.20 vs community-1 0.28.
- **Data handling:** output deleted after 24 h, never used for training,
  hosted in the EEA.
- **But** this is the first time Bristlenose would send *audio*, not text,
  to a third party, and a new processor at that. It needs:
  - its own consent line (`docs/methodology/consent-gradient.md`);
  - a Settings toggle;
  - a key in the credential store;
  - an entry on all three privacy/terms pages (root `CLAUDE.md`, "TWO
    privacy pages").
- Opt-in only, never a default. **Not run in this research** (it costs
  money and uploads participant audio).

### F. Transcription APIs with built-in diarization (no)

AssemblyAI, Deepgram, ElevenLabs, Speechmatics, AWS, Azure, Google Chirp 3,
OpenAI `gpt-4o-transcribe-diarize`, Gemini 3.5 Transcribe.

- They replace our transcript rather than label it.
- Several have blockers for this job:

  | Service | Blocker |
  |---|---|
  | OpenAI diarize | No word timestamps; 25 MB cap |
  | Gemini 3.5 Transcribe | 30 min cap with diarization on |
  | Chirp 3 | 20 min cap with word timestamps on |
  | Deepgram, AWS | Train on customer data by default |

- Independent benchmarks put bundled diarization at 40–67 % DER on
  far-field audio, against 15–31 % for dedicated diarizers (Voice Arena,
  partly unverified).
- Not worth a second transcript.

### Rejected

| Option | Why not |
|---|---|
| DiariZen (best open DER) | Weights CC-BY-NC-4.0 |
| Sortformer v1 | Weights CC-BY-NC-4.0 |
| WhisperX | Wraps pyannote, pins torch~=2.8 and Python <3.14; we already have the ASR and word timing halves |
| whisper.cpp `-tdrz` | small.en only, turn tokens without identities, project paused |
| SpeechBrain ECAPA alone | Torch, embedding only, so we would build the rest anyway |
| NeMo in Python | Weight of the toolkit, numba on Darwin |
| VibeVoice-ASR | ~9B parameters |
| Apple Speech / SpeechAnalyzer / SoundAnalysis | **No speaker or diarization API** in the published macOS 26 docs (checked 3 Oct 2026; pre-release macOS 27 SDK not checked) |

## How voice joins the existing flow

Voice answers "which stretches are the same person". The LLM keeps answering
"who is the moderator, and what are their names". Sketch (Option A):

```
s05_transcribe   → segments[] with words[] (unchanged)
s05b, SplitGate.SPLIT only:
  1. voice_turns(audio, segments)                     NEW, local, ~0.005× RT
       embed each segment's word span (≥ 0.6 s); fit k clusters on spans ≥ 2 s
       k from speaker-count estimate (eigengap) or 2 by default
       per WORD: cluster of the span it falls in, refined by a sliding
         1.5 s window where the segment's margin is low
       → Word.speaker (cluster id), segment.voice_margin
  2. recut_at_voice_changes(segments)                 NEW, pure
       split a segment where ≥ 2 consecutive words change cluster;
       new segments inherit text/word slices and timings
       label = "Voice 1" / "Voice 2" (generic, so is_generic_label() holds)
  3. if centroid cosine > ~0.85 (one voice found) or the voice pass failed:
       fall back to split_single_speaker_llm()   (today's path, unchanged)
     else:
       skip the text splitter
  4. identify_speaker_roles_heuristic / _llm      UNCHANGED
       the role prompt now sees cleanly separated voices across the whole
       session; it maps Voice 1/2 → researcher/participant and pulls names
  5. assign_speaker_codes → s06 merge             UNCHANGED
```

Model changes, all additive and backward-compatible:

- `Word.speaker: str | None = None`, the voice cluster id.
- Either `TranscriptSegment.voice_confidence: float | None = None` (the
  margin), so a later "uncertain speaker" affordance in the transcript editor
  (`design-speaker-editing.md`) has something to key on, or the same value
  kept in the speaker-info cache instead of the model.
- `TranscriptSegment.source` stays the ASR source. Provenance of the
  *speaker* goes in a new field (`speaker_source: "voice" | "llm-text" |
  "platform"`), never overloaded onto `source`, because
  `PLATFORM_TRANSCRIPT_SOURCES` reads that field.

Caching: the speaker-info cache already holds segments with roles. Store the
voice turns in `intermediate/voice-turns/{sid}.json` so a role re-run doesn't
re-embed. Stage-cache honesty rules apply (`bristlenose/stages/CLAUDE.md`
§"Stage-cache honesty"): a failed voice pass is recorded as failed, not as
absent.

Two traps this design has to respect:

- **The split gate is a product decision, not a technical one.** A platform
  transcript naming one account is never split by a model today (product
  call Q3, 1 Oct 2026). Voice evidence is better evidence than text, but it
  doesn't by itself reopen that call. The in-room case is a separate
  decision for the user.
- **The pipeline must state what voice decided**, the same way
  `NOT_SEPARATED` is stated, so a researcher who sees "Voice 1/Voice 2" with
  no names knows why.

## Measured against platform ground truth (4 Oct 2026)

Option A's voice pass (TitaNet-small, one embedding per Whisper segment,
two clusters; `experiments/speaker_split_full/voice.py`) was scored against
the named turns of a Teams `.docx` transcript, on the same 385 Whisper
segments (real word timings) as the shipped text splitter. The text splitter
is the one shipped on 3 Oct 2026: whole transcript, in parts. Voice clusters
got their roles from the shipped LLM role pass, as the product would, and
segments too short to embed (27, under 0.6 s) kept the text label.
Scoring: `experiments/speaker_split_full/eval_voice.py`; truths as in
`docs/design-speaker-splitting.md` § Measured.

| Method | Wrong, text truth (286 scored) | Wrong, timing truth (212 scored) | Word accuracy (text truth) |
|---|---|---|---|
| Text splitter alone (2 runs) | 22, 22 | 29, 26 | 95% |
| Voice alone | 17 | 18 | 98.5% |
| **Voice, text where voice has no verdict** | **12, 12** | **15, 15** | **98.8%** |

- **About 45% fewer wrong segments** than the text splitter alone (22 → 12;
  27 → 15 on the timing truth), and about 75% fewer wrong words.
- **The mistakes left are short.** Of the 12, eight are one- to three-word
  backchannels ("Yeah.", "Okay."), mostly too short to embed. On lines of
  four or more words, the ones that can become quotes, text alone gets 12
  wrong and voice with text gets 4.
- **The role pass mapped the clusters correctly.** The oracle permutation
  picks the same mapping.
- **Cheap, as before:** 15 s of embedding for 38 minutes of audio on CPU;
  centroid cosine 0.26 (WeSpeaker on the same audio: 0.87, close to
  "one voice").
- **Not measured:** segments that hold both voices (65 of 385 by the Teams
  timing). Re-cutting them at word level is what Option A adds beyond this
  per-segment pass, and there is no word-level truth to score it against.
  Also one session, one Teams recording, one moderator; the research above
  found a Meet recording harder.

## Licence: espeak-ng in the sherpa-onnx wheels — options for the owner (4 Oct 2026)

**Decided 4 Oct 2026: option 2, on every channel.** sherpa-onnx is gone from the
`voice` extra, the dev extra, the sidecar spec, the RPM and the snap; the pass runs
TitaNet through onnxruntime with kaldi-native-fbank features (§ A, top). That takes
espeak-ng — and with it any GPL-3.0 copyright holder's standing to object — out of
everything Bristlenose conveys. What remains is permissive: onnxruntime (MIT, with
its `ThirdPartyNotices.txt` of Apache/BSD/MIT/MPL components, none GPL-only),
kaldi-native-fbank (Apache-2.0), and the model (the NeMo Toolkit licence,
Apache-2.0). Those require their notices to travel with the binary — the notices
item `TODO.md` already lists for the Mac bundle — and nothing more. The brief below
is kept as the record of the choice.

**Options brief as written (not decided at the time).** Scripts and logs were in
the session scratchpad; the commands that matter are inline.

**The finding, re-measured.** The published sherpa-onnx 1.13.8 wheels
statically link espeak-ng (GPL-3.0-or-later) from sherpa's TTS code. On the
darwin cp312 wheel in `.venv-sidecar`, case-sensitive
`nm <lib> | grep -c '_espeak'` gives **50** in `_sherpa_onnx.cpython-312-darwin.so`
and **8** in `libsherpa-onnx-c-api.dylib` (which also carries 19 `piper`
symbols); 0 in `libonnxruntime.dylib` and `libsherpa-onnx-cxx-api.dylib`.
Count case-sensitively: `grep -i espeak` also matches `OfflineSpeaker…` and
`wespeaker`, and inflates every count. The built sidecar carries all four
libraries (the `_internal/libsherpa-onnx-c-api.dylib` beside them is a symlink,
not a second copy). The c-api dylib is never loaded by Python, so excluding it
from the spec would not help: the extension the pass uses carries espeak-ng
itself.

**Nothing has shipped with it yet.** `git tag --contains 93eb8c30` (the sidecar
commit) is empty; the last release is v0.32.0, which has no `voice` extra. The
call is due before the next release on any channel that conveys the binary:
the Mac app (.dmg and TestFlight/App Store), the Snap and the Copr RPM (all
three ship the extra on `main`, unreleased). A pip install of the `voice` extra conveys
nothing of ours: k2-fsa distributes that wheel.

### 1. Build sherpa-onnx from source, TTS off, for the sidecar

**Measured: it builds, it carries no espeak-ng, and it gives the same
embeddings, bit for bit.** Tag `v1.13.8` (`11afbd0`), on this Mac (arm64,
macOS 27, Apple clang 21), Python 3.12.13:

```
SHERPA_ONNX_CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release -DSHERPA_ONNX_ENABLE_TTS=OFF \
  -DSHERPA_ONNX_ENABLE_SPEAKER_DIARIZATION=OFF -DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF \
  -DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF -DSHERPA_ONNX_ENABLE_BINARY=OFF \
  -DSHERPA_ONNX_ENABLE_C_API=OFF -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
  -DPython_EXECUTABLE=<venv>/bin/python -DPython3_EXECUTABLE=<venv>/bin/python -G Ninja" \
python setup.py bdist_wheel
```

- **Time:** 82–85 s wall, ~450 s CPU, two clean runs.
- **Result:** the installed package has two libraries: the extension (3.6 MB)
  and the same prebuilt `libonnxruntime.dylib` 1.28.2 (29.0 MB). That is
  **31 MB against 37 MB today (−6 MB)**. `_espeak` symbols: 0. `piper`: 0.
  kaldifst/OpenFst (Apache-2.0) is still linked, because sherpa's decoder uses
  it.
- **Same output:** 17 spans of a synthetic two-voice file through the source
  build and the published wheel gave a max absolute difference of 0.0.
- **Build ownership it adds**, all hit in this measurement:
  - **cmake and ninja.** Neither is on this Mac. They pip-install into a
    throwaway build venv, so nothing goes on the system.
  - **Configure-time downloads.** It fetches ten archives: pybind11,
    kaldi-native-fbank, kissfft, kaldi-decoder, kaldifst, OpenFst, Eigen,
    simple-sentencepiece, nlohmann/json, and a **prebuilt** onnxruntime from a
    maintainer's personal releases (`csukuangfj/onnxruntime-libs` v1.28.2, the
    same binary the published wheel vendors). Each carries a `URL_HASH`
    (checked on the eight that matter), so a cached build is reproducible, but
    the build needs the network or a pre-seeded download directory.
  - **Interpreter selection.** Without `-DPython_EXECUTABLE`, CMake's
    FindPython took Homebrew's 3.14 over the `PYTHON_EXECUTABLE` setup.py
    passed. The result was a wheel *tagged* cp312 holding a `cpython-314`
    extension, which fails at import with no build error.
  - **Platform tag.** `bdist_wheel` tags from the interpreter's sysconfig,
    which is `macosx-26.0-arm64` for this Homebrew 3.12. The binary's `minos`
    is 11.0, but pip on the 15.0 floor would refuse a `macosx_26_0` wheel.
    The build needs `--plat-name macosx_11_0_arm64`.
  - **A two-line patch.** `import sherpa_onnx` fails on a TTS-off build:
    `__init__.py` imports `GenerationConfig` and `OfflineTtsSupertonicModelConfig`
    from the extension unconditionally. Upstream fixed this class of bug
    ([k2-fsa/sherpa-onnx#2658](https://github.com/k2-fsa/sherpa-onnx/issues/2658),
    closed 9 Oct 2025), but master still imports both names (fetched
    4 Oct 2026). Remove the two lines and the import works,
    `SpeakerEmbeddingExtractor` included. An upstream PR would retire the
    patch.
- **Where it would live:** a step in `build-sidecar.sh` ahead of Layer V. It
  builds the wheel once per (sherpa version, cmake args, Python minor) into a
  cache and installs it `--no-deps` over the resolved one. The step has to sit
  inside the release preflight's resolve-once venv, or the drift gate sees a
  different sherpa from the one that ships. PyPI has an sdist (1.06 MB), so
  `pip install --no-binary sherpa-onnx` with `SHERPA_ONNX_CMAKE_ARGS` set may
  collapse the build to one line; that is **not tried**, and the patch would
  still be needed. CI needs nothing, because the Mac CI job builds against a
  stub sidecar. Linux channels would keep the published wheels, so Snap and
  Copr carry GPL-3.0, which is fine beside AGPL-3.0. Every sherpa bump becomes
  a rebuild plus re-applying the patch. Dependabot sees only the version pin.
  The SBOM would name a PyPI purl for a wheel PyPI never served.

### 2. Drop sherpa-onnx and drive onnxruntime directly

**Measured: the same voice verdicts, from about 50–80 lines.** The "~200
lines" in Option A's dependency notes was for pyannote segmentation
post-processing. The shipped pass embeds Whisper segments, so it needs none of
that. What it needs is sherpa's NeMo front end
(`speaker-embedding-extractor-nemo-impl.h` at v1.13.8): kaldi fbank (80 bins,
25/10 ms, Hann window, pre-emphasis 0.97, librosa mel, `snip_edges`, no DC
removal, no dither), per-feature mean/std normalisation, a `(1, 80, T)` tensor
with a frame count, and output `embs`. The prototype's class is 73 non-blank
lines with two interchangeable feature paths:

- **`kaldi-native-fbank`** (Apache-2.0, 0.27 MB, same author as sherpa).
  Cosine to sherpa's embedding: **1.000000** to six places, on 2.0, 0.7 and
  5.0 s windows of a synthetic two-voice file.
- **Pure numpy**, which needs no native code beyond onnxruntime. Cosine to
  sherpa: **≥ 0.99995**.

Through Bristlenose's own `cluster_voices`, on three public FOSSDA interviews
(25, 15 and 17 spans) and on **794 fixed 3 s windows over the 40-minute s1**,
both feature paths gave **the same verdict on every span**. Centroid cosine
was identical to four places (knf) or within 0.0006 (numpy). Time: 17.3 s
direct against 18.0 s for sherpa over the 794 windows.

**One trap.** sherpa resizes its buffer to a multiple of 16 frames, but the
tensor it hands the model keeps the unpadded frame count, so the padding never
reaches the model. A port that pads the way the code *reads* scores 0.89 on
0.7 s spans. Port the behaviour, not the reading.

- **Size, Mac.** The onnxruntime 1.30.0 package is **80 MB installed**. The
  spec's "58 MB" comment is dated. It holds:
  - `onnxruntime_pybind11_state.so`, 40.8 MB, self-contained: `otool -L` shows
    no libonnxruntime.
  - `libonnxruntime.1.30.0.dylib`, 33.2 MB, which Python never loads. The
    prototype ran with it moved aside.
  - `transformers/` (5.2 MB), `quantization/` (1.8 MB) and `tools/` (1.5 MB).

  Trimmed to the pybind module and its Python files, that is **about 42 MB,
  against 37 MB for sherpa today (+5 MB)**. A `collect_all` would add about
  43 MB. The spec excluded onnxruntime partly to cut torch's incoming edge
  through `onnxruntime.transformers.machine_info`. A targeted exclude keeps
  that edge cut.
- **Size, Linux:** 0 MB. onnxruntime is already a core dependency through
  faster-whisper. This option also takes sherpa's second onnxruntime (1.28.2)
  and its bundled `libasound` off the Copr CVE watch (`design-fedora-packaging.md`
  §7), and ends the two-runtimes-in-one-process arrangement.
- **Licence:** 0 `_espeak` symbols in the pybind module. Its
  `ThirdPartyNotices.txt` (5,093 lines) mentions GPL only in disjunctive terms:
  MPL-2.0's secondary-licence definition, and Mbed TLS "Apache-2.0 OR GPL".
  The notice obligation the TODO already lists stays, and is easier to meet:
  this package ships the notices file, and sherpa's wheel does not.
- **What we would own:** the feature front end, about 40 lines of maths with
  no upstream to track. A model change would need the equivalence re-run
  (keep it as a test against stored embeddings). The ITMS-91061 watch moves
  from `libonnxruntime.dylib` to the pybind module, which statically links
  Abseil and Protobuf too.

### 3. Declare and accept

- **The App Store question is about espeak-ng's licence, not ours.**
  Bristlenose's AGPL code is the owner's (CLA), so the owner can distribute it
  on Apple's terms. espeak-ng's copyright holders have not agreed to those
  terms. GPL-3.0 §10 forbids "any further restrictions" on the rights it
  grants, and the FSF treats Apple's Usage Rules as such restrictions.
- **GNU Go, 25 May 2010.** The FSF, as copyright holder, notified Apple. Apple
  removed the app rather than change its terms. The FSF's summary: Apple
  "imposes numerous legal restrictions on use and distribution", which GPLv2 §6
  forbids ([FSF](https://www.fsf.org/news/2010-05-app-store-compliance)).
- **VLC for iOS.** Accepted in September 2010. Removed in January 2011, after
  one of VLC's own copyright holders complained
  ([Cult of Mac](https://www.cultofmac.com/news/vlc-app-pulled-from-the-app-store-in-response-to-nokia-employees-gpl-crusade)).
  It came back in July 2013, and only after relicensing. libVLC went from
  GPLv2+ to LGPLv2.1+, announced 21 Dec 2011: every contributor agreed but
  one, whose code was rewritten
  ([VideoLAN](https://www.videolan.org/press/lgpl-libvlc.html)). The app itself
  moved to MPL-2.0
  ([Wikipedia](https://en.wikipedia.org/wiki/VLC_media_player)).
- **In both cases enforcement came from a copyright holder's complaint, not
  from App Review.** "Declare and accept" means shipping and relying on no
  espeak-ng copyright holder objecting. If one does, the listing is pulled,
  and the remedy is option 1 or 2, done under deadline.
- **Not established:** whether the Mac App Store differs. Mac apps are not
  FairPlay-encrypted, which was the iOS complaint's DRM point. But the FSF's
  objection was to the Usage Rules, and those apply to Mac apps too. I found
  no Mac-specific case either way.
- **Declaring is not free on any channel.** GPL-3.0 §4 and §6 require the
  licence text and the Corresponding Source with every conveyed binary: the
  .dmg, TestFlight, the Snap and the Copr RPM. The Corresponding Source here
  is sherpa-onnx v1.13.8 plus espeak-ng from `csukuangfj/espeak-ng@ed530aa`, a
  personal fork pinned in `cmake/espeak-ng-for-piper.cmake`. The bundle today
  carries only sherpa's Apache `LICENSE`.

### Owed under any option

- **`THIRD-PARTY-BINARIES.md`:** yes, done with this brief. It is the licence
  inventory `SECURITY.md` points to, and it named no GPL-3.0 component. Its
  generator reads wheel metadata, which says "Apache", so a regeneration would
  never surface this on its own. _Replaced with option 2 by rows for the
  onnxruntime binding and kaldi-native-fbank._
- **`SECURITY.md`:** no change. It defers licences to the inventory.
- **Website:** no change. `content/terms.html` says AGPL-3.0 governs "the
  software itself" and lists no third-party licences. The bundle already ships
  LGPL ffmpeg and the GPL-with-exception PyInstaller bootloader under the same
  wording.
- **Snap:** `snap/snapcraft.yaml` still declares `license: AGPL-3.0-only`,
  while the snap now ships the `voice` extra (`09876530`). That field needs the
  same compound expression the RPM's `License:` now carries. _Moot under
  option 2: with no copyleft component left, `AGPL-3.0-only` is no less
  accurate than it was before the voice pass, and the RPM's field dropped its
  GPL and LGPL terms._
- **Aside, not licence:** TitaNet-small refuses a span over 12,288 frames
  (~123 s): `RuntimeError … 12288 by 17998`. `refine_speakers_by_voice`
  catches it and the whole session falls back to the text split. Whisper's
  ≤ 30 s segments should never reach it. It was hit here only because the
  `.txt` transcripts carry start times alone, so a span ran to the next
  segment. Option 2 and the shipped path behave the same, because the limit is
  the model's.

## The first experiment (free, local, proposed — not run)

Goal: score all three methods (opening sample, whole-transcript LLM, voice)
against the same hand labels, on the two Talismanic sessions already in the
30 Sep run output that `experiments/speaker_split_full/` builds its page from.

1. **Add a third column.** Extend `experiments/speaker_split_full/run.py`'s
   per-segment rows with `voice` (M/P/?) and `voice_margin`. Move a cleaned
   copy of this research's per-segment script (kept locally) into
   `experiments/speaker_split_full/voice.py`. The voice role mapping should
   come from the LLM role pass on voice-labelled segments, **not** the oracle
   permutation used above. That is the honest product number. It costs one
   role call per session, ~$0.01. Ask before running.
2. **Extend `page.html`.** The stats panel currently scores "sample" vs
   "whole". Add "voice", plus a fourth bucket: rows the researcher labels
   **Both**, scored against `mixed` (did voice flag the segment as holding
   two speakers?). The labels already persist in `localStorage` and export as
   JSON, so labels made before the change are kept.
3. **Label.** s1 (238 segments) and s2 (377) at the page's j/k/m/p/b pace
   is about an hour. **Prioritise:** the page's existing "disagreements"
   filter, then a random 50 from the agreements, which estimates the shared
   error rate that agreement alone hides.
4. **Report, per session:**
   - accuracy for each method on M/P rows;
   - recall on Both rows (voice only);
   - the talk-time share each method implies, against the share the labels
     imply. Talk time is the number the report actually shows (the 69 %
     claim).
5. **Add one hard case.** If a recording exists with two people at one
   laptop mic in the same room, add it. That is where voice is weakest and
   where Teams/Zoom give no help. s7 ("Talismanic object UR session") may be
   that shape; check its source first.

Decision rule:

- **Build A** if voice ≥ whole-transcript LLM on M/P accuracy for both
  sessions, and recall on Both ≥ 50 %.
- **Score C (pyannote community-1) on the same labels before building
  anything** if voice is close but loses on s2. C is the pipeline A would
  grow into, and B wraps the same model on the Mac.
- **Ship whole-transcript LLM splitting first** (already measured, no new
  dependencies) and park voice if voice loses on both sessions.

**Reproducing the measurement above:**
- Scratch venv: `python3.12 -m venv v && v/bin/pip install sherpa-onnx soundfile numpy`.
- Models: from the k2-fsa `speaker-segmentation-models` and
  `speaker-recongition-models` releases (sic; that is the tag's spelling).
- Audio: `ffmpeg -ac 1 -ar 16000` into a session scratchpad, never into
  `bristlenose-output/`.
- Delete the WAVs afterwards; they are participant audio.

## Secondary: prosody as a research signal (brief)

What tone of voice could add next to the text-based sentiment, in order of
defensibility:

1. **Pauses and speech rate.** Free, because they come from the word
   timestamps we already keep. Long latency before an answer, or a slowdown
   mid-answer, is a hesitation signal researchers already look for by ear.
   It needs care at segment boundaries (Whisper word timings drift; see the
   ±2 s pad in the signal gate). No new dependency.
2. **Filled pauses ("um", "uh").**
   - Whisper often drops them, and our mlx path visibly keeps some (the
     Talismanic transcripts are full of "um"), inconsistently.
   - CrisperWhisper keeps them as tokens but is **CC-BY-NC-4.0**, so it's
     out.
   - Counting what Whisper does keep is cheap, but not a reliable measure.
3. **Pitch range and emphasis.**
   - parselmouth (Praat) is GPLv3+. It can be combined with AGPL, but
     adds a native library.
   - openSMILE/eGeMAPS requires a paid licence for commercial products.
   - Worth it only if (1) proves useful.
4. **Speech emotion recognition: not recommended.**
   - The Odyssey 2024 challenge on natural podcast speech: the best of 68
     systems reached 37 % accuracy across 8 classes.
   - Wagner et al. (arXiv 2203.07378) find that audio valence models mostly
     re-derive *linguistic* content (so they duplicate the text sentiment
     we already have), and are unfair across speakers.
   - The best natural-speech model (audEERING MSP-Podcast) is
     CC-BY-NC-SA.
   - Hume's API shut down in June 2026.
   - Labelling a participant "frustrated" from their voice would be a
     confident-sounding claim the evidence doesn't support. That is the
     opposite of what this report owes a researcher.

If anything ships here, it is (1): an "answered after a long pause" marker on
a quote, framed as an observation, not an emotion.

## Sources

- Local measurements: kept locally, gitignored (they contain transcript
  text).
- pyannote community-1 card and telemetry config:
  huggingface.co/pyannote/speaker-diarization-community-1;
  github.com/pyannote/pyannote-audio `src/pyannote/audio/telemetry/config.yaml`.
- sherpa-onnx: github.com/k2-fsa/sherpa-onnx (releases
  `speaker-segmentation-models`, `speaker-recongition-models`); PyPI
  `sherpa-onnx` 1.13.8.
- Nemotron-3-Diarization: huggingface.co/nvidia/Nemotron-3-Diarization;
  NeMo-Speech.cpp: github.com/NVIDIA/NeMo-Speech.cpp.
- FluidAudio: github.com/FluidInference/FluidAudio
  (Documentation/Benchmarks.md).
- DiariZen: github.com/BUTSpeechFIT/DiariZen.
- TitaNet-large licence: huggingface.co/nvidia/speakerverification_en_titanet_large.
- Benchmarks: github.com/argmaxinc/OpenBench (BENCHMARKS.md, 22 Sep 2026);
  voicearena.com/diarization-bench; arXiv 2509.26177; arXiv 2507.16136.
- Cloud pricing and data terms: pyannote.ai/pricing and
  docs.pyannote.ai/data-retention; assemblyai.com/pricing;
  deepgram.com/pricing and the MIP opt-out docs; ai.google.dev Gemini 3.5
  Transcribe model page; developers.openai.com speech-to-text guide.
- Prosody: arXiv 2408.16589 (CrisperWhisper), arXiv 2405.20064 (Odyssey
  2024), arXiv 2203.07378 (Wagner et al.); github.com/audeering/opensmile.
