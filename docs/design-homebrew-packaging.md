# Design: Homebrew Packaging

Status: Implemented in v0.12.2 (Mar 2026). Formula in `cassiocassio/homebrew-bristlenose`.

---

## The problem: Mach-O dylib relinking on pre-built wheels

Homebrew's post-install cleanup walks every Mach-O binary in the keg —
including files deep inside `libexec/lib/python*/site-packages/` — and rewrites
dylib IDs using `install_name_tool` to use Cellar paths. Pre-built Python wheels
(like `av`, `cryptography`, `Pillow`) ship `.so`/`.dylib` files with short
Mach-O header padding. The Cellar paths are much longer than the original short
install names (e.g. `./libEGL.dylib` at 14 bytes vs a 191-byte Cellar path), so
the rewrite fails with `MachO::HeaderPadError`.

Homebrew's relocation code (`extend/os/mac/keg_relocate.rb`) has no error
handling for this and no skip mechanism for paths like `site-packages/`.

### Who else hit this

- **AWS SAM CLI** — `cryptography/hazmat/bindings/_rust.abi3.so` fails relinking
  ([aws/aws-sam-cli#4405](https://github.com/aws/aws-sam-cli/issues/4405))
- **DVC** — `PIL/.dylibs/liblcms2.2.dylib` fails relinking
  ([iterative/homebrew-dvc#9](https://github.com/iterative/homebrew-dvc/issues/9))
- **Selenium** — universal wheel binaries with x86 linkage paths on ARM64
  ([Homebrew/brew#17275](https://github.com/Homebrew/brew/issues/17275))

None of these have a clean documented solution.

### Why bristlenose triggers it

Our dependency tree includes `av` (PyAV, for FFmpeg bindings) pulled in via
`faster-whisper`, and `cryptography` pulled in via various transitive deps. Both
ship pre-built macOS wheels with short Mach-O header padding.

---

## Approaches considered

### 1. Full resource blocks (the "official" Homebrew way)

Use `include Language::Python::Virtualenv` with `virtualenv_install_with_resources`
and declare every transitive dependency as an explicit `resource` block (URL +
SHA256 pointing to sdist tarballs on PyPI). Dependencies compile from source
under Homebrew's build environment, which injects `-headerpad_max_install_names`,
so resulting `.so`/`.dylib` files have sufficient padding.

**Tools for generating blocks:** `brew update-python-resources <formula>`,
[homebrew-pypi-poet](https://github.com/tdsmith/homebrew-pypi-poet),
[poetry-homebrew-formula](https://codeberg.org/janw/poetry-homebrew-formula).

**Real-world scale:** yt-dlp has 9 resource blocks (mostly pure Python),
ansible has 81, azure-cli has 151. Bristlenose with `av`, `cryptography`,
`faster-whisper`, `torch`, `spacy`, etc. would easily exceed 100.

**Pros:** Accepted by homebrew-core. Reproducible (pinned URL + SHA256). All
native extensions compile with proper header padding.

**Cons:** 100+ resource blocks. Every dependency update requires regeneration.
Needs `depends_on "rust"` for cryptography, `depends_on "cmake"` for ML
packages. Build time 10+ minutes vs seconds with wheels. For third-party taps
there's no bottling CI, so users always pay the full compilation cost.

**Verdict:** Would be necessary for homebrew-core submission, but massively
over-engineered for a third-party tap.

### 2. `--no-binary` for problem packages

Add `--no-binary av,cryptography` to the pip install command so those specific
packages build from source while everything else uses wheels.

**Tried and failed.** `av` builds fine from source, but `cryptography` requires
a Rust toolchain to compile from source (`pip install cryptography` without a
wheel invokes the Rust build). Homebrew environments don't have Rust by default.
Adding `depends_on "rust"` would fix it but opens a can of worms — other
transitive deps may also have native builds, and you're halfway to Approach 1.

### 3. `post_install` pip install (chosen approach) ✓

Create the venv and a bash wrapper script during `install`. Run `pip install`
from PyPI during `post_install`. Since `post_install` executes **after**
Homebrew's keg relocation/cleanup phase, the pre-built wheels are never touched
by `install_name_tool`.

The wrapper script is the key insight: Homebrew's `link` phase runs after
`install` but before `post_install`. It needs a real file (not a symlink) in
`bin/` to link into `/opt/homebrew/bin/`. A symlink to `libexec/bin/bristlenose`
would be dangling at that point (pip hasn't run yet). So we write a bash script
that `exec`s the venv binary — it's a real file at link time, and at runtime the
venv binary exists because `post_install` has already run.

**Pros:** Zero resource blocks. Zero build tools. Fast install (pre-built
wheels). Zero maintenance on dependency updates. Completely avoids the dylib
issue.

**Cons:** Not accepted by homebrew-core (no explicit dependency pinning). No
reproducibility guarantee (pip resolves at install time). Requires PyPI access
during `post_install`. No bottle support.

**Verdict:** Right tradeoff for a third-party tap.

### 4. Bottles (pre-built binaries)

Build the formula once with all resource blocks, then host the resulting bottle
on GitHub Releases. Users download and extract instead of building.

**Verdict:** Still requires the 100+ resource blocks for source-build fallback.
Good add-on to Approach 1 if we ever submit to homebrew-core, but doesn't reduce
formula complexity.

### 5. Skip Homebrew entirely (`pipx`)

Tell users to `brew install pipx && pipx install bristlenose`.

**Verdict:** Loses the `brew install bristlenose` simplicity and can't bundle
non-Python deps like FFmpeg.

---

## Current formula

```ruby
class Bristlenose < Formula
  desc "User-research transcription and quote extraction engine"
  homepage "https://github.com/cassiocassio/bristlenose"
  url "https://files.pythonhosted.org/packages/.../bristlenose-X.Y.Z.tar.gz"
  sha256 "..."
  license "AGPL-3.0-only"

  depends_on "ffmpeg"
  depends_on "python@3.12"

  def install
    # Venv created here so the Cellar directory exists for link phase.
    system Formula["python@3.12"].opt_bin/"python3.12", "-m", "venv", libexec

    # Bash wrapper — must be a real file (not a symlink) so Homebrew's
    # link phase can expose it in /opt/homebrew/bin/ BEFORE post_install.
    (bin/"bristlenose").write <<~SH
      #!/bin/bash
      exec "#{libexec}/bin/bristlenose" "$@"
    SH
    (bin/"bristlenose").chmod 0755

    man1.install "man/bristlenose.1" if (buildpath/"man/bristlenose.1").exist?
  end

  def post_install
    # pip runs here — AFTER Homebrew's dylib relinking phase.
    # Pre-built wheels with short Mach-O header padding are never touched.
    system libexec/"bin/pip", "install", "bristlenose==#{version}"
  end
end
```

### Why each piece exists

| Formula element | Why |
|-----------------|-----|
| `python@3.12` | Pinned Python — avoids venv breakage on minor Python upgrades |
| `venv` in `install` | Cellar directory must exist for Homebrew's link phase |
| Bash wrapper script | Real file required for linking — symlinks to `libexec/bin/bristlenose` would be dangling at link time |
| `pip install` in `post_install` | Runs after dylib relinking, avoids `MachO::HeaderPadError` |
| `ffmpeg` as `depends_on` | Non-Python dependency, can't be installed via pip |

---

## Automation

The formula auto-updates on each release via the CI chain:

```
bristlenose release.yml (v* tag push)
└─ notify-homebrew job → sends repository_dispatch to tap repo

homebrew-bristlenose update-formula.yml
└─ fetches sdist URL + SHA256 from PyPI JSON API
   → patches Formula/bristlenose.rb (url, sha256)
   → commits and pushes
```

Only the URL and SHA256 change. The `install`/`post_install` structure is stable.

---

## Known tradeoffs and failure modes

### Python version upgrades

If Homebrew upgrades `python@3.12` to a new patch version, the venv *should*
survive (same minor version). If Homebrew bumps to `python@3.13`, the formula
needs updating (`depends_on` + venv creation). The CI automation doesn't handle
Python version bumps — manual intervention required.

### PyPI unavailable during `post_install`

`post_install` requires network access. If PyPI is down or the user is behind a
restrictive firewall, installation fails. `brew install` itself fetches the
tarball (so network was available), but there's a window between `install` and
`post_install` where connectivity could drop.

### `brew upgrade` with broken venv

If the venv breaks (e.g. Python runtime moved), `brew reinstall bristlenose`
fixes it — `post_install` recreates the pip install in the fresh venv.

### No `brew linkage` verification

Homebrew's `brew linkage` command can't verify dynamic linkage of files installed
in `post_install`. This means `brew audit` would flag issues. Acceptable for a
third-party tap; would block homebrew-core submission.

---

## If we ever want homebrew-core

1. Switch to `include Language::Python::Virtualenv` with full resource blocks
2. Use `brew update-python-resources bristlenose` or `poet` to generate blocks
3. Add `depends_on "rust" => :build` for cryptography
4. Add `depends_on "cmake" => :build` for any ML packages needing it
5. Set up bottling CI (homebrew-core provides this for accepted formulas)
6. Expect 100+ resource blocks and 10+ minute source builds

This is significant work and only worth it if user demand justifies it. The
third-party tap with `post_install` pip works fine for now.

---

## References

- [Python for Formula Authors — Homebrew docs](https://docs.brew.sh/Python-for-Formula-Authors)
- [Packaging a Python CLI for Homebrew — Simon Willison](https://til.simonwillison.net/homebrew/packaging-python-cli-for-homebrew)
- [MachO::HeaderPadError discussion — Homebrew #4878](https://github.com/orgs/Homebrew/discussions/4878)
- [Binary Python dependencies discussion — Homebrew #5670](https://github.com/orgs/Homebrew/discussions/5670)
- [Python resources RFC — homebrew-core #157500](https://github.com/Homebrew/homebrew-core/issues/157500)
- [homebrew-pypi-poet](https://github.com/tdsmith/homebrew-pypi-poet)
- [AWS SAM CLI dylib failure — #4405](https://github.com/aws/aws-sam-cli/issues/4405)
- [DVC dylib failure — homebrew-dvc#9](https://github.com/iterative/homebrew-dvc/issues/9)
