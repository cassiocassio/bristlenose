---
status: proposal
date: 22 Nov 2026
owner-decisions: none yet (see §9)
timing: 2027, after the beta reliability phase and after the Report lens
mockups: docs/mockups/research-agent-publisher.html, docs/mockups/research-agent-it-handover.html, docs/mockups/research-agent-team-member.html
---

# PRD: the published research agent ("@UXR-ProductX")

A researcher finishes a body of work and leaves behind something the rest of the
company can **ask**, in the tools they already use (Teams, Slack, Figma Make,
Claude, ChatGPT), not a `.html` on a file share that nobody opens twice. It
answers in quotes with citations, it counts correctly, and it belongs to the
client, not to us.

This is a product proposal to argue about. Nothing in it is decided. It is
written from **people's jobs and the experiences they should have**. How it is
built is parked in Appendix A until the product strategy is settled (owner,
22 Nov 2026).

---

## 1. The problem

Research outlives its report badly.

- The deliverable is a meeting, a deck and a file
  ([`docs/research/search-or-ask.md`](research/search-or-ask.md)). Three months
  later a PM writing a PRD, a designer prompting Figma Make, or an engineer in
  a Slack thread needs "what did users say about onboarding?" They don't open
  the report, so they guess, or they ask the researcher, who may have left.
- Freelance researchers are worse off. The engagement ends, the knowledge
  leaves with them, and the client is left with a folder.
- Companies already make "agents" from files. Fed a research report, those
  agents guess at counts, lose who said what, and can't tell a researcher's
  starred quote from a passing remark.
- The hosted alternatives put the research on someone else's servers, which a
  client's IT often won't approve.

## 2. The stories

> **Sam is a freelance researcher.** Over six months they ran three studies for
> a client's Product X: onboarding, pricing, and the admin console. On the last
> day of the engagement Sam picks the starred quotes, the strongest signals and
> the clips worth watching, and publishes them as **"What we know about Product
> X"**. Sam asks the client's IT for one thing: somewhere to run it that only
> people with company sign-in can reach. From then on **@UXR-ProductX** answers
> in Teams, Slack, Figma Make and Claude, with Sam's quotes and Sam's counts.
>
> **Five months later the client hires Sam again** for two more studies. Sam
> publishes them **into the same agent**. Nobody re-installs anything, the name
> doesn't change, and the agent now knows all of them and says which one each
> quote came from.
>
> **Meanwhile Priya**, an in-house researcher at the client, on her own Mac,
> adds a study of her own to the same collection and corrects one of Sam's
> numbers in hers. Neither of them has to coordinate with the other.

Smaller stories the scenarios also cover:

- A researcher at a company that gives staff a self-serve platform for
  internal experiments wants to put it up themselves, without a ticket.
- IT wants to offer published research to **everyone with a role** (all of
  Design & Research) or another scope, through Microsoft 365 or Google
  Workspace.
- A PM is writing a PRD, a market-opportunity analysis or a design strategy
  doc in Claude and wants the research beside them while they write.
- A designer in Figma Make wants research as context for the prompt that makes
  a prototype.

## 3. Users and their jobs

### 3.1 The publisher: a researcher, in-house or freelance

> **When** I finish a body of research, **I want** the team to keep using what
> we learnt, in my words and the participants' words, **so that** decisions
> months from now still rest on evidence, and my work keeps its credit.

- **Also:** when I come back with more research, add it to what's already
  there, without starting again or needing the old files.
- **Also:** when a colleague researches the same product, let us both
  contribute without stepping on each other.
- **Pains:** "What do I even ask IT for?"; losing control over what leaves the
  room; becoming the support desk for something I left behind.
- **Never wants:** to run, patch or babysit a server.

### 3.2 IT: the client's Microsoft 365, Google Workspace or cloud admin

> **When** a researcher asks me to host their research for the team, **I want**
> to understand quickly what I'm being asked, say yes on infrastructure and
> sign-in we already have, and give access to exactly the right people, **so
> that** the team gets it without me taking on a risk or a support burden.

- **Also:** offer it to everyone in a role, or to one team, using the groups I
  already manage.
- **Also:** see that it's healthy and in use; handle a researcher coming back;
  retire it cleanly.
- **Pains:** a third party holding company data; something that phones home;
  a tool nobody owns after the person who asked for it leaves.
- **Never wants:** a second list of users to maintain.

### 3.3 The asker: anyone on the product team

PMs, designers, engineers, executives, new joiners.

> **When** I'm deciding something about Product X in the tool I'm already in,
> **I want** to ask what the research says and get evidence I can trust and
> paste, **so that** I don't guess and I don't wait for a researcher.

- **Designer in Figma Make:** when I prompt a prototype, I want it grounded in
  what users actually said.
- **PM in Claude or ChatGPT:** when I write a PRD, opportunity analysis or
  strategy doc, I want quotes and counts I can cite.
- **Anyone in Teams or Slack:** when a thread argues about users, I want to
  @-mention the research and settle it with evidence.
- **Pains:** learning a new tool; a 90-page report; an answer I can't tell
  from a guess.
- **Never wants:** to be told who a participant is (and shouldn't be able to).

## 4. Experience principles

1. **Ask where you already are.** The research comes to Teams, Slack, Figma
   Make and Claude; nobody goes to it.
2. **Answers are quotes, not prose.** Every claim carries its evidence: the
   quote, the participant code, the study, and when it was fielded.
3. **It says what it doesn't know.** A question the research doesn't cover
   gets "the research doesn't cover that", never a fill-in from general
   knowledge.
4. **Curation is the consent boundary.** The agent can only say what the
   researcher chose to publish. Choosing what goes in is choosing what may
   leave the room.
5. **It belongs to the client.** It keeps working after the researcher leaves,
   closes their laptop, or stops paying for Bristlenose.
6. **One sentence to IT.** The researcher's request is something IT gets every
   week: *"Let me run one thing that only people with our sign-in can reach."*
7. **Staleness is visible, not hidden.** Every answer shows how old its
   evidence is, so nobody needs a warning banner.

## 5. What gets published, in people's terms

- **A collection**: a named body of research ("What we know about Product X")
  with a name people can @-mention (@UXR-ProductX is a placeholder).
- **Made of studies.** Each study is published on its own and stays as it was
  published. Adding studies later doesn't disturb the earlier ones, and doesn't
  need their source files.
- **Curated, not everything.** It comes from a future **Report lens**: the best
  signals, the starred quotes, "if you only watch these clips". Today's report
  is "Bristlenose for people without Bristlenose"; the Report lens is the
  researcher's argument. **The Report lens is a prerequisite.** Without it,
  publishing means publishing everything, which breaks principle 4.
- **Never in it:** participants' names (speakers are codes like `p3`), hidden
  quotes, unpublished work. No video in the first version: clips show faces and
  need a higher level of consent.
- **Optionally, an end date** after which it stops answering and says who to
  ask instead.

## 6. Three ways to leave research behind

| | **The report file** | **The agent pack** | **The research agent** |
|---|---|---|---|
| Exists today? | Yes (HTML export) | No | No |
| In one line | A file people open | Files the researcher turns into an agent in Copilot, Gemini, ChatGPT or Claude | Something IT hosts once, that the whole team can ask from anywhere |
| Who sets it up | The researcher | The researcher, in about ten minutes | IT, once; researchers publish into it after that |
| Needs IT? | No | No | Yes, once |
| Where people meet it | A browser | Wherever that builder's agents appear | Teams, Slack, Figma Make, Claude, ChatGPT |
| "How many of the 12 said X?" | Read it in the report | Best effort: only what the pack states | Exact, with the denominator |
| Several studies | One file each | Separate sets of files | One collection, each answer naming its study |
| Can it be withdrawn or expire? | No: copies are copies | No: files get copied | Yes |

**The agent pack is the way in; the research agent is the step up**, chosen when
"the agent we made from files gets the numbers wrong" or "we need to be able to
withdraw it".

## 7. Scenarios

Grouped by whose job they serve. Each says what the person should experience
and what they must never experience. Ids match the mockups.

### 7.1 Publisher

| Id | Situation | They experience | They never experience |
|---|---|---|---|
| P1 | An in-house researcher publishes one study for their own team | Report lens → Publish → a summary of exactly what will leave (studies, quotes, what's excluded) → choose agent pack or research agent | Publishing something they didn't choose |
| P2 | **A freelancer leaves three studies behind on their last day** | Pick three projects, name the collection, optionally set an end date, get a ready-written request to send IT | Having to know what Docker, SSO or MCP are |
| P3 | Nothing is curated yet | A plain refusal naming what's missing, and a way to the Report lens | "Publish everything" as a default |
| P4 | Some quotes were flagged as possibly identifying | The count, and each one to keep or leave out before publishing | Finding out after it's live |
| P5 | IT says no | The agent pack instead, from the same curation | Redoing the work |
| P6 | **Two researchers on two Macs both contribute to the Product X collection** | Each publishes their own studies into it, whenever they like | Overwriting each other; having to coordinate a release |
| P7 | **The freelancer returns and adds two studies to the original three** | Publish into the existing collection by name; the three earlier studies stay as they were | Needing the old files back; a new name or a new install for the team |
| P8 | A researcher has a self-serve platform for internal experiments | The same publish, pointed at their platform; a clear stop if nothing checks who's signing in | Accidentally putting participant quotes on the open internet |
| P9 | A researcher corrects a published study | Republish it; askers see the new date | The old version lingering somewhere |
| P10 | **A researcher publishes the agent pack to Copilot or a Gem** | Bristlenose puts the pack where the builder reads it (their OneDrive, their Google Drive) and walks them through the last few clicks in Agent Builder or Gemini: pick this folder, paste these instructions, share with this group | A sign-in that stops at "needs admin approval"; being told to "upload files" with no idea which |

### 7.2 IT

| Id | Situation | They experience | They never experience |
|---|---|---|---|
| I1 | A request arrives from a researcher they've never met | One page, written for IT: what it is, what data, what it needs, how to remove it | Reading a README to work out what they're being asked |
| I2 | Deciding whether to say yes | The answers a reviewer checks, on the first screen, with the details behind a link | A third party in the data path |
| I3 | Setting it up | A short guided choice: where to run it (Microsoft, Google, our own platform) and who can ask | A second user list; anything that needs a developer |
| I4 | **Offering it to everyone in a role, or one team** | Pick existing groups (Microsoft 365 or Google Workspace) for "who can ask" and "who can publish", per collection | Managing membership anywhere but where they already do |
| I5 | Telling people it exists | A ready-made announcement for the team's channel | An agent nobody knows about |
| I6 | Day to day | A quiet page: healthy, in use by how many people, nothing to do | Being paged by it |
| I7 | **The freelancer returns**, their access long expired | One clear request: let Sam publish again, until a date | Re-installing or re-approving the whole thing |
| I8 | Two researchers publish at the same time | Both appear in the activity, in order | A conflict to resolve |
| I9 | The end date passes, or the company wants it gone | It stops answering and says who to ask; removal is one action | Wondering whether a copy is left anywhere |

### 7.3 Asker

| Id | Situation | They experience | They never experience |
|---|---|---|---|
| A1 | A PM asks in Teams "what did people say about onboarding?" | A few quotes, each with participant code, study and date, and a link to the full report | A summary with no evidence |
| A2 | "How many of the 12 admin-console participants mentioned permissions?" in Slack | An exact count with its denominator and study | A confident guess |
| A3 | A designer in Figma Make prompts a prototype with research as context | The research shapes the prototype, and they can see which quotes it used | Research they can't trace |
| A4 | A PM writes a PRD in Claude | Quotes and counts they can cite, ready to paste with their source | Having to rewrite citations |
| A5 | A question the research doesn't cover | "The research doesn't cover that", and what it does cover | An answer from general knowledge dressed up as research |
| A6 | "Who is p3?" | A polite no, and who the researcher of record is | A name |
| A7 | Someone outside the group asks | Who to ask for access | A cryptic error |
| A8 | Someone asks for a clip | The moment's timecode and a link to the report | Video in the first version |
| A9 | Asking after Sam's return | Answers from all six studies, each saying which study and when | Not knowing whether it's up to date |
| A10 | Asking after a study's end date | That study has expired, and who to ask | Silence, or a stale answer |
| A11 | Finding out it exists | An announcement in their channel; the agent listed where their tool lists agents | Hearing about it six months later |

## 8. Flows

End to end, as drawn in the mockups.

1. **Leave it behind** (Sam, IT, then everyone): P2 → I1 → I2 → I3 → I4 → I5 →
   A11 → A1. *IT mockup frames 1–5; team mockup frames 1–2.*
2. **Ask from your tool** (askers): A1 Teams, A2 Slack, A3 Figma Make, A4 Claude.
   *Team mockup frames 2–5.*
3. **Hit the edges** (askers): A5, A6, A7, A10. *Team mockup frame 6.*
4. **Come back with more** (Sam, Priya, IT, askers): P7 + P6 → I7 → I8 → A9.
   *IT mockup frame 6; team mockup frame 7.*
5. **End of life** (IT, askers): I9 → A10. *IT mockup frame 7.*

6. **Publish** (researchers): P1 → P3 → P2 → P4 → hand-off to IT (P5) or the
   agent pack (P10); later P7 and P6, P9, and the P8 stop. *Publisher mockup,
   frames 1–9.*

## 9. Open product questions for the owner

1. **Name.** "Research agent"? What the asker sees: @UXR-ProductX is a
   placeholder.
2. **Is the agent pack a product on its own**, or only the way in to the
   research agent?
3. **Transcripts.** Curated quotes only, or may the publisher include full
   transcripts (more answerable, much more disclosed)?
4. **Who owns it after a freelancer leaves?** And who can act on a
   participant withdrawing consent once the researcher has gone?
5. **Codebooks across contributors.** Two researchers with different codebooks:
   is "counts aren't comparable across these studies" enough, or should a
   collection share one?
6. **Who pays, and for what?** Out of scope here; noted so it isn't forgotten.
7. **Publishing the agent pack: save into a synced folder, or sign in and
   upload (P10)?** Saving into the OneDrive or Google Drive folder already on
   the researcher's Mac needs no sign-in at all. Uploading needs the reverse of
   cloud import's sign-in, with the consent gates that import already met
   (Appendix A). Either way, creating the agent itself stays a guided last
   step the researcher does in the builder.

## 10. Out of scope for the first version

- Video clips.
- Askers changing anything (stars, tags, comments).
- Live sync from a researcher's Mac.
- Bristlenose hosting anything.

---

## Appendix A: implementation questions, parked

Parked by the owner on 22 Nov 2026 until the product strategy is settled. Kept
so the thinking isn't lost; none of it is a requirement yet.

- **Packaging.** One generic container image; studies published into it, kept
  apart from the software so updates never touch the data and deleting a study
  is deleting a file.
- **A slim install.** `faster-whisper`, `av` and the Presidio packages are core
  dependencies in `pyproject.toml`, so an image would carry transcription and
  redaction it never uses. Needs a dependency split, which touches every
  channel.
- **What IT's security review will ask of the image:** amd64 and arm64; a
  signature and an SBOM; non-root with a read-only filesystem; a health
  endpoint; no outbound calls in MCP-only mode; logs that never hold quotes.
  A chiselled Ubuntu Python rock with Pebble health checks covers most of it;
  the signature and SBOM would be ours.
- **Sign-in.** Let the platform's front door do it: Azure Container Apps with
  Entra ID ("assignment required" plus a group), or Cloud Run with
  Identity-Aware Proxy. Slack (signed requests) and Figma Make, Claude and
  ChatGPT connectors (MCP's OAuth flow) need their own paths. On Google, IAP
  passes who the user is but not their groups, so access per collection needs
  either a group lookup or one service per collection.
- **Fail closed.** It shouldn't serve a quote without a sign-in in front of it
  (scenario P8). How it detects "a front door is present" without being fooled
  by a header is the hard part.
- **Concurrent publishing** (P6): the agent owns each collection's list of
  studies and applies a publish as "add or replace my studies".
- **Several studies per answer.** The MCP tools take one `project_id` per call
  today; searching across a collection is new.
- **A model inside it**, for a Slack bot that answers on its own, would use the
  client's own key and change the "no outbound calls" statement.
- **Function-only hosts** (Netlify, Vercel) can't run a container; supporting
  them would mean a second implementation of the grounding core.
- **Publishing the agent pack is cloud import in reverse, for files only**
  (P10; owner's question, 22 Nov 2026). What
  [`design-cloud-import.md`](design-cloud-import.md) learnt applies directly:
  - **Google:** import already stays on `drive.file`, which is non-sensitive
    and also covers files the app *creates*. Writing the pack into the
    researcher's Drive should need no new scope tier and no verification
    beyond what import carries. Not measured.
  - **Microsoft:** import holds `Files.Read`. Writing to the researcher's
    OneDrive is `Files.ReadWrite`, behind the same Publisher Verification and
    tenant consent-policy gates import hit. Writing to a team's SharePoint
    site means `Sites.ReadWrite.All`, which is admin-consent only: the
    procurement gate import was designed to avoid. So publish to the
    researcher's own OneDrive, and share from there (Agent Builder accepts
    OneDrive folders as knowledge since May 2026).
  - **Creating the agent** (a Copilot agent, a Gem) has no user-consentable
    route that I know of: Gems have no public creation API, and a Copilot
    declarative agent is an app package that tenants often block from
    upload. That step stays guided, done by the researcher in the builder.
  - **The zero-sign-in route:** save the pack into the OneDrive or Google
    Drive folder their sync client already keeps on the Mac, through a save
    panel. No OAuth, no consent screen. (Cloud-backed folders bring the
    placeholder-file rules in `docs/design-cloud-files.md`.)
  - Import's lesson stands: a consent check passed on our own tenant proves
    nothing, because its owner is a Global Administrator. Test on a
    client-shaped tenant.
- **The same code as serve mode**, not a fork: `grounding.py`, `mcp_server.py`,
  `INVARIANTS`; the study snapshot shares its data with the HTML export
  (`EMBED_PATH_TEMPLATES` in `routes/export.py`).

## Appendix B: evidence (external facts, dated)

Checked 22 Nov 2026 by web search. These platforms change monthly; re-check
before building.

| Fact | Source |
|---|---|
| Figma Make custom connectors must be publicly reachable HTTPS MCP servers; localhost and stdio aren't supported; org admins control who may add them | [Figma Help](https://help.figma.com/hc/en-us/articles/35440096186007-Connect-external-tools-to-Figma-Make-using-MCP) |
| Dovetail and Marvin are among Figma Make's certified connectors | [CMSWire](https://www.cmswire.com/digital-experience/figma-make-adds-custom-model-context-protocol-6-new-connectors) |
| Teams channel agents and Copilot declarative agents register MCP servers by URL, with admin approval | [Microsoft Support](https://support.microsoft.com/en-us/teams/chat-channels/use-channel-agent-with-jira-asana-and-github), [Microsoft 365 Dev Blog](https://devblogs.microsoft.com/microsoft365dev/build-declarative-agents-for-microsoft-365-copilot-with-mcp/) |
| Microsoft 365 Copilot Agent Builder: share to teams (Mar 2026), OneDrive folders and up to 50 files (May 2026), SharePoint lists up to 20,000 items (Jul 2026); "can't be used in Teams Chat" | [Microsoft 365 Copilot release notes](https://learn.microsoft.com/en-us/microsoft-365-copilot/release-notes) |
| Gems with Drive files can be shared, subject to Drive sharing settings; Gems becoming "skills" (16 Nov 2026) | [Google: share a Gem](https://support.google.com/gemini/answer/16504957), [Workspace Updates](https://workspaceupdates.googleblog.com/2026/11/share-skills-add-files-from-Drive-Notebook-Photos-to-skills-Gemini-app.html) |
| Slack Socket Mode needs no public endpoint but can't be listed in the Slack Marketplace | [Slack](https://docs.slack.dev/apis/events-api/using-socket-mode/) |
| Cloud Run can enable IAP directly, without a load balancer; same-organisation identities only | [Google Cloud](https://docs.cloud.google.com/iap/docs/enabling-cloud-run) |
| Rockcraft `fastapi-framework` extension; chiselled Ubuntu; 12-year LTS offer | [Rockcraft](https://documentation.ubuntu.com/rockcraft/1.19/reference/extensions/fastapi-framework/), [Ubuntu](https://ubuntu.com/blog/chiselled-ubuntu-ga), [Ubuntu](https://ubuntu.com/blog/canonical-offers-12-year-lts-for-any-open-source-docker-image) |
| Programmatic tool calling: the model writes code that calls tools in a sandbox; not available with MCP-connector tools | [Claude Platform docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) |

From general knowledge, not checked: Azure Container Apps' built-in Entra ID
sign-in with "assignment required"; Rockcraft multi-arch builds, the 12-factor
extensions' non-root user and Pebble health checks; IAP access for a
Workspace group.
