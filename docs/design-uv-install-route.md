---
status: in progress (step 1 done)
last-trued: 2026-11-28
---

# uv as the self-managed install route

**The question:** should `uv tool install bristlenose` be offered as well as pip and pipx, or instead of them?

**The position under test (owner, 28 Nov 2026):** as well as. uv takes pipx's place as the lead route for people who manage their own installs; pipx stays as the alternative; Homebrew, winget, the Snap and Copr keep their places as the convenience routes. uv serves Linux users who look after their own tools, people on a distro with no package, and people who won't use a Snap. *(An earlier version of this position put uv directly under the Snap line on Ubuntu. The owner reversed that on 28 Nov 2026 as counterproductive; see the Ubuntu ruling below.)*

**The rule (owner, 28 Nov 2026): don't swim against the flow.** The question isn't whether uv is better. For each distro people will be running in 2026–27, it's what works out of the box and what that distro's own users expect. Community momentum counts as a tiebreak, not as the reason.

**Decided (owner, 28 Nov 2026), after the evidence below:**
- **Ubuntu: the Snap. Fedora: our Copr.** Both are easy calls wherever we build for the architecture (today x86_64 for both, and release 43 for Fedora).
- **Debian and Raspberry Pi OS: pipx first**, uv second. apt ships pipx, and the OS's own pip refusal names it.
- **Everything else is roughly a wash, so it lists uv first**, then pipx. That means Arch and any other distro. The tiebreak is the direction of travel: ask in two years where pip and uv stand, and the answer is plain enough that it's time to start doing the work.
- **Keep the docs light (owner, 28 Nov 2026).** "The people who know will find it": a Pythonista on any of these platforms already has an opinion about pipx and uv. So the page gets an "Install with uv" section after the pipx one, plus "uv, pipx" in the table's catch-all row. There's no per-distro rework beyond that; Mint stays with Debian, and Fedora's fallback stays pipx.

The precondition: uv installs have to actually work end to end. Today they don't, in two places (§3), so the code fix comes first and the docs change after it.

### The grain, distro by distro (checked 28 Nov 2026)

"Its pip refusal says" is the PEP 668 `EXTERNALLY-MANAGED` text the distro ships: the message a user sees the moment `pip install bristlenose` is refused. That's the distro telling its own users what the convention is. Debian's and Arch's were read from their packaging source; Ubuntu and Mint inherit Debian's.

| Distro, release in use 2026–27 | `python3` | Its pip refusal says, for an application | pipx | uv | Lead | Then |
|---|---|---|---|---|---|---|
| Ubuntu 26.04 LTS | 3.14 | `pipx install xyz` (Debian's text) | apt | not in apt¹; curl installer or a Snap | Snap | none alongside; uv a link away |
| Ubuntu 24.04 LTS | 3.12 | `pipx install xyz` | apt | not in apt | Snap | none alongside; uv a link away |
| Mint 22 | 3.12 | `pipx install xyz` | apt | not in apt | pipx (Mint blocks snapd; kept with Debian) | uv |
| Ubuntu 22.04 LTS (to Apr 2027) | 3.10 | `pipx install xyz` | apt | not in apt | Snap | none alongside; uv a link away (brings a newer Python; see below) |
| Debian 13, Raspberry Pi OS | 3.13 | `pipx install xyz` | apt | not in apt | pipx | uv |
| Fedora 43, 44 | 3.14 | nothing yet: Fedora's marker change is still pending, so pip doesn't refuse | dnf | dnf, and Fedora Magazine promotes it | our Copr (43, x86_64); otherwise pipx | uv |
| Arch | rolling | `pipx install xyz`, "make sure you have python-pipx installed via pacman" | pacman | pacman (`extra`) | uv (a wash: the OS's message says pipx, the repo has both) | pipx |

¹ For 26.04, not confirmed against Ubuntu's own package index; confirmed for 24.04 and Debian 12 and 13.

Two things the evidence changed from the position under test:

- **Ubuntu ruling (owner, 28 Nov 2026): nothing goes directly under the Snap line.** The Snap is Ubuntu's own convention for applications, and it's the channel we build, test and update; putting an alternative right beside it is counterproductive for us. People who can't or won't use it (Arm, Snap-avoiders) reach the self-managed section by a link, as the website's Ubuntu section already does for Arm (its link goes to pipx, and stays that way). Someone who just wants the tool on Ubuntu follows the Snap instructions (owner).
- **uv bringing its own Python matters less than it seemed.** Every release in the table ships a Python Bristlenose runs on (3.10 or later; the Copr build already runs on 3.14). The case left is Ubuntu 22.04, whose 3.10 is too old for the any-llm extra (3.11 or later). That LTS is in its last standard-support year.

This is the end-user install route only. Moving the Homebrew formula, CI or the contributor venv onto uv is a separate developer-tooling question (`docs/design-cli-just-works.md` §"Debate 2"); root `CLAUDE.md` still says not to use uv for the dev venv, and nothing here changes that.

---

## 1. Where uv stands in Bristlenose today

Already shipped:

- README "Anything else" block: `pipx install bristlenose`, then `uv tool install bristlenose    # alternative`.
- INSTALL.md mentions uv as an aside on macOS and Linux, and makes it the step-by-step route on Windows.
- The Windows one-liner (`scripts/windows/install.ps1`) installs uv and then runs `uv tool install --python 3.13 bristlenose`. It's tested twice per push on `windows-latest` (`install-test.yml`, `windows-install-ps1`) and was exercised on real Windows on 5 Oct and 19 Nov 2026 (`docs/design-windows-port.md`).
- `bristlenose/utils/install_channel.py` recognises a uv tool environment by its directory, and the voice and any-llm hints give uv users a `uv tool install --force` command that keeps the extras they already have.
- The `serve`-deps hint in `doctor_fixes.py` gives `uv tool install --reinstall bristlenose`.

Not yet in place:

- `detect_install_method()` in `doctor_fixes.py` returns `"pip"` for uv (its comment says so). Every fix keyed on that function treats a uv user as a pip user.
- `install-test.yml` has no uv job on Linux or macOS; pip and pipx have one each.
- The website's Linux table sends Debian, Mint, Raspberry Pi OS, Arch and "anything else" to pipx, with uv only as a parenthesis.

---

## 2. The evidence

### Confirms

- **Momentum is real and measured.** In Stack Overflow's 2025 survey uv was the most admired technology in its category (74%). The PSF/JetBrains Python Developers Survey put uv at 11% usage, up sharply from the year before; that figure comes from The Register's report, not the survey page itself. uv's own PyPI downloads were about 128 million a month against pip's 624 million (Socket.dev, 30 days to 15 Oct 2026), and that undercounts uv, because its curl installer and release binaries bypass PyPI. Older installer-share snapshots go from 4.8% (PEP 777's appendix) to about 23% of trackable installer traffic (a Python Discourse thread, now about 18 months old).
- **uv is packaged where the self-managers live.** Arch has `uv` in `extra` (`pacman -S uv`). Fedora has had `uv` since release 40 (`dnf install uv`). Alpine has it in community. So on those distros uv comes from the distro's own package manager, which is exactly what someone who looks after their own system wants.
- **Snap aversion is policy, not just mood.** Linux Mint has blocked `snapd` from installing through APT by default since Mint 20 (2020), after Ubuntu made Chromium a Snap, and later releases kept the block. So a Mint user can't use our Snap without first undoing a distro default. Our Snap is x86_64-only. It's also edge-only for now, but that changes when the App Store version goes live, with winget expected around the same time (owner, 28 Nov 2026). So edge-only is no argument for another route; the aversion is.
- **uv brings its own Python; pipx uses the system one.** If no compatible interpreter is on the machine, uv downloads a managed build (python-build-standalone). pipx installs into whatever Python is there. Our own code already pays for that difference: the any-llm hint tells pipx users to reinstall with `--python python3.12` (`llm/anyllm.py`), which only works if the box already has a 3.12. The Windows route pins `--python 3.13` to sidestep the voice extra's 3.14 gap. On Linux in 2026–27 this rarely matters (see the table above); Ubuntu 22.04 is the case where it does.
- **The two tools are near drop-in.** pipx's own comparison page maps `pipx install X` to `uv tool install X` almost one for one, so swapping which one leads costs docs, not concepts.

### Refines

1. **Debian and Ubuntu don't ship the `uv` command.** Debian's `uv` source package builds only `python3-uv-build` (the build backend). Ubuntu doesn't provide the CLI in apt either. Debian's own `tox-uv` notes point people to the upstream installer or pipx. On those systems uv means one of:
   - Astral's `curl … | sh` installer;
   - `pipx install uv`;
   - a Snap (`astral-uv`), which is the very route this group is avoiding;
   - a one-person third-party apt repo.

   **So across the Debian family, Ubuntu included, pipx stays the lead**: `apt install pipx` is distro-native, and the OS's own pip refusal tells users to use it. uv is the named alternative. Fedora (when not on 43) leads with uv; Arch is a tie (see the table).
2. **Fedora's `uv` package turns off Python downloads.** A third-party guide reports that Fedora's RPM ships `/etc/uv/uv.toml` with managed-Python downloads disabled, preferring the system interpreter. If that's right, `--python 3.13` on Fedora fails unless that Python is installed (`dnf install python3.13`). Not checked on a Fedora box yet.
3. **Don't install with both.** pipx and uv both put their shims in `~/.local/bin`. Someone switching should run `pipx uninstall bristlenose` first. That belongs in the docs, and maybe in `doctor`.

### Against (weighed, not decisive)

- **Ownership.** OpenAI announced on 19 Mar 2026 that it would acquire Astral. I found no confirmation that the deal has closed. Both companies say the tools stay open source, and they're MIT/Apache-2.0, so a fork is possible. Simon Willison notes OpenAI has little track record of maintaining open-source projects. For Bristlenose the exposure is small: we recommend a command, we don't build on it. pipx stays as the fallback, and the Windows installer is the only place we'd need to swap tools.
- **pip still carries most PyPI traffic**, about 5:1 by download count. But that counts every CI job; it says little about what a researcher types.
- **Our own channel mix is unknown.** We have no measurement of how Bristlenose users install. PyPI's public download data records the installer for each download, and querying it for `bristlenose` would answer this directly. That query sends the package name to an outside service, so it waits for the owner's go-ahead.

---

## 3. What breaks in a uv install today (verified 28 Nov 2026)

A uv environment has no pip: on uv 0.10.11, `python -m pip` in a fresh `uv venv` fails with "No module named pip". pipx environments do have pip, through pipx's shared libraries. Two runtime installs depend on pip.

1. **PII redaction, first run.** `ensure_spacy_model` runs `python -m spacy download` (`utils/package_install.py`). With no pip, spaCy falls back to `uv pip install` when `uv` is on PATH (`spacy/cli/download.py`, `_get_pip_install_cmd`). From a uv tool install that command doesn't target the tool's environment:
   - with no virtualenv around, it fails with "No virtual environment found";
   - if the current folder or any parent has a `.venv`, it installs the 400 MB model **into that unrelated environment**.

   Both behaviours were reproduced with `uv pip install --dry-run`. Either way the confirming `spacy.load` afterwards fails, so it's loud, not silent. The in-process download into the user cache that Snap and RPM installs use (`s07_pii_removal.fetch_spacy_model`) already avoids pip; uv installs just aren't routed to it. This also undercuts the hint we give winget users ("To use --redact-pii, install Bristlenose with uv instead").
2. **`doctor --fix` for MLX on Apple silicon.** `get_mlx_install_command` runs `sys.executable -m pip install mlx mlx-whisper`, which fails outright under uv.

Hints that give a uv user the wrong command: the spaCy-model hint (`python3 -m spacy download …`) and the Presidio hint (`pipx inject …`; Presidio is a core dependency, so a missing one means a broken install anyway).

Since run end to end (§6): with the released 0.48.0, `spacy download` failed with "No virtual environment found" on every distro. With this checkout, a real `--redact-pii`-equivalent run fetched the model into the user cache and redacted the real transcripts.

---

## 4. The plan

1. **Make uv installs work (reliability; fits the beta's no-new-features rule).** *Done 28 Nov 2026: `2cc85d3bd`, then the overnight follow-ups in §6.*
   - A pip-less install that isn't a frozen build now takes the in-process spaCy download into the user cache (`spacy_model_needs_user_cache` in `s07_pii_removal.py`, asking the new `install_channel.pip_available()`). It's keyed on whether pip is importable, not on a directory, so it covers any pip-less environment. The Mac app and the winget build are left out on purpose: each keeps its own answer.
   - `doctor --fix` for MLX runs `uv pip install --python <this python> mlx mlx-whisper` when there's no pip and `uv` is on PATH. That's the same "install into this environment" behaviour as the pip command it replaces, so it's no more permanent than before.
   - The hints are channel-aware where a uv user was told the wrong thing. The spaCy hint names the cache. The MLX hint names the `apple` extra through `add_extra_command` (persistent across rebuilds). The Presidio hint says `uv tool install --reinstall`, since Presidio is a core dependency. `installed_extras()` now detects `apple`, so a later voice or any-llm hint keeps MLX instead of rebuilding without it.
   - `detect_install_method()` is unchanged; the hints ask `install_channel()` or `pip_available()` instead, which keeps the change off every other caller.
   - Tests: `tests/test_uv_install_route.py`, 11 tests. Each of the six fixes, reverted alone, turns at least one red. Not done: an AST sweep requiring a pip check beside every `-m pip` argv. Today there's one such site, and its outcome test covers it.
2. **Test uv in CI.** *Written 28 Nov 2026, not yet run: nothing is pushed.* One `uv` job in `install-test.yml`, on `ubuntu-latest` and `macos-latest`. It runs Astral's installer, then `uv tool install --python 3.14 .`, `bristlenose --version`, a check that the tool env has no pip and that stage 7 chooses the user-cache route, and `scripts/check-doctor-install.sh`.
3. **Docs, kept light.** *Website done 28 Nov 2026, uncommitted in the website repo and not deployed.* In `docs-src/install.md`:
   - The table's catch-all row is split. "Debian, Raspberry Pi OS, Linux Mint" stays on pipx; "Arch and anything else" lists uv, then pipx.
   - The Arch section offers both, with the `pacman` line for each.
   - A new "Install with uv" section follows "Install with pipx": `pacman` and `dnf` lines, Astral's installer for everywhere else, `uv tool update-shell` if the command isn't found, and `pipx uninstall bristlenose` first for anyone switching.
   - Overnight, from the walk (§6): `uv tool install --python 3.14 bristlenose`, with one line on why, and a `pipx ensurepath` line in the pipx section. Arch doesn't put `~/.local/bin` on PATH.
   - The README and INSTALL.md keep their own layouts. Their uv lines now carry `--python 3.14` too.
   - The man page isn't affected: it doesn't document install routes.

   Revisit the table yearly. It changes when a distro does: Debian or Ubuntu packaging the uv CLI, Fedora shipping its marker, or a distro's pip refusal naming uv.
4. **Later, only if the numbers ask for it:** the PyPI installer-share query for Bristlenose, to see whether pipx has users worth keeping as the lead anywhere.

Order: 1 before 3. Recommending uv first while its PII path breaks would send people to the route that fails.


---

## 5. Open for discussion

1. **Should `doctor` notice a double install** (bristlenose in both pipx and uv, with one shadowing the other on PATH)? It's cheap to detect, but it's a new check.
2. **The PyPI installer-share query for `bristlenose`:** run it? It sends the package name to Google BigQuery or ClickHouse's public dataset.
3. **Does the winget page keep pointing PII users at uv?** Once step 1 lands it works; until then that advice leads into the failure in §3.

---

## 6. The walk: following our own page in fresh containers (28 Nov 2026, overnight)

`experiments/uv-install-walk/` (README there). Each run follows the website's Linux page to the letter in a fresh container, as a user with sudo. It then transcribes a real project and runs `probe.py`, which checks:
- the transcripts;
- an FFmpeg thumbnail from every video;
- PII redaction on the real transcripts, where asked;
- `bristlenose serve`, answering `/api/health` and `/report/`.

The project was cut from the Talismanic recordings (public test data): two Teams MP4s and a Google Meet MP4 with their original names, the Teams Word transcript, a phone-style HEVC `.MOV`, M4A, MP3 and WAV audio, a silent WAV and a cloud VTT. No LLM call, nothing billed.

**Matrix:** Debian 12 and 13, Ubuntu 22.04, 24.04 and 26.04, and Fedora 43 and 44, on native Arm; Arch as x86_64 under emulation. Each was run with pipx and with uv, plus macOS (Apple silicon) with uv, isolated in scratch directories.

**Results:**
- **Install and doctor.** Every route installs. `doctor`'s only failing row anywhere is the missing API key.
- **Transcription.** All 8 speech sessions transcribe everywhere, the HEVC phone file included. The silent WAV is correctly left with no segments.
- **PII redaction.** The same 238 redactions on Debian, Fedora, Arch and macOS with uv.
- **Serve.** It answers `/api/health` and serves the report everywhere.
- **Thumbnails.** All drawn, except the HEVC file on Fedora, where `ffmpeg-free` can't decode HEVC. The page already says so.
- **macOS.** The MLX fix ran its real `uv pip install`, and the next transcription used MLX.

**What the walk found, and what was done:**
1. **uv's own default Python, 3.15, can't install Bristlenose.** onnxruntime (faster-whisper's dependency) has no 3.15 wheel. Ubuntu and Fedora were fine because uv used the system Python. Debian's image has no system Python, so uv downloaded 3.15 and the install failed. Fedora's packaged uv sets `python-downloads = "manual"` and `python-preference = "system"` (its `/etc/uv/uv.toml`), so `--python 3.13` fails there, while `--python 3.14` uses the system 3.14. **Fix:** every uv install line says `--python 3.14`: the website, the README, INSTALL.md (macOS and Linux) and the CI job. Windows keeps 3.13, for the voice extra. The voice extra installs on 3.14 on Linux, Arm and x86_64. uv's receipt records `python = "3.14"`, so our own `uv tool install --force "bristlenose[…]"` hints keep it (checked: still 3.14.10 after a `--force`).
2. **The released 0.48.0's PII first run fails on every uv install**, with spaCy's "No virtual environment found". Reproduced on every distro; this checkout fetches into the user cache instead.
3. **Arch puts no `~/.local/bin` on PATH.** Both routes need the PATH line. The uv section had `uv tool update-shell`; the pipx section now has `pipx ensurepath`.
4. **The uv route on Debian and Ubuntu needs `curl` or `wget`**, for Astral's installer. Desktops ship `wget`; Docker images ship neither.
5. **Channel detection missed a moved tool dir.** Under a custom `UV_TOOL_DIR`, a uv install was told to `pip install` its extras. **Fix:** `install_channel()` reads uv's `uv-receipt.toml` and pipx's `pipx_metadata.json` in the environment first, with the path as fallback. The serve-deps hint now asks the same function instead of its own sniff.
6. **Bare `pip install` hints for everyone.** The Apple-silicon MLX lines in transcription and the hardware check, and the MCP extra line in `serve`, told pipx and uv users `pip install …`. **Fix:** all three use `add_extra_command`. `installed_extras()` detects `mcp` too, so a later hint keeps it. The transcription-backend hint gets a uv branch.

7. **Intel Macs need an older Python.** Seen natively on a 2014 MacBook Pro (macOS 11.4, x86_64): onnxruntime stopped publishing macOS x86_64 wheels after 1.23.2 (Python 3.10–3.13), and on macOS 11 and 12 the newest that installs is 1.19.2 (up to 3.12). So `--python 3.14` and `--python 3.13` both fail there, and `--python 3.12` installs. Intel Macs are a stated CLI target (`docs/design-platform-policy.md`, the cryptography pin). **Fix:** INSTALL.md's macOS uv line says `--python 3.12`. That works on every Mac and is the Python the Homebrew formula and the Mac app use. Linux keeps 3.14. With 3.12 and a working FFmpeg (that machine's Homebrew FFmpeg was broken, below), audio transcription, PII redaction (the user-cache route) and serve all ran natively on x86_64.
8. **`uv tool install --force` does not keep the Python.** On the Intel Mac, a working 3.12 install was rebuilt on 3.14 when `--force` was given no `--python`, and the rebuild failed. On Linux it happened to keep 3.14 only because no newer Python was installed. Our hints used exactly that form. **Fix:** every uv rebuild we suggest names the running Python (`install_channel.uv_python_flag()`): the extra hints, any-llm's `--with` hint, and the serve-deps, Presidio and transcription-backend reinstall lines.
9. **A broken media toolchain stopped `transcribe` with a Python traceback**, worded as if the recording were at fault. On the Intel Mac, Homebrew's ffprobe aborted on a missing `libx265` dylib, and stage 2's `AudioToolError` propagated bare. **Fix:** `Pipeline._extract_audio_or_abandon` turns it into a clean stop on all three stage-2 calls (`run`, `transcribe`, the late decode). The banner says "FFmpeg or ffprobe is installed but failed to run. Run `bristlenose doctor` to see why." The `missing_binary` Cause carries no file name; the full text goes to the local log. `tests/test_stage2_toolchain_abandon.py` pins the outcome, and an AST check confirms that no stage-2 call bypasses the guard.
10. **`doctor` showed ✓ FFprobe for an ffprobe that aborts.** The row only checked that the file existed. **Fix:** it runs `ffprobe -version` as the FFmpeg row does, and says "found, but it will not run (dyld: …)". It stays a warning, as a missing ffprobe is, because only video needs it.

**Rerun on the committed code** (a wheel of `efbc71b1b`): Debian 13, Ubuntu 24.04 and 26.04, and Fedora 44 with uv, plus macOS (Apple silicon) all pass the real-media probe. Fedora's HEVC thumbnail is the documented exception. The voice hint each install prints, run word for word, installs the extra and keeps the same Python.

**Then, the same night:**
- **Windows 11 on Arm** (the UTM test VM, `experiments/uv-install-walk/windows-walk.ps1`). INSTALL.md's uv route, `uv tool install --python 3.13 bristlenose`, gives a native ARM64 Python 3.13.18, and the engines install. The released 0.48.0's PII first run fails with "No virtual environment found", as everywhere. With this checkout, all 8 speech sessions transcribe, every thumbnail is drawn (HEVC included; winget's Gyan FFmpeg), PII gives the same 238 redactions through the user cache, serve answers, and the uv hint names `--python 3.13`.
- **x86_64 Linux, emulated:** Ubuntu 24.04 with uv (PII included) and Debian 13 with pipx, on a smaller project (a Teams video, the HEVC `.MOV`, an M4A and the VTT). Both pass. Emulation makes transcription about 20× slower; that is the emulator, not the product.
- **Not supported, by any route:** 32-bit Arm (32-bit Raspberry Pi OS) and musl distributions (Alpine). ctranslate2, the transcription engine, publishes no `armv7l` or `musllinux` build for any Python. The website's Debian and Raspberry Pi section now says the Pi needs the 64-bit OS.

**Later still:**
- **Windows on Arm needs the x64 Python named.** Astral's Arm64 uv (fetched from its release, as a native Arm64 PowerShell would get it) asked for `--python 3.13` picks an Arm64 CPython. ctranslate2 publishes no `win_arm64` wheel for 3.13, so the install fails. Asked for `cpython-3.13-windows-x86_64-none`, it installs, and the probe passes everything under Windows' x64 emulation (wheels `win_amd64`, platform `win-amd64`). The earlier "ARM64" runs were x64 Pythons: `platform.machine()` names the machine, not the process. **Fix:** the one-liner asks for the x64 Python when `Win32_Processor.Architecture` is 12 (parsed, PSScriptAnalyzer clean and evaluated on the VM). `uv_python_flag()` names it for an x64 Python on Arm64 Windows; the voice hint it prints, run word for word with the Arm64 uv, installs and stays x64. INSTALL.md and the website tell Arm PCs to write the full request in their own commands.
- **The new CI job, replayed without a push.** Both legs of `install-test.yml`'s `uv` job were run step by step: Linux in an x86_64 `ubuntu:24.04` container from a `git archive` of HEAD (no built frontend, as on the runner), and macOS isolated on this Mac. Both pass. The job also gains a step that synthesises a sentence (`espeak-ng`, `say`), transcribes it with the tiny model and checks the words came back. Until now no job ran FFmpeg and Whisper on real audio (`full-run`'s fixtures are VTT); the step was proven on x86_64 Linux and macOS. Whether `say` works on the hosted macOS runner is for the first real run to show.
- **Intel Mac video stays blocked** by that machine's FFmpeg. A `/tmp` library shim let `ffmpeg -version` run, but reading any file binds `x265_api_get_176`, which the newer x265 lacks. It was a real end-to-end test of the new stage-2 stop, though: every file's refusal logged, one clean banner, a Cause with no file name. A download of a stand-in FFprobe was refused as a third-party binary; `brew reinstall ffmpeg` on that Mac is the owner's call. Its Docker Desktop 2.3 never starts its daemon (likely waiting on a dialog).

- **Three tests that failed under load or on their own now test their claim** (`63dbc8274`, each mutation-checked):
  - The cloud-fetch budget test records each file's wait bound instead of timing the run.
  - The redirected cp1252 test no longer compares two runs of `pipeline`. That command lists this machine's Ollama models through a 0.3 s port probe and a 2 s `ollama list`, so two runs could differ.
  - The PII-on-3.14 test imports Presidio before faking the version; under a fake 3.14, Presidio's import reached for `annotationlib`.

  The full suite then passed with nothing failed (11,516).

**Native x64 Windows, clean (benbecula's VirtualBox `win11-26h2`, 28 Nov 2026).** The one-liner, run as the signed-in test user through `experiments/uv-install-walk/vbox-uv-walk.sh` (a companion to `packaging/windows/vbox-test.sh`), installs uv, FFmpeg from its pinned zip and Bristlenose (x64 Python 3.13, `win_amd64` wheels).
- **On a clean Windows the engines cannot load.** The image has no Microsoft Visual C++ runtime (no `msvcp140.dll` or `vcruntime140*.dll` in System32), and uv's Python carries none. So ctranslate2 ("Could not find module … ctranslate2.dll (or one of its dependencies)"), spaCy's thinc and the voice pass all fail. Doctor said "reinstall", which cannot help. CI's runner and the UTM VM evidently have the runtime, so nothing caught it. The winget build carries its own and transcribed on these VMs on 9 Oct.
- **Microsoft's redistributable needs administrator rights.** `vc_redist.x64.exe /quiet` exits 1602 without elevation, and the one-liner promises none.
- **Proven no-admin fix:** PyPI's `msvc-runtime` in the tool environment, plus `os.add_dll_directory(sys.prefix)` before the engines load. The DLLs alone in the venv are not enough: Windows looks beside the base `python.exe`. With both, the real CLI passes everything above.
- **Done:** doctor names the missing runtime with Microsoft's link (`msvc_runtime_missing`, architecture from the Python), proven on the VM. `bristlenose/utils/windows_runtime.py` names `sys.prefix` to Windows at import when the DLLs are there, and does nothing otherwise. INSTALL.md and the website say what to do on a newly set-up PC.
- **Owner's call:** make `msvc-runtime; sys_platform == 'win32'` a dependency. With the import-time call already in, that one line makes the one-liner and uv work on a clean PC with no admin. It is a third-party package (it repackages Microsoft's redistributable DLLs), so it is a supply-chain decision. Until then a user can add `--with msvc-runtime`, but a later `uv tool install --force …` hint drops it again.
- **The harness's VMs expired.** The snapshots' test user was made on 9 Oct, and Windows' 42-day password age locks guest control out since about 20 Nov ("guest additions never answered"). `BN_GUEST_CLOCK=2026-11-19`, now in both `vbox-test.sh` and the walk, boots the guest on a date that works, with host time sync off, and resets it afterwards. It must be after the TLS certificates' start (10 Oct failed against GitHub). Run everything in one guest logon: the guest's own time service corrects the clock once online, and a second logon then fails. The lasting fix is a rebuilt snapshot whose password never expires.

**Not covered:** the Snap and Copr (unchanged routes); the Windows one-liner as a signed-in user (the VM walk ran as SYSTEM through the guest agent; the one-liner has its own CI job); Linux Mint (Ubuntu 24.04 is its base); native x86_64 Linux (Docker on the Intel Mac waits on a dialog; Linux x86_64 ran emulated); video on the Intel Mac (its ffprobe is broken, and the stand-in FFmpeg had none); and analysis (needs a key).

**Not ours, seen on the way:** `tests/test_doctor.py::TestCheckPiiDiagnosesTheModelDirectory::test_on_314_the_incompatibility_is_what_it_says` fails when run alone and passes in file order, so it depends on an earlier test in that file. Recorded, not chased.

---

## Sources

- Stack Overflow Developer Survey 2025, technology: https://survey.stackoverflow.co/2025/technology/
- The Register on the PSF/JetBrains survey (uv at 11%): https://www.theregister.com/software/2025/08/19/python-usage-growing-while-foundation-struggles-for-funds/937983
- JetBrains, The State of Python 2025: https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025
- Socket.dev, uv glossary (download counts): https://socket.dev/glossary/uv
- PEP 777 appendix, installer usage on PyPI: https://peps.python.org/pep-0777/appendix-pypi-download-analysis/
- Python Discourse, PyPI download statistics and CI: https://discuss.python.org/t/pypi-downloads-statistics-and-continuous-integration/91810
- Arch Linux package `uv`: https://www.archlinux.org/packages/extra/x86_64/uv
- Fedora package `uv`: https://packages.fedoraproject.org/pkgs/uv/uv/fedora-44.html
- Fedora Magazine on uv: https://fedoramagazine.org/enhancing-your-python-workflow-with-uv-on-fedora/
- Debian package tracker `uv`: https://tracker.debian.org/pkg/uv
- Debian `tox-uv` README.Debian: https://metadata.ftp-master.debian.org/changelogs/main/t/tox-uv/stable_README.Debian
- uv as a Snap (`astral-uv`): https://snapcraft.io/astral-uv
- Debian's `EXTERNALLY-MANAGED` text (Python packaging source): https://salsa.debian.org/cpython-team/python3/-/raw/master/debian/EXTERNALLY-MANAGED.in
- Arch's `EXTERNALLY-MANAGED` text: https://gitlab.archlinux.org/archlinux/packaging/packages/python/-/raw/main/EXTERNALLY-MANAGED
- Fedora change proposal, mark Python externally managed (pending): https://www.fedoraproject.org/wiki/Changes/PythonMarkExternallyManaged
- Ubuntu 26.04 ships Python 3.14: https://computingforgeeks.com/install-python-ubuntu-2604/
- Fedora 43 and 44 use Python 3.14: https://linuxcapable.com/how-to-install-python-on-fedora-linux/
- Linux Mint 20 blocks snapd (LWN): https://lwn.net/Articles/825005
- Re-enabling Snap on Mint (It's FOSS): https://itsfoss.com/enable-snap-support-linux-mint
- uv managed Python: https://docs.astral.sh/uv/guides/install-python/
- pipx vs uv comparison: https://pipx.pypa.io/stable/explanation/comparisons/
- uv tools: https://docs.astral.sh/uv/concepts/tools/
- OpenAI to acquire Astral: https://openai.com/index/openai-to-acquire-astral
- Simon Willison on the acquisition: https://simonwillison.net/2026/Mar/19/openai-acquiring-astral
- The New Stack on the acquisition (closing pending): https://thenewstack.io/openai-astral-acquisition/
