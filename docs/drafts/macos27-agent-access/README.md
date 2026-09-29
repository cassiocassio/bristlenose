# macOS 27 agent access: two ready-to-apply patches

> **`0001` applied to `main` on 29 Sep 2026 as `d086f08d`**, with the maintainer's
> approval. Before committing: full pytest (5525 passed), ruff and
> `check-locales --strict`. **`0002` applied as `4945dce2`** the same day, once its
> claim was measured on the config-file route (the plugin-spike session: a Chat
> thread refused the tool, and a Work thread used it).

Prepared 29 Sep 2026 while the maintainer was away. **Not applied to `main`**:
the maintainer asked to approve code and locale changes before they land.
Built and tested in a throwaway detached checkout of `3952cfe9`. Nothing on
`main` had touched these files since, and `git apply --check` passes against
`main` at `393d5ef2`. Spec: [`../../design-mcp-files-and-folders.md`](../../design-mcp-files-and-folders.md)
§3, §4 and §8.

## What they do

**`0001` (Claude, the Node `.mcpb`, today's state).** On macOS 27 the first
question is silently blocked, and the fix is a Files & Folders switch
(measured for Claude and ChatGPT).
- The proxy's `permission` sentence branches on macOS 27 and names the host
  the package declares: `BRISTLENOSE_MCP_HOST`, with "your AI app" as the
  fallback. This is the same name and fallback as the native proxy.
- The `.mcpb` manifest declares `BRISTLENOSE_MCP_HOST=Claude`.
- `check-mcpb.sh` now rejects any `BRISTLENOSE_DEV_*` in a pack.
- Settings ▸ MCP Agents, Claude tab: on 27, the note names the switch and has
  an **Open Files & Folders** button. It deep-links, and falls back to System
  Settings. macOS 26 keeps the existing dialog note.
- Adds `filesFoldersNote` and `openFilesFolders` to all 21 full locales.
- Adds `tests/test_mcpb_proxy_messages.py`.

**`0002` (the ChatGPT tab).** Adds "In ChatGPT, ask in Work mode —
Bristlenose's tools aren't available in Chat." under the dialect, and adds
`chatgptWorkNote` to all 21 locales. **Kept separate on purpose:** the claim is
measured for the ChatGPT *plugin*, and only inferred for today's config-file
route. Apply it once one question in Chat mode has confirmed it, or apply it
now if the English v1 is enough.

## Apply

```bash
cd ~/Code/bristlenose && git apply docs/drafts/macos27-agent-access/0001-*.patch
```

```bash
cd ~/Code/bristlenose && git apply docs/drafts/macos27-agent-access/0002-*.patch
```

`git am` works too, if you want the prepared commit messages.

## Verified (29 Sep 2026)

- **Proxy:** `node --check` passes on the source and on the packed copy. ESLint
  is clean. `build-mcpb.sh` + `check-mcpb` pass on a real pack, and the pack
  carries the env and no `BRISTLENOSE_DEV_*`.
- **New proxy tests:** 3 pass, and all 3 **fail on the unpatched proxy**.
  They drive the real proxy under Node, so they run on Linux CI too.
- **Locales:** `check-locales.py --strict` passes, and
  `tests/test_locale_key_readers.py` (the orphan-key gate) passes, because
  every new key is read by the Swift. No pre-existing locale value changed.
  The script asserted this for every file.
- **Swift:** the app builds with each patch, with no new warnings in
  `MCPAgentsSettingsView.swift`. The full Swift suite with both patches:
  **1547 passed, 1 failed**. The failure is
  `ServeManagerStartGuardTests/aFailedServeCanBeRestartedOnTheSameProject`, which
  **fails identically on the unpatched base**. It's a pre-existing red on
  `main`, not caused by these patches, and is flagged as its own task.
  _(Fixed 29 Sep 2026, `55628d90`: the test depended on the build embedding a
  sidecar, which a fresh checkout does not, so it failed here and passed in the
  main repo. The product was correct.)_

## Not verified

- **Not looked at on screen.** The pane's new note and button were never run
  or rendered in the app. The mockup
  ([`../../mockups/mcp-files-and-folders.html`](../../mockups/mcp-files-and-folders.html))
  shows the intent.
- **No VoiceOver hint on the button.** The Mac-UX review asked for one
  ("Opens System Settings"), but it would need a new string in 21 locales that
  nobody has drafted.
- **The v2 shorter copy** from the same review is recorded in the spec as a
  proposal. v1 is what these patches carry.

## When the native proxy ships

These patches are the **today** state. If the sandboxed app-group proxy ships
(spec §4(c); Apple's validator accepted it on 29 Sep 2026), the Claude tab's
note stops being pre-announced, the proxy sentence stays as the recovery path,
and the ChatGPT tab grows an install row. That's a separate change.
