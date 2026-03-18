# Windows CI — Design and Compatibility Plan

_10 Mar 2026_

## Motivation

Bristlenose currently tests on one platform in CI: Linux x86_64 (`ubuntu-latest`). Local development covers macOS ARM64 (daily driver) and Linux ARM64 (Multipass on Apple Silicon). That leaves a glaring gap: **Windows**, which is likely where most potential users are — corporate UX research teams run on Windows laptops issued by IT.

The goal is not to ship a polished Windows experience tomorrow. It's to **keep the codebase honest** — add `windows-latest` to CI so that every push catches path bugs, import failures, and platform assumptions at the point they're introduced. After 100 or 1000 pushes, if we ever decide to support Windows properly, the delta is small instead of a month-long audit.

### Current test matrix

| Platform | Arch | Coverage |
|----------|------|----------|
| macOS | ARM64 (M1+) | Local development |
| Linux | x86_64 | CI (`ubuntu-latest`) |
| Linux | ARM64 | Local (Multipass) |
| **Windows** | **x86_64** | **None** |

### Stated compatibility target

macOS 15 Sequoia + Apple Silicon (M1+). Windows is explicitly out of scope for user-facing support today. This plan is about CI hygiene, not a support commitment.

---

## What we know works

The core stack is cross-platform by design:

- **pathlib** throughout (no raw string concatenation for paths — mostly)
- **subprocess.run()** with list args (no `shell=True`)
- **Pydantic**, **FastAPI**, **SQLAlchemy** — all cross-platform
- **LLM API calls** — HTTP, nothing platform-specific
- **React frontend** — browser-based, OS-irrelevant
- **pytest** — runs anywhere

## What will break (audit results)

Ranked by likelihood of causing test failures:

### Tier 1 — Will definitely fail

1. **Man page installation** — writes to `~/.local/share/man/man1`. Directory doesn't exist on Windows, `Path.mkdir(parents=True)` succeeds but the man page is useless. Currently wrapped in try/except, so probably won't *crash*, but the test might assume the path exists.

2. **`file://` URI construction** — `cli.py` uses `f"file://{path.resolve()}"` which produces `file://C:\Users\...` (backslashes) on Windows. Should use `Path.as_uri()` instead, which handles this correctly.

3. **Doctor fix messages** — hardcoded `brew install ffmpeg`, `sudo apt install ffmpeg`. On Windows: no brew, no apt. The `detect_install_method()` function checks `/opt/homebrew/` and `/usr/local/Cellar/` — always returns `"pip"` on Windows, which is actually fine.

4. **Snap-related code paths** — `SNAP_USER_COMMON`, snap detection. Irrelevant on Windows but should be guarded, not crashing.

### Tier 2 — Might fail depending on test coverage

5. **FFmpeg subprocess calls** — `ffmpeg` and `ffprobe` need to be on PATH. GitHub's `windows-latest` runner doesn't include FFmpeg by default. Tests that shell out to FFmpeg will need it installed or mocked.

6. **Hardware acceleration flags** — `-hwaccel videotoolbox` is macOS-only. Already gated by `platform.system() == "Darwin"`. Windows equivalent (`dxva2`, `qsv`) not implemented but the fallback (no hwaccel) is fine.

7. **Credential store** — Falls back to `EnvCredentialStore` on Windows. Tests should pass since they mock credentials.

8. **`os.kill()` / signal handling** — Any process management code. Windows doesn't support POSIX signals the same way.

### Tier 3 — Probably fine but worth watching

9. **Temp directory assumptions** — `tempfile` module handles cross-platform. No hardcoded `/tmp`.

10. **Line endings** — Git on Windows might check out `\r\n`. Tests comparing exact file output could break. `pyproject.toml` should set `*.py text eol=lf` in `.gitattributes`.

11. **Path separator in test assertions** — Any test that asserts a path string contains `/` will fail if the code produces `\`.

12. **Unicode filenames** — Windows has different filesystem encoding. Real-world interview files have spaces, accents, CJK characters.

---

## Phased plan

### Phase 1: Green CI (the goal)

**Effort:** 1–2 sessions. **Value:** Massive — every future push stays honest.

#### Step 1: Add `windows-latest` to CI matrix

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    python-version: ["3.12"]
  fail-fast: false
```

`fail-fast: false` so Linux CI still reports even if Windows fails during the ramp-up period.

#### Step 2: Add `.gitattributes`

```
* text=auto
*.py text eol=lf
*.md text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.json text eol=lf
*.toml text eol=lf
*.html text eol=lf
*.css text eol=lf
*.js text eol=lf
*.ts text eol=lf
*.tsx text eol=lf
```

Prevents line-ending issues on Windows checkout.

#### Step 3: Install FFmpeg on Windows runner

```yaml
- name: Install FFmpeg (Windows)
  if: runner.os == 'Windows'
  run: choco install ffmpeg -y
```

GitHub's `windows-latest` has Chocolatey pre-installed.

#### Step 4: Fix the easy breaks

- `file://` URI: use `Path.as_uri()` everywhere (not string concatenation)
- Man page: skip installation on Windows (`sys.platform == "win32"` guard, or just let the try/except handle it)
- Doctor messages: add Windows branch for FFmpeg install instruction (`choco install ffmpeg` or `winget install ffmpeg`)
- Any path string assertions in tests: use `pathlib` comparison instead of string comparison

#### Step 5: Skip what can't work

Mark tests that are inherently platform-specific:

```python
@pytest.mark.skipif(sys.platform == "win32", reason="man page is Unix-only")
def test_man_page_install():
    ...

@pytest.mark.skipif(sys.platform == "win32", reason="snap is Linux-only")
def test_snap_detection():
    ...
```

Keep these to a minimum. Every skip is a debt marker.

#### Step 6: Make Windows CI non-blocking initially

```yaml
- name: Run tests (Windows)
  if: runner.os == 'Windows'
  continue-on-error: true
  run: pytest --tb=short -q -m "not slow"
```

Start informational (like mypy today), then remove `continue-on-error` once green.

### Phase 2: Stay green (ongoing, zero effort)

Once Phase 1 is green:

- Remove `continue-on-error`
- Windows failures now block the build like Linux failures
- Every push is automatically tested — no maintenance required
- Path regressions caught at introduction

### Phase 3: Windows user experience (future, only if demand)

Not planned. Captured here for completeness:

- Windows Credential Manager integration (via `keyring` or `ctypes`)
- Windows hardware acceleration (DXVA2, QSV, NVENC)
- `winget` / MSIX packaging
- Windows-specific doctor instructions
- WSL detection and recommendation
- `.exe` distribution via PyInstaller

---

## CI cost

GitHub Actions provides 2,000 free minutes/month for private repos, 3,000 for public. `windows-latest` runners cost 2× Linux minutes.

Current CI run time (estimate): ~3 minutes for lint+test, ~2 minutes for frontend, ~3 minutes for E2E. Adding a Windows lint+test job adds ~4–5 minutes (Windows runners are slower).

**Monthly cost estimate:** At ~30 pushes/month, that's ~150 Windows minutes = 300 Linux-equivalent minutes. Well within free tier for a public repo.

E2E tests (Playwright) stay Linux-only for now — the serve-mode browser tests don't gain much from running on Windows since the browser experience is identical.

---

## Skip list (tests that will never pass on Windows)

| Test area | Reason | Action |
|-----------|--------|--------|
| Man page installation | Unix concept | `skipif win32` |
| Snap detection / snap paths | Linux-only | `skipif win32` |
| MLX / Apple Silicon | macOS-only | Already gated |
| Homebrew detection | macOS/Linux | `skipif win32` |
| Keychain (macOS) | macOS-only | Already gated |
| Keychain (Linux/libsecret) | Linux-only | Already gated |

---

## Decisions

1. **Windows CI is informational first, then blocking.** Start with `continue-on-error: true`, promote to blocking once green.

2. **No Windows-specific features.** This is about not *breaking* Windows, not about *supporting* it. Doctor messages get a Windows branch for FFmpeg; credentials fall back to env vars. That's it.

3. **WSL is the recommended path for Windows users today.** If someone asks, "install WSL, follow the Linux instructions." We don't document this prominently because Windows isn't a supported platform yet.

4. **E2E stays Linux-only.** Browser rendering is platform-independent. The Python pipeline is where platform bugs live.

5. **Frontend CI stays Linux-only.** Node/Vite/React have no platform-specific behaviour worth testing separately.

---

## Files to modify

| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Add `windows-latest` to matrix, add FFmpeg install step |
| `.gitattributes` | New file — line ending normalisation |
| `bristlenose/cli.py` | Fix `file://` URI construction |
| `bristlenose/doctor_fixes.py` | Add Windows FFmpeg install instruction |
| `tests/` (various) | `skipif win32` for platform-specific tests |

---

## Open questions

1. **Should we also add `macos-13` (Intel Mac)?** It's the last Intel macOS runner GitHub offers. Cheap to add, covers the macOS x86_64 gap. Could be Phase 1b.

2. **Python version matrix on Windows?** Start with 3.12 only (matching Linux). Expand to 3.10–3.13 later if Windows adoption happens.

3. **Should Windows CI run the full test suite or a subset?** Full suite initially — the point is to find what breaks. If it's too slow, introduce a `windows` marker to run a subset.
