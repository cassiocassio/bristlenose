# Vendor-owned words: when our copy names another app's label

**Read before translating any string that tells a user what to click, open or look for inside Claude, ChatGPT, Codex, Figma, Zoom, Microsoft or any other vendor's app.** The word the user must find is the vendor's, in the vendor's localisation, and two vendors translate the same English word differently. "Plugin" is the worked case (13 Nov 2026); the rule is general.

## The rule

1. **A vendor label is not ours to translate.** Our own buttons and sentences use our locale's word; a sentence that points at a vendor's screen quotes the vendor's label as that vendor spells it in that language. Settle it with evidence per vendor per language, never by one noun for both.
2. **Where the vendor does not localise, quote the English label.** If Claude's help centre has no article in a language, the app is probably English there too, and a translated noun matches nothing on screen. (Probably: docs and app can differ; Spanish was checked against the app and agreed.)
3. **One key family per vendor.** A string shared by two vendor tabs (`installPlugin` on both the ChatGPT and Claude tabs) is the same mistake as reusing a key that "fits" (`.claude/gotchas.md` § i18n). **Split 13 Nov 2026:** `desktop.mcpAgents.chatgptInstall` / `chatgptReinstall` / `chatgptUpdate` / `chatgptBuild` and `claudeInstall` / `claudeReinstall` / `claudeUpdate` / `claudeBuild` / `claudeUnknownBuild`, each filled from the table below (the ChatGPT family from the OpenAI column, the Claude family from the Claude column, English "plugin" where Claude does not localise). Spanish is the proof: "Instalar complemento…" on the ChatGPT tab, "Instalar plugin…" on the Claude tab. The nouns come from help-centre titles; the running apps are the ground truth and were being checked per language when this was written.
4. **Evidence goes in the table below, dated.** A vendor rename (Claude renamed Extensions to Plugins on 13 Nov 2026, the day this was written) makes a row stale; re-run the method before relying on one.

## Evidence, 13 Nov 2026 (what each vendor's own help centre calls a plugin)

| Locale | ChatGPT help article title | Claude help article title | Note |
|---|---|---|---|
| es | **Complementos** en ChatGPT; the Codex app UI says Complementos (owner screenshot, Spanish macOS) | Usar **plugins** en Claude; the Claude app sidebar says **Plugins** (owner screenshot, Spanish macOS) | the clearest split: same language, two words |
| fr | Les **plugins** dans ChatGPT (fr-fr); les **plugiciels** (fr-ca) | Utiliser les **plugins** | we said "module": matches neither |
| de | **Plugins** in ChatGPT | **Plugins** in Claude verwenden | no hyphen in either |
| it | **Plugin** in ChatGPT | Usa i **plugin** | no hyphen |
| pt-BR, pt-PT | **Plugins** no ChatGPT (both) | Usar **plugins** no Claude (one `pt` article) | |
| ja | プラグイン | プラグイン | native noun, agree |
| ko | 플러그인 | 플러그인 | agree |
| ru | Плагины | плагины | agree |
| uk | Плагіни | none (English article) | |
| cs | **Pluginy** | none | we said "zásuvný modul" |
| da | Plugins | none | |
| sv | Pluginer | none | |
| nb | Pluginer | none | we said "tillegg" |
| fi | Lisäosat | none | |
| nl | Plug-ins | none | |
| pl | Wtyczki | none | |
| tr | eklentiler | none | |
| ca | "Connectors" (the app says it too, so not stale) | none | we said "complement"; the ChatGPT tab now says connector |
| zh-Hant | no help article (zh-tw, zh-hk, zh-cn all 404), but the app says 外掛程式 (both Taiwan and Hong Kong) | 外掛程式 | agree |

Claude's help centre localises only es, fr, de, it, pt, ja, ko, ru and zh-TW; every other locale path serves the English article. OpenAI's localises 20 of our 21.

Vendor-side words that are not ours: Claude's **Plugins** sidebar item and **Uninstall** button, ChatGPT's **Install plugin** and **Work** mode. Where that vendor localises (see the table) our copy uses its localised word; where it does not (the ten locales Claude's help centre skips), the word is probably English on the user's screen, and our sentences quote it as English. Claude's own app was checked only in es, fr and en.

## App ground truth, 13 Nov 2026 (ChatGPT/Codex desktop, Settings ▸ Integrations sidebar item, language set per language)

The ChatGPT desktop app's own Plugins label in all 21 of our languages (the owner approved driving the app; its language override applies immediately, and the setting was returned to Auto detect): es **Complementos**, fr **Plugins**, de **Plugins**, it **Plugin**, pt-BR and pt-PT **Plugins**, ja プラグイン, ko 플러그인, nl **Plug-ins**, pl **Wtyczki**, ru **Плагины**, sv **Pluginer**, da **Plugins**, nb **Plugins**, fi **Lisäosat**, tr **Eklentiler**, uk **Плагіни**, cs **Pluginy**, ca **Connectors**, zh-TW and zh-HK 外掛程式, en **Plugins**. It agreed with the help-centre titles in every language; the help centre was right even where it looked wrong (Catalan "Connectors"). So the cheap method below is reliable for ChatGPT; the app check is for a language the help centre lacks. Claude Desktop's own app was checked only in Spanish and French (Plugins in both) plus English.

**Claude's section name, from its own localised help articles** (the article quotes the UI path "Customize > Plugins", so the path shows the label the app uses in that language; 14 Nov 2026): es, fr, de, pt **Plugins**; it **Plugin** (Personalizza > Plugin); ja プラグイン (カスタマイズ > プラグイン); zh-TW 外掛程式 (自訂 > 外掛程式); **ru left it English** ("Customize > Plugins" inside the Russian article, so Claude's UI is probably English there, and `claudeReinstallHow` quotes «Plugins»). ko's article gave no path; its title says 플러그인.

**The new Debug build was checked running (14 Nov 2026, English UI, read through macOS accessibility, not by screenshot):** Settings ▸ MCP Agents ▸ Claude Desktop shows "Adds Bristlenose to Claude Desktop as a plugin. Claude Desktop will ask you to confirm." and "Plugin 0.46.0 (6528)". The ChatGPT tab and the other languages were not read in the running app (only the bundle's locale files).

## Resolved 14 Nov 2026: the Latin word stays on the Claude tab, until the owner reverses it

Resolution, not an open item: the rule below was approved with the key split on 13 Nov 2026 ("Claude tab: the Claude column where it's localised, otherwise the English 'plugin'"), so it stands. The recommendation that follows is the alternative if a native reader finds the Latin word jarring; it is a 10-locale revert of the five Claude-family keys plus the hint, prompt note and welcome tip, with the ChatGPT-tab values as the source.

### Recommendation if revisited

Rule 1 says our own buttons use our locale's word; rule 3 fills the Claude-tab button family (`claudeInstall`, `claudeReinstall`, `claudeUpdate`, `claudeBuild`, `claudeUnknownBuild`, `claudeDesktopHint`) from the Claude column, which is Latin "plugin" in the ten locales Claude does not localise. The result in uk, tr, fi and others is a loanword or Latin word inside a native sentence ("Встановити plugin…", "Asenna plugin…") next to a ChatGPT tab that says плагін, lisäosa. **Recommendation:** keep Latin only where we QUOTE Claude's screen (`claudeReinstallHow`'s section name «Plugins», which is what the user must find), and give the buttons and sentences our own locale's noun, the one the ChatGPT tab already uses, because a button is ours and the user does not search for it. That makes the Claude and ChatGPT tabs read alike in those ten locales and removes the uninflected Latin word from Cyrillic, Finnish and Turkish sentences. It is a 10-locale change (ca, cs, da, fi, nb, nl, pl, sv, tr, uk) to the five Claude-family keys plus the hint and prompt note; not made overnight because it reverses the 13 Nov ruling in rule 3 and wants a native read.

## Method (rerun it, do not trust the table's age)

- **Claude**: `curl -s -L -A "<browser UA>" -H "Accept-Language: <loc>" https://support.claude.com/<loc>/articles/13837440-use-plugins-in-claude`, read the final URL and `<h1>`. An unlocalised locale redirects to `/en/`.
- **OpenAI**: `help.openai.com` answers curl and WebFetch with 403 (Cloudflare). Open one article in the **built-in browser**, then from `javascript_tool` run a same-origin `fetch('/<loc>/articles/20001256')` per locale (`fr-fr`, `fr-ca`, `es-es`, `es-419`, `de-de`, `pt-br`, `ja-jp`, `zh-tw` ... the `xx-yy` form) and read `<h1>`. The article id 20001256 is "Plugins in ChatGPT".
- **The app itself**: the help centre is evidence, the running app is proof. The owner switches macOS language and screenshots the vendor's Plugins page. Two such screenshots (Spanish, Claude and Codex) agreed with the docs and disagreed with each other.
- **Owner ruling, 13 Nov 2026: the help centre is trusted as the clue.** Where a vendor's localised article exists, its noun is used; no per-language app screenshots. The ChatGPT app's own language override (Settings ▸ General ▸ Language) made the per-language app check cheap; it was run once on 13 Nov and agreed with the docs everywhere. A Tart guest is no longer needed for ChatGPT.
- A search-engine summary of a localised help page is not the page; fetch it.

## Where this is wired

- `docs/glossary.md` row **plugin** (user text) points here.
- `.claude/agents/i18n-review.md` § 4 checks vendor-label strings against this table.
- `docs/adding-a-language.md` Step 5: a new language needs a row per vendor here before its Claude and ChatGPT tab strings are seeded.
- Keys: `desktop.mcpAgents.*` (Claude tab: `claudeDesktopHint`, `claudeReinstallHow`, `claudeDesktopPromptNote`; ChatGPT tab: `chatgptHint`, `chatgptReinstallHow`, `updateChatGPT`, `moveToApplications`; buttons and build lines are per tab: `claudeInstall` / `claudeReinstall` / `claudeUpdate` / `claudeBuild` / `claudeUnknownBuild` and `chatgptInstall` / `chatgptReinstall` / `chatgptUpdate` / `chatgptBuild`; no key is shared between the tabs). Where the two sources disagree on a form (nb: the help centre says Pluginer, the app's sidebar says Plugins) the help-centre title decides plural forms and the app decides the label.
