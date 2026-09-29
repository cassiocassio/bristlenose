---
status: spike — measured, nothing shipped
last-trued: 2026-09-29
---

# ChatGPT plugin, macOS 27, and the native proxy

_Measured on 29 Sep 2026 on one Mac (macOS 27.0, build 26A428; ChatGPT desktop
26.924, bundle id `com.openai.codex`, free account). Spike code:
[`experiments/mcp-native-proxy/`](../experiments/mcp-native-proxy/). Every claim
is labelled **measured**, **inferred** or **unverified**. The raw session record
is in the maintainer's private handoff notes, kept outside the public tree._

Related docs:
- [`design-mcp-extension.md`](design-mcp-extension.md) — the shipped Claude Desktop `.mcpb`
- [`design-mcp-server.md`](design-mcp-server.md) — the `/mcp` endpoint
- [`design-mcp-files-and-folders.md`](design-mcp-files-and-folders.md) — the System Settings route; drafted the same day

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
   disclaimed removes both problems:** no Node, and no Files & Folders step.
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
   inside ChatGPT (§6.2). One real TestFlight upload and human
   App Review remain. The native port still lacks several of the Node proxy's
   states (§4.3).

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
- **ChatGPT asks per tool** ("Allow the bristlenose MCP server to run tool
  X?" — Always allow / Deny / Allow once). "Always allow" on one tool did not
  cover the next. *Measured.* After marking every tool
  `annotations.readOnlyHint: true`, six tool calls ran with **no approval card
  at all**. *Inferred* that the annotation is the cause; nothing else changed.
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

| Problem | Node proxy today | Native, disclaimed (§4) | Native, sandboxed + app group (§6) |
|---|---|---|---|
| ChatGPT one-click install | works (`marketplacePath` link) | works | works (same link) |
| Mac without Node (ChatGPT) | **fails** | works | works |
| Claude Desktop runtime | Claude's own Node | binary server | binary server |
| macOS 27, new install | **silently denied** until Files & Folders is switched on | allowed, same-team | allowed, same-team group |
| macOS 27, carried-over grant | works | works | works |
| Mac App Store build | ships today | **rejected** (§6) | passes `--validate-app` (§6.5); one upload and review remain |
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

**Developer ID only: ship with risk.** If kept as a contingency there:
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
| 1 | **Team-prefixed group container + sandboxed native proxy** | **passes Apple's validator** (§6.5); upload processing and human review remain | both |
| 2 | Mach IPC rendezvous under the group prefix (`CFMessagePort` / XPC). No token on disk; the long-run hardening against macOS 27's tightening on files created by other teams | ship with risk | both |
| 3 | `SMAppService` agent with `MachServices` | as 2, plus the background-item notice (§2.4.5(iii)) | both |
| 4 | LaunchServices helper `.app` | useless on MAS (must be sandboxed); needs a relay | — |
| 5 | Files & Folders on MAS only | ships, but gives ChatGPT nothing on MAS (no Node, and a sandboxed Mach-O can't read the data container) | Claude only |
| 6 | Handshake outside the container (temporary exception or bookmark) | two exceptions to justify; the token becomes readable by any same-user process | — |
| 7 | Bonjour, a fixed port, or the keychain | none of these moves the token; the keychain needs a profile the bare proxy can't carry | — |

### 6.4 Recommended: one mechanism on both channels

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

### 6.6 Still open

- **One real upload to internal TestFlight** carrying the nested sandboxed
  tool, to see whether processing agrees with validation. It spends a build
  number for good; pick one that cannot collide with a release. Maintainer's
  call.
- A runtime-built `.mcpb`.
- §2.5.2 / §2.4.5(ii), "installs code into other apps". This applies to
  today's `.mcpb` as well, and needs review notes whichever route ships.

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
