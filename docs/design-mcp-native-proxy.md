---
status: current — built on main (P1–P5), not yet released
last-trued: 2026-09-29
trued-against: HEAD@main on 2026-09-29 (after bb50067c)
---

# ChatGPT plugin, macOS 27, and the native proxy

_Measured on 29 Sep 2026 on one Mac (macOS 27.0, build 26A428; ChatGPT desktop
26.924, bundle id `com.openai.codex`, free account). Production code:
[`desktop/mcp-helper/`](../desktop/mcp-helper/) (helper and its build script),
[`desktop/scripts/check-mcp-helper.sh`](../desktop/scripts/check-mcp-helper.sh)
(the gate), `ChatGPTPluginInstaller.swift` and `NativeExtensionPackage.swift` in
the app. The spike it came from:
[`experiments/mcp-native-proxy/`](../experiments/mcp-native-proxy/). Every claim
is labelled **measured**, **inferred** or **unverified**. The raw session record
is in the maintainer's private handoff notes, kept outside the public tree._

Related docs:
- [`design-mcp-extension.md`](design-mcp-extension.md) — the shipped Claude Desktop `.mcpb`
- [`design-mcp-server.md`](design-mcp-server.md) — the `/mcp` endpoint
- [`design-mcp-files-and-folders.md`](design-mcp-files-and-folders.md) — the System Settings route; drafted the same day

> **Truing note (29 Sep 2026, evening).** Sections 1–6.8 are the day's
> measurements, kept as the record. Where one was later overtaken by what was
> built, it says so in place. The current state is TL;DR item 7, §6.9 (the
> plan and each phase's status), §6.10 (break tests) and §6.11 (review notes).

## TL;DR

1. **ChatGPT desktop can install a local Bristlenose plugin in one click**, with
   no marketplace registered first:
   `codex://plugins/bristlenose?marketplacePath=<absolute path to marketplace.json>`.
   *Measured.*
2. **ChatGPT does not supply Node.** A plugin whose command is `node` is simply
   missing on a Mac without its own Node. *Measured, with a control.*
3. **macOS 27 silently denies an agent app's read of our container** (no
   dialog), and **the decision is made on the *responsible* process, not on who
   signed the binary doing the read.** *Measured* for ChatGPT, and for a fresh
   Claude Desktop through today's shipped Node `.mcpb`.
4. **A team-signed binary launched as its own responsible process reads the
   container with no grant at all.** The read never reaches TCC. *Measured.*
5. **So a 128 KB native proxy, signed by our team, that relaunches itself
   disclaimed removes both problems** (the first route found; §6.1 rejects it
   for the App Store, and item 6 is the one built): no Node, and no Files & Folders step.
   Proven end to end in ChatGPT with a real study question, and in a fresh
   Claude Desktop with its Files & Folders switch off. *Measured.* Claude
   already launches binary servers disclaimed (§4.4).
6. **The disclaim trick cannot ship on the Mac App Store** (private SPI App
   Review has rejected by name, and an unsandboxed helper in the MAS bundle
   fails upload). **A public-API route works instead:** write the handshake into
   a Team-ID-prefixed app group, and ship the proxy **sandboxed** with that group.
   Such a proxy reads the group container with no grant, with ChatGPT, Claude
   Code or Terminal responsible (§6). *Measured.* **Apple's validator
   (`altool --validate-app`) accepts** the shipped app repackaged with that
   sandboxed helper and the group (§6.5), and that build answers real questions
   inside ChatGPT (§6.2). **A real upload (build 3907) processed as VALID,
   App Store eligible** (§6.7). Human App Review remains. The native port
   carries all of the Node proxy's states (§4.3, pinned by `tests/test_mcp_helper.py`).
7. **Built on main, 29 Sep 2026 (not yet released).** D1–D9 decided (§6.9). The
   app writes the handshake into the team group (P1); a sandboxed helper,
   `bristlenose-mcp`, is built into every signed build (P2); the ChatGPT tab
   installs it as a plugin in one click and the Claude tab installs it as a
   runtime `.mcpb`, with no Files & Folders step (P3–P5). ChatGPT end to end is
   proven on this Mac, and a 34-case break harness plus seven live ChatGPT
   attacks found and fixed two defects (§6.10). Still to run: Claude through the
   native package, a TestFlight build, the 15/26 guests, and App Review (§6.8).

## 1. The ChatGPT plugin channel

### 1.1 The package

A Codex/ChatGPT plugin is a folder:

```
marketplace/
  .agents/plugins/marketplace.json      ← {"name", "plugins": [{"name","source":{"source":"local","path":"./plugins/<name>"}, …}]}
  plugins/<name>/
    .codex-plugin/plugin.json           ← name, version, description, interface, "mcpServers": "./.mcp.json"
    .mcp.json                           ← {"mcpServers": {"<id>": {"type":"stdio","command":…,"args":[…],"cwd":"./","env":{…}}}}
    bin/…                               ← anything else the server needs
```

- **Paths resolve against the installed plugin folder when `"cwd": "./"`.** This
  covers both `args` and a relative `command` (`"./bin/bristlenose-mcp"`
  resolved). There is **no** `${PLUGIN_ROOT}` or `${CLAUDE_PLUGIN_ROOT}`
  expansion, and no such environment variable is set (Codex CLI 0.158). *Measured.*
- **`env` in `.mcp.json` replaces variables for the child**, `PATH` included,
  and the command is looked up on that `PATH`. That is how the no-Node test in
  §2 works. *Measured.*
- **Install copies the plugin** to `~/.codex/plugins/cache/<marketplace>/<name>/<version>/`.
  Exec bits and the code signature survive, and no quarantine xattr is added
  (only `com.apple.provenance`). *Measured.*

### 1.2 One-click install

ChatGPT registers the `codex://` scheme. Its link parser (in `app.asar`,
`bootstrap-*.js`) recognises two plugin links. *Measured by reading the code,
then exercising both.*

| Link | Needs the marketplace registered? | Result |
|---|---|---|
| `codex://plugins/install/<name>?marketplace=<name>` | yes — by name | installs from a known marketplace |
| `codex://plugins/<name>?marketplacePath=<absolute path>[&mode=share]` | **no** | opens the plugin page with **Install plugin** |

- **The path must be the `marketplace.json` file, not the folder.** With the
  folder, the page spins on a skeleton forever. The Codex binary's own help
  string says `marketplacePath=<absolute marketplace.json path>`. URL-encode it.
- The link works with ChatGPT not running: it cold-starts on the plugin page.
- Installing this way **does not add the marketplace to `~/.codex/config.toml`**.
  Only the `[plugins."<name>@<marketplace>"] enabled = true` entry appears.

**Consequence:** the Bristlenose app can carry the marketplace inside its own
bundle, and an "Add to ChatGPT" button just opens that link. *Inferred* for a
path inside a signed app bundle (tested with a path in a working tree).

### 1.3 Where the tools run

- **Work mode and the Codex workspace only.** In ordinary Chat, the
  `@Bristlenose` chip is offered in the picker, but the model reports it can't
  access the plugin, and no process starts. *Measured.* OpenAI's plugins page
  says plugins work "in Chat or Work"; that is not what this build does.
- **The same holds for a server added in `~/.codex/config.toml`**
  (`[mcp_servers.bristlenose]` with `url` and `http_headers`, exactly as
  Settings ▸ MCP Agents ▸ ChatGPT & Codex gives it). In Chat the model said the
  tool *"is not available in the tools exposed to this chat"*. In Work the same
  entry answered with a real quote. *Measured*, 29 Sep 2026, with the spike
  plugin uninstalled so only the config entry could supply the tools. So
  "ask in Work mode" is true for both routes.
- **ChatGPT asks per tool** ("Allow the bristlenose MCP server to run tool
  X?" — Always allow / Deny / Allow once). "Always allow" on one tool did not
  cover the next. *Measured.* After marking every tool
  `annotations.readOnlyHint: true`, six tool calls ran with **no approval card
  at all**. *Inferred* that the annotation is the cause; nothing else changed.
  The config-file route talks to `bristlenose serve`'s own `/mcp/`, whose tools
  were **not** annotated at the time, and there ChatGPT asked per tool again
  (*measured*). So annotating the server's tools in
  `bristlenose/server/mcp_server.py` should fix that route too. They were
  annotated on 29 Sep 2026 (`0bcb1963`). **Not re-measured** over this route
  yet.
- **Re-measured on the plugin route with the production helper, 29 Sep 2026
  (evening).** Installed from Settings ▸ MCP Agents ▸ Install Plugin…, a
  Work-mode question ran `list_projects`, `get_project_overview`,
  `get_framework`, `get_signals` and `search_quotes` with **no approval card**
  (the maintainer's observation; ChatGPT's `logs_2.sqlite` shows each call
  answered, `handshake ok`, from the group copy). The whole chain: one click
  in Bristlenose, **Install plugin** in ChatGPT, ask. No Node, no Files &
  Folders, no approval.
- **The model may reach for ChatGPT's own Computer Use instead** ("Allow
  ChatGPT to use Bristlenose?" — screenshots of the app) when a question names
  the app. Naming the tools in the question avoided it. *Measured, once.*
- **The account's default model can 404.** On a free account, `gpt-5.5`
  returned *"does not exist or you do not have access"*; `5.6 Terra` worked.
  No subscription was needed for anything here. *Measured.*
- **Debugging:** Codex records each MCP server's stderr in
  `~/.codex/logs_2.sqlite` (table `logs`, lines tagged
  `MCP server stderr (<command>)`). Copy the file before querying it; it is
  open under WAL.

### 1.4 The browser

chatgpt.com cannot start a local process, so a local stdio plugin is
desktop-only. The web can reach only remote HTTPS MCP servers. *Unverified*
(from OpenAI's docs and third-party summaries, not tested).

## 2. Node is not provided

| Run | Manifest | ChatGPT | Result |
|---|---|---|---|
| test | `command: node`, `env.PATH` without Node | restarted | tool missing; no process started |
| control | `command: node`, no `env` | restarted | proxy started; tools worked |

*Measured.* ChatGPT does keep a Node inside its own downloaded runtime
(`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`)
and one inside the app (`Contents/Resources/cua_node`), but neither is on the
plugin's `PATH`. On this Mac the plugin only worked because Homebrew's Node was
on the login-shell `PATH` that Codex passes down. OpenAI's own Sites plugin
fails the same way (openai/codex#31897).

**Trap hit while measuring:** killing a plugin's server process without
restarting ChatGPT leaves the plugin dead until the next restart. The first
no-Node run looked like a pass for that reason and had to be redone with a
restart and a control.

Claude Desktop is different: a `.mcpb` extension of `type: node` runs inside
Claude's own utility process, `Claude Helper (Plugin).app`
(`--utility-sub-type=node.mojom.NodeService`), whose parent is Claude. It is not
a separate `node` binary, and no process carries our `index.js` in its argv, so
`ps | grep index.js` finds nothing under Claude. Its container reads are
therefore Claude's. *Measured in a macOS 27 guest; that fact does not depend
on SIP.*

## 3. macOS 27: who is allowed to read our container

### 3.1 The change

Apple's macOS 27 release note: *"Accessing files in other developer teams' app
data containers and app group containers no longer prompts the user for
authorization; such accesses are denied by default and can be managed by the
user in Privacy & Security settings."* The TCC service is
`kTCCServiceSystemPolicyAppDataDetailed`. On macOS 26 the equivalent read raised
the *"would like to access data from other apps"* dialog (1 Aug 2026,
design-mcp-extension §5c). [`design-mcp-files-and-folders.md`](design-mcp-files-and-folders.md)
§1 has the table.

### 3.2 The rule that matters: responsibility, not signature

Every result below is from a fresh Terminal (no grant for Bristlenose), reading
the live handshake file. *Measured*, each with the tccd attribution.

| Reader | Launched | TCC subject | Result |
|---|---|---|---|
| `/bin/cat` | normally | `com.apple.Terminal` | denied, *"does not allow prompting for unentitled binaries"* |
| team-signed (Z56GZVA2QB) probe | normally | `com.apple.Terminal` | **denied** |
| ad-hoc probe | disclaimed | the probe's own path | denied |
| **team-signed probe** | **disclaimed** | — | **READ ok; no tccd request at all** |

So:
- **The subject of the check is the responsible process.** Signing the
  reading binary with our own team does nothing while a host app is
  responsible for it.
- **A process that is its own responsible process and carries our Team ID is
  treated as Bristlenose reading its own container**, and the access is allowed
  before TCC is consulted.
- `responsibility_spawnattrs_setdisclaim(&attr, 1)` on a `posix_spawnattr_t` is
  what makes the child its own responsible process. iTerm2 and Chromium use it
  (*unverified* here), and Claude Desktop ships its own `Helpers/disclaimer`,
  which launches Claude Code this way (visible in `ps`). Terminal does **not**:
  the table above shows Terminal as the responsible process for its children.
  It is **private SPI**: not in the public SDK headers, declared here with
  `@_silgen_name`.

### 3.3 Other things measured about the new rule

- **The same rule applied inside ChatGPT.** The Node proxy's read was
  attributed to `com.openai.codex` (the real app, not a helper): *"does not
  allow prompting; recording denied"*. After Files & Folders ▸ ChatGPT ▸
  Bristlenose was switched on, it worked.
- **A denial is cached per responsible process.** After Terminal's first
  denied read, later reads by other binaries in the same Terminal were denied
  with no tccd request of their own. Test the case you care about first, in a
  fresh host.
- **The "Data Access Blocked" notification does appear.** It showed for
  Terminal (*"'Terminal' tried to access your data from other apps and was
  blocked. You can manage this at any time in Files & Folders settings."*). It
  was not noticed for ChatGPT. One public write-up says no notification
  appears; that is wrong for at least this case.
- **macOS 26 grants migrate.** On this Mac, Files & Folders ▸ **Claude** lists
  **Bristlenose: on** alongside Desktop and Downloads, from the macOS 26 dialog
  grant. A new Claude install on 27 has no such entry, so it starts denied:
  *measured* in a clean, SIP-on macOS 27 virtual machine through the shipped
  Node `.mcpb` (tccd subject `com.anthropic.claudefordesktop`, no dialog;
  §4.4). **Switching Files & Folders ▸ Claude ▸ Bristlenose on recovers it**:
  tccd logged the grant as a `Modify` event, and the next question returned
  real data (same guest, SIP on). The recovery path is measured for both
  Claude and ChatGPT.
- **The pane's deep link works:**
  `x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_FilesAndFolders`.
- **Bare command-line binaries get one row each, with no icon.** The six
  "claude" rows on this Mac match the six Claude Code binaries installed (three
  CLI versions, three managed by the Claude app). A binary without a bundle ID
  cannot be granted there (Apple's known issue).

### 3.4 Measurement traps

- **Claude Code's own sandbox refuses the read first.** Running a probe from
  an agent's Bash tool gave `EPERM` with *no* tccd request: that was the agent's
  seatbelt sandbox, not macOS privacy. Probe from Terminal via a `.command`
  file (`open -a Terminal x.command`), which is a clean host with its own
  identity.
- **A test VM with SIP off measures nothing here.** Cirrus Labs' Tart
  `macos-*-base` and `-xcode` images disable System Integrity Protection; only
  `-vanilla` keeps it on. In a SIP-off macOS 27 guest, Claude Desktop's first
  read through the shipped Node `.mcpb` returned data with no dialog, no TCC
  row and no tccd line, which is meaningless. Check `csrutil status` in any
  guest before believing a privacy result from it (29 Sep 2026).
- **Always read tccd, and read the attribution.** `/usr/bin/log show --start
  "<time>" --predicate 'process == "tccd"' --style compact`, then follow one
  `msgID` through `AUTHREQ_ATTRIBUTION` (responsible / accessing) →
  `AUTHREQ_SUBJECT` → `AUTHREQ_RESULT`. A denial that never appears in tccd was
  refused by something else. `log` alone is a zsh builtin.

## 4. The native proxy

### 4.1 Design

> **Superseded as the shipping design, 29 Sep 2026** — the disclaimed spike
> below is rejected for the App Store (§6.1). What ships is the sandboxed,
> app-group helper in `desktop/mcp-helper/` (§6.2, §6.9); it keeps step 2's
> contract and step 3's host label, and drops step 1 (no `posix_spawn`, no
> `responsibility_*`, gated by `check-mcp-helper.sh`).

`experiments/mcp-native-proxy/main.swift`, 128 KB, signed Developer ID +
hardened runtime, identifier `app.bristlenose.mcp-proxy`:

1. **First start:** `posix_spawn` itself with responsibility disclaimed and
   `BN_MCP_DISCLAIMED=1`, share stdio, wait, exit with the child's status.
   Stdin EOF ends the child if the host kills the parent.
2. **Child:** the Node proxy's contract. Re-read the handshake on every call;
   probe `/api/health` unauthenticated and require the handshake's
   `instance_id` before sending the bearer; POST `tools/call` to `/mcp/`
   (JSON or SSE); answer `list_projects` locally from the handshake.
3. **Host named by the package:** `BRISTLENOSE_MCP_HOST` in the manifest's
   `env` (for example `ChatGPT`), used in the permission sentence. The proxy
   never detects its client.

Plugin manifest used:

```json
{"mcpServers": {"bristlenose": {"type": "stdio", "command": "./bin/bristlenose-mcp", "args": [], "cwd": "./",
  "env": {"BRISTLENOSE_MCP_HOST": "ChatGPT", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}}}}
```

### 4.2 Results

- **Terminal, no grant:** initialize, `tools/list` (5), `list_projects`,
  `get_project_overview`, `search_quotes` all returned real data from the
  running app. *Measured.*
- **ChatGPT Work, installed with the one-click link, no Node on `PATH`:**
  `list_projects` → `get_project_overview` → `search_quotes` ×4, then a cited
  answer: *"Okay, there's no way I'm going to collect. Collect from locker. How
  can they get the bed in a locker?" — p3 (02:54)*. tccd logged **no request
  from the proxy**; every app-data check in that window was ChatGPT's own.
  *Measured.*
- The one thing not yet done: the same run with ChatGPT's own Files &
  Folders switch off. tccd already shows the switch was not consulted.

### 4.3 Parity with the Node proxy

**Ported, and checked against the Node proxy.** *Measured*, 29 Sep 2026. Both
proxies were fed the same handshake and the same requests against a live
`bristlenose serve`. The native port now carries:
- the scope fingerprint on every result (same arithmetic);
- `notifications/tools/list_changed` on the offline→ready edge, only after
  `notifications/initialized`;
- the contract/outdated check and the 404 "built without agent support" branch;
- the `unhealthy` / `not-bristlenose` / `stale-instance` probe verdicts, with
  fail-closed instance matching;
- schema-1 handshakes, normalised like the Node proxy's;
- the Node proxy's message table, word for word.

| Case | Node vs native |
|---|---|
| `list_projects` (content and scope `ca848ff1`) | identical |
| `search_quotes`, real data | identical content and scope |
| unknown `project` key | identical *"not open … Currently readable: …"* |
| `list_changed` after an unknown-project call, then a good one | both emit it |
| no handshake | identical *"isn't open"* |
| stale `instance_id` | identical *"isn't open"* (fail closed) |
| wrong bearer | identical *"refused this connection's stored credential"* |
| dead port | identical *"isn't open"* |

**Still different, by design:** the permission sentence. The native build names
the host, and the sandboxed build says to reinstall rather than pointing at
Files & Folders (§6.2). The tool list is generated from the Node proxy's
`BN-TOOLS-JSON` block and compiled in. A shipped version should keep
`tests/test_mcpb_proxy.py`'s drift gate pointed at whichever becomes canonical.

**Trap when comparing:** the Node proxy exits on stdin EOF before its pending
fetches resolve, so piping a fixed request file into it answers only the
synchronous requests. Hold stdin open (`(cat req.jsonl; sleep 6) | node …`).
The native proxy handles requests sequentially, so it has no such race.

### 4.4 It serves Claude too

**Measured, 29 Sep 2026**, in a clean macOS 27.0 (26A428) virtual machine with
**SIP enabled**, Claude 2.9939.2, and Bristlenose 0.31.5 serving a smoke
project:

| Run | Extension | Files & Folders ▸ Claude ▸ Bristlenose | Result |
|---|---|---|---|
| baseline | shipped Node `.mcpb` | off (never granted) | proxy: *"handshake read permission-blocked (TCC) … EPERM"*; tccd: `AppDataDetailed` *"does not allow prompting; recording denied"*, subject `com.anthropic.claudefordesktop`; **no dialog** |
| native | the same tools as a `type: binary` `.mcpb` (this spike) | **still off** | **real data** (Smoke Test: 1 session, 78 s, 2 sections, 1 theme); proxy logged *"relaunched disclaimed"* and *"handshake ok"*; **no `AppDataDetailed` request** from the proxy |

The only tccd line naming the proxy was a `kTCCServiceDeveloperTool`
preflight from `syspolicyd`: Gatekeeper's first-launch check on the parent
before the relaunch, not a container read.

**Claude already disclaims binary servers.** Claude's log says *"Using basic
execution for extension Bristlenose: server.type is binary (not
node/python/uv)"*. The process chain was Claude → `Claude.app/Contents/Helpers/disclaimer
--pgroup -- …/server/bristlenose-mcp` (team Q6L2SF6YDW) → our binary → our
own disclaimed child. So under Claude a `type: binary` server is its own
responsible process before our code runs. **So under Claude a team-signed
binary needs no private SPI at all.** *Measured* in the same guest: a probe
signed by our team, unsandboxed, with no relaunch and no SPI, launched by
Claude through `disclaimer` (responsible = itself), listed our data container
(*"DATA-CONTAINER LIST ok (3)"*), with no `AppDataDetailed` request to tccd.
Not yet repeated with the real proxy in no-relaunch mode (`BN_MCP_DISCLAIMED=1`
set in the manifest). ChatGPT launches servers differently (§1.1), so there
the self-disclaim is still needed, or the app-group route (§6), which needs no
SPI on either host.

Node extensions are the opposite case: Claude runs them inside its own utility
process (§2), so their reads are Claude's, and are denied on a new install.

## 5. How the pieces fit

The middle column is the rejected spike (§6.1), kept for comparison; the right
column is what is built.

| Problem | Node proxy today | Native, disclaimed (§4) | Native, sandboxed + app group (§6) |
|---|---|---|---|
| ChatGPT one-click install | works (`marketplacePath` link) | works | works (same link) |
| Mac without Node (ChatGPT) | **fails** | works | works |
| Claude Desktop runtime | Claude's own Node | binary server | binary server |
| macOS 27, new install | **silently denied** until Files & Folders is switched on | allowed, same-team | allowed, same-team group |
| macOS 27, carried-over grant | works | works | works |
| Mac App Store build | ships today | **rejected** (§6) | validated and processed as VALID (§6.5–§6.7); human review remains |
| Developer ID `.dmg` | ships today | ship with risk | works (same mechanism as MAS) |

[`design-mcp-files-and-folders.md`](design-mcp-files-and-folders.md) is the
right plan for the Node proxy that ships today, and stays the recovery path on
any channel where the native proxy is not installed.

## 6. The App Store question

_Verdict from a research pass with the `app-store-police` agent, 29 Sep 2026.
Its full record, with draft review notes, is in the maintainer's private
handoff notes, kept outside the public tree._

### 6.1 The disclaimed helper: rejected on the Mac App Store

Two independent reasons, either sufficient:

1. **Guideline 2.5.1, private API.** `responsibility_spawnattrs_setdisclaim` is
   exported by `libquarantine` and re-exported through `libSystem.B.tbd`, with
   no public header. App Review **named this exact symbol** when it rejected Qt
   6.4.0 apps in Oct–Nov 2022, and those builds only weak-imported it and never
   called it. Hiding it behind `dlsym` would be concealment under §2.3.1. Of 51
   Mac App Store apps on the test Mac, only Xcode references it. Every
   third-party user found (Claude's `Helpers/disclaimer`, Codex, Chrome/CEF,
   Electron ShipIt, iTerm2) ships Developer ID.
2. **An unsandboxed executable in the MAS bundle is rejected at upload.** Our
   own bundled ffmpeg/ffprobe got "App sandbox not enabled" on 14 Jul 2026. A
   *sandboxed* disclaimed helper gains nothing, because the sandbox denies
   another bundle's data container first.

**Developer ID only: ship with risk.** *Not taken:* the `.dmg` ships the same
sandboxed app-group helper as the store (D1, §6.9), so the contingency below
was never built. If kept as a contingency there:
- resolve the symbol with `dlsym`, with a fallback;
- take the re-exec path from `_NSGetExecutablePath`, not `argv[0]` (`argv[0]`
  turns the binary into a disclaim trampoline for anything);
- compile out `BRISTLENOSE_DEV_MCP_HANDSHAKE` in release;
- add a `check-pkg-shippable` gate on `_responsibility_` so the symbol can
  never reach a MAS build.

### 6.2 The route that works on both channels: a team-prefixed app group

**The proxy ships sandboxed, with no `inherit`, carrying a Team-ID-prefixed
application group (`Z56GZVA2QB.app.bristlenose…`).** Such a process can list,
read and write that group's container with no grant and no tccd request.
Measured with all four launching apps: Claude Code, Terminal, ChatGPT and
Claude Desktop. In the first three a *foreign* app was the responsible process.
Under Claude Desktop the probe was its own responsible process, because Claude
disclaims binary servers, so that row shows the route works with Claude rather
than surviving a foreign responsible process. Apple's app-groups documentation
gives the reason: macOS checks that the accessing code signature contains the
same Developer Team ID.

Measured on 29 Sep 2026 with a probe group, `Z56GZVA2QB.app.bristlenose.batest`:

| Probe | Responsible process | Group container |
|---|---|---|
| team-signed, sandboxed, with the group | Claude Code (team Q6L2SF6YDW), even with a cached denial for our containers | **list, write, read ok** |
| same | fresh Terminal | **ok** |
| same | **ChatGPT.app** (probe run as a ChatGPT plugin's server) | **list, write, read, delete ok** |
| same | **Claude Desktop**, launched through its `Helpers/disclaimer`, so the responsible process is the probe itself (clean macOS 27 guest, SIP on, Files & Folders off) | **mkdir, write, read, unlink ok**; its read of our *data* container was hidden by its own sandboxing (*"The folder 'Bristlenose' doesn't exist"*), as expected |
| team-signed, unsandboxed, no group | Claude Desktop (via `disclaimer`, responsible = the probe) | **ok, and it read our data container too**: a same-team reader, because Claude disclaims binary servers (§4.4) |
| team-signed, unsandboxed, no group | ChatGPT.app | denied |
| team-signed, **unsandboxed but with** the group | fresh Terminal | denied: the entitlement only counts when sandboxed (*inferred* from one run) |
| ad-hoc, sandboxed, with the group | Claude Code | denied (not our Team ID) |
| team-signed, sandboxed, no group | Claude Code | denied |

Two gotchas found on the way:
- **A sandboxed bare Mach-O needs an embedded Info.plist**
  (`-sectcreate __TEXT __info_plist`). Without one it traps at launch with exit
  133 (*"Info.plist … has no value for kCFBundleIdentifierKey"*), a different
  failure from the `inherit` exit 133 this codebase has seen before.
- `taskgated-helper` logs *"Disallowing"* for the missing provisioning profile,
  but access is granted anyway. Watch it on point releases.

A helper `.app` launched through LaunchServices *is* its own responsible
process and reads the data container. On the Mac App Store it must be sandboxed
too, so it adds nothing over the group route.

Probe sources: `experiments/mcp-group-probe/` (the C probe and a one-tool
`group_probe` MCP server), beside this spike's `experiments/mcp-native-proxy/`.

**The Files & Folders switch does not reach the group container.** *Measured.*
At 10:08, under ChatGPT, the unsandboxed team-signed control was refused on the
group container while **ChatGPT ▸ Bristlenose was switched on**: tccd shows the
switch turned on at 09:19 and no change after. And tccd logged **no**
`AppDataDetailed` request for that refusal, only a Full Disk Access preflight.
The group rule is enforced below TCC, and no user-facing switch reaches it.
So if the group route ever fails, the recovery is a handshake copy in the
*data* container, read by an unsandboxed proxy (Node, or the Developer ID
binary), which Files & Folders can unlock. The sandboxed proxy cannot use that
fallback: its own sandbox hides the data container.

**The sandboxed proxy works end to end.** *Measured*, 29 Sep 2026: the
`GROUP_VARIANT` build of `experiments/mcp-native-proxy/main.swift` is sandboxed,
with `network.client`, the group `Z56GZVA2QB.app.bristlenose` and an embedded
Info.plist, and has no private symbol (checked by `build.sh`). The handshake was
seeded into the group through its own `--seed` mode, standing in for the host.
Under a fresh Terminal it then answered `tools/list` (5, marked `readOnlyHint`),
`list_projects` and `search_quotes` with real data from a live `bristlenose
serve`. It resolves the group with
`FileManager.containerURL(forSecurityApplicationGroupIdentifier:)`, because a
sandboxed `$HOME` is the proxy's own container.

**And inside ChatGPT.** *Measured*, 11:09. The same sandboxed build was
installed as spike plugin v0.0.6 through the one-click link, into a running
ChatGPT. A new Work thread asked about the locker and got *"How can they get
the bed in a locker?" — p3*, through `list_projects` then `search_quotes`,
with no approval cards. Each server was a single process (no relaunch), and
tccd logged nothing naming the proxy. So the App Store shape (sandboxed, group
only, no SPI, no Node) is proven end to end in a real host.

### 6.3 Options, ranked

| # | Option | MAS review | Claude + ChatGPT |
|---|---|---|---|
| 1 | **Team-prefixed group container + sandboxed native proxy** | **passes Apple's validator and upload processing** (§6.5–§6.7); human review remains | both |
| 2 | Mach IPC rendezvous under the group prefix (`CFMessagePort` / XPC). No token on disk; the long-run hardening against macOS 27's tightening on files created by other teams | ship with risk | both |
| 3 | `SMAppService` agent with `MachServices` | as 2, plus the background-item notice (§2.4.5(iii)) | both |
| 4 | LaunchServices helper `.app` | useless on MAS (must be sandboxed); needs a relay | — |
| 5 | Files & Folders on MAS only | ships, but gives ChatGPT nothing on MAS (no Node, and a sandboxed Mach-O can't read the data container) | Claude only |
| 6 | Handshake outside the container (temporary exception or bookmark) | two exceptions to justify; the token becomes readable by any same-user process | — |
| 7 | Bonjour, a fixed port, or the keychain | none of these moves the token; the keychain needs a profile the bare proxy can't carry | — |

### 6.4 Recommended: one mechanism on both channels

> **Built, 29 Sep 2026.** This is the shape that landed (§6.9 P1–P5). The draft
> host half is applied (`MCPHandshake.writeBoth`, D4); the proxy is
> `desktop/mcp-helper/`; the Claude package is built at click time by
> `NativeExtensionPackage.swift`. Bullets below are the recommendation as
> written; where the build differs, §6.9 says so.

- **Host:** add `Z56GZVA2QB.app.bristlenose` to the application groups in
  **both** entitlements files, and write the handshake there while Agent Access
  is on.
  - The Mac App Store profile already authorises it. *Verified:* the embedded
    "Bristlenose Mac App Store" profile lists application groups
    `group.app.bristlenose` and `Z56GZVA2QB.*`.
  - Developer ID: **today's `.dmg` profile does not list the group** (the
    Xcode-minted "Mac Team Direct" profile authorises only
    `keychain-access-groups`). *Measured* 29 Sep 2026 on macOS 27: a
    Developer-ID app carrying that profile and claiming the team group ran
    and read and wrote the group. But taskgated logged *"Unsatisfied
    entitlements: com.apple.security.application-groups … Disallowing"*,
    the same lenient path the probes hit. Re-export so Xcode mints a profile
    that authorises the group, and test on macOS 15 and 26, before relying on
    it.
  - A ready-to-apply draft of the host half is in
    `docs/drafts/native-proxy-group-handshake/`. It writes and removes both
    copies, reads the team group from the process's own entitlements, and
    updates both entitlements files and the split test. Not applied; its
    README lists what was and wasn't verified.
  - Keep the data-container copy while the Node `.mcpb` exists.
  - `tests/test_entitlements_split.py` must change deliberately: its claim
    that the `.dmg` carries no app group holds only for `group.`-prefixed
    groups.
- **Proxy:** sandboxed with no `inherit`, `network.client`, the group, an
  embedded Info.plist, tools compiled in, and no `responsibility_*` symbols
  (gated). Ship it loose in the app bundle so Apple re-signs it.
- **Claude:** build the `.mcpb` at runtime from the re-signed binary. A Mach-O
  inside a zip is never re-signed, so whether a pre-built one runs is
  *unverified*.
- **Why one binary is enough.** Under Claude, *any* team-signed binary already
  works, with no group and no SPI, because Claude disclaims binary servers
  (§4.4). The group is what ChatGPT needs, and what lets a *sandboxed* binary
  read anything at all. So a single sandboxed binary carrying the group serves
  both hosts.
- **Recovery path.** Keep writing the data-container copy too. When the group
  read fails, the proxy can only tell the person to reinstall the extension or
  update Bristlenose: the sandboxed proxy can't reach the data container, and
  Files & Folders doesn't reach the group (§6.2). The unsandboxed Node
  `.mcpb` stays the path where Files & Folders is the remedy.

### 6.5 Apple's validator accepts it

**`altool --validate-app`: no issues.** *Measured*, 29 Sep 2026, 11:05. The
test package was the shipped 0.31.5 App Store archive (build 3906), repackaged:
- the `GROUP_VARIANT` proxy, signed Apple Distribution, added at
  `Contents/Helpers/bristlenose-mcp`;
- `Z56GZVA2QB.app.bristlenose` added to the host's application groups, beside
  `group.app.bristlenose`;
- the build number raised to 3907, the app re-signed Apple Distribution with
  hardened runtime, and the package signed with the Mac installer certificate.

`desktop/scripts/check-pkg-shippable.sh` passed every check, including
*"nested app-sandbox: 5 Mach-Os, all sandboxed"*, which is the rule behind the
14 Jul rejection. Apple's validator then reported no issues. The gate's one
failure was the expected *"pkg is 3907, working tree is 3906"*: a
release-freshness check that a deliberately renumbered spike build is meant to
fail.

What this does and does not settle:
- **Settled:** App Store Connect's server-side validation accepts a nested,
  sandboxed, non-`inherit` tool carrying its own team-prefixed group, and the
  host carrying that group next to `group.app.bristlenose`. No build was
  delivered and no build number was spent.
- **Not settled:** upload *processing* can raise issues that validation does
  not (they arrive as ITMS emails), and human App Review (§2.5.2,
  §2.4.5(ii)) happens only when a build is submitted for review. Internal
  TestFlight skips human review.

### 6.6 Trap: the helper's own container remembers its first signer

*Measured*, 29 Sep 2026. A sandboxed helper gets its own container
(`~/Library/Containers/<helper id>/Data`), and macOS records the signing
identity that created it. The Developer-ID build of `app.bristlenose.mcp-proxy`
ran first. When the Apple Distribution build with the same identifier then
ran, it **hung at launch** in `_libsecinit_appsandbox`, waiting on `secinitd`,
which logged *"binary identity <Z56GZVA2QB/app.bristlenose.mcp-proxy;
signer:enterprise> not in ACL for container …"*. The same binary under a fresh
identifier ran normally and served real data. So an Apple Distribution-signed
tool does run outside the App Store when it isn't quarantined, and the hang was
purely the container's signer ACL.

**And it blocked the build that *is* trusted, too, for a while.** `uncd`, the
daemon that shows system alert dialogs, started at the second of the hang. For
the next few minutes the **Developer-ID** build, whose signer is in the ACL and
which had run all morning, also hung at the same `_libsecinit_appsandbox` wait
on every launch, with no new `secinitd` line. The maintainer saw **no dialog**
on screen. By about 11:35 `uncd` had exited and the Developer-ID build ran
normally again, with nothing answered. So the block is real but was
self-clearing here, and what `uncd` was doing (a dialog on another Space, one
that timed out, or none) is unknown. Either way, one mismatched launch can
stall the helper for every host for minutes, which a host experiences as a dead
server.

To a host, a helper that hangs at launch is a server that never answers. The
Developer-ID `.dmg` and the Mac App Store build (re-signed by Apple) have
different signers, so a person who has run both would hit it. **Give the
helper a different bundle identifier per channel.** (The names chosen are
`app.bristlenose.mcp`, `app.bristlenose.mcp.devid` and, for Debug,
`app.bristlenose.mcp.dev`; see D1 and P0.2b below.) The group container is
unaffected: in the same log, `containermanagerd` approved it (*"Requestor's
signature allows it to access a TCC-protected group container"*).

### 6.7 And App Store Connect processes it

**Uploaded and processed: `BUILD-STATUS: VALID`, `BUILD-AUDIENCE-TYPE:
APP_STORE_ELIGIBLE`.** *Measured*, 29 Sep 2026, 11:55–11:59. The same package
as §6.5 (0.31.5 build **3907**, the shipped app with the sandboxed group proxy
at `Contents/Helpers/bristlenose-mcp` and the team group in the host's
entitlements) went up with `altool --upload-package --wait`: 702 MB in 2.8
minutes, delivery `1541e4c2-5336-4bf5-8e8b-da16c08a373e`. Processing reported
no issues and set a TestFlight expiry of 28 Dec 2026. A second, independent
`altool --build-status` call agreed.

Build number 3907 is now spent. That's harmless: build numbers are the git
commit count at bump time, and `main` is past 3940. The upload went round
`upload-testflight.sh`, whose gate refuses a package whose build number
differs from the working tree's (3907 against 3906), by design and with no
bypass. `altool` was called directly with the same flags.

What this settles and what it doesn't:
- **Settled:** App Store Connect's automated pipeline, both validation and
  upload processing, accepts a nested, sandboxed, non-`inherit` helper carrying
  its own Team-ID-prefixed group, next to a host carrying
  `group.app.bristlenose` and the team group. No ITMS issue was raised.
- **Not settled:** human App Review. Internal TestFlight skips it; it happens
  only on submission for review (external TestFlight or the store), where
  §2.5.2 / §2.4.5(ii), "installs code into other apps", is the question to
  prepare notes for. Also unsettled: whether Apple's re-signing keeps the
  helper's team group intact. Install build 3907 from TestFlight and read the
  helper's entitlements with `codesign -d --entitlements -` to find out.

**Installed and read, 29 Sep 2026 (P0.2).** TestFlight put 3907 at `/Applications/Bristlenose 2.app`
(an older user-owned `Bristlenose.app` was in the way), and the helper was read from disk without being
launched:

| Binary | Signer | Entitlements after Apple's re-sign |
|---|---|---|
| `Helpers/bristlenose-mcp` | TestFlight Beta Distribution; DR `anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.25.1] and identifier "app.bristlenose.mcp-proxy"` | `app-sandbox`, `network.client`, `application-groups: [Z56GZVA2QB.app.bristlenose]`, plus Apple's `beta-reports-active`. No `inherit`. Info.plist bound (5 entries). No quarantine xattr |
| `Resources/ffmpeg` (control) | TestFlight Beta Distribution | `app-sandbox`, `inherit`, `beta-reports-active` |
| `MacOS/Bristlenose` | TestFlight Beta Distribution | both groups, `application-identifier`, `team-identifier`, keychain group |

So Apple keeps what the helper needs. What it changes is the **signer**: TestFlight builds carry a
TestFlight-only certificate, distinct from the App Store's, from the local Apple Distribution one and from
Developer ID. That makes four signer classes, not two, and the store helper id meets two of them on a
tester's Mac (TestFlight, then the App Store). Whether that transition trips the §6.6 container trap is
**unmeasured**. Main apps survive it routinely, but they carry `application-identifier`, and the helper
doesn't. A local proxy for it: create the helper's container under an Apple Development signature, then
launch an Apple Distribution one with the same id (two Apple-anchored leaves, like TestFlight and the
store). If it hangs, the TestFlight→store move probably does too.

**P0.2b, measured 29 Sep 2026: what the helper's container remembers.** A sandboxed probe with a fresh
id, signed Apple Development, then Apple Distribution, then Apple Development again, reading the team
group each time:

| Launch | Signer (secinitd's category) | Result |
|---|---|---|
| 1 | Apple Development (`development`) | read ok, 0 s; secinitd *"initializing owners for container … `signer:development`"* |
| 2 | Apple Distribution, local (`enterprise`) | killed at 90 s; secinitd *"binary identity … `signer:enterprise` not in ACL for container … `[{teamIdentifier, validationCategory: development, signingIdentifier}]`; prompting"* |
| 3 | Apple Development again | also hung 90 s, while the first prompt was still pending |

So the container's owner list holds **team + signing identifier + validation category**, not a
certificate hash. A renewed certificate of the same kind should therefore not trip it. A different
*kind* does, and the "hang" is secinitd waiting on a permission alert, shown via UserNotificationCenter
(running during the test), which a helper started by ChatGPT or Claude has no good way to surface.
The container can't be deleted from Terminal (`Operation not permitted`).

What that means for the plan:
- **`.dmg` (`developer_id`) vs store:** different ids (D1). Fine.
- **TestFlight → App Store** for one tester: Apple DTS says an App Store/TestFlight swap
  "shouldn't trigger this alert" (Quinn, forum thread 732768, June 2023), so the two categories are
  meant to be treated as one. That's stated for apps, and unmeasured for a bare helper; check it at
  the first store release on a tester's Mac.
- **The maintainer's Mac:** a locally exported App Store build is `enterprise`, while TestFlight is
  `testflight`. Never run a locally exported store build's helper on a Mac that runs the TestFlight
  one. Debug builds carry the helper under its own id, `app.bristlenose.mcp.dev` (D2 as amended),
  so everyday work never claims the store id.

**P0.1, measured 29 Sep 2026 on clean SIP-on guests** (Cirrus `-vanilla` images: macOS 15.7.7 24G720
and 26.6.2 25G83), plus this Mac on 27:

| Check | macOS 15 | macOS 26 | macOS 27 |
|---|---|---|---|
| `.dmg` host (3906 Developer-ID export) re-signed to claim `Z56GZVA2QB.app.bristlenose`, profile unchanged | **launches**; taskgated *"Unsatisfied entitlements … Disallowing"*, amfid *"Soft-restriction provisioning profile validation failure"* | **launches**, same three lines | launches (§6.4) |
| control, same app without the group | launches | launches | — |
| profile-less sandboxed helper, Developer ID: write the group (`--seed`), then answer `list_projects` from it | ok | ok | ok |
| the same, Apple Distribution | ok | not run separately (see next row) | ok |
| same helper id, Developer ID then Apple Distribution | **no hang** | **hang** (*"not in ACL … prompting"*) | hang (§6.6, P0.2b) |

So "Disallowing" is a soft restriction on every supported version: it's logged, the app runs, and the
group works. That takes P0.3 (re-export the profile) off the critical path: still worth doing for a
clean log, but it no longer gates P1. The signer ACL on the helper's container arrived in 26.

**A build requirement found on the way:** the first 15 run crashed at launch with
*"Library not loaded … libswift_DarwinFoundation1.dylib"*, because `swiftc` defaulted to the build
machine's OS. The helper must be compiled with `-target arm64-apple-macos15.0`, the app's floor.
D3's gate adds: `LC_BUILD_VERSION minos` equals the app's deployment target.

**P0.5 for ChatGPT, measured 29 Sep 2026 (ChatGPT.app 26.924, stub plugin, marketplace
`bristlenose-p05`).** Install 0.0.8 by link, bump the manifest to 0.0.9, open the same link again:
- The plugin page **re-reads the marketplace** (it shows "Version 0.0.9") but offers only **Try now**.
  The ⋯ menu holds a single item, **Uninstall**. The cache keeps `0.0.8`, and that's what ChatGPT runs.
- **⋯ ▸ Uninstall** acts at once, with no confirmation (toast: "Bristlenose plugin uninstalled"). Then
  **Install plugin** copies `0.0.9` into the cache.

So ChatGPT is outcome B: an update costs two extra clicks on the page our link already opens. The
`.olderRelease` foot line on the ChatGPT tab says so (mockup 2.3).

**P0.5 for Claude Desktop, measured the same evening (maintainer clicking, Claude's `main.log`
read).** A probe `.mcpb` (`local.mcpb.bristlenose.bn-open-probe`) opened by a sandboxed app:
- at the **same** version as the installed one, Claude shows its preview with only **Uninstall**
  (the Node-era observation, reproduced);
- at a **higher** version it offers **Update**. The log shows *"Installing unsigned extension from
  …/Containers/app.bristlenose.openprobe-7e1a/Data/tmp/bn-open-probe.mcpb"* and then *"Successfully
  installed … v0.0.2"* straight over v0.0.1, with no uninstall in between.

So Claude is outcome A. **Update Extension…** works in one click when the manifest version
rises. *As built, the Claude manifest carries the plain release version, not the build number*
(`NativeExtensionPackage.manifest`: a `-<build>` suffix is a semver pre-release and would sort
below the Node extension it replaces). So a different **build** of the same release lands on the
Uninstall-only preview; the Claude tab's foot line tells the researcher to uninstall in Claude
first, then Install Extension… (`claudeReinstallHow`, `bb50067c`). Only ChatGPT's plugin version
carries the build (D8).

**P0.4, partly measured the same evening.** A sandboxed probe (Developer ID, fresh id) wrote a
dummy `.mcpb` into its own container's `tmp` and opened it with Claude via
`NSWorkspace.open(_:withApplicationAt:)`. LaunchServices ran its download-style XProtect check on the
file (`operation:lsopen`, risk level 2) and delivered it. Claude logged *"Handling DXT/MCPB file: 1
path(s)"*, and tccd logged no AppData request or denial for Claude. The install then completed: at 19:32 Claude logged *"Installing unsigned extension from
…/Containers/app.bristlenose.openprobe-7e1a/Data/tmp/bn-open-probe.mcpb"* and *"Successfully installed
… v0.0.1"*. So **Claude reads an extension file written into a sandboxed app's own container**
(LaunchServices hands it over, and no cross-team block applies), and finding 42's fear doesn't hold. Two points follow for P4. A file written
by a sandboxed app is treated like a download, so expect quarantine on what Claude extracts, which the
original P0.4 list already covers. And "Claude can't read our container" is **not** the blocker it was
feared to be: this path goes through LaunchServices, not a cross-team path read.

### 6.8 Still open

> **Rebuilt 29 Sep 2026 (evening) from §6.9 and §6.10.** Still to run: Claude
> through the native package (live install); a TestFlight build of the
> helper-carrying app; Claude and ChatGPT on the 15 and 26 guests; a translocated
> `.dmg` app (D7's refusal); the TestFlight→App Store move for one tester (§6.7);
> the Files & Folders-off run for the Node fallback; the screen recording and
> external TestFlight for App Review (§6.11). A runtime-built `.mcpb` is built
> (P4). The list below is the morning's, kept as written.

- **Human App Review** of the agent-access feature: a submission, with review
  notes for §2.5.2 / §2.4.5(ii).
- **Build 3907 installed from TestFlight:** check the helper after Apple's
  re-signing, i.e. its signer and entitlements
  (`codesign -d --entitlements - …/Contents/Helpers/bristlenose-mcp`). That is
  all 3907 can verify through normal use: its host is unchanged 0.31.5 code
  and never writes the group handshake (the host half is the unapplied draft
  in `docs/drafts/native-proxy-group-handshake/`). A manual end-to-end run is
  possible, because the helper is the spike build and keeps `--seed`. But **not
  on a Mac where the Developer-ID spike helper has run**: the Apple-re-signed
  helper has the same identifier and would hit the §6.6 signer trap. Use a
  clean Mac or user account.
- A runtime-built `.mcpb`.
- §2.5.2 / §2.4.5(ii), "installs code into other apps". This applies to
  today's `.mcpb` as well, and needs review notes whichever route ships.

## 6.9 Implementation plan (v2, 29 Sep 2026 — reviewed; D1–D9 decided 29 Sep 2026)

v1 (commit 67b5e843) went through a six-agent plan review plus a parsimony pass;
41 findings and their adjudication are in the maintainer's private review log,
kept outside the public tree. v2 folds in the adjudication. The decisions below were proposals when written
and were all taken the same day (see *Decisions (taken 29 Sep 2026)*). Their UX
consequences are drawn in `docs/mockups/mcp-native-proxy-decisions.html`.

**Goal (decided):** Claude Desktop and ChatGPT read Bristlenose on macOS 27 with
no Node and no Files & Folders step, on the Mac App Store and the Developer-ID
`.dmg`, with no private SPI. Gemini later, on the same helper.

### Decisions (taken 29 Sep 2026)

All nine were taken as proposed below, with these notes from the maintainer:

- **D1:** the helper is `app.bristlenose.mcp` on the App Store and `app.bristlenose.mcp.devid`
  on the `.dmg`; the executable is `bristlenose-mcp` on both. A name is fixed per channel for
  good; new builds from the same signer never need a new one.
- **D2, amended when the button was built (29 Sep):** Debug builds DO carry the helper, under a third
  identifier, `app.bristlenose.mcp.dev` (Apple Development is its own signer category, §6.7), so the
  ChatGPT flow can be tried from Xcode without ever claiming the store identifier on the maintainer's Mac.
  An ad-hoc or unsigned build still skips it, and its ChatGPT tab keeps the pasted-config layout.
- **D6:** the only existing Claude user who has to reinstall is the maintainer.
- **D7:** the "move to Applications" rule also goes in the help page.
- **Not doing:** a "connected at 14:02" line in Settings, because the antenna, Last asked and the
  row subtitle already show it. Also no per-session exclusion: agent access is opt-in per project,
  and that model stays.
- **Later:** help-page screenshots of ChatGPT's Chat | Work switch.

| # | Decision | Chosen | Rejected, and why |
|---|---|---|---|
| D1 | Helper identifier | **Fresh ids, one per signer class** (how many classes: measured in P0.2). The spike's `app.bristlenose.mcp-proxy` is never shipped: its container on the maintainer's Mac records a spike signer (§6.6). | A different id per *copy*: identical bytes share a container safely. A symlink for the marketplace copy: ChatGPT copies the plugin into its cache, where a link breaks. A `.dev` id: rejected here, then **added** when D2 was amended (Apple Development is its own signer category, so Debug builds need their own id). Ad-hoc builds still carry no helper. |
| D2 | How the helper is built | **Compiled and signed inside the Copy phase** from the identity the host is being signed with (`EXPANDED_CODE_SIGN_IDENTITY_NAME`; skipped when that is empty or `-`), and skipped when its stamp matches. *As built:* Debug builds carry it too, as `.dev` (see the amended D2 above); the `.dmg` lane pins `BRISTLENOSE_HELPER_CHANNEL=devid` at archive, because it archives with development signing and re-signs at export. | A pre-built script product plus freshness stamp (the ffmpeg pattern): it can go stale and ship an ad-hoc helper in a Release archive. An Xcode command-line target: `build-dmg.sh`'s command-line `CODE_SIGN_ENTITLEMENTS` override would apply to it too and give it the host's entitlements. |
| D3 | Gates | **One post-export gate, both copies, both lanes**: sandboxed, no `inherit`, the team group equal to the host's, Info.plist id equal to the signing id, the channel's id, team = `TEAM_ID`, the two copies byte-identical, no `responsibility_*` and no `--seed` string. *As built* (`check-mcp-helper.sh`): copies are compared by **CDHash**, not bytes, because export re-signs each nested copy; the gate also checks `minos` equals the app's floor and refuses the test-build path `BN_TEST_HANDSHAKE_PATH`. `nm` and `strings` output written to a file before `grep`. | Five separate gate proposals. |
| D4 | Group write failure | **Fail closed:** if the group write fails, delete the group copy; a read-back test pins it. Otherwise turning Agent Access off could leave a project readable through a stale group copy. | Log-and-continue (the draft's behaviour). |
| D5 | Proxy diagnostics | **None added.** Build defects are caught by D3; the proxy's messages stay as ported. | A launch breadcrumb (needs the helper to write the group, and watches the client); a group marker file; an HMAC probe challenge (same exposure as the Node proxy today; the real fix is option 2, Mach IPC). Tokens are re-minted at launch when a leftover handshake is found. |
| D6 | Rollout | **No feature flag.** The switch-over (Claude tab native, ChatGPT tab Install Plugin…, Files & Folders copy recovery-only) lands as one commit, after P6 passes on a checkpoint build. *As built:* it landed in two commits (ChatGPT with P3, Claude with P4) before P6 finished; a build without the helper keeps the old layout on both tabs. | A `UserDefaults` flag or `enum FeatureFlags` plus a Diagnostics toggle: before P6 the only audience is one internal tester and local builds. |
| D7 | ChatGPT marketplace location | **Inside the app bundle**, because a copy in our container is a cross-team read macOS 27 denies. A translocated app (a `.dmg` app run in place) is refused with "move Bristlenose to Applications". Written down so nobody "fixes" it. | The container (denied); a download (not reviewed code). |
| D8 | Install state and versions | **Per host.** The ChatGPT plugin version carries the build number (ChatGPT caches by version); Claude's manifest carries the plain release (§6.7). Each tab has Install / Reinstall / Update, never "Installed". An old ChatGPT without `codex://` support gets "Update ChatGPT", not "Download". | One shared state (a stale ChatGPT plugin would flip the Claude button). |
| D9 | App Review | Notes answer the literal words of §2.5.2 and §2.4.5(ii)/(iii)/(iv); screen recording; **external TestFlight before the store**, so a human reviewer sees it first. | — |

### Preserved as shipped (a constraint on every phase)

The plan changes how an agent **reaches** Bristlenose. It does not change how
Bristlenose tells the researcher what is exposed and what is being read, and no
phase may regress it:

| Shipped mechanism | Driven by | Obligation |
|---|---|---|
| Sidebar antenna, solid (exposed now) | `ServeFleet.handshakeProjectPaths` | P1 writes the group copy from the same set in the same call; D4 stops a group copy outliving the solid antenna |
| Antenna radiating, then the two-tap sign-off (an agent is reading, then has finished) | serve's per-project tool-call counter, `/api/agent-activity` | Nothing to build: the helper calls the same `/mcp/` with the same bearer. P6 checks a ChatGPT and a Claude question each radiate the right project. **ChatGPT confirmed 29 Sep 2026:** the antenna radiated on the asked project and Last asked read *Just now*; Claude still to check |
| Projects register: Active / Available when opened, tick, Sessions, Last asked, roll-up, receipts, empty state, scope note | `AgentProjectRegister`, `projectsSection` | Untouched. P5 edits only the pane's top half; `AgentProjectRegisterTests` and `MCPAgentsSettingsViewTests` pass unedited |
| Turn On / Off Agent Access, the badge tooltip, consent v2 | `AgentAccessPolicy`, menu verbs | Untouched |
| Anonymise | serve (`mcp_server.py`) | Untouched; the helper is a pipe |
| Install row's version compare and "asked recently" subtitle | `X-Bristlenose-Proxy-Version` → `agentProxyVersion` | The helper sends the same header; D8 **adds** a host label beside it and never replaces the per-project register |

The mockup (`docs/mockups/mcp-native-proxy-decisions.html`) draws the real
register in every Settings frame for this reason.

### Phases (re-ordered)

- **P0 — each can stop the plan.**
  - P0.1 (**done 29 Sep**, passes on 15/26/27; see §6.7): on clean SIP-on macOS **15 and 26** guests, launch (a) a Developer-ID host carrying the team group, and (b) the real profile-less helper as a foreign app's child; read taskgated. This is the least-discussed, highest-impact unknown: if 15/26 enforce the "Disallowing" check, the `.dmg` host breaks at launch for everyone on those versions.
  - P0.2 (**done 29 Sep**, see §6.7: entitlements survive; four signer classes; the TestFlight→store move is the new unknown, with a local Development-vs-Distribution proxy test as P0.2b): install TestFlight 3907 on a clean account; read both copies' signer, id and entitlements (ffmpeg as control). Sets D1's count. Then **expire 3907** in App Store Connect (**done 29 Sep**) and delete the spike binaries (both carry `--seed`).
  - P0.3: re-export the `.dmg` with the group requested; confirm the minted profile lists it.
  - P0.4 (**install path measured 29 Sep**: Claude reads and installs a `.mcpb` from a sandboxed app's container; the helper-inside-it half, meaning quarantine, exec bit and `spctl` under Claude's extraction, still waits for P4's real artefact): end to end through **Claude's own extraction** of a runtime `.mcpb`, on a clean 27 guest: quarantine flag, exec bit, `__MACOSX` entries, `spctl`; it answers with Files & Folders off.
  - P0.5: a second install at a bumped version, on each host: what ChatGPT and Claude offer. (**done 29 Sep**: ChatGPT outcome B, ⋯ ▸ Uninstall then Install plugin; Claude outcome A, Update in place when the version rises.)
- **P1 — host half** (**landed 29 Sep**: both copies written, D4 fail-closed via `MCPHandshake.writeBoth` with a read-back test; Swift 1553 passed, Python 5617 passed; P0.3 turned out not to gate it), only after P0.1 and P0.3 pass: the draft patch, amended to fail closed (D4) with a read-back test, and the reader set written into design-mcp-extension §3.1.
- **P2 — helper** (**landed 29 Sep**: `desktop/mcp-helper/main.swift` + `build-helper.sh`, the D3 gate `desktop/scripts/check-mcp-helper.sh` (also run by `check-pkg-shippable.sh` and `check-dmg-shippable.sh`), `tests/test_mcp_helper.py`; built in the Copy Sidecar Resources phase into `Contents/Helpers` and the ChatGPT marketplace; copies compared by CDHash) per D1–D3, source moved to `desktop/mcp-helper/`; the tool list read from the `BN-TOOLS-JSON` block with its annotations; that block moves out of `desktop/mcpb/` before the Node extension is retired, **and `tests/test_mcpb_proxy.py` moves with it in the same commit** (re-point `_PROXY_JS` and the regex). It is the only check that the static tool list and its annotations match the server's `tools/list`, and it looks like it belongs to the Node extension, so it would otherwise be deleted with it and leave the helper's list unguarded.
- **P3 — ChatGPT** (**landed and proven end to end 29 Sep**, §6.10): marketplace per D7, Install Plugin… per D8, link query encoded strictly (unit-tested with `& + # %` and spaces).
- **P4 — Claude** (**landed 29 Sep**: `NativeExtensionPackage` zips the helper at click time; the live install through Claude is still to be run): runtime `.mcpb` per P0.4; `MCPExtensionInstaller`'s bundled-file assumptions (`claudeDesktopCanInstall`, the disabled state, `bundledStamp`) repointed at the runtime artefact with a stamp beside it.
- **P5 — switch-over** (**landed 29 Sep**, in two commits rather than one: ChatGPT with P3, Claude with P4. A build without the helper keeps the old layout on both tabs, so no release carries a half-state), confined to the pane's top half (see *Preserved as shipped*).
- **P6 — verify** (**29 Sep, done so far:** Swift 1567 passed on the P4 build; the break harness, §6.10; ChatGPT end to end on this Mac; a **Developer-ID archive and export** built as `build-dmg.sh` does, minus notarisation: both helper copies came out signed Developer ID as `app.bristlenose.mcp.devid` with sandbox, network client and the team group intact, identical CDHash, the host carrying exactly the team group, and the app passing `codesign --deep --strict`. **Still to run:** Claude through the native package; a TestFlight build; Claude and ChatGPT on the 15 and 26 guests; a translocated `.dmg`; TestFlight→App Store), each item with its layer named: Swift tests (handshake read-back, installer manifest, zip, link encoding); script gates (D3, and `test-check-pkg-shippable.sh` cases — that suite has no helper case yet); by hand once: a TestFlight build, Claude and ChatGPT on 15 / 26 / 27, a translocated `.dmg` app, TestFlight→App Store update.
- **P7 — review notes** per D9 (**drafted 29 Sep**, §6.11; the screen recording and external TestFlight remain).

### Wire contract (D8, as built)

- The helper sends `X-Bristlenose-Proxy-Version` as the Node proxy does, plus
  `X-Bristlenose-Proxy-Host` from `BRISTLENOSE_MCP_HOST` (`Claude` in the
  `.mcpb` manifest, `ChatGPT` in the plugin's `.mcp.json`).
- serve records it per host (`ProxyIdentityRecorder._record_for_host`,
  `app.state.mcp_proxy_versions`; host label `^[A-Za-z0-9._-]{1,32}$`, at most 8
  hosts) and returns the map as `proxy_versions` from `/api/agent-activity`.
- The legacy single `proxy_version` slot stays the Node extension's, so an
  older app build reads what it always read.
- Swift reads it as `ServeManager.agentProxyVersions`; each tab compares its own
  host's entry (`MCPAgentsSettingsView.chatGPTState`, `extensionState`).

**Out of scope for v1:** Mach IPC instead of a handshake file (option 2 — also the real answer to the token-probe exposure); Gemini; the duplicate-row exposure bug.

## 6.10 Breaking it, 29 Sep 2026

Once the ChatGPT button worked, the plugin was attacked two ways: an automated
harness over stdio, and ChatGPT itself driven through the app.

### The harness (`tests/test_mcp_helper_behaviour.py`, 34 cases, ~5 s)

A **test build** of the helper (`-D BN_TEST_HANDSHAKE`) reads its handshake from
a path the test chooses; the shipped binary is never built that way, and
`check-mcp-helper.sh` refuses any binary containing the test path. The harness
starts a real `bristlenose serve` app in-process (uvicorn, free port, temp
database) and drives the helper exactly as a host does.

| Area | Cases |
|---|---|
| Happy path | five tools listed, all `readOnlyHint`; a proxied call answers; the call is counted (antenna); the host's build is recorded under `ChatGPT` (D8) |
| Handshake wrong | missing; eight kinds of garbage; unreadable (`chmod 0`: the permission sentence, never Files & Folders); schema 1; re-read on every call, with `tools/list_changed` on the offline→ready edge |
| Wrong process on the port | dead port; three impostor HTTP servers — **the bearer never reaches them**, only the unauthenticated `GET /api/health`; a restarted serve (stale `instance_id`) gets no tool call; a missing or empty `instance_id` fails closed; a crashed serve is not listed (below) |
| Serve refuses | wrong token → the credential sentence; a token carrying `\r\n` neither crashes nor injects; out of scope; no MCP; a newer app → "older than the Bristlenose app" |
| Several projects | ambiguous; unknown key; the right key; a hostile project name returns as data |
| Protocol | malformed frames (including 200 KB of junk) dropped; unknown method and unknown tool answered; 25 calls in a burst answered in order; EOF exits 0; `initialize` answers in under 2 s with a dead serve |

**Proved on mutants:** removing the stale-instance check fails exactly the four
instance cases; sending the bearer on the probe fails exactly the three impostor
cases; dropping the host header fails exactly the D8 assertion; reverting the
crash fix fails exactly its two cases.

### Driving ChatGPT (Work mode, plugin 0.31.5+3906/3907)

| Test | What ChatGPT did | Verdict |
|---|---|---|
| "Delete p3's quotes and rename the project" | called `list_projects`, found no write tool, said so | pass: read-only holds |
| project keys `../../../etc/passwd` and `x" OR 1=1 --`, then the real key | "not open … Currently readable: project-ikea"; the real key returned the overview | pass |
| `kill -9` Bristlenose, then ask | the sidecar exited itself within seconds; `get_project_overview` said "isn't open" — **but `list_projects` still listed the project** | **bug, fixed** (below) |
| same, after the fix | "Bristlenose isn't open, so there is no study data available" | pass |
| a Work thread **without** @Bristlenose | "I don't see any Bristlenose study materials"; once it called ChatGPT's own built-in `list_projects` (Codex workspace folders) instead | **copy fixed** (below) |
| continuing a thread that held the traversal and injection probes | "This content can't be shown — We take extra care with some cybersecurity requests" | ChatGPT's own filter; a limit on adversarial testing through ChatGPT, not a Bristlenose fault |
| the antenna and Last asked during a ChatGPT question | radiated; "Just now" | pass (maintainer's observation) |
| per-tool approval cards | none, five tool calls | pass |

**Two defects found and fixed:**
1. **A crash left a project listed as readable.** The handshake survives
   `kill -9`, and `list_projects` answered from it alone while every call said
   "isn't open". `list_projects` now probes each entry (unauthenticated, as
   every call already does) and lists only a live, matching serve.
   The Node proxy has the same behaviour and is retiring; it is left as is.
2. **The Work note didn't mention @Bristlenose.** ChatGPT uses a plugin only
   when the question mentions it, and without it will even reach for its own
   `list_projects`. The note now reads *"In ChatGPT, ask in Work mode and start
   with @Bristlenose — otherwise its tools aren't used"*, in all 21 locales.

**Leftovers noticed, not fixed:** ChatGPT's config still enables
`bristlenose@bristlenose-p05`, the P0.5 stub, whose cache is gone; ChatGPT's
Installed sidebar lagged a reinstall although `config.toml` recorded it.

## 6.11 App Review notes (draft, D9 / P7)

For the App Store Connect "Notes for Review" field on the first build that
carries the helper. Each paragraph answers the words of the guideline it names.

> **Agent access (optional feature).** Bristlenose can let the researcher's own
> AI assistant (Claude Desktop or ChatGPT, installed separately) read a study
> they have chosen to share. It is off until the researcher turns it on for a
> project (Project ▸ Turn On Agent Access), and it only answers while
> Bristlenose is running with that project open.
>
> **§2.5.2 (self-contained; no code downloaded or executed that changes
> features).** The helper `Contents/Helpers/bristlenose-mcp` and the copy inside
> `Contents/Resources/chatgpt-marketplace/` are part of this reviewed bundle,
> signed with it. Nothing is downloaded. The helper only relays read-only
> questions to Bristlenose's own local server; it does not change the features
> or functionality of Bristlenose or of any other app.
>
> **§2.4.5(ii) (no writing outside the container, except shared locations).**
> Bristlenose writes a small connection file into its own container and into its
> own team app group container (`Z56GZVA2QB.app.bristlenose`). It writes nothing
> into Claude's or ChatGPT's files or settings.
>
> **§2.4.5(iii) (no auto-launch without consent).** Bristlenose never launches
> the helper. The researcher clicks Install in Settings ▸ MCP Agents; the other
> app shows its own install confirmation, installs the plugin or extension
> through its own documented mechanism, and is the process that later runs the
> helper when the researcher asks it a question.
>
> **§2.4.5(iv) (no additional code in the bundle).** The helper is a single
> signed executable built from this app's source; it is sandboxed, carries only
> `app-sandbox`, `network.client` and the team app group, and uses no private API.
>
> **Scope.** Five read-only tools (list projects, project overview, search
> quotes, signals, framework). No tool writes, deletes or sends data anywhere
> but back to the researcher's own assistant. The researcher can revoke access
> per project at any time, and every agent question lights an indicator in the
> sidebar.
>
> A screen recording of the flow (turn on access, install into ChatGPT and into
> Claude, ask a question, turn access off) is attached.

**Before submitting:** record that screen recording; ship to **external**
TestFlight first so a human reviewer sees the helper before the store does
(D9); run `check-pkg-shippable.sh` on the exported `.pkg`, which now runs the
helper gate over every copy.

## 7. Recipes

```bash
# Open System Settings at Files & Folders
open "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_FilesAndFolders"

# Install a local plugin in ChatGPT by link (file path, URL-encoded)
open "codex://plugins/bristlenose?marketplacePath=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=""))' /abs/path/.agents/plugins/marketplace.json)"

# What did ChatGPT's MCP servers print?
cp ~/.codex/logs_2.sqlite* /tmp/ && sqlite3 /tmp/logs_2.sqlite "select * from logs" | grep 'MCP server stderr'

# Which process started a plugin, and which node did it use?
ps -o pid,ppid,command -ax | grep -E 'bin/bristlenose-mcp|server/index.js'
```

## 8. Sources

- Apple macOS 27 release note, quoted in
  [Blake Crosley, "macOS 27 Denies Cross-Team Container Access Without Asking"](https://blakecrosley.com/blog/macos-27-cross-team-container-access)
- [Wojciech Reguła, "Crossing the Golden Gate: macOS's New Application Support Protection"](https://wojciechregula.blog/post/golden-gate-appdata-protection/)
- [openai/codex#31897: Sites plugin fails on Macs without Node](https://github.com/openai/codex/issues/31897)
- [openai/codex#41977: duplicate Files & Folders entries on macOS 27](https://github.com/openai/codex/issues/41977)
- [maxgoedjen/secretive#839: macOS 27 blocks access to SecretAgent's container](https://github.com/maxgoedjen/secretive/issues/839)
- [sflinter/banktivity-swift-mcp#49: prompt reappears on every launch](https://github.com/sflinter/banktivity-swift-mcp/issues/49)
- [OpenAI: Package your plugin](https://developers.openai.com/codex/plugins/build)
- [DEVONthink MCP server](https://www.devontechnologies.com/blog/20260526-devonthink-mcp-server) and
  [Apple: Giving external agents access to Xcode](https://developer.apple.com/documentation/xcode/giving-external-agents-access-to-xcode) — native helpers, no Node
- [Qt forum 140400: App Store rejections naming the responsibility SPI (Qt 6.4.0, 2022)](https://forum.qt.io/topic/140400)
- Apple Developer Forums [thread 731504](https://developer.apple.com/forums/thread/731504) (no general API for responsibility) and [thread 721701](https://developer.apple.com/forums/thread/721701) (team-prefixed app groups without a profile)
- [Apple: Configuring app groups](https://developer.apple.com/documentation/xcode/configuring-app-groups) and the [`com.apple.security.application-groups` entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.application-groups)
- [ACE Studio: ChatGPT for desktop](https://docs.acestudio.ai/ai-agent/external-agent-access/chatgpt-for-desktop) — the clearest Work-vs-Chat explainer found
