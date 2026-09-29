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
   signed the binary doing the read.** *Measured.*
4. **A team-signed binary launched as its own responsible process reads the
   container with no grant at all.** The read never reaches TCC. *Measured.*
5. **So a 128 KB native proxy, signed by our team, that relaunches itself
   disclaimed removes both problems:** no Node, and no Files & Folders step.
   Proven end to end in ChatGPT with a real study question. *Measured.*
6. **The disclaim trick cannot ship on the Mac App Store** (private SPI App
   Review has rejected by name, and an unsandboxed helper in the MAS bundle
   fails upload). **A public-API route works instead:** write the handshake into
   a Team-ID-prefixed app group, and ship the proxy **sandboxed** with that group.
   Such a proxy reads the group container with no grant, with ChatGPT, Claude
   Code or Terminal responsible (§6). *Measured; App Store acceptance of the
   nested tool is unverified until one TestFlight upload.* The native port still
   lacks several of the Node proxy's states (§4.3).

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

Claude Desktop is different: `.mcpb` extensions of `type: node` run on the
Node that Claude ships.

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
  grant. A new Claude install on 27 has no such entry, so it starts denied.
  That last step is *inferred* from the release note and the ChatGPT
  measurement, not reproduced on a clean Claude.
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

### 4.3 What the spike leaves out

Before it could ship, the Node proxy's remaining states need porting: the
scope fingerprint on every result, `notifications/tools/list_changed` on the
offline→ready edge, the contract/outdated check, the 404 "built without agent
support" branch, and the `unhealthy` / `not-bristlenose` probe distinctions.
The tool list must stay generated from one source. The spike's `build.sh`
extracts the Node proxy's `BN-TOOLS-JSON` block; a shipped version should keep
`tests/test_mcpb_proxy.py`'s drift gate pointed at whatever becomes canonical.

One port bug surfaced on the way: an unknown `project` argument must answer
*"not open; readable: name = key"*, not *"isn't open"*. The first build did the
latter and the model reported Bristlenose closed. Fixed; per-call reasons are
logged to stderr, which lands in Codex's log (§1.3).

### 4.4 It serves Claude too

`.mcpb` supports a binary server, and the disclaim makes the host irrelevant:
proven under two hosts (Terminal and ChatGPT). The same binary would remove the
Files & Folders step for new Claude users on macOS 27. *Inferred* for Claude
itself (not run inside Claude Desktop).

## 5. How the pieces fit

| Problem | Node proxy today | Native, disclaimed (§4) | Native, sandboxed + app group (§6) |
|---|---|---|---|
| ChatGPT one-click install | works (`marketplacePath` link) | works | works (same link) |
| Mac without Node (ChatGPT) | **fails** | works | works |
| Claude Desktop runtime | Claude's own Node | binary server | binary server |
| macOS 27, new install | **silently denied** until Files & Folders is switched on | allowed, same-team | allowed, same-team group |
| macOS 27, carried-over grant | works | works | works |
| Mac App Store build | ships today | **rejected** (§6) | ship with risk: one TestFlight upload decides |
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
read and write that group's container with no grant and no tccd request. That
holds whichever app is responsible for it. Apple's app-groups documentation
gives the reason: macOS checks that the accessing code signature contains the
same Developer Team ID.

Measured on 29 Sep 2026 with a probe group, `Z56GZVA2QB.app.bristlenose.batest`:

| Probe | Responsible process | Group container |
|---|---|---|
| team-signed, sandboxed, with the group | Claude Code (team Q6L2SF6YDW), even with a cached denial for our containers | **list, write, read ok** |
| same | fresh Terminal | **ok** |
| same | **ChatGPT.app** (probe run as a ChatGPT plugin's server) | **list, write, read, delete ok** |
| team-signed, unsandboxed, no group | ChatGPT.app | denied |
| team-signed, **unsandboxed but with** the group | fresh Terminal | denied: the entitlement only counts when sandboxed (*inferred* from one run) |
| ad-hoc, sandboxed, with the group | Terminal | denied (not our Team ID) |
| team-signed, sandboxed, no group | Terminal | denied |

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

### 6.3 Options, ranked

| # | Option | MAS review | Claude + ChatGPT |
|---|---|---|---|
| 1 | **Team-prefixed group container + sandboxed native proxy** | ship with risk: acceptance of a nested non-inherit tool carrying its own group is unverified until one TestFlight upload | both |
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
  - The Mac App Store profile already authorises `XXXXXXXXXX.*`.
  - Developer ID needs no profile for team-prefixed groups.
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

### 6.5 Still open

- **One TestFlight upload** carrying the nested sandboxed tool with its own
  group.
- **The group probe with Claude Desktop as the parent.** Pending: a clean
  macOS 27 virtual machine is being prepared for the Claude tests.
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
