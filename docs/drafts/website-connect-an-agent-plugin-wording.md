# Website edits owed: Claude Desktop says plugin

**Applied 14 Nov 2026 on a held branch, not on `main`:** branch `after-app/plugin-wording` of the website repo (commit `1da8d23`, in the worktree `~/Code/.bn-website-plugin-wording`). Merge it when the Mac build that says "Install Plugin…" reaches users, then delete the worktree (`git worktree remove`). The one-sentence duplicate-row note and the older-Claude aside below, and the `bristlenose-website-miro-help` copy, were not applied.

`docs-src/connect-an-agent.md` lives in the website repo (`bristlenose-website`, and a copy in `bristlenose-website-miro-help`), whose `deploy.sh` publishes the working tree. These are the exact edits so they can be made on a clean checkout when the Mac app that says "Install Plugin…" ships (the page must not say a label the shipped app does not have yet). Written 14 Nov 2026 from commits `4f4f02167` and `aab597097`.

Evidence for the wording: Claude Desktop's sidebar and page say **Plugins** (owner screenshots, 13 Nov 2026), its Plugins page has an **Uninstall** button, and its own install dialog still says "extension" (the package format's word). See `docs/i18n-vendor-terms.md`.

| Line | Now | Replace with |
|---|---|---|
| 26 | "For Claude Desktop, click **Install Extension…** and confirm in Claude Desktop." | "For Claude Desktop, click **Install Plugin…** and confirm in Claude Desktop." |
| 56 | "The extension and the plugin find the running project by themselves" | "Both plugins find the running project by themselves" |
| 83 | "**Settings → MCP Agents → Install Extension…** — Claude Desktop opens and asks you to confirm. Bristlenose then appears in Claude Desktop under **Settings → Extensions**." | "**Settings → MCP Agents → Install Plugin…** — Claude Desktop opens and asks you to confirm. Bristlenose then appears under **Plugins** in Claude Desktop." |
| 85 | "If you installed the extension with an earlier version of Bristlenose, the same button reads **Update Extension…**, and Claude replaces the old one." | "If you installed the plugin with an earlier version of Bristlenose, the same button reads **Update Plugin…**, and Claude replaces the old one." |
| 143 | "install the extension or the plugin again" | "install the plugin again" |
| 145 | "an extension installed by an older version of Bristlenose … **Update Extension…** replaces it" | "a plugin installed by an older version of Bristlenose … **Update Plugin…** replaces it" |

Leave line 115 ("the Codex extension for VS Code"): that really is a VS Code extension.

## One sentence worth adding

Claude builds an installed plugin's id from the publisher name as well as the name, so the publisher change in `3545fe0fb` installs beside a copy made before it. Anyone who installed earlier than 14 Nov 2026 sees two Bristlenose rows in Claude Desktop's Plugins page after installing again (internal TestFlight only so far; see `desktop/gotchas.md`). If that can reach outside users, add under the install steps: "If Plugins lists Bristlenose twice, uninstall both, then click **Install Plugin…** again." Optionally for older Claude versions that still have a Settings page called Extensions: "(in older versions of Claude Desktop, under Settings → Extensions)".

## Also check

- Screenshots on the page that still show "Install Extension…".
- `docs-src/privacy.md:19` ("an AI agent … such as Claude Desktop or ChatGPT") is still correct.
- Both trees carry the same text: apply to `bristlenose-website` and `bristlenose-website-miro-help`.
