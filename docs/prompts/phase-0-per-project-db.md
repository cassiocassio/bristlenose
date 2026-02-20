# Phase 0: Per-project SQLite database

> **Context**: This is Phase 0c of the pipeline resilience plan (`docs/design-pipeline-resilience.md`). It's a standalone fix — no dependencies, no architecture changes.

## The problem

The serve-mode SQLite database lives at `~/.config/bristlenose/bristlenose.db` — one global DB for all projects. If you run `bristlenose serve` on project A, then later `bristlenose serve` on project B, project A's stale data (sessions, quotes, tags, codebook entries) is still in the DB. The importer runs on startup and adds project B's data, but leftover rows from project A can leak through.

This caused real confusion during the Plato stress test (Feb 2026) — stale sessions from a previous project appeared in the dashboard.

## The fix

Move the database from `~/.config/bristlenose/bristlenose.db` to `<output_dir>/.bristlenose/bristlenose.db`. Each project gets its own database. Clean separation, no cross-contamination.

## What to change

### 1. `bristlenose/server/db.py`

Currently (lines 13-14):
```python
_CONFIG_DIR = Path("~/.config/bristlenose").expanduser()
_DB_PATH = _CONFIG_DIR / "bristlenose.db"
```

The `_default_db_url()` function (line 21) creates this directory and returns the global path.

**Change**: Remove the global `_DB_PATH` constant. The default DB path should come from the project's output directory, not a global config dir. The `get_engine()` function (line 26) already accepts an optional `db_url` param — make the caller (`create_app`) always pass one.

### 2. `bristlenose/server/app.py`

The `create_app()` function (line 152) receives `project_dir` but doesn't use it for the DB path. It calls `get_engine(db_url)` where `db_url` defaults to `None`, falling back to the global path.

**Change**: Derive the DB path from `project_dir`:
```python
# In create_app():
if db_url is None and project_dir is not None:
    db_path = project_dir / ".bristlenose" / "bristlenose.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_path}"
```

Keep the `_default_db_url()` fallback for when `project_dir` is None (shouldn't happen in normal usage, but defensive).

### 3. Tests

The test suite already uses `db_url="sqlite://"` (in-memory) so tests won't be affected by the path change. But verify:
- `tests/test_serve_*.py` — confirm they all use in-memory DBs
- No test relies on the global `~/.config/bristlenose/bristlenose.db` path

### 4. CLI (`bristlenose/cli.py`)

The `serve` command creates `create_app(project_dir=project_dir)`. No changes needed here — `project_dir` is already passed through. The `project_dir` is the output directory (or the parent directory containing `bristlenose-output/`). Check how `project_dir` is resolved in the CLI to make sure the DB ends up in the right place.

## What NOT to change

- Don't migrate data from the old global DB to per-project DBs. Old DB just becomes unused.
- Don't delete the old global DB. Users can clean it up manually if they want.
- Don't add a migration or backwards-compatibility layer. The serve importer re-creates everything from pipeline output files on startup anyway — a fresh DB is fine.

## Validation

After the change:
1. `bristlenose serve interviews/` → DB created at `interviews/bristlenose-output/.bristlenose/bristlenose.db`
2. `bristlenose serve other-project/` → separate DB at `other-project/bristlenose-output/.bristlenose/bristlenose.db`
3. No data leakage between projects
4. All existing serve tests pass unchanged
5. `ruff check .` clean
6. `.venv/bin/python -m pytest tests/` all green

## Estimated effort

20-30 lines changed across 2 files. 30 minutes including testing.
