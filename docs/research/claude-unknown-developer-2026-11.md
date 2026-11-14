# "Unknown developer" on Claude Desktop's Plugins page: why it stays (14 Nov 2026)

**Verdict: there is no way to remove it for a local MCP server used in Claude chat. Do not try again through the manifest. Revisit only if Anthropic ships developer verification for locally installed extensions.** This note exists so no future session re-runs the investigation.

## What we saw

Claude Desktop's Plugins page lists the Bristlenose extension under the name with **Unknown developer**, beside the correct version and licence. The install dialog for the same package says **Made by Martin Storey** (a link), AGPL-3.0-only, version 0.46.0, with the fish icon and the new description, under a red banner saying developer information shown "has not been verified by Anthropic". Seen with the Node build, and again after a clean reinstall of the native package (registry entry `local.mcpb.martin-storey.bristlenose`, author name and url, `icon.png`, server type `binary`).

## What we tried (all useless for this label)

- Author name "Bristlenose", then "Martin Storey", with `author.url`.
- `homepage`, `repository`, `license` in both manifests (they appear in the dialog and the detail page, which is why version and licence show).
- Reinstalling from scratch, native package versus Node package, with and without the old row.
- Searching Claude's app bundle for the label: it is not a literal string there, so the rule could not be read from code.
- Searching the indie and developer community: tutorials and awesome-lists, a few issues mentioning an unverified-developer warning for non-directory extensions, and no thread where anyone removed the label.

Side effect worth knowing: Claude builds an extension's id from `author.name` as well as `name`, so changing the author installs a second copy (`desktop/gotchas.md`).

## What Anthropic's own docs say (read 14 Nov 2026)

1. **`.mcpb` is for private distribution.** [Build a desktop extension with MCPB](https://claude.com/docs/connectors/building/mcpb.md): intended for internal use or private distribution; users install the file themselves, and the install UI lets them review details and permissions. Nothing links the manifest author to a verified label.
2. **The directory no longer takes MCPB.** [Publish to the directory](https://claude.com/docs/directory/publish): desktop extension listings are deprecated and local servers packaged as MCPB are no longer accepted; a local server reaches the directory only inside a **plugin bundle** (public GitHub repo, automated validation and security scan, a person reviews a new listing, submitted at claude.ai/directory/manage by any paid plan). "Verified" is a tier Anthropic assigns during review; there is no separate application.
3. **Chat ignores a plugin's local servers.** [Plugin feature support across platforms](https://claude.com/docs/plugins/platform-support.md): a local MCP server inside a plugin, `.mcpb` bundles included, is **ignored in Chat** and loads only in Cowork and Claude Code. Bristlenose is used by asking questions in Claude chat, so a directory plugin would not serve it.
4. **Remote connectors are the verified route, and not ours.** [Submit a connector](https://claude.com/docs/connectors/building/submission.md): a connector must be a remote HTTPS server. Bristlenose reads local project data and has no servers by owner decision (`project_no_servers_is_a_feature` in memory, `docs/design-mcp-extension.md`).
5. **Organisations** (Team and Enterprise) can allowlist, upload and sign extensions ([Add a connector that isn't in the directory](https://claude.com/docs/connectors/custom/add-unlisted.md)); that is an admin control, not a public verified badge.

## What we did about it

- Told users it is normal: a short info note on the public Connect-an-agent page (website repo, `docs-src/connect-an-agent.md`, after the Claude Desktop install steps), saying the label is Anthropic's rule for this kind of extension and that the install window names the maker and licence. Committed to the website repo's `main` (not deployed) and merged into the held branch `after-app/plugin-wording`.
- Recorded the finding in `desktop/gotchas.md` (§ Platform APIs).

## Revisit only if

Anthropic announces developer verification for locally installed extensions, a directory route for local servers that works in chat, or a chat-capable local-server component for plugins (re-read the platform-support table). Until then the answer is "this is normal".
