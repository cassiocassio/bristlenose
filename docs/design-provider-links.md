# Provider links and the claims that rest on them

The Mac app, the command line, the README and the website all send people to a provider's
pages (where to make a key, where to add credit, where the prices are), and a few of our
sentences rest on what those pages say (a US$5 minimum, that a free tier may use your
content to improve products). Provider pages move. Apple's app bundle cannot change after
release, so a wrong link baked into a build stays wrong until the next build.

**One register, one gate.** `bristlenose/data/provider-links.json` declares every link
once: its purpose, when it was last verified, and the files that carry a copy (its
mirrors). It also lists the claims, each with the page that supports it, and the retired
URLs that must never come back.

| | What it does |
|---|---|
| `tests/test_provider_links.py` | The offline gate, part of the normal test run. Fails when a provider URL appears in the tree that is not registered (printing `file:line`), when a listed mirror no longer carries its URL, when a file carries a URL it is not listed for, when a retired URL returns, or when a claim's wording leaves its file. |
| `scripts/check-provider-links.py` | The same check from the command line. `--list` prints every URL with its mirrors. |
| `scripts/check-provider-links.py --live` | Fetches each URL (browser User-Agent, redirects followed by hand) and reports the status and any move. A permanent move or a 4xx is a finding, with the files to update printed under it. A sign-in redirect on a link marked `login` is expected. A 403 is "check in a browser", not broken: some portals refuse scripts. `--provider claude` narrows it. |

What the sweep reads: tracked source under `bristlenose/`, `desktop/Bristlenose/Bristlenose/`
and `frontend/src/`, the README, INSTALL, DEVELOPMENT and `.env.example`, and the website
repo's `docs-src/` when it is checked out (`BN_WEBSITE_REPO`, default
`~/Code/bristlenose-website`; its mirrors are skipped when it is not). Markdown notes inside
the source directories are not read. API and OAuth endpoints, Azure endpoint placeholders and
font hosts are protocol constants, not links: the `ignore_patterns` list names them. Zoom,
Teams, Meet and Miro have no setup URLs baked in beyond those, and appear only where the
website docs link to their help pages.

## Procedure

**Changing a link** (a provider renamed a page, or `--live` reported a move):

1. Find it in the register by id (`scripts/check-provider-links.py --list`).
2. Change its `url` and `verified` date, then every file in its `mirrors`. The test names
   anything you missed, with the line.
3. If the old URL must never return, add it to `retired` with what to use instead.
4. Run the test, then `--live` for that provider.
5. Strings in the app bundle (Swift, the locale files, the bundled sidecar) are baked into
   a build and cannot change after release. The README and the website can change any time.

**Quarterly** (with the dependency review in `TODO.md`): run
`scripts/check-provider-links.py --live`, fix what it reports, then open each claim's
`source` page and check the claim still holds. Update `verified`. Then check the price
rows in `bristlenose/llm/pricing.py` against the four pricing pages (the `prices.token-rates`
claim) and bump `PRICE_TABLE_VERSION` only if a rate changed.

**Adding a link.** Put it in the register first, with the files that will carry it. A new
provider URL that is not registered fails the test, which is the point.

## Prices and policy wording

These are claims, not links. Each is listed under `claims` with its source page, the date
it was verified, and the exact phrase that must remain in each file (`contains`). If you
reword a sentence, change the phrase in the register in the same commit, and check the
source again. Claims verified on 21 Nov 2026: OpenAI and Gemini state a US$5 minimum
purchase; Anthropic's billing page states none; Anthropic says Max, Ultra and Team plans
include monthly API credits; Google's terms say unpaid Gemini services may use content to
improve its products and paid ones do not; new Gemini accounts default to prepaid credits.
The per-token rates were last checked on 19 Nov 2026.

## Known limits

The live check cannot see past a sign-in, so a console page that loads its shell but no
longer holds the setting it is named for looks fine to it. An `#anchor` is invisible to it
too. Both need a person in a browser, which is why the quarterly step says to open the
pages.
