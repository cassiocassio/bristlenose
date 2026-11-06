# Whisper download battery

Synthetic failure tests for the first-run Whisper download, run against the **real frozen sidecar** inside clean
Tart macOS guests. Written 30 Oct to 2 Nov 2026 while chasing a red pill on a researcher's fresh Mac; it found
four defects that reading the code had not, and the harness was lost from a scratch directory on 4 Nov, so this
is the reconstruction (6 Nov 2026), re-run on a clean macOS 15 guest.

```bash
cd experiments/whisper-download-battery
./osrun.sh ghcr.io/cirruslabs/macos-sequoia-vanilla:latest bat-15 macos15      # the whole battery
./osrun.sh <macos-26-image> bat-26 macos26 fetch orphan_fresh net              # a few rows
NETDOWN=40 ./osrun.sh <image> bat-15 blip15 netblip                            # one outage length
python3 fakehub.py 429:4        # on the host, before `HUBMODE=429:4 ./osrun.sh … hub`
```

Results land in `results/<label>.txt` (gitignored scratch). The guest ends up running: stop and delete it yourself
(`tart stop bat-15; tart delete bat-15`). It installs whatever sidecar is in
`desktop/Bristlenose/Resources/bristlenose-sidecar/` (build it first: `desktop/scripts/build-sidecar.sh`).

## What it needs

- Tart, one image per OS (the Cirrus `macos-*-vanilla` images; password `admin`), and an ssh key at
  `~/.ssh/id_ed25519_tartvm` (override with `BATTERY_KEY`). The guest's `sudo` password is also `admin`.
- `expect`, `rsync`, `nc` on the host.
- **macOS allows two guests at once on one host.** A third `tart run` quietly does not start.

## The rows (`bat.sh`)

| Test | What it does | What it proved |
|---|---|---|
| `info`, `cold` | OS, chip, free disk; first-ever sidecar start and `--mlx-probe` | cold start 3 to 14 s; probe 2 to 3 s warm |
| `fetch` | clean download, then again | 1,540 to 1,543 MiB on disk, peak equals final (no scratch); 36 to 63 s |
| `orphan`, `orphan_fresh` | `kill -9` mid-download, refetch (old partial, young partial) | a restart does not reuse or reclaim the partial: 2,174 MiB peak (model plus orphan); now swept at the start (over 120 s) and after success (over 20 s) |
| `sigint` | SIGINT mid-download | stops in about 1 s, partial removed (needs job control, see traps) |
| `concurrent` | a second fetch 6 s after the first | both finish, nothing corrupt |
| `sleepsim` | writer SIGSTOPped 150 s while a second fetch starts | the partial is older than the 120 s rule, yet both fetches complete: the HF flock protects it |
| `tls`, `badcert`, `proxy`, `unwritable` | missing CA bundle; untrusted root (badssl); dead proxy; read-only `HF_HOME` | all fail in seconds, none retried; a dead proxy once waited 5 minutes before "connection refused" was removed from the retry list |
| `lowdisk`, `boundary`, `enospc` | about 1.7 GB free; 3.1 GB free; disk filled during the download | refused before a byte is written; passes; clean `[Errno 28]` and a clean recovery |
| `net`, `netblip` | interface down mid-download (`NETDOWN` s); and down at the start of a fetch | **12 s survived, 18 s killed the pre-fix build**; with the retry loop 25 s (all three OSes) and 40 s (15) complete |
| `stall` | silent drop (`pfctl block drop` on 443) for `STALL` s | 60 s (15) and 25 s (26) survived with no help from us |
| `hub` | fake endpoint: `429:4`, `5xx:4`, `portal` | 429 handled; a captive-portal page fails in about 4 s with "Expecting value: line 1 column 1" |

## Results, 30 Oct to 2 Nov 2026 (macOS 15.7.7 / 26.6.2 / 27.0, M2 Max guests, 8 GB)

Every row behaved as intended on all three OSes on the final build, except `boundary` once on 27 (see traps).
The one real OS difference was **not** in this battery: the shipped 0.43.0 sidecar crashed on macOS 15 only
(MLX built for macOS 26; fixed in 0.44.0, `check-sidecar-mlx-floor.sh`).

| Failure found by running it | Fix | Commit |
|---|---|---|
| macOS 15 launch crash (MLX macOS 26 wheels) | pin the 15 wheels; gate; probe by `find_spec`, start asked of a child | `4ba513387` |
| a network outage over about 15 s ends the 1.6 GB download; Retry restarts at zero | quiet wait-for-Hub and restart, bounded | `4ba513387` |
| a killed download's partial stays; Retry stacks them | sweep at the start and after success; skip a partial whose HF lock is held | `4ba513387` |
| a dead proxy waited 5 minutes | "connection refused" is an answer, not an outage | `4ba513387` |
| the pill said only "failed" | disk, connection, certificate named | `7675848e0` |

Measured facts worth keeping: the HF lock `<hub>/.locks/<repo>/<etag>.lock` is **held** during a real hf_xet download
and its name is the partial's etag prefix; hf_xet's own errors read `(os error 54)` not `[Errno 54]`; a
download's disk use peaks at its final size.

## Traps (each cost a wrong conclusion)

- **A non-interactive shell starts background jobs with SIGINT ignored.** Python then never sees Ctrl+C. It made the
  SIGINT row say "Stop leaves a partial" (false), and made three `tests/test_package_install.py` Ctrl+C tests fail when pytest was
  launched as a background job. `set -m` inside the job fixes a script; for pytest run it as an ordinary foreground command.
- **expect's one-line `expect { … }` form never matches.** Use the multi-line form (as `desktop/scripts/guest-walk/prep-base.sh` says).
- **A fresh clone takes minutes before password login works**; `osrun.sh` retries. A key copied "too early" fails silently.
- **The sidecar traps from a shell** (`sandbox + inherit` entitlements): re-sign the main binary ad hoc, no entitlements. Do not use
  the guest's `ffmpeg` from the app bundle the same way without re-signing it.
- **APFS free space drifts by about 200 MB** within seconds of deleting a cache; a boundary at 2.8 GB failed once on macOS 27 ("needs 2.61 GB, only 2.57").
  Leave 3.1 GB. The low-disk row now fills in a loop until `df` is under 1.8 GB.
- **Taking the interface down kills ssh**, so `net`, `netblip` and `stall` run detached and `osrun.sh` polls for `DONE`.
- **A wait loop that greps for "passed" matches ruff's "All checks passed!"**: anchor on a number, `[0-9]+ passed`.
- A VM has a virtual GPU. "Works in the guest" is strong evidence, not proof, for MLX.

## Not covered

Apple's speech model on 26 and later; an M5 (the macOS 15 MLX has a smaller kernel library, 44 MB against 78 MB); a real
macOS 15 Mac; sleep/wake with a real lid (`sleepsim` freezes the process instead); a captive portal that returns a 403 or a proxy
that returns 407 (not retried by design); IPv6-only networks; a VPN split tunnel; the HF cache on an unmounted volume.
