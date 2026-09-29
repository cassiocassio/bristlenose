<!--
DRAFT for the website repo, docs-src/connect-an-agent.md. 29 Sep 2026. Not deployed.
Spec and reasoning: docs/design-mcp-files-and-folders.md in the bristlenose repo.

How to place it. Each block below says what it replaces or where it goes; the
rest of the page is unchanged.

Two things to settle before it goes live:
  1. The Claude Desktop paragraph says macOS 27 blocks Claude silently. Measured
     for both: ChatGPT on the host, and a clean Claude in a SIP-on macOS 27
     guest on 29 Sep 2026, where turning on the switch fixed it (spec §1, #1).
  2. The ChatGPT block is written for today's TOML path. If the Codex plugin
     ships, the ChatGPT block takes the Claude Desktop block's shape instead
     (spec §4 (b)).
-->

<!-- ═══ REPLACES: under "### Claude Desktop", Mac app fork, the paragraph that
     starts "Expect one more prompt…" ═══ -->

There is one more step, and it comes later than you might expect: macOS has to
let Claude read Bristlenose's data. This happens on the first question, not at
install, so it can turn up after setup already looks finished.

- **macOS 27 and later.** macOS blocks the first question without asking. In
  Bristlenose, click **Open Files & Folders** under the Install button, or
  open **System Settings ▸ Privacy & Security ▸ Files & Folders** yourself.
  Expand **Claude**, turn on **Bristlenose**, and ask again.
- **macOS 26.** macOS asks once whether Claude may access data from other
  apps. Click **Allow**.

Either way you do this once per agent app, not once per project.

<!-- ═══ INSERT: under "### ChatGPT and Codex", after "Restart the app after
     saving." ═══ -->

::: info
In the ChatGPT app, ask your questions in **Work** mode. Bristlenose's tools
aren't available in **Chat**, even though Bristlenose appears in the `@` list
there.
:::

<!-- ═══ NEW SECTION: after "## Try asking", before "## Good to know" ═══ -->

## If your agent says macOS blocked it

This is the macOS 27 permission from the Claude Desktop steps above. macOS
doesn't show a dialog for it, so the first you hear of it is your agent saying
it can't reach Bristlenose. macOS may also show a **Data Access Blocked**
notification. Its **Manage** button opens the same settings page.

1. Open **System Settings ▸ Privacy & Security ▸ Files & Folders**. Bristlenose
   has a button for this under **Settings ▸ MCP Agents**.
2. Find your agent app in the list: **Claude** or **ChatGPT**. The list is
   alphabetical, so scroll down to it.
3. Expand it and turn on **Bristlenose**.
4. Ask your question again. Nothing in Bristlenose needs changing, and there's
   nothing to reinstall.

If your agent app isn't in the list, ask it one question first. macOS adds an
app to the list once it has tried to read something.

**That switch is not the same as Agent Access.** The Files & Folders switch
lets an agent app find Bristlenose at all. **Agent Access**, which you turn on
per project in Bristlenose, still decides which projects an agent can read. To
stop sharing one project, turn off its Agent Access. Turning off the Files &
Folders switch cuts that agent app off from every project.

<!-- ═══ INSERT: in "## Good to know", as a new bullet ═══ -->

- **Windows.** The Mac app and its extensions are macOS-only. On Windows,
  Bristlenose runs from the command line, and the command-line steps on this
  page haven't been tested there.

<!-- ═══ OPTIONAL, separate correction: "### Command line" under "## Install and
     start". `pip install 'bristlenose[mcp]'` doesn't reach a pipx install,
     which is how install.md tells people to install on every platform. ═══ -->

If you installed with pipx, reinstall with the extra:

```
pipx install --force 'bristlenose[serve,mcp]'
```

If you installed with pip, `pip install 'bristlenose[mcp]'` in the same
environment.

<!-- Homebrew: not checked whether the formula carries the mcp extra. Check
     before writing a Homebrew line; don't tell people to pip into brew's venv. -->

