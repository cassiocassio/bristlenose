# Design: Serve-mode doctor checks

Last updated: 17 Feb 2026

## Problem

The existing doctor checks (`doctor.py`) cover the pipeline (transcribe → analyse → render) but know nothing about `bristlenose serve --dev`. Three silent failures discovered 17 Feb 2026, all requiring manual diagnosis:

1. **`[serve]` pip extras missing** — fastapi/uvicorn/sqlalchemy/sqladmin not installed → server won't start. Error message says `pip install bristlenose` (unhelpful for editable installs)
2. **`node_modules` missing** — switching branches or cloning fresh leaves `frontend/node_modules` absent → Vite won't start
3. **Vite port conflict** — stale node process squats on 5173, Vite silently moves to 5174, server hardcodes 5173 in `<script>` tags → all five React islands render as empty divs with no error

## Vite auto-discovery

The hardcoded Vite port (5173 in `app.py` line 498) is the root cause of the most confusing failure. Vite silently increments to the next available port when its preferred port is taken, but the server doesn't know.

### What Vite exposes

Vite dev servers expose several endpoints that can be used for discovery:

| Endpoint | What it returns | Useful for |
|----------|----------------|------------|
| `/__vite_ping` | The full `index.html` including `<title>` | Best fingerprint — confirms both "this is Vite" and "this is *our* Vite" (check for `Bristlenose` in the response) |
| `/@vite/client` | HMR client JavaScript | Confirms it's a Vite server (any Vite project) |
| `/src/main.tsx` | The app entry point source | Confirms it's specifically the bristlenose frontend |

### Discovery algorithm

At server startup (`_build_vite_dev_scripts()` in `app.py`):

1. Scan ports 5173–5180 (Vite's default auto-increment range)
2. For each port, `GET http://localhost:{port}/__vite_ping` with a short timeout (~500ms)
3. Check if the response body contains `Bristlenose` (from `<title>Bristlenose</title>`)
4. First match → use that port for all injected `<script>` tags
5. No match → log a warning that Vite isn't running (React islands won't render)

This replaces the hardcoded `vite = "http://localhost:5173"` on line 498.

### Alternative: configurable port

A simpler but less automatic approach: respect an env var or CLI flag.

```
BRISTLENOSE_VITE_PORT=5174 bristlenose serve --dev
bristlenose serve --dev --vite-port 5174
```

This could be the fallback if auto-discovery fails (Vite on a port outside 5173–5180).

### Recommendation

Do both: auto-discover first, fall back to `BRISTLENOSE_VITE_PORT` env var, fall back to 5173. Log the discovered port so it's visible in the server startup output.

## Proposed doctor checks

### `check_serve_deps()`

Try importing the four `[serve]` extras: `fastapi`, `uvicorn`, `sqlalchemy`, `sqladmin`. Any `ImportError` → fail with fix message `pip install -e ".[serve]"`.

### `check_node_modules()`

Check `frontend/node_modules` exists. Optionally compare `node_modules/.package-lock.json` mtime against `package.json` mtime to detect staleness. Missing or stale → warn with `cd frontend && npm install`.

### `check_vite_dev_server()`

Use the discovery algorithm above. Possible results:

- **Found on expected port (5173)** → OK
- **Found on different port** → WARN: "Vite running on 5174, server will auto-discover" (or FAIL if auto-discovery isn't implemented yet)
- **Not found on any port** → FAIL: "Vite dev server not running → cd frontend && npm run dev"
- **Found but wrong project** → FAIL: "Port 5173 has a Vite server but it's not bristlenose → kill the process or use a different port"

### `check_database()`

Check the SQLite file exists for the project being served. Missing → fail with "re-run the pipeline or check the project path".

## Integration into existing architecture

### `doctor.py`

Add to `_COMMAND_CHECKS`:

```python
_COMMAND_CHECKS: dict[str, list[str]] = {
    "run": [...],
    "run_skip_tx": [...],
    "transcribe-only": [...],
    "analyze": [...],
    "render": [],
    "serve": ["serve_deps", "node_modules", "vite_dev_server", "database"],
}
```

### `doctor_fixes.py`

Add fix keys:

| fix_key | Fix message |
|---------|------------|
| `serve_deps_missing` | `pip install -e ".[serve]"` (adapt for install method) |
| `node_modules_missing` | `cd frontend && npm install` |
| `vite_not_running` | `cd frontend && npm run dev` |
| `vite_wrong_port` | Show discovered port, suggest killing squatter with `lsof -i :5173` |
| `vite_wrong_project` | `kill <pid>` (from lsof) then restart |
| `serve_db_missing` | Re-run pipeline or check project path |

### Preflight in `bristlenose serve`

Run `run_preflight(settings, "serve")` at the start of the serve command, same pattern as the existing `run` preflight. Block startup on failures, warn on warnings.

### `app.py` changes

Replace hardcoded port in `_build_vite_dev_scripts()`:

```python
def _build_vite_dev_scripts() -> str:
    port = _discover_vite_port() or int(os.environ.get("BRISTLENOSE_VITE_PORT", 5173))
    vite = f"http://localhost:{port}"
    ...
```

## Future: auto-start Vite

`bristlenose serve --dev` could start Vite as a subprocess so the user doesn't need two terminals. This is a separate piece of work — the doctor checks and auto-discovery are useful regardless.

## Key files

| File | What changes |
|------|-------------|
| `bristlenose/doctor.py` | Add 4 new check functions, add `"serve"` to `_COMMAND_CHECKS` |
| `bristlenose/doctor_fixes.py` | Add 5–6 new fix keys |
| `bristlenose/server/app.py` | Replace hardcoded port with `_discover_vite_port()` |
| `bristlenose/cli.py` | Add preflight call in `serve` command |
