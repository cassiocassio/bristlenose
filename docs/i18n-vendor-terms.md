# Vendor-owned words: Claude's and ChatGPT's "plugin"

**Read before translating any string that tells the user what to click or find in another vendor's app.** Settled by the owner on 14 Nov 2026: do not re-research per session, use the row.

## The rule

- **Say what the vendor says, in that vendor's tab, in the user's language.** The vendors disagree with each other (Spanish: Claude says *Plugins*, ChatGPT/Codex says *Complementos*) and that is fine.
- **Ground truth is two things together:** the vendor's sidebar label in its own app, and the same word in its public help centre. Where the vendor does not localise a language, use its English word.
- **One key family per vendor** (`desktop.mcpAgents.claude*` and `chatgpt*`), never a shared key or a shared noun.
- **Two tie-breaks.** Our own sentences use the noun the vendor's help title uses; a section or button we *quote* is spelled exactly as the app shows it (Russian: noun *плагин*, quoted «Plugins», because Claude's Russian help article leaves its UI path in English). Where help title and app disagree on form (Norwegian ChatGPT: help *Pluginer*, app *Plugins*), the help title decides the plural and the app decides the label.

## Where the answer lives

`bristlenose/locales/vendor-terms.json` is the only table: per vendor, per locale, the `label` users see, the `stem` every string of that tab must carry, and the `evidence` grade. `tests/test_vendor_plugin_terms.py` pins it (a new language fails until both vendors have a row); the Swift `VendorPluginWordTests` checks the labels resolve and fit. The JSON covers "plugin" for these two vendors only; other vendor labels (Miro, Figma, Zoom, Teams) follow the same rule and have no data yet. macOS's own labels follow `.claude/agents/i18n-review.md` § 6c, not this.

## Why not the platform glossary

The Apple/Microsoft glossary settles generic words (window, paste, zoom). Measured in Apple's 3,275 system loctables: no string translates "Plug-in", and Apple's noun for the category is "Extension" (Microsoft's corpus was not measured). For a vendor's own feature name the only authority is the vendor.

## Refreshing a row

Only on a vendor rename, a new language, or a user report; then edit the JSON row and its `checked` date and run the test.
- **Claude:** `curl -sL -A "<browser UA>" https://support.claude.com/<loc>/articles/13837440` (it redirects to `/en/` where Claude is not localised) and read the UI path the article quotes.
- **ChatGPT:** `help.openai.com` answers automated fetches with 403, so open one article in a browser and `fetch('/<xx-yy>/articles/20001256')` per locale for the title; read the sidebar label in the desktop app (Settings ▸ General ▸ Language switches the whole UI at once).
- A search-engine summary of a help page is not the page.

History and the evidence behind today's rows: `docs/archive/i18n-vendor-terms-evidence-2026-11.md`, and the 14 Nov 2026 entry in `docs/design-i18n.md`.
