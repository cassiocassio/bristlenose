---
status: draft
last-trued: 2026-09-29
---

# Agent access on macOS 27 — the Files & Folders step

_Drafted 29 Sep 2026 for review. **Nothing here is built.** No code, locale or
manifest file has changed. This doc holds the measured facts, the proposed
copy for every surface (proxy, Settings pane, help page), and the per-locale
strings ready to paste once the English is settled. Mockup:
[`mockups/mcp-files-and-folders.html`](mockups/mcp-files-and-folders.html).
Help-page draft for the website repo:
[`drafts/connect-an-agent-macos27.md`](drafts/connect-an-agent-macos27.md)._

Parent docs: [`design-mcp-extension.md`](design-mcp-extension.md) (§3.5, §5b,
§5c) and [`design-mcp-server.md`](design-mcp-server.md). The ChatGPT half
depends on the Codex-plugin spike, now written up in
[`design-mcp-native-proxy.md`](design-mcp-native-proxy.md).

> **Later the same day (29 Sep 2026): a route that needs no Files & Folders
> step was measured.** A proxy signed by our team and launched as its own
> responsible process reads the container as Bristlenose itself, and macOS 27
> allows it without consulting TCC. It was proven end to end in ChatGPT, with no
> Node either. It uses private SPI, so it is an App Store question first. This
> doc stays the plan for the Node proxy that ships today, and the fallback for
> any channel where the native proxy cannot ship. See
> [`design-mcp-native-proxy.md`](design-mcp-native-proxy.md) §5–§6.

> **App Store verdict, 29 Sep 2026: this doc is the recovery path, not the
> primary route, on either channel.** The disclaimed native proxy can't ship
> on the Mac App Store: it calls a private symbol App Review has already cited
> under §2.5.1, and it is an unsandboxed executable, which the upload
> validator rejects. The recommended route for both channels, **measured on
> the host**, is:
> - the handshake moves into our **Team-ID-prefixed app group container**
>   (`Z56GZVA2QB.app.bristlenose`);
> - the proxy is a **sandboxed binary carrying that group**, with no inherit;
> - macOS lets it read the container even with Claude or Terminal as the
>   responsible process, and tccd is never consulted.
>
> Repeated with **Claude Desktop** as the parent on 29 Sep 2026 in a clean
> macOS 27 guest with SIP on: it passes (§1, measured #1). Not yet repeated
> with ChatGPT as the parent, and not yet through a TestFlight upload. So the Files & Folders flow and copy here
> stay needed for **(a)** today's Node `.mcpb` users, until the new proxy
> ships, and **(b)** permanently, as the recovery path if the group route
> fails on some host. Don't build a primary onboarding step around it if the
> group route ships: the `permission` state becomes rare, and the copy stays
> for when it happens. The full review is in the maintainer's private handoff
> notes; the public summary is `design-mcp-native-proxy.md` §6.

## 1. What changed underneath us

The extension finds Bristlenose by reading a handshake file inside our app
container (`~/Library/Containers/app.bristlenose/Data/Library/Application
Support/Bristlenose/mcp-handshake.json`). The reader is a Node process that the
agent app starts, so macOS attributes the read to **that app**. It is a read
into another developer team's container.

| | macOS 26 | macOS 27 |
|---|---|---|
| TCC service | `kTCCServiceSystemPolicyAppData` | `kTCCServiceSystemPolicyAppDataDetailed` |
| First read | a dialog: *"Claude" would like to access data from other apps* | **denied, no dialog** |
| Where the grant lives | answered in the dialog | System Settings ▸ Privacy & Security ▸ **Files & Folders** ▸ *(agent app)* ▸ **Bristlenose** |
| Measured | 1 Aug 2026, Claude Desktop (design-mcp-extension §5c) | 29 Sep 2026, ChatGPT (below) |

Apple's macOS 27 release note, verbatim: *"Accessing files in other developer
teams' app data containers and app group containers no longer prompts the user
for authorization; such accesses are denied by default and can be managed by
the user in Privacy & Security settings."* The boundary is the **Team ID**, so
moving the handshake into an app group does not help **while the reader is
another team's process** (Claude's or ChatGPT's Node). It does help when the
reader is **our own sandboxed binary carrying the group**. Then it's a
same-team read, which is the App Store session's measured route (banner
above).

### Measured, 29 Sep 2026 (this Mac, macOS 27.0, build 26A428)

- **ChatGPT, fresh.** Tool call returned the proxy's `permission` sentence. No
  dialog. tccd attributed the read to `com.openai.codex`
  (`ChatGPT.app/Contents/MacOS/ChatGPT`), service `…AppDataDetailed`,
  *"does not allow prompting; recording denied"*. Attribution is correct: the
  responsible process is the real app, not a helper.
- **The fix works.** Files & Folders ▸ expand **ChatGPT** ▸ switch
  **Bristlenose** on. The next tool call answered with real project data.
- **The deep link exists on 27.**
  `x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_FilesAndFolders`
  opens System Settings directly on Files & Folders (opened and screenshotted,
  29 Sep). The extension's Info.plist sets
  `allowsXAppleSystemPreferencesURLScheme`, and `Privacy_FilesAndFolders` is
  one of its anchors. There is also a `Privacy_AppContainer` anchor, not
  tested.
- **The pane's own header** reads *"Apps that appear here have requested
  access to files, folders and other app data. You can manage access at any
  time."* The list is alphabetical and long: ChatGPT and Claude sit under C,
  below the fold on a typical Mac.
- **The Darwin version is 27.0.0** (`uname -r`, and Node's `os.release()`).
  macOS 26 is Darwin 25, so the proxy can branch on `major >= 27`.
- **macOS has a notification string for this service**
  (`TCC.framework` `Localizable.loctable`): header *"Data Access Blocked"*,
  body *"“%@” tried to access your data from other apps and was blocked. You
  can manage this at any time in Files & Folders settings."*, button
  *"Manage"*. **We did not see it** during the ChatGPT test. **Later the same
  day it did appear**, for a Terminal read of the container (*"'Terminal'
  tried to access your data from other apps and was blocked…"*), so it is
  real, but whether it fires for every host is still unknown. The copy below
  mentions it only conditionally.
- **ChatGPT tools run only in Work mode** (and the Codex workspace). In Chat,
  the `@Bristlenose` chip is offered but the model cannot call the tool.

### Not measured, and the copy depends on them

1. ~~**A new Claude Desktop install on 27.**~~ **Measured 29 Sep 2026: silently
   denied, same as ChatGPT.** A clean macOS 27.0 (26A428) guest under tart, with
   **SIP enabled** (`csrutil status` checked beside every result), Claude
   2.9939.2 never granted anything, Bristlenose 0.31.5 serving with Agent Access
   on. The first question through the shipped Node `.mcpb` got the proxy's
   `permission` sentence: stderr `handshake read permission-blocked (TCC) …
   EPERM`, and tccd *"kTCCServiceSystemPolicyAppDataDetailed does not allow
   prompting; recording denied"*, subject `com.anthropic.claudefordesktop`.
   **No dialog.** Files & Folders then listed **Claude**. Two things came out
   of the same run:
   - **Claude runs a Node `.mcpb` inside its own `Claude Helper (Plugin)`
     utility process** (`node.mojom.NodeService`), so Claude is the
     responsible process and the read is cross-team. That's why it's denied.
   - **Claude runs a `type: binary` `.mcpb` through its own
     `Claude.app/Contents/Helpers/disclaimer`**, so the binary is its own
     responsible process. A binary signed by our team then reads our
     container as a same-team read, and tccd is never asked: the native
     helper and both app-group probes, sandboxed and not, all read with the
     Files & Folders switch **off**. So on the Claude channel, a binary
     proxy removes this step with no private SPI
     ([`design-mcp-native-proxy.md`](design-mcp-native-proxy.md)).
   A first run was **invalid**: Cirrus `-base`/`-xcode` images ship with SIP
   off, and there the Node read "succeeded". Only `-vanilla` keeps SIP on.
   Not yet measured: turning the switch on and asking again under Claude.
   The fix is measured for ChatGPT only. Evidence and runbook are on the test
   drive, in the maintainer's notes.
2. ~~**Does the agent app appear in Files & Folders *before* its first denied
   read?**~~ **Settled 29 Sep 2026, by the pane's own contract: no.** Files &
   Folders lists only apps that have requested access (*"Apps that appear here
   have requested access…"*), not every app on the system. The proxy reads the
   handshake only inside a tool call, so the first question is the first
   attempt, and no *agent app ▸ Bristlenose* row can exist before it. The
   copy's order (ask, get blocked, turn it on, ask again) is the only order
   there is.
3. ~~**Whether a carried-over macOS 26 grant shows up in Files & Folders** under
   Claude.~~ **Answered 29 Sep 2026: it does.** Files & Folders ▸ **Claude**
   lists **Bristlenose: on**, beside Desktop and Downloads. So an existing
   user revokes it in the same place a new user grants it.
4. **ChatGPT's localised labels for "Work" and "Chat".** Its strings are
   compiled into the Electron bundle, not shipped as `.lproj` catalogs. The
   draft keeps the English labels in every locale until someone reads them off
   a localised ChatGPT.

## 2. What is wrong today

| Surface | What it says | Wrong because |
|---|---|---|
| Proxy `MSG.permission` (`desktop/mcpb/server/index.js:76`) | *"macOS is asking whether Claude may access… click Allow on the macOS dialog"* | No dialog on 27. It also names Claude, but the same proxy would run under ChatGPT |
| `desktop.mcpAgents.claudeDesktopPromptNote` × 21 | *"macOS asks once… Click Allow"* | Pre-announces a dialog that never comes on 27 |
| Website `connect-an-agent.md` § Claude Desktop | *"Expect one more prompt… Click **Allow**"* | Same |
| design-mcp-extension §5c | *"prompt-once-then-silent is the shipped reality"* | A macOS 26 result (trued in this pass) |
| design-mcp-server §1, design-mcp-extension §3.5 | *"OpenAI Plugins require a public HTTPS endpoint… one-click is Claude-only"* | That rule is for the public directory. A local marketplace installs a stdio plugin that runs our unmodified proxy (trued in this pass) |

## 3. The proxy message

The proxy's sentences are **tool results the model relays**. They stay English
by design (design-mcp-extension §5d): the model paraphrases them into the
conversation's language. So the facts have to survive rewording: name the
host, give the path, and say "ask again".

**Two inputs, neither of them client detection:**

- **The host is declared by the package, not detected.** Each package sets
  `BRISTLENOSE_MCP_HOST` in its own manifest: the `.mcpb` sets `"Claude"`,
  the Codex plugin's `.mcp.json` sets `"ChatGPT"`. The proxy interpolates the
  value. When it's missing (a hand-rolled config, or a future package that
  forgets it), a neutral phrase stands in. One proxy source, as decided on
  29 Sep 2026. The value must match the row label in Files & Folders, which is
  the app's display name: measured `ChatGPT` (bundle `com.openai.codex`) and
  `Claude`.
- **The OS version is a platform fact**, read from `os.release()`. Knowing
  which macOS we run on is not knowing the client.

Both manifests accept an `env` block. MCPB's `mcp_config.env` is in the spec;
**that Codex's `.mcp.json` passes `env` through is unverified**. Check it in the
spike before relying on it. If it doesn't, the neutral fallback is what ChatGPT
users see, and it still works.

### Proposed wording

```js
// The package declares its host (manifest env); never detected. Must equal the
// app's row label in Files & Folders — its display name.
const HOST = (process.env.BRISTLENOSE_MCP_HOST || "").trim();
// macOS 27 (Darwin 27) denies cross-team container reads without a dialog;
// macOS 26 is Darwin 25. A platform fact, not a client fact.
const SILENT_TCC = process.platform === "darwin" && parseInt(os.release(), 10) >= 27;

permission: SILENT_TCC
  ? "macOS has blocked " + (HOST || "this agent app") +
    " from reading Bristlenose. On this version of macOS there is no prompt — " +
    "the access stays off until the person turns it on. Tell the person to open " +
    "System Settings ▸ Privacy & Security ▸ Files & Folders, expand " +
    (HOST || "the app they are asking from") + " in the list, and turn on Bristlenose, then ask " +
    "again. Nothing in Bristlenose needs changing. " + GROUNDING
  : "macOS is asking whether " + (HOST || "this app") + " may access data from " +
    "other apps — that permission is how this extension finds Bristlenose. Tell " +
    "the person to click Allow on the macOS dialog (or grant it in System " +
    "Settings ▸ Privacy & Security), then ask again. " + GROUNDING,
```

Why each clause is there:

- *"there is no prompt"* stops the model from telling the person to look for a
  dialog, which is the most likely paraphrase of a permissions error.
- *"Nothing in Bristlenose needs changing"* heads off "reinstall the
  extension" and "turn on Agent Access", both wrong here. It is the same
  discipline as `authFailed` versus `closed`.
- The Settings path uses macOS's English pane names. The model translates them
  if the chat isn't in English. Localised pane names are for our own pane (§4),
  where we control the rendering.

`tests/test_mcpb_proxy.py` already extracts the tool JSON. Two cases would pin
this: `BRISTLENOSE_MCP_HOST=ChatGPT` yields "ChatGPT" twice, and unset yields
no product name at all. Faking the Darwin version means injecting `os.release`.
The proxy has no seam for that today, so it is a small refactor.

## 4. Settings ▸ MCP Agents

### Claude Desktop tab

On macOS ≤ 26, nothing changes: `claudeDesktopPromptNote` keeps
pre-announcing the dialog, and it is still true there.

On macOS 27 the note below the install row becomes a **step with a button**.
It sits in the same slot, for the same reason (§5c): it happens on the first
*question*, not on install.

> The first time you ask a question, macOS blocks Claude from reading
> Bristlenose, without asking. To allow it, open System Settings ▸ Privacy &
> Security ▸ Files & Folders, expand Claude and turn on Bristlenose — then ask
> again.
>
> **[Open Files & Folders]**

- **Why a button now, when the 26 note had none.** On 26 the remedy was a
  dialog that came to the researcher. On 27 they have to go somewhere, and
  it's four levels deep in an app we don't own. The deep link is verified, and
  it's the one piece of this we can make one click. It's a bordered, regular
  button, not prominent: the pane's single filled button stays **Install
  Extension…**. No ellipsis: nothing further happens in our app, and Apple's
  own "Open System Settings" buttons carry none.
- **Why keep the full path in the sentence** when there's a button: the
  researcher still has to find **Claude** in a long list, expand it, and find
  **Bristlenose** under it. The path is also what they'll see in the
  notification's wording, if it appears, and it's what the help page says.
- **Still the `info` register**, never a caution triangle. Nothing has gone
  wrong: this is how macOS 27 works, and it's a once-per-agent-app step.
- **Locale values quote macOS's own pane names** (Apple's
  `SecurityPrivacyExtension` loctables, and `System Settings.app`'s
  `CFBundleName`), the same technique as `claudeDesktopPromptNote` (§5c).
  Recognition is the mechanism: the words in our pane match the words in
  System Settings a moment later.

Implementation shape, for the record rather than for building now:
`ProcessInfo.processInfo.isOperatingSystemAtLeast(OperatingSystemVersion(majorVersion: 27, …))`
picks the branch, and `NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:…")!)`
runs the button. Opening a URL is not blocked by the sandbox. **One new key
takes `{{app}}`** so both tabs share it, and the ChatGPT tab reuses the whole
note.

### ChatGPT & Codex tab

Be precise about which path needs the step, because today's tab doesn't:

| Path | Reads the container? | Files & Folders step? |
|---|---|---|
| **Today**: TOML stanza / *Add server* form, URL + bearer over HTTP | No. The client connects to `127.0.0.1` directly | **None.** It still carries the rotating port (§3.5a) |
| **If the Codex plugin ships**: stdio plugin running our proxy | Yes, the handshake | **Yes**, naming ChatGPT |

So there are two drafts, and which one ships depends on the spike:

**(a) Today's tab + one line.** The Work-mode fact applies to the TOML path
too. That's inferred, not measured: the spike measured the plugin in Chat
versus Work, and there's no reason the config route would differ. Add under
the copy button:

> In ChatGPT, ask in Work mode — Bristlenose’s tools aren’t available in Chat.

**(b) The plugin era.** The tab takes the Claude Desktop tab's shape: hint,
install row, Files & Folders step naming ChatGPT, plus the Work line. The
install gesture itself is **not designed here**. The spike has since measured
that a one-click install works from the `marketplace.json` **file** path
(`codex://plugins/<name>?marketplacePath=…`), per
[`design-mcp-native-proxy.md`](design-mcp-native-proxy.md). Two known
blockers to name before this ships:

- **Node is not supplied.** ChatGPT spawns the proxy with the login-shell
  PATH, and **measured with a control, ChatGPT does not supply Node to
  plugins.** On the test Mac `node` resolved to Homebrew's. The `.mcpb` doesn't
  have this problem, because Claude Desktop ships its own Node for extensions.
  A Node proxy under ChatGPT works only for researchers who happen to have
  Node. No copy can fix that, and the tab mustn't imply otherwise. The native
  proxy (`design-mcp-native-proxy.md`) removes this blocker and the Files &
  Folders step together, if its private SPI can ship.
- **The TOML path doesn't go away.** It's the one ChatGPT route with no
  permission step and no Node dependency. Keep it as the fallback, as the
  Generic MCP tab is for everything else.

### Can Bristlenose tell that the grant is missing?

**No, and v1 shouldn't try.** We can't read another app's TCC state. *Know the
protocol, never the client.* What we *can* observe is weaker than it looks:

- A blocked proxy never reaches the serve. It can't read the handshake, so it
  doesn't know the port. So from the app's side, a denial looks exactly like
  *nobody has asked yet*. Absence is ambiguous.
- `serveManager.agentProxyVersion` does prove that *some* proxy got through.
  But with two host apps, one getting through says nothing about the other.
  Collapsing the note after the first contact would hide it from the
  researcher who installs the second agent next week, which is precisely the
  person who needs it.
- The proxy *could* send its declared host with the health probe. It's
  package-declared, so it wouldn't be detection. It would, though, start a
  per-host state machine to answer a question that a note answers for free.
  **Recommendation: don't.** Revisit only if cohort researchers miss the note.

So on macOS 27 the note is **always shown** under each install row. It costs
two lines of footnote, it's true every time it's read, and the button makes it
actionable. **That holds only while the Node `.mcpb` is the shipped proxy.** If
the app-group proxy ships (banner at the top), a fresh install no longer
meets the block, and an always-on note would pre-announce a step most
researchers never see. Then the copy moves out of the pane's primary flow
and lives in the in-chat `permission` message and on the help page, where
it's read only when it's true.

The in-chat message (§3) is the other half, and it is **the only channel that
reaches the moment of failure**. The pane is read before; the tool result is
read during. Both are needed.

### Revocation, now that there are two switches

Files & Folders ▸ *(agent app)* ▸ Bristlenose is **all or nothing for that
app**: it lets the extension find the handshake at all. **Agent Access**, per
project in Bristlenose, is still what decides which studies an agent can read.
The help page should say this plainly. Otherwise a researcher who wants to
stop sharing one study goes to System Settings and cuts off every study
instead, or thinks they have when they've only reached one app.

## 5. Windows

What the repo actually supports, checked 29 Sep 2026:

- **The Mac app, the `.mcpb` extension, the container handshake and TCC are
  macOS-only.** None of this doc applies on Windows.
- **On Windows Bristlenose is a command-line tool**: `pipx install
  'bristlenose[serve]'` (website `install.md`). The README lists Windows as
  *"the pipeline works but hasn't been widely tested"*. CI runs on
  `ubuntu-latest` and `macos-latest` only (`.github/workflows/ci.yml:175`). The
  Windows port proper (Scoop, GPU probe) is parked
  (`design-windows-port.md`).
- **The agent path there** is the CLI's: with the `mcp` extra, `bristlenose
  serve` prints the MCP address and an `Authorization` header
  (`_print_mcp_connect`, `cli.py:1712`). Port 8150 is stable and the token
  changes on every restart. There's no container, no handshake file and no
  permission step. An agent connects over HTTP to `127.0.0.1`.

Gaps. These are for the maintainer, not for the help page:

1. **The MCP endpoint has never been run on Windows** by anything we own: no
   CI, no recorded manual test. The help page must not claim it works there.
2. **The connect page's `pip install 'bristlenose[mcp]'` is wrong for a pipx
   install** on any OS: it installs into whichever Python `pip` names, not
   pipx's venv. The pipx form is `pipx install 'bristlenose[serve,mcp]'` (or
   `pipx inject bristlenose mcp`). On Windows, PowerShell takes the single
   quotes and `cmd.exe` doesn't.
3. **Which Windows agents take a URL + header is unverified.** The page's
   Claude Desktop "command line" block (`url` + `headers` in
   `claude_desktop_config.json`) and the ChatGPT TOML stanza are the Mac
   dialects. Nobody has checked them against the Windows builds of those apps.
   Don't write Windows-specific agent steps until someone has.

The help-page draft carries one honest sentence and no steps (§7).

## 6. Truing done in this pass

- `design-mcp-extension.md`: §3.5's "OpenAI Plugins need public HTTPS" and
  §5c's "prompt-once-then-silent" each get a dated correction banner. The
  Status table's "that shipped 3 Aug 2026" note gains a macOS 27 caveat, and
  there's a changelog line.
- `design-mcp-server.md` §1: the same OpenAI correction, and a changelog line.

**Owed when this is built** (not touched now): `desktop/CLAUDE.md:623`
(describes the shipped pre-announce), the proxy comment at `index.js:74`, the
`MCPAgentsSettingsView.swift:976` comment block, the website page, and the
CHANGELOG entry. The README's 0.23.x changelog line stays as it is: it's
history.

## 7. Open decisions for the maintainer

1. ~~**Settle the English** of the three strings in §8.~~ **Settled 29 Sep
   2026: the English v1 in §8 stands as drafted.** The 20 translations are
   pasted in one pass when this is built (21 full locales, not `zh-Hant-HK`).
2. ~~**Run the Claude-on-27 test.**~~ **Done 29 Sep 2026: Claude is silently
   blocked too** (§1, #1), so the Claude tab's note does say "blocks". New
   decision this opens: a `type: binary` `.mcpb` makes the step unnecessary on
   the Claude channel, because Claude disclaims binary servers. If that ships,
   the Claude tab's note falls to the recovery-path role (§4).
3. **ChatGPT plugin: ship or not.** Draft (a) is safe to ship on its own.
   Draft (b) waits for the install gesture and the Node question.
4. **Website deploy.** The help-page draft replaces a paragraph that is
   already false for every new macOS 27 user.

## 8. Strings — proposed keys, all 21 full locales

Pane names are lifted from macOS 27.0 (26A428): `System Settings.app`
`InfoPlist.loctable` `CFBundleName` (soft hyphens stripped from de/da/nb),
`SecurityPrivacyExtension.appex` `InfoPlist.loctable` `CFBundleDisplayName`
("Privacy & Security") and `Localizable.loctable` `FILE_ACCESS_COMBINED`
("Files & Folders"). Apple codes via `scripts/apple-locale-map.json`.

| ours | System Settings | Privacy & Security | Files & Folders |
|---|---|---|---|
| en | System Settings | Privacy & Security | Files & Folders |
| es | Ajustes del Sistema | Privacidad y seguridad | Archivos y carpetas |
| ca | Configuració del Sistema | Privacitat i seguretat | Arxius i carpetes |
| ja | システム設定 | プライバシーとセキュリティ | ファイルとフォルダ |
| fr | Réglages Système | Confidentialité et sécurité | Fichiers et dossiers |
| de | Systemeinstellungen | Datenschutz & Sicherheit | Dateien & Ordner |
| ko | 시스템 설정 | 개인정보 보호 및 보안 | 파일 및 폴더 |
| cs | Nastavení systému | Soukromí a zabezpečení | Soubory a složky |
| it | Impostazioni di Sistema | Privacy e sicurezza | File e cartelle |
| pl | Ustawienia systemowe | Prywatność i ochrona | Pliki i foldery |
| ru | Системные настройки | Конфиденциальность и безопасность | Файлы и папки |
| uk | Системні параметри | Приватність і безпека | Файли та папки |
| da | Systemindstillinger | Anonymitet & sikkerhed | Arkiver & mapper |
| sv | Systeminställningar | Integritet och säkerhet | Filer och mappar |
| nb | Systeminnstillinger | Personvern og sikkerhet | Filer og mapper |
| tr | Sistem Ayarları | Gizlilik ve Güvenlik | Dosyalar ve Klasörler |
| nl | Systeeminstellingen | Privacy en beveiliging | Bestanden en mappen |
| fi | Järjestelmäasetukset | Tietosuoja ja suojaus | Tiedostot ja kansiot |
| pt-BR | Ajustes do Sistema | Privacidade e Segurança | Arquivos e Pastas |
| pt-PT | Definições | Privacidade e segurança | Ficheiros e pastas |
| zh-Hant | 系統設定 | 隱私權與安全性 | 檔案和檔案夾 |

**`{{app}}` is always a product name** ("Claude", "ChatGPT"). The
translations keep it in the nominative by putting a head noun in front of it
where the grammar would otherwise inflect it (cs *aplikaci {{app}}*, pl
*aplikacji {{app}}*, fi *sovellusta {{app}}*, tr *{{app}} uygulamasının*, ca
*l'app {{app}}*, ko *을(를)*).

### `desktop.mcpAgents.filesFoldersNote` (macOS 27+, both tabs)

| | |
|---|---|
| en | The first time you ask a question, macOS blocks {{app}} from reading Bristlenose, without asking. To allow it, open System Settings ▸ Privacy & Security ▸ Files & Folders, expand {{app}} and turn on Bristlenose — then ask again. |
| es | La primera vez que hagas una pregunta, macOS impedirá que {{app}} lea Bristlenose, sin preguntar. Para permitirlo, abre Ajustes del Sistema ▸ Privacidad y seguridad ▸ Archivos y carpetas, despliega {{app}} y activa Bristlenose; luego vuelve a preguntar. |
| ca | La primera vegada que facis una pregunta, el macOS impedirà que l'app {{app}} llegeixi el Bristlenose, sense preguntar-ho. Per permetre-ho, obre Configuració del Sistema ▸ Privacitat i seguretat ▸ Arxius i carpetes, desplega l'app {{app}} i activa el Bristlenose; després torna a preguntar. |
| ja | 最初に質問したとき、macOSは確認なしで{{app}}によるBristlenoseの読み取りをブロックします。許可するには、「システム設定」▸「プライバシーとセキュリティ」▸「ファイルとフォルダ」を開き、{{app}}を展開してBristlenoseをオンにしてから、もう一度質問してください。 |
| fr | À la première question, macOS empêche {{app}} de lire Bristlenose, sans rien demander. Pour l’autoriser, ouvrez Réglages Système ▸ Confidentialité et sécurité ▸ Fichiers et dossiers, développez {{app}} et activez Bristlenose, puis posez à nouveau la question. |
| de | Bei der ersten Frage blockiert macOS den Zugriff von {{app}} auf Bristlenose, ohne nachzufragen. Zum Erlauben Systemeinstellungen ▸ Datenschutz & Sicherheit ▸ Dateien & Ordner öffnen, {{app}} aufklappen und Bristlenose aktivieren — dann erneut fragen. |
| ko | 처음 질문할 때 macOS는 확인 없이 {{app}}의 Bristlenose 읽기를 차단합니다. 허용하려면 시스템 설정 ▸ 개인정보 보호 및 보안 ▸ 파일 및 폴더를 열고 {{app}}을(를) 펼친 다음 Bristlenose를 켜십시오. 그런 다음 다시 질문하십시오. |
| cs | Při první otázce macOS bez dotazu zablokuje aplikaci {{app}} přístup k Bristlenose. Chcete-li to povolit, otevřete Nastavení systému ▸ Soukromí a zabezpečení ▸ Soubory a složky, rozbalte položku {{app}} a zapněte Bristlenose. Pak se zeptejte znovu. |
| it | Alla prima domanda, macOS impedisce a {{app}} di leggere Bristlenose, senza chiedere. Per consentirlo, apri Impostazioni di Sistema ▸ Privacy e sicurezza ▸ File e cartelle, espandi {{app}} e attiva Bristlenose, poi fai di nuovo la domanda. |
| pl | Przy pierwszym pytaniu macOS, nie prosząc o zgodę, zablokuje aplikacji {{app}} dostęp do Bristlenose. Aby na to pozwolić, otwórz Ustawienia systemowe ▸ Prywatność i ochrona ▸ Pliki i foldery, rozwiń pozycję {{app}} i włącz Bristlenose, a potem zapytaj ponownie. |
| ru | При первом вопросе macOS без запроса заблокирует приложению {{app}} доступ к Bristlenose. Чтобы разрешить его, откройте «Системные настройки» ▸ «Конфиденциальность и безопасность» ▸ «Файлы и папки», разверните {{app}} и включите Bristlenose, затем задайте вопрос снова. |
| uk | Під час першого запитання macOS без запиту заблокує програмі {{app}} доступ до Bristlenose. Щоб дозволити його, відкрийте «Системні параметри» ▸ «Приватність і безпека» ▸ «Файли та папки», розгорніть {{app}} і ввімкніть Bristlenose, а тоді поставте запитання знову. |
| da | Første gang du stiller et spørgsmål, blokerer macOS {{app}} i at læse Bristlenose uden at spørge. Du giver adgang ved at åbne Systemindstillinger ▸ Anonymitet & sikkerhed ▸ Arkiver & mapper, udvide {{app}} og slå Bristlenose til — og derefter spørge igen. |
| sv | Första gången du ställer en fråga blockerar macOS {{app}} från att läsa Bristlenose, utan att fråga. Du tillåter det genom att öppna Systeminställningar ▸ Integritet och säkerhet ▸ Filer och mappar, expandera {{app}} och slå på Bristlenose — ställ sedan frågan igen. |
| nb | Første gang du stiller et spørsmål, hindrer macOS {{app}} i å lese Bristlenose, uten å spørre. For å tillate det åpner du Systeminnstillinger ▸ Personvern og sikkerhet ▸ Filer og mapper, utvider {{app}} og slår på Bristlenose — og spør deretter på nytt. |
| tr | İlk soruyu sorduğunuzda macOS, sormadan {{app}} uygulamasının Bristlenose’u okumasını engeller. İzin vermek için Sistem Ayarları ▸ Gizlilik ve Güvenlik ▸ Dosyalar ve Klasörler’i açın, {{app}} öğesini genişletin ve Bristlenose’u etkinleştirin; ardından soruyu yeniden sorun. |
| nl | De eerste keer dat je een vraag stelt, blokkeert macOS zonder te vragen dat {{app}} Bristlenose leest. Om dat toe te staan, open je Systeeminstellingen ▸ Privacy en beveiliging ▸ Bestanden en mappen, klap je {{app}} uit en zet je Bristlenose aan. Stel daarna je vraag opnieuw. |
| fi | Kun esität ensimmäisen kysymyksen, macOS estää kysymättä sovellusta {{app}} lukemasta Bristlenosea. Salli se avaamalla Järjestelmäasetukset ▸ Tietosuoja ja suojaus ▸ Tiedostot ja kansiot, laajentamalla kohta {{app}} ja laittamalla Bristlenose päälle. Kysy sitten uudelleen. |
| pt-BR | Na primeira pergunta, o macOS impede que o {{app}} leia o Bristlenose, sem perguntar. Para permitir, abra Ajustes do Sistema ▸ Privacidade e Segurança ▸ Arquivos e Pastas, expanda {{app}} e ative o Bristlenose. Depois pergunte de novo. |
| pt-PT | Na primeira pergunta, o macOS impede que o {{app}} leia o Bristlenose, sem perguntar. Para o permitir, abra Definições ▸ Privacidade e segurança ▸ Ficheiros e pastas, expanda {{app}} e ative o Bristlenose. Depois volte a perguntar. |
| zh-Hant | 第一次提問時，macOS 會直接封鎖 {{app}} 讀取 Bristlenose，不會先詢問。若要允許，請打開「系統設定」▸「隱私權與安全性」▸「檔案和檔案夾」，展開 {{app}} 並開啟 Bristlenose，然後再問一次。 |

### `desktop.mcpAgents.openFilesFolders` (button, macOS 27+)

| | |
|---|---|
| en | Open Files & Folders |
| es | Abrir Archivos y carpetas |
| ca | Obre Arxius i carpetes |
| ja | 「ファイルとフォルダ」を開く |
| fr | Ouvrir Fichiers et dossiers |
| de | Dateien & Ordner öffnen |
| ko | 파일 및 폴더 열기 |
| cs | Otevřít Soubory a složky |
| it | Apri File e cartelle |
| pl | Otwórz Pliki i foldery |
| ru | Открыть «Файлы и папки» |
| uk | Відкрити «Файли та папки» |
| da | Åbn Arkiver & mapper |
| sv | Öppna Filer och mappar |
| nb | Åpne Filer og mapper |
| tr | Dosyalar ve Klasörler’i Aç |
| nl | Open Bestanden en mappen |
| fi | Avaa Tiedostot ja kansiot |
| pt-BR | Abrir Arquivos e Pastas |
| pt-PT | Abrir Ficheiros e pastas |
| zh-Hant | 打開「檔案和檔案夾」 |

### `desktop.mcpAgents.chatgptWorkNote` (ChatGPT tab, any macOS)

"Work" and "Chat" are ChatGPT's own labels, and they stay in English until
someone reads ChatGPT's localised labels (§1, unmeasured #4).

| | |
|---|---|
| en | In ChatGPT, ask in Work mode — Bristlenose’s tools aren’t available in Chat. |
| es | En ChatGPT, pregunta en el modo Work: las herramientas de Bristlenose no están disponibles en Chat. |
| ca | A ChatGPT, pregunta en el mode Work: les eines del Bristlenose no estan disponibles a Chat. |
| ja | ChatGPTでは「Work」モードで質問してください。Bristlenoseのツールは「Chat」では使えません。 |
| fr | Dans ChatGPT, posez vos questions en mode Work : les outils de Bristlenose ne sont pas disponibles dans Chat. |
| de | In ChatGPT im Modus „Work“ fragen — in „Chat“ sind die Werkzeuge von Bristlenose nicht verfügbar. |
| ko | ChatGPT에서는 Work 모드에서 질문하십시오. Bristlenose 도구는 Chat에서 사용할 수 없습니다. |
| cs | V ChatGPT se ptejte v režimu Work — v režimu Chat nejsou nástroje Bristlenose k dispozici. |
| it | In ChatGPT, fai le domande in modalità Work: gli strumenti di Bristlenose non sono disponibili in Chat. |
| pl | W ChatGPT zadawaj pytania w trybie Work — narzędzia Bristlenose nie są dostępne w trybie Chat. |
| ru | В ChatGPT задавайте вопросы в режиме Work — в режиме Chat инструменты Bristlenose недоступны. |
| uk | У ChatGPT ставте запитання в режимі Work — у режимі Chat інструменти Bristlenose недоступні. |
| da | Stil dine spørgsmål i ChatGPT i tilstanden Work — Bristlenoses værktøjer er ikke tilgængelige i Chat. |
| sv | Ställ frågorna i ChatGPT i läget Work — Bristlenoses verktyg är inte tillgängliga i Chat. |
| nb | Still spørsmålene i ChatGPT i Work-modus — verktøyene til Bristlenose er ikke tilgjengelige i Chat. |
| tr | ChatGPT’de sorularınızı Work modunda sorun; Bristlenose araçları Chat’te kullanılamaz. |
| nl | Stel je vragen in ChatGPT in de modus Work — de tools van Bristlenose zijn niet beschikbaar in Chat. |
| fi | Kysy ChatGPT:ssä Work-tilassa — Bristlenosen työkalut eivät ole käytettävissä Chat-tilassa. |
| pt-BR | No ChatGPT, pergunte no modo Work — as ferramentas do Bristlenose não ficam disponíveis no Chat. |
| pt-PT | No ChatGPT, pergunte no modo Work — as ferramentas do Bristlenose não estão disponíveis no Chat. |
| zh-Hant | 在 ChatGPT 中請使用「Work」模式提問——Bristlenose 的工具無法在「Chat」中使用。 |

`claudeDesktopPromptNote` is kept unchanged for macOS ≤ 26. No ChatGPT
counterpart is drafted for 26: whether ChatGPT gets the 26-era dialog is
untested, so there's nothing to quote yet.
