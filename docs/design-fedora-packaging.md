---
status: current
last-trued: 2026-08-27
trued-against: HEAD on 2026-08-27
---

> **Truing status:** Current. Written alongside the implementation, from measurements
> taken on a real Intel Fedora 42 box (`aella up --fedora`, Xeon Platinum 8488C) and
> in `fedora:42` containers. Every number in this doc was measured, not estimated —
> where something is an estimate it says so.

## Changelog

- _2026-08-27_ — created, then trued against the build it describes. Covers the Copr
  channel: the offline-build problem and the chosen answer, the `ffmpeg-free` codec
  verdict (a live question that turned out **not** to be a bug), the arch decision
  (x86_64 only), and the honest cost of maintaining the channel. §2a records the defect
  this work actually turned up — the export bundle missing from every published wheel —
  which is not a Fedora problem and is much larger than one. §7 first recommended
  **holding**; that was overturned the same day and it now reads *ship it*, with the
  recurring costs recorded rather than deleted. Later that day the channel was proven
  on Copr's own builders, and the release machine was wired for it without being
  switched on.
- _2026-08-27 (truing pass)_ — this doc contradicted itself in three places and the
  public install docs had jumped the queue. Fixed: the Status block claimed no Copr
  build had ever run while §6 recorded one; this changelog still said "hold" while §7
  said "ship"; §7's "Against, and this is the part that decides it" was pre-decision
  text left standing under a post-decision heading. Separately, `INSTALL.md` and
  `README.md` had shipped `dnf copr enable cassiocassio/bristlenose` — a project that
  returns 404 — which is precisely the ordering mistake §7 names. Reverted to pipx
  until the channel exists. Two independent reviewers caught the same thing; the
  lesson is the skill's own: **a section-scoped sweep never reaches the summary, and
  the summary is what gets believed.**

# Design: Fedora packaging via Copr

Status: **implemented, proven on Copr's own builders, no production project.**
A Copr build *has* run — an uploaded SRPM built green on `fedora-43-x86_64`, and
`dnf copr enable` + `dnf install` worked from a clean box (§6) — but into an
unlisted, auto-deleting **test** project. `cassiocassio/bristlenose` does not
exist: `api_3/project` returns **404**, verified 27 Aug 2026. Nothing a user can
install from is published, and the public install docs deliberately say nothing
about Copr until it is (§7's ordering).

Sibling docs: `docs/design-doctor-and-snap.md` (the Snap channel, and the closest
prior art for a Linux packaging decision), `docs/design-homebrew-packaging.md` (the
structural model for a per-channel packaging doc).

---

## 1. Why

Fedora users are currently told to use pipx:

```bash
sudo dnf install pipx ffmpeg-free
pipx ensurepath
pipx install bristlenose
```

That works. It is also not what a Fedora user's hands reach for. The Fedora idiom
for third-party software is a Copr — Fedora's PPA equivalent:

```bash
sudo dnf copr enable cassiocassio/bristlenose
sudo dnf install bristlenose
```

Two commands, both `dnf`, no separate package manager, and `dnf upgrade` keeps it
current. This is additive: pip/pipx, Homebrew, Snap and the Mac app all keep working.

### Not Flatpak

Flatpak is a desktop-app format. Bristlenose on Linux is a CLI.
`flatpak run app.bristlenose.Bristlenose` with no `$PATH` entry and a sandboxed view
of the user's recordings is a *worse* CLI than pipx. Revisit only if a Linux GUI
ever ships.

### Not official Fedora repos

Official packaging needs a packager sponsor and forbids bundled dependencies. This
dependency tree cannot satisfy that — see §3. Copr is laxer by design, and is the
right altitude for a pre-1.0 project.

---

## 2. The `ffmpeg-free` question — answered first, because it outranked the packaging

`INSTALL.md` and the website tell Fedora users to `sudo dnf install ffmpeg-free`.
That is Fedora's patent-free FFmpeg build. Nobody had tested whether it decodes what
actually lands in a researcher's folder. If it were short a decoder, that would be a
live bug affecting Fedora users *today*, and it would outrank shipping an RPM.

**Verdict: `ffmpeg-free` is sufficient. The docs are correct. There is no bug.**

The reasoning that predicts a bug is seductive and wrong, so it is worth writing down.
`ffmpeg-free`'s configure line contains:

```
--disable-decoder='h264,hevc,libxevd,vc1,vvc'
```

The native H.264 decoder is compiled out. From that you would conclude that an `.mp4`
from Teams or Zoom — H.264 High profile + AAC-LC — cannot be read. Two things make
that conclusion false:

1. **Bristlenose never decodes the video stream to do its work.** `extract_audio_from_video`
   passes `-vn` ([bristlenose/utils/audio.py:151](../bristlenose/utils/audio.py)). It
   demuxes the container and decodes only the *audio* stream. AAC decode is enabled
   (`--enable-decoder=...,aac,libfdk_aac,...`), so the video codec is irrelevant.
2. **H.264 decode works anyway, via `libopenh264`.** `libavcodec-free` carries a hard
   `Requires: libopenh264.so.7()(64bit)`, and the `fedora-cisco-openh264` repo is
   enabled by default. So Cisco's decoder is present on any machine that can install
   `ffmpeg-free` at all. Contrary to its Constrained-Baseline reputation, it decoded
   720p **High** profile (CABAC, 8x8 transform, B-frames) without complaint.

### What was measured

A 26-file corpus covering all 24 media extensions in `AUDIO_EXTENSIONS` /
`VIDEO_EXTENSIONS` (10 audio + 14 video, `bristlenose/models.py:111`), run through the
exact three subprocess calls Bristlenose makes (`probe_duration`, `has_audio_stream`,
`extract_audio_from_video`), compared against full FFmpeg 8.1 on macOS.

| | result |
|---|---|
| Files decoding correctly under `ffmpeg-free` | **26 / 26** |
| Audio fidelity vs full FFmpeg | max delta **1 LSB** of 32768; **114 dB** SNR |
| Video fidelity (thumbnails) vs full FFmpeg | **44.7 dB** PSNR, mean abs error 0.75/255 |
| Teams-style H.264 High + AAC `.mp4` | pass |
| Zoom-style H.264 Main / Baseline + AAC `.mp4` | pass |
| Meet-style `.webm` (VP8/Opus), `.mov`, `.mkv`, `.m4v` | pass |
| AVCHD `.mts`/`.m2ts` (H.264 + AC-3) | pass |
| Legacy `.avi` `.wmv` `.asf` `.flv` `.mpg` `.3gp` | pass |

The 1-LSB audio delta is rounding between FFmpeg 7.1 and 8.1's AAC decoder, not a
`ffmpeg-free` limitation. It is inaudible and irrelevant to transcription.

**And then the whole pipeline was run, which is the proof that counts.** A synthesised
two-speaker interview, encoded exactly as Teams exports (H.264 High + AAC-LC in `.mp4`,
1280×720), through `bristlenose transcribe` on the installed RPM: 6 segments, 21s of
audio, 14.4s wall. The transcript came back word-for-word correct. A codec probe says
the decoder exists; this says the researcher gets their words.

### The `noopenh264` edge — looked for, not found

Fedora ships a `noopenh264` stub that can satisfy `libopenh264.so.7()(64bit)` while
decoding nothing. On such a machine H.264 decode would fail, widening the gap below from
"iPhone HEVC" to "any Teams/Zoom recording".

**Not reproducible on a stock Fedora 42 cloud image.** `dnf swap openh264 noopenh264`
reinstalled the real one; with `fedora-cisco-openh264` disabled, `dnf` reports "Nothing
to do" because the stub is not in the enabled repositories at all. Recorded as a
theoretical edge rather than a measured one. Note it would cost *thumbnails only*
either way: audio extraction passes `-vn` and never opens the video decoder — proven
directly, and again by the full transcription run above.

### Checked against real recordings, not just synthesised ones

The corpus above was **synthesised** to match how Teams, Zoom and Meet encode. That is an
assumption about those platforms, so it was checked against 253 real recordings on the
maintainer's machine (codec metadata only — this is participant material). 107 of them are
video containers:

| video codec | streams |
|---|---|
| H.264 Main | 43 |
| H.264 Constrained Baseline | 30 |
| H.264 High | 16 |
| **HEVC Main** | **5** |
| ProRes / MJPEG / VP9 / VP8 / AV1 / H.263 / MPEG-4 / WMV2 | 1 each |

Audio is `pcm_s16le` (140), `aac LC` (81), bare `aac` (13), then Opus, MP3, FLAC, HE-AAC,
WMAv2, Vorbis in ones and twos.

So the synthesised fixtures were representative: **89 of 102 identifiable video streams are
H.264 in exactly the three profiles tested**, and AAC-LC dominates the audio. Every codec in
that table decodes under `ffmpeg-free` except HEVC.

### `sudo dnf install ffmpeg` is NOT broken — measured twice, claimed wrong twice

`doctor_fixes.py` tells a Fedora user `sudo dnf install ffmpeg`, while `INSTALL.md` and the
website say `ffmpeg-free`. That looks like a bug, and **two independent reviewers have now
reported it as one** ("on stock Fedora `dnf install ffmpeg` resolves to nothing").

**It does not. Measured on Fedora 41 and Fedora 42, stock repos, no RPM Fusion:**

```
$ dnf install --assumeno ffmpeg
Installing:
 ffmpeg-free   x86_64   7.1.4-1.fc42   updates
```

There is no package literally named `ffmpeg` in the stock repos, and dnf5 resolves the
request to `ffmpeg-free` anyway. The command works, and on a machine that *does* have RPM
Fusion it installs the fuller build — which is also fine. So the two spellings are an
inconsistency of *register*, not a defect, and changing it would mean editing `cmd_fedora`
across 21 locale files for no user-visible gain.

**Recorded here because it has now cost two review cycles.** If a third reviewer raises it,
this section is the answer; if you still want the change, make it for consistency and say so,
not as a bug fix.

### The one real gap: HEVC — and it is not hypothetical

`hevc` is disabled with no `libopenh265` equivalent, so **HEVC video cannot be decoded on
Fedora**. The tempting framing is "an iPhone edge case". The corpus says otherwise: **5 of
107 real video files are HEVC**, about 5%. Teams, Zoom and Meet are H.264 and always were —
these come in the other way, when a researcher drops in something recorded on a phone or
captured with a modern screen recorder.

**What it costs is still only a thumbnail.** All five are `.mov` carrying AAC audio, so all
five transcribe normally; audio extraction passes `-vn` and never opens the video decoder.
Measured on such a file:

| Bristlenose call | result |
|---|---|
| `probe_duration` | 4.00s — **works** (demux, no decode) |
| `has_audio_stream` | `audio` — **works** |
| `extract_audio_from_video` | 128,420 bytes of PCM — **works** |
| `extract_thumbnail` | `no decoder found for: hevc` — **fails** |

Transcription is unaffected. `extract_thumbnail` already degrades gracefully — it logs
a warning and returns `None` ([bristlenose/utils/video.py:120](../bristlenose/utils/video.py)),
which is the designed behaviour for a cosmetic failure. So the user-visible symptom is a
missing thumbnail on roughly one video session in twenty, and nothing else.

**Decision: accept it. Do not send Fedora users to RPM Fusion.** Full FFmpeg means a
third-party repo, a bigger ask than the Copr itself, and a licensing conversation, all
to restore a thumbnail. Document it instead. If HEVC recordings turn out to be common
among researchers, revisit — the fix is one `dnf install` line in the docs, not code.

---

## 2a. What this work actually found: the export bundle shipped in no wheel

Not a Fedora problem, and much larger than one. It is recorded here because this is
where it surfaced — the spec's `%check` refused to build, correctly.

`bristlenose/server/static-export/` holds the dedicated single-file export build
(`frontend/vite.export.config.ts`). It is generated by `npm run build`, it is
**gitignored**, and it was **not** in `pyproject.toml`'s `[tool.hatch.build] artifacts`.
Hatchling's `artifacts` is the one mechanism that re-includes a VCS-ignored path, so the
directory was in no sdist and no wheel ever published — verified against
`bristlenose-0.27.0` on PyPI: 226 entries under `server/static/`, **zero** under
`server/static-export/`.

`routes/export.py` raises a 500 when `app.js`/`app.css` are missing. So **Export HTML has
been broken on every pip, pipx, Homebrew and Snap install.** Only the macOS app worked,
because `desktop/bristlenose-sidecar.spec:159` lists the directory separately and got it
right — which is also why nobody saw it.

Nothing could have caught it. `tests/test_serve_export_coverage.py` is the anti-drift gate
for exports and it classifies **routes, not assets**; every other test runs against
`pip install -e .`, where the directory exists at its source path whether or not it is
packaged. A green suite and a clean build were both compatible with a wheel that had no
export bundle in it.

Fixed, with a gate that asks the only question with teeth — *is this path declared for
packaging?* — of **every** gitignored path under `bristlenose/`, not just the two we know
about (`tests/test_packaging_artifacts_coverage.py`; fails on the previous
`pyproject.toml`, passes on the current one).

**This blocks the Copr.** The channel builds from the PyPI sdist, so it cannot ship until
a release carries the fix — the `%check` in `rpm/bristlenose.spec.in` asserts both halves
of the SPA and will refuse 0.27.0. `rpm/make-srpm.sh` grew `BN_LOCAL_DIST=` so a release
candidate can be packaged and proven *before* it is tagged, which is how everything below
was measured.

---

## 3. The central technical problem: no network in `mock`

Copr builds in `mock`, and `%build` has no network by default. The dependency tree
includes `faster-whisper`, `ctranslate2`, `presidio-analyzer`, `presidio-anonymizer`,
`spacy` and a spaCy model. None of those are in Fedora's repos, so `pip install` at
build time is impossible.

### What Fedora *does* have

Measured against Fedora 42 (`dnf repoquery`):

| in Fedora | missing |
|---|---|
| `typer` `pydantic` `pydantic-settings` `rich` `pyyaml` `jinja2` `inflect` `docx` `pysrt` `openai` `numpy` `onnxruntime` `tokenizers` `huggingface-hub` `fastapi` `uvicorn` `sqlalchemy` `alembic` `httpx` `tqdm` | `faster-whisper` `ctranslate2` `presidio-analyzer` `presidio-anonymizer` `spacy` `anthropic` `google-genai` `webvtt-py` `av` |

The missing set is small in count but contains all the heavy native code:
`ctranslate2` (38 MB), `spacy` (34 MB), `av` (35 MB), plus spaCy's `thinc`/`blis` chain.

### Options weighed

**1. Vendor all wheels as `Source:` entries; `pip install --no-index --find-links` in `%build`.**
Chosen — see §4. Downsides, plainly: the RPM ships manylinux binaries built against a
different toolchain than Fedora's, with no debuginfo, no Fedora hardening flags, and no
Fedora CVE tracking for anything in the vendored set. This is exactly what disqualifies
it from the official repos. For a Copr it is normal and accepted.

**2. `pyproject-rpm-macros` + a generated requirements freeze.**
Rejected. These macros assume dependencies resolve to *Fedora RPMs*. Nine are absent,
including all the native ones, so this reduces to "first build 9 dependency RPMs" —
and `spacy` alone drags in `thinc`, `blis`, `cymem`, `preshed`, `murmurhash`, `srsly`,
`catalogue`, `wasabi`, `confection`, `weasel`, `cloudpathlib`, `langcodes`,
`spacy-legacy`, `spacy-loggers`. That is a 20-package Copr to maintain forever, each
needing its own version bumps. Wildly out of proportion for a solo project.

**3. Ship a self-contained venv inside the RPM.**
Chosen, *combined with* option 1 — they are orthogonal. Option 1 answers "where do the
wheels come from", option 3 answers "what lands on disk". A private prefix at
`%{_libdir}/bristlenose` with a thin `%{_bindir}/bristlenose` launcher is also what the
Homebrew formula does (`libexec` venv) and what the Snap does, so all three Linux/macOS
channels have the same shape. Unclean by Fedora standards; consistent with our own.

**4. A `_service`-style SRPM generator that fetches outside `mock`.**
Chosen as the *mechanism* for option 1. Copr's SCM build method with
`--method make_srpm` runs `make -f .copr/Makefile srpm` in a container **with network**,
which is the sanctioned escape hatch. The generator pins and downloads the wheelhouse,
then tars it as `Source1`.

**5. `copr-cli create --enable-net on`.**
Copr exposes a per-project switch for build-time network access. It would make this whole
problem vanish — `%build` could just `pip install`, and the 248 MB `Source1`, the SRPM
generator and the per-Python wheelhouse would all be unnecessary.

Chosen against, but the usual reproducibility argument for doing so **does not survive
contact with this project's own practice** and should not be repeated as if it did. The
Snap does unpinned `pip install ".[serve]"` at build time *and* pipes NodeSource's
installer into `bash` (`snap/snapcraft.yaml:49`, `:70`); the Homebrew formula runs `pip
install` in `post_install`, on the user's machine, at install time. Both ship. Rejecting
option 5 for "two builds of the same tag can differ" while shipping those two would be
inconsistent — and note that `pip wheel "bristlenose[serve]==$VERSION"` pins only
bristlenose, so two wheelhouses generated a week apart differ too. **The vendoring is not
reproducible either; it is merely *recorded*.**

The honest reasons to prefer it are narrower: the SRPM is a self-contained artefact you
can re-download and rebuild from years later, which a networked build can never be; and
`--enable-net` is off by default and revocable, so a channel built on it is a channel that
can stop building for reasons outside the repo. Both are real. Neither is overwhelming.

**If this channel ever becomes a maintenance problem, `--enable-net` plus a committed
hash-pinned constraints file is the smaller design, and it would be a reasonable
retreat** — not a defeat.

### The decisive find: the PyPI sdist already contains the built React SPA

`bristlenose/server/static/` is gitignored but declared as a hatch `artifact`
([pyproject.toml:138](../pyproject.toml)), and `release.yml` runs `npm ci && npm run build`
*before* `python -m build`. So the published sdist carries 226 built SPA files, all 195
locale JSONs, and the man page — verified against `bristlenose-0.27.0.tar.gz`.

**Therefore: build the RPM from the PyPI sdist, not from git.** Serve mode works with
zero `npm` in `mock`. Building from git would require Node.js and a network `npm ci`
inside the build — the single hardest part of the Snap's `override-build`, avoided
entirely. This also matches Fedora convention, where `Source0` is conventionally the
PyPI sdist URL.

---

## 4. The design

```
Source0: https://files.pythonhosted.org/.../bristlenose-%{version}.tar.gz   (14 MB, has the SPA)
Source1: bristlenose-vendor-%{version}.tar.gz                               (213 MB wheelhouse)
```

`Source1` is produced by `.copr/Makefile` at SRPM time, where network is available:

```
pip wheel --wheel-dir=vendor "bristlenose[serve]==$(VERSION)"
```

`pip wheel` rather than `pip download` deliberately: `pysrt` publishes only an sdist, and
`pip download` leaves it as a `.tar.gz`. Installing that in `mock` would trigger a PEP 517
isolated build, which reaches for `setuptools` **from the network**. `pip wheel` builds it
to a wheel up front, so `%build` sees wheels only and never needs an index.

`%build` then, with no network:

```
python3 -m venv %{buildroot}%{_libdir}/bristlenose
pip install --no-index --find-links=vendor "bristlenose[serve]==%{version}"
```

Plus: the spaCy model `en_core_web_sm` is vendored the same way and installed into the
prefix, so `--redact-pii` works out of the box (the Snap does the same); the man page is
installed from `bristlenose/data/bristlenose.1` in `%install`, **not** `%post` — anything
placed after the link phase never gets symlinked, a trap already paid for on Homebrew
(`CLAUDE.md` § "Anything installed in brew `post_install` skips the auto-link phase").

`Requires: ffmpeg-free` — per §2 that is genuinely sufficient, so the RPM should depend on
it rather than on RPM Fusion's `ffmpeg`.

### Measured cost

All from the real build on Fedora 42 / x86_64 (Xeon 8488C, 2 vCPU):

| | measured |
|---|---|
| Wheelhouse (`Source1`) | **225 MB**, 107 wheels (106 + the spaCy model). An earlier run measured 213 MB / 106 before the spaCy model was added — both figures appear in this doc's history; 225 MB is the shipped one |
| sdist (`Source0`) | 14.3 MB |
| **SRPM** | **248 MB** |
| **Binary RPM** | **195 MB** |
| **Installed** | **823 MB**, 24,511 files on Fedora 43 (815 MB / 24,510 on Fedora 42, which Copr no longer builds for) |
| SRPM generation (network) | ~2 min cold, 23s warm |
| `mock` build (no network) | ~7 min |

823 MB installed is large — dominated by `ctranslate2`, `onnxruntime`, `spacy`+`blis`,
`av` and `numpy`. It is the honest cost of a self-contained ML CLI and is comparable to
the Snap. §7 records the subpackage split that would reduce it, and why it is not being
done yet.

### The dependency metadata, verified rather than assumed

The real risk with a vendored tree is rpm's automatic dependency generator: left on, it
scans the bundled `.so` files and emits both unsatisfiable `Requires` (sonames for
libraries bundled *inside* the wheels) and bogus `Provides` that leak a private venv into
the distro-wide namespace. `__requires_exclude_from` / `__provides_exclude_from` suppress
it — and the check that proves they worked is `rpm -qp` on the built package, not the
spec:

```
$ rpm -qp --requires bristlenose-0.27.0-1.fc42.x86_64.rpm
/usr/bin/ffmpeg
/usr/bin/ffprobe
python(abi) = 3.13
rpmlib(...)              ← plus four rpmlib entries

$ rpm -qp --provides bristlenose-0.27.0-1.fc42.x86_64.rpm
bristlenose = 0.27.0-1.fc42
bristlenose(x86-64) = 0.27.0-1.fc42
```

Three real requires, nothing unsatisfiable, no leaked sonames.

`Requires: /usr/bin/ffmpeg` names the **capability**, not the package: it is satisfied by
`ffmpeg-free` from the stock repos *and* by RPM Fusion's `ffmpeg` for anyone who already
has it, where naming `ffmpeg-free` would pin them to the lesser one.

`Requires: python(abi) = 3.13` is not optional. The venv's `bin/python3` symlinks to
`/usr/bin/python3` while its packages live in `lib/python3.13/`; without the pin, a Fedora
release upgrade would leave an installed package where **every import fails**, at runtime,
with no warning from dnf.

### One wheelhouse per Python — and the target is not what was tested

The vendored wheels are tagged for one Python minor, and an SRPM is a single artefact
shared by every chroot it is built for. A cp313 wheelhouse **cannot** satisfy a chroot
running 3.14: `pip install --no-index` fails on every heavy dependency at once, inside
mock, where it is least convenient to discover.

**And the chroot list makes this immediate, not theoretical.** `copr-cli list-chroots`
offers `fedora-43`, `fedora-44`, `fedora-45`, `eln` and `rawhide` — **there is no
`fedora-42-x86_64` chroot**. Everything in §6 was proven on Fedora 42, which Copr will
not build for. Fedora 43 ships **Python 3.14.7**, so the wheelhouse has to be cp314.

Checked, because "the wheels exist" is exactly the assumption that would fail late: every
heavy dependency does publish cp314 — `ctranslate2` 4.8.1, `spacy` 3.8.16, `onnxruntime`
1.29.0, `blis`, `thinc`, `tokenizers`, `numpy`, `pydantic-core`, and `av` via `cp311-abi3`.

**And then it was built.** Fedora 43 / Python 3.14.7 / **RPM 6.0.2** — a major rpm version
ahead of the 4.20.1 the first pass used — `mock` exit 0 with no network, and the whole
pipeline green afterwards (§6). **Nothing needed fixing for the newer platform**: the
`python(abi)` requires tracked to 3.14 on its own, the `brp-*` suppressions and the
`__requires_exclude_from` / `__provides_exclude_from` filters behaved identically under
rpm 6, and the metadata came out as clean as before — three requires, two provides. The
one number that moved is the installed size, 815 MB → **823 MB**, which is the newer
wheels rather than anything we did.

Because of that, the interpreter is now chosen rather than inherited: `make-srpm.sh` takes
`BN_PYTHON` and refuses to run if it is absent, and `.copr/Makefile` installs `python3.14`
and names it. Leaving it as "whatever the SRPM builder happens to ship" makes the SRPM's
correctness an accident of Copr's container image.

This is also the honest counter to the arch saving above: the channel already carries a
"regenerate per target" cost, so x86_64-only saves a wheelhouse, not the mechanism.

### Architecture: x86_64 only

**Decided: x86_64 only**, matching the Snap, which has only ever published amd64.

`aarch64` wheels exist for every heavy dependency (checked: `ctranslate2`, `spacy`,
`onnxruntime`, `av`, `blis`, `thinc`, `tokenizers`, `numpy` — all present, 126 MB), so
arm64 is *possible*. It is not *free*: an SRPM is one artefact for all arches, so
supporting both means either shipping both wheel sets (~340 MB SRPM) or `%ifarch`-guarded
`Source` entries. Fedora on laptops is realistically Intel/AMD, same as the Ubuntu target.
Revisit if arm64 Fedora demand appears.

---

## 5. `bristlenose doctor` grew an `rpm` arm — done

`detect_install_method()` knew `snap`, `brew` and `pip`. Measured on the installed RPM
before the change:

```
sys.prefix : /usr/lib64/bristlenose
detected   : pip
```

…so every fix message handed a Fedora user a pip command. For `serve_deps_missing` that is
not merely wrong-distro but **harmful**: `pip install 'bristlenose[serve]'` on Fedora either
refuses with `EXTERNALLY-MANAGED` or drops a second bristlenose into `~/.local/bin`, which
then shadows `/usr/bin/bristlenose` on PATH — the user ends up running a different copy than
the one they packaged.

**Detection is a marker file, not another path sniff.** The RPM's venv lives at
`/usr/lib64/bristlenose` and nothing about that path distinguishes it from any other venv, so
a heuristic would have to guess; the packaging recipe already knows the answer, so `%install`
writes `.install-method` into the prefix and `detect_install_method()` reads it from
`sys.prefix`. Any future packager can drop the same file instead of adding a fifth sniff. An
unrecognised value is ignored rather than trusted, so a typo in some future spec cannot invent
a method no fix message handles.

Five fix functions can fire on Linux — `ffmpeg_missing`, `backend_import_fail`,
`spacy_model_missing`, `presidio_missing`, `serve_deps_missing` — and all five get an `rpm`
arm of the same shape as `snap`'s: the RPM bundles ffmpeg's dependency, ctranslate2, the
spaCy model, presidio and the serve extras, so a missing one is a packaging defect and the
answer is `dnf`, not `pip`. `_fix_mlx_not_installed` is untouched; MLX is Apple-only.

The test pins the **invariant**, not the strings: no `rpm` fix may contain `pip install` or
`pipx`, and each must offer a `dnf` command. The spec asserts the same thing in `%check`, so
a build that would mis-detect itself does not become an RPM.

Still owed: an `rpm` column in `docs/design-doctor-and-snap.md` §"Install-method-specific fix
table". Note that table is **already stale** — 4 rows against 6 method-branching functions,
and its `mlx_not_installed` brew cell disagrees with the code — so adding a column without
truing the rest would compound the drift rather than document it.

---

## 6. What gets tested, and how

A container is **not** a Copr build. The tiers actually exercised:

| tier | what it proves | how |
|---|---|---|
| container (`fedora:41/42/43`) | codec support; which Python each release ships; that the wheels exist | Docker. **Not a mock build** — no chroot, no rpm, network available in the same shell |
| **`mock` on a real Fedora box** | the no-network `%build` genuinely works, and the spec is correct | `aella up --fedora`, real Intel Xeon 8488C — run on **Fedora 42** first, then re-run in full on **Fedora 43 / Python 3.14 / rpm 6.0.2**, which is what Copr actually builds |
| `dnf install` of the built RPM | file placement, the launcher, the man page, `doctor`, the install-method arm, a real transcription | same box, both releases |
| **Copr's own builders** | Copr's chroot, its rpm, its mock — the only tier we do not control | uploaded SRPM into an unlisted, auto-deleting project |

The middle two are the ones that matter for correctness and both ran on real x86_64
hardware, not emulation. The Copr tier is the gate in §7.

**What actually ran, and what it proved** (all of it twice — once on Fedora 42, then
again end-to-end on Fedora 43, the release Copr builds for):

- `mock -r fedora-42-x86_64 --rebuild`, **network unavailable throughout** — exit 0. The
  offline `pip install --no-index` resolved all 107 wheels from `vendor/` with no attempt to
  reach an index (`grep -iE "Looking in indexes|pypi.org|Downloading http"` on `build.log`:
  no matches).
- `%check` ran inside that build: version match, 13 imports including `ctranslate2` /
  `spacy` / `av`, both halves of the SPA present, and `detect_install_method() == "rpm"`.
- `dnf install` of the resulting RPM, then `bristlenose --version`, `bristlenose doctor`
  (all green bar the API key, which is not configured on a throwaway box), the launcher
  symlink, and `man -w bristlenose` resolving to the gzipped page.
- A real transcription: Teams-shaped H.264+AAC `.mp4` → correct transcript (§2), 12.6s
  on Fedora 43.
- `rpm -qp --requires/--provides` on the built package (§4).
- **The whole thing as a user would do it**, from a clean box:
  `sudo dnf copr enable cassiocassio/bristlenose-test` then `sudo dnf install bristlenose`.
  Copr signs what it builds, so the install imported a Copr GPG key and verified against it
  — which is worth noting against §3's "no Fedora hardening" caveat: the *package* is
  signed even though the vendored wheels are not built by Fedora.
- The two things this channel exists to get right, asserted on the installed RPM rather
  than in a test: `detect_install_method()` returns `rpm`, and the export bundle is
  present so `_build_export_html` no longer 500s.

**One defect only the *installed* package could have shown.** `_install_man_page`
([bristlenose/cli.py](../bristlenose/cli.py)) copies the man page into
`~/.local/share/man/man1/` on first run so a `pipx` user gets `man bristlenose`. It skipped
snap and Homebrew — via two inline sniffs — because those packagers ship their own. The RPM
does too, and was not skipped. On the Copr install, `man -w bristlenose` resolved to
`~/.local/share/man/man1/bristlenose.1`, **not** the rpm-owned
`/usr/share/man/man1/bristlenose.1.gz`: `man` reads `~/.local` first, so the home copy
shadows the packaged one, and because no package owns it `dnf remove` leaves it behind and
`man bristlenose` goes on working after the tool is gone.

Fixed by routing all three through `detect_install_method()` (§5) rather than adding a third
sniff. Note what found it: not a test, and not `mock` — a `man -w` on a machine where the
package was actually installed. The class is the one `CLAUDE.md` already names about the
desktop app: *a test asserts what someone thought to ask.*

**Three further defects the build tiers caught, in order.** A `tar | grep -q` guard in `make-srpm.sh` that
inverted itself under `set -o pipefail` (grep's early exit SIGPIPEs tar; pipefail reports
tar's 141 for the whole pipeline) — it declared a good sdist bad on its first run.
`pip install en_core_web_sm-3.8.0`, which is a filename stem, not a requirement. And the
export-bundle gap in §2a, which `%check` refused to build past.

---

## 7. Publishing: decided yes, with the costs recorded

It works. That is a measured claim, not a hope — §6, twice, on both Fedora releases.

**The call has been taken: ship the channel.** This section previously recommended holding,
and the arguments below are kept rather than deleted — not to relitigate a settled decision,
but because every one of them is a *recurring cost* that someone has to keep paying, and a
cost nobody wrote down is a cost that surprises you later. The technical risk is the part
that has actually gone away.

**For:** two idiomatic `dnf` commands; `dnf upgrade` keeps users current where `pipx`
silently does not; and the per-release cost really is small, because the wheelhouse is
generated rather than hand-listed and the version is read from `bristlenose/__init__.py`
like every other channel.

**Against — kept because these are the recurring costs, not because the decision is
still open:**

1. **There is no Fedora user.** The TF cohort was never enrolled; the tester is the
   maintainer. The cost of not shipping is a hypothetical person typing three pipx commands
   instead of two dnf ones.
2. **Retiring a Copr is not the cheap exit it looks like.** Once someone has run
   `copr enable`, retiring the repo means their `dnf upgrade` silently stops updating them
   — precisely the failure mode §1 uses to argue *against* pipx. "Try it and withdraw if it
   costs too much" is therefore not available in the form it appears to be.
3. **No CVE tracking for the vendored set.** A CVE in `ctranslate2` or `numpy` is invisible
   to `dnf` and has to be caught by our own dependency process, forever. That is a
   permanent obligation, not a one-off cost.
4. **A fourth Linux channel** to keep green alongside Snap, Homebrew and PyPI, plus a
   release-ordering constraint: the Copr can only build a version PyPI already has, so it
   lands *after* the 23–25 minute PyPI verification, not alongside it.
4a. **The wheelhouse tracks Fedora's Python, not ours.** Copr dropped fedora-42 while this
   was being written; F43 is 3.14 and F44/45 will move again. Each move needs a regenerated
   wheelhouse and a re-proof, and it happens on Fedora's schedule, not on release
   boundaries — the one recurring cost that is genuinely outside our control.
5. **823 MB installed**, which the deferred split below says is the wrong shape.

### What publishing obliges

Three of those are one-offs the decision absorbs. Two are standing obligations, and they
are the ones to hold onto:

- **CVE tracking for the vendored set is ours, permanently.** `dnf` cannot see inside the
  wheelhouse, so a CVE in `ctranslate2`, `numpy` or `onnxruntime` is invisible to the
  distro's own machinery. The existing dependency process (`cassandra`,
  `docs/dependency-premortem-log.md`) is the only thing standing there.
- **The wheelhouse tracks Fedora's Python, on Fedora's schedule.** Copr dropped `fedora-42`
  during the writing of this doc. Each Fedora release needs a regenerated wheelhouse and a
  re-proof, triggered by Fedora's calendar rather than ours. `.copr/Makefile` names
  `python3.14` explicitly so this fails loudly at build time instead of quietly resolving
  wrong — but it still needs a human to change the line.

### The ordering constraint — read before publishing

The Copr builds `Source0` from **PyPI**, so it can only build a version PyPI already has.
`%check` asserts both halves of the SPA, which means **it will refuse every release up to
and including 0.27.0** — those have no export bundle (§2a). The first publishable build
therefore waits on the next release.

Sequence, and it does not commute:

1. Release to PyPI, carrying the `static-export` fix. Verify with the version-specific
   endpoint, not the cached index (`CLAUDE.md`, post-push PyPI verification).
2. Push `rpm/` and `.copr/` so Copr has something to clone.
3. `copr-cli create bristlenose --chroot fedora-43-x86_64`, then `buildscm --method
   make_srpm`. Confirm the build is **succeeded**, not merely submitted.
4. *Then* the public docs go live — `INSTALL.md` §Fedora, `README.md`, and the website's
   `docs-src/install.md` + homepage Linux panel. Each is a promise that `dnf copr enable`
   will work.

Doing 4 before 3 ships instructions that fail. That is the one ordering mistake this
channel makes easy — **and it was made here, the same day this was written.** All four
surfaces were updated to name the Copr while `api_3/project` still returned 404, and
reverted only when a truing pass caught it. Two independent reviewers flagged it; nobody
noticed while writing the rule down. Writing an ordering constraint into a doc does not
enforce it, which is the argument for `probe_copr` and the preflight gate below being
mechanical rather than prose.

The reverted text is not lost — it is in this file's git history at `74b033df`, and the
flip commit can restore it verbatim.

### The release train

**Copr is Homebrew-shaped, with one difference that matters.** Both are downstream
repackagers of the PyPI artefact, so both fire *after* PyPI. `notify-homebrew` in
`release.yml` is `needs: publish` and dispatches an `update-formula` event at the tap.

The difference: **Homebrew's formula pip-installs from PyPI at *install* time; Copr fetches
the sdist at *build* time.** `publish` completing means twine uploaded — not that PyPI's CDN
is serving it yet, which is exactly what `verify-pypi` polls for, up to ten minutes. Homebrew
tolerates that race because the user installs later. A Copr build triggered on `needs:
publish` can 404 on `Source0`.

**So the Copr job is `needs: verify-pypi`, not `needs: publish`.** The release train already
has the gate this channel needs; it just has to be the one it hangs off.

```yaml
  trigger-copr:
    # NOT needs: publish — see above. verify-pypi is what proves the sdist is
    # actually fetchable, and Source0 is fetched during the Copr build.
    needs: verify-pypi
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@…
      - name: Trigger the Copr build
        env:
          COPR_LOGIN: ${{ secrets.COPR_LOGIN }}
          COPR_TOKEN: ${{ secrets.COPR_TOKEN }}
        run: |
          [ -n "$COPR_TOKEN" ] || { echo "::error::COPR_TOKEN not set"; exit 1; }
          pip install copr-cli
          umask 077; mkdir -p ~/.config
          printf '[copr-cli]\nlogin = %s\nusername = cassiocassio\ntoken = %s\ncopr_url = https://copr.fedorainfracloud.org\n' \
              "$COPR_LOGIN" "$COPR_TOKEN" > ~/.config/copr
          copr-cli buildscm bristlenose \
              --clone-url https://github.com/cassiocassio/bristlenose.git \
              --commit "$GITHUB_REF_NAME" --method make_srpm
```

**Not committed yet, deliberately** — it needs two repo secrets and a Copr project, neither
of which exists, and a job that warns on every release is noise rather than a gate.

**The probe *is* written**: `probe_copr` in `verify-channels.sh`, reading Copr's own
unauthenticated API, with three cases pinned in `test-verify-channels.sh` — the correct
version, a stale one, and a *failed* build (which must not read as shipped). It reports
`unreachable` for a project that does not exist yet, which is honestly different from
"built the wrong version".

**But `copr` is deliberately held out of `CHANNELS`.** `rollup()` counts `unreachable` as
not-ok — unverified is not verified — so listing the channel before its first build fails
every release verification in between, for a reason that is not a defect. `CLAUDE.md`:
*a gate that cries wolf gets switched off, which is worse than no gate.* The tests enable
`copr` in their own sandbox instead, so the probe is exercised and the switch is proven to
work before anyone flips it.

**Flip it in the same commit that creates the Copr project and lands its first green build.**
That commit is: `copr` into `CHANNELS`, the `trigger-copr` job above, and the two secrets.

**One recurring hazard, now gated.** The Copr API token expires every 180 days (this one on
23 Feb 2027), so a channel that ships a few times a year finds it dead exactly when it is
next needed. A date-based reminder exists, but the durable home is `check-release-ready.sh`,
where it now lives: the token matters *at release time*, and a gate that fires while you are
releasing cannot be missed the way a calendar entry fired while you were doing something else
can.

It checks two different things, because they fail differently:

- **Expiry**, read from the `# expiration date:` comment Copr writes into the config. Expired
  → fail; inside 30 days → warn; no expiry recorded → warn. Never touches the token itself.
- **Read-back**, when `copr-cli` is available: `whoami` must return `$COPR_OWNER`. The expiry
  comment is a *claim* about the token — a hand-edited file, a revoked token, or a config for
  the wrong account all read fine on expiry alone. Same discipline as `CredentialStore.set()`
  returning cleanly proving nothing. Without `copr-cli` it warns "unverified" rather than
  passing.

**It is gated on `CHANNELS`, so it renders nothing while `copr` is off** — and activates by
itself on the day the channel is enabled, with no second thing to remember. Nine cases pinned
in `test-release-sh.sh`, including that silence, and both the expiry thresholds and the
read-back fail the suite when broken.

### What shipped regardless

The export-bundle fix (§2a), which was worth the exercise on its own and is not a Fedora
thing at all, and the doctor `rpm` arm (§5).

**Deferred, deliberately:** splitting into `bristlenose` + `bristlenose-transcribe`
(faster-whisper/ctranslate2) + `bristlenose-redact` (presidio/spacy). It would cut the base
install from 823 MB to well under 200 MB, and it maps onto how the project already thinks
about extras — a researcher working from Teams/Zoom VTT files needs no Whisper at all.
`Recommends:` rather than `Requires:` would keep the default `dnf install bristlenose` fat
(so no new "not installed" state for the default user) while letting
`--setopt=install_weak_deps=False` get the slim one. It stays deferred because it is a
*product* decision about what `dnf install bristlenose` promises, not a packaging one.
