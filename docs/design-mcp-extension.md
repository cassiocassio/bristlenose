---
status: draft
---

# The Bristlenose extension — connecting Claude Desktop without a config file

_Scoped 31 Jul 2026, the night the hand-paste path failed three times in a row.
This doc covers the `.mcpb` route recorded as §6a route 3 in
[`design-mcp-server.md`](design-mcp-server.md), promoted from "polish" to "the
thing that makes Claude Desktop usable". The MCP server itself is unchanged —
this is purely how a client gets connected to it._

## Changelog

- _31 Jul 2026_ — initial scope, after the QA walk (Finding 86) and a read of
  Figma's shipped extension.

---

## 1. Why the current path cannot ship

Three consecutive failures in one sitting, all from one cause, plus a
destructive failure mode and a sandbox that forbids us from helping.

**JSON has no append-safe form.** Adding a server means inserting a member into
an existing object: a comma goes on the *previous* line, none after the new one.
Paste after the closing brace and you get `Unexpected non-whitespace character
after JSON`; fix the braces wrong and you get `Extra data: line 111`. Both
happened. No wording of a how-line removes this — it is a property of the
format, not of the instructions.

**The failure is destructive, not inert.** Claude Desktop does not skip an
unparseable key; it rewrites the entire settings file. Observed live: 298 lines
→ 107, taking `codeGroups` and `simulatorDeviceConsent` with it. A syntax slip
while adding an MCP server costs the researcher unrelated settings.

**We cannot validate the result.** The App Sandbox keeps the desktop app out of
another app's container — reading that file is as blocked as writing it. The
`NSOpenPanel` escape hatch (user navigates to a foreign app's JSON) is poor UX
and the kind of thing App Review scrutinises; §6a rejected it and that stands.

**The restart costs more than we said.** `claude_desktop_config.json` carries
`ccd-sessions-filter`, `coworkUserFilesPath`, `desktop-frame.paneStore.v1` —
it is the host app's own state. "Restart Claude Desktop after saving" can end
the researcher's own working session in that app.

Against the objective — *friction-free, non-error-prone, just works* — the
hand-paste path fails all three. It is not a copy problem.

## 2. What Figma does (read from the installed extension, not from docs)

`~/Library/Application Support/Claude/Claude Extensions/ant.dir.ant.figma.figma/`

- **`manifest.json`** declares `server.type: "node"`, `entry_point:
  "server/index.js"`, and `mcp_config: {command: "node", args:
  ["${__dirname}/server/index.js"]}`. **A manifest cannot declare a remote HTTP
  server.** Every extension is a stdio command; reaching an HTTP endpoint means
  shipping a proxy.
- **The proxy is small** — 88 lines of entry + 191 lines of vendored proxy.
- **It proxies to `http://127.0.0.1:3845/mcp`** (falling back to `/sse`). Figma
  Desktop serves MCP on a local port; the extension bridges stdio↔HTTP. **This
  is Bristlenose's architecture exactly.**
- **The not-running case is handled beautifully.** If neither endpoint answers,
  it starts a *fallback* MCP server that registers every tool from the manifest
  by name and description, each returning step-by-step instructions for turning
  the real server on. The tools always appear in the client; a stopped app
  produces a helpful sentence, never a dead connection.
- `user_config` (seen in Anthropic's filesystem extension) lets the **client**
  collect configuration through its own UI and interpolate it via
  `${user_config.x}` — values need not be pasted into a file at all.

Two patterns to steal outright: **the fallback tool server**, and **trying more
than one endpoint shape**.

One difference that drives our design: Figma pins port **3845**. Bristlenose
uses `--port 0` (kernel-assigned, per the A6 decision), so the proxy cannot
hardcode an address.

## 2a. Better prior art than Figma — Sketch, and a reference handshake

Found after the first draft, and it changes what we cite as validation.

**Sketch ships an official `.mcpb` that is our exact shape**
([`sketch-hq/sketch-mcp-bundle`](https://github.com/sketch-hq/sketch-mcp-bundle)):
macOS app, Node stdio proxy, localhost Streamable HTTP, manifest v0.3,
`platforms: ["darwin"]`, **136 lines** of `server/index.js`. Unlike Figma's, it
is a real extension in Claude Desktop's directory rather than a hand-configured
CLI entry — so it is prior art for the *distribution* question too, not just
the transport.

Its degradation model is better than Figma's and matches what §3.2 arrived at
independently, which is reassuring: it **never fails `initialize`** (placeholder
`serverInfo`/capabilities when the app is closed), returns placeholder tool
stubs from `tools/list`, and answers `tools/call` with **tool-result text
addressed to the model** — *"Either Sketch is not running or its MCP Server is
not yet enabled. Explain the situation to the user and direct them to…"* — never
a JSON-RPC error. It opens a **fresh HTTP transport per request**, so it
self-heals the moment the app launches. Take all of it.

One addition from JetBrains' bridge: fire **`notifications/tools/list_changed`**
when the server appears, so a researcher who launches Bristlenose mid-session
recovers without restarting Claude Desktop. That closes the last restart in the
flow.

**And the handshake file has a complete reference implementation.**
[`Automattic/shippable-code-review`](https://github.com/Automattic/shippable-code-review)
states our exact problem in a source comment — *"picks an ephemeral port at
boot… the MCP server is a separate process with no IPC channel, so it can't
find us without a stable on-disk pointer"* — and solves it the way §3.1 does:
`{schemaVersion, port, pid, startedAt}`, atomic temp+rename, `0o600`, removed on
graceful exit, and **health-checked before the file is trusted**, because *"the
health check is what makes a stale file safe to leave on disk"*. Chrome's
`DevToolsActivePort` is the same design at Google scale, and Microsoft documents
it for precisely the `--remote-debugging-port=0` case. Proxyman ships a
per-session token at `…/mcp-handshake.json` (0600) — the same filename this plan
picked independently.

**What Sketch is a reference for, and what it isn't.** Worth separating,
because the axis it doesn't cover is the one that gates this plan.

*It is good evidence for:* a **Mac-only** extension being a legitimate shipping
shape — `platforms: ["darwin"]`, listed in Claude Desktop's directory, no
Windows/Linux parity required, which matters because BN's desktop app is
macOS-only and we'd otherwise wonder if that disqualifies us; a **companion
desktop app** getting listed at all; a **non-engineer audience** (designers,
much like researchers) being handed an extension rather than a config file; and
the degradation model above.

*It is not evidence for:* **the container read.** Sketch hardcodes
`http://localhost:31126/mcp` — its proxy never reads a file from Sketch's
container, so it crosses no sandbox boundary and tells us nothing about TCC.
Same for Figma (3845) and Beeper (23373). Nor does it cover ephemeral ports,
or a bearer token. So the single unattested step in §3.1 stays unattested
however much prior art we accumulate, and §8.1 remains the gate.

**And Sketch ships a cautionary tale that argues for our approach.** Their own
[docs](https://www.sketch.com/docs/mcp-server/) say the port is user-changeable
via `defaults write com.bohemiancoding.sketch3 mcpServerPortNumber` — but the
bundle hardcodes 31126, so a user who changes it silently breaks the connector.
That is the failure mode a hardcoded constant produces the moment the value can
move. Ours moves *every launch*, and our `.mcpb` never auto-updates — so
hardcoding anything the app can change would be that bug by construction. The
handshake isn't gold-plating; it's the minimum for a port we don't control.

**Two alternatives this surfaced, both worth a sentence before we commit:**

- **Drop TCP entirely — a UNIX socket.** Both vendor-official macOS precedents
  avoid ports: Apple's `xcrun mcpbridge` (XPC) and Unity's official relay (UNIX
  socket), as do 1Password and Anthropic's own Claude-in-Chrome. Uvicorn
  supports `--uds`. A socket at a deterministic path inside the container
  removes port discovery, ephemeral ports, collisions **and** DNS-rebinding
  exposure in one move — but it does not remove the container-read question,
  and it costs the browser-reachable `/mcp` URL the CLI path uses.
- **Ship the proxy inside the app bundle instead of the `.mcpb`.** Proxyman does
  exactly this: `"command": "/Applications/Proxyman.app/Contents/MacOS/mcp-server"`.
  The proxy then always matches the app version, which **dissolves the
  never-auto-updates problem** (§6.3) — at the cost of the one-click install the
  whole plan is for, and of a hardcoded `/Applications` path. Probably not, but
  the version-skew trade should be recorded rather than rediscovered.

## 3. The design

### 3.1 The handshake file (how the proxy finds the server)

The Swift host writes a small file whenever a project starts serving, updates it
on warm re-point, and removes it on stop:

```
~/Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json
```

```json
{
  "schema": 1,
  "port": 58735,
  "token": "<MCP-scoped bearer>",
  "instance_id": "<random per serve start, echoed by /api/health>",
  "updated_at": "2026-07-31T01:19:46Z"
}
```

**`instance_id`, and never send the bearer to an unverified port.** This is the
highest-value detail in the design and it replaces three weaker mechanisms at
once. The port is kernel-assigned and ephemeral; a handshake that outlives a
SIGKILL (force quit, OOM, the Xcode stop button — none of which run our "delete
on stop" path) names a port something *else* may now own. A proxy that opens an
authenticated transport against it hands a **durable** bearer to a squatter, who
can then scan loopback for Bristlenose's next port. So:

1. Unauthenticated `GET /api/health` first — it is auth-exempt and data-free.
2. Compare `instance_id`. Only on a match does the proxy open the
   authenticated transport.

That closes the naive squat *and* the targeted one, costs one round-trip and
about six lines, and subsumes `pid` entirely — liveness by "does the socket
answer with my instance id" is stronger than liveness by pid (which is
reuse-vulnerable) and portable to a JS proxy with no libproc binding. It also
makes "handshake names A while the server serves B" detectable rather than
silent.

**No `project` field.** `MCPTokenStore.accountKey` already SHA-256s the project
path precisely so a client's folder name (`~/Clients/Acme/…`) never becomes
readable metadata; writing `"path": "/Users/…"` in cleartext into a file with
the same reader set would contradict that decision for no gain. The proxy
doesn't need it — tool payloads carry the project and the overview is the
authority.

**Write it the way this codebase already writes credentials.** Not
`Data.write(to:options:.atomic)` — that has no way to express a mode and lands
at the umask default (verified: `projects.json` in this very directory is
`0644`, while `state.json` is `0600`). Use `open(2)` with
`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600` on a uniquely-named temp, write,
`rename()` — mirroring `run_lifecycle.py:_write_pid_file`. `O_NOFOLLOW` is
load-bearing rather than decorative: the containing directory is
`drwxr-xr-x`, so any same-user process can pre-plant
`mcp-handshake.json → ~/Library/Mobile Documents/…`, and a following write
would replicate a live bearer to iCloud and off the machine. Also set
`NSURLIsExcludedFromBackupKey` — it is a runtime artefact with no restore
value.

Mode `0600`, opened `O_NOFOLLOW` — match the sibling credential class
(`bristlenose/llm/telemetry.py` enforces both). That directory already holds
`state.json`, `projects.json` and `pids/`. **The axis that makes the read
possible is same-UID, not file mode** — both `app.bristlenose` and its `Data`
dir are `drwx------`, so "world-readable" would be wrong and would mislead the
next reader. The path is deterministic (the bundle id is
irrevocable) and needs no entitlement on either side: BN writes inside its own
container; the proxy is not sandboxed.

**The handshake must never carry the *server* token — and the obvious
implementation will.** The shipped sheet reads
`serveManager.mcpToken ?? serveManager.authToken`, and `mcpToken` is nil
whenever the Keychain refuses — which is *always* on ad-hoc-signed builds
(-34018, review-log Finding 72). Copy that expression into a handshake writer
and every local QA build publishes the **unscoped** token — the one that opens
`/api/*`, participant names and curation writes — into a file another vendor's
process reads. Today that token only reaches the WebView cookie jar and host
memory. So: write an MCP-scoped token or write nothing. When the Keychain
refuses, mint an *ephemeral process-lifetime scoped* token and inject that,
rather than falling back to `authToken`.

The proxy resolves in order, first hit wins:

1. `$BRISTLENOSE_MCP_HANDSHAKE` (dev override)
2. the sandboxed container path above (desktop app)
3. `~/Library/Application Support/Bristlenose/mcp-handshake.json` (CLI `serve`
   on a non-sandboxed install)

(3) is a deliberate bonus — a CLI user can install the same extension rather
than hand-editing anything — **but it must not ship as drafted.** On the CLI
there is no `_BRISTLENOSE_MCP_TOKEN`, so `middleware.py` falls back and `/mcp`
validates against `auth_token`: the credential that opens all of `/api/*`,
including participant names and destructive curation writes. Writing that to a
well-known path would walk review-log Finding 57 back in through the CLI door,
and would falsify SECURITY.md's "opens the four read-only tools and nothing
else" for every CLI user. **Writing a handshake must imply scoping**: the CLI
mints its own scoped token when handshake-writing is enabled, or it refuses to
write one. Pin it with a sibling of `TestScopedMcpToken` asserting the
handshake token 401s on `/api/projects/1/people`.

Path (1), the dev override, is also an attacker-settable input: `launchctl
setenv` needs no privileges and applies to every GUI app launched afterwards,
which would let someone point the proxy at their own port and become a
man-in-the-middle *inside* the tool-result envelope the model is told to trust.
Ship the override only in a dev-built `.mcpb` that never enters
`Contents/Resources` — the shipped JS has no Debug/Release split, so the
`#if DEBUG` discipline the Swift side uses cannot be inherited.

**Why this is also a security improvement.** The token stops travelling: it
never enters another vendor's plaintext config and never touches the
pasteboard. It lives at `0600` inside BN's own container and is read at connect
time. Claim it no more strongly than that. The permissions story is roughly a wash
(`claude_desktop_config.json` is itself `0600` in a `0700` parent); **the real
win is duration and handling** — a config file is a document humans open, edit,
screenshot, sync with dotfile managers and paste into support threads, while
the handshake is a runtime file no human opens that dies with the process.

**And the argument that should lead any security conversation about this
surface:** an attacker who can read the handshake could already read the
study. `bristlenose-output/transcripts-raw/*.txt` is `0644` in a `0755`
directory — the raw transcripts are *more* permissive than the token will be.
The MCP surface adds no confidentiality boundary a same-user attacker didn't
already have. That is why the interesting attacks are the ones that *escape*
the same-user assumption — the symlink redirect, the port squat, and the env
override below — and those are the four this design engineers against.

One place the token is genuinely load-bearing rather than a speed bump: **a
multi-user Mac**. The file is unreachable across users (`~/Library` is `0700`),
but `127.0.0.1:58735` is machine-wide, so under Fast User Switching the bearer
is the only thing between user B and user A's quote corpus. Anyone later
tempted to "simplify" this to *the file read is the authorisation* would be
removing the only control in that configuration. Revocation becomes a
file write instead of a hunt through a foreign config — which retires
Findings 66 (rotating port), 72's UI half (revoke), and the sheet's address
caveat in one move.

### 3.1a Why not just pin the port, like everyone else?

The obvious question, because a fixed port deletes discovery, the handshake
file, the container read, and the TCC gate in one move. Considered and
rejected — recorded here so it isn't re-proposed as a bright idea.

**First, why the port moves at all.** Not to avoid clashes. The A6 redesign
(Apr 2026) dropped deterministic per-project ports because they existed *only*
to support orphan cleanup, which the sidecar now does itself via its
parent-death watcher; removing them deleted ~150 lines of djb2-port-walker and
libproc scaffolding. The desktop host never needed port stability — the
WKWebView is injected with whatever URL the sidecar reports.

**Why pinning doesn't save us: the token still has to travel.** Every
fixed-port precedent we surveyed has *no authentication* — Figma's is "managed
automatically by Figma", Sketch's has none. Bristlenose has a bearer token, and
per the security review it is the one genuinely load-bearing control on a
multi-user Mac (the handshake file is unreachable across users, but
`127.0.0.1:<port>` is machine-wide). So a pinned port would still leave us
writing a file for the proxy to read — one field shorter, with the container
read and the TCC question entirely intact. Putting the token in `user_config`
instead is hand-pasting a secret again, and lands on the `$`-corruption bug
(§6.7).

**Two further costs.** `/mcp` is mounted on the *same* FastAPI app as the
report, so "pin the MCP port" means "pin the serve port" — and the warm-sidecar
pool keeps a parked project alive on its own port, so two live sidecars cannot
share one pinned number. And a fixed port buys a collision support burden that
Figma demonstrably carries.

**Conclusion:** keep `bind(0)`, and treat the handshake as carrying the
*credential* first and the address second. That framing also explains why the
`instance_id` probe (§3.1) is worth its six lines: with a moving port we must
prove we are talking to Bristlenose before the bearer leaves the machine's
memory.

### 3.2 The proxy

`server/index.js`, ~150 lines, using the official MCP SDK's own transports:
`StdioServerTransport` on the client side, `StreamableHTTPClientTransport`
(with the `Authorization` header from the handshake) toward BN, piping messages
between them.

**Not `mcp-remote`, and now for a second reason.** Figma vendors and *patches*
it, naming the patch in a source comment: [mcp-remote
#106](https://github.com/geelen/mcp-remote/issues/106) — when the server
restarts, the session id goes stale, the server 404s, and mcp-remote **errors
forever instead of re-initialising**. Figma can live with that (their port is
fixed at 3845); we cannot, because our port moves on *every* launch. So:

**The proxy must re-read the handshake and re-initialise on `404` /
`ECONNREFUSED`, not just at startup.** This is the single most important
behavioural requirement in the design — a proxy that resolves the handshake
once at boot is broken by the second Bristlenose launch, which is the ordinary
case rather than an edge.

Three constraints from the platform, all confirmed:

- **Pure JS only.** Extensions run in an Electron `UtilityProcess` under
  hardened-runtime library validation, and any `.node` native module not signed
  with Anthropic's Team ID is rejected by `dlopen` *before our JS runs* —
  "Server disconnected", nothing in the log
  ([#229](https://github.com/modelcontextprotocol/mcpb/issues/229)). A
  `fetch`-based proxy is fine; no native keychain binding, ever.
- **Never write to stdout.** A stray `console.log` corrupts the stdio protocol.
  Figma's shipped proxy has zero of them and uses `console.error` throughout.
- **Be version-tolerant against the API.** Locally-installed extensions
  **never auto-update** (Claude Desktop's update check explicitly skips
  `local.mcpb` / `local.dxt` ids), so the installed proxy will lag Bristlenose
  indefinitely. It must degrade rather than break when the server moves ahead —
  which is easy here, because it forwards messages rather than interpreting
  them.

**Do NOT copy Figma's two-server shape.** Theirs is `runProxy(url)` throws →
`startFallbackServer()` connects a *different* server to the stdio transport —
and once that is connected there is no upgrade path. A researcher who launches
Claude Desktop *before* opening Bristlenose gets the apology tools for the whole
session, and the only fix is relaunching Claude Desktop: the exact restart cost
§1 spends a page arguing against. Copying it would reintroduce the thing we are
deleting.

**One server, four real tools, registered once.** The decision is made *per
call*, not once at boot:

| Per tool call | What the agent gets |
|---|---|
| Handshake fresh, server answers | The real result, proxied. |
| No handshake, or host process gone | The tool returns the "Bristlenose isn't open" text. |
| Handshake present, health probe fails | Same, with the reason named. |

This self-heals the moment Bristlenose starts serving — no relaunch, no
stickiness — and it is what makes Option A (§3.3) real rather than nominal:
**the handshake is re-read on every tool call**, so switching project in
Bristlenose changes the agent's subject on the next question. A proxy that
resolves the handshake once at startup would pin whatever was fronted when
Claude Desktop launched, which is the opposite of what §3.3 promises. A stat +
read of a sub-1KB file per call is free; re-create the HTTP client when the
port or token move.

Probe with `/api/health` — it is auth-exempt and records no activity. Never
probe with a real tool: that would light the sidebar antenna with no researcher
present.

Three cases, three sentences — the proxy can tell them apart and the fixes
differ. Written for the *model* as much as the human, because a model handed
"no data" will sometimes apologise and then answer from memory anyway, and a
confidently fabricated finding is the worst failure this feature has:

> Bristlenose isn't open, so there is no study data available. Tell the person
> to open Bristlenose and select a project, then ask again. **Do not answer
> from memory or from general knowledge.**

That last clause is the same family as `INVARIANTS` in `grounding.py` and
should live beside them. Note the vocabulary: *"isn't open"*, never *"isn't
serving"* — the researcher does not know Bristlenose serves anything.

The fallback is most of what makes this *non-error-prone*: the tools are always
listed, and the ordinary failure is a sentence telling the researcher what to
do. (Not *all* — see §5a for the one state that is genuinely broken.)

### 3.2a The subject-change announcement — SUPERSEDED by the Option B decision

_Kept because it is the argument that produced the decision, not because it
ships. Under Option B the agent is pinned to one project, so there is no
subject change to announce. If Option A is ever revisited, this section is why
it needs more than labelling — and why labelling isn't enough._

Under Option A (§3.3) the agent's subject would follow Bristlenose. The failure that
matters is not technical:

> Researcher asks Claude about IKEA. Alt-tabs to Bristlenose to check a quote,
> clicks the Nurses study in the sidebar — an entirely innocuous act; clicking
> a sidebar row is not a "change my agent's subject" gesture in anyone's model.
> Alt-tabs back. Types "and how did that compare on cost?" Gets a confident
> answer about Nurses, in a scrollback that is otherwise all IKEA. Pastes it
> into a report.

Nothing marks the switch. "Every tool payload carries the project" is passive
metadata in a JSON blob, and a model summarising for a human drops it nine
times in ten.

**So make it an event, not a field.** The proxy is long-lived for the client's
session. It holds `lastSeenProject`, and when the project changes between two
tool calls it **prepends a marked line to the very next tool result**:

> **Note: Bristlenose is now showing a different study — "Nurses onboarding"
> (previously "IKEA discovery"). Everything below is from "Nurses onboarding",
> which is not anonymised.**

Models relay in-band notices far more reliably than metadata fields. The
anonymisation clause is appended **only when it differs from the previous
project** — otherwise the governance boundary moves without a gesture: IKEA
anonymised, Nurses not, and real names start appearing in a chat the researcher
believes is anonymised. §6a records the anonymise decision as "the choice
belongs to the researcher everywhere"; this is the one path where it could
change without the researcher choosing.

~10 lines in the proxy, and it is the single highest-leverage thing in this
design.

### 3.2b Answer `initialize` fast

Claude Desktop times out the `initialize` handshake at **60 seconds**, and
starts every configured server *in parallel* at app launch — so a slow start
can be pushed over the line by someone else's extension. Everything slow
belongs *after* the handshake, never before it: read the handshake file, answer
`initialize`, and only then attempt the HTTP connection. The worst observed
version of getting this wrong is not a broken connector but a broken *client* —
a blocking connect-retry during startup pushed one bridge past the deadline and
*"completely breaks the entire host client and prevents all my other MCP servers
from loading"*. In particular the
fallback decision must not be made by waiting on a connection attempt with
retries — decide from the file's presence and liveness, and let the first real
tool call discover a dead server.

### 3.3 Scope model — the decision worth taking deliberately

Today's model is **per-project**: a token per project, a config entry naming one
project. With an extension there is a second option, and it is simpler.

**Option A — follow the fronted project (recommended).** One extension. It
connects to whatever Bristlenose is currently serving. Switching project in BN
switches what the agent can read.

- Matches the mental model: *ask about what I'm looking at.*
- Removes re-configuring per project entirely — the thing that makes the
  current path feel like work every single time.
- The per-project **Anonymise** switch still applies correctly, because it
  travels with the project the server is serving — *mechanically*. But note
  what Option A does to it in effect: the grant became global while the
  compliance control stayed per-project. The researcher turns Anonymise ON for
  the sensitive study, fronts a different project whose switch is off by
  default, and names flow with no interaction and no signal. §3.2a's
  announcement is the minimum mitigation; the real options are an instance
  default with per-project override, or strictest-wins while an agent is
  active. Worth deciding alongside Finding 74 (the consent-version bump)
  rather than after.
- Risk: the agent's subject can change under it. Mitigations — every tool
  payload already carries the project, `get_project_overview` leads with it, the
  server `instructions` state that the project may change and the overview is
  the authority, and BN's sidebar antenna shows *which* project is exposed.

**Option B — pin to one project.** `user_config` could hold a project path.
Keeps the narrow grant, reintroduces per-project setup.

**DECIDED 31 Jul 2026: Option B.** Not on UX grounds — A is friendlier — but
because A has a failure mode no labelling can reach.

**The case that settles it.** A researcher may keep a study on local models
(Ollama) *precisely because* they are contractually barred from putting that
data on a network. Under Option A, merely clicking that project in the sidebar
while an agent is connected sends its quotes to a cloud model vendor. And
§3.2a's announcement cannot save it: the notice is prepended to the tool result
that *already carries the quotes*, so the warning and the disclosure arrive in
the same message. A project that was never meant to be exposed gets exposed by
a gesture that means "let me look at this", with the contractual breach already
committed by the time anything is said.

"The researcher can already see both projects on the same trackpad" is true and
irrelevant — what changes is not who can *see* the data but whether it crosses
the network. That is the line the researcher signed something about.

So: **exposure must be an explicit act.** `user_config` with
`type: "directory"` is the mechanism, exactly as Anthropic's own filesystem
extension uses it — the researcher picks a folder once, in Claude Desktop's own
UI, and it interpolates via `${user_config.…}`.

**v1 scope: one project.** The researcher picks that project's folder.

### 3.3a Folder grant — the phase-2 shape, and why it's the better end state

Recorded now because it changes nothing in v1 but must not be foreclosed by it.

A per-folder grant is not merely a bigger unit of scope. **It makes the sidebar
folder the exposure control**: grant a folder once, then move projects
deliberately into and out of it. Exposure becomes direct manipulation — a drag
— which is both the most Mac-native way to express consent and the most
legible. The secret Ollama-only study simply never gets dragged in, and pulling
a project out is a revocation gesture that needs no dialog.

It also unlocks the capability we actually want: **asking questions across a
whole folder** — the cross-study querying that `design-mcp-server.md` §3b
describes, where a code re-used across unrelated projects is the continuity
carrier.

**What v1 must not foreclose**, so this drops in rather than being rewritten:

- **The `user_config` field is already right.** `type: "directory"` points at a
  folder path — a *project* folder in v1, a *folder of projects* in phase 2.
  Same field, same picker, no manifest change.
- **The tools are already right.** Every one takes `project_id`
  (`design-mcp-server.md` §9); folder scope adds a project *set* rather than a
  new signature.
- **The handshake must be keyed, not singular.** v1 can write one file for one
  project, but the schema should assume a *set* is coming — don't bake
  "the project" into the shape.
- **The badge generalises upward.** Under folder grant the antenna belongs on
  the folder row, with every project inside inheriting it.

**And one hazard to design against when it lands.** Dragging a project into a
granted folder is a one-second act with contractual consequences — the same
class of quiet exposure that killed Option A, only now the gesture is
deliberate. So the folder must *look* exposed: antenna on the folder row and on
every project inside it, not just on the folder. Cheap, and it keeps the drag
honest.

**But A behind a per-project right-click is a lie, and that must be fixed in
the same pass.** Right-click *IKEA discovery* → a sheet headed "Connect an
agent to 'IKEA discovery'" → Install. Every part of that gesture says *you have
connected this project*. Under A you have not: you have connected the machine,
and the subject is whatever is selected. A researcher who believes they granted
one study and later finds the agent read another will experience that as the
app having lied at the moment of granting — and this is a consent surface. The
scope line exists precisely so "what was right-clicked is unambiguous at the
moment of granting" (§6a); under A that line describes *status*, not *scope*,
without a word changing.

Two fixes, both cheap:

- **The header states the model.** "Agents read whichever project is selected
  in Bristlenose", with the project + counts underneath as *current state*
  rather than as a grant.
- **Consider moving the install act out of the per-project sheet** — installing
  is a once-ever, machine-wide setup act, not a per-project one. See §7 Q6.

### 3.4 What the researcher does

1. In Bristlenose: **Connect Agent…** → Claude Desktop.
2. Click **Install Extension…** (ellipsis: the action completes in *another*
   app). `NSWorkspace.shared.open` on the `.mcpb`; LaunchServices hands it to
   Claude Desktop, which runs its own install flow. The sheet dismisses on a
   successful hand-off — otherwise Claude Desktop comes forward and strands a
   modal behind it.
3. No token, no port, no JSON, no re-paste when the port rotates.

Three implementation details that are not incidental:

- **Open, don't reveal.** Reveal-in-Finder is a worse gesture in a safer
  costume — it converts a one-click promise into "here's a file, you figure it
  out", which is most of the way back to hand-pasting. The Mac idiom for one
  app handing a plug-in to another is a typed file you double-click
  (`.alfredworkflow`, `.sketchplugin`, `.mobileconfig`); Claude Desktop's own
  Extensions pane is the same shape.
- **Don't hand LaunchServices a path inside our bundle.** `Contents/Resources/`
  changes on every app update and can be replaced under a running Claude
  Desktop. Copy the `.mcpb` once into the container beside the handshake file
  (`…/Application Support/Bristlenose/Bristlenose.mcpb`, `0644`), refresh when
  the bundled copy is newer, and open *that*.
- **Claude Desktop might not be installed.** `NSWorkspace.open` with no
  registered handler produces the system's "There is no application set to open
  the document" dialog — nobody's voice, no next step, and the researcher reads
  it as our bug. `NSWorkspace.urlForApplication(toOpen:)` answers this with no
  entitlement: when it returns nil, the tab says so and offers the download
  link instead of a live button.

**What the tab must NOT contain: a code block.** A bordered monospace box next
to an Install button is a copy affordance, and putting one there re-opens the
door Finding 86 closed ("so do I copy this *and* click Install?"). Keep the
fixed pane height — geometry is fixed, content bends — and fill it with what
the extension is and what clicking does.

**And it needs a status line**, because on visit two the researcher isn't
asking what the button does, they're asking whether it took. We cannot read
Claude's container — but we observe the better fact from our own end:
`mcp.active` on `/api/health` already means *an agent called a tool*. "An agent
has asked about this project recently" / "No agent has asked yet" is free
today (`serveManager.agentActiveNow` is already plumbed into the sheet's host).
Do **not** persist "we opened the file once" and call it Installed — we don't
know they didn't cancel Claude's confirm.

Claude Code and ChatGPT/Codex tabs are unchanged (`claude mcp add` edits their
config correctly *as a command*; the Codex TOML append is forgiving). Their
fragility is not the same.

### 3.5 The other two tabs, and where "any other agent" goes

**Claude Code is unambiguous.** `claude mcp add` writes Claude Code's own
config (`~/.claude.json`), which is separate from
`claude_desktop_config.json` — verified. So the command is correct whether the
researcher runs Claude Code in a terminal or inside the Claude Desktop app, and
the tab label needs no disambiguation.

**ChatGPT & Codex get the same improvement, and it isn't a big thing.** One
`~/.codex/config.toml` covers ChatGPT desktop, the Codex CLI and the IDE
extension, and TOML append is far more forgiving than JSON (a new `[section]`
at the end just works — no comma arithmetic, no destructive rewrite). So the
fragility that killed the Claude Desktop path is not present here. But they
still carry a port and a token that both rot, and `bristlenose mcp-proxy`
(§7 Q3) fixes that for them exactly as it does for Claude Code:

```toml
[mcp_servers.bristlenose]
command = "bristlenose"
args = ["mcp-proxy"]
```

Worth noting ChatGPT desktop also has **Settings → MCP servers → Add server**,
its own form — so many researchers never edit the file at all. There is no
`.mcpb` equivalent for ChatGPT (their Plugins need public HTTPS), so the form
plus the TOML is the ceiling; one-click install is a Claude Desktop-only
affordance.

**The wrinkle: `bristlenose` is not on PATH for a desktop-only researcher.**
The CLI binary comes from pip/brew/snap; the desktop app carries its sidecar
inside the bundle at
`/Applications/Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar`
(which already accepts subcommands). Two options, decide before writing the
tab copy:

- **Absolute path into the bundle**, which is what Proxyman ships
  (`/Applications/Proxyman.app/Contents/MacOS/mcp-server`). Survives app
  updates in place; breaks if the researcher moves or renames the app.
- **A small stable launcher** written into the container dir we are already
  writing the handshake into, kept current by the app, pointing at whichever
  sidecar is live. Survives moves — but it is a generated executable another
  app then runs, which wants an `app-store-police` read before it ships.

**And the footnote must become per-tab.** "Works with any MCP-compatible agent"
is true of the *server* and false beside an Install button — a `.mcpb` is
Claude Desktop-only. It stays on the Claude Code and Codex tabs; the Claude
Desktop tab gets something true ("Installs into Claude Desktop. Other agents
connect their own way.").

### 3.5a The generic MCP path must keep a home

**The endpoint is unchanged.** `/mcp/` remains a plain streamable-HTTP MCP
server with a bearer token; any compliant client can connect to it. The
extension is a delivery mechanism for *one* client, not a replacement for the
endpoint, and "works with any MCP-compatible agent" stays true of the server.

**But the plan as drafted starves that path.** With Claude Desktop becoming an
Install button and the other two tabs moving to `bristlenose mcp-proxy`, no tab
shows the raw URL and token any more. An earlier draft of this doc said the
manual page was the home for them; that is wrong. The manual can document the
*shape*, but the researcher needs the *live* values — a port that changes every
launch and a per-project token — and a static page cannot carry those.

**DECIDED: a fourth tab, "Generic MCP".**

An earlier draft argued for a disclosure instead, on the grounds that the
separate "Other agent" affordance had already been deleted in favour of a
statement. That objection was stale. The affordance was cut when all three tabs
showed the *same* URL+token payload and a fourth was a literal duplicate. Each
tab now shows something genuinely different — an install button, a shell
command, a TOML block — so the fourth is no longer redundant; it is the only
home for a whole class of client.

It resolves two problems at once:

- **The footnote disappears.** "Works with any MCP-compatible agent" was doing
  the work of a missing tab, and next to an Install button it was actively
  wrong (§3.5). With a Generic MCP tab, the picker *is* the statement, and it
  is actionable rather than reassuring.
- **The name is correctly self-selecting.** "Generic MCP" is jargon, and that
  is the point: anyone who needs this tab is running an MCP client and knows
  the word. A researcher who doesn't will never reach for it, because the three
  named tabs cover them. ("Other" is the softer, more Mac-ish word but loses
  the signal — worth a look on real pixels before it's fixed.)

**It is also the fallback that makes "replace the hand-paste path" safe** — but
be precise about what it does and doesn't cover. Review log #27 argued for
keeping hand-paste as a labelled fallback, because the extension route carries
more machinery (Node resolution, TCC, install UI, version skew) whose failures
are *less* diagnosable than a JSON syntax error. The Generic MCP tab answers
most of that: a researcher whose extension silently fails is not stranded, and
the escape hatch is a *safe* one — hand over two values to a client that
accepts them directly, rather than hand-edit another app's settings file.

The honest limit: it is a fallback across *clients*, not within Claude Desktop.
A Claude Desktop user whose extension won't install can reach for Claude Code
or Codex, but Claude Desktop itself still has only the destructive JSON path —
which is precisely why we are not documenting that path any more.

**Order the picker by frequency, not alphabet.** The three named clients are
the ~90% case; Generic MCP goes last. It is the tab most people never open, and
the one its audience will find immediately.

**It is the desktop counterpart to the CLI connect block**, which already does
exactly this job. `_print_mcp_connect` prints the two primitives and the
permanent docs URL and — per its own comment — *"never a vendor's command:
dialects rot, so they"* live in the manual. That division holds across both
surfaces and is worth keeping deliberate:

| | Vendor dialects | Raw primitives |
|---|---|---|
| **CLI** | in the manual (they rot) | printed on `serve` |
| **Desktop** | the three named tabs (a UI can carry them and keep them current) | the Generic MCP tab |

So the desktop isn't inconsistent with the CLI — it adds dialects *because it
can update them with the app*, and keeps the same neutral fallback underneath.

### 3.5b Gemini — checked, and deliberately not a v1 tab

Researched 31 Jul 2026 rather than assumed. Two Gemini surfaces speak MCP:

- **Antigravity** (2.0 IDE + the `agy` CLI + the SDK) shares one central config
  at `~/.gemini/config/mcp_config.json`, keyed `mcpServers` — configure once,
  every surface picks it up. It accepts **remote servers via `serverUrl` +
  `headers`**, and community guidance is that headers mode is *preferred*
  because Antigravity's MCP OAuth is unreliable. That is precisely our shape:
  a URL and an `Authorization` header, no proxy required. Structurally it is
  the Claude Code / Codex analogue — developer-facing, one file covering three
  surfaces.
- **Gemini Spark** on the macOS Gemini desktop app gained MCP support on
  1 Jul 2026 — the Claude Desktop analogue, a consumer chat app. But it is in
  **beta and gated to AI Ultra at $99/month**, so its population right now is
  negligible for our cohort.

**Decision: no named Gemini tab in v1.** Not because the gap isn't real, but
because the Generic MCP tab (§3.5a) makes skipping it cost *capability*
nothing. An Antigravity user takes the two primitives from tab four and it
works today — `serverUrl` plus `headers` is exactly what that tab hands over.
What a named tab would add is convenience, and convenience for a population we
can't yet size.

Two notes for when it's revisited:

- **It would be cheap.** Antigravity is arguably easier than Codex was — same
  URL+headers shape, one config for three surfaces. A named tab is a dialect
  string, not structure.
- **Don't conflate provider with agent.** Gemini is one of Bristlenose's four
  analysis providers, so it is tempting to read "we support Gemini" as implying
  a Gemini agent path. They are separate choices: the model that ran the
  analysis and the agent the researcher chats in have nothing to do with each
  other, and a researcher analysing with Gemini may well be asking questions in
  Claude Code.

Revisit when either Spark leaves beta/Ultra, or a cohort researcher asks.

One geometry note: four segments in a 560pt sheet is about 130pt each, and
"ChatGPT & Codex" is the longest label. Check it on real pixels; if it crowds,
the fix is shorter labels, not a narrower sheet.

Two things worth knowing about that path:

- **Its scope semantics are already Option B**, with no extra work. Each
  project's serve has its own port *and* its own token
  (`MCPTokenStore` is keyed per project), so a URL+token pair names one
  project's sidecar. A generic client cannot wander between projects the way
  Option A would have allowed.
- **It keeps the rotating-port problem**, because there is no proxy in front of
  it to re-resolve. That is honest and fine — it just means the tiers differ:
  one click for the client we can ship an extension for, one command for the
  clients with a CLI, and copy-two-values-and-re-copy-after-restart for
  everything else. Say so on the tab rather than letting it be discovered.

**How to say it — `INFO`, not `WARNING`.** Checked against the HIG and against
our own taxonomy, which agree:

- HIG `patterns/feedback.md`: *"match the significance of the information to
  the way it's delivered"*, and warn *"when they initiate a task that can cause
  data loss that's unexpected and irreversible… don't warn when data loss is
  the expected result"*. Nothing here is lost or irreversible — a config goes
  stale and is re-copied.
- `MessageKind.WARNING` in `bristlenose/ui_kinds.py` means *"recoverable /
  partial / soft-degrade"* — something that **has** gone wrong in a run. This
  hasn't. `INFO` is *"neutral note"*, which is the closest existing kind, and
  `design-pipeline-diagnostic-popover.md` requires fitting new messages into
  the five-kind vocabulary rather than inventing a glyph.
- Two more reasons not to reach for ⚠: it would appear on **every** view of the
  tab, permanently, and warnings that never go away stop being read; and BN has
  real warnings (partial runs, missing models) that need the glyph to keep its
  meaning.

So: **`info.circle`, `.secondary`** — not `exclamationmark.triangle`, not
yellow or orange. Per HIG `foundations/color.md` (*"avoid relying solely on
color… use text labels or glyph shapes"*), the glyph and the words carry it and
colour is not load-bearing, which also keeps it legible for colour-blind
readers and in both appearances.

**And the text does the work the glyph shouldn't.** The current line states a
fact; it should name the moment and the remedy, per HIG `foundations/writing.md`
(*"guide people on actions they can take"*):

> ℹ The port number changes each time Bristlenose starts — copy the address
> again after a restart. Your token stays the same.

**Be exact about which half moves, because the two channels invert.** In the
desktop app the address is kernel-assigned (`--port 0`) so the port changes
every launch, while the token is durable per project from the Keychain. On the
CLI it is the other way round: `serve` defaults to port 8150 (stable, for
bookmark-and-reload) and the token is a fresh `secrets.token_urlsafe(32)` per
start. So:

| | Address | Token |
|---|---|---|
| Desktop app | changes every launch | stable (Keychain, per project) |
| CLI `serve` | stable (8150) | changes every restart |

The Generic MCP tab lives in the desktop sheet, so desktop semantics apply and
"the port changes, the token doesn't" is the accurate line. The website's
connect page already forks this correctly per channel — keep them in step if
either changes. (Caveat for QA builds: on ad-hoc signing the Keychain write
fails with -34018 and the token falls back to the rotating one, so a *local*
build behaves like the CLI. That is a build artefact, not the shipped
behaviour.)

Saying the token is stable is also honest disclosure rather than mere
convenience: it tells the researcher that what they handed over persists until
revoked, which is the fact the Revoke affordance (review-log Finding 72) is
owed against.

One observation worth keeping in view: that this line needs saying at all is a
property of the *path*, not the copy. On the three named tabs the problem does
not exist — the extension and `mcp-proxy` both re-resolve. The caveat is the
price of the generic path, and the right long-term measure of success is that
most researchers never open tab four.

### 3.7 Where does this live? — the entry point, reopened by Option B

Option B changed what the sheet can actually *do*, so the per-project
right-click needs re-deciding. Two facts first, because they constrain
everything:

- **Bristlenose cannot perform the Claude Desktop grant.** Under B the project
  is chosen in Claude Desktop's own directory picker (`user_config`), and the
  premise of this whole plan is that we cannot write their config. For that tab
  we can only *instruct*: install this, then point it at this folder. A
  right-click on project X that says "Connect Agent" promises something that
  path cannot deliver from our side.
- **`user_config` is per-extension**, and extension identity is the manifest
  `name` (which must be globally unique). So one install grants one project,
  changed by editing the extension's settings inside Claude Desktop. That is
  Option B's real friction cost, and it should be stated rather than discovered.

The six jobs, and their true lifetimes:

| | Job | Lifetime |
|---|---|---|
| J1 | Install the extension | once, machine-wide |
| J2 | Point the extension at a project | per project — **happens in Claude Desktop**, we can only name the path |
| J3 | Claude Code / Codex command | per project |
| J4 | Raw URL + token (Generic MCP) | per project |
| J5 | Anonymise | per project — ours |
| J6 | See which project is exposed | per project — the badge |

Only J1 is machine-wide. That is the whole of the mismatch.

**The sane options:**

1. **App-level only** — Settings ▸ Connections, or a `Bristlenose ▸ Connect
   Agent…` menu item, owning J1–J4 with a project picker inside.
   *Against:* four of the six jobs are per-project, so the pane must re-ask
   "which project?" — reintroducing a selection the sidebar already expresses,
   and losing the "what I right-clicked is what I'm granting" clarity.
2. **Split by lifetime (recommended).** J1 (+ install status) moves to
   Settings ▸ Connections; the per-project sheet keeps J2–J5 and links to
   Settings for install. The Claude Desktop tab becomes instructional and
   genuinely useful: *"Install the extension in Settings, then point it at this
   folder"* with the path and a **Reveal in Finder** — which is exactly what
   the researcher needs in Claude's picker.
   *Against:* two places. But they are two genuinely different lifetimes, which
   is the honest reason for two places rather than an accident.
3. **Menu bar only** — one `Connect Agent…` window with a project selector at
   the top. Self-contained, but it duplicates the sidebar's job of expressing
   which project you mean.
4. **Make the antenna badge the entry point** — click the exposed-project glyph
   to open the sheet. Attractive as direct manipulation, but it collides with
   the settled sidebar rule that status is *attention, not affordance* (the
   Mail model). Flagging, not proposing.
5. **Leave it as-is** — keep the per-project right-click and accept that its
   Claude Desktop tab is instructional. Cheapest, and defensible *if* the copy
   is honest about what the researcher must do in Claude Desktop. It is the
   right answer if we want zero structural change before the TCC spike settles.

**DECIDED (31 Jul, after the options above): a global home — Settings ▸ MCP
Agents**, with `Bristlenose ▸ Connect MCP agent…` as a route to it and a
Welcome-screen entry for discovery. This supersedes the "split by lifetime"
recommendation below; the reasoning that produced it is kept because it is how
the constraint was found.

**First, a technical correction that strengthens Option B rather than
undermining it.** Per-project connection *is* possible: each serve process
serves one project on its own port with its own token, so a URL+token pair
names one project's sidecar. What is not under the researcher's control is
**availability** — only the fronted project has a live serve, plus at most one
parked in the warm pool's single slot. So a pinned agent will often find its
project not running.

The consequence is the important bit: **the pin buys refusal, not access.**
Pinned to IKEA while the researcher is looking at Nurses, the agent answers
*"open Bristlenose and select IKEA"* rather than silently answering about
Nurses. The Ollama-only study is protected not because the agent cannot reach
it, but because the agent will not answer about anything it was not pinned to.
That is precisely the property Option B was chosen for, and it survives the
availability constraint intact.

**Why the home is global.** Bristlenose cannot perform the grant — Claude
Desktop's directory picker does. BN's controllable share is installing the
extension, showing status, and handing over values: overwhelmingly global, with
the project as a *parameter* of a connection rather than the frame around it.
That also mirrors how Claude Desktop itself models it — a connector in Settings
with its own project config inside.

**The pane does not change shape with project state.** Installing is a
higher-order concern than which project is open — a researcher who opens
Settings from the Welcome screen is doing setup, and the pane has no business
showing an empty state or telling them to go and select something first. So:

- **Header, always:** *"Agents read whichever project is selected in
  Bristlenose."* That switching projects changes what the agent can see is
  **not obvious and not intuitive**, and saying it plainly is the v1 answer to
  a genuinely surprising behaviour.
- **Sub-line, when there is one:** *"Now showing: IKEA discovery · 6 sessions ·
  214 quotes."* A for-example line that makes the header's rule legible by
  demonstrating it. With no project selected it simply **disappears** — no
  placeholder, no dash, no "no project selected". Absence is the information.
- **Cut with it:** the old "Bristlenose isn't running a project" state, which
  was a hangover from the per-project sheet. Under a global home it answered a
  question nobody asked.

**Three consequences to settle with it:**

1. **What happens to the per-project sheet?** Its Claude Code / Codex / Generic
   MCP payloads are genuinely per-project, so Settings needs a project
   selector to produce them — which is the objection raised against option 1
   above, now answered: the selector is a parameter, not a re-asking of what
   the sidebar already said. The right-click item can then retire, or become a
   shortcut that opens Settings pre-selected to that project.
2. **Where does Anonymise live?** It is per-project data governance, and it sat
   in the connect sheet only because that was the MCP surface. If MCP config
   becomes global-with-a-project-parameter, it sits naturally beside the
   project row there. The alternative reading — that it belongs *with the
   project*, like its name and icon — is also defensible and worth a moment.
3. **The Welcome-screen entry is the discovery answer**, and it is the right
   one: §5a records that the extension solves *installation*, not *discovery* —
   a researcher who never learns the feature exists is not helped by a
   one-click install. Welcome is where that gap closes.

**Naming — and a rename of a shipped tab.** The Settings tabs become
**Appearance · LLM Provider · Transcription · MCP Agents**.

"MCP Agents" over "Connections" (too vague); the jargon is correctly targeted,
since the researcher meets "MCP" in Claude Desktop's own "Local MCP servers"
pane. And renaming the existing `LLM` tab to **LLM Provider** earns its churn:

- **It separates the axes.** Bare "LLM" beside "Agents" reads as two flavours
  of one thing. "LLM Provider" vs "MCP Agents" says which model does the
  analysis (in) versus which agents can read the results (out).
- **"LLM" names a domain, not a setting.** The pane is a provider list plus
  detail (the Mail Accounts shape), so *Provider* is what it configures — and
  it is already the codebase's own word (`bristlenose/llm/CLAUDE.md`).
- **The singular/plural asymmetry is deliberate:** one *Provider* (only one is
  active, by design), several *Agents* (Claude Desktop and Codex can both be
  connected). The labels encode a real difference.
- **Widths are fine** — "Transcription" (13) remains the longest.
- **Cost:** one string × 20 locales (`settingsTabs.llm`), immediately after the
  seeding pass. Small, and cheaper now than once the cohort has muscle memory.

Icon: the antenna, matching the sidebar badge — one concept, one symbol, two
surfaces. Position: last, since Appearance is chrome and the other two are the
engines, while who can read your work is a fourth concern.

**Why the two-word form actually helps comprehension, not just symmetry:** the
acronym is the *qualifier*; the **noun carries the meaning**. A researcher who
does not know what "LLM" stands for still understands *Provider* — you must
have one. A researcher who has never heard of "MCP" still understands
*Agents* — an agent is a thing you talk to. Bare acronyms gave them no such
fallback. This is the argument that makes the pair worth the rename even
setting parallelism aside.

### 3.7a Blast radius of the rename + new tab — measured

| Surface | Affected? | Detail |
|---|---|---|
| **Desktop Settings tabs** | **Yes** | `desktop.settingsTabs.llm` → `LLM Provider`, plus a new `settingsTabs.mcpAgents`. Consumed by `SettingsView.swift`. |
| **Locale files** | **Yes** | Both keys × **20 full locales** (not `zh-Hant-HK` — thin override fork). Plus the new pane's own strings. |
| **SPA settings nav** | **No** | Entirely separate taxonomy: General · Project · Profile · API Keys · Config · Pipeline (`settingsNav` in `settings.json`). There is no "LLM" tab there to rename, and **MCP config is desktop-only** (install, sharing), so the SPA gains nothing. |
| **SPA config reference** | **No — and it already agrees** | `configReference.categories.llm` is already **"LLM Provider & Model"**. So the desktop rename *increases* cross-surface consistency rather than creating a divergence. No MCP category needed: the MCP settings are a DB flag and an optional extra, not env vars a researcher sets. |
| **CLI** | **No** | No settings UI. The man page already says "LLM provider" in prose (`.SS LLM settings`, §OPTIONS) — descriptive text, not a label, and already consistent. |
| **README / man page** | **No** for the rename | Neither documents the desktop Settings tabs. |
| **Website docs** | **Yes, later** | `docs-src/connect-an-agent.md` currently describes the right-click sheet; it must move to Settings ▸ MCP Agents when that ships. Use the `::: fork` channel mechanism — this is a **Mac-app-only** flow. |

**Two gaps this surfaced, both worth stating rather than discovering:**

1. **The CLI has no share toggle, and now no MCP settings surface either.** It
   already lacks the Anonymise switch (§SECURITY). So a CLI user can serve
   `/mcp` but cannot express *which* projects may be read — because on the CLI
   the answer is "the one you served", which is arguably the honest equivalent.
   Worth confirming rather than assuming that is acceptable.
2. **Nothing renders `settingsTabs` outside the desktop**, so the rename cannot
   break the SPA or CLI. That is a genuinely small blast radius — the cost is
   translation volume, not integration risk.

---

_Superseded recommendation, kept for the reasoning:_ **2**, with 5 as the
acceptable interim. The split matches the
two real lifetimes, it is what the Mac review independently argued for, and it
removes the "machine-wide act inside a per-project consent sheet" mismatch
without inventing a new surface. Reveal-in-Finder is the small piece that makes
the instructional tab actually work.

**One thing to settle either way:** the sheet's header. Under B the grant *is*
per project, so "Connect an agent to 'IKEA discovery'" is honest again — but
only for J2–J5. If J1 stays in the sheet, the header over-promises.

## 4. Packaging

```
desktop/mcpb/
  manifest.json
  server/index.js         # proxy + fallback, bundled to ONE file
  icon.png                # 512x512 png
  .mcpbignore             # .env* — `mcpb pack` does NOT honour .gitignore
desktop/scripts/build-mcpb.sh   → build/Bristlenose.mcpb
```

**Bundle to a single file (esbuild/rollup); do not vendor `node_modules`.**
Anthropic's own advice once the tree is non-trivial, and it sidesteps four
separate traps at once: native-module library validation, the missing
CPU-arch field in the manifest schema, the undocumented size ceiling, and the
`NODE_MODULE_VERSION` ABI mismatch (`mcpb pack` does not warn about `.node`
files). Our proxy is `fetch` plus the SDK — it bundles cleanly.

Three manifest values that are not cosmetic:

- **`compatibility.claude_desktop: ">=1.13576.0"`.** Below that build, a
  `yauzl` deflate deadlock hangs the unzip on any deflate-compressed entry
  over ~16 KB — which is every realistically-sized bundle. Declaring the floor
  turns "nothing happened" into a version message.
- **`compatibility.runtimes.node: ">=18"`** — modest, so the built-in Node
  stays in range (§5a).
- **A globally unique `name`, with no version string in it.** Claude Desktop's
  enterprise allowlist identifies extensions *by manifest name*, and a version
  inside it has been reported to stop the extension appearing at all.

Built by `mcpb pack`, copied into `Contents/Resources/` by the existing Copy
Sidecar Resources phase, and gated the way the other bundle contents are (a
`doctor --self-test`-style check that the `.mcpb` is present and its manifest
parses).

Settled by the research pass:

- **`manifest_version: "0.3"`.** `0.4` exists but the published
  `mcpb-manifest-latest.schema.json` is byte-identical to 0.3 — declaring 0.4
  and validating against "latest" fails.
- **Pin `@anthropic-ai/mcpb@2.1.2`** (published Dec 2025; the repo has been
  quiet ~8 months with structural bugs open — don't assume fixes land).
- **No signing.** `mcpb sign` is non-functional end to end (`node-forge`'s
  `pkcs7.verify()` is an unimplemented stub); Anthropic's own Filesystem
  extension records `"signatureInfo": {"status": "unsigned"}` on this machine.
  Local install works unsigned and signing buys nothing today. Don't budget for
  it — and don't rely on it as an integrity story.
- **Size is not a concern.** No documented cap for extensions (the 30 MB limit
  in the shipped app applies to Skills); Figma's is 21 MB unpacked, 20 MB of it
  `node_modules`. Ours is a proxy — far smaller.
- **Set `tools_generated: true`** in the manifest. It makes Claude Desktop skip
  live tool verification at install, which is *what lets the fallback server
  work when Bristlenose isn't running* — without it, installing while the app
  is closed is a worse experience.

### 4a. Supply-chain obligations the JS tree creates

Bundling to a single file (above) keeps this small, but it is still new
third-party code inside a signed, notarised bundle, and the repo's existing
machinery does not cover it:

- `.github/dependabot.yml` covers `pip:/`, `npm:/frontend`, `npm:/e2e` — add
  `npm:/desktop/mcpb`.
- CI's `npm audit` / `npm sbom` run in `frontend/` only — extend.
- `THIRD-PARTY-BINARIES.md` opens with *"every non-Bristlenose binary that
  ships in `Bristlenose.app/Contents/Resources/`"*, which becomes false the day
  the `.mcpb` lands. Widen it from "binary" to "third-party code" and add a
  generated npm section.
- **A build gate that fails if the packed `.mcpb` contains any Mach-O**
  (`.node`, `.dylib`) — the day a transitive dep grows one is the day an
  unsigned binary silently enters a notarised bundle. Same class as
  `check-bundle-manifest.sh`; the pattern is established.
- One honest sentence in SECURITY.md: the proxy runs under the *client's* Node
  runtime, which is outside Bristlenose's signing boundary. A drawn boundary is
  defensible; a silently-crossed one is not.

### 3.6 What Option B changes elsewhere

Five open items resolve, one grows, one new question appears.

**Resolved by the decision:**

- **The sheet header is honest again.** "Connect an agent to 'IKEA discovery'"
  describes a real per-project grant, so the review finding that it implied a
  grant it wasn't making (log #22) dissolves. No model-stating line needed.
- **The Anonymise hole closes** (log #11). The project is pinned, so its
  Anonymise setting is the only one in play — no fronting a different project
  and having names flow with no interaction.
- **The subject-change announcement is unnecessary** (§3.2a).
- **The parked-sidecar correctness bug softens** (log #21). The agent is bound
  to a project, not to whatever is fronted, so parking no longer silently
  redirects it.
- **`user_config` gets a job** — and it's the one field type that is safe
  (`type: "directory"`, no secret, so the `$`-corruption bug in §6.7 can't
  bite it).

**What grows: the sidebar badge.** Keep it — under B it is the *only* place the
researcher can see which project is exposed to an agent, which makes it more
load-bearing than it was under A. But note the change it needs: as shipped, the
badge follows the **fronted** serve (`agentActiveProjectPath` is
`currentProjectPath` when `mcp.active`). Under B an agent can be connected to
project X while the researcher is looking at Y, and X's sidecar is *parked but
alive* — so the badge must be able to light on a **non-fronted** row. That
means per-project activity, not fronted-serve activity: either the handshake
mechanism reports per project, or the parked sidecar's health is polled too.
Scope note rather than a blocker, but it must land with B.

**The new question: where does the handshake live now?** Option B opens a door
that may delete the TCC gate entirely (§6.1) — if the handshake sits in the
**project folder the researcher explicitly picked**, the proxy reads a path
the user granted through Claude Desktop's own directory picker, and no app
container is read at all. Bristlenose already writes `bristlenose-output/` into
that folder and holds a lifetime security-scoped bookmark for it.

But it trades one risk for another, and this machine is the worked example:
the live test project is
`~/Library/CloudStorage/Dropbox/project-ikea3-on-dropbox-remote` — **a token
written into that folder syncs to Dropbox.** That is the same off-machine
replication the security review flagged as the worst variant (its symlink
finding), arrived at by design rather than by attack. Three ways out, to weigh
in the morning: keep the handshake in the container and accept the TCC
question; put only the *port* in the project folder and keep the token in the
container; or make the token `sensitive: true` in `user_config` so Claude
Desktop holds it in the OS keychain (at the cost of pasting a secret once, and
of bug #244 displaying it in plaintext in their settings pane).

## 5. What this does *not* change

- The MCP server, its four tools, the scoped token, and the Anonymise switch —
  all unchanged. This is a transport/onboarding change only.
- Claude Code and Codex paths.
- The sidebar antenna badge (it reads `/api/health`; the proxy's pre-flight
  probe uses the same auth-exempt route, which records no activity — a probe
  that called a real tool would light the antenna with no researcher present).
- **Egress.** The handshake is a local discovery file; the recipient set is
  unchanged, and SECURITY.md item 7 already names the agent's model vendor.
  Nothing new leaves the machine — worth saying explicitly, because it is the
  cheapest reassurance in the document.

## 5a. Checked against the objective

The objective is *friction-free, non-error-prone, just works*. Taken one at a
time, honestly, including where it doesn't hold.

**Friction-free.** Two clicks (Install, confirm) against seven steps today
(copy · find file · edit · fix commas · save · quit · relaunch). Nothing to
re-do when the port rotates, nothing to re-do per project. **Caveat pending
research:** if Claude Desktop requires a relaunch to pick up a newly installed
extension, that reintroduces the restart — and this is the app that may be
hosting the researcher's own session. If so, say it in the sheet rather than
discovering it at 1am.

**Non-error-prone.** There is no free-text entry anywhere in the flow, so the
entire class of failure from tonight is *structurally* unavailable rather than
merely discouraged. The fallback server covers the ordinary failure — the app
not being open — with a sentence naming the fix.

Two states remain genuinely broken, and the plan should not claim otherwise:
**Claude Desktop not installed** (handled at the button, §3.4) and **the proxy
failing to start at all**, in which case none of our copy runs and Claude
Desktop shows a failed extension. The second was the Node question — now
answered below, which is what lets this section make the claim at all.

**Just works — the make-or-break question, answered.** `server.type: "node"`
implies a Node runtime, and our audience is "a working researcher under
deadline, not an engineer" who will not have Node installed. "Install Node.js
first" would be worse onboarding than the JSON we are replacing, so this gated
the whole approach.

**Claude Desktop ships its own Node and uses it for MCP servers.** Verified on
this machine, from `~/Library/Logs/Claude/main.log`:

```
extension Figma: appConfig.isUsingBuiltInNodeForMcp is true and built-in node is compatible
Node.js for MCP server: Figma        nodeVersion: '24.18.0'
```

There is no `node` binary inside `Claude.app` itself, and the host's own Node
is 26.0.0 via Homebrew — neither is what ran it. So a `type: "node"` extension
works on a machine with no Node at all, which is the whole audience.

Two conditions to respect, both cheap: the log's phrasing (*"and built-in node
is compatible"*) implies a version check against the extension's declared
requirement, so keep `compatibility.runtimes.node` modest (`>=18`) rather than
chasing a recent floor; and the behaviour is behind a config flag
(`isUsingBuiltInNodeForMcp`), so the fallback to system Node should still be
survivable — vendor dependencies rather than assuming a global install.

The `type: "binary"` contingency (a small signed Swift proxy, no runtime
dependency) is therefore **not needed**, and is recorded here only so a future
reader knows it was considered and why it was dropped.

**Where friction genuinely remains** — worth stating rather than glossing:

- First-run consent inside Claude Desktop (their dialog, correct that it exists).
- The researcher still has to know the feature exists — the extension does not
  solve discovery, only installation.
- A researcher who uses Claude Desktop on a second Mac installs it twice.

## 5a-bis. The badge means exposure, not activity

**Decided 31 Jul.** The antenna is **permanent while the project is exposed** —
it says *any connected agent can read this project's quotes if the researcher
asks it to*. That is a capability, and capabilities are persistent state.

This supersedes what is built. The shipped badge is driven by `mcp.active` on
`/api/health` — a 120-second *activity* window meaning "an agent called a tool
recently". Under the share model the badge's input becomes
**shared && handshake live**, which is exposure. Activity is the weaker fact:
the researcher knows they just asked a question; what they cannot otherwise see
is that a project is reachable at all.

**Why permanent is right rather than noisy.** Exposure is precisely the state
"absence is information" is for: no antenna means not reachable, and that is
worth being able to trust at a glance. It also makes the sidebar an **audit
surface** — which pairs with the Settings list rather than duplicating it: the
sidebar answers *what is exposed right now*, Settings answers *what have I
shared*.

**Only one row can carry it.** The handshake exists for the fronted shared
project only, so at most one project is exposed at a time. Simple and honest.

**The state set — three, after cutting two.**

| | State | Meaning | Treatment |
|---|---|---|---|
| 0 | Not shared | Cannot be reached, ever | **No badge** — absence is the information |
| 1 | Shared, not open | Potential: open it and it is reachable | Pale / outline |
| 2 | Shared, serving | Exposed now | Solid |

Two candidate states were considered and cut:

- **"Starting up" (a pulse).** Cut, and the reason generalises: during those
  seconds the researcher is not looking at Bristlenose's sidebar — they are
  looking at Claude's window waiting for an answer. **A badge cannot fix a
  confusion the user is experiencing in another app.** The fix for cold start
  is the proxy's own sentence (§5b state 2), and once that exists the badge
  tier adds nothing. It would also last seconds and collide with the run ring,
  which shares this slot and wins.
- **Query activity** (the old `mcp.active` behaviour, as a flourish on state 2).
  Cut: the researcher asked the question, so a glyph confirming it is noise.

**Keep the pale tier**, despite being the marginal one, because under an
allowlist the sidebar becomes the audit surface and *"what have I shared?"* is
a question a researcher may be asked by someone else. Answering it at a glance
rather than through Settings earns the extra tier.

**Deliberately NOT on the badge: the Anonymise state.** "Exposed with names"
and "exposed with codes only" is a materially different governance fact, but it
is a second axis, and two axes on one glyph is unreadable. It belongs in the
tooltip and the Settings list.

**Known hole:** during a pipeline run the activity ring takes this slot
(`RightSlot` precedence: ring > copy > agent > cloud), so an exposed project
shows no antenna. Exposure remains true, just invisible. Probably acceptable —
runs are transient — but it is a gap in the audit story rather than a rendering
detail, and should be a deliberate acceptance rather than a discovery.

**Also worth surfacing: a failed share.** If the handshake write fails
(Keychain refusal, disk error) the toggle says shared and the project is not
actually reachable. That is a UI-is-lying case and deserves a signal if it is
detectable — but an error treatment, not a fourth badge tier.

**Open: colour.** It is currently `.secondaryLabelColor`, matching the iCloud
sibling, on the argument that ambient status joins the quiet family (and a Mac
review agreed). The counter-argument is now stronger: this is a data-egress
indicator, not a sync glyph. My lean is still secondary — it is a state the
researcher opted into deliberately, it is permanently on, and a coloured glyph
that never turns off becomes wallpaper (the same argument that keeps the
stale-address caveat out of yellow). A distinctive glyph in a quiet colour
stays legible without crying wolf. But this one should be looked at rather than
argued.

**Tooltip copy should carry the disclosure**, in the user's own framing, which
is more accurate than mine was: name the actor, the action and the condition —
*"Shared with agents. Any connected agent can read this project's quotes when
you ask it to."*

## 5b. The acceptance criterion: zero setup on return

Stated by the user, and the right test to hold the whole design to:

> When the researcher comes back the next day or the next hour to a project
> they were sharing, and clicks to make that project visible, they expect
> **zero setup in Claude** — to keep chatting, or to start a new session.

Traced against the design, it holds — but it is carried almost entirely by one
decision, and three others that must not be undone:

| Return scenario | What makes it work |
|---|---|
| Next day, new Claude session | Handshake rewritten with the new port; the token is durable (Keychain, per project) so it is unchanged |
| Same hour, Claude still open, Bristlenose restarted | **The proxy re-reads the handshake per tool call.** A proxy that resolved once at startup is dead here — this is the scenario that makes §3.2's requirement non-negotiable |
| Claude opened *before* Bristlenose | **No sticky fallback** (§3.2) — one server deciding per call, self-healing; plus `notifications/tools/list_changed` when the server appears |
| Switched to another shared project | Handshake rewritten; the next call picks it up and §3.2a marks it in the transcript |

**The constraint itself is accepted, and that is a scoping decision.**
"Bristlenose must be open, with the project open, to make queries" is
comprehensible and native — this is a desktop app, not a cloud service, and
every companion-app precedent we surveyed (Sketch, Figma, Beeper, Unity) says
exactly "open the app". Researchers can hold that model.

So the fallback text can be **plain rather than apologetic**, and a family of
heroics is ruled out before anyone proposes it as an improvement: no
auto-launching Bristlenose from the proxy (nothing in the survey does this), no
background daemon keeping the server alive while the app is closed, and no
always-on serve decoupled from the app's lifecycle.

**The gap this criterion exposes: the cold-start window.** Click a shared
project and ask Claude immediately — the serve is still booting (sidecar cold
start, plus the documented ~15s first-launch code-signature stall). The
handshake either does not exist yet or names a port that is not listening, and
the proxy answers *"open Bristlenose and select a project"* — which is wrong,
and infuriating, because they just did.

**Fix: three states, not two.** The proxy must distinguish

1. **no handshake** → not shared, or Bristlenose is not open → *"Open
   Bristlenose and select the study you want to ask about."*
2. **handshake present, port not answering** → starting up → *"Bristlenose is
   starting — ask again in a moment."* Optionally a short bounded retry (a
   second or two) **inside the tool call**, never during `initialize` (§3.2b).
3. **answering** → proxy normally.

State 2 is the one a naive implementation collapses into state 1, and the
researcher's own action is what creates it — so it is the state most likely to
be met and the most damaging to get wrong. Note that accepting the
"Bristlenose must be open" constraint does **not** relax this: state 1's
sentence is correct for a closed app and wrong three seconds after the
researcher opened it and clicked the project.

**Corollary for the handshake write.** Bristlenose should write the handshake
**when the port is confirmed listening**, not when the serve is requested.
`ServeManager` already has exactly this moment — it transitions to `.running`
only after `waitForPort` succeeds. Writing on `.running` means "handshake
exists" implies "port answers", and state 2 collapses to the narrow window
between the click and that transition, which is honest and short.

## 5c. Spike results — 31 Jul 2026

Run before writing any shipping code. Artefact: `desktop/mcpb-spike/`.

### The gate is open: the container read is not TCC-protected

`kTCCServiceSystemPolicyAppData` protects **Apple's own** app containers, not
third-party sandboxed ones. Measured from a shell **without** Full Disk Access
(verified — reading the TCC store itself was denied), so the test is valid:

| Container | Result |
|---|---|
| `com.apple.Notes`, `com.apple.Safari`, `com.apple.mail` | **DENIED** |
| `com.apple.Maps` | readable |
| `app.bristlenose`, `barbican.test`, `com.adobe.*` | **readable** |

The permission chain is `drwx------` all the way to
`~/Library/Containers/app.bristlenose/Data` — so **same-UID is the gate, not
TCC**, and the proxy runs as the researcher. Caveat stated honestly: this
measured reads from a shell, not from a Claude-Desktop-spawned process. Since
the path is not in the protected set at all, responsible-process attribution
should not matter — but it is reasoning, not measurement.

**Risk §6.1 dissolves**, and with it the §3.6 dilemma: the handshake stays in
the container, so **no token is ever written into a project folder** and the
Dropbox-sync problem never arises. The safe option turned out to be free.

### The mechanism works end to end

Against a real `bristlenose serve` (smoke fixture), through a **90-line,
zero-dependency** Node proxy:

- client → stdio → HTTP → real tools → **real data** (1 session, 4 quotes)
- **three states**, each with its own message: no handshake (*"Bristlenose
  isn't open…"*), handshake present but port silent (*"Bristlenose is
  starting…"*), ready (proxied)
- **self-heals** — handshake removed then restored mid-run, recovered on the
  next call with no restart of anything
- **the bearer is genuinely enforced** on this path: a corrupted token in the
  handshake returns `401`, not a silent pass
- `initialize` answers immediately; nothing slow precedes it

### The write path's security claims hold

`O_CREAT|O_EXCL|O_NOFOLLOW, 0600` + atomic rename: verified the file lands at
`0600`, and a pre-planted symlink pointing into Dropbox **blocked the write**
with nothing created at the target. (`O_EXCL` fires first because the symlink
is an existing directory entry; `O_NOFOLLOW` covers the non-exclusive case.
Keep both.)

### Packaging is simpler than feared

A `.mcpb` is a zip. Built one with plain `zip` — **4 KB, three files, no
`node_modules`** — so the 8-month-stale `@anthropic-ai/mcpb` CLI is not a
dependency. And a dependency-free proxy sidesteps native-module library
validation (§6.6), the missing CPU-arch field, the ABI trap, the size ceiling,
**and most of §4a's supply-chain obligations** — there is no npm tree to
audit, SBOM or Dependabot.

### What the spike did not answer

- **Installing into Claude Desktop.** Needs a click, and the relaunch would end
  the session that built the bundle. `Bristlenose-spike.mcpb` is ready.
- **Whether install requires a relaunch** (§6.8) — same reason.
- **`instance_id` matching** — the proxy implements the check, but
  `/api/health` does not emit one yet. Inert until it does.

### Two things the spike revealed that were not on the list

1. **404 and 401 need different messages, and each must name its own remedy.**
   A build without the `mcp` extra returns `404` on `/mcp/`; a stale or rotated
   credential returns `401`. A proxy that lumps both into "upstream error"
   hides the difference at exactly the moment the researcher needs it.
   - **404** — *"This copy of Bristlenose was built without agent support. No
     setting will enable it."* Say the last part: pointing at a Settings pane
     that cannot fix it is worse than admitting the limitation.
   - **401** — *"Tell the person to open **Bristlenose ▸ Settings ▸ MCP
     Agents** (⌘,) and check this project is still shared."* Two precisions
     that are easy to get wrong: **name the app**, because this text is read
     inside Claude Desktop where "Settings" means Claude's; and note that
     unsharing *deletes* the handshake, so that path yields the "not shared"
     message rather than a 401 — a 401 is a stale/rotated credential, and
     sending the researcher to reinstall would be a rabbit-hole.
   This makes the Settings pane's name a **dependency of the proxy's copy**,
   not merely a label.

   **Where these appear, since it constrains how they are written:** they are
   **tool results**, returned as ordinary text rather than JSON-RPC errors —
   Claude reads them and the *model* relays them into the conversation. Not a
   dialog, not a Bristlenose window. Three consequences: the model paraphrases,
   so the *facts* must survive rewording and we cannot lean on exact phrasing
   or markdown; it can never be a button, so we can name a destination but not
   navigate to it; and this is the **only channel we have into the other app**,
   which is the same asymmetry that made the badge the wrong tool for cold
   start (§5a-bis).
2. **The stale-sidecar trap bites this feature hard.** The running bundled
   sidecar reported `mcp: None` because it predated today's build — so the
   proxy correctly reported an upstream 404, and anyone testing the extension
   against a stale bundle will see *"not available in this build"* and chase
   the wrong thing entirely. The freshness gate exists for this; do not bypass
   it while testing MCP.

## 6. Risks and what could bite

From the research pass (issue numbers are `modelcontextprotocol/mcpb`) and from
this machine. Ordered by how much they'd hurt.

1. **The container read may be TCC-gated — this can invalidate the design.**
   macOS gates `~/Library/Containers/<bundleid>/` behind
   `kTCCServiceSystemPolicyAppData` ("*would like to access data from other
   apps*"), and it applies to unsandboxed apps too. Verified on this machine
   that container reads *are* TCC-mediated. If the read is attributed to Claude
   Desktop, the researcher's first connect produces an alarming prompt from a
   third party at the exact moment we promise "done" — and a "Don't Allow" is
   sticky, leaving a permanently broken extension with a recovery path buried
   in System Settings that neither app can explain. Cuts both ways: if it
   *does* prompt, that is macOS enforcing a real boundary visibly, which is a
   better story than a config file any process reads silently — pre-announce it
   in the sheet and the concern inverts into a selling point. **Unknown is the
   only unacceptable state.** Answerable in an afternoon (§8.1); if it prompts
   badly, the fallbacks are a non-container path, or Option B with the
   handshake living in the project folder BN already holds a bookmark for.
2. **Install can silently no-op — for exactly our shape.**
   [#284](https://github.com/modelcontextprotocol/mcpb/issues/284) /
   [#283](https://github.com/modelcontextprotocol/mcpb/issues/283): drag-to-
   Settings does nothing, the progress bar never advances, the Install button
   renders as a blank disabled pill. **Both reporters were `type: node` bundles
   wrapping a proxy** — precisely what we'd ship. Mitigation: our gesture is
   `NSWorkspace.open` (the double-click path, which works) and **never** drag;
   acceptance must watch `~/Library/Logs/Claude/main.log` for the `can_install`
   call and check `mcp-server-Bristlenose.log`.
2. **Stale-session death** (mcp-remote #106) — covered in §3.2 by re-reading
   the handshake and re-initialising rather than resolving once. If we get this
   wrong the feature works exactly once per Bristlenose launch.
3. **The `.mcpb` will lag the app, and there is no upgrade path at all.**
   Local installs never auto-update, *and* dropping in a newer bundle offers
   no "update" — only uninstall-then-reinstall, which loses the extension's
   stored configuration. There is no `update_url` in the manifest spec
   ([#65](https://github.com/modelcontextprotocol/mcpb/issues/65), not
   adopted). Two consequences: the proxy must stay version-tolerant (§3.2),
   and *we* own the update prompt — Bristlenose knows both versions and can
   offer to re-install when its bundled copy is newer (§7 Q6).
   **Our design is unusually well placed for this**: because the handshake
   file carries everything and we use no `user_config`, a reinstall loses
   nothing. That is an argument for keeping it that way.
4. **Enterprise kill switch.** Claude Desktop polls per-organization
   `dxt/blocklist` and `dxt/can_install` endpoints; an admin can disable the
   directory or blocklist publishers, and *"enterprise policy controls at the
   user-machine level will override any in-app controls"*. A researcher at a
   locked-down client may simply be unable to install, no matter what we ship.
   The Claude Code / Codex paths remain their fallback — an argument for §7 Q3.
5. **Directory listing is a poor near-term fit.** Anthropic's own docs now say
   *"MCPB is the secondary distribution path; remote MCP servers are
   recommended for directory listing"*; review has no SLA; a missing privacy
   policy is an immediate rejection; and the open-source + "spec will evolve"
   clauses are *non-waivable* (AGPL-3.0 likely satisfies the first — worth
   checking rather than assuming). Direct download from bristlenose.app plus
   the in-app button is the realistic channel.
   Note one prerequisite we already have an open finding for: the directory
   requires **tool annotations** (`title` plus `readOnlyHint` /
   `destructiveHint`) on every tool. That is review-log Finding 53 on the
   server doc, currently open — it becomes a gate rather than a nicety if we
   ever submit.
6. **Native modules are foreclosed** (#229). Only matters if someone later
   reaches for a native dependency in the proxy — write it down so they don't.
7. **`user_config` has a live corruption bug** — values containing `$` are
   silently mangled by a `String.replace` interpolation
   ([#258](https://github.com/modelcontextprotocol/mcpb/issues/258)), reported
   in the wild as 401s on a correct password. Our design uses no `user_config`
   at all, which sidesteps it; if Option B (§3.3) is ever chosen, this is a
   reason to carry the project path rather than anything secret.
8. **Unverified, and worth answering before the copy is written:** whether
   Claude Desktop needs a relaunch after installing an extension. §1 argues the
   restart cost is understated in the current path; it would be poor form to
   under-state it again in the replacement. Test, then write the button copy
   from the answer.

## 7. Open questions for the morning

1. **Scope model** — Option A (follow the fronted project) or B (pin one)? §3.3.
2. **Does the extension replace the Claude Desktop tab entirely,** or sit
   alongside "advanced: paste it yourself"? (Recommendation: replace. A second
   path we know is destructive is not a fallback, it is a trap.)
3. **`bristlenose mcp-proxy` as a CLI subcommand** — the same handshake trick
   would let Claude Code and Codex drop tokens and ports from their configs too
   (`claude mcp add bristlenose -- bristlenose mcp-proxy`). Worth doing in the
   same pass, or later?
4. **Directory submission** — research says near-term poor fit (§6.5), so the
   recommendation is *ship locally, revisit later*. Confirm that's acceptable,
   and note the trap if we ever do both: a directory listing plus an in-app
   button is **two install paths for one extension**, which is the same trap
   §7 Q2 refuses, arriving by a different door.
5. **Where does Install live — the per-project sheet, or app-level Settings?**
   Installing is a once-ever, machine-wide act; the sheet is a per-project
   consent surface. Review argues for splitting them (a Settings ▸ Connections
   row with the extension's name, version and an Install button; the sheet's
   Claude Desktop tab becomes status plus a "Set Up…" link). Cleaner model,
   bigger change. The minimum that must ship either way: the sheet header
   states Option A rather than implying a per-project grant, and the proxy
   announces subject changes (§3.2a).
6. **Who prompts for updates?** Local installs never auto-update, so a
   Bristlenose that ships a newer `.mcpb` than the installed one should
   probably say so. Where — the sheet's status line, or nothing until it
   actually breaks?

## 8. Verify before writing code

Cheap, and each one changes a decision rather than a detail:

1. **Does reading BN's container from the extension trip a TCC prompt?**
   (§6.1 — may change the design.) Throwaway `.mcpb` whose one tool returns the
   errno from that read; install locally, quit and relaunch Claude Desktop,
   read `~/Library/Logs/Claude/mcp-server-*.log`. Do this before anything else.
2. **Does installing an extension require a Claude Desktop relaunch?** (§6.8 —
   writes the button copy.)
2. **Does `NSWorkspace.open` on a `.mcpb` from the sandboxed app actually reach
   Claude Desktop's install flow?** And what happens with Claude Desktop
   absent (§3.4)? Test on a Mac without it.
3. **Does a minimal `type: node` bundle install cleanly by double-click**, with
   `can_install` in `main.log`? (§6.1 — this is the one that silently no-ops
   for our shape; find out on a throwaway bundle before building the real one.)
4. **Does AGPL-3.0 satisfy the directory's non-waivable open-source clause?**
   Only matters if Q4 goes the other way.

## Related docs

- [`design-mcp-server.md`](design-mcp-server.md) — the server, §6a connect UX,
  §9a spike results
- [`design-desktop-python-runtime.md`](design-desktop-python-runtime.md) — how
  the sidecar is bundled and signed
