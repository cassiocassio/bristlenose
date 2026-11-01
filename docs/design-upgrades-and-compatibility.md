---
status: proposal. Nothing here is decided except §2 (what beta does today). §4 is for the maintainer to rule on.
last-trued: 2026-11-01
trued-against: HEAD@main on 2026-11-01
---

# Upgrades and breaking changes: what we promise, in beta and at v1

**The question (maintainer, 1 Nov 2026):** *what is the strategy for upgrades and breaking
changes? Once v1 is out of beta we have different promises to keep than the weekly churn of
a beta with no users.*

**Short answer.** Beta promises almost nothing and that is fine: formats change, caches are
re-paid, an older build refuses a newer study with one line (N147, built 1 Nov). At v1 a
researcher's **study folder becomes an archive they own**, so the promise changes from "the
newest build works" to "**a study keeps opening, and keeps its work, across versions**". That
promise is cheap to keep if the rules are set before v1 and expensive to retrofit after.
This document inventories what is versioned today, says what beta does, proposes the v1
promises, and lists the owner decisions.

---

## 1. What is versioned today (measured 1 Nov 2026)

A study is a folder the researcher keeps; several of its files carry a format that code reads
back. Different builds (the Mac app, the CLI from PyPI or Homebrew, an older sidecar) read the
same folder, and they do not update together (`design-channel-version-lag.md`).

| What | Where | Version today | On a newer file |
|---|---|---|---|
| Study database (curation: stars, tags, edits, names) | `bristlenose.db`, Alembic | 25 revisions, newest `025` | **older build refuses with one line** (N147) |
| Pipeline manifest | `.bristlenose/pipeline-manifest.json` | `schema_version` 1 | not checked here |
| Run events log | `.bristlenose/pipeline-events.jsonl` | `SCHEMA_VERSION` 1 (`events.py`) | readers fail closed on a known event that no longer fits |
| Run condition | derived from the events log | `SCHEMA_VERSION` 1 | derived |
| Session registry (sticky `s1`, `p3` ids) | `.bristlenose/sessions.json` | `REGISTRY_VERSION` 3 | not checked here |
| Sidebar project list | `projects.json` (Mac) | `Project.currentSchemaVersion` 1 | a damaged file is set aside |
| Transcript parsers | in cache fingerprints | `s03`=2, `s04`=4 | a bump re-reads, and **re-pays** (see §3) |
| Report data contract | `pipeline_view/render.py` | `SCHEMA_VERSION` 4 | |
| Intermediate JSON (topics, quotes, clusters) | `.bristlenose/intermediate/` | **none** | read by whatever build runs next |
| Host to sidecar | handshake file, bridge messages, MCP tools, `.mcpb` | a schema field on the handshake only | |
| Exports: CSV, HTML export, Miro/FigJam board, clips | the researcher's own files | none | the researcher's, forever |

**What is missing.** There is no golden "a study made by release X" fixture opened by HEAD
in CI (there are per-migration tests, and the smoke fixture is an *input*). There is no copy
of the database taken before a migration runs. The intermediate JSON has no version at all.

## 2. What beta does today (and should keep doing)

- **Always migrate forward; never downgrade.** The database upgrades to head on open.
- **An older build refuses a newer study** with *"This study was opened by a newer Bristlenose.
  Update to open it."* and exit 2 (`StudyIsNewerError`, N147). No traceback, no guessing.
- **Caches are fingerprint-keyed; a bump re-reads.** Cheap when the reread is local; **not
  cheap when it cascades to a paid call.** On 31 Oct 2026 a Word-parser bump (4 to 5) was
  caught in review because the parser version is folded into the fingerprint of *every*
  transcript session, so it would have re-paid a speaker-identification call per transcript
  session in every existing project. It was reverted. The lesson is the rule in §4.3.
- **The changelog is exhaustive** (maintainer rule, pre-v1): it is the burn-down record.
- **No compatibility shims for beta users.** There are none to protect.

## 3. Failure modes the product has already met

1. **An older build on a newer study** crashed with Alembic's traceback (N147).
2. **A fix that changed a stored format** (the `?`/`%` database path, N197) left some
   studies opening empty; the best available answer was one log line (ruling 7).
3. **A version bump that silently re-paid analysis** (above).
4. **A format with no version**: intermediate JSON changed shape under existing projects and
   was survived only by "tolerate a missing key, stamp it, be strict next time"
   (`_inputs_changed`).
5. **Channels that update at different times** put two builds on one folder at once (the Mac
   app and a Homebrew CLI, or a sidecar older than the app).

## 4. Proposed promises for v1 (for the maintainer to rule on)

The principle: **a researcher's work is never lost or silently re-paid by an upgrade.** The
rest follows from it. Each item is a promise we would be willing to put in the docs.

### 4.1 Forward: a study keeps opening
*Promise:* a study made by any v1.x release opens, with its work, in every later v1.x
release. *Cost:* migrations are additive or expand/contract (add, dual-read, remove only after
N releases); no destructive migration without a reversible step. *Today:* true by habit, not
by test.

### 4.2 Backward: an older build says no, kindly
*Promise:* an older build never corrupts a newer study; it refuses with one sentence, and the
Mac says the same in its own words. *Choices:* refuse outright (today), or open read-only if
the schema is only additively newer. *Recommendation:* keep refusing; read-only is a feature.

### 4.3 No silent re-pay (the rule that failed on 31 Oct)
*Promise:* an upgrade never causes a paid call the researcher did not ask for. *Mechanism:*
every fingerprint input that a release changes is classed **free** (re-read, re-render) or
**paid** (re-extract, re-identify), and a **paid** change must either not invalidate existing
work or wait for an explicit Re-analyse. A release's changelog says "re-reads once" for the
first and nothing is allowed for the second without owner sign-off. *Cheap first step:* a test
that opens a frozen v-previous study at HEAD and asserts **zero LLM calls on Analyse**.

### 4.4 A safety net before the one-way door
*Promise:* before the first migration of a study's database to a newer revision, keep a copy
(`bristlenose.db.pre-<rev>`), removed after a successful open and one clean run, or kept N
days. *Today:* none. *Cost:* a file copy; the sandbox allows it inside the study.

### 4.5 A real-world upgrade fixture and a matrix
*Promise, enforced:* CI opens **golden studies made by previous releases** (one per
migration era, scrubbed) in HEAD: migrates, opens the report, Re-analyse offers the right
confirmation, curation counts match. The v1 gate is "the matrix is green". Without this the
promises in 4.1 to 4.4 are intentions.

### 4.6 Version the unversioned formats at v1
Add a version and a "tolerate older, refuse newer" rule to the intermediate JSON and the
manifest before v1, because after v1 "no version" means "version 1 forever". The cheapest
time to do it is the release that declares v1.

### 4.7 Surfaces other than the study folder
- **CLI:** flags and commands are deprecated for N releases with a warning before removal;
  `--help`, the man page and the website `cli.md` change together (existing rule).
- **Exports the researcher keeps** (CSV columns, the self-contained HTML export, board
  exports): additive changes only; a removed column is a breaking change with a changelog
  line. The HTML export embeds its own bundle and stays readable offline from `file://`.
- **MCP tools and the `.mcpb`:** names and argument shapes are an API; add, do not change.
- **Host to sidecar (bridge, handshake):** the app and its bundled sidecar ship together
  (always matched); only the CLI-with-Mac-app mix needs the version fields to be honest.

### 4.8 Communicating it
Release notes say, per release, one of: *nothing changes for your studies*, *your studies are
re-read once (free)*, or *Re-analyse will use new analysis (paid, optional)*. The changelog
format already groups New/Improved/Fixed; this adds a one-line "your studies" status.

## 5. What this does not settle

- Whether v1 means "no breaking change in a major" (semver) or a looser promise.
- The support window: how many releases back must a study open? (Proposal: all of v1.x.)
- Downgrade of the *database* itself (rejected: a refusal is cheaper and safer).
- Channel lag (`design-channel-version-lag.md`): a promise is only as good as the slowest
  channel's ability to receive the fix that keeps its older studies opening.

## 6. Decisions for the maintainer

1. Adopt "a study keeps opening and keeps its work; an upgrade never silently re-pays" as the
   v1 principle (§4.1, §4.3)?
2. Take a copy of the database before a migration (§4.4), and for how long?
3. Build the golden-study matrix as a v1 gate (§4.5)? Which eras (first public build, first
   TestFlight build, each migration cluster)?
4. Version the intermediate JSON and manifest in the v1 release (§4.6)?
5. Is an older build allowed to open a newer study read-only, or only refuse (§4.2)?
6. How long do CLI flags and exports stay deprecated before removal (§4.7)?

**Cheap things that are safe before any of that:** the paid-versus-free class on fingerprint
inputs (§4.3), the pre-migration copy (§4.4) and one golden study from the current release
as a seed for §4.5. None changes a researcher's screen.
