---
name: session-digest
description: A dense, terse "where was I?" page for one session (default) or a week of sessions. Goals from the owner's own prompts, where you were / next / waiting on you, a dated map, screenshots and wording changes with a lightbox, decisions (and where they are logged), ideas rejected, review findings fixed/unfixed, done/undone/deferred, and a source link on every line. Use at the end of a session, or before returning to one after days away.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Skill, Artifact, AskUserQuestion, Agent
---

Read-only: no code edits, no tests, no commits. It writes the digest (and, after one yes, the open items).

```
/session-digest            this session
/session-digest week       the last 7 days of sessions, rolled up
/session-digest --local    skip publishing; keep the file only
```

Run after `/end-session` so commit states are final, or before it to see what is left.

## Rules

1. **Evidence, not recall.** Every line traces to a commit, file, tool result, agent report or owner message. If you cannot point at it, mark it `unverified` or cut it.
2. **Terse.** At most 12 words a line. Nouns and numbers. No adverbs of effort, no cheering.
3. **One state word per item**, from: `shipped committed decided logged done verified met drafted uncommitted partly unverified deferred rejected unbuilt pivot undone open blocked nowhere`. Decisions carry where they are logged, or `nowhere`.
4. **Say what you could not read** in `scope` (compacted conversation, a session known only by its reports).
5. **Count from the source.** Review findings come from the reviewer's own report; ungraded ones go under `U`. Never invent H/M/L.
6. **Chronological and concrete.** Build the map from recorded activity in time order (`git log --reverse`, file times, tool results, message order), never from memory.
7. **A link on every line that can have one** (refs, below).

## Steps

**0. Anchor.** One Bash call: `git rev-parse --short HEAD`, `git branch --show-current`, `git status --porcelain`, `git remote get-url origin` (https, credentials stripped), `git rev-parse --show-toplevel`. These fill `generated`; the page shows them with a freshness chip and a copyable `git log <head>..HEAD`. A digest is a snapshot: write a new one, never edit an old one.

**1. Gather, in parallel.**
- The conversation: the owner's messages, tool results, agent hand-backs.
- `git log --since=<session start> --reverse --stat`, `git status --short`, new files in `docs/`, `docs/mockups/`, `.claude/skills/`, new memory files.
- Linked sessions: `mcp__ccd_session_mgmt__list_sessions` with `linked: true`; read their reports, not their transcripts.
- Reviews: `/usual-suspects`, `/code-review`, agent hand-backs.
- *Week:* read the `.json` files already written to `docs/private/digests/` in the window, plus `git log` and the `100days.md` / `TODO.md` diff. Run an `Agent` per session only for sessions with no digest (it reads a whole transcript, so it is the expensive part).

**2. Write `digest.json`** (shape: the data block in `template.html`; every key optional, an item is a string or `{t, ref}`). Keys: `name` (2–4 word title), `title`, `window`, `scope`, `generated`, `last_active`, `resume{where, next, blocked[{t, cause, ref}]}`, `goals[{problem, state, quote}]`, `timeline[{when, label, state, now?, shot?, ref?}]`, `evolution[{subject, steps[{label, note, shot?}]}]`, `shots[{id, kind, when, caption, path}]`, `wording[{where, before, after, ref?}]`, `before`, `after`, `reviews[{round, reviewer, H, M, L, U}]` (each `[fixed, unfixed]`), `decisions[{text, logged_in, ref?}]`, `rejected[{idea, why, ref?}]`, `artefacts[{path, kind, state, unverified?}]`, `checks[{pattern, times, quote, answered, note, ref?}]`, `axes{product, feature, design, implementation: {chose, undone, deferred}}`, `done`, `undone`, `deferred[{item, trigger, age?, ref?}]`, `owner_open`, `unverified`. *Week:* `mode: "week"` and `sessions[{title, state, axes{product, feature, design, implementation}}]` with one short string per axis.

- **`blocked.cause`** is `decision`, `approval`, `input`, `review` or `external`: what unblocks it.
- **Goals** come only from the owner's messages: the problems they said they were solving, in their words (quote at most 8). Never your task list. At most 6; `pivot` when the goal changed, saying what changed it.
- **A decision** is something the owner chose or clearly accepted; a recommendation is not one. An unlogged decision (`logged_in: null`) is the most useful finding.
- **Rejected idea**: proposed and turned down, with the one reason. At most 5.
- **Axes**: product (what and for whom), feature (what it does), design (look and behaviour), implementation (how built). "none" is an answer.

**3. Read the owner's questions.** Take their last 15–25 messages (week: last 10 per session). Group repeats into patterns. Per pattern: the question in plain words, how many times, a quote of at most 8 words, and how it was answered: `evidence` (you cited something checkable), `assertion` (said so, nothing checked), `conceded` (you were wrong or overreached), `open`. No mood, no guessing at feelings. A question asked twice or more points at a gap in the record (a principle that is not written down, a check not made): name it and the smallest durable fix (a `CLAUDE.md` line, a test, a memory) in `owner_open`, as a suggestion. `assertion` and `open` answers go in `owner_open` too.

**4. Refs.** `ref = {file?, lines?, sha?, url?, cmd?, label?, snip?}`. The page links it when a durable https target exists and always offers a copyable command (`⧉`).

| Target | Use | Notes |
|---|---|---|
| Committed file or line | `sha` + `file` + `lines` | sha-pinned GitHub permalink; opens anywhere |
| Commit | `sha` | `/commit/<sha>`; copies `git show` |
| Uncommitted or untracked file | `file` | no link; copies `open -R "<root>/<file>"` |
| A doc section | `file` + `snip` (the heading) | line numbers drift, headings survive |
| A session | `cmd: "claude --resume <id>"` | no documented link to a session or message; copy only |
| An outside page | `url` (https) | |

`build.py` verifies every ref in one pass and marks it `ok` or `gone`. Not used: editor schemes (`vscode://`), `claude://`, `file://`, text fragments. All are unverified from a file page or a published artifact. Link behaviour on the three surfaces (file, desktop pane, artifact) has not been tested live.

**5. Visuals.** List design mockups, screenshots and QA images from this session in `shots` with their `path` only; search the session folder and any image path in the transcript, and keep missing ones (`build.py` marks them gone). Never put image data in the JSON: `build.py` downscales (960px JPEG) and embeds, at most 24 images and about 3 MB. Screenshots are of local files or mockups, never the dev stack, never participant data. Wording changes are exact strings copied from the diff.

**6. Build.**

```bash
python3 .claude/skills/session-digest/build.py digest.json docs/private/digests/YYYY-MM-DD-<slug>.html --root "$(git rev-parse --show-toplevel)"
```

Keep `digest.json` next to the page (week mode reads it). The page folder is gitignored; never `git add -f`.

**7. Publish.** Unless `--local`: build again with `--fragment` to a scratch path, load the `artifact-design` skill, publish with `icon: "summary"` and a one-sentence `description`. It stays private. Do not publish a digest that quotes research participants, recordings or transcripts.

**8. Offer the saves.** Only what `/end-session` has not already done: undone and deferred items to `100days.md` via `/add-todo` (kind and priority per item, creates a board card), unlogged decisions to the design doc named, one durable-principle suggestion to memory. List exactly what would be written and wait for a yes per list.

## Final message

Three numbers (undone, deferred, unlogged decisions), the link, the one item most likely to be forgotten. Nothing else.

## Not here

No test runs, code edits, commits or pushes. No participant data. No padding: an empty section says `none`.
