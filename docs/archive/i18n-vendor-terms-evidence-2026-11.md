> **Frozen history, 13-14 Nov 2026.** This is the research log the vendor-word guidance grew from. It is not guidance: the current rule is [../i18n-vendor-terms.md](../i18n-vendor-terms.md) and the current table is `bristlenose/locales/vendor-terms.json`. Kept so the evidence stays traceable; do not update it.

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

## Owner ruling, 14 Nov 2026: say what each vendor says, in each language

**The principle:** whichever agent a researcher uses, in whichever language they use it, Bristlenose's wording matches that vendor's own word for the thing. The vendors do not agree with each other (Spanish: Claude "Plugins", ChatGPT/Codex "Complementos") and that is fine: the truth is what each vendor's app and docs say, found by reading them (the evidence above), not by our preference or a shared translation. Where a vendor does not localise a language, its English word is what the user sees, so that is the word we use.

**Consequence for the open question:** the Claude tab uses Claude's word, which in the ten languages Claude does not localise (ca cs da fi nb nl pl sv tr uk) is the English "plugin". The current implementation follows the ruling, so nothing is reverted; the native-noun alternative previously recommended here is withdrawn.

## Why vendor words and not the platform glossary (measured 14 Nov 2026)

The glossary normally settles basic computer words (window, paste, zoom) from Apple's and Microsoft's own localisations so we do not surprise people with an ad-hoc translation. "Plugin" is the case where that source is silent. Measured in Apple's system tables (`/System/Library/{Frameworks,PrivateFrameworks}/**/*.loctable`, 3,275 files, all our languages): **no string translates the English "Plug-in" at all.** Apple's settled noun for this category is **Extension**: de *Erweiterung*, fr *Extension*, es *Extensión*, it *Estensione*, sv *Tillägg*, fi *Laajennus*, pl *Rozszerzenie*, ru *Расширение*, ja 機能拡張, ko 확장 프로그램, zh-Hant 延伸功能. That is the word Claude used before it renamed to Plugins, which is why the old copy read well. Apple's one "Add-on" string differs again (es *Extras*, pt-BR *Complemento*, tr *Eklenti*, nb *Tillegg*). Microsoft's corpus was not measured in this session. So for "plugin" there is no industry-settled word to borrow, and the only authority for what a researcher will see on screen is the vendor's own localisation, which is why we follow Claude and OpenAI per language and do not use a platform term.

**Order of sources, then:** (1) a basic platform word (window, menu, paste, zoom, Settings of macOS itself) takes the Apple/Microsoft glossary term; (2) a label that names another app's specific thing takes that app's own word in that language, from its app or help centre, recorded in `vendor-terms.json`; (3) a word of ours takes our own glossary term. Where (1) and (2) collide, the vendor's word wins inside that vendor's tab, because the user is looking at that vendor's screen.

## The mapping as data, and sweep findings (14 Nov 2026)

`bristlenose/locales/vendor-terms.json` carries the table above as data, and `tests/test_vendor_plugin_terms.py` fails when a vendor family's string loses that vendor's word or borrows the other vendor's. **Update the JSON and the table together, with evidence and the date.**

**Sweep: other strings that quote a vendor's UI (not yet checked per language):**
- `desktop.connectAgent.chatgptCodexHow`: "In ChatGPT: Settings → MCP servers → Add server …" is **stale** (checked 14 Nov 2026). OpenAI's help centre now puts everything under **Settings > Plugins** ("Connected apps in ChatGPT", "Connecting and managing app accounts"), and custom MCP server connections are described only for ChatGPT **Business and Enterprise/Edu on the web**, with admins/owners creating them ("Connecting custom MCP servers in ChatGPT", article 12584461). The real desktop app (13 Nov 2026) has Settings ▸ Integrations ▸ Plugins with tabs Plugins, Apps, MCP, Skills and an **Add** menu. **Opened 14 Nov 2026 (English UI, nothing chosen): Create plugin, Add a marketplace, Add MCP server, Record a skill.** So the real path is Settings ▸ Plugins ▸ Add ▸ Add MCP server. So the "MCP servers" settings page the string names probably no longer exists for a consumer, and the `~/.codex/config.toml` half is the route that still works (it is what Install Plugin… automates). **Interim fix applied 14 Nov 2026 (`c76371a6a`):** the string in all 21 locales now says only to add the entry to `~/.codex/config.toml`; the path comes back once the labels are read. History: the old path came from `docs/design-mcp-extension.md` §ChatGPT ("Settings → MCP servers → Add server", written weeks ago), and no earlier session or screenshot holds the Add labels per language (the 13 Nov per-language loops read the Plugins sidebar label and the Settings title only; only the user's Spanish and French screenshots show Add). **To restore the path, read those four labels per language** (the language dropdown in the ChatGPT app makes this quick), then word the path per language: Settings and Plugins are known in all 21 languages (the sidebar readings above), MCP stays Latin, but the localised labels of Add and Add MCP server are known only in es (Añadir) and fr (Ajouter) for the first. Until then a shorter honest string (the config.toml line only) is safer than a confidently wrong path.
- `desktop.mcpAgents.filesFoldersNote` and similar quote macOS labels: those follow the Apple loctable rule (`.claude/agents/i18n-review.md` § 6c), not this table.
- Miro, Figma, Zoom and Teams labels in `desktop.miro*`, the FigJam sheet and the cloud-import flows are the same class and have no per-language evidence yet.

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

## Appendix, 14 Nov 2026: the ChatGPT Add menu, read in all 21 languages (not used)

Read from the ChatGPT/Codex desktop app (Settings ▸ Plugins ▸ Add menu), one language at a time, so the stale `desktop.connectAgent.chatgptCodexHow` path ("Settings → MCP servers → Add server") could be restored. The owner ruled it out of scope (the sidebar word plus the help centre is the ground truth), so the string says only to add the entry to `~/.codex/config.toml`. Kept in case the path is ever wanted. Real path in English: Settings ▸ Plugins ▸ Add ▸ Add MCP server. Menu items: Create plugin, Add a marketplace, Add MCP server, Record a skill.

| Locale | Settings | Plugins page | Add | Add MCP server |
|---|---|---|---|---|
| en | Settings | Plugins | Add | Add MCP server |
| ca | Configuració | Connectors | Afegeix | Afegeix un servidor MCP |
| cs | Nastavení | Pluginy | Přidat | Přidat server MCP |
| da | Indstillinger | Plugins | Tilføj | Tilføj MCP-server |
| de | Einstellungen | Plugins | Hinzufügen | MCP-Server hinzufügen |
| es | Ajustes | Complementos | Añadir | Añadir servidor MCP |
| fi | Asetukset | Lisäosat | Lisää | Lisää MCP-palvelin |
| fr (France) | Paramètres | Plugins | Ajouter | Ajouter un serveur MCP |
| it | Impostazioni | Plugin | Aggiungi | Aggiungi server MCP |
| ja | 設定 | プラグイン | 追加 | MCP サーバーを追加 |
| ko | 설정 | 플러그인 | 추가 | MCP 서버 추가 |
| nb | Innstillinger | Pluginer | Legg til | Legg til MCP-server |
| nl | Instellingen | Plug-ins | Toevoegen | MCP-server toevoegen |
| pl | Ustawienia | Wtyczki | Dodaj | Dodaj serwer MCP |
| pt-BR | Configurações | Plugins | Adicionar | Adicionar servidor MCP |
| pt-PT | Definições | Plugins | Adicionar | Adicionar servidor MCP |
| ru | Настройки | Плагины | Добавить | Добавить сервер MCP |
| sv | Inställningar | Pluginer | Lägg till | Lägg till MCP-server |
| tr | Ayarlar | Eklentiler | Ekle | MCP sunucusu ekle |
| uk | Налаштування | Плагіни | Додати | Додати сервер MCP |
| zh-Hant (Taiwan) | 設定 | 外掛程式 | 新增 | 新增 MCP 伺服器 |

French Canada reads Plugiciels / Ajouter / Ajouter un serveur MCP.
