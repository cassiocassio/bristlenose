# "Unknown developer" on Claude Desktop's Plugins page: why it stays (14 Nov 2026)

**Verdict: we found no way to remove it: no manifest field changes it, and Anthropic documents no verification route for a file-installed local server that works in chat. The rule behind the label is undocumented (none of the pages below mentions it), so "Anthropic's rule" is our inference. Do not try again through the manifest. Revisit only if Anthropic ships developer verification for locally installed extensions.** This note exists so no future session re-runs the investigation.

## What we saw

Claude Desktop's Plugins page lists the Bristlenose extension under the name with **Unknown developer**, beside the correct version and licence. The install dialog for the same package says **Made by Martin Storey** (a link), AGPL-3.0-only, version 0.46.0, with the fish icon and the new description, under a red banner saying developer information shown "has not been verified by Anthropic". Seen with the Node build, and again after a clean reinstall of the native package (registry entry `local.mcpb.martin-storey.bristlenose`, author name and url, `icon.png`, server type `binary`). Observed on our own extension only; we did not record how another file-installed extension (for example Anthropic's Filesystem) is labelled, so "every file-installed extension gets it" is inferred. We also never looked at the config-file (Command line) path.

## What we tried (all useless for this label)

- Author name "Bristlenose", then "Martin Storey", with `author.url`.
- `homepage`, `repository`, `license` in both manifests (they appear in the dialog and the detail page, which is why version and licence show).
- Reinstalling from scratch, native package versus Node package, with and without the old row.
- Searching Claude's app bundle for the label (14 Nov 2026, by hand; no command recorded): it is not a literal string there, so the rule could not be read from code.
- Searching the indie and developer community (web search, 14 Nov 2026; queries and links not kept): tutorials and awesome-lists, a few issues mentioning an unverified-developer warning for non-directory extensions, and no thread where anyone removed the label.
- **Signing was not tried here, and is ruled out elsewhere:** `mcpb sign` exists, but `docs/design-mcp-extension.md` (§ on signing, around line 1731) records it as non-functional end to end, and Anthropic's own Filesystem extension is recorded unsigned.

Side effect worth knowing: Claude builds an extension's id from `author.name` as well as `name`, so changing the author installs a second copy (§ Platform APIs, policy and sign-in).

## What Anthropic's own docs say (read 14 Nov 2026)

1. **`.mcpb` is for private distribution.** [Build a desktop extension with MCPB](https://claude.com/docs/connectors/building/mcpb.md): intended for internal use or private distribution; users install the file themselves, and the install UI lets them review details and permissions. This page does not link the manifest author to a verified label.
2. **The directory no longer takes MCPB.** [Publish to the directory](https://claude.com/docs/directory/publish): desktop extension listings are deprecated and local servers packaged as MCPB are no longer accepted; a local server reaches the directory only inside a **plugin bundle** (public GitHub repo, automated validation and security scan, a person reviews a new listing, submitted at claude.ai/directory/manage by any paid plan). "Verified" is a label Anthropic assigns during review (defined for connectors in `connectors/verification.md`; the publish page does not say it plainly for plugins); there is no separate application. Submission needs a paid plan, and on Team and Enterprise an Owner.
3. **A plugin's local servers are documented as not running in chat.** [Plugin feature support across platforms](https://claude.com/docs/plugins/platform-support.md) (a table row): a local MCP server inside a plugin, `.mcpb` bundles included, is ignored in Chat and loads in Claude Code and in Cowork when the session runs on your computer. The prose in `connectors/building/what-to-build.md` says the same (local server: Claude Code and local Cowork, not chat). This is about a server *inside a directory plugin*; our directly installed `.mcpb` does work in chat. Read, not tried: we did not build a plugin to see whether chat really skips it. Our conclusion that a directory plugin would not serve Bristlenose rests on that reading.
4. **Remote connectors are the verified route, and not ours.** [Submit a connector](https://claude.com/docs/connectors/building/submission.md): a connector must be a remote HTTPS server. Bristlenose reads local project data and has no servers by owner decision (8 Nov 2026, recorded in the owner's private notes; not in this repo).
5. **Organisations** (Team and Enterprise) can turn extensions off, limit which ones install, and deploy their own through enterprise software management ([Add a connector that isn't in the directory](https://claude.com/docs/connectors/custom/add-unlisted.md); custom uploads and allowlists are also in `mcpb.md`); that is an admin control, not a public verified badge.

## What we did about it

- Told users it is normal: a short info note on the public Connect-an-agent page (website repo, `docs-src/connect-an-agent.md`, after the Claude Desktop install steps), saying Bristlenose is installed from a file so Claude has not checked who made it, and that the install window named the maker and licence. It sits in the Mac app section only, worded to claim just what we observed. Committed to the website repo's `main` (not deployed as of 14 Nov 2026) and merged into the held branch `after-app/plugin-wording`.
- Recorded the finding in `desktop/gotchas.md` (§ Platform APIs, policy and sign-in).

## Revisit only if

Anthropic announces developer verification for locally installed extensions, a directory route for local servers that works in chat, or a chat-capable local-server component for plugins (re-read the platform-support table). Until then the answer is "this is normal".
