---
status: proposed — a starting point, after the App Store; nothing here is built
last-trued: 2026-11-18
trued-against: HEAD@claude/clever-volta-j3fvkb on 2026-11-18 (18f479b)
---

# Windows and Linux hardware testing: where the real risk is

## What this is

The starting point for testing Bristlenose on Windows and Linux *hardware*, written
on 18 Nov 2026 when the old Intel Mac (`benbecula`) that carried the client-Windows
VMs was about to leave. It records what that machine actually covered, where
hardware-dependent risk actually lives in this product, what cloud can and cannot
replace, and the code defects that fell out of reading the CUDA path. Work it after
the App Store; the code fixes in §5 can go earlier, because they need no hardware.

The short version: **the risk is not "client Windows vs Server", and not x64 vs
Arm. It is the transcription engine choosing a code path from the hardware it
finds: CPU vendor, instruction set, and above all an NVIDIA GPU.** The user most
exposed is a researcher on a high-end Intel Windows (or Linux) laptop with a good
NVIDIA GPU, and nothing has ever run that path on real hardware.

Sibling docs: [`design-test-environments.md`](design-test-environments.md) (the
instruments; this doc proposes changes to its §2 and §5),
[`design-winget.md`](design-winget.md) and [`release-winget.md`](release-winget.md)
(the Windows installer and its per-release checks),
[`design-deployment-targets.md`](design-deployment-targets.md).

## 1. What changes when benbecula goes

`benbecula` (2014 MacBook Pro, Haswell i7, Big Sur, VirtualBox 7.0.26) ran
`packaging/windows/vbox-test.sh` against two VMs: Windows 10 22H2 Pro and the
Windows 11 26H2 Enterprise evaluation (which expires 7 Jan 2027 regardless).
Nothing else depended on it.

What it covered, read honestly:

- **Client Windows editions**, natively, for the installer: install, `--version`,
  `doctor --self-test`, a real transcription, the PATH entry, uninstall.
  `winget validate` and `winget install --manifest` ran there by hand (Win10 ships
  no winget).
- **Without anyone deciding it, the typical-Intel-laptop CPU path**: a native Intel
  CPU with AVX2 and no AVX-512, which is what most Intel laptops are. No other
  machine we have takes that path (§2).

What it never covered: SmartScreen or Smart App Control (files copied in carry no
Mark of the Web), an AMD CPU, any GPU, realistic speed.

VirtualBox on Apple silicon runs only Arm guests, so `vbox-test.sh` has no
successor host. The checks themselves are worth keeping (§6.1).

## 2. Where hardware-dependent behaviour actually lives

The installer, Python, file paths, PATH and the report do not care which x64 CPU
they run on. The transcription engine does. CTranslate2 (under faster-whisper)
decides at runtime:

- **Backend by CPU vendor**: Intel MKL only on a genuine Intel CPU; other vendors
  get a different backend. `CT2_USE_MKL` overrides.
- **Code path by instruction set**: AVX-512, AVX2, AVX or generic. `CT2_FORCE_CPU_ISA`
  overrides CTranslate2's own kernels; MKL has its own (`MKL_CBWR`).
- **Device**: CUDA if it counts an NVIDIA GPU, which it does whenever a driver is
  present, whether or not the cuBLAS and cuDNN libraries it then needs are there.

Which path each machine takes:

| Machine | Path | Stands in for |
|---|---|---|
| aella Server / Fedora (Xeon Platinum 8488C) | Intel, MKL, AVX-512 | servers, few laptops |
| GitHub `windows-latest` / `ubuntu-latest` | depends on the CPU allocated: not checked | unknown |
| Windows 11 on Arm, UTM (Prism) | emulated AVX2 (24H2+); vendor as Prism reports it: not checked | Snapdragon laptop users running the x64 build |
| benbecula (Haswell), until retired | Intel, MKL, AVX2 | **a typical Intel laptop** |
| an AMD laptop | non-MKL backend | nothing, ever |
| any NVIDIA GPU | CUDA, `float16` | nothing, ever |

**Is Windows on Arm mature enough to stand in for x64?** No, and maturity is not the
reason. Prism is a good emulator (AVX and AVX2 since the late-2025 update), but it
answers a different question: it is what Snapdragon users run, it is slow enough to
shake out timeouts, and its failures are mostly false alarms. It cannot be an Intel
CPU running MKL, it stops at AVX2, and it has no CUDA.

## 3. Windows

### 3.1 The environments, without Intel hardware of our own

| Need | Where | Cost |
|---|---|---|
| The suite on native x64 Windows | GitHub `test (3.12, windows-latest)`, blocking | free (public repo) |
| Installer build, smoke tests, schemas | `windows-installer.yml` | free |
| Native x64 install acceptance: admin and normal user, doctor, transcription, upgrade while serving, uninstall, `winget install --manifest` | aella `up --windows` (Server 2025, same 26100 base as Windows 11 24H2); passed all of it on 5 Oct 2026 | already paid |
| Client Windows 11, SmartScreen on a browser-downloaded file | UTM on the Mac (Prism) | free |
| CPU paths other than AVX-512 | aella, forced (§6.2) | already paid |
| NVIDIA / CUDA | aella with a GPU instance (§6.3) | ~$10–15 a year, estimated |
| Windows 10 | dropped: out of support, and Windows 10 on Arm cannot run x64 programs | — |

### 3.2 Client Windows in Azure: looked at, not taken

AWS offers no licence-included Windows 10/11; it is bring-your-own on dedicated
hosts. Azure runs Windows 10/11 Marketplace images on ordinary VMs
(`--license-type Windows_Client`) for users covered by a qualifying per-user
licence (Microsoft's list: Microsoft 365 E3/E5/A3/A5/F3, Business Premium, Windows
Enterprise E3/E5, Visual Studio subscriptions for dev/test). The compute is cheap,
about $35 a year for a weekly 1.5-hour Windows 10 + 11 run on a `D4s_v5`. The
current Microsoft 365 plan carries no Windows licence; qualifying would add roughly
$190 a year, for native x64 *desktop* Windows only, which aella Server plus UTM
cover almost entirely. Turned down on 18 Nov 2026 (and for cost on 9 Oct). Revisit
if a user reports a bug that reproduces only there: a month of a qualifying plan is
easy to buy then.

If it is ever taken: the Windows VMs go in their own resource group, which aella
creates, tags and alone may delete (the subscription also holds the Azure OpenAI
test resource); auto-shutdown on every VM; a budget alert. A forgotten `D4s_v5`
costs about $140 a month, a year's budget in a week.

### 3.3 winget, as of 18 Nov 2026

- **Published**: `Bristlenose.Bristlenose` 0.36.0, the package's first PR
  (microsoft/winget-pkgs#449372), merged 11 Nov 2026 after the DisplayVersion /
  1.28.0 schema / `PrivacyUrl` fixes.
- **Behind**: the latest release is 0.46.0. 0.37.0 was built and held behind the
  first PR (`release-winget.md` step 4a); no PR exists for 0.38.0–0.46.0.
- **Next**: one ordinary version update with the newest release, not a replay of
  0.37.0 onwards. It carries the silent-uninstall fix (`/SUPPRESSMSGBOXES`), which
  is unproven until a Windows build exercises it. After that acceptance, step 5
  (`winget-releaser` automation) meets its own precondition of "one or two accepted
  versions".
- **Testing it without benbecula**: `winget validate` and `winget install --manifest`
  on aella Server 2025 (has winget) and on the UTM Windows 11 VM (client edition).
- **Still owed from TODO**: the human SmartScreen click-through on a real desktop;
  the winget.exe-never-exits harness hang.

**Checked on 18 Nov 2026, for the 0.46.0 submission:**

- The `v0.46.0` tag (`10f2a7568`) already carries every fix from the first PR's
  moderation: manifest schema 1.28.0 (`build.ps1` default), no `DisplayVersion`,
  `PrivacyUrl`, `LicenseUrl` pinned to the tag, and the silent-uninstall refusal
  (`InitializeUninstall` in `bristlenose.iss` skips the message box under
  `UninstallSilent()`). No code change is needed to submit it.
- `windows-installer.yml` has been dispatched on a tag only twice (`v0.36.0`,
  `v0.37.0`); never on `v0.46.0`. The `v0.46.0` GitHub Release has no
  `bristlenose-0.46.0-setup-x64.exe` asset. So `release-winget.md` steps 1–4 are
  all still to run.
- Skip 0.37.0–0.45.0: winget needs no unbroken run of versions, and each extra PR
  is a moderator's time. 0.37.0's held artefact (expires 10 Jan 2027) can lapse.

**Test list for the next submission** (aella Server 2025 for native x64, UTM
Windows 11 for the client edition; the guest script of §6.1 should absorb this):

1. `winget validate` on the filled manifests; every manifest URL returns 200
   (installer URL after it is attached).
2. `winget install --manifest <dir>` as a normal user: silent, PATH entry set,
   `bristlenose --version`, `doctor --self-test`, one real transcription.
3. **Uninstall while running**, the unproven fix: start `bristlenose serve`, then
   `winget uninstall --id Bristlenose.Bristlenose -e`. Must return promptly with a
   refusal (exit code mapped to winget's `packageInUse`), never wait on a hidden
   dialog; stop serve, uninstall again, folder and PATH entry gone.
4. Upgrade in place over the published 0.36.0 (`winget install` 0.36.0 from the
   public source first), with `serve` running: Restart Manager closes it. Also open
   a project in 0.36.0 after 0.46.0 migrated it: the downgrade traceback seen on
   9 Nov (TODO item 5) is a known open problem, not a submission blocker.
5. On UTM only: download the installer in Edge and double-click it (Mark of the
   Web), recording what SmartScreen shows.
6. After merge: `winget search`, `winget list --id`, `winget upgrade --id` from 0.36.0
   on any Windows box (`release-winget.md` step 7).

**Where each step runs.** Steps 1–2 of `release-winget.md` (dispatch the build,
check the artefact) can be done from a cloud session through the GitHub tools;
step 3 (attach to the Release) and step 4 (`komac submit` from the fork) need the
Mac's `gh` and Komac. Any `after-winget/<version>` branch of user-facing docs is
local to the Mac (none on `origin`); `release.sh verify` says whether it can land
now that winget serves 0.36.0.

## 4. Linux

### 4.1 The environments

| Need | Where | Status |
|---|---|---|
| The suite, packaging, release | GitHub `ubuntu-latest` | in place |
| Fedora / Copr end to end | aella `up --fedora` | in place |
| Snap on amd64 and arm64 | built on both (`snap/snapcraft.yaml`) | **arm64 never run by us** |
| Linux arm64 (Graviton, Ampere, Pi, Snapdragon Linux) | GitHub's free `ubuntu-24.04-arm` runner, or aella on Graviton | not in place |
| CPU paths other than AVX-512 | aella, forced (§6.2) | not in place |
| NVIDIA / CUDA | aella with a GPU instance (§6.3) | not in place |

### 4.2 CUDA on Linux, by channel (from reading, not run)

- **pip / pipx / uv, Homebrew on Linux, Fedora Copr**: not frozen, so no guard. A
  machine with the NVIDIA driver (on Fedora usually RPM Fusion's `akmod-nvidia`)
  but without cuBLAS 12 / cuDNN 9 is counted as CUDA and will likely fail its
  first transcription (§5.1). Copr vendors no CUDA libraries.
- **Snap**: strict confinement with no GPU plug (`home`, `network`,
  `network-bind`, `removable-media` only), so CTranslate2 should see no device
  and fall back to CPU. Probably fails closed; unverified.

## 5. Defects found by reading the CUDA path (no hardware needed to fix)

None of these has been run on a GPU. Line numbers as of 18f479b.

1. **No CPU fallback when CUDA cannot load.** On every non-frozen channel,
   `_check_cuda_available` (`bristlenose/utils/hardware.py:343`) trusts
   `ctranslate2.get_cuda_device_count()`, and `_init_faster_whisper_backend`
   (`bristlenose/stages/s05_transcribe.py:1715`) then picks `cuda` / `float16`.
   A driver without cuBLAS 12 / cuDNN 9 (the common case on a gaming or creator
   laptop) should fail on a missing library, possibly as a hard crash rather than a
   Python exception. Wanted: a load-or-first-inference probe that falls back to CPU
   with one clear line, on Windows and Linux.
2. **`doctor` reports CUDA when transcription will use the CPU.** `doctor.py:243`
   calls `get_cuda_device_count()` directly instead of the shared guard, so on the
   frozen Windows build (CPU-only by design, `hardware.py:353`) with an NVIDIA GPU
   it says "CUDA", and the "GPU found but not used" warning at `doctor.py:305` can
   never fire there.
3. **The fix text is Linux-only.** `_fix_cuda_not_available`
   (`bristlenose/doctor_fixes.py:507`) tells Windows users to
   `export LD_LIBRARY_PATH`.
4. **Nothing says which path ran.** `doctor --self-test` should print the device,
   backend and instruction set actually in use (CTranslate2 reports these under
   `CT2_VERBOSE=1`, to be confirmed). A user's report then names their path, and
   each test machine records the path it covered instead of us inferring §2's table.

Tests can recreate "GPU counted, library missing" on any OS by stubbing, the way
`tests/test_windows_portability.py` recreates the frozen Windows build.

## 6. Proposed instruments

### 6.1 One guest-side check script

Lift the checks out of `vbox-test.sh` into a PowerShell script that runs *inside*
Windows (install, `--version`, doctor, transcription with its words checked, PATH,
uninstall, the path report from §5.4). aella-AWS, a future aella-Azure, UTM and any
real machine then differ only in how the script gets there and runs, and pass/fail
lives in one place. Run it over SSH as the test user (the route that works on
aella, `design-winget.md` §"What was measured"); never as SYSTEM (`utmctl exec`, Azure
run-command), which is the wrong user for a per-user installer. A shell twin for
Linux follows the same shape.

### 6.2 Forced CPU paths on aella

The same transcription, same audio, words compared, under:

- `CT2_FORCE_CPU_ISA=AVX2` + `MKL_CBWR=AVX2`: a typical Intel laptop (what
  benbecula gave by accident);
- `CT2_USE_MKL=0`: the AMD backend, never tested;
- `CT2_FORCE_CPU_ISA=GENERIC`: old or odd CPUs.

This tests dispatch and each path's code, which is where such bugs live; it does
not reproduce one chip's quirks, and nor did one 2014 laptop. On UTM, Prism's
"Hide newer emulated CPU features" gives the no-AVX path.

### 6.3 A GPU option for aella

`aella up --windows --gpu` (and `--gpu` for Linux): an AWS GPU instance (a
`g4dn.xlarge`, NVIDIA T4, is the cheap one) with NVIDIA's driver. Three runs:
driver only (the common case: must fall back cleanly), driver plus CUDA libraries
(must use the GPU), and the winget build (must report CPU honestly). Around an hour
per release; check current pricing.

Blind to: laptop hybrid graphics (Optimus), OEM driver builds, 6–8 GB laptop VRAM
(enough for `large-v3-turbo` in `float16`). §5.1 matters far more than any of these.

### 6.4 Intel Macs, while we are here

Nothing tests the CLI on Intel macOS (the `cryptography` cap was predicted from
metadata, not caught on hardware). A `macos-pip` job on GitHub's `macos-15-intel`
runner, which GitHub says it keeps until fall 2027, closes that for free.

## 7. Owner decisions

1. **Should the winget build ship CUDA?** CPU-only predates thinking about the
   high-end-laptop user. cuBLAS and cuDNN are large; the alternative is a guided
   "add GPU support" step. Your call, after §5.1 makes the CPU path safe.
2. **Windows 10**: dropped as proposed, or kept as untested-but-supported?
3. **Azure client Windows**: confirmed as not taken (§3.2)?

## 8. Order of work

1. §5 fixes with tests (any time; no hardware).
2. Next winget submission with the newest release (§3.3).
3. §6.1 guest script; §6.2 forced paths on aella.
4. §6.3 GPU runs, Windows and Linux.
5. §6.4 Intel Mac CLI job; Linux arm64 runner (§4.1).
6. True `design-test-environments.md` §2 and §5 and `release-winget.md`
   § "Client Windows in VMs" once benbecula is gone.

## Sources (read 18 Nov 2026)

- Microsoft: [How to deploy Windows 11 on Azure](https://learn.microsoft.com/en-us/azure/virtual-machines/windows/windows-desktop-multitenant-hosting-deployment)
- AWS: [Bringing your Windows 11 image to AWS](https://aws.amazon.com/blogs/modernizing-with-aws/bringing-your-windows-11-image-to-aws-with-vm-import-export); [Windows licensing on AWS](https://aws.amazon.com/windows/licensing/)
- Pricing (third-party trackers, confirm before relying): [AzureSpeed D4s_v5](https://www.azurespeed.com/AzureVmPricing/Standard_D4s_v5); [Azure managed disks](https://azure.microsoft.com/pricing/details/managed-disks/)
- CTranslate2: [environment variables](https://opennmt.net/CTranslate2/environment_variables.html); [hardware support](https://opennmt.net/CTranslate2/hardware_support.html)
- Prism: [Program Compatibility Troubleshooter on Arm](https://learn.microsoft.com/windows/arm/apps-on-arm-program-compat-troubleshooter); [Neowin on AVX/AVX2](https://www.neowin.net/news/prism-update-unlocks-avx-avx2-support-for-windows-on-arm/)
- GitHub: [macOS 13 runner closing down, Intel until fall 2027](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/)
