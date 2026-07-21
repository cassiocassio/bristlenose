# CLI formatting — de-facto conventions

**Status: DESCRIPTIVE, not yet ratified.** Captured 21 Jul 2026 during the
first-run provider-guidance rework. This doc writes down the presentation-layer
conventions the CLI has *actually* been following (scattered across code and a
few design docs) so they can be reviewed and either ratified or corrected in one
pass — there was no single home for them before. It is a description of current
practice plus open questions, not a spec handed down from on high.

Sibling docs own adjacent concerns: `design-cli-just-works.md` (§Glyph discipline,
first-run defaults), `design-cli-improvements.md` (§80-column width, Typer chrome),
`design-cli-provider-selection.md` (provider/model resolution), `design-cli-analysis-register.md`
(report voice/register). This doc is the presentation layer — glyphs, colour,
placeholders, tables, links — not feature behaviour.

## Source of truth (code)

- **`bristlenose/ui_kinds.py`** — the `MessageKind` taxonomy: glyph + colour per
  kind. This is authoritative; the tables below just describe it.
- **`bristlenose/cli.py:60`** — `console = Console(width=min(80, Console().width))`.
- **`bristlenose/utils/text.py`** — `count_noun()` for count-bearing strings.

## De-facto standards (observed, consistent)

1. **Width.** Our own output is capped at 80 columns (`Console(width=…)`). Typer's
   help/error boxes ignore this and use the full terminal — a known, accepted
   mismatch (users see help *or* pipeline output, not both). See
   `design-cli-improvements.md` §80-column.

2. **Glyphs are for state changes, not narrative.** Plain text is the default; a
   glyph appears only on a state-event line (success / info / warning / error /
   skipped). Emitted via `cli_prefix(MessageKind)` / the `_say()` helper. Same
   taxonomy the desktop uses (one vocabulary across channels).

3. **Colour comes from `CLI_COLOUR`** — SUCCESS green, INFO cyan, WARNING yellow,
   ERROR red, SKIPPED dim. Cyan is explicitly noted (in `ui_kinds.py`) as reading
   cleanly on both light and dark terminals. Content owns colour; *state* is the
   thing colour encodes.

4. **`[bold cyan]` is the accent for a runnable/hero command.** Introduced for the
   empty-state `bristlenose configure <provider>` (the one action on that screen).
   Cyan is already the INFO colour, so this is on-grid, not a new colour. **Open:
   whether this generalises** — see Open questions.

5. **Ordinary command references in prose are `[bold]bristlenose …[/bold]`** (bold,
   no colour) — ~18 sites. Bold-only is the baseline; cyan is the deliberate
   exception for a primary action.

6. **Placeholders: `<value>` in help/prose.** Angle brackets denote a
   value-to-replace — `<provider>`, `<folder>`, `<input-dir>`, `<output-dir>`,
   `<slug>`, `<id>`, `<name>`, `<command>`. Consistent across CLI help and docs.

7. **Square brackets in prose are NOT "optional".** In help/README/docs `[...]`
   means a markdown link (`[open an issue]`) or a pip extra (`pip install
   'bristlenose[serve]'`) — never an optional-argument marker. The man page
   (`bristlenose.1`, roff) is the one place the classic man convention applies:
   *italic* for a required replaceable (`.I input-dir`), `[...]` for optionals
   (`[ options ]`, `[ -o output-dir ]`). Two registers, no collision.

8. **Clickable URLs use `[link=url]url[/link]`.** This emits a real OSC-8 hyperlink
   *and* keeps the visible URL text, so OSC-8 terminals (iTerm2, VS Code, kitty,
   WezTerm) get a hyperlink and Terminal.app auto-linkifies the visible text.
   **Gotcha:** bare `[link]url[/link]` (no `=url`) emits **no** hyperlink — it only
   underlines. Always show the full `https://` so the fallback works.

9. **Tabular output is hand-aligned, not `rich.Table`.** 2-space indent, `.ljust(N)`
   / `{x:<N}` columns, `[dim]…[/dim]` for secondary detail. No box-drawing, no
   `rich.Table`, no panels — keeps the cargo/uv minimalist register.

10. **Plurals via `count_noun(n, "singular")`** for any count-bearing string (CLI is
    English-only in alpha). No hand-rolled `f"{n} thing{'s' if …}"`.

11. **Markup safety.** `escape()` any user-interpolated text inside markup;
    `markup=False` / `highlight=False` where Rich would otherwise eat brackets or
    auto-highlight a token (e.g. `<provider>` rendering magenta under the repr
    highlighter; `pip install pkg[extra]` losing `[extra]`).

12. **Copy principles (settled this session).** No cost figures (they bit-rot and
    are false-precision without a study-size). No opinion labels
    (recommended / enterprise / budget / "good quality"). No cute copy. State
    prerequisites (facts: "needs an Azure OpenAI resource"), not judgments. Teach
    the verb; let ordering + defaults carry any recommendation implicitly.

13. **First-run guidance is print-and-exit, not a numbered menu.** A CLI user who
    already handles `run`, paths, `serve`, `--clean` doesn't need a wizard —
    show the command and where to get a key, then exit.

## Working assumptions (grounded, but not independently re-verified)

- **Cyan is theme-safe** on light and dark terminals (per the `ui_kinds.py`
  comment; not re-tested across the full terminal matrix).
- **Terminal.app does not support OSC-8**, so plain-URL auto-linkification is the
  floor and OSC-8 is progressive enhancement. (True as of writing; Apple could
  change it.)
- **The 80-column cap is the target for *our* output only**; Typer chrome is out
  of scope by decision, not oversight.

## Open questions (for the review)

- **Should runnable commands be cyan CLI-wide,** or does cyan stay reserved for a
  screen's single hero/primary action (empty-state `configure`)? Today it's the
  latter by default; a ~18-site sweep would make it a rule. Consistency vs.
  emphasis — pick one and state it.
- **`<provider>` placeholder rendering** — currently plain inside the bold-cyan
  command. Option: a deliberate placeholder treatment (dim/italic) so it reads as
  "fill this in." Trivial either way; wants a taste call.
- **Does `configure <provider>` set the active provider?** Today `configure chatgpt`
  stores the key but a plain `bristlenose run` still defaults to Claude unless
  `--llm` is passed. Orthogonal to formatting, but surfaced here because the
  guidance implies "configure = done." (Also tracked as a capture in the inbox.)
- **Man-page vs prose placeholder registers** — documented above (§7) and correct,
  but worth a nod in the review so nobody "fixes" one to match the other.
- **Ratify or fold.** Decide whether this becomes a ratified standard (and whether
  it should merge into `design-cli-just-works.md` rather than stand alone).
