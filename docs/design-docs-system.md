# Docs design system + writing style

> **Status:** proposal / working spec. Pairs with the mockup at
> [`docs/mockups/docs-site-mockup.html`](mockups/docs-site-mockup.html) and the
> integration plan in [`design-website-v2.md`](design-website-v2.md). The
> *versioning* axis (current / pre-release / archived-by-minor; path not dropdown;
> in-package docs as a free per-version archive) is split into
> [`design-docs-versioning.md`](design-docs-versioning.md).
> Read alongside the help-delivery thread (universal markdown → web + in-package
> sidecar `/docs/`, system-browser viewer, channel-fork, i18n boundary).
> Part B (writing style) is the standard the **`user-documentation-review`** agent
> should check the website docs against; this doc itself is trued by
> **`/true-the-docs`**. Part C maps every doc surface and the sync ripple.
> _Drafted 25 Jun 2026; voice + channel + links + map sharpened 26 Jun 2026._

The goal is a docs surface that **reuses the app's design language wholesale** and
adds the smallest possible docs-specific layer on top. Reuse first; invent only
what docs genuinely need that the app doesn't have.

---

## Part A — Design system

### A1. Reused from `bristlenose/theme/` (unchanged)

The docs stylesheet **consumes the same tokens as the SPA** — it does not redefine
them. When served by the sidecar (`/docs/`), it shares `bristlenose/theme/tokens*.css`;
the website render copies the same token values. The reuse is total at the token layer:

| Layer | Reused token | Value (neutral light) |
|---|---|---|
| Type family | `--bn-font-body` | Inter Variable → Segoe → system |
| Weights | `--bn-weight-normal / emphasis / strong` | 420 / 490 / 700 |
| Text | `--bn-colour-text` | `#1a1a1a` |
| Muted | `--bn-colour-muted` | `#6b7280` |
| Hairline | `--bn-colour-border` | `#e5e7eb` |
| Surface | `--bn-colour-bg` | `#ffffff` |
| Accent | `--bn-colour-accent` | `#2563eb` |
| Badge | `--bn-colour-badge-bg / -text` | `#f3f4f6` / `#374151` |
| Warning text | `--bn-colour-error-text` | `#c2410c` |
| Theming | `light-dark()` + `color-scheme` | dark mode comes free |

Also reused, not rebuilt: inline `code` styling, the **icon convention** (inline SVG,
`currentColor`, 2px round-cap stroke — see A3), and the calm/flat aesthetic we
converged on (hairlines not boxes, quiet labels, content owns colour / chrome stays
neutral).

### A2. Docs-specific additions (the whole new layer)

Deliberately small. In the app's atomic vocabulary:

**Atoms (new)**
- `.typebadge` — quiet pill naming the page's kind (Tutorial / How-to / Reference / Explanation) with its type icon.
- `.callout` — `info` / `warn` / `tip`. Hairline box, 3px left accent, leading icon. The one place semantic colour enters body content.
- `.copybtn` — copy-to-clipboard affordance on code blocks.
- `.crumbs` — breadcrumb trail.

**Molecules (new)**
- `.code` — fenced block + copy button.
- `.fork` + `details.ch[data-channel]` — the **app↔CLI channel disclosure** (native, independent, OS-default, per-page memory; see the channel-fork thread).
- `.sharedline` — "✓ same in app and browser" marker for non-forked guides.
- `.card` — front-page quadrant card.
- `.prevnext` — sequential footer nav.
- `table` styling — reference + troubleshooting tables.

**Organisms / templates (new)**
- `.topbar` — brand · nav · version chip · search.
- `.sidebar` — grouped doc tree.
- **Doc page template** — crumbs → type badge → h1 → lead → body → prev/next.
- **Front page** — hero + 4 cards + popular guides.

That's the entire docs-specific surface: 4 atoms, 6 molecules, 4 templates. Everything
else is the app's tokens.

### A3. Icon set — Lucide (real, not home-grown)

[Lucide](https://lucide.dev) (ISC). Inlined as SVG (no npm dep, no icon font — stays
within the bundle discipline), `currentColor`, 2px round-cap stroke — a near-exact
match for the SPA's hand-drawn icons (stroke ratio 0.083 vs the report's 0.087). The
**minimum set the docs actually use** (17):

| Icon | Use |
|---|---|
| `chevron-right` | disclosure, sidebar/quick-links |
| `book-open` / `wrench` / `list` / `compass` | the four type/group markers |
| `info` / `triangle-alert` / `lightbulb` | callouts (info / warn / tip) |
| `monitor` / `terminal` | app / CLI channel labels |
| `copy` / `check` | code-copy (+ the shared ✓) |
| `search` | topbar |
| `arrow-left` / `arrow-right` | prev/next |
| `menu` | mobile sidebar |
| `external-link` | links that leave the docs (recommended; not yet in the mock) |

Rule: lift the exact Lucide SVG; don't redraw. If the docs and the SPA both need a
glyph, use the *same* Lucide source so the two surfaces stay identical.

---

## Part B — Writing style guide

### B1. Reuse the glossary (don't restate it)

`docs/glossary.md` already owns **terminology + tone** — provider product names
("Claude", "ChatGPT", "Azure OpenAI", "Gemini", "Ollama"/"Local"), British spelling,
the seven sentiments, identity/privacy terms. It's the must-read before writing any
user-facing text and this guide does not duplicate it. This section adds only the
**docs-specific** layer on top.

### B2. The four kinds — register per kind (Diátaxis-lite)

We keep Diátaxis's *spirit* (separate by what the reader is doing) without the
*letter* (four rigid trees, never-mix policing). Friendly group names, not the academic
words:

| Group (nav) | Kind | Register — the one rule |
|---|---|---|
| **Get started** | Tutorial | Teacher owns the outcome. Guaranteed success on sample data. Minimal explanation, no choices. "By the end you'll have X." |
| **How-to guides** | How-to | A recipe (see B3). The one kind we're strict about. |
| **Reference** | Reference | Austere, neutral. *Describe* the machinery, don't instruct. Tables. Link out for "how to". |
| **Understand** | Explanation | Discursive — the *why*, the trade-offs, the alternatives. The page you could read away from the keyboard. |

A page declares **one** primary kind (its type badge). It may carry a short lead of
another register, but its body holds that register. Don't bury a recipe in theory;
don't turn reference chatty.

### B3. The how-to recipe rules (be strict here — it's our gap)

1. **Title states the goal**: "How to set up Claude", never "Claude".
2. **Serve a real-world goal**, not the mechanism. Assume competence — you're not teaching.
3. **A sequence of steps**, causally ordered, that anticipates where the reader's going.
4. **Omit the unnecessary** — no theory, no completeness-for-its-own-sake. Usability over coverage.
5. **Conditional imperatives**: "If you want X, do Y." Stay adaptable to the reader's variant.
6. **End with troubleshooting** (symptom → fix table) and a "see also" line.
7. **Channel fork only where steps genuinely differ** (setup / get-started). Most guides are shared — mark them "✓ same in app and browser" and don't fork.

### B4. Formatting conventions

- **Sentence-case headings.** "Set up Claude", not "Set Up Claude".
- **`code` for everything literal** — commands, paths, env vars, values, filenames. Never translate or alter code (`bristlenose configure claude` stays exact in every locale).
- **Callouts are rationed.** `info` = a useful aside; `warn` = data/privacy risk or a real footgun; `tip` = a shortcut. If every paragraph is a callout, none is. No new callout types.
- **Channel fork** authored as the two `<details>` (`macOS` / `CLI`) — quiet labels, app-first on Mac (see channel-fork thread).
- **Links — three roles, applied by the generator.** *Internal* (another docs page): accent + underline, same tab, no icon. *External* (off `bristlenose.app`): accent + underline + a trailing `external-link` glyph, new tab (`rel="noopener noreferrer"`). The generator adds external treatment automatically by host, so authors write plain markdown links. **`code` is for literals you type or read** (commands, flags, paths, env vars) — **never a URL you're meant to visit**: a settings URL is a link, not a code chip. When a treatment is unclear, match **Stripe** — calm, confident, unmistakable links are the bar.
- **Code/commands out of translatable prose** — so the future translation pipeline never mangles a command.

### B5. Voice checklist (before publishing a page)

- **Neutral and non-hectoring.** State facts and consequences, not morals. "Consistent codes are easier to compare across participants", not "…keeps the analysis honest". Cut value-laden adjectives — *honest, rigorous, proper, real, disciplined*.
- **Don't tell researchers how to do their job.** Explain what the tool does and the vocabulary it uses; the method is theirs. No universal claims about what research *is* ("that revision *is* the analysis"), no assuming their workflow ("expect to revise…"). A reader may have a fixed scheme, iterate, or be time-boxed — all valid.
- **Offer, don't insist.** "There is no single correct framework" beats "you should…". Conditional imperatives, not commands. Keep genuine safety imperatives (re-identification risk, false confidence in redaction) — those are about the tool, not their method.
- **Slightly British, no caricature.** Understated and plain; en-GB spelling (per the glossary). British by restraint, not costume — no "brilliant", "rather", "do mind".
- Peer-to-peer with an outside professional. No "as you know", no "no software to learn", no hand-holding.
- Never "power users" to justify anything. Our reader is a researcher, not an engineer.
- Provider **product** names in prose; internal config values (`anthropic`) only inside `code`.
- One fact, one home — if the manual/reference already states it, link, don't restate.

### B6. Channel posture (every page declares one)

The reader is on the macOS app *or* the command line, and is never asked to work out which. Never assume a paragraph's channel — mark every action. Each page takes one of four postures:

- **Fork** (`::: fork` → *macOS app* / *Command line*): when steps genuinely differ (setup, running). Each side is **self-complete** — the reader of one platform gets everything they need; never make them read the other side or compute a diff. Write the macOS steps from the actual app behaviour, the CLI steps from the actual commands.
- **Shared banner** (`::: shared`): in-report SPA actions identical in app and browser — star, tag, hide, export, codebooks, Miro, search. One "✓ same in app and browser" line, no fork.
- **Single-channel disclosure**: a CLI-only (PII redaction, transcribe-only) or app-only feature still carries the disclosure header naming its channel, so the reader knows whether it's for them.
- **No marker**: conceptual / reference pages with no platform-specific action.

## Part C — Doc surfaces & the sync map

Bristlenose documents itself across many surfaces in two genres, each with its own truth source and review agent. One feature change ripples through several at once — this is the index of what to touch and who guards it.

### The surfaces

| Surface | Genre | Truth source | Checked by |
|---|---|---|---|
| `docs/design-*.md`, `CLAUDE.md` (root + siblings), walkthroughs | Developer (human + robot) | Code + commits | `design-doc-review` via `/true-the-docs` |
| `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `SECURITY.md` | User-facing | Code, vs glossary | `user-documentation-review` |
| `man/bristlenose.1` (`.TH` date auto-bumped by `bump-version.py`) | User-facing (CLI) | Code | `user-documentation-review` |
| `bristlenose/cli.py` `--help` | User-facing (CLI) | Code (is code) | `user-documentation-review` |
| `bristlenose/locales/*/*.json` (×7) | User-facing (in-app chrome) | glossary + platform-text-map | `user-documentation-review` + `i18n-review` |
| `docs/manual.md` → `manual.html` | User-facing | Code; rendered at website deploy | `user-documentation-review` |
| **Website docs** (`bn.app/docs/` + sidecar `/docs/`) — this system | User-facing | Code; this guide, Part B | `user-documentation-review` *(out-of-tree — see gap)* |

Truth is always the **code** — `docs/methodology/` is the one inversion (spec over code). Derived docs are leads, not authority: true every fact against the code before drawing from it.

### The ripple — one feature change

code → `docs/design-*.md` (rationale) → `CLAUDE.md` (orientation) → `README` (feature list) → man page + `cli.py --help` (CLI) → locale JSON ×7 (in-app chrome) → website docs (how-to / reference / explanation) → `manual.md` (until it retires into the website docs).

Two things shrink it:

- **One markdown source → web + sidecar.** The generator emits both the website tree and the in-package `/docs/` from the same `content/*.md`, so in-app and web docs can't drift (see [`design-website-v2.md`](design-website-v2.md)).
- **The in-app Help modal is gone.** `?` / Help opens the browser-served docs, so help text lives **only** in the website docs — one home, not two.

### Doing vs should-be-doing

- ✅ Developer docs trued against code (`design-doc-review` / `/true-the-docs`).
- ✅ Classic user surfaces (README, man, locales, manual) audited by `user-documentation-review`.
- ◻️ **Gap, now closing:** the website docs live in a separate repo (staging `bristlenose-website-v2/` now; the website repo post-cutover), so no agent reaches them yet. `user-documentation-review` now names them as a surface and points here for the standard; wiring it to the website tree is a follow-up.
- ◻️ **Candidate:** a per-page channel-posture declaration the generator can lint (every page must declare fork / shared / single-channel / none).
- ◻️ **Candidate:** a voice-linter — greppable anti-patterns (`honest`, `rigorous`, "the point is", "expect to", "is the analysis") flagged at build.

---

## Assumptions made in the mockup

1. **Nav grouped by kind** (Get started / How-to / Reference / Understand) with friendly labels, not the Diátaxis words.
2. **Channel fork = section-level disclosure**, app-first on Mac, per-page memory — per the earlier thread.
3. **Universal docs are English**; the translated "core" stays in-app (the settled i18n boundary). Locale route reserved (`/docs/<lang>/…`) but only `en` exists.
4. **One markdown source → web + in-package**; desktop opens `/docs/` in the **system browser** (no in-app viewer); `/docs/` is auth-exempt.
5. **Light mode only** in the mock; `light-dark()` makes dark free when wanted.
6. **Lucide inlined**, ~17 glyphs, no dependency.
7. **Front page is a quadrant-card landing**, not a marketing page (marketing stays on `bn.app/`).
8. **Reference values are illustrative** — the env-var defaults (`large-v3-turbo`, `llama3.2`, etc.) must be truthed against current code before publishing.
9. **A downloadable sample folder exists** for the tutorial — it doesn't yet; the tutorial assumes we ship one.
10. **Version chip = installed version** (in-package docs are version-matched; web shows latest).

## Open decisions to firm up

1. ~~Sidebar IA: by kind vs by topic~~ — **settled: by-kind** (current): Get started / How-to / Reference / Understand.
2. **"On this page" right-hand TOC** — omitted for tightness; long reference/explanation pages may want one.
3. **Type badges** — keep (current) or is the sidebar group enough signal? Mild redundancy.
4. **The tutorial's sample folder** — do we produce and host one? The tutorial can't exist without it.
5. **Search** — stub only. Real search needs a mechanism (client-side index like Pagefind, or server-side). Deferred.
6. **manual.html ↔ docs front page** — does the new landing supersede `manual.html`, or do they coexist with cross-links? The one-source call.
7. **Where "Install" lives** — Get started group vs stays in the manual. Cross-link vs duplicate.
8. **Dark mode** — ship via `light-dark()` (free) or light-only for v1?
9. **Prev/next** — needs a defined linear order per section, or drop it for a flat "related" list.
10. **Reference accuracy pass** — a truthing sweep of every value against the code is a prerequisite for the reference section (not the how-tos/explanations).
