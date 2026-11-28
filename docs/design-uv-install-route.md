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

Not run end to end: a real `uv tool install bristlenose` followed by `run --redact-pii`. The mechanism is proven piece by piece above; step 1's test should make the whole failure happen before the fix lands.

---

## 4. The plan

1. **Make uv installs work (reliability; fits the beta's no-new-features rule).** *Done 28 Nov 2026, uncommitted at the time of writing.*
   - A pip-less install that isn't a frozen build now takes the in-process spaCy download into the user cache (`spacy_model_needs_user_cache` in `s07_pii_removal.py`, asking the new `install_channel.pip_available()`). It's keyed on whether pip is importable, not on a directory, so it covers any pip-less environment. The Mac app and the winget build are left out on purpose: each keeps its own answer.
   - `doctor --fix` for MLX runs `uv pip install --python <this python> mlx mlx-whisper` when there's no pip and `uv` is on PATH. That's the same "install into this environment" behaviour as the pip command it replaces, so it's no more permanent than before.
   - The hints are channel-aware where a uv user was told the wrong thing. The spaCy hint names the cache. The MLX hint names the `apple` extra through `add_extra_command` (persistent across rebuilds). The Presidio hint says `uv tool install --reinstall`, since Presidio is a core dependency. `installed_extras()` now detects `apple`, so a later voice or any-llm hint keeps MLX instead of rebuilding without it.
   - `detect_install_method()` is unchanged; the hints ask `install_channel()` or `pip_available()` instead, which keeps the change off every other caller.
   - Tests: `tests/test_uv_install_route.py`, 11 tests. Each of the six fixes, reverted alone, turns at least one red. Not done: an AST sweep requiring a pip check beside every `-m pip` argv. Today there's one such site, and its outcome test covers it.
2. **Test uv in CI.** Add `linux-uv` and `macos-uv` jobs to `install-test.yml`: `uv tool install .`, `bristlenose --version`, `bristlenose doctor`, and a check that the spaCy route chosen is the user-cache one (not a 400 MB download per run).
3. **Docs, kept light.** *Website done 28 Nov 2026, uncommitted in the website repo and not deployed.* In `docs-src/install.md`:
   - The table's catch-all row is split. "Debian, Raspberry Pi OS, Linux Mint" stays on pipx; "Arch and anything else" lists uv, then pipx.
   - The Arch section offers both, with the `pacman` line for each.
   - A new "Install with uv" section follows "Install with pipx": `pacman` and `dnf` lines, Astral's installer for everywhere else, `uv tool update-shell` if the command isn't found, and `pipx uninstall bristlenose` first for anyone switching.
   - The README already lists uv in its "Anything else" block, and INSTALL.md has its own layout. Both are left as they are.
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
