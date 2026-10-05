# Windows Tech Debt

Oneday!

Platform assumptions that work on macOS/Linux but will need attention for Windows support. Not blocking — bristlenose is macOS/Linux first — but tracked here so we don't lose sight of them.

**Updated:** 15 Feb 2026. **Superseded 5 Oct 2026** by the status section of [design-windows-port.md](design-windows-port.md): Windows now has blocking CI and the CLI runs there. Of the items below, the `index.html` symlink is moot (`_ensure_index_symlink` has no caller), FFmpeg guidance and the config directory are done, and the rest are kept as history.

---

## Serve branch

### Symlink for index.html → report file
- **Where:** `bristlenose/server/app.py` → `_ensure_index_symlink()`
- **Issue:** `Path.symlink_to()` requires admin privileges or Developer Mode on Windows
- **Fix:** Fall back to a small `index.html` with `<meta http-equiv="refresh">` redirect, or just copy the file

---

## Main (pre-serve)

### FFmpeg dependency
- **Where:** `bristlenose/stages/s02_extract_audio.py`, `doctor.py`
- **Issue:** Install instructions assume Homebrew (macOS) or apt/snap (Linux). Windows users need manual FFmpeg install or choco/winget
- **Fix:** Add Windows install guidance to `doctor` output

### Snap packaging
- **Where:** `snap/snapcraft.yaml`
- **Issue:** Snap is Linux-only. No Windows equivalent configured
- **Fix:** Consider MSI/NSIS installer or just document pip install for Windows

### Path separators in output
- **Where:** Various — `output_paths.py`, `render/`, transcript page paths
- **Issue:** Forward slashes used in path construction; mostly fine (Python's `Path` handles it) but string formatting of paths for display or URLs may assume `/`
- **Fix:** Audit all `str(path)` usages that end up in HTML or user-facing output

### Config directory
- **Where:** `bristlenose/server/db.py` → `~/.config/bristlenose/`
- **Issue:** `~/.config/` is a Linux/macOS convention. Windows equivalent is `%APPDATA%` or `%LOCALAPPDATA%`
- **Fix:** Use `platformdirs` library or `Path.home() / "AppData" / "Local"` on Windows

### File watching / inotify
- **Where:** Uvicorn reload in dev mode
- **Issue:** Uvicorn's file watcher uses different backends per OS. Should work on Windows but untested
- **Fix:** Test; may need `watchfiles` package explicitly installed

### Shell commands in scripts
- **Where:** `scripts/bump-version.py`, various shell scripts
- **Issue:** Bash scripts don't run natively on Windows
- **Fix:** Rewrite as Python scripts or document PowerShell equivalents
