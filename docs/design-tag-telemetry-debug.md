---
status: current
last-trued: 2026-11-26
trued-against: HEAD@main on 2026-11-26 (2f4a3a0b5), as built
---

# Tag signal, counted locally

*Owner decision, 26 Nov 2026: before any tag telemetry is sent anywhere, the
owner counts the signal from their own real studies, on their own Mac, for
months, to see whether it is worth having. Nothing is sent, so nothing is
declared. When testers are asked to send it, that change carries the opt-in,
the App Store privacy label, SECURITY.md and the privacy pages, as the
methodology doc requires.*

The spec for the signal is
[`docs/methodology/tag-rejections-are-great.md`](methodology/tag-rejections-are-great.md).
This phase departs from it in one way, recorded there as a dated ruling: it
collects nothing new and sends nothing. It reads what each study's database
already holds.

## 1. Why local, and why not a sender

A first version of this design (same date) had a Debug-only switch in the Mac
app turning on a Python sender that posted to `bristlenose.app/telemetry.php`
with a shared key. An adversarial review rejected it:

- **The Python half would ship everywhere.** The sender module would be in the
  App Store and `.dmg` sidecars and in every CLI package. Anyone setting the
  right environment variables would make their install send; the key only
  stops the endpoint recording it. A dormant sender in a shipped bundle is
  what Apple's guideline 2.3.1 is about, and SECURITY.md's list of what leaves
  the machine would no longer be complete.
- **The four wire fields can't be counted correctly.** One proposal can be
  denied, undone and denied again, and nothing in the four fields ties those
  events together. Most proposals are decided by the confidence threshold,
  which the spec's formula scores as failures.
- **The owner's Debug Mac is also the test machine.** A fixture study coded
  twenty times would count twenty times.

Each study's database already holds every proposal's final state, who decided
it, its confidence, the prompt version and the model. Counting from there
answers all three, sends nothing, and leaves the metric open until real
numbers have been seen.

## 2. The tool

`scripts/tag-signal.py`, run by hand:

```
.venv/bin/python scripts/tag-signal.py <study output folder> [<another> ...] [--csv <path>]
```

It lives in the source tree only. `scripts/` is in the sdist but in no wheel,
sidecar, snap or installer, and the script has no network code.

**Studies are chosen, never discovered.** It reads only the folders named on
the command line, each `<output>/.bristlenose/bristlenose.db`. No scanning of
the disk and no default list, so a test fixture counts only if the owner
names it.

**It leaves a closed study's folder exactly as it found it, to the byte.**
For an open study the main file and `-wal` are untouched too; only SQLite's
shared-memory `-shm` index changes, as it does for every reader, the app's
included. Run it with the app closed for a guaranteed untouched folder.
SQLite's `mode=ro` is not enough: on a cleanly closed WAL database it creates empty `-wal` and
`-shm` files beside it (measured 26 Nov 2026), which would change the folder
the Mac's locate flow compares by modification time. So:

- if there is no `-wal`, or it is empty, the database is opened `immutable=1`
  (the same rule as `CurationCountsReader.swift`), which creates nothing;
- otherwise (the app has it open, or crashed with frames in the WAL) it is
  opened `mode=ro`;
- a WAL with frames but no `-shm` (a copied folder) is skipped, since
  `mode=ro` would create one;
- a database with a `-journal` file is skipped: a read-only connection
  cannot roll back an interrupted write and would count half-written rows.

The URI is built with `Path.as_uri()`, so folder names with `?`, `#` or `%`
open the right file. A missing database is reported, never created. Each
study is read with `fetchall()` and the connection closed before the next, so
no read is held open against the app's checkpoints. A study that cannot be
opened is skipped with its reason on stderr and the run carries on, and a
study named twice is read once.

**Old databases are skipped, not crashed on.** It reads `alembic_version`
first. Below `027` (no `decided_by` column) the study is skipped with "open it
in Bristlenose once to update it" on stderr, and the run carries on.

**Shipped tags only, matched the app's way.** A row counts only if its group's
`framework_id` names a bundled template *and* the tag's stored name matches,
by `codebook_sync._key` (lower-case, stripped), either that template tag's
current name or one of its `renamed_from` names. So a study not opened since
a wording revision still counts under the current name. A framework tag the
researcher renamed, a custom tag moved into a framework group, a retired tag
and an archived framework are all skipped. Per framework the tool prints how
many rows it read, counted and skipped, as counts, so a skip is visible.

**Strings come from code where it matters.** The framework id and tag name
printed are the template's. The job's `llm_provider`, `llm_model`,
`prompt_version` and `status` and the proposal's `status` and `decided_by` are
printed as stored; the app writes all of them, and only `llm_model` is free
text. Per-study errors, which carry folder
paths, go to stderr only.

**What is counted.** One row per `ProposedTag`, by its current `status`
(`pending`, `accepted`, `denied`) and its raw `decided_by` (`researcher`,
`threshold`, `unknown`, or none). Undo and re-decide collapse to whatever the
database holds now. `unknown` is every proposal decided before migration 027
(23 Nov 2026): those cannot be split by who decided.

**Grouped by** framework, tag, the job's `prompt_version`, `llm_provider`,
`llm_model` and job `status`, with the number of studies contributing to each
line.

**Output** is a table on the terminal, or `--csv <path>` to a file the owner
chooses, with an `as_of` date column. Nothing is written anywhere else.
Snapshots, if kept, belong in the owner's private notes, not the public repo.

## 3. Choosing the metric later

The spec's `success_rate = (accepted + edited) / suggested` scores a
threshold-decided row as "ignored", which it counts as failure. This phase
picks no formula. It reports raw counts split by `decided_by`, so the owner
can compare "researcher accepted", "researcher denied" and "threshold
decided" after looking at real studies. The chosen metric goes into the
methodology doc as a dated ruling before any sender is designed.

**Stopping rule, owner's call:** how many researcher-decided rows over how
long would mean "not worth having". There is one proposal per quote per
codebook and most are decided by the line, so researcher decisions will be
few.

## 4. What this change removes

The unused public plumbing from Phase 1 (2 May 2026) goes, because today it
advertises a switch that is on by default:

- `BRISTLENOSE_TELEMETRY_ENABLED`, `BRISTLENOSE_TELEMETRY_URL`,
  `DEFAULT_TELEMETRY_URL` and `DEV_TELEMETRY_URL`, and the `telemetry` block
  of `/api/health` (`bristlenose/server/routes/health.py`). Every HTML export
  embeds that block, so it goes from new exports too.
- The `telemetry` part of `HealthResponse` and `DEFAULT_TELEMETRY_URL` in
  `frontend/src/utils/health.ts`.
- Tests and fixtures: `tests/test_serve.py`, `tests/test_serve_export_api.py`,
  `frontend/src/router.crashContainment.test.tsx`,
  `frontend/src/components/FeedbackModal.test.tsx`,
  `frontend/src/components/Footer.test.tsx`.
- Docs: `bristlenose/server/CLAUDE.md`, `bristlenose/server/gotchas.md`,
  `docs/design-welcome-cli-reuse.md`, and a dated ruling in the methodology
  doc. `docs/design-website-v2.md` keeps its mentions: it is the record of the
  cutover, when the endpoint did ship.
- Website repo: `content/telemetry.php`, its row in `notes/server-endpoints.md`
  and `README.md`, and a `deploy.sh` check that the URL returns 404. The file
  leaves the server at the next deploy; `data/telemetry.csv` must be deleted
  by hand (`deploy.sh` protects `data/` from `--delete`).

The `--dev` stub at `/api/dev/telemetry` stays: it is local, mounted only in
dev, and is where a future sender would be exercised first. Its docstring
stops naming the public URL.

**Not done by this change:** the built frontend under
`bristlenose/server/static/` and the Mac sidecar still contain the string
until their next rebuild. Exports already sent carry the old block for good:
a URL and a flag, with no sender behind them.

## 5. Known limits

- **Provider, model and prompt version describe the job, not each
  proposal.** There is one `AutoCodeJob` per project and codebook, stamped at
  its main run; the catch-up path stamps nothing, and `llm_model` is the
  configured default rather than the model actually called (an Ollama tag or
  Azure deployment is not recorded). Grouping by them separates runs only
  roughly.
- **`prompt_version` is hand-bumped** (`0.1.1` from the prompt's front
  matter). A prompt edit without a bump is invisible.
- **A tag's definition can change** while its name stays the same. Rows are
  grouped by current name only.
- **Counts can shrink.** Re-analysis deletes a study's proposals
  (`importer.py`), and removing a codebook deletes its jobs and proposals
  (`delete_jobs`, `autocode.py`). A study's counts describe its latest
  AutoCode run; history lives only in the snapshots the owner keeps.
- **Running, failed and cancelled jobs** contribute partial sets; the job
  status column shows which.
- **A study and its backup clone** are different folders and both count if
  both are named.
- **A proposal whose tag was deleted** drops out of the join and is not in the
  read tally.
- **There is no `edited` event.** AutoCode proposals have no span adjustment.
- **Confidence is not reported.** Threshold rows mean more next to where the
  line sat; add it if the counts prove interesting.

## 6. Tests

In `tests/test_tag_signal_script.py`, each protection mutation-checked:


- Fixture databases covering: a shipped tag; a shipped tag stored under a
  `renamed_from` name; a framework tag the researcher renamed; a custom tag in
  a framework group; a custom group; an unknown framework id. Only the first
  two count, under the template's current spelling, and the skip counts are
  right.
- A proposal denied, then accepted, then denied counts once, as denied.
- `decided_by` of `unknown` and none are reported as themselves.
- A database below migration 027 is skipped with a message, and the next
  study is still counted.
- **The study folder's listing, sizes, modification times and bytes are
  unchanged** after a run: for a closed database, for an empty `-wal` left by
  another reader (with and without its `-shm`), and, `-shm` content aside, for
  one the app has open. A WAL with frames but no `-shm`, and a `-journal`, are
  skipped with nothing created.
- An unreadable study, a database with no `alembic_version`, and a study named
  twice don't stop or inflate the run; the `studies` column counts studies.
- A folder name containing `?` and `#` opens the right database.
- `/api/health` has no `telemetry` key, and no export embeds one.
