<!--
DRAFT for the website repo, docs-src/connect-an-agent.md. 29 Sep 2026. Not deployed.
Spec and reasoning: docs/design-mcp-files-and-folders.md in the bristlenose repo.
Revised the same day after a user-documentation review (see the spec's changelog).

How to place it. Each block below says what it replaces or where it goes; the
rest of the page is unchanged.

What this draft does and doesn't claim:
  1. Claude: measured on macOS 27, both the silent block and the fix (spec §1, #1).
     Only the Claude Desktop EXTENSION reads the handshake. The command-line
     Claude Desktop setup (url + headers) connects over HTTP and is never blocked.
  2. ChatGPT: today's TOML / Add server setup connects over HTTP and is never
     blocked, so ChatGPT is NOT named in the troubleshooting section. Add it
     back only when a ChatGPT plugin ships (spec §4(c)).
  3. The Work-mode note is measured for both the ChatGPT plugin and the TOML
     setup (29 Sep 2026: a Chat thread said the tool "is not available", and a
     Work thread returned a quote).
  4. The "Open Files & Folders" button isn't built. The sentences naming it
     sit in comments marked BUILD, for the deploy that ships the button.
-->

<!-- ═══ REPLACES: under "### Claude Desktop", Mac app fork, the paragraph that
     starts "Expect one more prompt…" ═══ -->

There is one more step, and it comes later than you might expect: macOS has to
let Claude read Bristlenose's data. This happens on the first question, not at
install, so it can turn up after setup already looks finished.

- **macOS 27 and later.** The first time you ask Claude a question, macOS stops
  Claude reading Bristlenose, and it doesn't ask you first. Open **System
  Settings ▸ Privacy & Security ▸ Files & Folders**, expand **Claude**, turn on
  **Bristlenose**, and ask again.
  <!-- BUILD: add "Bristlenose's **Open Files & Folders** button, under Install
       Extension in Settings ▸ MCP Agents, takes you straight there." -->
- **macOS 26.** macOS asks once whether Claude may access data from other
  apps. Click **Allow**. If you clicked **Don't Allow**, turn it on in the same
  place as on macOS 27 (see *If Claude says macOS blocked it*, below).

Either way you do this once per agent app, not once per project.

<!-- ═══ INSERT: under "### ChatGPT and Codex", after "Restart the app after
     saving." Measured for this setup (see note 3). ═══ -->

::: info
In the ChatGPT app, ask your questions in **Work** mode. Bristlenose isn't
available in **Chat**, even though it appears in the `@` list there. You may
also be asked to approve each tool the first time ChatGPT uses it.
:::

<!-- ═══ NEW SECTION: after "## Try asking", before "## Good to know" ═══ -->

## If Claude says macOS blocked it

On macOS 27 and later, macOS stops an agent app reading Bristlenose's data
until you allow it, and it doesn't ask first. This applies when you connected
Claude Desktop with the extension from the Mac app. Claude tells you that macOS
blocked it. You may also see a **Data Access Blocked** notification from macOS;
its **Manage** button leads to Files & Folders.

1. Open **System Settings ▸ Privacy & Security ▸ Files & Folders**.
   <!-- BUILD: "Bristlenose's **Open Files & Folders** button, in Settings ▸ MCP
        Agents, opens it for you." -->
2. Find **Claude** in the list. It's alphabetical, so scroll down to it. If it
   isn't there, ask Claude one question first: macOS lists an app only after it
   has tried to read something.
3. Expand **Claude** and turn on **Bristlenose**.
4. Ask your question again. Nothing in Bristlenose needs changing, and there's
   nothing to reinstall.

**That switch is not the same as Agent Access.** The Files & Folders switch
lets Claude find Bristlenose at all. **Agent Access**, which you turn on per
project in Bristlenose, still decides which projects an agent can read. To stop
sharing one project, turn off its Agent Access. Turning off the Files & Folders
switch cuts Claude off from every project.

<!-- ═══ INSERT: in "## Good to know", as a new bullet ═══ -->

- **Windows.** Bristlenose runs from the command line on Windows. The steps on
  this page haven't been tested there.

<!-- ═══ OPTIONAL, separate correction: "### Command line" under "## Install and
     start". `pip install 'bristlenose[mcp]'` doesn't reach a pipx or uv tool
     install, which is how install.md tells people to install on every
     platform. Snap, Copr and Homebrew: unchecked whether they carry the mcp
     extra. Check before writing a line for them. ═══ -->

If you installed with pipx or uv, reinstall with the extra:

```
pipx install --force 'bristlenose[mcp]'
```

```
uv tool install --force 'bristlenose[mcp]'
```

If you installed with pip, run `pip install 'bristlenose[mcp]'` in the same
environment.

<!-- ════════════════════════════════════════════════════════════════════════
     PART 2: WHEN THE NATIVE PROXY SHIPS (both channels). Not for today's
     page. Spec §4(c). Apple's validator accepted the App-Store-shaped proxy on
     29 Sep 2026; TestFlight upload and review are still open. Replace the
     Part 1 blocks above with these in the same deploy as that build.
     ════════════════════════════════════════════════════════════════════ -->

<!-- ═══ REPLACES the Part 1 "There is one more step…" paragraph under
     "### Claude Desktop": no pre-announced step any more. ═══ -->

That's the whole setup. There's no config to edit, no permission to grant, and
nothing to re-copy after a restart.

<!-- ═══ REPLACES "### ChatGPT and Codex": the plugin is the Mac-app route;
     the config file stays, for the Codex CLI and as a fallback. ═══ -->

### ChatGPT and Codex

::: fork
### Mac app
**Settings → MCP Agents → ChatGPT & Codex → Install Plugin…**. ChatGPT opens
and shows its own page for the Bristlenose plugin; click **Install plugin**
there. That's the whole setup.

Ask your questions in **Work** mode. Bristlenose isn't available in **Chat**.

To connect by hand instead, the same tab shows the configuration for
`~/.codex/config.toml`.

### Command line
<!-- keep today's TOML + "Add server" text unchanged here -->
:::

<!-- ═══ REPLACES Part 1's "## If Claude says macOS blocked it" section: now a
     rare recovery path. The only case Files & Folders can fix is an
     unsandboxed reader of the data container (spec §4(c)); the native proxy's
     sandboxed build says "install the extension again, or check for a
     Bristlenose update" instead. So the page's recovery text follows the
     proxy's own sentence. ═══ -->

## If your agent says it can't reach Bristlenose's data

Open **Bristlenose → Settings → MCP Agents** and install the extension (or the
ChatGPT plugin) again, then ask again. If that doesn't help, check for a
Bristlenose update.
