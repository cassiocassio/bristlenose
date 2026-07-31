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

### 3.2a The subject-change announcement — the highest-leverage part

Under Option A (§3.3) the agent's subject follows Bristlenose. The failure that
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
`initialize`, and only then attempt the HTTP connection. In particular the
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

Recommendation: **A**, with the labelling above, plus §3.2a. B remains
available later as an optional `user_config` field if a cohort researcher asks.

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
