# Changelog

All notable changes to Bristlenose are documented here. See also the [README](README.md) for the latest releases.

**0.43.0** — _24 Oct 2026_

The reliability burn-down: in five days well over a hundred ways for Bristlenose to fail, lose work or stay quiet were found and closed. Analyses stop, resume and fail honestly; changes that don't save say so and take themselves back; a crash in one part of the report leaves the rest working; and a failure that survives its retry offers to send a problem report.

**New**

- **Problem reports.** When something fails and still fails after Retry, Bristlenose offers to send a problem report. This covers the Mac app failing to start (Show details, Send Feedback) and the report crashing as a whole. The feedback form opens as a problem report with the details filled in, in the Mac app and the browser.
- **Right-click menus in the Mac app say exactly what each item does.** A blue timecode plays. A badge opens the transcript. A quote card offers Star or Unstar, Hide, Add Tag…, Copy Quote and its transcript. Each item has a "…in New Window" twin: Quotes ▸ Show in Transcript, Open Transcript in New Window. The menus are in all 21 languages, and they keep their items after the report reloads. WebKit's own Download, Share and new-window items are gone.
- **A new window can open at a place in the study**, such as a transcript at a moment or a Quotes section. It waits for the report before going there. ⌘-click on a Dashboard featured quote opens its transcript in a new window again.
- **View ▸ Reload Report (⌘R)** in the Mac app, also on the report's right-click menu.
- **A first analysis on a new Mac starts at once.** On macOS 26 and later, in Apple's nine languages, it transcribes with Apple's on-device speech model while Whisper downloads. Whisper now downloads in the background from launch, once the AI disclosure is accepted and only with 20 GB free, with progress in the toolbar. A session in another language waits for Whisper and runs on its own when it arrives. To turn Apple's model off, run `defaults write app.bristlenose BristlenoseAppleSpeech -bool NO`.
- **A sixth provider in the CLI, any-llm: Mistral, OpenRouter and others.** `bristlenose configure any-llm` stores the model and key and checks them with the run's own request. `bristlenose use mistral:mistral-large-latest` switches between stored models. It's an optional extra, `bristlenose[any-llm]`.
- **A report that can't be shown says so.** "This report couldn't be shown." comes with Retry instead of a bare "Error". In the Mac app the project's row shows a warning, and its popover offers Copy details. The row clears when the report renders again.
- **`run --clean` asks before it discards your stars, tags and edits.** It lists them and asks, as the Mac's Re-analyse does. `--yes` skips the question, and a script with no terminal is refused rather than left to guess.

**Improved**

- **Every detail pane in the Mac app says what happened, in plain words, and offers the one thing that helps.**
  - No selection: "Drop a folder of recordings or transcripts".
  - An empty project: "Drag interviews here".
  - Several projects selected: "3 projects selected".
  - Folder moved: "Can't find this project's folder".
  - A drive and a network share each have their own pane, named by their own name: "“Samsung T7” isn't connected", "“server.local” can't be reached", then "Reconnect to continue."
  - A run that ended with the app: "The analysis stopped before it finished", with Resume Analysis.
  - A Stop: "Analysis stopped", with Resume Analysis. A Stop over an earlier report shows that report.
  - No provider: "Choose an AI provider to analyse this project", with Set Up Provider….
  - A failure: "The analysis didn't finish", the reason in a sentence, the button that remedy allows, and Show details.
  - The analysing pane shows the row's ring, and "Stopping…" while a Stop plays out.
  - The engine-failed pane is the standard macOS one.
  - The browser's status pages say the same things.
- **Dialogs look and behave like macOS sheets.** All nine report dialogs draw through one shared component: Export, Feedback, Miro, FigJam, Settings, AutoCode Review, Uninstall codebook and the two merge confirms.
  - They drop into place and rise out.
  - The page behind is greyed, not blacked out.
  - Escape closes only the topmost dialog.
  - Focus goes in on open and back where it was on close.
  - Tab stays inside the dialog.
  - Every one has a close button.
  - A click outside never closes a dialog.
- **Re-analyse is a clean fresh start that keeps what it should.** Your exported clips and screens move into the new output under the old analysis's date. A Re-analyse that fails, stops or crashes after finishing a session keeps that session for Analyse to finish. Only a confirmed Re-analyse replaces a report.
- **A partial run says how much it analysed.** The sidebar reads "6 of 8 sessions analysed" instead of "Partial completion". A CLI run that lost recordings ends "Done with warnings — 8 of 10 sessions analysed", not "✓ Done".
- **After an analysis, lenses update quietly.** Nothing dims while a lens reads the new results, a failed read is tried once more and leaves the lens as it was, and new data fades in as it arrives.
- **A speaker you recode into or out of participant is picked up by the next Analyse.** That session's quotes are found again from the right speaker, together with any new files. The separate Re-analyse button on the Sessions row is gone. Analyse is also offered after a run that finished with some sessions failed.
- **The Mac app remembers the report's zoom, quote grouping and panel sizes across a relaunch**, and zoom also survives a reload.
- **A first analysis shows the speech-model download** on the progress ring and the row, then starts again for the analysis, instead of looking stuck.
- **The progress ring fills stage by stage.** "Grouping themes" moves within its own share of the ring instead of racing to the end the moment it starts. A new stage no longer shows the previous stage's "8 of 8".
- **The raw transcripts folder says not to edit it.** `transcripts-raw/` holds a README: these are the transcripts as first transcribed, written again on every run, and corrections belong in the report.
- **Toasts are spoken** by VoiceOver and screen readers, in the report and the Mac app. VoiceOver also announces an API key that couldn't be saved, and the verdict on a key you pasted.
- **Files added while a study is being analysed are copied in**, and wait as "+N unanalysed" for the next analysis.
- **The codebook library cards name their authors** the way the codebook page and sidebar do, with the title bolder above. Their Install and Uninstall buttons are back to the system size.
- **The FigJam plugin shows progress and Stop for a board file dropped on the canvas**, as it does for one it builds.
- **A reply that breaks one quote keeps the others.** If a model returns one incomplete quote, the session keeps the rest and the CLI says "1 incomplete quote left out (s10)". If more are broken than kept, the session fails and is retried rather than kept lopsided.
- **The certificate bundle drops the compromised emSign root.** `certifi` is floored at 2026.10.19, which upgrades through pipx and Homebrew now pick up.
- **`bristlenose serve` prints its access token only for the Mac app**, not into terminal scrollback or a piped log.
- **onnxruntime's startup GPU warnings go to the log**, not the terminal.

**Fixed**

_Stopping, quitting and resuming_

- **Quitting during an analysis left it to fail.** On relaunch the row read "Resuming…" and then "CLI exited with code 1". Quitting or force-quitting now stops the run cleanly, and Resume Analysis picks up where it left off.
- **Quitting dropped the studies waiting to be analysed.** Reopening Bristlenose within four days now starts them again in order, the one in progress first, unless a study's folder has gone or holds nothing to analyse. A restored queue waits for the AI disclosure.
- **Stop could take minutes during transcription.** It now ends the run within 30 seconds whatever it is doing, and almost always at once.
- **Stopping a run that took a while to wind down read "Analysis stopped unexpectedly".** It now reads Stopped, and the run's history records a stop rather than a failure.
- **Stopping an analysis left the row blank.** It now says Stopped, as a reconnected run already did.
- **Stopping a re-run made the next run redo every recording.** Work a stopped run had already finished is now kept, so the next run does only what is left.
- **Stopping or quitting could leave a run's helper processes going.** Stop and Quit now reach everything the analysis started.
- **Quitting the Mac app during a stalled first download ends the run within 20 seconds.**
- **Quitting the Mac app while it was putting a previous report back could leave the report missing.**
- **Stopping a re-analysis while it cleaned up could bring back the old report over the new one.**
- **Stopping a run that was slow to stop could leave the report hidden until the next run.** It is now put back before the run exits.
- **A run that ended after the Mac app had gone was recorded as failed.** It is recorded as stopped.
- **Closing the terminal mid-run was recorded as a crash.** It is recorded as stopped.
- **A stopped or failed analysis could only be restarted from scratch.** If it ended after transcription, the only choice was Re-analyse, which discards your work. Analyse is now offered too and carries on where the run left off.
- **A Re-analyse that had to wait for another study ended on the old report.** It now starts afresh when its turn comes.
- **A study could stay on "Analysing" for good** if it finished just as another was started. It now settles, and the other starts after it.
- **A Mac run could read "stopped unexpectedly" in its first moments.**
- **A run started from Terminal on a study in the sidebar read "Analysis stopped unexpectedly" while it ran.** It now reads Analysing and settles to its real end a few seconds after it finishes.
- **An analysis started in Terminal while the app was open went unnoticed.** Switching back to Bristlenose now shows it as Analysing until it ends. Stop isn't offered on it; stop it in Terminal.
- **Quitting a second copy of the app could stop the first copy's analysis.**
- **"Analysis stopped unexpectedly" could outlive a fresh report.** It now clears when a later run finishes.
- **A run that failed with an explanation sometimes said only "Failed".** The reason is now read before the failure is named.
- **A run that finished on a slow or sleeping drive read "Not responding" until relaunch.** The app now reads the project again until the drive answers, including for a run it reconnected to.
- **A reconnected analysis on an unresponsive drive could read "Analysing" until you quit.** The app now notices when it ends, and the Mac can sleep again.
- **An unresponsive network drive stopped the analyses queued behind it.** The study on it says "Not responding" and the next one starts.

_Your curation: stars, tags, hides, edits, undo_

- **Tags, stars, hides and edits could vanish from quotes you hadn't touched.** Each change now saves only the quotes it was made on. Before, it could erase the tags AutoCode added after a run, the curation of quotes a speaker recode had set aside, and, from a transcript's margin, every other quote's tags. A deleted tag no longer comes back under Uncategorised.
- **"Couldn't save" left the change on screen anyway.** A star, hide, tag or edit that doesn't save is now taken back.
- **A refresh in the middle of curating could undo changes still being saved.** Changes in flight, and AutoCode accepts and denies, are kept.
- **Undo offered steps that never saved.** If a star, hide, tag, edit or speaker name fails to save, Edit ▸ Undo names the step before it.
- **Undoing the removal of an AutoCode tag brought it back as your own.** It now comes back as AutoCode.
- **Deleting a sentiment badge couldn't be undone.** Edit ▸ Undo Remove Tag (⌘Z) now brings it back.
- **An open transcript didn't show an undo made elsewhere.** Undoing a star, hide, tag or badge change in Quotes while that session's transcript was open left the transcript showing the old state. It now reads again after the undo, without bringing back a badge or tag deleted meanwhile.
- **A refused undo or redo of a paragraph split, join or speaker move said nothing.** It now says so, and Edit offers the same Undo again, not a Redo.
- **A failed undo of a speaker name said nothing.** The name goes back to what it was, and you can try the undo again.
- **A rename on the Sessions grid that didn't save kept showing the new name.** The grid puts the old name back.
- **Clicking into a quote or heading and out again recorded an edit.** Nothing is written now unless you changed something, spacing included.
- **A quote edit in progress was lost when you switched lens** with ⌘1–5 or the sidebar. It is now kept.
- **Re-analyse could skip its "you'll lose N edits" warning.** Stars and tags made in the current session were invisible to the check; they now count.
- **Re-analyse could discard your work without asking.** When Bristlenose couldn't read a study's stars, tags and edits, it treated them as none and rebuilt straight away. It now asks first, and says it couldn't count them.
- **Re-analyse could discard a star made moments before without asking.** If the report was busy reading at the instant you starred a quote, the count could miss it. The app now asks whenever it can't be sure the count is complete.
- **Two quotes that started at the same moment could collapse into one.** The second now keeps its own row and its own id. A star, hide, tag or edit on it stays on it across re-analyses, and existing projects keep every id they had.
- **A change to a quote that a re-analysis had removed said only "Couldn't save".** It now says the quote is no longer in the report, and the quote leaves the screen.
- **A tag name another tag already used was refused with only "Couldn't save your change."** It now opens the "already taken" dialog that renaming a group uses.
- **Showing or hiding a tag group could un-hide your other groups.** Each eye now saves only its own groups, and a failed save puts the eye back.
- **A tag group's eye could flip back** if it was clicked while the sidebar was loading.
- **A tab left open across a serve restart couldn't save, and didn't say why.** It now says Bristlenose has restarted and to reload the page. The Mac app never shows this, because its report reconnects by itself.

_Hidden quotes_

- **A hidden quote still counted.** Signals, the session sentiment bars and the Dashboard's featured quotes now leave out quotes you've hidden, matching the chat lens. A starred quote you then hid is no longer cut as a video clip. The Quotes lens still lists hidden quotes so you can unhide them.
- **The Dashboard's quote and tag counts included hidden quotes.** They now match the Quotes lens.
- **An export of selected quotes included ones you'd hidden.** Exporting a selection to CSV, Excel, Miro or FigJam now leaves out hidden quotes, as the whole-project export always has.
- **Codebook counts included other projects' quotes.** A tag's count in the Codebook lens could include quotes from other projects using the same codebook. It now counts this project's quotes only, and leaves out hidden ones.

_AutoCode and codebooks_

- **AutoCode left some sessions uncoded for good.** If some of a codebook's batches failed, the sessions in them were never coded by that codebook again. Bristlenose now remembers which sessions each codebook has finished, so the next analysis, or switching the codebook back on, codes the rest. A stopped re-code keeps what it had already tagged, and a codebook's suggested tags no longer disappear from Quotes while it re-codes.
- **Applying a codebook again after stopping it re-coded everything.** It paid again for quotes already coded and brought back tags you had rejected. It now sends only the quotes the stopped run never reached. Apply while a stopped run's batch is still out is refused with "Already tagging with this codebook."
- **A finished AutoCode run didn't show its proposals until a reload.** Quotes, its tag sidebar, Discussion and Screens now update when it finishes.
- **Switching a codebook back on re-coded its new sessions without a word.** It now shows a progress chip, a reload brings it back, and a catch-up that fails says so instead of reporting done.
- **Turning a codebook off and on during re-coding started a second re-coding.** The first one is left to finish.
- **Re-coding chips said "some batches failed" when nothing had.** Each re-code reports its own result.
- **A failed re-coding said only "Tagging failed."** It now says why, for example that the account is out of credit.
- **Stopping a re-code didn't stop it.** A Stop ends it, and the sessions it hadn't reached are coded next time.
- **A run finishing during a re-code could undo it.** The two no longer run together.
- **A reinstalled codebook's run showed the previous run's "Done".** It now gets its own chip.
- **The AutoCode catch-up chip was in English in every language.** It now reads "Coding the remaining sessions…" in all 21.
- **Accepting or rejecting an AutoCode suggestion could look done when it hadn't saved.** It now says so, and the suggestion comes back, or follows whatever was decided elsewhere.
- **Codebook edits and on/off switches could fail without a word.** A rename, move, merge, delete or switch that doesn't save now says so, and the codebook shows what was saved.

_Files, folders and recordings_

- **The same interview under two names was transcribed twice and counted as two participants.** A Finder copy or a renamed download beside its original is now one session. The copy is listed in the Files bucket as a second recording, Whisper runs once, and Signals count the interview once. A re-exported or trimmed recording is still a different recording. On a study analysed before this fix, the next run folds the duplicate away, and any stars, tags or edits on the duplicate's quotes go with it. That's rare: it needs both a duplicate and curation on it.
- **The same transcript downloaded twice counted as two participants.** `transcript.vtt` beside `transcript (1).vtt`, or a Teams `.vtt` and `.docx` pair taken twice, is now one session. The copy is listed under Files and never read.
- **A meeting recorded with Zoom's desktop app came out as several interviews.** Today's Zoom names the folder without a meeting ID, so the video, the audio and each person's separate track were analysed apart. Each meeting folder is now one session, and the combined audio is the one transcribed.
- **A transcript or recording added beside an interview you'd already analysed changed it.** The next Analyse paid for that interview again, renumbered its speakers and gave starred quotes uncurated twins. The new file is now set aside and named in the run's summary, and Re-analyse reads it.
- **A study with its interviews in participant folders looked empty in the Mac app.** It now counts files the way analysis finds them, up to three folders deep, shows how many there are to analyse and offers Analyse. The never-run status page finds them too.
- **An empty folder, or one with nothing Bristlenose reads, ended "Done" on an empty report.** The run stops with "No analysable interviews found.", and a Re-analyse of an emptied folder keeps the previous report.
- **`analyze` on a folder with no transcripts finished as if it had worked.** It now stops with an error.
- **`analyze` skipped plain-text transcripts with no timecodes without saying so.** It names each one under "files not analysed" as a format it doesn't read.
- **A folder Bristlenose couldn't read didn't list the files it had passed over.** `run` and `transcribe` record each one with its reason, so the Mac app can show them too.
- **`bristlenose run` or `analyze` on your home folder or a system folder crashed with a traceback.** It now refuses the folder by its full path and writes nothing, including when the report would have landed in your home folder. In the Mac app such a study says why and refuses dropped or added files.
- **A recording and its transcript whose names differed only in how an accent was stored were treated as two sessions.** They are now one, and a linked folder no longer doubles sessions or loops.
- **Subtitles and transcripts saved as Windows-1252 or UTF-16 weren't read.** They are now; a legacy non-Western encoding is refused rather than misread.
- **A subtitle cue with a malformed time was moved to 0:00.** It is now skipped and logged.
- **An empty or unreadable subtitle file was reported as a recording in which nothing was said.** It is now reported as empty or unreadable.
- **A transcript emptied to its header was called "Not a format Bristlenose reads."** It now says the transcript has no lines.
- **A Word lock file (`~$…`) was analysed as an extra session.**
- **In a Teams `.docx`, a line ending in a time such as "10:30" could be read as a speaker heading.** Only the real heading is a speaker now.
- **The help and man page listed `.txt` as an accepted transcript.** Bristlenose doesn't read plain-text files, and the lists now match what it accepts.
- **A typo in `people.yaml`, or one damaged file, stopped the report opening.** The report opens without the damaged file, and the log names it. A run with a damaged `people.yaml` finishes without the names in it, leaves your file exactly as it is, and the terminal names the line to fix. An unreadable quote file imports nothing rather than half its quotes.
- **A damaged progress record stopped `run` and `status`.** `run` keeps a copy, says every stage runs again, and starts afresh. `status` no longer says there's no record.
- **On the Mac, a damaged project file read "Can't be read".** It now reads "Project file damaged" and offers Analyse to rebuild it.
- **An unreadable project list emptied the sidebar without a word.** The Mac app says why, and that your projects and their edits are safe in their folders.
- **A damaged word-timing cache cost the whole session.** It now costs only the word timings.

_Cloud folders, drives and network shares_

- **Dropping a recording still in iCloud froze the copy until you force-quit.** The drop is now refused straight away.
- **Choosing a discussion guide still in iCloud froze the app.** Bristlenose says the guide isn't downloaded yet and leaves the project as it was.
- **A recording not downloaded in time failed the whole run.** It is now that session's own failure, "Wasn't downloaded to this Mac in time.", which the next run retries. The other sessions go on.
- **A stalled cloud provider could hold a run for hours.** After a provider's first timeout, its other files wait two minutes, not thirty, so twenty stalled files cost about 40–70 minutes, not 2½–10 hours. Audio-only placeholders, which had no limit at all, now have one.
- **Analyse ran a study whose drive had been ejected.** The row now says "Folder not found", and the next study in the queue goes ahead.
- **A study whose iCloud, Dropbox or OneDrive folder had been deleted or moved was still analysed, and failed.** It now shows as a missing folder with Locate…, like an ejected drive. A folder whose files are only stored online still analyses, downloading each file as it goes.
- **A vanished cloud folder was labelled "In iCloud",** with advice to connect a drive and no Locate…. It is now the Can't Find pane with Locate….
- **A study stayed on "Folder not found" after its drive or folder came back.** It updates on its own, without relaunching.
- **A study added through a linked folder opened once, then read "Can't be read".** The app keeps access to the folder the link points to, so the study opens after a relaunch.
- **Cloud messages promised more than Bristlenose can know.** They say what is known and stop: no "download it in Finder", no "still downloading", no "yet".

_Providers, keys and the LLM_

- **Setup could say your API key was fine, then the run failed on it.** The key check now sends the same model and settings the analysis uses, so a refused setting fails at setup, in the provider's own words. `bristlenose doctor` does the same for an Azure OpenAI deployment.
- **A new key, endpoint, model or output limit wasn't checked the same day.** Changing any of them within 24 hours skipped the check before a run, so a bad one failed at the first stage. It's checked again now.
- **A model the provider has retired showed as "the provider rejected the request".** Bristlenose now says the model is unavailable and where to choose another.
- **A Gemini run could hang for good after the Mac slept or changed network.** Gemini calls now time out after ten minutes and retry, as Claude's and ChatGPT's do.
- **A lost connection on ChatGPT or Gemini showed a generic failure.** It now says the provider couldn't be reached, as Claude's always did.
- **With no AI provider set up, adding interviews started an analysis that could only fail**, then said "Something went wrong" and "No interviews to analyse yet". The study now says no AI provider is set up, with Set Up Provider…, and Analyse runs once a key is saved.
- **A long, dense interview could run for over an hour and then fail.** Quote extraction splits such a session rather than waiting on one oversized request.
- **A failed speaker-identification call wasn't retried.** The next run retries it.
- **A grouping that fell back after a failed call kept its fallback.** If one of the two grouping calls failed, every later analysis reused the fallback grouping. The next Analyse tries both calls again.
- **The "Out of credit" notice stayed lit after a top-up and a successful run, or could go out after a run that never contacted the provider.** It now clears only after a run that actually used that provider.
- **The run summary could name the wrong model.** An Azure run printed Claude's price. The reported model is now the one that ran.
- **Provider errors and failed replies could be logged in full.** The log now keeps a status, a message and field names, never the reply or the provider's body.

_API keys and Settings (Mac)_

- **An API key that failed to save looked saved.** Settings ▸ LLM Provider now says so under the field and keeps your pasted key, so you can press Return to try again. If you move to another provider, that provider's row reads "Key not saved".
- **A pasted API key could be lost.** Closing Settings, switching back to your report, picking another provider or quitting before pressing Return now saves it.
- **Showing a half-typed API key saved it.** The show/hide button no longer saves the key or reloads the report.
- **A key the Keychain refused could still be used in Terminal.** When Settings couldn't save a new key over the old one, `bristlenose run` still switched to the new key while the app kept the old one. Now neither changes until the save works.
- **A key first set up with `bristlenose configure` couldn't be removed in the Mac app: it came straight back.** Remove now keeps it out of the app until the CLI writes it afresh, and the CLI keeps its copy. Clear in Settings also reads back, so a key the Keychain kept is shown rather than an empty field.
- **Changing LLM settings reloaded the report over and over.** Tabbing through the key field, dragging the concurrency slider or typing an Azure address reloads it once, when you've finished, and only if something changed.
- **A setting changed while a study was opening never reached it.** A new key, a provider switch or Anonymise now applies to the study that is still opening. A setting changed then no longer briefly says it stopped.
- **The first launch on a new Mac could fail with "Bristlenose didn't finish starting".** A slow first start is now given time, and a start that crashes still says so at once.
- **Install for Claude Desktop or ChatGPT could fail without a word.** It now says the installation couldn't start, under the button. When it falls back to the older extension, the tab shows how to let Claude read Bristlenose.
- **A stored sign-in this build couldn't read couldn't be removed.** It is now listed as needing sign-in.

_The report: crashes, lenses and chips_

- **A crash in one lens, sidebar, the header, tab bar, footer or a dialog blanked the whole report.** The broken part now shows a quiet broken mark, or a short message with Retry in a lens, and the rest keeps working. A crashed dialog can still be closed.
- **A lens that couldn't load showed a raw error such as "GET /transcripts/s3 404".** It now says the lens couldn't be shown, with Retry, and clears once a later load works. The Sessions tab does the same.
- **A failed refresh could replace what was on screen with an error.** Quotes, Dashboard, Codebook, Discussion, Sessions and the Screens board keep what they show.
- **The Screens lens could keep retrying a failed read for hours.** It tries once more, then stops.
- **An activity chip spun for ever when the server restarted or stopped answering.** After a few seconds, or about half a minute if the server hangs, the chip says the task failed and can be dismissed. A finished export stays finished.
- **A reload during AutoCode, a clip export or a screens export lost its progress chip.** The chip comes back with its progress, and an export that finishes during the reload still ends with Show in Finder or reaches the clipboard. Cancel names its export.
- **View Report on a chip that came back after a reload opened nothing** on a first visit to the Codebook lens. It now opens the review.
- **A screenshot that failed to load stayed "unavailable".** It's tried again the next time you show it.
- **A transcript's Timeline button could disappear after one failed read.**
- **The transcript of a session a re-analysis removed offered a Retry that could never work.** It now says the session is no longer in the report, and links back to All sessions.
- **Clicking a session row on the Project tab did nothing**; only the #N link did. The whole row now opens its transcript.
- **Quotes ▸ Reveal in Transcript did nothing.** It opens the quote's session at the moment the quote starts.
- **A quote edit could be lost if you dragged a crop bracket and put it back.**
- **⌘R on a focused quote applied the last tag instead of reloading, and ⌘T opened the tag box.** Both are left to the browser and the app.
- **An unmeasured session's length read "0m".** It reads "—" everywhere.
- **Two quotes starting in the same second could produce a clip that stopped before the second one ended.** Both are clipped.
- **Report feedback disappeared when it could neither be sent nor copied.** The form stays open with your text.
- **A feedback send that failed looked like it had worked.** All three forms (Mac sheet, report, status page) now say it wasn't sent, keep your text and say where to paste the copy. The Mac shows "Sending…" while it waits.
- **A timecode in threshold review, or Open Link in New Window, replaced the video player** with a report page. Only the player opens the player window now.

_Mac app: sidebar, menus, export and windows_

- **Commands that couldn't run stayed lit and did nothing.** After the report process stopped, the Quotes, Video and Undo menus now dim. Export Report dims until the whole report is there. Send to Miro and Send to FigJam dim when the report server isn't running, and follow the window you're in. Re-analyse is no longer dimmed after a first analysis until you reselected the study.
- **File ▸ Add Files… opened on a study that couldn't take files**, then took them and did nothing. It now dims while a study is analysing, queued, failed, or its folder can't be reached. Markdown files are greyed out.
- **Dropping files on a study that was running, queued, failed or couldn't be reached was accepted and ignored.** The files spring back on both sidebars.
- **Dragging files Bristlenose can't use onto the sidebar looked accepted.** The pointer refuses them.
- **Dropping a folder on the empty window could add a second copy of a study.** It now does what the same drop on the sidebar does.
- **Dropping a folder already in the sidebar showed nothing.** Its row flashes.
- **A new or re-dropped study wasn't scrolled into view.**
- **A new study lost its icon while you typed its name**, and other studies' progress froze until you pressed Return.
- **Deleting a sidebar folder scattered its studies.** They stay together where the folder was.
- **Pressing Export Report twice opened two save panels.** The second press is ignored.
- **Export Report showed nothing until the save panel opened.** The row reads "Exporting…" meanwhile.
- **A failed export was saved as though it were the report.** You see "The export could not be saved." instead.
- **Ticking Anonymise in the save panel asked you to save twice.**
- **Show in folder on a finished clips or screens export did nothing in the Mac app.** It opens Finder at the clips folder, or with the first screenshot selected.
- **A failed Show in folder said nothing,** and one whose file manager never returned could hang the report server. It now says the folder couldn't be shown, and gives up after 10 seconds.
- **A toast appeared in every open window**, not just the one you were working in.
- **Send Feedback opened a sheet in every open window, or none.** It opens one, in the window that asked.
- **The feedback sheet couldn't be closed while it was loading.** Cancel and Esc work from the moment it appears.
- **Cancelling Send Feedback while it was sending could still copy to the clipboard or say "Thanks".** Cancel and Esc stop the send, and nothing appears afterwards.
- **"~1 min left" read as plural in French, Spanish, Italian, Portuguese and Catalan.** It now agrees in the singular, matching the browser report.
- **Brazilian Portuguese counted zero as plural**, against CLDR. It now counts zero as "one".

_Miro, FigJam and cloud import_

- **A failed Miro status check showed Connect as if you were signed out.** It now says the check failed.
- **Connecting to Miro while the server was down said "check the token".** It now says the server isn't running.
- **Starting a Miro board while not connected was said in English.** It's in the app's language.
- **A Miro board that completed without a link was reported as ready.** It's reported as failed.
- **Closing the Miro sheet mid-load, or cancelling a board build mid-request, was reported as an error.** Both are a cancel.
- **A Miro token that connected but wasn't saved said nothing in the browser.** It now says where it couldn't be saved.
- **A screens board that Miro refused said nothing useful.** It now says so, as the quotes board does.
- **Cloud import:** a declined grant cleared nothing on the sidebar's batch ring, a stopped batch settling late could end the next one, closing Google's Picker marked the rows failed instead of leaving them ticked, a declined Teams sign-in was said in English, and a Zoom name found after sign-in wasn't saved. All five now behave.

_CLI_

- **`transcribe` and `analyze` gave up with a traceback.** They stop with one line, as `run` does.
- **`bristlenose transcribe` transcribed every recording again on a project that had already been run.** It reuses the earlier transcription and transcribes only new or changed recordings. `--whisper-model` or `--whisper-language` still transcribe everything.
- **`transcribe` replaced the speakers a full run had identified.** On a project you had already analysed, it rewrote the transcripts with one guessed speaker and gave participants new numbers. Unchanged recordings now keep the speakers the run found.
- **`transcribe` counted retried sessions as new.** Its "Transcribed … new sessions" line counts only new recordings, as `run`'s does.
- **`bristlenose analyze` on a project you had already run made the next `run` pay again for every session's analysis.** The next `run` keeps what `analyze` produced, and analyses again only a transcript you edited by hand.
- **A project from an older `--skip-transcription` run said "No speech found" for every recording, on every run.** The next run transcribes them, and `--skip-transcription` now prints one line saying how many recordings it didn't transcribe.
- **A recording could be reported as having no speech after an interrupted or damaged cache.** It is transcribed again on the next run.
- **A transcript file that couldn't be read was reported as a recording with no speech from the second run on**, and the recording beside it was transcribed again on every run. It's reported as unreadable on every run, and transcribed once.
- **A damaged speaker or transcription cache could stop a run with an error.** The run redoes that session's speakers or transcription instead.
- **A run with more than ten problems could miss the re-run when Whisper arrived.** It now picks those recordings up, and a run with more than ten waiting says "Waiting for Whisper".
- **`serve` said it rendered a report it couldn't**, printing "Rendered report 0 quotes" after the error.
- **`bristlenose help` listed the removed `render` command.** The help pages also give the right default output and transcripts folders.
- **`bristlenose configure` pointed at itself, and `use`/`configure` didn't say when a `.env` file overrode them.** They now do.
- **`live check --stages` works again.**

**Removed**

- **File ▸ Print and Page Setup are gone for now.** What printed wasn't a usable deliverable: cards below the fold came out blank, the app's controls printed, and real names printed whatever the Anonymise setting said. Printing comes back once it has been designed properly.
- **Archive, which was always dimmed, is gone from the Project and Folder menus.** It returns when it does something.
- **The "In iCloud" state and its cloud glyphs.** A folder that has gone is a folder that has gone.
- **Loose-file studies.** Every study has been a folder since July. A study record older than that loads as a study of its folder.
- **The per-session Re-analyse button on the Sessions row.** A speaker recode is picked up by the next Analyse.

**0.42.0** — _20 Oct 2026_

Quotes in the Discussion lens work like quotes everywhere else, and Re-analyse no longer loses curation made in the same sitting.

**New**

- **Quotes in the Discussion lens are full quote cards.** The timecode plays, the badge opens the transcript, and you can star, hide, tag and edit a quote and take AutoCode's proposals, as on Quotes and Screens. A hidden quote leaves the lens and is counted beside its question. A question with nothing to show is a quiet grey row.

**Improved**

- **The tag sidebar no longer fills with zeros after AutoCode.** Each tag shows one number: what you have accepted, or, before you accept anything, its proposals in grey.
- **Miro boards start in flat colour**, as FigJam boards do; sentiment colour is still offered. Theme columns follow the order of the themes in the Quotes lens, and a long quote is never split where words were cut.

**Fixed**

- **Re-analyse could discard stars, tags and edits made in the same sitting** in the Mac app, without its "you'll lose edits" warning.
- **After a stopped run, the next run redid every session**, unchanged ones included, and paid for the analysis again. It now reuses what the stopped run finished.
- **Teams and Google Meet sign-in didn't start in the Mac app downloaded from bristlenose.app.**
- **A meeting downloaded from Zoom's web portal came in as separate sessions**, the video transcribed from scratch and Zoom's transcript on its own. They are now one session, with Zoom's transcript and speaker names.
- **Quote exports from sessions over an hour long were out of order.** CSV and Excel rows, and board theme columns, put 1:00:05 before 59:00.
- **The Project page flickered between one and two rows of tabs** at some window widths.
- **On Windows, a run could stop with an access-denied error** while the report was open.
- **Code scanning findings closed:** the video player reads only the parameters it uses, and translations and codebook templates load only from Bristlenose's own files.

**Removed**

- **"Link quotes to clips" is hidden on Miro and FigJam boards.** Every link it made pointed at a clip file that didn't exist.

**0.41.0** — _19 Oct 2026_

Miro and FigJam boards show their progress and can be stopped, and a long quote split over several stickies breaks where it reads, in every language Bristlenose speaks.

**New**

- **Building a Miro or FigJam board shows its progress.** What is being placed and how many of how many, a bar, and the time left once there is enough to go on. Stop ends the build and keeps what was made. In Send to Miro, closing the window and opening it again picks the build back up.

**Improved**

- **Long quotes break where they read.** A quote split over two or three stickies breaks at a sentence end, at a cut the quote already marks, or where the participant paused, and never just after a word like "the" or "of". Each language follows its own subtitling and typography rules. Japanese and Chinese break between phrases instead of mid-word.
- **Japanese, Chinese and Korean stickies on Miro are sized for their characters**, so their type matches the rest of the board.
- **In the Discussion lens, the selected session's column is lighter.** A pale band behind its cells replaces the blue outlines, and it slides across when you pick another session.

**Fixed**

- **On Miro, the stickies of a split quote sat apart**, so they read as separate quotes. They now sit much closer.
- **A speaker trailing off showed as "that..…"** where a quote was split.
- **Two labels in the Mac app's Send to Miro window were cut short.**

**0.40.0** — _18 Oct 2026_

The Discussion lens opens on all sessions at once, its guide shows how much each question drew out of each session, and a failed re-analyse no longer leaves the report empty.

**New**

- **The Discussion lens opens on All.** In a study with two or more sessions, each question appears once, with every session's answers beneath it, each led by that session's badge, which opens the session at that question. Sessions that skipped the question are listed under "Not asked in".
- **The guide shows how much each question drew out of each session.** It replaces the session chips and the #N pull-down, and grows with the guide's width: a bar and a count, then a strip with one cell per session, then a grid. A cell's shade is how many quotes it drew compared with the rest of the study.

**Improved**

- **In the Mac app, the transcript's Timeline menu is a native Mac menu.**
- **The Screens lens names its screens, screenshots and quotes in the window subtitle**, as in "23 Screens · 51 Screenshots · 41 Quotes". English now says "screenshot" where it said "screengrab", as every translation already did.

**Fixed**

- **After a failed Re-analyse, the report could reopen empty**, and stars, tags and edits made afterwards went into a set-aside copy rather than the project.
- **A long moderator question's timecode sits beside its first line** in the Discussion lens, not its last.

**0.39.0** — _17 Oct 2026_

Every row of the Sessions lens carries its timeline and a transcript can show it too, the transcript margin links each quote, screen and question to its lens, the Screens lens exports to a folder, the clipboard and Miro, and four new colour palettes arrive in light and dark.

**New**

- **Every session in the Sessions lens shows a thin strip of its interview under its row.** The participant's turns, in the colours of what was on screen. Clicking the strip opens the full timeline at the moment clicked, growing out of the strip; clicking anywhere else on the row opens the transcript. The timeline now flags every visit to a section, not only the first.
- **A transcript can show its session's timeline in place of the journey chain.** The Timeline button at the end of the transcript's header row switches between the two, and its menu sets how much the timeline shows: Compact (sections and speakers), Standard (adds sentiment) or Full (adds themes). While you read, the timeline marks the paragraphs on screen; clicking a flag, a speaker clip or a sentiment bar scrolls the transcript there, and dragging the marked window scrolls the page. In the Mac app, View ▸ Show Session Timeline does the same.
- **The transcript margin links what it marks.** Each quoted passage is marked in a new gutter and links to its section or theme in the Quotes lens; where a session moved to a screen, the margin shows the screen's title and a thumbnail and links to it in the Screens lens; a moderator's question links to it in the Discussion lens. Hovering outlines the passage.
- **The Screens lens exports its screens.** Export Screens writes every screen, one image per participant, full size, to `bristlenose-output/screens`; Copy Screens puts them on the clipboard, to paste into Miro or FigJam as one image each. Send to Miro on the Screens lens builds a board with a frame per screen and everyone's quotes about it beneath. Mac only, as the Screens lens is.
- **Four new palettes: Catppuccin, Gruvbox, Rosé Pine and Solarized**, each in light and dark, in the report, the Mac app's sidebar, the welcome screen and the command line.
- **Miro boards offer square or rectangle stickies, and can break long quotes into a short set of stickies.** The board name arrives filled with the project's name.

**Improved**

- **A link lands with a yellow flash on what it points at**, in every lens, as the transcript already did.
- **A renamed section or theme shows its new name everywhere**: the transcript, the Dashboard, Signals, the exports and agent access, not only the Quotes lens. Links to it keep working after the rename.
- **Miro boards carry each quote in full.** Quotes over 300 characters used to be cut short.
- **A heading in the Quotes contents lands below the search bar on the first click**, not behind it.

**Fixed**

- **The quotes CSV and Excel downloads failed for a project named outside the Latin alphabet**, and the HTML export dropped such a name from its filename. Both now keep the name as typed.
- **The Dashboard's featured quote opens the transcript at the quote**, not at the top.
- **A click on the transcript's journey chain lands its paragraph below the header**, not behind it.
- **The keyboard focus ring was missing in every palette.**
- **Removing an interview now also removes its exported screen images.**

**0.38.0** — _16 Oct 2026_

The Sessions and Quotes lenses open while a first analysis is still running, the Mac app reads the screens participants shared into a new Screens lens, the session timeline shows what was on screen, transcripts in eleven more languages come out punctuated, and a moved, renamed or copied project stays one project.

**New**

- **On a first analysis, you can read each session as soon as it is transcribed, and its quotes as soon as they are found.** The Sessions lens opens while the run is still going: sessions already transcribed can be opened, the one being transcribed shows its filename shimmering, and the rest wait in grey with what is already known about them. The Quotes lens opens at the first session with quotes, grouped by session; once sections and themes exist, a control above the quotes switches between the two groupings, and stars, hides and tags made during the run are kept. Each session's quotes are found while the next is being transcribed, so they arrive during transcription and the whole analysis finishes sooner; a transcript you have open picks them up as they arrive, keeping your place. With PII redaction on, sessions open together when redaction finishes. In the Mac app the analysis animation gives way to the report at the first readable session, and the sidebar and window subtitle say how many sessions can be read so far. Not yet for a resumed run or a re-analyse, which show the finished report as before. Export waits until the run ends.
- **The Mac app reads the screens participants shared, and a Screens lens shows each screen with what was said about it.** With Settings ▸ Transcription ▸ Read shared screens on (the default), each recording with video is read in the background after the report opens. Once a project has screens, the Screens lens joins the rail: each screen once, with the quotes that share its words placed beside it as the report's own quote cards. Drag a card to place it, and Tidy puts them back; the arrangement is kept with the project. What is read stays in the project's output folder, and turning the setting off deletes it. Mac only.
- **The session timeline shows what was on screen.** Inside each speaker clip, a strip of colour follows the recording moment by moment, so the call becoming a screen share, or a browser becoming a terminal, shows as a change in the bar. The strip is computed in the background after the report opens and appears on its own; a project analysed earlier gets it the next time it is opened. Serve only, and only for sessions with video.
- **Resting the pointer on a session's timeline shows the participant's screen at that moment.** A small still appears below the speaker clips, one for each participant turn and one more wherever the screen changes within a turn; it steps as you move along, and clicking while it shows a change opens the transcript just before that change. Taken in the background like the strip, and kept out of exported reports, which carry no participant screens.
- **With diagnostics on, each session's timeline shows how well the recording transcribed.** Under the timeline, a closed Diagnostics line gives the share of windows Whisper had to retry and how long the recording has sound but no words; opened, it adds lanes for sound level, pace, doubtful words and gaps, and the numbers behind them, with links to the places worth a listen. In the Mac app it appears with Settings ▸ Appearance ▸ Show Diagnostics menu turned on, in the browser with `serve --dev`. Numbers only, never in an exported report, and for recordings transcribed from now on; on a Mac with Apple silicon it measures the most.
- **Long answers are broken into paragraphs.** In recordings transcribed from now on, a speaker's paragraph ends at a sentence end once it passes about 60 words. Existing transcripts keep their paragraphs, and the splits and joins made on them.
- **The Mac app's Locate… finds a moved project by itself, on any disk.** Each project's output folder now carries a small `bristlenose-study.txt` with the project's id, which Spotlight can search for; Locate… looks for it first, then asks you to confirm the folder it found. A project analysed before this version gets the file the next time it is opened.
- **A copied project says where it came from.** Hovering its sidebar row reads "Copied from" and the original's name, so two rows with the same name can be told apart.

**Improved**

- **The first Whisper download shows its progress.** The command line used to print a banner and then nothing for minutes while about 1.6 GB downloaded; Hugging Face's progress bar now shows in a terminal, with where the model goes and that Ctrl+C is safe.
- **The session timeline opens at a scale that suits every session, and keeps it.** It used to fit the longest session loaded, so a project of short sessions opened with white space on the right, and an open timeline shrank whenever a longer session arrived. The shortest typical session now fills the width, the longest opens at no more than four widths, and a session far shorter or longer than the rest no longer sets the scale for them.
- **During a first analysis, the timeline is drawn as each session arrives, with its scene colours.** Option-click opens every session readable so far; an open quote stays open when another session arrives.
- **Interviews in Spanish, French, Italian, German, Portuguese, Catalan, Swedish, Danish, Norwegian, Turkish and Korean come out with punctuation and capitals.** On a Mac with Apple silicon, Whisper now gets a punctuated example in each of those languages, as English and Japanese already did, so a transcript no longer drifts into long lower-case runs without full stops. Dutch, Polish, Czech, Russian, Ukrainian and Finnish were measured too and already come out punctuated, so they get none. Applies to recordings transcribed from now on.
- **Speech the transcriber couldn't make out is shown as inaudible, not as invented words.** On a Mac with Apple silicon, a line where Whisper only repeated its own example phrases ("Ainda, hum, na verdade.") is now marked as a gap of that length in the transcript, and its words are not kept, so they cannot be quoted. Applies to recordings transcribed from now on.
- **Whisper's repetition loops are taken out of new transcripts.** On a Mac with Apple silicon, a word or line repeated as many separate lines ("nada nada nada…", or "Gracias." every half minute over music) is removed, and where Whisper's first pass looped, the stretch is transcribed again in case speech was under it.
- **`serve --dev` restarts only for changes to Bristlenose's own Python.** It used to watch the whole working directory, so a sidecar rebuild under `desktop/` restarted the dev server dozens of times.
- **A re-run leaves the videos of sessions already transcribed alone.** Every run used to decode every video again, which for a project in iCloud meant downloading it again. A session's thumbnail is now re-cut when its video changes, where before it was kept for good.
- **Timecodes, tags and codes no longer fall back to Courier.** They draw in the system's monospace face in the Mac app and Safari, Menlo in Chrome, and Cascadia Mono or Consolas on Windows. Every tag is now one weight, and numbers in the Signals lens use the report's body type with aligned digits.
- **Icons across the report come from one set.** Hand-drawn icons, and characters standing in for them (×, ✓, ▶, ▾), are now one icon family whose strokes match the weight of the text beside them.
- **As a browser window narrows, the report gives up its extras in order.** The tab bar tightens, then its icon tabs move up into the header, then the minimap, Contents and Tags close, and the tabs wrap onto a second row only after that, instead of running under the minimap. In the Mac app the minimap goes before the projects column.
- **In the Codebooks lens, a code's bar and count open its quotes**, with the tag sidebar showing just that code, as the tag sidebar's own bars do.

**Fixed**

- **Ctrl+C during the first Whisper download stops it.** It used to be ignored until the whole file had arrived; it now stops within about two seconds, and the next run starts the download again.
- **The Mac app's failure popover says "CLI exited with code N" in the app's language.**
- **A report could come up empty after the first analysis in the Mac app, with every signal green.** The app starts the report server on the next pass after it starts a run, so the server usually came up before the run had made `bristlenose-output/`, rooted its database at the interview folder, and the run's results then landed in a second project row the report never reads. The database and log are now created under `bristlenose-output/` before the first run, a never-analysed project's row names that folder, `serve <folder>` and `serve <folder>/bristlenose-output` are one project (recordings play from either), and the server says so in its log if a second row ever appears. One visible consequence: opening a never-analysed project in the app creates an empty `bristlenose-output/` folder beside the interviews straight away, where it used to leave a hidden `.bristlenose/` folder.
- **The report server follows a replaced output folder.** A failed Re-analyse puts the previous report back, and the next run reclaims one left by a crash; the server used to keep answering from the copy that had been set aside, and curation went into it, until it was restarted. It reattaches to what is on disk the moment the folder changes. If the project folder itself is renamed or moved under a running server, the log says so once; restart the server at the new location.
- **Nothing writes the session registry under a live run.** Swapping or recoding a speaker and reassigning a paragraph to a new moderator are refused while an analysis owns the project (the run would overwrite the write at its end), and the importer no longer carries speaker picks until the run has let go. `run --clean` no longer moves a live run's output out from under it.
- **A session that was transcript-only gains its recording.** Source files are re-verified on every import, so a recording that turns up later plays, and a file that has gone is no longer marked as seen.
- **`bristlenose status` finds the report, and names the stash.** It used to look for `.bristlenose/` at the project root first, and said nothing about a stashed previous report while the output folder was absent, which is when that stash is the only copy. It no longer offers `rm -rf` for it, or calls it "kept while a run is in flight" when no run is.
- **`bristlenose serve` on an output folder outside the interview folder (`run -o`) no longer tries to analyse the folder above it**, which crashed when that was the home folder.
- **Moving, renaming or copying a project folder no longer transcribes every recording again.** The transcription cache was keyed on each file's full path, so any change to the folder's location paid for transcription a second time. A project moved before its first run on this version still re-transcribes once.
- **An interview you removed no longer comes back into the report.** Deleting or renaming a recording left its old transcript in the output folder, and the report rebuilt the session from it. A run now removes the files of sessions that are no longer in the project.
- **Two recordings with the same name in different folders are two sessions.** They were merged into one, and the second was dropped without a word.
- **Renaming a project folder leaves one report, not one per name.**
- **`bristlenose analyze` on a project's own transcripts keeps the project's name.** Pointed at `bristlenose-output/transcripts-raw`, it named the project and its report `transcripts-raw`.
- **The Mac app follows a project folder you rename in Finder.** It kept the report on the old path, and a re-analysis run after the rename never reached the report. A folder moved to the Bin shows as Can't find, with Locate…, instead of being served from there.
- **Reopening the Mac app during an analysis shows that analysis.** The row said Analysing with a Stop button that did nothing, and Analyse could start a second run on the same folder.
- **The Mac app's sidebar says when a project's report database holds a second project**, the shape the empty-report bug above left behind, instead of showing a session count the report could not.
- **In the Codebooks lens, the add-tag chip and a dragged tag are the same size as the tags beside them.**
- **A failed save says why.** Every failed change used to say "check your connection", including the server refusing it while an analysis runs; it now says which.
- **"That's Me" on a moderator works during a first analysis.** It was refused, and read as a connection problem.
- **In the Mac app, `/` focuses the search field on Quotes, as ⌘F does,** and opening the Signals panel puts focus on the first signal.
- **A moved, renamed or copied project stays one project.** The report's database matched its project by folder path, so a moved folder grew a second project and the stars, tags and edits stayed behind on the first. Each project now carries an id in its output folder and its report follows it. A copy gets its own id, its own report and its own agent access, and Re-analyse keeps the id.
- **A renamed or re-filed interview keeps its session.** Recordings are now recognised by their content rather than their name, so renaming one, filing it into a subfolder, or moving the project keeps its session, its names and codes, and when it happened, and does not transcribe it again. A recording renamed while it is still in iCloud is downloaded and recognised before the run goes on. A recording re-exported or trimmed under its old name is a new session, and the old session's quotes no longer play against the new file.
- **Agent access follows a moved project.** A config pasted into an agent keeps working after the project folder moves or is renamed.
- **A report a crashed Re-analyse set aside is put back when the report server starts**, not only by the next run.

**0.37.0** — _12 Oct 2026_

Transcripts come out punctuated, Word tables are read, PII redaction works on the Snap and Fedora packages, and the Sessions Start column shows when a session began.

**New**

- **Transcripts come out punctuated.** Whisper now gets a short punctuated prompt on every 30-second window, in English and Japanese, so a recording no longer turns into long lower-case stretches with no full stops. This applies to recordings transcribed from now on; existing transcripts are not redone.
- **Text inside Word tables is read.** A discussion guide laid out as a table was reported unreadable, and a transcript in a table came out nearly empty. Tables are now read; a timed table that can't be aligned is refused with a clear message. Sessions from `.docx` files are re-parsed on the next run, so their analysis runs again.
- **PII redaction on the Snap and Fedora packages.** They had shipped the wrong language model, so `--redact-pii` failed. The first redacting run now downloads the right model into your own cache, checked against a pinned hash.
- **A session timeline on the Mac app's Welcome screen**, showing how a session's row opens into its timeline.

**Improved**

- **`bristlenose doctor` exits 1 when a check fails**, so a script or CI step can rely on it. Warnings still exit 0.
- **A missing PII model is a warning on pip and Homebrew installs**, since the run downloads it. It had been a failure that stopped `run --redact-pii` before it could.
- **The Welcome screen's background links say where they go** ("Analysis method", "Sentiment taxonomy") instead of "Learn more", in every language.
- **Faster first model download on Windows**, which now uses Hugging Face's Xet transfer.

**Fixed**

- **The Sessions Start column showed when a recording was saved or downloaded, not when the session began.** Start now comes from the recording's own clock, from Bristlenose's import stamp, or from the meeting app's filename (Teams, Zoom, Meet, Screen Recording, Android, OBS). It also no longer shows an hour early during British Summer Time. Re-run a project to correct its existing sessions.
- **Reopening a project whose output folder had lost files could delete your quotes.** With the cluster or theme files missing, quotes went with their hidden flags and tags, and with transcripts gone too, starred and edited quotes and whole sessions. The cleanup now runs only when the output is complete.
- **One duplicate in an AutoCode answer threw away the whole job.** Every proposal was rolled back and a retry failed the same way. The best-scoring proposal per quote is now kept.
- **An anonymised clip export sat beside the previous export's clips**, whose filenames carry participant names. Each export now removes the previous one's clips first.
- **An API key containing a line break could be printed in full** by `doctor` and `run`. It is now refused with a fixed message.
- **On Windows, a `winget.exe` or `nvidia-smi.exe` in the current folder could run in place of the real one.** The same fix 0.36.0 made for ffmpeg and Ollama.
- **Google Meet `.docx` transcripts kept only the first turn after each timestamp.** Every turn is now read; turn times between Meet's timestamps are estimated from text length.
- **A Gemini answer cut off at its output limit failed the session** instead of being split and retried, as with the other providers.
- **`configure local` named a model it never saved**, so the next run asked for a model that wasn't installed.
- **`doctor` reported a local model installed when only a similarly named one was**, and suggested pulling the wrong tag.
- **A failed download of Ollama's install script was reported as "Ollama installed".**
- **An Azure endpoint without `https://` crashed `run`** with a traceback. It now fails the network check with advice.
- **The first transcription printed Hugging Face warnings, each twice**, asking for an access token, Developer Mode or a `pip install`. They are silent now; real download failures still show.
- **`serve` never checked its own dependencies** before starting. It does now.
- **Editing a quote could pull focus back from the tag field** in the same card.
- **In the Mac app's Sessions sidebar, full names could overflow the row** at the width where they first appear.
- **Disconnect Miro could clear the wrong project's connection** in the Mac app when several were open.
- **The Mac app kept removed projects' folders open**, and old report views alive, until it quit.
- **Turning off Agent Access could leave the previous connection file in place** if rewriting it failed. It is now removed.

**0.36.0** — _8 Oct 2026_

Transcript text can be selected across paragraphs and pasted into a document with its timecodes, and the transcript no longer shows a platform's speaker name past anonymisation.

**New**

- **Copy transcript paragraphs into a document.** Drag across as many paragraphs as you like and paste: a plain-text editor gets Markdown, one paragraph per block with its speaker code and timecode; Word and other rich-text editors get the timecode styled as the app draws it. Badges, annotations and buttons are left behind.
- **A paragraph starts with a capital where a sentence begins** — the first paragraph, a new speaker's turn, or after a full stop. This is display only: the transcribed words are unchanged, and a word spelled lower-case on purpose, such as iPhone, keeps its spelling.

**Fixed**

- **A speaker's name from the source transcript could appear past anonymisation.** Imported text kept the label written after each speaker code — "(Speaker B)", or a meeting platform's real name — and it reached exports, search and the agent endpoint. It is now removed on import; "(laughs)" and similar stay.
- **On Windows, an `ffmpeg.exe` or `ollama.exe` in the folder you ran Bristlenose from could run in place of the real one.** A file planted in a client's interview folder would have been run. Bristlenose now looks only in the install folder and in the folders on PATH.
- **Removing a session that had a split, join or move made every later import fail.** Its edits now go with it.
- **A paragraph given to a new moderator could pass that moderator's code, and name, to another voice on a re-run.**
- **A split in a paragraph without word timings appeared at the end of the session** instead of where it was made.
- **Paragraph edits from 0.35.0 could stop applying** after a change to speaker labels or to PII redaction.

**0.35.0** — _7 Oct 2026_

Each session opens into a timeline of the interview, a speaker's role can be changed after the fact, and transcript paragraphs can be split, joined and moved to another speaker.

**New**

- **Each session can open into a timeline.** In the Sessions lens, the chevron beside a session number opens a strip under that row that runs the length of the interview. It shows where each section starts, who is talking, every quote as a sentiment mark (positive above the line, negative below), and the span of each theme. The talking turns are tinted with the colour of what was on screen at the time. Click the strip to open the transcript at that moment, or click a sentiment mark to read the quote. One zoom control sets the scale for every open timeline, and they stay open when you come back from a transcript. On-screen colours are worked out when a project is run, so a project analysed before 0.35.0, or with `analyze` alone, shows plain grey turns until its next `run`.
- **Change a speaker's role.** In the person picker, a moderator can now be made an observer and back, and any speaker can be moved into or out of participant. The picker also opens from the transcript and the dashboard, not only the Sessions page, and it opens on the current name, ready to type over. Edit ▸ Undo takes a change back.
- **Re-analyse one session.** If a participant turns out to have been the moderator, or the other way round, that session's quotes came from the wrong person. They leave the report until the session is re-analysed, and come back with their stars and tags if you undo. The Sessions page offers Re-analyse… on that session, saying what will change and what it costs; on the Mac it runs from there, and in the browser it shows the command to run.
- **Split and join transcript paragraphs.** Place the caret in a paragraph and press Return to split it in two; Backspace at the start of a paragraph joins it to the one above when both are the same speaker. The words themselves can't be edited — they are the recording's. A split survives a re-run, and Undo takes it back.
- **Move one paragraph to another speaker.** The transcript's picker has a **Session | Paragraph** switch: Session changes who the speaker is throughout, Paragraph gives just that paragraph to someone else — including a new moderator, for a call where two voices were heard as one. A quote whose words moved away from its participant leaves that participant.

**Improved**

- **The ✕ in the person picker means "not this person".** The speaker goes back to unknown, and a re-run won't propose that name again.
- **The picker offers only people someone has confirmed.** A name Bristlenose guessed for one speaker no longer appears in every other speaker's list, so one wrong guess doesn't spread.
- **Renaming a person renames them everywhere**, and a name another moderator or observer already has is refused rather than merging the two.
- **Two unknown moderators in one session are told apart** as mA? and mB?.

**Fixed**

- **A new voice in a re-run could take an earlier moderator's code, and their name with it.** A moderator's code is now never reissued within a session.
- **The Star & hide picture on the Welcome screen was cut off in a narrow window.** It now shrinks to fit.
- **The Windows installer said "Bristlenose was not installed" when it had been.** A failure after the install now says Bristlenose is installed, and what went wrong.

**0.34.0** — _5 Oct 2026_

The command-line tool now installs and runs on Windows, through pipx or uv with x64 Python — newly tested there, so expect rough edges. Installing with pipx or uv no longer needs `[serve]`.

**New**

- **One line installs Bristlenose on Windows.** In Terminal, `irm https://bristlenose.app/install.ps1 | iex` installs uv, FFmpeg and Bristlenose for your user, without administrator rights, then runs `bristlenose doctor`; run it again to upgrade. It works on x64 and on Windows on Arm, where Bristlenose runs through x64 Python and transcribes more slowly. If a company proxy or policy blocks a step, INSTALL.md has the same install one command at a time.
- **Local AI installs on Windows.** `bristlenose configure local` now installs Ollama with winget, starts it and downloads a model, as it already did on macOS and Linux. Without winget, it points you to the download page.

**Improved**

- **`pipx install bristlenose` and `uv tool install bristlenose` are the whole install.** The packages behind the report used to come with the `[serve]` extra, and without it Bristlenose could only transcribe. They now come with every install. `'bristlenose[serve]'` still works.
- **`bristlenose doctor` gives Windows users commands they can type:** `winget` for FFmpeg, `setx` rather than `export`, and where the key file really is.

**Fixed**

- **On Windows, every run stopped before it started.** The first record a run writes failed on Windows, so no run got past it, and past that, a run stopped again at its second step.
- **On Windows, a run in progress read as stopped.** A second run on the same folder was not refused, and the report could call a running analysis stranded.
- **On a fresh Windows machine, `bristlenose doctor` said the network was down and `configure` could not check a key.** Windows had not yet fetched the certificate the Claude and ChatGPT servers use; Bristlenose now carries its own copy alongside the system's.
- **Saving `bristlenose doctor` to a file, or piping it, crashed on Windows.** Redirected output now prints `+` for a pass and `x` for a fail.
- **`run --clean` on Windows wrote over the previous report, and a failed run could not put it back.**
- **A recording named in Japanese or Chinese stopped the run on Windows.**
- **On Windows, every run crashed at its very end once a project had made 1,000 AI calls.**
- **Burned-in subtitles were never made on Windows.**
- **`bristlenose configure` on Windows named the key file as `~/.config\bristlenose\.env`.** It now shows the full path.
- **A run could crash as it finished.** The library behind the voice pass, added in 0.33.0, sends usage statistics to Microsoft by default, and its upload could crash Bristlenose on exit. Bristlenose now switches it off.

**0.33.0** — _4 Oct 2026_

A Discussion lens beside your interview guide, speakers told apart by voice, a person picker, search that suggests, and Undo.

**New**

- **The Discussion lens.** Put your interview guide in a folder named "Discussion guide" beside the recordings (on the Mac, **Add your guide…**) and the lens lays the quotes against the questions you planned and the ones you actually asked. The guide is a panel you can show and hide.
- **Speakers are told apart by voice as well as by what they say.** When a recording has no transcript naming its speakers, Bristlenose also compares the two voices and corrects the lines the text alone got wrong — on a test interview, 12 lines wrong instead of 22. It runs on your machine and makes no extra AI call; the first time it is needed it downloads a 40 MB model. Built into the Mac app, Homebrew, the Snap and the Fedora package; with pip, install `bristlenose[serve,voice]`. Turn it off with `BRISTLENOSE_VOICE_PASS=false`.
- **Who is this speaker?** Click a speaker on the Sessions page to confirm the name Bristlenose found, pick another, or type someone new. On the Mac it opens as a native popover; in the browser, as a menu. A name you haven't confirmed yet has a dotted ring and grey text, and screen readers announce it as a proposed name. Press Return to confirm it.
- **Undo for your edits to the report.** Edit ▸ Undo and Redo (⌘Z, ⇧⌘Z; Ctrl+Z and Ctrl+Y off the Mac) take back naming, picking or confirming a speaker, starring, hiding and unhiding quotes, adding and removing tags (a whole selection is one step), and editing a quote, a section or theme title, or a description. On the Mac the menu names what it will undo ("Undo Rename Moderator"). Undo lasts as long as the report is open: reloading, switching project or running a new analysis starts afresh. On the Mac, undoing a quote edit with ⌘Z isn't reliable yet; the revert arrow on the quote card always restores the original text.
- **Search suggests people and tags as you type.** In Quotes, a chosen suggestion becomes a token whose meaning you can change from its menu (said by, mentions, not; tagged, contains, not tagged). Words typed together are found together, in order, and accents and apostrophes don't need typing.

**Improved**

- **Speaker labels now hold for the whole recording.** For a recording without a platform transcript, speakers used to be worked out from the first few minutes and every later line took the last label, so a moderator could be credited with most of an interview. The whole transcript is read now. Projects analysed before this release keep their old labels until analysed afresh. With redaction on, this step sends the whole transcript, unredacted, to your AI provider, where it used to send the first few minutes (`SECURITY.md`).
- **A meeting transcript that names nobody is now split into speakers,** instead of being kept as one voice.
- **A resumed run's time estimate covers only the steps still to run.**
- **On the Mac, the sidebar's + button offers New Project… and New Folder…,** and a new project opens with its name ready to edit.

**Fixed**

- **The dashboard's Words card never appeared.** It now counts the words in your transcripts.
- **Choosing a smaller transcription model with `-w` crashed before transcribing.** On Linux and other non-Apple-Silicon machines, `-w tiny`, `base`, `small` or `medium` failed with "Repository Not Found". Every model name now fetches the model that is used, and the download notice gives that model's real size.
- **A mistyped model name gets a plain answer.** `-w smal` stops before anything downloads and asks whether you meant `small`, listing the names this machine accepts.
- **A session in which nobody was detected as a participant could take a real participant's number,** and its placeholder could overwrite their figures. Participant numbers are now never issued twice.
- **A speaker the pipeline re-detected as an observer could hand their participant number, and the name typed for them, to the next new participant.**
- **`bristlenose transcribe` put every speaker in a session under one participant.** It now numbers moderator and participants as a full run does.

**0.32.0** — _30 Sep 2026_

Exported clips carry subtitles, ChatGPT can read your studies, and the video player learns its keys.

**New**

- **Exported clips carry subtitles.** Each clip gets a `.vtt` file beside it and a subtitle track inside it, tagged with the language that was spoken so QuickTime shows it on a plain double-click. Everyone audible is subtitled, and speakers are told apart by colour, following the BBC's subtitle guidelines. Your corrections to a quote reach its subtitles.
- **Subtitles can be burned into the picture,** for slides and screen shares that ignore a subtitle track. Tick **Burn subtitles into the video** under Extract clips (on the Mac, **Quotes ▸ Burn Subtitles into Clips**) and each clip also gets a `(subtitled)` copy; the clean clip is kept. If your FFmpeg can't draw subtitles, the export says so and still makes the plain clips.
- **The video player shows subtitles.** Switch them on in Settings ▸ Video, or on the Mac with **Video ▸ Subtitles** or the C key.
- **Japanese and Chinese subtitles break between characters,** keeping closing punctuation off the start of a line and opening brackets off the end.
- **Install Plugin… for ChatGPT.** Settings ▸ MCP Agents ▸ ChatGPT & Codex adds Bristlenose to the ChatGPT desktop app in two clicks, with no Node and no config file to edit. Ask in Work mode and start the question with @Bristlenose — ChatGPT doesn't use a plugin otherwise. Bristlenose needs to be in your Applications folder.
- **The video player has keyboard controls on the Mac.** With the player in front: Space plays and pauses, ← → jump 5 seconds, ⌥← ⌥→ jump 30, < and > change speed, C switches subtitles, and fn-F goes full screen. The Video menu shows them while the player is in front.

**Improved**

- **The Claude Desktop extension is now a small helper signed by Bristlenose,** rather than a script run on Claude's own Node. If you installed it before, Settings ▸ MCP Agents offers Update Extension….
- **ChatGPT no longer asks you to approve each tool call.** Bristlenose's tools now declare themselves read-only.
- **The projects column scrolls under the toolbar,** fading out beneath it as in Photos and Notes, instead of stopping at a hard edge with a grey band.

**Fixed**

- **On macOS 27, Claude and ChatGPT couldn't read a shared study, and nothing said why.** macOS 27 blocks another app from reading Bristlenose's files without asking. The new helper reads them with no extra permission, so there is nothing to switch on.
- **Closing the video player and then clicking a timecode could crash the Mac app.**
- **The Video menu was greyed out exactly while the player was in front,** and Picture in Picture did nothing from the menu.
- **Japanese and Chinese transcripts had no word timings,** so playback highlighting could not follow the words as it does in other languages.
- **Transcription failed on a fresh install on Linux, Windows and Intel Macs.** A new release of PyAV, the audio library faster-whisper reads recordings with, broke its decoder on the day it came out. Bristlenose now stays on the previous version until faster-whisper catches up.

**0.31.5** — _29 Sep 2026_

Other programs on your computer can no longer read a project's private files through the report server, and a re-analysis reaches the report without a restart.

**Fixed**

- **Other programs on the same computer could read files the report server should have kept to itself.** While a report was open, another local program could fetch the PII re-identification key, the unredacted transcripts and the run log without the report's token, and a web page could reach the server by pretending to be your own machine. The server now hands out only recordings and the report's own assets without the token, answers only to local addresses, and its sign-in cookie no longer works for pages served from other local ports.
- **A static report could run a script hidden in a transcript.** A speaker name in a supplied .docx or .vtt could break out of the page's embedded data and run when the HTML file was opened. It is now escaped.
- **After Re-analyse, the report could stay on the old analysis until the server was restarted.** A run that is in progress, or that stopped without finishing, also no longer hides the report you already have, and a run that crashed stops reading as in progress.
- **Queuing a re-analysis showed the previous run's failure.** The Mac app now shows "Queued" or "Analysing…" in its place until the new run finishes.
- **The projects column could hide itself when the window was resized and not come back.**

**0.31.4** — _28 Sep 2026_

A recording with no sound no longer comes back as an interview of "Thank you.", and the transcript page shows the whole interview again.

**Fixed**

- **A recording with no sound was transcribed as "Thank you." every thirty seconds, and analysed as an interview.** On the Mac, and at the command line on Apple Silicon, Whisper answers silence with an invented "Thank you." for each thirty-second stretch rather than with nothing, so a 29-minute video whose audio track was silent produced some sixty lines that were then read as a participant's session. Whisper's own no-speech check never fires on the model Bristlenose uses. The audio is now measured before it is transcribed: a recording with nothing in it is reported as "No speech found" and left out, and lines invented over long silences inside a real interview are dropped. Quiet speech is kept — the cut-off sits far below the quietest speaker measured. Speech invented over room tone or music is not caught yet. Projects already transcribed keep their old transcripts until those sessions are transcribed again.
- **Most of a transcript could vanish behind a few words from its first minutes.** Word-level timings were matched to transcript paragraphs by position instead of by time, and the transcript page shows those words in place of the paragraph. So an interview whose lines were merged by speaker displayed its opening minutes spread across the whole timeline. Existing projects correct themselves the next time they open; nothing needs re-running.
- **Playback highlighting went out early on the last paragraph of a transcript.** It now lasts until the recording's final words.
- **A project whose folder permission was lost had no way back.** The Mac app showed "Can't be read", and Show Log failed with a permission error. The project now offers Locate…, which opens on the folder, so one click grants access again.
- **At rest, the book shelf on the Welcome screen showed every cover through the one in front.**

**0.31.3** — _26 Sep 2026_

Dropping the same folder in twice no longer imports everything twice.

**Improved**

- **The Signals lens scrolls like every other lens, and the heatmap stays put.** It was the one lens with its own scroll model — the cards scrolled inside a fixed frame while the page did not — and that is where the phantom scrollbar, the heading cut off under the toolbar and the clipped card shadows all came from. The page scrolls now, and the heatmap pane is pinned to the bottom of the window as you go. Jumping to a card or tabbing to one lands it above the pane rather than behind it.
- **The heatmap bar reads as part of the panel it sits on.** It runs edge to edge, wears the left panel's tint, keeps its height whether open or closed, and its title and icon line up with their neighbours.

**Fixed**

- **Dropping a folder you had already dropped made a second copy of every recording in it.** The importer asked only whether something already sat at that name, so re-dropping — the natural way to ask for another analysis — put `clip 2.mov` beside `clip.mov`. That cost more than disk. The transcription cache keys on the file's path, so every renamed copy was a guaranteed miss and paid to transcribe the same interview again: one re-dropped folder came to $0.62 against $0.09 for the same work done once. Worse, the two copies became two participants saying identical things, which then clustered together — so the report read as corroboration rather than as a mistake. A file you already hold is now recognised by its contents and skipped, and identity is proven rather than guessed, because getting it wrong the other way would silently drop a real interview.
- **Folders in the sidebar would not stay collapsed.** Closing one held only until the next selection change or progress tick, which re-expanded it. Collapsed folders now stay shut, and survive a relaunch.
- **The projects column stayed away when the window grew, and came back after you had hidden it.** Both were the same root: the column's width was being measured at moments when it had none — as the window mounted, and mid-animation — so a column you had taken never fitted again, and one you had deliberately hidden was handed back on the next resize.
- **A browser set to Norwegian got an English report.** The codes a system reports for Norwegian — `no`, and Nynorsk's `nn` — were not recognised as the Bokmål we ship, so the interface fell through to English. Both resolve to Bokmål now, as the Mac app already did. `bristlenose --lang no` works too.
- **Show Diagnostics did not hide the build-info capsule in development builds.** One switch now hides the machinery, which is what you want before a screenshot or a demo.

**0.31.2** — _23 Sep 2026_

A second control in the Quotes lens announced itself in English to screen readers.

- **The tag badge that assigns a tag to your selected quotes spoke English to screen readers.** It announced "Assign Frustration to selected quotes" in every language, because the label was assembled in English in the code rather than translated. Sighted users saw the tag's own name, which was already correct; anyone using VoiceOver or a screen reader in one of the other twenty languages heard the surrounding sentence in English. Same defect as the tag group's show and hide button in 0.31.1, one control along.

**0.31.1** — _23 Sep 2026_

A control in the Quotes lens announced itself in English to screen readers, whatever language the report was in.

- **The show/hide button on a tag group spoke English to screen readers.** It announced "Show Frustration" or "Hide Onboarding" in every language, because the label was assembled in English in the code rather than translated. The identical control in the panel beside it had been translated since the day it shipped, so the two disagreed. Sighted users saw nothing wrong; anyone using VoiceOver or a screen reader in one of the other twenty languages heard English. It now uses the same words as the rest of the lens.

**0.31.0** — _22 Sep 2026_

Bristlenose hears the language a recording was spoken in, writes its headings back in yours, and the Mac app speaks it everywhere — and the framework codebooks now carry only their authors' words.

**New**

- **Recordings are transcribed in the language they were spoken.** Every run told Whisper the audio was English — the command line by default, and the Mac app whatever language its interface happened to use — so a non-English interview was decoded under an English assumption and came out wrong. The spoken language is now detected per file: a study whose sessions are in different languages transcribes each in its own, with nothing to configure, and the transcript files record what was detected. Pin it when you already know the corpus: `--whisper-language es` on `run` and `transcribe`, or `BRISTLENOSE_WHISPER_LANGUAGE`.
- **Section and theme names come back in your language.** A Spanish researcher got English headings over Spanish quotes. The stages that write section names, theme titles and descriptions now write them in the interface language — `--lang es`, or the language the Mac app is running in — and the quotes stay verbatim, product names and on-screen labels as the participants said them. English sends the model nothing extra, so an English run's prompts are unchanged. Signal findings, AutoCode reasons and chat answers are not steered and usually arrive in English.
- **The framework codebooks say what their authors said.** Every codebook shipped in February had exactly four tags per group, because the extraction padded each group where the book ran out. Norman, Garrett, Nielsen, Yablonski and Morville have been re-read against the source: tags the author never wrote are gone (Morville's twenty-eight are fifteen), tags in the author's own words are back, groups take the author's titles, and the useful tags that were ours moved to the Bristlenose UXR Codebook. A codebook you already have installed migrates in place: a renamed tag keeps the quotes it was on, a retired tag stays if any quote still carries it, and new tags arrive empty. Each codebook has a decision register, and a change to one now needs a witness quote.
- **The Mac menu bar follows your language.** File, Edit, View, Window and Help — and every standard item inside them — were English in every language, because the app declared no localisations; Project, Codes, Quotes and Video were English literals. All follow the language now. Changing it offers to relaunch, in Apple's own words; the menus pick up the change at the next launch, and an analysis that is running is never interrupted. A fresh install starts in your Mac's language instead of English, and a language chosen in System Settings ▸ Apps ▸ Bristlenose is respected.
- **The Welcome screen is translated.** Its prose, tips and study tools, and the example quotes, tags, theme words and filenames inside the illustrations, authored per language rather than translated — the disfluency demo strikes out "o sea" in Spanish and 「えっと、あの」 in Japanese. The shelf shows the local edition of a book where one exists: Norman in ten languages, Braun & Clarke in Polish.
- **Focus mode reaches the Signals lens.** `z` on Signals, and View ▸ Focus Mode is live there. Before, switching lenses while in focus mode left Signals half-dimmed by rules meant for quote cards.
- **The Miro board follows your language.** Frame titles, counts, "Other" and the clip marker were English on every board, and a one-quote board was titled "1 quotes". Long Japanese quotes now wrap instead of running over neighbouring stickies.
- **The pre-run cost estimate prints.** "Estimated LLM cost: ~$X for N sessions" had been silent since April: the shipped baseline was empty and a model generation it had not seen found nothing. Backtested against twelve real runs at a median of 0.95× the actual spend.

**Improved**

- **The Mac app speaks your language in the places that were still English.** Failure rows and sign-in failures in the Teams, Meet and Zoom import window; the "Sign in with Microsoft / Google / Zoom" buttons, in the vendors' own words; Today, Yesterday and attendee counts in the recordings list; the run-failure line under a project and the diagnostic popover's category; the explanations under the status dot in Settings ▸ AI; the screen that says why Bristlenose couldn't start; the player window's title; drag-and-drop refusals; the Miro sheet's own failure sentences. Settings tab titles follow a language change and no longer jump you back to General.
- **The Language picker tells the truth.** It showed English while the app ran in German on a fresh install, and choosing the row it showed would have switched you to English; the report opened in English inside a French app.
- **The edit pencil on a section or theme heading is visible.** It was drawn in the disabled-icon colour and hovering the heading did nothing. It now appears when you hover the heading, brightens under the pointer, reveals for keyboard focus, stays visible on touch — and announces itself to screen readers in your language.
- **Codebook author cards fit their column**, and Morville's says he devised the UX Honeycomb the codebook is built on.
- **Signals navigation rows indent under their location**, so a heading and its entries no longer start at the same edge.
- **Better words in more places.** Traditional Chinese uses Apple's ⋯; Norwegian says Finn… and markering; the French export column says favori; dialog titles use each language's own quotation marks; the catch-all theme uses each platform's own "Uncategorised".

**Fixed**

- **The AI-tags stat card put you back on the dashboard you clicked from** — a 0.30.0 regression from the Signals rename. It opens the Signals lens again.
- **Twenty languages still described "the analysis page"** one sentence below the Signals labels 0.30.0 renamed, the help text had lost its definition of a signal, and the intensity tooltip said 0–3 when the scale is 1–3.
- **Hiding a selection sent a write for every pair of quotes** — twenty-five for five, all racing — and starring a selection or Restore all sent one per quote. Each is one write now, and hiding a selection that spans several groups collapses every group.
- **Star and Unstar disagreed.** With a mixed selection the Quotes menu said Star while `s` unstarred everything. One rule everywhere: unstar only when every selected quote is already starred.
- **The Codebooks uninstall sheet had an English title and buttons** inside a translated warning, since 0.29.0.
- **Miro export failures were English prose** in the report's panel; they are sentences in your language now, and a half-built board still gives you its link.
- **"1 hidden quote" sat in English above a translated "Show:"**, in every language.
- **The Welcome illustrations didn't change language until dark mode was toggled**, and one depicted a 0–3 scale and "2 quote(s)" — two things the product doesn't do.

**Removed**

- **The pattern chip from the illustrated signal card.** The Signals lens dropped it in 0.30.0; the illustration was teaching a control that no longer exists.

**0.30.0** — _21 Sep 2026_

The Analysis lens is called Signals, its cards were redrawn, and PII redaction finally works end to end on the command line.

**New**

- **The Analysis lens is now Signals.** The name was doing two jobs and neither well: analysis is what *you* do — reading, tagging, revising — and what the pipeline does when you press Analyse. Signals is the thing Bristlenose computes: the concentration scores, the cards, the lens that shows them. Calling one lens "Analysis" implied the other four weren't, which is untrue — tagging in Quotes is analysis. Everything that names the lens now says Signals, in all 21 languages. Old links keep working: `/report/analysis/` redirects, and bookmarks and already-exported reports still open.
- **Signal cards, redrawn.** A card now names its location once, in the heading, and opens with four quotes rather than one. The chip says what the feeling *is* — "Frustration", "Mixed sentiments" — instead of naming the framework it came from, which told you nothing. Findings arrive a chunk at a time over cards already on screen, so a long elaboration no longer holds the whole list back.
- **PII redaction works end to end — on the command line.** `--redact-pii` bundles the detection engine, fetches its model on first use with the terminal to itself, and the report records when the transcripts were redacted. A phone number read aloud is now caught; it wasn't before. Turning redaction off clears the redacted copy rather than leaving a stale one for three different readers to disagree over. **This is the CLI only** — the Mac app can't reach it yet.
- **A focus cursor in Codebooks, and a Codes menu to drive it.** Move between codes from the keyboard, with one focus ring at a time and an edit field that looks like one.
- **⌘F searches.** It was bound to nothing on lenses that have a search box, and dims on the ones that don't.
- **One keychain.** A provider key saved in the app is now seen by the CLI, and the other way round. They had been writing same-named items to different keychains and neither read the other's.

**Improved**

- **The Signals lens has one navigation, one card list, and one order.** The left panel and the main content used to disagree about what came first.
- **The report keeps its reading measure when the window narrows.** Panels give way in a deliberate order — the Mac sidebar first — instead of squeezing the text.
- **Provider defaults are current again.** ChatGPT moves off a May-2024 model, Gemini's two picker models are retired for new users (the default was already broken), and Claude's default returns to the model that passes our tool schema on real transcripts. ChatGPT requests now use structured outputs, so the response shape is guaranteed rather than asked for.
- **Doctor stops blaming your Python version for a corrupt model pack.**
- **Better words in more places.** The codebook is `kod kitabı` in Turkish — the term MAXQDA's own Turkish UI uses — and stops reading as a person rather than a book in Russian and Ukrainian. The Codes menu no longer says "Install Codebook" in twenty languages that never wanted it.
- **Settings ▸ AI sizes to the provider you picked** instead of holding a fixed height for the tallest one.

**Fixed**

- **Quote deep links could point at the wrong moment.** Some models write timecodes with minutes where hours belong, so a quote at 3:36 was recorded as 3 hours 36 minutes and its link landed nowhere. Every quote's timecode is now range-checked against its own session. If you have deep links that went somewhere odd, re-analysing will correct them.
- **A lens could go dead after switching projects.** Clicking Quotes or Signals did nothing at all until the window was reopened.
- **A session that failed was never retried.** It was recorded as complete, so the next run skipped it — your interview stayed missing from the report with nothing saying why. It is now retried.
- **An AutoCode run that coded nothing claimed it had.** A job whose every batch failed is now a failed job, and one that produced no codes no longer stamps the watermark that stops it running again.
- **A redacted project leaked participant names into the export.**
- **The Agree. figure claimed more voices than there were people.**
- **The window menu collapsed a moment after opening**, because every update rewrote the whole menu bar.
- **The app waited on a webfont it then threw away**, delaying the first window.
- **A drag-in copy that failed now says why**, whichever gesture started it.
- **The Signals lens had a second scrollbar** — the page was scrolling its own padding.

**Removed**

- **The temperature slider in Settings ▸ AI.** Several models reject the parameter outright; the rest are tuned for this work already.
- **Six Codes menu commands that never had a target**, and Find Next / Find Previous — a filter has no "next".

**0.29.1** — _31 Aug 2026_

Switching one codebook off switched the others back on — and three more surfaces reported more than they had actually done.

- **Only one codebook could be off at a time.** Switching a second one off silently switched the first back on, and its tags reappeared across the report without anything saying so. Every switch now records the state of every codebook rather than just the one you touched. If a codebook came back on without you asking, switch it off again — it will stay off this time.
- **Switching a codebook off could start AutoCode on a different one.** A codebook coming back on is treated as a deliberate re-enable, so it catches up on any sessions imported while it was off. Because the switch was turning others back on by accident, that catch-up could run on a codebook you had deliberately switched off — spending on codes you never asked for. Worth a look at your review queue if you were toggling codebooks on 0.29.0.
- **An AutoCode run that coded only some of your quotes said it had finished.** When a batch fails the run carries on with the rest, which is right — but the activity chip had no way to say so, so a run that tagged 58 of 72 arrived as an unqualified success with the shortfall dropped. It now says the run was partial, and keeps the link through to review what it did produce. The correct behaviour had been written and tested some time ago; it had landed in a component nothing renders.
- **Reopening a review drew the confidence thresholds in the wrong place.** The thresholds you set when applying a codebook are stored with the run, but the review panel reset to its own defaults every time it opened — so a report reopened after an apply showed lines at 0.30 and 0.70 whatever you had actually chosen, a picture of a run that never happened. It now opens where you left it.
- **On macOS 26 the toolbar pills sat inside a second capsule.** The system now wraps every toolbar item in its own glass capsule, and the status pills already drew one, so they arrived nested inside a brighter chrome that was never designed. All three now keep their own capsule and opt out of the system's.
- **"Switch provider" opened whichever settings pane you last used.** It asked for the settings window without naming a destination. It now opens the AI provider pane — the one that answers the question.

**0.29.0** — _31 Aug 2026_

The codebook is a lens you navigate rather than a page you scroll — and three things the app was telling you were not true.

- **Codebooks got a navigator.** Every codebook in the project is a row in the left panel, grouped into your own tags, what ships by default, and the frameworks you installed — each with its author under the title. Click a row to open it; switch one off and its tags stay on your quotes but stop appearing anywhere until you switch it back. The old single page, with every codebook stacked on it, is gone.
- **The library is somewhere you can go back from.** **Browse Codebooks** opens a catalogue of what's available, and it is now a real place — the back button in the app toolbar and in your browser both return you to the codebook you came from, and the page can be linked to and reloaded. Each card says how big the codebook is, and for one you have installed, how far it has actually reached: **28 tags · applied to 2 quotes in Ikea**.
- **Uninstalling told you the opposite of what it does.** The confirmation said "AutoCode results are preserved — reinstall any time". They are not: uninstalling deletes the AutoCode run and every proposal under it, including ones you had already reviewed. It said so in 21 languages, on the one screen you read before losing the work. The dialog now says what is true, and the new lens measures the cost before you confirm.
- **`pipx install bristlenose` produced a tool that could not run.** `run`, `analyze` and `serve` all need the `serve` extra and the instructions did not ask for it, so following the README gave you a Bristlenose that could only transcribe. Homebrew, Snap and Fedora were unaffected; pipx and uv are the routes we recommend first, and the only ones on ARM Linux. Now `pipx install 'bristlenose[serve]'`.
- **The privacy page said there is no Bristlenose server.** There is one: the feedback form posts a rating and your message to it. Nothing else — no project, no transcript, nothing identifying you or your machine — and only when you submit the form. But the page listing where data goes had left it out, and denied it above the list. Corrected, along with two other claims that were wrong: exports do **not** anonymise by default, and speaker identification sends a sample of the transcript to your AI provider *before* PII redaction runs.
- **A long description now reads at two levels.** The first sentence carries the claim in full-strength text; the rest continues in a lighter tone, so you can take the point at a glance without anything being hidden or truncated. Applied to codebook descriptions and to the finding on every signal card.

**0.28.0** — _27 Aug 2026_

Exported reports work outside the Mac app again — and are less than half the size. A project Bristlenose can't reach now tells you why, in your language.

- **Export HTML worked in the Mac app and nowhere else.** The single-file export build is produced by the frontend build and gitignored, and it was never declared for packaging — so it shipped in **no wheel and no sdist ever published**. The **Export HTML** button returned a 500 on every pip, pipx, Homebrew and Snap install. Only the Mac app worked, because it lists that directory separately. Verified against the published 0.27.0 wheel: 226 files of the report app, none of the export one. A test now fails the build if any generated asset directory goes undeclared, so this cannot recur silently.
- **Exported reports are less than half the size.** Every export carried all 22 languages — 1,802 KB of a 3.38 MB file you hand to a client, including Czech strings for a `--whisper-model` flag. A report now embeds the language you chose, plus its fallback chain, so a missing key can never print a key name at a stakeholder. **3.38 MB → 1.55 MB.**
- **A project Bristlenose can't reach now says why — in your language, and where you'll see it.** A volume that has gone, a project it can't read, a folder taking too long: five states that rendered as bare English sentences on the row, with no glyph and nothing to click, in every language. They now carry a glyph, a popover with the full explanation, and translations in 21 languages.
- **`man bristlenose` no longer outlives the package.** Snap and Homebrew installs ship their own man page, but Bristlenose was also dropping a copy into your home directory. `man` reads that first, so it shadowed the packaged one — and because no package owned it, uninstalling left `man bristlenose` still working, showing whatever version last wrote it.
- **Snap users with a broken PII component are no longer told to run `pipx`.** The suggested fix was `pipx inject` into a strictly-confined install, which cannot work. presidio ships inside the snap, so the answer is `snap refresh`.
- **Fedora: two commands, and `dnf upgrade` keeps you current.** `sudo dnf copr enable cassiocassio/bristlenose`, then `sudo dnf install bristlenose`. The package bundles Python and every dependency; FFmpeg comes from Fedora's own repositories, whose free build handles everything Teams, Zoom and Meet produce. x86_64, Fedora 43. The install was proven on a clean box before these instructions went live.
- **Agent access keeps explaining itself.** A fresh install this week would have picked up a newer MCP library that swallows Bristlenose's refusal messages — an agent asking about a closed study would see `Error executing tool` instead of being told the project is out of scope and to reopen it. Pinned until refusals survive the newer library.

**0.27.0** — _22 Aug 2026_

As many studies open as you want, each in its own window; recordings pulled straight from Teams and Meet; and a folder that no longer fails as a whole because one file in it is broken.

- **Open as many studies as you want, each in its own window — and as many windows on one study as you need.** The Mac app showed one study at a time; opening another replaced it. Now every window holds its own. **File ▸ New Window** (⌥⌘N) opens another view of the study you're on, each window on its own lens — quotes here, the transcript they came from there, the analysis beside it. **Open in New Window** on a project brings up a different study alongside; on a folder, **Open in New Windows** opens every study in it at once. Windows keep their own lens, sidebar and scroll position, their titles say which study each is showing and number them when two would read alike, and menu commands act on the window in front. Bristlenose now opens on the Welcome screen rather than reopening whatever you had last.

- **Bring in recordings from Teams and Google Meet without downloading them by hand.** Connect a work account and **File ▸ Import** lists the meetings you recorded: filter by title or by who was there, choose how far back to look, tick what you want. Bristlenose fetches the recordings, puts them in a project and starts the analysis. It recognises recordings you already have on disk so you don't fetch twice, handles a meeting that holds two recordings, and says plainly when one has expired or your account can't reach it. Connect and disconnect in **Settings ▸ Accounts**. Zoom isn't offered yet.

- **If you have run a Teams or Meet Word transcript through Bristlenose, re-run that study.** Both were read wrong and neither said so — the report looked fine. Teams packs a whole speaking turn into one paragraph, so every turn arrived anonymous and stamped 0:00. Meet was worse: its download flattens Gemini's summary of the meeting into the same file as the transcript, and Bristlenose read all of it as speech — so an AI paraphrase *about* your participant could be extracted and shown in your report as their verbatim quote, with their email address alongside it. Both now yield genuine speech only, with real timecodes and real speaker names. A `.docx` too damaged to read is refused by name instead of half-parsed.

- **One unreadable file no longer costs you the whole batch.** A single empty or truncated recording used to stop the run and take every healthy session with it — a 42-session folder could return nothing because of one bad `.mp4`. The bad file is now refused by name, with the reason, and everything else is analysed. Files Bristlenose declines are listed rather than silently skipped, and it reads **27 file types**, up from 16.

- **You can see which studies an agent can read.** **Settings ▸ MCP Agents** lists every project: whether an agent can reach it now or only once you open it, how many sessions that exposes, and when it was last asked. Access survives quitting — it used to look permanent and quietly wasn't. The sidebar antenna lights while an agent is actually reading. With several studies open, an agent can reach all of them rather than only the front one.

- **Re-analyse works, and tells you what it would cost.** It had been permanently dimmed. It now runs, and asks first — naming the edited quotes, tags, starred quotes, renamed speakers and named themes a fresh analysis would discard. Recordings you drop into a project folder in Finder are noticed and offered. A failed run no longer leaves debris that blocks the retry.

- **Controls that edit a report were live inside reports you had exported.** An exported HTML report is meant to be a read-only leave-behind, and five things in it weren't: the accept and deny buttons on suggested tags, the hidden-quote counter and its **Unhide all**, the codebook's **+ tag** row, and **Browse codebooks**. The accept/deny pair had been clickable in exports since a redesign renamed the control out from under the rule that hid it, so anyone you sent a report to could change how it was coded. All five are gated again, and a test now fails the build if a rule ever stops matching the thing it hides.

- **A failed analysis stays failed until you deal with it.** A run that failed yesterday came back blank this morning — the row lost its error, and **Show Diagnostics** disappeared with it, because the menu item is only offered on a row in a failure state. The cause had been recorded correctly the whole time; every surface that would have shown it to you switched off at once, leaving the reason readable only by going into a hidden folder in Finder. The failure and its explanation now survive a relaunch.

- **`bristlenose transcribe` says which recordings were silent.** It reported 42 of 57 sessions transcribed and listed nothing as failed — an honest count with no account of the missing fifteen. A recording with no speech in it is now named, with its filename and the reason, because a count tells you something is missing and only the name tells you who.

- **A session's length reads as a length, and a timecode is the same everywhere.** The Sessions grid showed `26:31` in a row that also carries a date and a start time, where it reads as a time of day; it now says `26m`, which is what the window title, the session switcher and the exported data already said. Separately, a quote's timecode said `05:30` on the card and `5:30` in the CSV of that same quote — they now agree, in the report and in every export of it.

- **The panel that explains a missing participant now speaks your language.** It translated its heading, its counts and its buttons, and then gave the one sentence that says *why* a recording was skipped in English — to every language but English. All eight reasons are now translated across all 21 languages. Diagnostics you copy for a bug report stay in English on purpose, so they read the same to whoever you send them to.

- **Català — Bristlenose now speaks Catalan.** Catalan (`ca`) joins the desktop app, web report, and CLI (Settings → Language) — twenty-two locales in all. It ships as one locale, not a Valencian pair. It's a machine-seeded **community preview**, offered so native speakers can refine it on [Weblate](https://hosted.weblate.org/projects/bristlenose/); the seed is _fill-empty-only_, so contributed translations always win the next sync. Ships on PyPI and in the desktop app.

- **Switching session on the Mac is a titlebar popover, not a sidebar.** **Switch Session** (⌘⌥L on the Sessions lens) replaces both a permanent left column and a dropdown you had to be reading a transcript to find. It's a real source list, so type-select, arrow keys and VoiceOver are the system's: type a few letters of a participant's name to jump to them. Each row carries the badge, the session number and *all* the names on a multi-participant session, with duration and date beneath. The lens also returns you to the view you left rather than the index. In a browser nothing changes.

- **Fewer words in the report's sidebars.** The Codebook lens is **Codebooks** — it holds several, and always did. "Your tags" is **Manual tags**, "Built-in" is **Default**, "Frameworks" is **Library**. The Quotes and Codebooks sidebars drop title bars that were an empty padded box in the Mac app, and the left navigation narrows to suit contents rather than tags. English only this release; the other locales keep their current words until the English settles.

- **Two privacy settings that were never implemented now stop the run instead of warning past it.** Setting `BRISTLENOSE_PII_LLM_PASS` or `BRISTLENOSE_PII_CUSTOM_NAMES` used to warn and carry on — so you could list the handful of names you most wanted gone and get a run reporting that redaction succeeded with those exact names still in the transcripts. Either now stops the run and says which setting it can't honour, counting the names it was given without ever printing them.


**0.25.3** — _10 Aug 2026_

- **Cancelling a run no longer records it as a failure.** Press Ctrl-C in the first moments of a run — while it was still starting up — and Bristlenose wrote nothing at all about the cancellation. The run was left looking abandoned, and the next run you started reported the previous one as having stopped unexpectedly. You stopped it on purpose; you were told it had failed. The window was a narrow one, so this was rare on an idle machine and more likely on a busy one, but nothing afterwards could tell a deliberate cancel from a crash. A cancellation is now always recorded as a cancellation — including when the signal lands in the very first milliseconds, while the run's own opening log entry is still being flushed to disk, which is the case 0.25.2 left open. The same change means a run that cannot write its own bookkeeping — a full disk, say — is recorded as a failure with a reason attached, rather than leaving no trace.

**0.25.2** — _9 Aug 2026_

_Reached TestFlight and the direct-download `.dmg` only — never published to PyPI, Homebrew or Snap. Its fix was incomplete, leaving the narrowest case still misreported. Superseded by 0.25.3; use that one._

- **Cancelling a run no longer records it as a failure.** Press Ctrl-C in the first moments of a run — while it was still starting up — and Bristlenose wrote nothing at all about the cancellation. The run was left looking abandoned, and the next run you started reported the previous one as having stopped unexpectedly.

**0.25.1** — _7 Aug 2026_

- **Speaker names in a shared offline report are links again.** In an exported report — the self-contained file you hand to a stakeholder — clicking a speaker badge on a quote did nothing useful: it navigated the browser off the file to a path that doesn't exist. Every other link in the export had been converted to work without a server; the quote cards' jump-to-this-moment-in-the-transcript link was the one that hadn't, so it broke silently, with no error message to explain it. It now lands on the transcript at the right timecode, the same as everywhere else. **If you are on 0.25.0, upgrade** — it carries the bug.

**0.25.0** — _6 Aug 2026_

_Superseded within the hour by 0.25.1, which fixes broken speaker links in exported reports. Use 0.25.1; `pip install bristlenose` gives you it by default._

The Sessions lens learns to shrink, the arrow keys learn the layout, and two build gates that couldn't fail learn to.

- **The Sessions lens no longer runs off the side of the window.** It was a plain HTML table with no responsive strategy at all: every column was fixed or nowrap except Start, so the whole of the shrink pressure landed on that one column and the user-journey path collapsed to one word per line — while the table itself still overflowed the page by 195px at a narrow window. It's now a grid that degrades on purpose. **Column order never changes** — ID, thumbnail, speakers, start + journey, sentiment, duration, file, at every width — so nothing rearranges under you as the window narrows; what changes is only what's given up, and in a deliberate order. Speakers and start + journey shrink together as a proportional pair, duration and filename join them when it gets tighter, and below that a ladder sheds detail in order of what you can most afford to lose: **surnames first** (falling back to the short name), then the **user journey** — a whole column of content, spent before identity legibility is — then names entirely, leaving the speaker badges. The badge is the anchor and never moves to its own line, and names are never broken mid-word. It's pure CSS using container queries, with no width measurement in JavaScript, so it behaves identically in the app, in a browser, and in an exported report opened offline from a file.
- **Every lens now has a proper title.** Sessions had no heading at all, and Codebook's had lost its horizontal rule in all three of its render states — it inherited the right type from being an `h1`, which is exactly what made the missing rule easy to miss. Sessions gains a titled zone matching Quotes and Analysis (with the "Moderated by" line moving underneath it as the intro), and Codebook gets its rule back. Underneath, the heading became a real component rather than a class you had to remember to type, so a zone title can no longer be produced without its rule.
- **The arrow keys move by what you can see; `j`/`k` move by reading order.** The quote grid became multi-column, and then masonry — but the arrow keys were still walking the underlying list one item at a time. So on any window wide enough for two columns, pressing **down** moved the cursor to the card on the **right**, and left/right did nothing at all. There are now two coherent models instead of one broken one: `j`/`k` are a list cursor — "the next quote in reading order", whatever the layout, and what **Quotes ▸ Next/Previous Quote** drives — and the arrows are geometric, measured off what the browser actually laid out, so lanes, headings between groups and filtered-out cards all resolve without special cases. (In a single column the two coincide, which is why the split went unnoticed for so long.) Three related fixes came with it: `⇧`+arrow could select an off-screen quote and then feed it to bulk star, hide and copy; left/right also drove the sidebar resize handle, so one press resized the sidebar *and* moved the cursor *and* scrolled the page; and the quote shortcuts stayed live after you left the lens, where the arrows ate page scroll on Transcripts and Analysis and `s`/`h` starred or hid whichever quote you'd navigated away from. Arrows now only take the keypress when the cursor actually moves, so ordinary page scrolling survives at the edges of the grid and on an empty search.
- **The Analysis heatmap was drawing light-mode colours on a dark background.** It chose its colour band by reading an attribute that the report only sets when you pick a theme in its own web settings panel — which never happens in the Mac app, where appearance is owned natively and inherited by the report. So the check was permanently false there, and the heatmap rendered its pale band against a dark page every time. It now follows the system appearance, still letting an explicit in-report choice override it, and repaints live when you switch rather than waiting for a reload.
- **Focus Mode, tuned against real studies.** Five changes from living with 0.24.0's reading mode in all four palette-and-appearance combinations. The **starred left edge now dissolves** with everything else: exempting it looked right ("your own mark stays lit") and was wrong, because starred is a *plural* state — a mark that reads well on one card reads as noise on twenty. The star glyph and the heavier text carry it instead. The **keyboard cursor gets a thin accent ring in dark mode**, because Focus drops the focused card to the page colour, which in dark is the same colour every dissolved neighbour already is — an invisible cursor in a field of identical cards. **Section and theme descriptions now fade with their titles** instead of staying lit alone. Printing from Focus Mode no longer strips the starred edge. And the descriptions now honour reduced motion, which they'd been quietly ignoring.
- **The starred edge stops shouting in dark mode.** Outside Focus Mode too: the marker sat at more than triple the contrast of its light-mode counterpart, and at that strength a hairline in a multi-column gutter reads as a *divider between two quotes* rather than the left bracket of one — so on a wide screen you couldn't tell which card it marked. It's now tuned to match the light-mode reading. The star glyph is untouched; taming the shared colour instead would have flattened the starred-versus-unstarred difference almost to nothing.
- **Switching Light/Dark on the Mac no longer reloads your report.** The appearance preference was restarting the whole background process, which meant the report cold-mounted on every switch — losing your route, your scroll position, your open panels and your focus, plus a couple of seconds of boot — all to serve byte-identical HTML. Appearance never travelled that way in the first place; it reaches the report through the platform. Typography and Language keep the restart, because those genuinely do change what the process is told.
- **Two half-finished affordances are switched off rather than shipped half-done.** The moderator question pill and the expand-quote-context chevrons both work, but neither is discoverable enough to put in front of the alpha cohort: the pill's trigger is an unmarked hover zone over the start of a quote, and context expansion is one-way with nothing marking a card as expanded, so there's no reason to look for an undo. Both are behind feature flags — the code still builds and is still tested, so revisiting them starts from working code and a written rationale rather than a dig through history.
- **Under the hood: two build gates that could not fail, and a near-miss.** A complete, correctly-named, correctly-sized 0.24.0 disk image sat finished-looking for 14 hours while macOS would have refused to open it — it was never notarised, and two of the four final checks meant to catch exactly that were written in a shell form that silently cannot fail. The check is now one shared gate that mounts the image and interrogates the app *inside* it (the build tool takes a copy, so a notarisation ticket applied to the original never reaches the one you'd actually download), and it runs as a precondition of publishing rather than as a step someone can skip on the one night it matters. Publishing itself became atomic — the previous approach wrote straight over the live file, so for the quarter-hour a transfer took, every visitor got a truncated download with nothing reporting an error. Separately, the freshness check that decides whether the Mac app needs rebuilding was ignoring five of the directories it ships, including the entire theme and every LLM prompt — so editing a stylesheet or a prompt and rebuilding produced a confident "matches source" tick and an app still running the old copy. That's worse than having no check, since it turns an open question into false reassurance; all five are covered now, and a test reads the packaging manifest itself and proves each entry moves the fingerprint.
- **Fixes:** a focused card that was also selected drew a doubled line down its left edge; the keyboard cursor's ring kept glowing while the app was in the background; and the build report's live progress display smeared copies of itself down the screen on any terminal narrower than 92 columns.

**0.24.0** — _3 Aug 2026_

A reading mode for the report, and a pass over the Mac app's chrome.

- **Focus Mode — read the quotes, not the furniture.** Press `z` on the Quotes lens (⌘⌥F, or **View ▸ Focus Mode**, in the Mac app) and everything that isn't the signal recedes: tag chips, sentiment badges, timecodes, context lines and the card box itself fade to a faint outline, while the quote text, the speaker code and the stars stay lit. Nothing moves — the toggle touches colour and opacity only, never layout, so the quote under your eye stays exactly where it was and a card may simply show a blank band where its chips were. Anything you touch comes back to full strength: hover a receded chip, tab to it, or open a tag input with `t`, and it lights up. Stars are never dimmed, because reading undistracted is what you do *in order to* star. It's a mode, not a theme — Focus works in light, dark and Edo alike, fades over about a third of a second, and snaps instantly if you've asked the system to reduce motion.
- **Hiding the sidebars now remembers what you had open.** `\` on the Quotes lens (⌘⌥\ in the Mac app's View menu) used to toggle both sidebars independently, so "contents open, tags closed, hide, show" handed back a tag sidebar you never had. It now stashes the arrangement and restores it.
- **The View menu says what each row will actually do.** All four panel rows are toggles, and every one of them read "Show …" whether or not its panel was already open. They now swap to "Hide …" off the panel's real state — including the three web panels, which the native menu can't see inside the web view to read, so the report now mirrors their state to the menu.
- **The Mac app's appearance preference reaches every surface.** Choosing Light or Dark in Settings themed the main windows but left roughly a dozen surfaces following System Settings instead: the export save panel, both Locate panels, the download-failure alert, the sidebar context menus, the icon-picker popover, the video pop-out, and the five auxiliary windows including System Health. All of them now inherit the app's own preference. Invisible whenever your app preference agreed with the system, which is how it went unnoticed.
- **The Pipeline view knows all four local models.** It described "local" as a single model while the Mac app's picker had offered four since April; it now lists Llama 3.2 3B and the three Gemma 4 sizes with the memory each needs, and says "needs more memory" — in the same words as the Ollama setup sheet — for one your machine can't hold.
- **Homebrew 6.0 had quietly stopped upgrading Bristlenose.** Homebrew 6.0 requires non-official taps to be trusted, and the check reads the command you typed: `brew install cassiocassio/bristlenose/bristlenose` still works, but a bare `brew upgrade` never names the tap, drops Bristlenose from the plan and warns rather than fails — so an existing install goes stale with nothing you'd notice. `bristlenose doctor` now checks for this and prints the one-off `brew trust` line that fixes it. Two related fixes: the upgrade command Bristlenose prints is now fully qualified (the short form is refused for exactly the people being told to run it), and installing ffmpeg or Ollama through Bristlenose no longer asks you to confirm the same decision twice.
- **Connecting an agent is disclosed as what it is.** The AI disclosure covered one recipient — the cloud provider you pick for the analysis — and 0.23.0 added a second it never mentioned: connect an MCP agent and what it reads goes to *that* agent's vendor, a different company under different terms, at the moment you ask rather than when the analysis runs. That is now a disclosed recipient in its own right, and the sheet no longer contradicts itself — it had promised participant names "always stay on your device" six lines below saying an agent's provider receives them, which with Anonymise off is exactly what travels. Everyone who accepted the previous version sees the new one once.
- **Settings ▸ MCP Agents works before a project is running.** With nothing serving, the three copyable tabs collapsed to "Start the project before connecting an agent" — an empty state shown to precisely the person doing first-time setup. They now show the shape of the configuration with placeholder address and token, greyed and not copyable, so you can see what you'll be pasting before you have it. The Mac install tab also pre-announces the one-time macOS prompt asking whether Claude may access data from other apps, quoting the system dialog's own wording in every language, so it reads as expected rather than as a fault.
- **Fixes:** a tag you typed by hand appeared on the quote but not in the tag sidebar until you reloaded; wrapped journey chains in the sessions grid drew a stray few pixels of indent at the start of each line; and the welcome screen no longer offers a Redact PII tool the Mac app can't yet run.

**0.23.0** — _1 Aug 2026_

Ask your study questions from your own AI agent — and pick which provider runs the analysis.

- **Ask your study from Claude, Claude Code, ChatGPT or Codex.** Bristlenose now speaks the Model Context Protocol: a read-only endpoint that hands a connected agent four tools — a project overview, quote search, signals, and your codebook — so you can ask questions about a study in your agent's own window, on your own subscription. What comes back is the *curated* corpus, not the raw pipeline: quotes you hid are excluded, quotes you edited come back edited, and every quote cites a quote id you can look up in the report. Nothing is written, no filesystem path is ever accepted, and Bristlenose makes no LLM calls of its own to answer. On the command line it's an optional extra (`pip install 'bristlenose[mcp]'`); the macOS app ships it built in.
- **On the Mac, connecting Claude Desktop is one button — no address, no token, no JSON.** Install the Bristlenose extension from **Settings ▸ MCP Agents** and confirm in Claude Desktop; that's the whole setup. It finds the running project by itself through a short-lived handshake file, so nothing needs re-copying when Bristlenose restarts on a new port — the thing that made the old hand-pasted config a weekly chore. (Hand-editing another app's settings file turned out to be worse than tedious: a stray comma makes Claude Desktop rewrite its own config and drop what it can't parse.) Claude Code, ChatGPT & Codex and a Generic MCP tab keep the copyable form for every other client.
- **Exposure is a deliberate act, per project — and you can see it at a glance.** No agent can read a project until you choose **Turn On Agent Access** (right-click the project, or the Project menu). A project you never turn on is unreachable, whatever agents you have installed. While access is on, an antenna appears on the project's row in the sidebar — solid while that project is open and reachable now, pale while it isn't — so "what is exposed?" is answered by looking, not by opening a settings pane. Turning access off deletes the handshake on the spot, which is what revocation means here.
- **One switch decides whether agents see participant names.** **Anonymise** sits at the top of Settings ▸ MCP Agents, off by default, using the same word and the same meaning as the export surfaces: switch it on and agents see speaker codes (p1, m1) only. Quotes always cite codes regardless; names, when allowed, appear only in the overview's speaker map.
- **Choose which AI provider runs your analysis — and stop re-typing keys.** New `bristlenose use <provider>` switches the current provider (`claude`, `chatgpt`, `gemini`, `azure`, `local`); `bristlenose configure <provider>` now makes that provider current as well as storing its key, and says so. There is no vendor default any more: Bristlenose uses your explicit `--llm` if given, then the provider you last chose, then your sole configured key — and if you have several keys but have never chosen, it asks you to pick once instead of quietly guessing. Keys stay stored when you switch, so changing provider never means re-entering one.
- **A native Health window on macOS** shows dependency and configuration checks — the `doctor` report, without the terminal.
- **Rename a project in the sidebar, four ways.** Inline rename now works from the context menu, the Project menu, Return, and a slow second click on the name — the Photos gesture — rather than only from a menu.
- **Transcripts name the speaker in the sticky header** while keeping code-only badges on the lines below, so you can see who is talking while scrolling without turning the page into a wall of names.
- **The welcome screen is illustrated.** The study-tools carousel gains a Connect-an-AI-agent cell alongside the rest, so the feature is discoverable before you go looking for it — the extension solves installing an agent, not finding out you can.
- **Diagnostics stopped disappearing on re-runs.** A run in which any stage was entirely cache-hits wrote a `null` duration that the desktop refused to decode — and losing that one field silently discarded the *whole* pipeline summary, so re-running a finished project produced no diagnostic at all. The contract now carries the null case in a fixture, and a parity test keeps the Python and Swift ends honest.
- **Clip export handles cloud-stored sources and cancellation.** Cutting clips is the go-back-to-an-old-study operation, which is exactly when a provider has evicted your recordings; the source is now fetched before cutting rather than downloading inside the clip's own time budget and reporting a failure. Cancel a clip export and it records itself as cancelled, keeping the clips already written instead of overwriting the run as "completed".
- **Failed files can name themselves.** A recording that fails while being probed or ingested never reaches a session, so nothing downstream could say which file it was — and the sidebar counted it twice, once as waiting and once as failed. Failures now carry the filename.
- **Dragging in the sidebar handles a mixed selection.** Projects and folders travel as one kind-tagged payload, so a multi-select drag of both works and a folder drag can no longer be mistaken for a file drag from Finder.
- **Fixes:** interviews stored in iCloud or Dropbox are now fetched before Bristlenose probes them, instead of failing inside the probe's own timeout; the Whisper preflight no longer prints a download banner for a model that's already cached; a cloud-fetch timeout no longer says "1 minutes"; the codebook lens packs its cards without ragged gaps; the Settings window follows an appearance change while it's open instead of only at next open; "Show Transcripts in Finder" reaches the Project menu and always lands somewhere real; and the report's centre column no longer draws a stray focus ring.
- **Security note.** The credential an agent holds is scoped: it opens the four read-only tools and nothing else — it cannot reach the rest of the local API (participant names, curation writes). On the Mac it now lives in a runtime handshake file inside Bristlenose's own container rather than travelling into another vendor's config file or across your pasteboard. [SECURITY.md](SECURITY.md) item 7 has the full account of what an agent can read and how to revoke it.

**0.22.0** — _26 Jul 2026_

A large release — codebooks you can switch on and off, a self-contained offline report you can share as a single file, a more reliable AutoCode, and a pass over the whole report's visual system.

- **Codebooks you can install, switch off, and trust to stay put.** The Codebook Library is now a two-way surface — every tile has one button, **Install** or **Uninstall** (retiring the old _Add_ / _Remove_), so an installed codebook is no longer look-only. Each codebook carries an **on/off switch** with a matching **status dot** in the sidebar (blue on, grey off); switch one off and its section folds to a one-line summary, its badges hide across the whole report, and it drops out of the tag sidebar and tag suggestions — but its tags stay on your quotes and every result is kept, so flipping it back on restores everything. "Off means off" is functional, not cosmetic. Uninstalling now also forgets a codebook's on/off state, so reinstalling one you'd switched off returns it **on**, not greyed-out. And the codebooks you have switched on now **code newly-added sessions too** — add interviews to a finished project and the existing codebooks catch up on the new quotes, rather than leaving them blank. Ships on PyPI and in the desktop app.
- **Share an offline report — a self-contained leave-behind that opens from a file.** Export a report as a single HTML file that runs the full app straight from `file://` with the data inlined — no server, no internet, nothing to host. It opens **read-only** (the editing controls that can't persist offline are removed, not left as dead buttons), bakes in the researcher's UI language so it reads the same offline, and its coverage is guaranteed by construction: a build-time gate derived from the live API surface fails the build if any report data would be missing from the embed, so the download can't silently ship half a report. **Security:** the embedded data is now escaped against `<` / `>` / `&`, closing a stored-XSS hole where a literal `</script>` in transcript text, a participant name, or a tag could break out of the data block in a shared file. Ships on PyPI and in the desktop app.
- **AutoCode stopped losing proposals — and a stalled run is recoverable.** A run could cheerfully report _"AutoCoded in 50s ✓ — 0 of 0 proposals"_ while the model had actually returned dozens (seen against the IKEA data with Bristlenose UXR and JJG's Elements: 38 proposals returned, every tag stuck at zero). The culprit was a **cosmetic progress counter sinking the real payload**: after each batch the job wrote its running quote-count with a read-then-write transaction, which SQLite refuses outright (_"database is locked"_) the moment any other write is in flight, and because that write wasn't isolated its failure dragged the batch's proposals down with it. The progress write is now a bare, write-only update that waits its turn for the lock, and can no longer discard proposals if it does fail. Alongside it: re-apply proposals are de-duplicated per quote (no more perpetual silent re-fails), a cancelled or failed AutoCode job can be **re-run** instead of being stuck, start-time errors surface instead of looking like nothing happened, and orphaned jobs are reconciled on server startup. Ships on PyPI and in the desktop app.
- **The report reads calmer.** A pass over the whole report's visual system: one true heading per content zone instead of competing title weights, section dividers unified to a single full-width rule (the heavier capped rule is gone), balanced gutters on panes with no minimap, and a consistent corner-radius tier so nested cards stop inverting. The Analysis lens scrolls to the bottom properly again, transcript margin annotations use a cleaner grid layout with first-occurrence de-duplication, and the quotes-page minimap keeps its true proportion when quotes reflow into columns — it reads the live grid's column count rather than a second set of breakpoints. Ships on PyPI and in the desktop app.
- **CLI: configure a provider without a system keyring, using the env vars the SDKs already expect.** `configure` now persists keys to a config file when no OS keyring is available (headless boxes, some Linux setups), and Bristlenose reads the SDK-native, unprefixed environment variables for Gemini and Azure — so a key that already works with the official SDK works here without renaming. The no-provider guidance was reworked to point straight at `configure` (in the house cyan accent) and to name the right app store per platform. Ships on PyPI.
- **The Snap is now strictly confined.** Converted from classic to **strict confinement** (home, network, network-bind, and removable-media interfaces), with `libblas3` / `liblapack3` staged so `ffprobe` finds its shared libraries and the frontend built under Node 22 (core24's Node 18 can't build Vite 8). Published to the edge channel. Snap users only.
- **Fixes worth calling out.** Media probing now **fails loud** when `ffprobe` / `ffmpeg` errors, instead of reporting an empty success and producing a silently blank transcript. The Sessions sidebar detects moderators correctly again (the stored role is `researcher`, never `moderator`, so the old check silently never fired). And the thin-theme bucket is now plain _"Uncategorised"_. Ships on PyPI and in the desktop app.
- **Desktop (reaches the alpha cohort with the next bundled build).** The welcome screen is now **illustrated** — looping science-cell animations for the sentiment, quote, and theme concepts, a study-tools carousel introducing AutoCode and Codebooks one at a time, and a self-scaling book-shelf motif. The **Settings window is resizable** with animated per-tab height, a uniform width, and in-cell help subtitles. The menus fill in: dynamic _Hide/Show Projects_, _Help ▸ Welcome to Bristlenose_, a Sessions-contents toolbar toggle, a preference-gated Diagnostics menu, and debug windows no longer double into the Window menu. Distribution: a signed **direct-download `.dmg`** (developer-id archive→export flow) now works for the expiring alpha alongside the App Store / TestFlight path.

**0.21.0** — _16 Jul 2026_

- **"Out of credit" now says out of credit — not "rate limit reached."** When a provider refused a call because the account had run dry, Bristlenose told you to wait. Credit exhaustion and rate-limiting both landed in the same `QUOTA` category, which rendered as _"rate limit reached"_ — advice that will never come true for a bankrupt key. Billing exhaustion is now its own **non-retryable** category (waiting doesn't fix it; topping up does), across every surface that reports a failed LLM call: the run-failure cause, the CLI banner, the desktop failed-run row, a new out-of-credit toolbar pill, and the Settings provider check. Detection is a single shared classifier with provider-scoped rules, and the wire is stranger than the documentation admits — **Anthropic serves out-of-credit as an HTTP 400** carrying _"credit balance is too low"_, not the documented 402, and **OpenAI shares 429** between billing (`insufficient_quota`) and genuine rate-limiting — so the classifier reads the provider's own error code first, its message second, and the HTTP status **last**. Where a provider genuinely doesn't distinguish the two — Azure has no credit concept, and Gemini folds billing into `RESOURCE_EXHAUSTED` — Bristlenose keeps calling it rate-limiting rather than inventing a top-up story the wire never told it. 33 tests built from real provider payloads. Ships on PyPI and in the desktop app.
- **Feedback from every state — and it can't be redirected off-host.** The native feedback sheet arrived in 0.20.0 for the screen that needed it most (the status page after a failed run); it now opens from **every** state of the macOS app, so _Help ▸ Send Feedback_ never dead-ends on whatever happens to be on screen. Alongside it, a hardening that applies to every feedback submission on every surface: the endpoint allow-list only ever checked the *first* request, and the HTTP client follows redirects by default — so a redirect from the feedback host would have quietly re-sent your typed message somewhere else. Redirects off `bristlenose.app` are now refused outright. Ships on PyPI and in the desktop app.
- **The dashboard fills the window, and features up to five quotes.** The Project tab still carried a 52rem reading-width cap that every other tab had shed, so on a wide display it sat in a column with the right-hand side empty. It now fills the width like the rest of the app — full-span panes stretch, and the two navigation lists share a flush row instead of trailing a ragged right edge. Featured quotes go from three to **five**: three across on a laptop, five across from 1400px up, with the visible count always matching the column count so a row never ends half-empty. Ships on PyPI and in the desktop app.
- **Desktop: the welcome screen teaches you the app, a little at a time.** The screen you land on with no project open was a single static panel — drop a folder, and that was the whole of it. It's now a **grid that drip-feeds the things worth knowing**: features you haven't found yet, the research science the analysis rests on, practical tips, help getting an LLM set up, and pointers into the documentation. The drip is the point. A wall of onboarding gets read once and dismissed, whereas the empty window is a surface you pass back through every time you finish a project — so it can keep handing you one more thing you didn't know, rather than one thing you've already ignored. Desktop-only (Swift); reaches the alpha cohort with the next bundled-sidecar build.
- **Desktop: the shoal moves like a murmuration — and your analysis is what disturbs it.** The word-flock that drifts during a run moved as though floating in treacle. The cause was a force clamp crushing every steering impulse — including the startle and attract behaviours — down to an idle nudge. Retuned, it banks and overshoots around a wandering attractor the way a real murmuration does. And it's no longer decorative motion running beside the work: **the analysis drives it**. Each batch of arriving words, themes and sentiments fires a matching disturbance through the flock — a cohort joining, a startle wave, a predator swoop — so the shoal reacts as your interviews are actually processed. Desktop-only (macOS); reaches the alpha cohort with the next bundled-sidecar build.
- **Developer: a read-only database browser, in the direct-download beta only.** The SQLAdmin browser now mounts at `/admin` for debugging a cohort user's data on a call — read-only over transcripts and PII, bound to localhost, and **fail-closed by construction**: it's gated on a compile-time flag set only by the direct-notarised beta build, so the App Store and TestFlight builds both hide it. A receipt check was considered and rejected — App Review runs under the StoreKit sandbox, so a receipt can't tell a reviewer from a tester, and the Debug menu would have been exposed to review. Read-only also disables table export, which was an unauthenticated full-table dump. Developer-facing.
- **Under the hood: the macOS app is sandboxed, hardened and accepted by App Store Connect.** The Release build now runs under the App Sandbox with the Hardened Runtime, pinned to arm64 (the Python sidecar is arm64-only), with every nested binary signed the way App Store Connect requires — three separate upload rejections' worth of signing corrections. Not user-visible; it's what makes the macOS app distributable at all.

**0.20.0** — _11 Jul 2026_

- **Your curation now survives re-analysis — and what's new is flagged.** Re-run the pipeline on a project and the work you'd already put in stays put. Any quote you've **starred, edited, or tagged** is frozen with a durable identity and its exact wording, held exempt from the stale-cleanup that clears regenerated data — so a fresh analysis can never quietly drop a quote you'd marked, even one the model wouldn't surface again. Report **sections keep their identity by _membership_, not by their heading text**, so a re-run that renames or re-clusters a theme no longer scrambles the headings you'd edited; a theme name you've anchored to a starred quote persists across runs. And genuinely new material earns a dismissible green **New** badge on its section, so a returning researcher's eye goes straight to what changed without disturbing the sections they'd already curated. This is the persistence foundation for incremental analysis (adding sessions to a finished project); the manual **re-assignment** write path — moving a quote between sections by hand — lands alongside it. Ships on PyPI and in the desktop app.
- **Desktop: the "Interviews" folder proxy reveals your source folder in Finder.** The folder chip above the sessions table is now a real proxy for the interviews folder: click it in the macOS app and Finder opens with that folder selected — the shortest path from "the report on screen" back to "the recordings on disk," the exact move a researcher reaches for the moment they've recorded another session. It follows the same _Show in Finder_ idiom as the project sidebar, and it's sandbox-safe by construction — the reveal is handed to Finder out-of-process, so it needs no extra file-access permission, no security-scoped bookmark, nothing new in the entitlements. In the browser (`bristlenose serve`), where there's no native bridge to hand off to, the chip keeps its copy-the-path-to-clipboard behaviour, and both the action and its tooltip follow the surface ("Show in Finder" in the app, "Copy folder path" in the browser). The desktop reveal reaches the alpha cohort with the next bundled-sidecar build; the groundwork behind it — a new `reveal-in-finder` WKWebView bridge action and a _Show in Finder_ label seeded across every language Bristlenose speaks — ships on PyPI.
- **Feedback that survives a failed run — and a native way to give it.** When a run is cancelled or fails, the report gives way to a status page, and its "Send feedback" link used to lead nowhere: it pointed straight at the submission endpoint, so a browser GET got back a bare "Method not allowed." Now feedback works from that screen in every context. The **macOS app opens a native feedback sheet** — five-point rating, a message, Cancel/Send, no web chrome — while the browser (`bristlenose serve`) opens an inline form on the status page itself. Both send the same anonymous `{rating, message}`, and both now report "sent" **only when the server actually confirms receipt** — a captive-portal or corporate-proxy page that answers `200 OK` with its own HTML can no longer swallow your feedback and call it delivered. If a send can't be confirmed, your message is preserved and copied to the clipboard rather than lost. The reliability fix reaches the in-report feedback form too. Browser form + reliability ship on PyPI; the native sheet reaches the alpha cohort with the next bundled build.
- **Help opens the live docs — so you can read it _beside_ the report, not over it.** The in-app Help overlay is retired in favour of the online documentation, which supersedes it and stays current. **Help → Bristlenose Help** and **Keyboard Shortcuts** now open the matching page at `bristlenose.app/docs` in your browser, and **Acknowledgements** opens the project's open-source credits. A panel that covers the very thing you need help with is the wrong shape for a tool you're actively using — the docs open in their own window (and the `?` key reuses a single tab), so the analysis stays in view while you read. Ships on PyPI and in the desktop app.
- **Jump from a session's journey straight to the moment it happened.** The screen path under each row in the Sessions view — _Beds Category → Bed Product Detail → Checkout_ — is now a row of live links. Click any step and Bristlenose opens that participant's transcript scrolled to the exact moment they first reached that screen, the segment briefly highlighted — the same deep-link the in-transcript journey navigation already performs, now reachable straight from the overview. The anchor is the participant's earliest quote on that screen, resolved to the nearest transcript segment so a step always lands somewhere real even when its first quote falls mid-segment. Plain click navigates in place; ⌘-click opens the moment in a new tab. Ships on PyPI and in the desktop app.
- **Sessions view: play from the thumbnail, and a steadier Start column.** The session thumbnail is now a play control — click it to open the pop-out video player at the start of that session, matching the filename link beside it (with the filename as a hover tooltip). And the Start column, which stacks the date above a sometimes-long screen path, gains a minimum width so it no longer collapses to one word per line as the window narrows — the path stays readable instead of shattering into a tall column. A fuller responsive pass on this dense, frequently-seen screen is tracked as follow-up. Ships on PyPI and in the desktop app.
- **A calmer failure, and a proper landmark.** A route-level error boundary now catches a crashing report view and shows a calm fallback instead of a blank page, and the routed content sits inside a `<main>` landmark so a screen reader can jump straight to it. Ships on PyPI.
- **Drop loose interview files, not just folders — Bristlenose builds the project for you.** The desktop app could only analyse a *folder* of interviews; dragging in individual files created a project that dead-ended on "this was created from individual files, so it can't be analysed." Now dropping loose files — onto the sidebar, or onto a new project you've just created — opens a native **Create Project Folder** sheet: name it, pick a location, and Bristlenose creates the folder, copies your interviews into it, and analyses them. Your originals stay where they are. It's a proper window-modal sheet — it slides from the title bar and follows the app's light or dark theme — not a stray floating panel, and single- vs multi-file drops read correctly. Desktop-only (Swift) — reaches the alpha cohort with the next bundled-sidecar build; the supporting interface strings ship on PyPI.
- **Add more interviews to a project you've already analysed.** Drop new files onto an analysed project — or use **File → Add Files…** (⇧⌘A) — and Bristlenose folds them in with an incremental re-run instead of starting over: a calm "Adding N interviews…" confirmation up front, then the normal stage ladder. Your starred, tagged, and edited quotes carry across (the curation persistence above). Desktop-only (Swift); the per-session caching that makes the re-run incremental ships on PyPI.
- **Recover a stopped or half-finished analysis.** Stop a run partway — or have one fail — and the interviews are already copied into the project's folder, so the project isn't a dead-end. Right-click it and choose **Analyse** to resume from the partial output already on disk. Files belong to the project: a stopped run is always visible and always retryable. Desktop-only (Swift).
- **Two fixes worth calling out.** Claude API-key validation now probes `/v1/models` rather than calling a since-retired model, so a valid key no longer reads as invalid. And a project — with its cached inputs — is now identified by its _resolved_ filesystem path rather than the spelling you happened to type, so the same folder reached two ways is one project, not two. Ships on PyPI.
- **Fix: your project's real name in the report, not "Untitled."** A project analysed the moment it was added could have its report and dashboard title freeze at the placeholder "Untitled" — the database row behind the report is built in the split second _before_ the pipeline writes the project's name to disk, and every later re-analysis healed that row's file paths but never its name. The importer now heals a stuck "Untitled" back to the pipeline's own project name (and its URL slug) on the next re-import, scoped tightly to the placeholder so it can never overwrite a name you've set on purpose. The desktop sidebar always read the right name — this repairs the report and dashboard heading, which reads from the database. Ships on PyPI and in the desktop app.
- **Shoal, sized to your screen — a fuller flock, held smooth.** The in-run word-flock now scales to the window it's drifting in: sparse in a laptop pane, a proper shoal across a 24″ external display, and it re-flocks live when you drag the window between screens — where before it drew the same fixed handful everywhere. It's capped at a steady 50 fps so the motion stays fluid instead of straining for a 120 Hz ProMotion refresh it can't hold (30 fps read janky; 50 was the sweet spot). The fix came from a better diagnosis: the flock's real cost is the main-thread flocking *simulation* — an O(n²) neighbour search every frame — not the GPU render we'd assumed, so 150 words only turned smooth once the frame rate was capped and the count was tied to the canvas area (clamped 24–200, still thickening early → late as analysis proceeds). Desktop-only (macOS); reaches the alpha cohort with the next bundled-sidecar build.
- **Acceptance testing you can't fake-pass — a conformance tier that runs the real thing.** Bristlenose's two automated test layers are hermetic by design: they mock every provider and binary so they stay fast and free, which leaves one whole class of bug invisible — the cross-seam kind where a setting reaches the wrong environment variable and every run silently falls back to a too-small model, green all the way down. This lands the first rung of a third tier that runs the _real_ pipeline against _real_ providers and asserts only **shape**, never content. Every input format we advertise now has a sub-second coverage check — all sixteen classify correctly, and thirteen media containers are produced and decoded through real ffmpeg, retiring the idea of a full transcription run per format. A provider matrix drives `bristlenose run` across Claude, ChatGPT, Azure, Gemini, and local Ollama and refuses to call a run successful unless it _actually produced work_: a completed-not-failed terminus, non-empty quote clusters, and the re-identification keys (`llm-calls.jsonl`, `pii_summary.txt`) provably absent from every export. The guards are themselves tested — an empty run, a missing artifact, a participant name that leaked past the anonymisation boundary all turn the check red — so a green run _means_ something. The tier was designed against an adversarial multi-agent review and then fired for real, which immediately earned its keep: it caught a fail-closed bug in the harness itself (a missing artifact crashed the check instead of failing it — fixed), and proved the discipline end to end — an empty run fails, a model that timed out fails, a genuine Claude run passes. Developer-facing; no user-visible surface — everything lives in `docs/testing/` and `scripts/acceptance/`.

**0.19.0** — _4 Jul 2026_

- **Nine new locales — Bristlenose now speaks nineteen languages.** Dutch (`nl`), Finnish (`fi`), Polish (`pl`), Russian (`ru`), Ukrainian (`uk`), Danish (`da`), Swedish (`sv`), Norwegian Bokmål (`nb`), and Turkish (`tr`) join the roster across the desktop app, web report, and CLI (Settings → Language) — nineteen locales in total. Each is a machine-seeded **community preview**, complete against all nine namespaces (`common, cli, desktop, doctor, enums, pipeline, preflight, server, settings`), offered so native speakers can refine on [Weblate](https://hosted.weblate.org/projects/bristlenose/); the seed is _fill-empty-only_, so contributed translations always win the next sync. Slavic + Turkic plural rules are respected — Polish uses the 1 / few / many / other split, Russian and Ukrainian retain `{{count}}` in the `_one` form because the shape recurs at 21/31/etc., Turkish is binary — and Scandinavian is one/other. Turkish register is formal (_siz_-and-imperative, `Vazgeç` for Cancel rather than the abrupt `İptal`). New tooling to catch regressions: a placeholder-union check across every locale, a `_one` completeness gate for East-Slavic, and a pytest guard that classifies unseeded strings against the English source. Norwegian ships as Bokmål only — the `no → nb` fallback path is an open follow-up. Ships on PyPI and in the desktop app.
- **Shoal — a live word-flock while your interviews are being analysed.** During a run, a SpriteKit flock of the words the pipeline is *currently* extracting drifts across the detail pane in the desktop app. A Python-side sampler filters transcript words for stopwords and appends them to a `shoal-feed.jsonl` sidecar as they surface; the Swift `ShoalFeed` polls the sidecar every ~1.5 s and injects the batch into the scene, colour-graded by sentiment. The flock respects **Reduce Motion** system-wide and a dedicated **Show animation while analysing** toggle in Appearance → Animation; if the feed is stale by the halfway mark it logs once and falls back to a canned word pool so you never see an empty pane. A 0–600-word density rig with FPS + node counters ships behind the DEBUG build for anyone tuning the flock. Desktop-only feature; the sampler + i18n strings ship on PyPI so the SPA carries the plumbing.
- **Palette picker + Edo, end to end.** Settings → Display picks between **Default** (re-grounded on Apple's system values — system-blue accent `#007AFF` / `#0A84FF`, the neutral-grey AppKit selection capsule `#EFEFEF` / `#2B2B2B`, 6 px corners, native inactive-window dimming — so the seam with the desktop app's native chrome disappears) and **Edo** (a Prussian-blue accent sampled from the pigment's *brilliant* undertone rather than the dull masstone of aged prints, paper-white paper, passport-navy ink, with a warmer paper in dark mode so it stays legible). The picker is now a native macOS pulldown in Settings — no restart needed, the SwiftUI `.tint()` propagates through Settings/Debug scenes, and a WKWebView bridge repaints the report the instant you switch. Your choice persists locally and paints *before* first render (no flash of the wrong palette), validated against an explicit `default` / `edo` allowlist rather than a permissive regex. A `--palette` CLI flag (renamed from the ad-hoc env var) lets `bristlenose serve --palette edo` boot straight into your preference. Translated across all nineteen locales; the picker's labels are provisional in the newer languages, pending native review. Ships on PyPI and in the desktop app.
- **Terminology fixes across four locales.** A glossary-consistency pass corrected drift the multi-locale audit surfaced: Japanese (Quotes 引用 → 発言, the glossary-forbidden form), Korean (a 왜곡 mis-spelling, Accept 승인 over 수락, Signals 시그널 with 을/은 particle fixes), German (Sessions Sitzung → Interview, undo Rückgängig → Widerrufen, three informal _du_ → formal _Sie_), and Spanish (dropping the over-literal _Tubería_ for _Pipeline_). Values only, no key changes — verified against `check-locales.py` and the locale-key parity tests. Ships on PyPI.
- **Supply-chain hardening — CycloneDX SBOMs, signed and attached.** Every release now attaches runtime-scoped CycloneDX SBOMs (Python + frontend) as durable GitHub Release assets, and binds the Python SBOM to the built wheel + sdist with a Sigstore attestation via `pypi-publish`'s attestation flow. A new gitleaks history-scan CI job checks the full git history on every push and PR (with three historical false positives allowlisted); a tracked-vs-gitignore guard catches the class of `.env`-shaped files being accidentally tracked while gitignored. Trusted Publishing (the OpenSSF baseline) was already in place — SBOM + attest close the falsifiable-property loop on "what shipped from what source." Ships in the release pipeline, no user-facing surface.
- **Lighter first paint.** The report's tab views (Dashboard, Quotes, Transcript, Codebook, Analysis) now code-split into lazy per-tab chunks instead of being simultaneously dynamically *and* statically imported — a contradiction that quietly folded them all back into the main bundle. The landing bundle drops to ~213 kB (size-limit ceiling ratcheted 230 → 220 kB), and switching tabs fetches its island on demand behind a shared loading boundary. Invisible on a fast machine; a real saving on a cold load. Ships on PyPI.
- **Smaller polish.** `AccentColor.colorset` is finally filled (it had been silently empty, letting the system pick a nearby colour). AutoCode is hidden on auto-applied Sentiment framework so it stops offering itself when there's nothing to auto-code. A `no-fake-success` pipeline acceptance test is added (slow, skip-in-CI) — the class of "green suite while the pipeline silently returned nothing" is now caught end-to-end. Translucent detail-column chrome merged from spike after full-screen inset handling was resolved. Ships on PyPI and in the desktop app.

**0.17.0** — _30 Jun 2026_

- **Five new locales — Portuguese, Italian, and Traditional Chinese.** Bristlenose now speaks Brazilian and European Portuguese (`pt-BR` / `pt-PT`), Italian (`it`), and Traditional Chinese for Taiwan and Hong Kong (`zh-Hant` / `zh-Hant-HK`) across the desktop app, web report, and CLI (Settings → Language) — twelve locales in all. Portuguese and Chinese each ship as a deliberate *pair* rather than one catch-all, because a single code reads as foreign to one side: Brazilian and European Portuguese diverge on everyday words (arquivo / ficheiro, usuário / utilizador), register (você), and the progressive (Brazilian _salvando_ vs. European _a guardar_); and Bristlenose's Chinese is Traditional only — a Taiwan-leaning `zh-Hant` plus a distinct Hong Kong variant — not Simplified. As with Czech, each locale is a complete machine-seeded baseline (all 8 namespaces + `preflight`) offered as a **community preview** for native speakers to refine on [Weblate](https://hosted.weblate.org/projects/bristlenose/); the seed is _fill-empty-only_, so a contributed translation is never overwritten and Weblate's own work always wins on the next sync. Apple-HIG action verbs and the Bristlenose research-method glossary (Codebook, Quotes, Sessions, Themes…) seeded per language so reviewers start from an agreed taxonomy. New guard tests pin locale-key parity, `{{placeholder}}` consistency, and plural-form completeness across every locale.

**0.16.1** — _28 Jun 2026_

- **Send to Miro becomes a native macOS sheet, and shows exactly where the board will land.** On the desktop app the export moves out of the in-report panel into a native sheet with its own Miro connection — paste your access token once and it's held in the macOS Keychain — and the sheet now names the connected account, workspace, and organisation plus the destination team, so you can confirm where the board lands before you push. The web report's Miro panel gains the same connected-account / workspace identity, so `bristlenose serve` users see it too. Desktop sheet reaches the alpha cohort with the next bundled-sidecar build; the Miro-panel changes ship on PyPI.
- **Desktop Quotes toolbar: a native search field and a starred-only toggle.** The Quotes view's search box and "starred only" filter are now native macOS toolbar controls rather than web widgets, debounced through a single-writer bridge to the report, and the redundant tag dropdown is removed. Desktop-only — reaches the alpha cohort with the next bundled-sidecar build.
- **Fix: the native Miro export no longer 401s after you switch projects.** The serve process now resets its bearer auth token on a cold start, so the desktop app's token stays in sync with the freshly-booted server and the Send-to-Miro request authenticates instead of failing 401. The `serve` change ships on PyPI; the symptom was desktop-only.
- **Desktop embedded report suppresses the web sidebar rails and close-×.** In the macOS app the native sidebar owns project navigation, so the SPA's own sidebar rails and close button are hidden when the report runs embedded in the app. Theme/CSS change ships on PyPI but only takes effect in the embedded (desktop) context.
- **Contributor tooling: a dev-only Run Inspector and a native Debug menu.** `bristlenose serve --dev` gains a Run Inspector (`/api/dev/run`, dev-gated + auth-enforced) that visualises instrumentation the pipeline already captures — `llm-calls.jsonl`, `pipeline-events.jsonl`, timing — without adding new logging paths, and the macOS DEBUG build gains a Debug menu (Run Inspector at ⌃⌘R, a live diagnostic-fixtures submenu, reveal-`.bristlenose` / open-log / copy-build-provenance). A build-time sidecar-staleness gate fails the desktop build loudly when the bundled sidecar is stale versus the Python source. Developer-facing; no change to the report or exports.

**0.16.0** — _27 Jun 2026_

- **Send to Miro — push your analysed quotes onto a Miro board.** A new export builds a first-draft research wall: a fresh board each time, one column per section then per theme (the report's left-to-right order), pink section headers and yellow quote stickies stacked session-then-time, coloured by sentiment. Connect once by pasting a Miro access token (guided setup at `bristlenose.app/docs/send-to-miro.html`), name the board, choose colour-by, optionally link quotes to hosted clips, and preview the whole board credential-free before pushing. Participant display names never leave your machine — stickies carry speaker codes (p1, p2) only, and hidden quotes are excluded. Experimental, phase 1 (paste-token; one-click browser connect comes later). In the SPA export menu now; the macOS native menu arrives with the next bundled build. `SECURITY.md` documents Miro as an opt-in sub-processor.
- **Desktop: native SF Pro typography, with a Typography setting.** The macOS app now renders on a calibrated SF Pro type scale aligned to Apple's text styles, and a new Typography setting switches between SF Pro and Inter. The type scale ships in the theme (so the in-app report matches, via WKWebView type-parity fixes); the setting is the macOS app.

**0.15.19** — _24 Jun 2026_

- **Desktop: the macOS project sidebar is rebuilt on native AppKit.** The sidebar moved off SwiftUI's `List` — which had hit selection and tap dead-ends on macOS 26 — onto a native `NSOutlineView`, bringing the row affordances the old list couldn't carry: two-line project rows (icon · name · session count, with a live status subtitle beneath), native activity and copy rings with hover-to-cancel on the row itself, status glyphs for can't-find and iCloud-evicted projects, the failure → diagnostic popover opened from the row, project and folder context menus, and Finder folder-of-videos drops wired into the sidebar. The migration came with its own test seams — pure `ProjectCellSpec`, `OutlineNode`, and `DropRouting` helpers with unit coverage — so the AppKit layer isn't an untested blind spot.
- **Desktop: the five report views become a lens rail, with a native window title + session subtitle.** Project · Sessions · Quotes · Codebook · Analysis move out of the toolbar picker into a lens rail at the top of the sidebar; switching lens updates a native window title and a lens-contextual session subtitle (the old toolbar title pill is gone). Desktop-only (Swift) — both land in the alpha cohort with the next bundled-sidecar build; the PyPI / Homebrew / Snap package gains the supporting interface strings across all seven languages.

**0.15.18** — _21 Jun 2026_

- **Desktop: copy progress moved onto the project row, and switching back to a recent project is now near-instant.** Two macOS-app refinements. (1) When you drag files into a project, the copy progress — a determinate ring, a "Copying · N%" subtitle, and hover-to-cancel — now rides that project's sidebar row instead of a separate toolbar pill, so per-project status lives where the project lives (the standalone copy pill is gone). (2) Switching *back* to the immediately-previous project re-points to its still-running ("parked") server instead of tearing it down and restarting, so the boot wait disappears for the common back-and-forth switch — the "warm-sidecar pool." Localised across all seven languages.

**0.15.17** — _18 Jun 2026_

- **Default Claude runs no longer break when Anthropic retires a model.** Bristlenose's built-in Claude default pointed at `claude-sonnet-4-20250514`, which Anthropic retired on 15 June — so from that day a plain `bristlenose run` on the Claude provider (with no `--model` set) failed at the topic-segmentation stage with a `404 model_not_found`. The defaults now track current aliases (`claude-sonnet-4-6`, plus `claude-opus-4-8` where Opus is offered), updated across every place a model id is named — provider registry, config, and pricing — so the next retirement is a one-line change rather than a forty-file hunt. Pin a model with `--model` or `BRISTLENOSE_LLM_MODEL` and nothing changes. Ships on PyPI.
- **Quote cards pack tighter on the report, where the browser supports it.** The quote grid now uses CSS Grid Lanes masonry (Safari 26.4+ and the desktop app's WebKit) so variable-height cards settle into the shortest column instead of leaving ragged gaps — a progressive enhancement that falls back cleanly to the existing grid everywhere else, with cards kept in reading order for keyboard and screen-reader users.
- **The desktop sidebar shows real progress on cached and first-time runs, instead of a frozen "Analysing…".** The per-stage verb ladder (Identifying speakers → … → Rendering) was driven only by the timing estimator, so two run types never advanced it — cache-verified / transcript-only runs (the only per-stage signal lived inside the "stage actually ran" branch), and every new user's first few runs (the estimator stays silent until it has ~4 runs of history, so day-one runs showed nothing). An estimator-independent signal now fires at the entry of each analysis stage, carrying the last-known ETA so warm runs are unchanged (the determinate ring doesn't regress) and cached / cold-start runs advance the verb with the ETA simply absent. Python-only — ships on PyPI and in the desktop sidecar; no change to the report or exports.

**0.15.16** — _10 Jun 2026_

- **Quote extraction no longer fails on dense interviews when the model's output limit is small.** Some models cap how much they can write in a single response — ChatGPT's gpt-4o stops at 16,384 tokens, small local models far less — and on a long, quote-rich transcript the quote-extraction stage could hit that ceiling mid-response: the JSON came back truncated and the whole run failed. We were seeing this on roughly one run in three against dense ChatGPT transcripts (caught 8 Jun during a real interview-analysis session). Bristlenose now detects the truncation, splits the transcript at a natural topic boundary — falling back to even halves when no confident boundary exists — extracts quotes from each piece separately, and merges the results, recursing up to three levels deep (≤8 chunks) for the densest material. Duplicate quotes that straddle a split are removed by matching their verbatim text, and the split is all-or-nothing per interview so a partial failure never leaves a half-analysed session. A new typed `TruncatedResponseError` carries an `OUTPUT_TRUNCATED` cause through the pipeline (mirrored on the desktop side so a truncation reads honestly, not as a generic failure), and the cloud LLM client now retries up to six times on rate-limit bursts. The split-point picker was deliberately kept to two tiers — a high-confidence topic boundary from the segmentation stage, then mechanical halves — after a third "moderator question pivot" tier was dropped: topic shifts in skilled interviews emerge from semantic drift over many turns, not from lexical signposts. Verified on Claude with a forced low cap (A/B), on a full real-interview pipeline, and against the live gpt-4o SDK; every quote still appears in exactly one report section. Ships on PyPI — benefits every provider with a tight output cap.

**0.15.15** — _9 Jun 2026_

- **Čeština — Bristlenose now speaks Czech, and it's the first language our users asked for.** Czech (`cs`) joins Spanish, Japanese, French, German, and Korean across the desktop app, web report, and settings (Settings → Language → Čeština). The backstory is the nice part: a volunteer signed up to translate Bristlenose into Czech on [Weblate](https://hosted.weblate.org/projects/bristlenose/) _before_ we'd shipped the language — the first organic demand signal for a locale we've had. So rather than hand them a blank slate, we machine-seeded a complete Czech baseline (all 8 namespaces + `preflight`, ~950 strings) with proper Czech four-form CLDR plurals — `one` / `few` / `many` / `other` — for them to react to and refine. The seed is _fill-empty-only_ (it never overwrites a contributed string), and Weblate's own translations win on the next sync, so the human work is always safe. Apple-HIG Czech glossary terms added (Uložit, Zrušit, Zavřít, Kopírovat…).
- **A coverage sweep so more of the app actually translates — settings, codebook, transcripts, accessibility labels, the desktop pipeline — plus the first Czech-correct plurals.** Adding Czech surfaced how many strings still hard-coded English and so reached _none_ of the seven languages; this pass wired them through i18n. Newly translatable: the Settings → Config reference (72 category + setting labels), the Codebook's "New group" / "New code" defaults, the transcript page's loading / error / empty states, ~30 React `aria-label`s and tooltips across eleven components (so screen-reader users on a non-English locale hear their own language), and the desktop pipeline-activity status — "Analysing…", "Stage 3", "Queued", "Elapsed", the popover header and the Stop button. The headline fix is grammatical: every desktop count-bearing string used a hardcoded `count == 1 ? one : other` selector that could never reach Czech's `few` form (counts 2–4), so a new `I18n.pluralCategory()` computes the real CLDR category and both the diagnostic-overflow text _and_ the three sidebar chrome counts (interview / unanalysed / missing) now render the right form — proven by Swift tests against the live Czech locale. New guard tests pin locale-key parity, `{{placeholder}}` consistency, the CLI↔GUI string mirror, and four-form completeness. Translation _quality_ for the machine-seeded strings remains the native-speaker community's to refine on Weblate; this pass is the mechanical groundwork. Mostly internal / UX — no API change.

**0.15.14** — _7 Jun 2026_

- **Desktop runs the LLM provider you actually chose — and an LLM failure no longer reads as "Transcription failed".** Four diagnosed defects in the desktop provider-resolution path, closed together. (1) The AI-consent resolver no longer flips a deliberately-chosen provider back to Claude when its cached verdict is merely *absent* (absent ≠ invalid), so a configured ChatGPT / Gemini / Azure account survives the consent sheet. (2) Spawn-time `overlayPreferences` injects provider **and** model as a matched pair instead of a bare global model — the bug that ran `gpt-4o` under the Anthropic endpoint and 404'd. (3) The failure classifier checks LLM-error markers before Whisper markers and names the provider in its human summary, so an out-of-credit or bad-key LLM failure stops masquerading as a transcription failure; `degradedBody` no longer hides the captured cause. (4) The Settings status board is now eager — every provider row paints from cache the moment Settings opens and silently reconfirms, retiring the lazy dashboard and the activation no-op. Out-of-credit (402) becomes its own sticky state shown through a cached green, with activation decoupled from strict-online via `canActivate`; a pure, unit-tested `resolveStatus` centralises the cache-vs-masking decision. Reviewed by six agents + William.
- **Desktop status polish — copyable help, ⌘, from any focus, honest offline caption.** Provider status explanations now render as markdown (backtick `command` → inline monospace) and are selectable, so every explanation is copyable; embedded shell commands (today Ollama's `ollama pull …` / `ollama serve`) get a one-click monospace copy row reusing the diagnostic popover's *silent* copy idiom (no "Copied" flash — the Finder / Safari pattern), backed by a pure `LLMValidator.shellCommands(in:)` extractor. `⌘,` now opens the native Settings window from report focus too — `BristlenoseWebView` was claiming the key equivalent while it hosted the first responder, so Settings previously opened only from native chrome (⌘1/2/3, ⌘F, ⌘⇧E unaffected). The offline status caption softens "Your key is fine" → "Your key was fine" — offline we can only vouch for the last known-good check, not the current key; 402 / 429 messages keep present tense because there the key authenticated. Status-indicator vocabulary settled on colour + label with no per-state glyphs (the blue selected-tick vs green OK-tick collision was decisive), and the provider / keychain design docs are trued to the shipped data-protection-keychain + eager-status-board reality. New `desktop.llmSettings.copyCommand` string across all 6 locales. Desktop-only; reaches the alpha cohort with the next bundled-sidecar build.

**0.15.13** — _4 Jun 2026_

- **`bristlenose pipeline` view gains per-(provider, model) grain (feature rung v2).** The pipeline view added in 0.15.11 now renders a row per (provider, model) pair instead of one row per provider: each LLM stage shows Claude / ChatGPT / Gemini / Azure with their individual models, per-model editorial quality ratings, and a `recommended` axis split from `default` (the first build where they diverge — Opus 4 and gpt-4o are recommended over the defaults). `llm_summary` deleted in favour of per-stage rendering; payload `schema_version` 3 → 4 with a `_migrate_schema` placeholder hook. CLI and the React Settings → Pipeline tab both render the sectioned-flat matrix with quality glyphs, inline notes, and a compact symbol key (Availability / Quality subheadings group the glyphs; italic = from-your-settings). Column alignment fixed across every stage table (`table-layout: fixed` + shared colgroup so transcription / anonymisation line up with the LLM tables); the current/in-use row carries the app's selection wash + `aria-current` + sr-only label rather than a loud badge, and collapsed-provider rows render flush-left at provider level so ChatGPT / Gemini / Azure read as peers of Claude, not its children. `list_models(timeout)` uses `errors="replace"` so a wedged Ollama binary can't break `probe_host()`'s never-raises contract. Provider naming stays product-names; the account-vs-product rename + logos are parked post-TestFlight. Feature rungs and `schema_version` are decoupled both ways (internal payload restructure with no UX change; render-only rungs over data the schema already carries) — documented in `docs/design-pipeline-view.md`. New `test_models.py` declaration invariants + `_collapse()` unit tests; brittle model-id pins dropped. Ships on PyPI (CLI surface).
- **Desktop: on-device (Ollama) setup is now a model-first "flow B", and consent activates the chosen provider.** Two desktop landings. (1) **Flow B setup:** a toolbar pill drives phase popovers — choose model → get Ollama → wait → download → finishing — replacing the old `OllamaSetupSheet`. Honesty rule throughout: a static hourglass while Bristlenose is waiting on the human (download Ollama, daemon spin-up), a moving bar/spinner only while Bristlenose is actually doing work, red reserved for genuine failure — no timeout-to-failure, no animation when nothing is moving. The pill sits in the toolbar `.status` zone (its own trailing slot, not absorbed into macOS 26's primary-action capsule). Cancellation guards on every late daemon-snapshot write so a re-entry or cancel can't be clobbered by a stale async result. 43-key locale layer across all 6 `desktop.json` (German uses formal Sie). (2) **Consent activation:** the AI-consent sheet's Continue/Done path never wrote `activeProvider`, so a validated cloud key silently didn't take effect and the pipeline routed to a stale backend. Continue now runs the same activation the Settings toggle does, via a tested `ConsentActivation.resolve` helper that only switches when the active provider is local or unconfigured (never overrides a deliberate cloud choice). Stay-local applies the RAM-aware default and pulls the model ambiently through an app-level download surfaced in the pill, so the fetch survives sheet dismissal. Review fixes: failure pill error glyph/colour (`xmark.circle.fill` / `.red`), VoiceOver label + value on the pill, consent relabel + download-size hint, redundant `UserDefaults` mirror writes dropped (AppStorage already persists), consent audit-trail (DPIA anchor) documented in the desktop security audit. DEBUG-only menu-bar "Debug" harness cycles every pill/popover state for live QA — menu-bar, because macOS swallows `.contextMenu` on toolbar items with its own "Customize Toolbar" menu. Desktop-only; reaches the alpha cohort with the next bundled-sidecar build.
- **CI hardening — bounded jobs, pinned actions, least-privilege tokens.** Three classes of fragility closed after the 2026-06-03 e2e hang burned toward the 6-hour ceiling: every job now carries `timeout-minutes` (e2e + perf-gate) with a bounded-retry wrapper around the Playwright install so a hung CDN download fails fast instead of cascading to sibling workflows; the three third-party actions that touch secrets (`peter-evans/repository-dispatch`, `snapcore/action-build`, `snapcore/action-publish`) are SHA-pinned; every workflow lacking one gets a read-only default `permissions:` block. Methodology documented in `docs/design-ci.md` as a six-class fragility map with standing audit targets and `verify-pypi` as a load-bearing fence. `/usual-suspects` gains a CI workflow lens routing `security-review` + `silent-failure-hunter` at any diff touching `.github/workflows/**`. Workflow + docs only — wheel unchanged.

**0.15.12** — _23 May 2026_

- **Anthropic credit-exhausted is now reported as "out of credit", not "model unavailable".** Preflight's BadRequestError classifier was substring-matching on `credit_balance_too_low` (an `error.type` token that doesn't appear in `str(exc)`) — the live SDK message is `Your credit balance is too low to access the Claude API. ...`, so the branch silently missed and fell through to the model-unavailable copy. Hit on 21 May on a clean `bristlenose run` after credit ran out; user saw "The requested model is not available for your Claude account" and was directed at the wrong fix. Substring widened to `credit balance` to match what the SDK actually emits, aligning with the runtime path at `pipeline.py:339` (runtime classification was already correct; this was a preflight-only miss). Regression-pinned with the real SDK message in `tests/test_preflight_api_key.py` plus a sibling test asserting that the underscored-only token does NOT match, so any future "tidy-up" back to the original substring fails loudly. Broader LLM-error taxonomy work (16-kind `LLMErrorKind` enum, runtime-classification rewire, per-provider classifiers) parked as a separate branch — over-built for current evidence; let user reports drive what gets distinguished.

- **Desktop: ⌘⌫ no longer beeps on placeholder projects or multi-selection.** The Project menu's `hasProject` predicate conflated "is a project selected" with "does the bridge handler hold a serve-able path" — so ⌘⌫ on a brand-new placeholder from `+ New Project` (empty path) and ⌘⌫ on any multi-selection both hit AppKit's disabled-shortcut beep instead of removing the row(s). Receivers in `ContentView.swift` were already total over empty/mismatched selection (they guard on `sole` / iterate the selection set), so the gates were duplicating work the handlers already do. Removed `hasProject` and the four `.disabled(!hasProject)` sites; sharpened Show in Finder to just `selectedProjectRevealablePath.isEmpty` (the real predicate). William adjudication on the usual-suspects review added back two surgical gates so single-only operations dim correctly rather than silently no-op on multi-select — Rename and Move-to-folder submenu now `.disabled(selectedProjectPath.isEmpty)`, matching the Finder / Notes / Mail / Things 3 indie-consensus pattern. Remove-from-Sidebar stays ungated. Desktop-only; doesn't affect CLI / PyPI users until the next bundled-sidecar build reaches the alpha cohort.

**0.15.11** — _21 May 2026_

- **`bristlenose pipeline` + read-only Pipeline tab in Settings.** New CLI verb (`bristlenose pipeline`, with `--json` and `--stage <id>` filter) and matching last-position tab in the React Settings modal that render the mixture of models Bristlenose currently uses across its pipeline stages: MLX/faster-whisper for transcription, the chosen LLM provider × model for speaker identification / topic segmentation / quote extraction / quote clustering / thematic grouping, Presidio (or "Off") for anonymisation, and an Apple Foundation Models row that returns `Unknown from CLI` until the Swift-side probe ships. Two-column definition-list layout; deterministic ingest/audio/parse/merge stages omitted (they don't participate in the mixture story). Host context strip at the bottom shows OS · arch · RAM · keys present · ollama status. Read-only on purpose — to change a backend you still edit settings or .env. Reuses `_resolve_backend` from `s05_transcribe.py` for the transcription row; no parallel resolver. Cross-language schema lock at `tests/fixtures/pipeline-view-contract.json` round-tripped by Python tests and the React tab. New module `bristlenose/pipeline_view/` (renamed mid-branch from `pipeline/` after the collision with the existing `pipeline.py` orchestrator surfaced); the underscore in the package name keeps the user-facing CLI verb intact. 28 new tests; full suite green. Design captured in `docs/design-cli-improvements.md` §Captured design.

**0.15.10** — _17 May 2026_

- **Release pipeline actually fixed (test-only — wheel unchanged).** PyPI had been stuck at 0.15.3 since ~10 May — six tag pushes (0.15.4-0.15.10) reached GitHub but `ci/perf-gate` failed on every one, blocking the release workflow. Root cause: the v0.15.4-era server-rendered status page interceptor (`bristlenose/server/status_page.py`) returns "Nothing to see here, yet." when `app.state.last_run[1]` has no terminus event, and the smoke-test fixture's `bristlenose-output/` had never carried a `pipeline-events.jsonl`. Every Playwright run against that fixture got the status page instead of the SPA, `#bn-app-root` mounted empty, and perf-gate's `DOM nodes — Quotes` test timed out 30s into `waitForPageReady` — surfacing the failure five layers downstream of the actual cause and silently cascading six other perf-gate tests as "did not run". Fix: ship a fixed `RunCompletedEvent` line for project 1 in the smoke fixture's `.bristlenose/pipeline-events.jsonl`. Test-infrastructure only — `tests/` doesn't ship in the wheel, so the v0.15.10 source artifact is byte-identical before and after this fix. Tag re-pushed after the fix landed on main; PyPI sees 0.15.10 for the first time.
- **Structural protections so the next silent-mount regression fails loudly.** Three new layers: `tests/test_server_status_page.py::TestSmokeFixtureMountsSPA` asserts the on-disk smoke fixture boots into the SPA, not the status page (pytest layer — the cheapest place to catch the regression class). `e2e/tests/spa-mounts.spec.ts` is a standalone Playwright mount-precondition gate across four primary routes, running in the e2e job in parallel with perf-gate, with `console.error` / `pageerror` surfaced on failure so future mount issues land with stack traces instead of a bare 30s timeout. `perf-gate.spec.ts` itself gains a `beforeEach` browser-error capture for the same reason.
- **Post-push PyPI verification step in CLAUDE.md release flow.** A tag push reaching GitHub is not the same as a release reaching PyPI. New release-flow step polls `https://pypi.org/pypi/bristlenose/json` for up to 15 minutes after `git push origin main --tags` and applies the v0.15.0 debouncing workaround (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`) if the workflow didn't fire. Five versions of silent-gap masking should not be repeatable.
- **SIGTERM lifecycle subprocess test resilience.** `tests/test_run_lifecycle.py::test_subprocess_sigterm_writes_run_cancelled` and the SIGINT sibling have post-signal `_wait_for_event` timeout bumped 30s → 60s. Heavy-load Python 3.12 ubuntu-latest runners under full CI matrix contention have been observed missing the 30s window — flake on top of the perf-gate failure, picked up opportunistically while the release pipeline is open.
- **`--codebook=<slug>` flag + `bristlenose codebooks` subcommand.** CLI plumbing for selecting an AutoCode codebook framework from the command line. `bristlenose codebooks` lists the nine available templates (`sentiment`, `uxr`, `cli-ux`, `garrett`, `morville`, `nielsen`, `norman`, `yablonski`, `plato`) with title and author; `--codebook=<slug>` on `run` and `analyze` validates the slug against the YAML inventory and exits cleanly with the available list and a pointer to the subcommand on a typo (preflight-abort convention, exit 2, matches the v0.15.8 banner mapping). Validation only — the pipeline doesn't auto-run AutoCode against the selected codebook yet; the flag stores the preference on `BristlenoseSettings.codebook` for a follow-up branch to wire the consumer side. C1 from the brew-first-run + IKEA-call cluster; the reframe (11 May) deliberately deferred the "auto-run default codebook" UX moment to a later desktop codebook-picker chunk, gated on cohort calls. Reviewed via three agents (code-review, james-bach, william-of-ockham); Rich-markup escape applied at the interpolation site even though no current YAML triggers the gotcha, future-proofing per the CLAUDE.md audit-on-write convention. New `list_available_templates()` + `list_available_slugs()` helpers in `bristlenose/server/codebook/` give the enabled-filter a single source of truth across the validator and the subcommand. 11 new tests; full suite 2681 passed.

**0.15.9** — _16 May 2026_

- **Multi-project Phase 2 #11 + #14 — drag-onto-folder copy machinery + folder watcher foundation.** Two big landings on top of the v0.15.8 multi-project foundation. Drag-onto-existing-project now goes through a copy path (`CopyMachinery`) instead of reference-in-place — progress pill with per-file estimate, `NewFilesSheet` stub for post-copy review, regression-pin tests in `CopyMachineryTests` covering collision-rename and folder-name preservation. Folder watcher: `NSFilePresenter` + SQLite ingested-set table (opened with `immutable=1` for the read path) tracks what's been seen per project; count pill on the row surfaces the delta against the project's current input set; clicking opens a sheet for triage. Two review passes ran on top — first pass: F1 iCloud-evicted detection, F3 debounce scans, F6 SQLite busy-handling; second pass: F49 cloud-evicted glyph swap (`icloud` outline, not `icloud.and.arrow.down` — that arrow connotes download-in-progress, wrong meaning here), F50 pointing-hand cursor on the delta button with no underline (native idiom, not web anchor), F52 session count uses `.footnote` (function-correct per Apple's text-style scale, not "12pt eyeballed"), F53 subtitle text uniformly `.secondary` (state via glyph, not via graduated text colour), F59 / F62 i18n + comments. `NewFilesSheet` flagged as TF scaffolding for post-TF SPA migration — data views belong in the React project dashboard, not native chrome. Row reshape: session count moved onto the title row, deltas moved into the subtitle, Schema A dates throughout.

- **Sidebar honesty wave 2 — `.ready` gated on disk evidence + per-reason cantFind glyphs.** v0.15.8 sealed the "fake-success" class of bug at the pipeline layer; this pass closes the matching surface in the sidebar. A re-opened project that had completed analysis weeks ago briefly showed "analysing…" because the row state was reading `is_running` instead of inspecting `bristlenose-output/` for completion artefacts. `.ready` now requires disk evidence — a completed run record plus at least one canonical output file — so re-opens read "Ready" immediately. cantFind glyph specialises per reason: `.moved` → `questionmark.folder`, `.cloudEvicted` → `icloud` (outline), `.permissionDenied` → `lock.shield`, `.removed` → `folder.badge.minus`. Volume remount no longer regresses to `.moved` when the bookmark resolves cleanly to the original path. AppleDouble (`._*`) sidecars and `.DS_Store` skipped across every directory scanner (`is_os_metadata()` in `bristlenose/utils/fs.py`, applied at `discover_files`, `load_transcripts_from_dir`, and the server importer scan sites) — hit 16 May 2026 when a project was copied to an ExFAT SD card and `._s1.txt` looked like a transcript to the pipeline and crashed utf-8 decode with `UnicodeDecodeError: byte 0xb0`. Swift `ProjectFolderWatcher` already filters via `.skipsHiddenFiles` + `name.hasPrefix(".")`, so the Python side closes the symmetry. New `tests/test_appledouble_filter.py` pins the behaviour. CLAUDE.md now flags the trap for future scan sites.

- **Pipeline subtitle i18n across 6 locales.** Sidebar row subtitles for in-flight pipeline state (`Transcribing…`, `Extracting quotes…`, `Clustering themes…`, etc.) now render in the user's locale — previously English-only because the strings were synthesised in Swift from raw stage keys. Translations across es / fr / de / ko / ja matched against the Apple glossary where possible; `dt()` overrides where the desktop register diverges from the CLI's. New keys flow through the existing six-locale `desktop.json` shape so subsequent additions stay symmetric.

- **Keychain hardening — biometric ACL on stored API keys + dev-build persistence.** API keys held in the macOS Keychain now require Touch ID (or password fallback) to read, via biometric access control on the Keychain item — adds a "you, at the keyboard" gate to the key escrow even if the device is unlocked and another app is malicious. Distinct from disk encryption; it raises the cost of a piggybacked-process attack. Debug builds switched from Apple Distribution to Apple Development signing because Distribution-signed debug builds were burning Keychain ACLs on every rebuild — every debug Run prompted for Touch ID and asked the user to re-grant access, making the feature un-dogfoodable. Hardware-validated on the dev machine across multiple build cycles; the underlying keychain entry survives across rebuilds, restarts, and worktree switches.

- **HIG corpus mirror + citation discipline for review agents.** Local Apple Human Interface Guidelines mirror added so `what-would-gruber-say` can cite HIG sections by path + paragraph anchor instead of paraphrasing from training data — same epistemics as `docs/design-test-philosophy.md` for `what-would-james-bach-say`, but for native-feel reviews. The scraper that built the corpus is written generic from day one so the public release (planned at github.com/cassiocassio/what-would-gruber-say) is a copy operation not a rewrite, mirroring the william-of-ockham pattern (MIT, 1 May 2026). Citation discipline is now expected for every Mac-app review finding the agent surfaces.

- **Misc polish.** `Window > Bristlenose` menu item to reopen the closed main window — Mac default that every document-shaped app has; ours didn't. Session start time no longer floored to midnight on the dashboard — display was rounding `started_at` to the date boundary, losing same-day session ordering when multiple sessions were transcribed within one calendar day. In-flight switch modal: "Continue analysing" reframed as the cancel role so Esc and the default action keep the analysis running rather than killing it — HIG-correct default is the non-destructive option, and the Stop and Switch action carries the destructive style.

**0.15.8** — _14 May 2026_

- **Honesty everywhere — the pipeline, the install path, the sidebar all stop faking success.** v0.15.7 was a pipeline-only meta-release; this is the substantive follow-up. The walks-fix-walks gate (7 May quality reset) demanded that "did this work?" be answerable everywhere in the app. Three currents land together:
  - **CLI honesty (A-stream brew/IKEA cluster).** `bristlenose doctor` now hard-errors with a brew/pipx/pip-aware fix message when `[serve]` extras are missing (was a silent runtime crash later in `bristlenose serve`); the message is zsh-glob-safe quoted to keep `'bristlenose[serve]'` from being eaten as a shell pattern. The Rich `console.print` markup-eating gotcha — `[serve]` rendered as `''` because Rich parsed it as a style tag — fixed at three print sites by adding `markup=False` to the relevant calls; a CLAUDE.md gotcha now flags any new `console.print` that interpolates package-spec / file-glob / version-range text. `bristlenose run` / `serve` / `analyze` all gate `serve_deps` in preflight before stage 1; when the pipeline abandons mid-run, `PipelineAbandonedError` maps `Cause.category` to a researcher-facing banner (QUOTA, API_REQUEST split from QUOTA, AUTH with provider name + key-shape suffix, NETWORK, API_SERVER, DISK, MISSING_INPUT, MISSING_BINARY) instead of a generic "Failed". The static-render naming is finally sealed: `bristlenose render` removed (replaced by a hidden Typer catch-all stub that redirects to `run` / `serve` with a friendly message), `--static` deleted as a `run` option. `--no-serve` restored as a hidden flag — A3's first pass deleted it alongside `--static`, the doc sweep caught it being aliased on the macOS sidecar's `PipelineRunner.swift` call site separating two semantically-distinct concerns (suppress static render vs suppress auto-serve), so it came back without the misleading `--static` alias. `_QUOTA_RE` split into QUOTA + API_REQUEST; `_AUTH_RE` extended to cover real Anthropic / OpenAI SDK 401 strings + tightened to drop bare-word false positives. Doc truing across man page, README, manual, CLAUDE / CONTRIBUTING / DEVELOPMENT / SECURITY, and 20 design docs in the same release.
  - **Stage-cache honesty (A4).** Abandon-check now fires BEFORE `mark_stage_complete` (was after — the bug at `pipeline.py:1308` that produced fake-success states where an LLM-failed stage cached its empty output and on rerun was skipped as "already done"). `s08` PII removal added abandon-check. `s10` (quote extraction) and `s11` (quote clustering) flipped from soft-fail to hard-fail: `StageFailure` is now emitted at the LLM call site BEFORE fallback runs, so the upstream cache and downstream pipeline both know the truth. `mark_stage_complete` refuses to record `content_hash` for empty content (defence-in-depth: even if a stage misbehaves, the cache stays honest). Privacy contract on `cause.message` — class name + provider + stage only, never `str(exc)` (exception strings can carry PII / API keys / file paths). Whisper-zero-segments treated as success (silent interviews are a real research signal, not a failure). `topics` bucket added to `PipelineSummary`; cross-branch contract fixture bumped to v5. 470 lines of new tests across `test_pipeline_abandon.py` / `test_manifest.py` / `test_run_lifecycle.py`.
  - **Long-audio quality (B1).** Whisper-loop band-aids: `collapse_adjacent_repeats()` post-processor catches Whisper looping on the same word ("thanks thanks thanks", "facebook facebook") while preserving natural interjection doubling ("No. No. No.", "yeah yeah"). Three Whisper params tuned for mlx-whisper: `condition_on_previous_text=False` (stops decoder context-poisoning across silent gaps), `no_speech_threshold=0.85` (raises bar for hallucinated transcript in silence), `compression_ratio_threshold=1.8` (catches repetition loops). Speaker propagation surface: regression-pin unit tests for moderator/participant heuristic + `pct_words` (defends against silent flip on future refactors); design-doc clarification + INFO log surfacing the architectural limit ("LLM splitter forward-propagates last label from 5–8 min sample window past the window"). Pre-implementation diagnostic against preserved interview artefacts caught two of three reported bugs as already-fixed or by-design before any code was written.

- **Multi-project foundation (Phase 0 + Phase 1) — the sidebar starts telling the truth about each project's state.** Phase 0 schema lock: `ProjectAvailability` enum (`ready` / `not-found` / `cloud-evicted` / `permission-denied`) with `last_seen_at` timestamps in `projects.json`, propagated through `BridgeHandler` and the sidebar's `ProjectRow`. Cross-branch contract fixture v5 documents the schema for follow-up branches. Phase 1 UX wins: removing a project from the sidebar is now undoable via a 5-second toast (Cmd-Z works during the window) — undo restores both the row position and any in-flight scroll state; cancelling commits the removal. "Locate…" flow for `not-found` projects walks the user through Spotlight one-shot search → NSOpenPanel fallback → cancel with grace; the chosen path is captured via security-scoped bookmark and stored alongside the existing bookmark, so the next launch resolves cleanly even after another move. Spotlight one-shot uses a 2-second `NSMetadataQuery` (returns top match by display name; tie-break by depth then mtime); query cancels cleanly if the user clicks Browse first or dismisses.

- **Multi-project sidebar switching (Phase 2 #1/#2/#3).** Sidebar-clicking a different project now tears down the current sidecar (SIGINT → 50ms poll → SIGKILL after 2s) and spawns a new one pointed at the picked project. In-flight pipeline runs prompt a confirm sheet (Stop and Switch / Stay) before cancelling — HIG-correct default-action "Stay" across all 6 locales, with Apple's negated-form translations (es No cambiar / fr Ne pas changer / de Nicht wechseln / ko 그대로 두기 / ja 変更しない). `ServeManager.shutdown(timeout:)` escalating teardown; `switchProject(to:)` orchestrator. Server `/api/projects/*` gets `Cache-Control: no-store` as belt-and-braces against WKWebView HTTP cache surviving the `.id()` rebuild. `ProjectBookmarkLease` (Mini-spec 3) ships as foundation with tests; the next-branch wiring (#14 folder watcher) consumes it. Reviewed by 6 agents + William's parsimony pass; finding 30 (in-flight cancel atomicity) parked — cost-bounded by existing manifest+resume; durability hardening is post-beta. Phase 3 (cloud-evicted single-state) remains open.

- **Pipeline-failure trust-UX (re-run failure ≠ broken project).** Cohort-style QA on multi-project switching surfaced a fake-success cousin: clicking Run on a project that already has `bristlenose-output/` produced `Failed (unknown)` + sidebar badge "Something went wrong" + Retry-that-just-fails-again in the popover. Cohort testers would read "the project is broken" — but the *re-run attempt* failed, not the prior analysis. New `PipelineFailureCategory.outputExists` (matches Python `CauseCategoryEnum` snake_case rawValue); `categoriseFailure` regex matches "output directory already exists" first in the chain so the broader whisper/model heuristic can't hijack it. Human summary in researcher register: *"Already analysed — re-analysing would replace the existing results."* Sidebar badge: *"Already analysed."* The popover swaps Retry → "Re-analyse…" which opens a destructive-confirm alert ("This will delete the existing analysis and run from scratch. Any researcher edits in this project will be lost.") before spawning with `--clean`. `PipelineRunner.start(project:clean:)` overload threads the flag through; queue path doesn't preserve it (queue + Re-analyse interaction is a follow-up if observed).

- **Drag-onto-project to add files, with project-onto-project rejection.** Plan §11 data-integrity guard. Dragging a Finder folder onto an existing project's row in the sidebar adds its files via the existing `addFiles` path (reference-in-place, not Copy — adequate for typical cohort flow where source folders are stable on local volumes). Guard: when the dropped folder is itself a Bristlenose project (`folderLooksAnalysed` — `bristlenose-output/` with at least one canonical artefact), the drop is rejected with a non-modal toast ("'%@' is already a Bristlenose project — drag its source files instead"). Started life as a single-button Apology-Alert; cohort QA — "alerts for things users won't want to do anyway? that's not how Mac apps work" — flipped it to a toast per HIG (alerts are for decisions, not explanations). Self-drops silently ignored. Six locales updated; out-of-scope deferred to chips: actual file copying, progress pill / Cancel / rollback for cross-volume multi-GB drops, "folder that *contains* a project" rejection (rare nesting), disk-space precheck, hover affordance polish.

- **Sidebar drop hit-test refactored to the native SwiftUI pattern.** Original implementation hand-rolled hit-testing on top of `.onDrop` + `DropDelegate` + `GeometryReader` + `PreferenceKey` plumbing in a custom coordinate space. The macOS coordinate-space mess (`.global` returns bottom-left Cocoa coords; `.named`/`.local` returns top-left SwiftUI coords; `DropInfo.location` documented as local but empirically inconsistent across SwiftUI versions — Apple forum thread 732076) produced two real bugs in cohort QA: drag-highlight followed the cursor at a constant y-offset (rows lit up one off the cursor's actual position), and the project-onto-project reject alert was silently unreachable because the hit-test missed the target. Two patches tried to fix the coordinate-space math (record frames in `.global`, then self-healing hit-test that prefers direct match) before the native-pattern refactor replaced ~209 lines of bespoke machinery with per-row `.dropDestination(for: URL.self, action:isTargeted:)` (since macOS 13). SwiftUI now manages coordinate-space concerns internally; URLs come pre-loaded — no `NSItemProvider` async dance. Polish: `.onDisappear` clears the hover-target state as insurance against the macOS intermittent bug where `isTargeted=false` doesn't fire when the cursor drag-leaves the window entirely. Chipped for follow-up: `FolderRow` accepting Finder URL drops directly, internal-project payload as a `Transferable` newtype (custom UTType app.bristlenose.project-id) instead of `String`, drop-affordance VoiceOver label.

- **Locales now reach the host bundle under sandbox.** The Xcode "Copy Sidecar Resources" script phase only declared `en/common.json` as an input/output anchor; editing any other locale file (en/desktop.json, the five non-en locales) didn't trigger the phase to re-run — Xcode's dependency analysis saw no relevant input change. The rsync inside the script never fired and the bundle kept yesterday's copy of every locale file. Symptom: new `desktop.chrome.*` keys rendered as raw key strings in alert titles/messages under the default scheme (sandbox=on, sidecar=bundled). Closes a longstanding "i18n locales not reaching host bundle under sandbox" gotcha. Fix: `alwaysOutOfDate=1` on the phase, same pattern Generate Build Info already uses; the rsync body is idempotent and the cost is ~50ms of syscalls per build.

- **Two pre-existing UX bugs surfaced by cohort QA.** `common.cancel` rendered as a raw key string in three alert dismiss buttons because the key actually lives under `common.buttons.cancel` and `common.activity.cancel` — none at the top level. Fixed all three call sites. File-subset projects (projects analysed against an explicit file selection rather than a whole folder) gated their detail pane on `inputFiles != nil` alone, so even file-subset projects with completed analysis showed the `UnsupportedSubsetView` instead of their report; same principle as the trust-UX work above — run state shouldn't block viewing what's already there. Added `pipelineHasViewableData` (true for `.ready` and `.partial`), ANDed with the `inputFiles` check.

- **HIG: trim ellipsis from "Choose Icon" menu label.** Opens a popover, not a dialog — ellipsis is wrong per HIG. Dropped from all 6 locales. Full flyout/submenu UX (trim palette, hybrid Finder-tag-colour, custom-grid Menu) captured for later.

- **Swift 6 main-actor isolation fix.** `SpotlightOneShot()` as a default argument was evaluated in the caller's isolation context, but the initializer is `@MainActor`-isolated. Swift 6 strict concurrency rejects this even though `LocateFlow` itself is `@MainActor`. Defaulting to `nil` and constructing inside the body keeps the call MainActor-scoped without forcing every caller into an async path. Was blocking Xcode build on main.

- **CI hygiene.** `.tool-versions` now pins node 24.6.0 + python 3.12.13 (mise / asdf / rtx all read this; CI workflows derive Node + Python versions from the same file). No more "works on my machine but fails on CI because mise gave me 24.8.0 and CI runs 24.6.0" drift. Branch-protection-style `no-red-CI-merges` policy documented in `CONTRIBUTING.md` — main branch only accepts green merges; two pre-existing CI failures surfaced by the gate are noted in TODO with reproduction steps. Release-pipeline fix from v0.15.7 stays in (the Node 24 measurement-artefact 210 → 215 kB ceiling re-baseline; `frontend/CLAUDE.md` documents the call: runtime currency / security / dep coherence outweighs sub-1% gzip headroom).

- **Workflow tooling for parallel Claude sessions.** Three skills land:
  - **`/end-session` sign-off sentinel + `/close-branch` drift check** — `/end-session` writes `.claude/last-end-session.json` (gitignored) recording phase outcomes + HEAD sha. `/close-branch` reads it: warns before archiving a branch that was never end-sessioned, or that has drifted (commits added) since sign-off. Stops the "I thought I closed that" class of mistake.
  - **`/new-feature --print-launch-url` flag + Step 14 hand-off** — branch-creation can now emit a `claude://` deep link the user can hand to the next session; the spawned session reads the canonical handoff path automatically. Pairs with the existing handoff convention.
  - **`/sitrep` skill** — situation-report with backward truth-check (plan-docs vs git over a rolling window) + forward candidate ladder. Sprint-aware grid format: prose preamble → sprint frame + contents tables → recent ships → in-flight branches → forward ladder (with sprint-tag column) → recommendation → suggestions. William of Ockham agent triaged the first review pass to 7 spec edits before the skill landed.

- **Agent ecosystem.** New `what-would-james-bach-say` reviewer agent — test-placement reviewer in the Bach / context-driven-testing tradition: catches tests at the wrong layer, tests that lock implementation rather than invariants, coverage gaps for invariants the user would actually notice, brittle exemplars that future agents will imitate, "while we're here let's also test X" scope creep. Sibling to code-review / perf-review / security-review — this one is testing taste and proportion, not correctness. Reads `docs/design-test-philosophy.md` for the project's house position. Reminder slated to audit aggregate impact after a month.

- **`/true-the-docs` v2.** New `--claude-pointers` mode reconciles the references-and-pointers layer of CLAUDE.md files specifically (which can drift independently of substantive prose). Phase 5 sweep landed: 3 historical docs archived, CLAUDE.md bloat trimmed, source-aware archival pattern documented in the public archive README. Sibling to A3's design-doc sweep — same epistemics, different doc class.

- **Sidecar build fixes.** PyInstaller bundle now ships `inflect` + `typeguard` `.py` sources alongside their `.pyc` — both packages call `inspect.getsource()` on their own functions at runtime, which fails on a bytecode-only bundle. Fix: `collect_data_files` for both packages. Sidecar resource-copy step also switched to `rsync -aL` (was `cp -RL`) to dereference symlinked sources cleanly — `cp -RL` was breaking the mlx metallib's internal rpath symlinks under macOS sandbox.

- **Frontend bundle ceiling 210 → 215 kB.** Node 20 → 24 zlib upgrade (1.2.13 → 1.3.1) compresses the live SPA bundle slightly differently; the 0.75 kB "overage" against the 210 kB ceiling was a measurement artefact, not a regression. Re-baselined: current live SPA is ~210.5 kB gzipped against the new 215 kB ceiling. `frontend/CLAUDE.md` documents the call.

**0.15.7** — _12 May 2026_

- **Release-pipeline fix that unblocks v0.15.4–6 reaching PyPI + Homebrew.** Three independent CI failures had been silently stacking up since 10 May, leaving PyPI and the Homebrew tap pointed at 0.15.3 while the source tree was on 0.15.6. No user-facing source change in this version; the entire v0.15.4–6 changelog (preflight block, server-rendered status page, SPA auto-refetch, sandbox-safe Export, structured failure causes, etc.) is what users actually pick up when `brew upgrade bristlenose` (or `pip install -U bristlenose`) catches up to 0.15.7.
  - **`tests/test_pipeline_abandon.py`** — the ffmpeg preflight introduced in v0.15.5 aborts on Linux CI runners (no ffmpeg on PATH). The test already patched the Whisper preflight; the same bypass is now extended to ffmpeg, with a reminder for future preflights.
  - **`tests/test_serve_auth.py`** — `test_spa_html_sets_cookie` hit `/report/`, which returns 500 (fail-loud, by design since C3) when the React bundle is absent. CI's Python `test` job doesn't run `npm run build`. Switched to the existing `_VITE_INDEX_HTML` + `_STATIC_DIR` patch pattern from `test_serve.py` — a 5-line fixture change rather than restructuring CI to build the bundle in 8 matrix cells.
  - **`.github/workflows/{ci,release}.yml`** — Node 20's zlib 1.2.13 compressed the live SPA bundle to 210.75 kB (over the 210 kB limit); Node 24's zlib 1.3.1 compresses identical bytes to 204.4 kB. The 0.75 kB "overage" was a measurement artefact of the CI Node version, not a real regression. `frontend/CLAUDE.md` already documented Node 24 LTS as required; CI is now in sync.

**0.15.6** — _11 May 2026_

- **Server-rendered status page for runs the SPA can't render** — `bristlenose serve`'s `/report/*` catch-all now serves a server-rendered page (no React mount) when the project has no completed run, or the latest run failed or was cancelled. The SPA's invariant becomes: it only mounts when there's data to render. Three states surfaced — no-run-yet (CLI vs desktop copy via `BRISTLENOSE_PLATFORM`), failed (with cause + log tail in a `<details>` block, sourced from `pipeline-events.jsonl`), cancelled. Reuses the five-kind `MessageKind` taxonomy from `bristlenose/ui_kinds.py` — no sixth kind invented. Page styling lives at `bristlenose/theme/templates/status-page.css` and uses the design system's tokens exclusively (sibling to `report.css` / `transcript.css` / `print.css` / `export.css`). The event-watcher startup seed in `bristlenose/server/app.py` also widened to seed `failed` and `cancelled` termini, not just `completed`, so non-happy-path runs survive a server restart. English-only in v1; locale fills for es/fr/de/ko/ja batched into the next translation pass

**0.15.5** — _11 May 2026_

- **First-run preflight block: Whisper / ffmpeg / API-key / spaCy, all before stage 2.** Eight-slice landing of `docs/design-cli-just-works.md`. Triggered by a 2-hour first-run call with a friendly CTO on 9 May where four blockers fired in sequence (silent ~1.5 GB Whisper download, Ctrl+C resumption opacity, `--redact-pii` hard-failing on missing `en_core_web_sm`, API key with no billing balance burning six minutes of transcription before stage 8 noticed). Every gap now surfaces up front:
  - **`bristlenose/preflight/whisper.py`** — Whisper-model preflight with backend-aware cache probe (`Systran/*` → `model.bin`, `mlx-community/*` → `weights.npz`; tolerates HF Hub leaving `config.json` from an interrupted download). Framed banner above (model name, `~1.5 GB`, "Cancellable with Ctrl+C; resumes cleanly next run."), HF Hub's native progress in the middle (Option B from the design-doc Debate 1 — we step aside; the Rich spinner stops + restarts around the fetch), `✓ Whisper model ready [Ns]` below. `WHISPER_SIZE_HUMAN` is the single source of truth — referenced by both the banner and the `doctor --fetch` help text. New `bristlenose <run|transcribe|analyze> --no-fetch` aborts cleanly with the recovery message instead of fetching; `bristlenose doctor --fetch` pre-warms the cache for offline runs.
  - **`bristlenose/preflight/ffmpeg.py`** — distro detection from `/etc/os-release` (`macos` / `ubuntu` / `fedora` / `arch` / `other`). Per-distro install table with the matching distro row first, padding computed at print time so translations don't misalign. On macOS with Homebrew on PATH and `brew --prefix` writable, an explicit `[y/N]` offers `brew install ffmpeg`; default flipped to **N** so a hurried Enter never installs system software. The brew subprocess runs natively with the Rich spinner stopped, `✓ ffmpeg installed [Ns]` after.
  - **`bristlenose/preflight/api_key.py`** + **`bristlenose/llm/billing_hints.py`** — paid-call validation against billing. Single-token `/messages` request (locked literal prompt `"."`, never user-derived; `User-Agent: bristlenose/<version>`) to the configured Anthropic or OpenAI account — costs ~$0.0001 and exercises the credit-balance path that a free probe misses. Anthropic 400 `credit_balance_too_low` → `billing_empty`; OpenAI 429 `insufficient_quota` → `billing_empty`; `AuthenticationError` → `invalid_key`; `BadRequestError` (other) → `model_unavailable`; `RateLimitError` → `rate_limit`. Each maps to a translatable wrapper around the code-owned `ProviderBilling` registry (`console_url` / `keys_url` / `billing_url` / `minimum_note` per provider). Azure / Gemini fall through to the generic "Provider says: …" copy per finding 24 in the design doc. Result cached for 24 h per provider in `state.json` (mode `0o600`, atomic write via `os.open` + `O_TRUNC`) at `~/Library/Application Support/Bristlenose/state.json` (macOS) / `$XDG_DATA_HOME/Bristlenose/state.json` (Linux). Non-TTY runs still validate (CI catches expired keys); only the first-run source-attribution banner is suppressed in non-TTY mode. `BRISTLENOSE_SKIP_PREFLIGHT=1` is the explicit escape hatch for spoofed-TTY CI runners. Network / TLS / corporate-proxy faults surface with a dedicated `network` error class rather than collapsing to the generic provider-error copy.
  - **`bristlenose/stages/s07_pii_removal.py`** — spaCy `en_core_web_sm` (~12 MB) lazy-fetches on the first `--redact-pii` run via `python -m spacy download`. Single inline line, no banner ("fetch UX scales with fetch size"). The spaCy `Console()` instantiation moved into `_ensure_spacy_model()` so terminal-width detection isn't frozen at module-import time (sandbox-piping concern). `MessageKind.SUCCESS` / `MessageKind.ERROR` glyphs used for the done/failed lines.
  - **`bristlenose/utils/package_install.py`** — two install helpers (`ensure_spacy_model`, `ensure_hf_model`) with frozen-sidecar guards so a desktop-bundle accidentally hitting these paths raises `FrozenSidecarError` instead of silently failing against read-only `site-packages`. (`ensure_wheel` shipped in an interim draft, deleted in the post-review pass when it had no callers.)
  - **Front-loaded as a single block in `bristlenose/pipeline.py`** — all preflights fire between ingest (stage 1) and audio extraction (stage 2). After the block, the pipeline prints `No more questions. ~X min (±Y min) to your report. Ctrl+C anytime.` (estimate from the existing Welford estimator when warmed up; degrades gracefully without the parenthesis when it isn't). No prompt fires for the rest of the run.
  - **Unified `PreflightAbortedError`** in `bristlenose/preflight/__init__.py` for all three preflights; CLI catches once at the `run` / `analyze` / `transcribe-only` call sites and exits 2 with the recovery message.
  - **i18n** — new `preflight.*` namespace under `bristlenose/locales/<loc>/preflight.json` covering banner copy, install-table labels + commands, four error-class recovery wrappers, source attribution, closing line. English is the source of truth; es / fr / de / ko / ja currently mirror en and will get native review in the next translation pass.
  - **Documentation truing** — design doc updated with a post-implementation Status table mapping each item to SHIPPED / DEFERRED / PARKED; sections that drifted (state path, Whisper stage placement, lint-rule promise, no-account-yet flow) now carry inline corrections + deferral banners. New §"i18n implications" subsection covers namespace shape, code-owned vs translatable surface, translator workflow. `SECURITY.md` adds a fourth "Data leaves your machine only when" bullet covering the preflight call (one full stop, ~$0.0001, no transcript content, 24 h cache), a "What Bristlenose writes to your machine" appendix, and an HF Hub LFS-hash integrity caveat. `docs/platform-text-map.md` carries a CLI-only row for the new namespace. Man page (`bristlenose/data/bristlenose.1`, symlinked from `man/bristlenose.1`) gains an `Options for doctor` section, documents `--no-fetch` / `--fetch` / `--yes` / `--static` / `--dev` (the last three were pre-existing gaps), records `state.json` under FILES, adds exit code 2, and the `BRISTLENOSE_SKIP_PREFLIGHT` env var. `scripts/bump-version.py` now refreshes both version and ISO date in the `.TH` line on every bump (no more stale "March 2026" on a May release).
  - **Deferred to follow-up** (captured in `.claude/plans/cli-just-works.md` Decisions block + `TODO.md`): the no-account-yet branch (numbered URL flow + getpass + Keychain persist) — material UX work depending on the front-load collector; `pipeline-events.jsonl` `Cause` entries on preflight abort; whitelist enforcement for read-only commands; Keychain-source attribution refinement.

**0.15.4** — _10 May 2026_

- **SPA: auto-refetch on pipeline completion** — new `GET /api/projects/{id}/last-run` endpoint and `LastRunStore` (module-level, single timer, 3 s poll, visibility-paused, in-flight skip, mount baseline). All four content tabs (`QuotesTab`, `SessionsTab`, `ProjectTab`, `CodebookTab`) accept `refreshKey?: number`; islands re-fetch when the store detects a new `run_id`. `announce(t("announce.pipelineCompleted"))` fires on `run_id` transition (skipped on first-poll startup-seed). Closes the gap where the browser SPA went silent after the pipeline finished — users now see fresh content within ~3 s without reloading. Import-then-publish race fixed on the server side
- **SPA: trust-UX layer on top of auto-refetch** — manual refresh button in the NavBar (serve-mode only; hidden in the desktop app's embedded mode, where the OS toolbar owns chrome and 3 s auto-poll carries the trust signal alone). Refetch overlay (opacity dim + pointer-events-none) on Quotes / Sessions / Dashboard while a refetch is in flight, so the screen no longer snaps silently. Post-zero-quotes empty state on the Quotes tab: *"Analysis finished but found no quotes. Check the source files or try a different LLM provider."* Pre-pipeline empty state deliberately out of scope here — that surface belongs to the upcoming generic-failure-surface work and the desktop `WelcomeView`
- **Desktop: Export downloads route via `WKDownload` + `NSSavePanel`** — sandbox-safe Export. Previously the browser/Vite serve path leaned on a synthetic `<a download>` click that the App Sandbox silently dropped — users got "Export" feedback but no file. The desktop shell now intercepts the Export request, hands the response to `WKDownload`, and prompts the user via `NSSavePanel` for a user-chosen destination. Six locale `desktop.json` files updated for the save-dialog strings. Edge case: round-tripping the locale JSON through `json.load`/`json.dump` rewrites every `\u` escape (or every literal Unicode, depending on `ensure_ascii`); fixed via targeted text-replace with per-value `json.dumps(value, ensure_ascii=True)`. Gotcha now captured in `CLAUDE.md`
- **Desktop: surface structured `Cause` from events log in the failure pill** — `EventLogReader` now exposes the categorised `Cause` from `pipeline-events.jsonl` (10 categories: `MISSING_INPUT`, `MISSING_BINARY`, `LLM_ALL_FAILED`, etc.). The failure pill in the project sidebar renders the category-appropriate glyph + short label instead of the generic "Failed" badge. Pairs with the schema-coupled `PipelineSummary` rollup that landed earlier in this version. New `Pipeline.run` integration test exercises the transcribe-all-fail abandon path end-to-end. Review-pass fixes: tightened `pytest.raises` assertions to specific exception types, copy-button now confirms with brief visual feedback, "human" category label refined

- **CLI: glyphs + colours sourced from `MessageKind` taxonomy** — the `_print_step` / `_print_warn_step` / `_print_error_step` / `_print_cached_step` family in `bristlenose/pipeline.py` now delegates to a single `_print_stage(message, kind, elapsed)` helper that consults `bristlenose.ui_kinds.cli_prefix(kind)` for the leading glyph + colour. New `_say(kind, message)` helper in `bristlenose/cli.py` replaces ~20 ad-hoc tinted `console.print("[colour]...[/colour]")` calls so glyph/tint comes from one table (CLI / popover / toast all in sync). Doctor + status icon dispatch also routes through `cli_prefix`. Decorative `[dim]…[/dim]` annotations untouched. No user-visible behaviour change beyond a few borderline-coloured lines now showing the correct kind glyph
- **Pipeline: structured per-stage failure summaries + abandon path for empty-data runs** — every terminus event (`run_completed` / `run_failed` / `run_cancelled`) now carries an optional `summary` field with a `PipelineSummary` rollup (per-stage attempted / succeeded / failed counts plus categorised `Cause` per failure). When every transcription session fails or every quote-extraction LLM call fails, the pipeline now raises `PipelineAbandonedError` instead of silently writing a fake-empty report — the run terminates cleanly with no report file on disk. Two new `Cause.category` values (`MISSING_INPUT`, `MISSING_BINARY`); bare-name `FileNotFoundError` (e.g. `'ffmpeg'` under sandbox) now categorises as `MISSING_BINARY` instead of `UNKNOWN`. Backward-compatible: legacy events log lines without the new `summary` field deserialise cleanly with `summary=None`. Schema-coupled with the upcoming desktop diagnostic-pill work but not runtime-coupled. See `docs/design-pipeline-resilience.md` 2026-05-07 changelog entry
- **Sidecar: prepend bundled FFmpeg dir to `$PATH` so `mlx_whisper` resolves under macOS App Sandbox** — `mlx_whisper.audio.load_audio` shells out to bare `"ffmpeg"` via `subprocess.run`, bypassing our `bundled_binary` helper. Under the sandbox the inherited PATH doesn't include Homebrew, so transcription failed with `[Errno 2] No such file or directory: 'ffmpeg'`. New `prepend_bundled_to_path()` in `bundled_binary.py` runs from `bristlenose/__init__.py` so the bundled directory is on PATH before any submodule imports. No-op for CLI / pip / Homebrew installs (no bundle dir to prepend). Same fix transparently covers `faster_whisper` and any other transitive bare-name shellouts
- **Sidecar: avoid `/bin/ps` exec under macOS App Sandbox** — `run_lifecycle._ps_start_time()` now reads process start time via libproc `proc_pidinfo(PROC_PIDTBSDINFO)` on Darwin (same call Activity Monitor uses) instead of subprocessing `/bin/ps -o lstart=`. The exec was blocked by the sandbox and crashed the bundled sidecar at startup before serving a single byte. Linux unchanged (no sandbox blocker; keeps the `/bin/ps` fallback). Third libproc swap in the family (`proc_pidpath`, `proc_listpids`+`proc_pidfdinfo`, now `proc_pidinfo`)
- **Sidecar: serve React bundle via in-memory `read_bytes` under macOS App Sandbox** — Starlette's `StaticFiles` (FastAPI mount path) opens files with `mmap`, which the App Sandbox can reject for bundled assets read from inside the `.app`. The serve-mode static handler now reads the React bundle into memory and returns it directly, bypassing the mmap path. Linux/CLI users see no change (path-existence + size-cap guards keep the read bounded). New regression coverage in `tests/test_static_serving.py`
- **Desktop: i18n sweep — LLM helpers, transcription settings, build-info, default project name** — extracted hardcoded English literals missed by earlier passes: `LLMProvider.swift` activation toggle, status labels, console-link labels, Ollama description; `TranscriptionSettingsView` Backend / Model / Auto / hint / model-recommended interpolated label; `BuildInfoSheet` Close button; default "New Project" name. All six locale `desktop.json` files updated (en/es/fr/de/ko/ja)
- **Desktop: delegate locale to System Settings** — removed the in-app language picker on macOS. Locale selection now flows through System Settings → Apps → Bristlenose, matching the macOS norm. `I18n.swift` reads `Bundle.preferredLocalizations` on every launch (Apple's BCP 47 matcher); `INFOPLIST_KEY_UIPrefersShowingLanguageSettings=YES` ensures the per-app language section is visible even for users with a single preferred language. Web/CLI serve picker unchanged. See `docs/design-locale-negotiation.md`

**0.15.3** — _4 May 2026_

- **Desktop: provider-switching hardening end-to-end** — the "Change provider" flow now actually activates the new provider across Keychain, sidecar env injection, and UI. Four fixes landed together: Ollama choice persists to `UserDefaults` *before* the consent log writes (defeats a race where a crash between the two left the app in an inconsistent state); the Change-provider button activates the row first then falls back to a selector if activation didn't take; sidecar API-key injection is scoped to the active provider only (was leaking other providers' keys into the child env); LLM Settings lazy-loads Keychain reads to the selected row only (was prompting on every row render). Desktop-only — no PyPI surface change
- **Prompt-injection sentinel-tag boundary (Phase A)** — adds a defence-in-depth boundary against prompt-injection attempts hidden in interview transcripts. Sentinel tags wrap the user-supplied content so the LLM can structurally distinguish data from instructions. Phase A is the boundary itself; later phases will tighten the prompt contract around it
- **Sidecar bundle trim (S1 + S2 + S3)** — three rounds of PyInstaller bundle slimming: S1 excluded `mlx_whisper.torch_whisper` from the bundle (PyTorch was being pulled in transitively); S2 introduced a dedicated build venv so the bundle no longer carries the contributor's full `.venv` graph; S3 evicted `torch` and `onnxruntime` and switched mlx-whisper packaging to `collect_all` so its `assets/` ship correctly. Net: significantly smaller sidecar, faster TestFlight uploads
- **Doctor: `mlx-whisper` recognised as a complete backend on Apple Silicon** — `bristlenose doctor` no longer reports a missing whisper backend on Apple Silicon when only `mlx-whisper` is installed (the bundled-sidecar configuration). Other platforms unchanged
- **Desktop: log-tail trust on sidecar exit-1-after-success** — when the sidecar exits with code 1 after a successful pipeline run (rare but observed during sandbox shutdown), the desktop app now trusts the log tail rather than misclassifying the run as failed
- **Desktop: sandbox-on Debug i18n + resizable window** — Debug builds with the App Sandbox entitlement enabled now load locales correctly and the window resizes properly on macOS Tahoe (was locking vertical resize)
- **Frontend dependency updates** — minor/patch bumps to `i18next`, `react-router-dom`, `eslint`, `eslint-plugin-react-hooks`, `typescript`, `typescript-eslint`, `vite`, `vitest` (#91); `react-i18next` 16.6.6 → 17.0.6 (#90). The v17 breaking change in `transKeepBasicHtmlNodesFor` doesn't apply — no usage in this codebase
- **Test: relax `maxHeight` assertion for jsdom 29 compatibility** — jsdom 29 normalises `style.maxHeight = "0"` to `"0px"` on read-back (matching real browsers); the previous `toBe("0")` assertion in `AnalysisPage.test.tsx` was leaning on jsdom 27's non-spec echo-the-input behaviour. Switched to `toMatch(/^0(px)?$/)` so the assertion passes on both versions, unblocking the upcoming jsdom 27 → 29 dependabot bump (#89, pending)
- **Tooling**: `/new-feature` skill grew optional flags for self-contained branch handoff (handoff doc + invocation in one paste-able command)

**0.15.2** — _2 May 2026_

- **Bundled FFmpeg/ffprobe discovery for sandboxed sidecar** — new `bristlenose/utils/bundled_binary.py` resolves FFmpeg and ffprobe from a bundle-relative path before falling back to `$PATH`. Lets the sandboxed desktop sidecar find ship-with-app binaries that aren't on the user's shell `PATH`. `audio.py`, `video.py`, and `clip_backend.py` route through the helper; `bristlenose doctor` reports the resolved path. CLI/PyPI users see no behaviour change — `$PATH` lookup is still tried
- **`bristlenose/server/lifecycle.py`** — new module factoring out serve-mode lifecycle handling (parent-death detection, sandbox-friendly bind(0), graceful shutdown). Used by Track A A6 sandbox-native sidecar work; CLI `serve` callers get the same lifecycle path
- **PipelineRunner: `SidecarMode.resolve` migration** (PR #96) — desktop sidecar invocation goes through the resolved-mode path, with logged mode + clearer error copy when the resolution fails
- **TLS sidecar redirect to certifi under sandbox** (PR #97) — bundled sidecar uses `certifi` for TLS root certs when the system trust store isn't reachable from inside the App Sandbox. Desktop-only impact
- **Frontend size budget**: re-baselined to live-SPA gzipped (lazy locales excluded from the budget figure since they're loaded on demand). Budget remains 320 kB
- **Docs**: manual + README reconciled with shipped bundled-binary-helper; pricing reframed per hour of audio rather than per study; HANDOFF.md branch-handoff convention surfaced at worktree root via gitignored symlink

**0.15.1** — _1 May 2026_

- **Desktop alpha-readiness landed (Sprint 2 Track C C2–C5)** — sandbox-safe API-key injection (Swift Keychain → env vars; Python no longer execs `/usr/bin/security`), libproc-based zombie cleanup (`proc_listpids` + `proc_pidfdinfo` + `proc_pidpath` — replaces `lsof` and `/bin/ps`, both blocked by App Sandbox), `os.Logger` with privacy redaction throughout `ServeManager`, key-shape stdout redactor (Anthropic / OpenAI / Google formats) as defence-in-depth against accidental key leakage in subprocess output, `SidecarMode.resolve` + three Xcode schemes for the dev escape hatch, privacy manifests for host + sidecar (TestFlight unblock), per-binary signing infrastructure, supply-chain provenance (`THIRD-PARTY-BINARIES.md` + auto-regen script). Desktop-only — no PyPI surface change
- **Desktop first-run experience (Sprint 2 Track B Branch 1)** — `BootView` unified boot/loading/failed surface, `WelcomeView` two-variant pattern (`.firstRun` + `.noSelection`), Beat 3 round-trip API key validation in `LLMSettingsView`, Beat 3b `OllamaSetupSheet` state machine (idle / installingOllama / waitingForDaemon / downloadingModel / finishing / failed) for local AI install, `I18n.findLocalesDirectory()` worktree-aware `#filePath` derivation, `boot.*` and `welcome.*` translation blocks added to all 6 desktop locale files (English drafts; native review owed for es/fr/de/ko/ja). Desktop-only
- **`bristlenose serve` fall-back to bundled theme CSS** — projects that have never run the pipeline have no per-project rendered CSS at `<output_dir>/assets/`. The SPA's stylesheet link would 404 and the entire UI rendered as raw HTML inside the WKWebView. Server now registers a typed CSS route that prefers per-project CSS if it exists and falls back to the bundled theme otherwise
- **`bristlenose doctor --self-test`** — new flag that verifies sidecar bundle integrity (spec → bundle file presence). Catches the "data files declared in `.spec` but missing from the built bundle" class of bug. Runs in `desktop/scripts/build-all.sh` step 2a
- **`bristlenose serve` fail-loud on missing React bundle** — returns a "Build incomplete" 500 page instead of silently falling back to the static render. The static render is officially vestigial scaffolding now, not a fallback
- **Japanese (`ja`) locale completion** — bulk-translated ~614 stub strings across 8 namespace files in `bristlenose/locales/ja/`, seeded `glossary.csv` with 83 `ja` rows. Alpha gate cleared
- **i18n: tag sidebar** — extracted hardcoded strings, added 11 keys across all 6 locales

**0.15.0** — _26 Apr 2026_

- **Pipeline resilience: Phase 1f / 4a-pre — run-level event log + honest run state** — pipelines now write a single-source append-only `pipeline-events.jsonl` recording how each run ended (started / completed / cancelled / failed) with a structured `Cause` object capturing category, code, message, provider, stage, signal. Replaces the inference path the desktop app previously used (which mis-classified interrupted runs as `.ready`). Survives crashes, recovers cleanly from torn writes, refuses concurrent runs against the same project. See `docs/design-pipeline-resilience.md` §"Run outcomes and intent"
- **Structured failure causes** — exceptions categorised into 10 cases: `auth` / `network` / `quota` / `disk` / `whisper` / `unknown` (existing) plus `user_signal` / `api_request` / `api_server` / `missing_dep` (new). Same case names on Python and Swift sides for lossless JSON round-trip; word-boundary regex matchers anchor the categoriser to avoid false positives (e.g. `"credit"` no longer matches `"credentials"`)
- **Cost as honest estimate** — pipelines now stamp `cost_usd_estimate` + `price_table_version` + `input_tokens` + `output_tokens` onto every terminus event. UI surfaces via `format_cost_estimate()` as `"~$0.46 (est.)"` — never bare dollars. Token counts are real (provider returns them); USD is best-effort. `SessionRecord` extended additively with the same fields
- **Python-side PID file with start-time check** — `<output>/.bristlenose/run.pid` containing `(pid, start_time, run_id)` for cross-process liveness. Defeats PID reuse on busy macOS; mode 0o600 + `O_NOFOLLOW`. Lives inside the project folder so App Sandbox doesn't need extra entitlements
- **Stranded-run reconciliation** — if a prior run died mid-flight (kill -9, OOM, hard reboot), the next `bristlenose run` notices the stranded `run_started` event and synthesises a `run_failed` for it before starting a new run. Honest fallback: cause is `unknown`, message is "Analysis stopped unexpectedly."
- **Desktop: `EventLogReader.deriveState`** — Swift consumer of the events log. New `PipelineState` cases `.partial(kind, stagesComplete)` (transcribe-only completed) and `.stopped(stagesComplete)` (user cancelled) join the existing set. UI verb wiring (Resume / Retry / Re-analyse…) deferred to a separate desktop UX iteration
- **Desktop: `BristlenoseTests` target wired up** — `xcodebuild test` now runs 90 Swift tests (Tab, I18n, LLMProvider, KeychainHelper, ProjectIndex, plus new `EventLogReaderTests`). Pre-existing test files marked `@MainActor` at suite level to satisfy Swift 6 strict concurrency
- **Test totals**: 2328 Python (4 new test files, 80 new tests) + 90 Swift, all green

**0.14.6** — _18 Apr 2026_

- **CI: e2e gate re-enabled as a blocking check** — cleared the three P3 items parked during v0.14.5. Autocode-status 404 allowlisted in `e2e/tests/network.spec.ts` (kept REST semantics; frontend at `CodebookPanel.tsx:609` already null-tolerant). Codebook-route console subresource 404 allowlisted in `e2e/tests/console.spec.ts` with a `TODO(S3)` pointer; root-cause fix deferred to the next frontend sprint. `_BRISTLENOSE_AUTH_TOKEN=test-token` wired into the main e2e workflow step so Node-side fetches can authenticate
- **Fix: Analysis page "Show all N quotes" toggle** — the expand/collapse toggle on signal cards was rendered as an `<a>` without `href`, which fails a11y (not keyboard-focusable) and trips link validators. Converted to a proper `<button type="button">` with minimal CSS reset in `analysis.css`. Discovered during the e2e gate-flip verification on this branch
- **Fix: Playwright config shell-quotes** — `playwright.config.ts` interpolated `${BRISTLENOSE}` and `${FIXTURE_DIR}` unquoted, so worktree paths with spaces (like `bristlenose_branch ci-cleanup`) broke the webServer launch. Paths now quoted. Pre-existing bug, surfaced by the branch naming convention
- **Security docs: `SECURITY.md` corrected** — prior text claimed the auth token was "random at startup" and "memory only" unconditionally. Reality: `_BRISTLENOSE_AUTH_TOKEN` in the process environment overrides the random token (required for CI fixtures and for uvicorn `--reload` session continuity across code saves). Spec updated to describe the actual behaviour; a future hardening task will gate the override behind `BRISTLENOSE_DEV_MODE=test`
- **Doctor: new `Auth token` check** — `bristlenose doctor` now warns if `_BRISTLENOSE_AUTH_TOKEN` is set in the shell environment. Helps catch accidental bleed from a previous CI run or dotfile that would otherwise silently pin the serve token
- **CI: allowlist register** — every deliberate suppression in the Playwright e2e gate now has an entry in `e2e/ALLOWLIST.md` and a `// ci-allowlist: CI-A<N>` marker in code. Three categories: `infra` (stack artefact, never fixable), `by-design` (intentional correct behaviour), `deferred-fix` (real bug with tracker link). Prevents silent accumulation of "we ignored that failure because" in the gate. Validator script + staleness gate deferred until ~10 entries

**0.14.5** — _17 Apr 2026_

- **CI: unblock release pipeline** — v0.14.0–v0.14.4 releases all failed in CI for three independent reasons that had compounded since early April. No user-facing changes; cutting this release to prove the pipeline is green end-to-end before resuming normal feature work
- **Fix: `eslint-plugin-react-hooks` peer-dep mismatch** — 7.0.1 capped the eslint peer at major 9, but the project ships eslint 10. `npm install` (local) is permissive; `npm ci` (CI) is strict and rejected it. Bumped to 7.1.0 which accepts eslint 10
- **Fix: pin `jsdom` to 27.x** — a dependabot auto-merge bumped jsdom 27 → 29, which stopped shimming Web Storage API methods. Combined with Node 25, 140+ frontend tests failed at `localStorage.*`. Reverted; reattempt once jsdom 29 + Node interaction has a proper polyfill
- **Fix: stale Vitest mocks after `api.ts` and i18n changes** — `useKeyboardShortcuts.test.ts` missed `apiGet` in its `vi.mock` factory (PlayerProvider now imports it); `CodebookSidebar.test.tsx` asserted on a raw template title that the component now passes through `t("codebook.sentimentTitle")`. Both updated
- **Fix: e2e install** — `e2e/package-lock.json` regenerated after `lighthouse` was added to `e2e/package.json` without running `npm install`. Same `npm install` vs `npm ci` divergence pattern as the eslint peer-dep issue
- **CI: exclude `perf-stress.spec.ts`** from default Playwright discovery. The spec has a CI guard that refuses runs under the default `trace: 'on-first-retry'` config; it runs via the dedicated `playwright.stress.config.ts` instead
- **CI: e2e gate temporarily informational** — three P3 e2e findings (console subresource 404 on `/report/codebook/`, noisy autocode status 404 when no job exists, perf-gate auth-token env wiring) parked to sprint 2. Re-enable the e2e gate once all three clear

**0.14.4** — _16 Apr 2026_

- **Pipeline resilience: input change detection** — phase 2c of pipeline resilience. Detects when input files have been added, removed, or modified between runs. Stale sessions are quarantined and the affected stages re-run automatically. SHA-256 content hashing with size-based short-circuit for large files
- **Alembic migration infrastructure** — replaced manual `_migrate_schema()` with Alembic for schema migrations. Existing databases auto-stamp to the baseline revision on first serve. New migrations go in `bristlenose/server/migrations/`
- **CI: multi-python matrix** — test suite now runs against Python 3.10, 3.11, 3.12, and 3.13. Lint job split from test jobs for faster feedback

**0.14.3** — _27 Mar 2026_

- **Export: video clip extraction** — starred and featured quotes extracted as trimmed video clips via FFmpeg stream-copy. Human-readable filenames (`p1 03m45 Sarah onboarding was confusing.mp4`), adjacent merge, async progress toast, `clips_manifest.json` audit trail. Two-backend architecture (FFmpeg now, AVFoundation future) with `ClipBackend` Protocol. 64 new Python tests
- **Fix: video player 401** — `<video>` elements can't send Authorization headers; `/media/` routes exempted from bearer token middleware. Also fixed `PlayerContext.tsx` and `Minimap.tsx` using raw `fetch()` instead of `apiGet()`
- **Fix: `safe_filename()` path traversal** — single-pass `..` removal could reassemble from `"..../"`. Now uses `while` loop
- **Refactor: `pick_featured_quotes()`** — moved from `dashboard.py` to `export_core.py` for shared use by dashboard and clip extraction

**0.14.2** — _24 Mar 2026_

- **Localhost bearer token** — defence-in-depth API access control for serve mode. Per-session `secrets.token_urlsafe(32)` validated via Starlette middleware on `/api/*` routes. Token injected into SPA HTML and desktop app WKWebView
- **Fix: TOC sidebar empty** — left-hand contents navigation on the Quotes tab was broken by the auth middleware (raw `fetch()` lacked the bearer token). Switched to `apiGet()` helper

**0.14.1** — _24 Mar 2026_

- **French, German, Korean locales** — machine-translated all 8 namespace files (common, settings, enums, cli, pipeline, server, doctor, desktop) for fr, de, ko. Cross-checked against Apple macOS glossaries and ATLAS.ti/MAXQDA research terminology. Native reviewer docs added for German and French
- **Contextual left-panel labels** — desktop app toolbar and View menu items now show tab-specific labels (Contents on Quotes, Codes on Codebook, Signals on Analysis) instead of generic "Navigation". View menu items renamed from "Toggle X" to "Show X" per Apple HIG
- **Tags sidebar shortcut** — `⌘⌥T` toggles the tag sidebar in the desktop app
- **Keyboard shortcuts design doc** — full inventory of desktop app shortcuts with conflict matrix

**0.14.0** — _20 Mar 2026_

- **Inspector panel** — DevTools-style collapsible bottom panel in the Analysis tab. Heatmap matrices (section × sentiment, theme × sentiment, codebook group) live in a resizable pane that opens via click, drag-up, or the `m` keyboard shortcut. Signal card selection (blue wash) syncs bidirectionally with inspector source tabs — click a card to drill into its matrix, click a tab to highlight its card. Drag-from-collapsed grows the panel smoothly from the 28px handle bar. Tooltip repositioning flips above when near viewport bottom. Footer auto-hides to maximise matrix space. New files: `InspectorPanel.tsx`, `InspectorStore.ts`, `useVerticalDragResize.ts`, `inspector.css`. 4 feature commits, 696 new test assertions
- **Codebook sidebar** — left-hand navigation panel now available on every tab, not just Quotes. The TOC sidebar becomes a codebook-tree sidebar showing tag groups, counts, and micro-bars for the current view. Tabs without a right sidebar get a symmetric spacer rail so the center column stays balanced. Inert rail layout ensures non-sidebar tabs render cleanly without sidebar state leaking
- **Finding flags on signal cards** — each sentiment-based signal card carries an optional finding flag (Win, Problem, Niggle, Success, Surprising, or Pattern) classifying the signal's direction and weight. Flags are computed from sentiment valence, participant breadth, and intensity. Conservative thresholds mean cards that don't clear the bar stay unflagged. Four tunable thresholds ready for calibration via a future dev-mode HUD. Two-tone micro-bars visualise signal composition. Flows through all three output paths: static render, sentiment API, and tag API. 27 new tests. Design exploration: `docs/design-finding-weight.md`
- **Settings modal** — gear-icon / `⌘,` modal with sidebar navigation shell (ModalNav organism). Reusable across modals — Settings and Help share the same `ModalNav` component with their own sizing classes
- **Help modal** — replaces the About page route and keyboard shortcut overlay with a sidebar-nav modal. Seven sections: Help, Shortcuts (keyboard grid with platform-aware badges), Signals, Codebook, and About group (Developer, Design, Contributing). Triggered by ⓘ navbar icon or `?` key. `/report/about/` URL gracefully redirects to `/report/`
- **About tab section components** — modular React components for each About section (AboutSection, CodebookSection, ContributingSection, DesignSection, DeveloperSection, SignalsSection). Worktree launch paths fixed for serve mode
- **Activity chips persist across tab navigation** — AutoCode progress toasts survive React Router navigation via a new `ActivityStore`. Action link uses real `href` for Cmd+click, label changed to "View Analysis", hidden when already on Analysis tab
- **New framework codebooks** — Nielsen's 10 Usability Heuristics and Yablonski's Laws of UX join the built-in codebook library. Import either via Codebook → Add Framework
- **Fix: sidebar not showing on codebook tab** when URL had a trailing slash
- **Fix: codebook grid fills available width** — removed max-width cap that left empty space on wide screens
- **Fix: autocode toast** — "View Report" link now opens the threshold review modal instead of always being visible; toast auto-dismisses on click

**0.13.7** — _16 Mar 2026_

- **Spanish locale** — machine-translated all 102 UI strings across 8 locale files (3 frontend, 5 backend). Covers navigation, settings, enums, CLI messages, doctor, pipeline progress, and server errors. Ready for native-speaker review and polish

**0.13.6** — _16 Mar 2026_

- **Single tag focus mode** — click a tag count in the sidebar to solo that tag (mixing-desk style). All other sidebar controls dim to 50%; the focused tag row stays at full brightness. "You are here" blue wash highlight matches the TOC sidebar's active link style. Click again or press Escape to exit and restore the previous tag filter
- **Fix circular dependency crash** — `SidebarStore` importing `setTagFilter` from `QuotesContext` at module scope created a circular dependency that caused "Cannot access uninitialized variable" in production builds. Refactored to pass `setTagFilter` as a callback parameter
- **Used/unused tag filter toggle** — "Used" link in tag sidebar header filters to show only tags that appear on at least one quote, hiding zero-count tags for a cleaner view
- **Sidebar tag click-to-assign** — select quotes then click a tag badge in the sidebar to apply that tag to all selected quotes. Flash animation on each newly tagged quote, toast notification when tagged quotes are off-screen
- **Tier 1 logging instrumentation** — persistent log file with stage-level timing, session counts, and LLM token usage. PII hardening: file paths, API keys, and participant names are scrubbed from log output
- **Multilingual UI infrastructure** — i18next integration with `useTranslation` hook, Python i18n module, browser language auto-detection on first visit. Translation keys for all user-facing strings (not yet translated)
- **Responsive signal cards** — signal framework cards use CSS grid layout with narrow-screen stacking for readable display on mobile viewports
- **Cache `system_profiler` results** — 24-hour TTL cache for macOS `system_profiler` output, avoiding the slow 2-3s startup penalty on every `bristlenose doctor` or `bristlenose run`

**0.13.4** — _14 Mar 2026_

- **Fix import FK constraint** — delete `ProposedTag` rows (AutoCode proposals) before removing stale quotes during re-import, preventing `FOREIGN KEY constraint failed` errors on `bristlenose serve` startup

**0.13.3** — _14 Mar 2026_

- **Help modal polish** — platform-aware keyboard shortcuts (⌘ on Mac, Ctrl on Windows/Linux), sans-serif keycaps with deeper shadow and min-width for visual consistency, typography tokens and spacing overhaul, entrance animation, dark-mode keyboard styling. Phase 3 adds custom tooltips with keyboard shortcut badges across the UI
- **Bulk actions on multi-selection** — star, hide, and tag operations now respect click-based multi-selection: clicking a starred quote in a selection unstars all, clicking an unstarred one stars all. Shift+click range selection no longer triggers browser text selection. Tag commits apply to all selected quotes
- **Sidebar animations** — push animation on keyboard shortcuts (`[`, `]`, `\`) and click, 4× faster open/close transitions, two-row header layout. Rail drag-to-open with 60px commit threshold and pointer-tracking overlay. Drag handle hover-intent (80ms delay) filters casual mouse traversal
- **TOC overlay clip-path animation** — smooth reveal/hide for the table-of-contents overlay panel, with playground toggle for overlay style
- **Scroll spy Safari fix** — two-phase click-intent override (immune phase 0–600ms, sticky phase >600ms) resolves Safari's smooth-scroll `getBoundingClientRect()` timing glitch. Minimap reordered to grid column 4 (between center and tag sidebar)
- **Pipeline error display** — failed stages show red ✗, partially successful stages show yellow ⚠ in CLI output
- **Speaker badge fix** — correct indent when speaker badge wraps to a new line
- **Scroll-margin fix** — section headings in React SPA now scroll to the correct position, accounting for the sticky navbar
- **CLAUDE.md refactor** — extracted frontend, pipeline, and LLM gotchas into dedicated child files (`frontend/CLAUDE.md`, `bristlenose/stages/CLAUDE.md`, `bristlenose/llm/CLAUDE.md`), keeping the root file focused on architecture and conventions

**0.13.2** — _11 Mar 2026_

- **Render refactor** — broke up the 2,903-line `render_html.py` monolith into `bristlenose/stages/s12_render/` package with 8 focused submodules: `theme_assets.py` (CSS/JS loaders, Jinja2 env), `html_helpers.py` (escaping, timecodes, badges, video map), `quote_format.py` (quote HTML, badges), `sentiment.py` (sparklines, rewatch/friction), `dashboard.py` (project tab, featured quotes, coverage), `transcript_pages.py` (standalone + inline transcripts), `standalone_pages.py` (codebook, analysis), `report.py` (orchestrator). No behaviour change — same HTML output, all 1,872 tests pass
- **Static render deprecated** — `render_html()` now emits `DeprecationWarning`. `bristlenose serve` is the canonical path; `bristlenose render` still works but is frozen
- Updated ~99 documentation references across 34 files to point to the new submodules

**0.13.1** — _10 Mar 2026_

- **Responsive layout playground** — dev-only responsive design tool (`--dev` mode) with device presets, type scale previews, and a HUD overlay for testing quote grid layouts across breakpoints. FAB toggle button, `PlaygroundStore` with `useSyncExternalStore`
- **Sidebar TOC overlay mode** — left sidebar TOC switches to hover-triggered overlay on narrower viewports. `useTocOverlay` hook manages open/close transitions with mouse-enter/leave
- **Minimap component** — document minimap for the quotes page, showing a scaled overview of quote sections with viewport indicator
- **Responsive quote grid CSS** — CSS-only responsive grid for quote cards, adapting column count to available width

**0.13.0** — _10 Mar 2026_

- **Codebook-aware tag autocomplete** — TagInput now groups suggestions by codebook section with colour-coded pills and section headers, matching the IDE-style autocomplete pattern. Highlighted suggestion takes priority over ghost text. Active pill uses white text, z-index fix prevents clipping under sidebar, deeper dropdown accommodates more suggestions
- **Sentiment tags unified into codebook framework** — sentiment tags (positive, negative, neutral, mixed) are now a proper codebook framework (`sentiment.yaml`) imported through the standard codebook system, replacing the ad-hoc UXR sentiment group. Tag colours use the design-system colour sets. Importer handles migration of existing sentiment tags to the new framework
- **Tag provenance tracking** — `QuoteTag.source` column tracks `"human"` (manual adds) vs `"autocode"` (LLM-suggested). Provenance is preserved across bulk tag operations (snapshot before delete, restore on re-insert). Exposed in the quotes API via `TagResponse.source`. Case-insensitive duplicate guard prevents adding the same tag twice
- **Hidden-group tag UX** — eye-toggled codebook groups show a grey closed-eye icon in TagInput autocomplete. Accepting a tag from a hidden group auto-unhides the group so the badge is immediately visible. `allTagNames` prop prevents invisible re-adds from hidden groups
- **Quick-repeat tag shortcut** (`r`) — press `r` on a focused quote to re-apply the last-used tag without opening the tag input. Shown in help modal
- **Context expansion fix** — fixed infinite re-render loop when clicking the up chevron to expand context on a quote card. `FocusContext` and `QuotesContext` updated to break the render cycle
- **Doctor offers MLX install on Apple Silicon** — `bristlenose doctor` now detects Apple Silicon Macs without MLX and offers interactive installation for GPU-accelerated transcription. Install helpers use `sys.executable` to target the correct Python. Skipped in non-interactive contexts
- **Sidebar UX accessibility** — focus management, ARIA attributes, and `prefers-reduced-motion` support for sidebar drag-resize animations
- **Dashboard Cmd+click fix** — stat cards now use `<a>` elements with real `href` attributes, so Cmd+click opens in a new tab as expected. Normal clicks still use React Router navigation

**0.12.2** — _2 Mar 2026_

- **Footer feedback restored in React serve mode** — the footer once again exposes both "Report a bug" and "Feedback" in the served React app. "Feedback" now opens a React-native modal (sentiment picker + optional message), matching the legacy flow rather than reusing the keyboard-shortcuts help modal
- **Feedback submit + fallback parity** — feedback sends `{version, rating, message}` JSON to the configured feedback endpoint when available over HTTP(S). On failure (or non-HTTP contexts), it falls back to copying a plain-text feedback payload to the clipboard and shows toast guidance
- **Health API contract extended** — `GET /api/health` now returns `links.github_issues_url` and `feedback.{enabled,url}` alongside existing `status` and `version` keys (unchanged)
- **Export parity with serve mode** — exported reports embed the same `health.links` + `health.feedback` shape so footer behavior is consistent between serve and export
- **Config via environment variables** — optional server-side overrides: `BRISTLENOSE_GITHUB_ISSUES_URL`, `BRISTLENOSE_FEEDBACK_ENABLED`, `BRISTLENOSE_FEEDBACK_URL`

**0.12.1** — _1 Mar 2026_

- **Word-level transcript highlighting** — during video playback, individual words in the transcript highlight in sync with the audio, karaoke-style. Whisper captures per-word start/end timestamps during transcription; these flow through the pipeline (`session_segments.json` → SQLite `words_json` → transcript API `words` field) and render as `<span class="transcript-word">` elements with `data-start`/`data-end` attributes. `PlayerContext.updateGlow()` scans word spans at 4 Hz and toggles `.bn-word-active` on the current word. Three-tier rendering fallback: word spans (Whisper sessions) → `html_text` with `<mark>` quote highlighting (non-Whisper with quotes) → plain text. CSS uses `color-mix(in srgb, accent 30%, transparent)` with `prefers-reduced-motion` underline fallback. VTT/SRT-imported sessions gracefully degrade to segment-level glow only. Glow brightness rebalanced: paragraph glow dimmed 50%, word glow brightened 50% — the active word pops against a subtler segment background
- Design doc: `docs/design-word-highlighting.md` — pipeline diagram, data flow, frontend architecture

**0.12.0** — _1 Mar 2026_

- **Dual sidebar for Quotes tab** — left sidebar: table of contents with scroll-spy (sections + themes, active heading highlights on scroll). Right sidebar: tag filter with codebook tree, eye toggles for badge hiding (persisted to localStorage). 5-column CSS grid (`rail | sidebar | center | sidebar | rail`), drag-to-resize with snap-close thresholds, keyboard shortcuts (`[` left, `]` right, `\` both, `⌘.` tag sidebar). Quotes-tab-only — other tabs see no grid or rails. New components: `SidebarLayout`, `TocSidebar`, `TagSidebar`, `TagGroupCard`, `TagRow`, `EyeToggle`. New hooks: `useDragResize`, `useScrollSpy`. Module-level `SidebarStore` with `useSyncExternalStore`. Backend: tag-group-with-quotes API endpoint, admin panel registration. 845 Vitest tests (60 files), 1856 Python tests
- **Frontend CI** — ESLint, TypeScript typecheck, and Vitest added to GitHub Actions (`frontend-lint-type-test` job on Node 20). ESLint step informational pending fix of 84 pre-existing errors

**0.11.2** — _1 Mar 2026_

- **Self-contained HTML export** — download button in the NavBar bundles all API data as embedded JSON, blob-URL'd JS chunks, and a hash router for `file://` — recipients open the report in any browser without Bristlenose installed. Optional anonymisation checkbox strips participant names before download. Read-only CSS + JS guards hide mutation UI in exported files. 26 Python tests, 20 frontend tests
- **About panel redesign** — sidebar layout (Claude-settings style) with 5 sections: About (per-screen product guide), Signals (sentiment taxonomy, concentration metrics, academic references), Codebook (sections/themes, sentiment tags, framework codebooks with author refs), Developer (architecture, stack, APIs, contributing), Design (design system, dark mode, component library, typography)
- **Configuration reference panel** — read-only grid in Settings tab showing all 63 configurable values across 12 categories with defaults, file badges, clickable env var names (copy to clipboard), and valid options
- **Morville honeycomb codebook** — Peter Morville's User Experience Honeycomb: 7 groups (useful, usable, desirable, findable, accessible, credible, valuable), 28 tags with discrimination prompts and cross-codebook references. Codebooks now sorted by browse order via `sort_order` field

**0.11.1** — _28 Feb 2026_

- **Fix video player** — double URL encoding broke playback for files with spaces (`%20` → `%2520`). Removed Python-side `_url_quote()` from `_file_to_media_uri()`; JS `encodeURIComponent()` now handles encoding once. Also fixed subdirectory loss: `merge_transcript.py` now stores relative paths (e.g. `interviews/show and tell 40.mov`) instead of just the filename

**0.11.0** — _28 Feb 2026_

- **Full React SPA in serve mode** — React Router (`react-router-dom` v7) replaces vanilla JS hash-based tab navigation. Single `RouterProvider` root with pathname routes (`/report/`, `/report/quotes/`, `/report/sessions/:id`, etc.). `AppLayout` wraps `NavBar` + `Outlet`. 8 page wrappers compose existing island components. Backward-compat shims (`window.switchToTab`, `window.navigateToSession`) delegate to React Router for any remaining callers
- **Player integration** — `PlayerContext` manages popout video player lifecycle, `seekTo(pid, seconds)`, glow sync via DOM class manipulation (not React state). `buildGlowIndex` keys by session ID from URL pathname. Progress bar via `--bn-segment-progress` CSS custom property. `player.js` bails out in SPA mode
- **Keyboard shortcuts** — `FocusContext` + `useKeyboardShortcuts` hook. j/k navigation, multi-select (Shift+j/k, x), bulk star/hide/tag, `?` help modal, `/` focus search, Escape cascade (modal → search → selection → focus). Data-derived visible quote IDs replace DOM queries
- **React app shell** — `Header` (logo, project name, subtitle), `Footer` (version, `?` for Help), `HelpModal` (keyboard shortcuts overlay). Serve mode serves Vite-built SPA directly — no more `_transform_report_html()` marker substitution. Route extraction: `app.py` refactored to route modules
- **Vanilla JS retired from serve path** — `_strip_vanilla_js()` removes all 26 modules from the IIFE while keeping `window.*` globals (`BRISTLENOSE_VIDEO_MAP`, `BRISTLENOSE_PLAYER_URL`, `BRISTLENOSE_ANALYSIS`). Static render path unchanged
- Video player links on sessions page and dashboard open the popout player
- Importer finds source files in one-level subdirectories (mirrors ingest scan pattern), fixing video 404s when files are in `interviews/`
- Speaker display names in sessions grid use normal font size (matching date/duration columns)
- Word-level timing data plumbed through pipeline to transcript API (`words` field on segments)

**0.10.3** — _21 Feb 2026_

- `bristlenose status` command — read-only project status from the manifest, shows stage completion with session counts, intermediate file validation, and `-v` per-session detail
- Pre-run resume summary — one-line status message before pipeline output when resuming an interrupted run (e.g. "Resuming: 7/10 sessions have quotes, 3 remaining.")
- Split speaker badges — two-tone pill with speaker code (left, mono) and participant name (right, body font). Settings toggle: "Show participants as: Code and name / Code only", persisted in localStorage. Applied across all surfaces: quote cards, session table, dashboard, transcript pages, user journeys, friction points
- Em-dash removed from quote attribution — replaced with `margin-left: 1rem` gap between quote text and speaker badge
- Always-on sticky transcript header — session selector dropdown always visible on transcript pages (not gated on journey data). Single-session pages show a plain label as page title
- Serve-mode session routing — session links now navigate to standalone transcript pages (React island) instead of inline Jinja2 drill-down. Inline Jinja2 transcript pages and vanilla JS subnav stripped in serve mode
- AutoCode frontend — complete lifecycle for LLM-assisted tag application: ✦ button on framework codebook sections triggers AutoCode run, progress toast with 2s polling and cancel support, threshold review dialog with confidence histogram and dual-threshold slider (accept/tentative/exclude zones), per-row override, proposed badges on quotes (pulsating dashed border, hover accept/deny with brightness flash animation). Tag colour pipeline carries `colour_set` + `colour_index` from CodebookGroup through to accepted user tags
- Threshold review dialog — confidence-aware triage: 20-bin histogram with tag colours, three proposal zones, bulk accept/deny with max_confidence filter, per-quote override before committing
- Activity chip and chip stack components — lightweight status indicators for background jobs with multi-stage progress, cancel button, and auto-dismiss on completion
- Transcript page improvements — greedy slot layout for annotation span bars (no overlapping when multiple quotes span the same region), suppress repeated label+sentiment annotations (show only on topic change), speaker badges use `bn-person-badge` styling consistent with sessions table
- Journey chain: full sequence with revisits — transcript sticky header now shows the complete user journey including revisited sections (e.g. Cat Nav → Prod List → Cat Nav → Checkout), not the deduplicated summary. Index-based tracking distinguishes repeated labels — clicking the second "Cat Nav" jumps to the second occurrence, scrolling highlights only the current one. Sessions table retains deduplicated labels unchanged
- Journey label active state — new `journey-label` CSS atom with `--bn-colour-hover` pill background on the active step, extracted from transcript styles into the atomic design system. Fixed CSS specificity bug where `all: unset` on buttons suppressed the active background
- Resilient transcript discovery — serve-mode importer now searches four locations in priority order (cooked → raw/output → raw/project → transcripts/project) instead of only `transcripts-raw/`, fixing empty transcript pages when pointing serve at non-standard output layouts
- Generic analysis matrix and signals — reusable computation engine for cross-tabulating any labelled data (not just quotes), with API routes for serve mode
- Man page and docs updated for `status` and `serve` commands
- Fix: serve-mode navigation escape — transcript page back link pointed to `/report/{filename}.html` (raw static HTML without React islands) instead of `/report/` (serve-mode route with React injection). Clicking "← Research Report" from a transcript now stays in serve mode

**0.10.2** — _21 Feb 2026_

- Pipeline crash recovery — interrupted runs resume where they left off instead of starting over. Kill mid-analysis, re-run the same command, and only the unfinished sessions get LLM calls. Completed sessions are loaded from cache in milliseconds
- Per-session tracking for topic segmentation and quote extraction — the manifest records which sessions finished within each stage, so a crash after 7 of 10 sessions only re-processes the remaining 3. Cached + fresh results are merged transparently
- CLI resume guard — re-running into an existing output directory now detects the pipeline manifest and resumes automatically. No `--clean` needed, no "output directory already exists" error. `--clean` still available for full re-runs
- Pipeline resilience design doc — CS foundations research (build systems, event sourcing, WAL, CAS, sagas) and phased implementation plan for crash recovery, data integrity, and incremental re-runs

**0.10.1** — _19 Feb 2026_

- Desktop app API key onboarding — first-run setup screen prompts for Claude API key, stores in macOS Keychain via `security` CLI, sidecar picks it up automatically via `_populate_keys_from_keychain()`. Settings panel (⌘,) for viewing, changing, or deleting the key
- `.dmg` packaging — `build-dmg.sh` archives via xcodebuild with ad-hoc signing, packages with hdiutil (or `create-dmg` for drag-to-Applications). `build-all.sh` chains sidecar + ffmpeg + whisper + dmg into one command
- Serve mode after pipeline — desktop app auto-launches `bristlenose serve` after pipeline completes, opens report at `http://127.0.0.1:8150/report/` with full React islands
- Deployment target updated to macOS 15 Sequoia (was 14 Sonoma)
- Codebook tag templates — pre-built tag sets via new API endpoints and UI

**0.10.0** — _18 Feb 2026_

- Desktop app v0.1 — SwiftUI macOS launcher (`desktop/Bristlenose/`) with folder picker, drag-and-drop, pipeline output streaming, View Report in browser. 4-state UI (ready → selected → running → done), ANSI escape stripping, report path detection from both OSC 8 hyperlinks and `Report:` text fallback. Xcode 26 project, 840 KB .app, macOS 14+ deployment target
- ProcessRunner — `@MainActor` ObservableObject that spawns `Process()`, reads stdout via `Task.detached`, streams lines to SwiftUI, extracts report file path
- FolderValidator — scans directories recursively for processable file extensions (mirrors `models.py` extension lists)
- Back-to-folder navigation on Done screen — re-validates folder state for re-render/re-analyse without starting over

**0.9.4** — _17 Feb 2026_

- `bristlenose serve` command — FastAPI local dev server that serves the HTML report over HTTP with SQLite persistence, React islands, and live JS reload in dev mode. Auto-renders before serving, auto-opens browser, prints clickable report URL
- React islands architecture — 5 islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel) mount into static HTML via comment markers and `re.sub` at serve time; 16 reusable React primitives (Badge, PersonBadge, TimecodeLink, EditableText, Toggle, TagInput, Sparkline, Counter, Metric, JourneyChain, Annotation, Thumbnail, MicroBar, ConfirmDialog); 182 Vitest component tests
- Codebook CRUD — React island replaces vanilla JS codebook: drag-and-drop tags between groups, inline editing of group titles and subtitles, tag merge with confirmation, create/delete groups and tags, pentadic colour system, MicroBar frequency bars, ConfirmDialog for destructive actions. 9 API endpoints, 36 Python tests
- Dashboard island — Project tab as React composition: 8 clickable stat cards, compact sessions table, featured quotes with reshuffle, section/theme navigation with cross-tab anchor links. 43 API tests
- Data API — 6 fire-and-forget PUT endpoints sync researcher state (hidden, starred, tags, edits, people, deleted-badges) from localStorage to SQLite. 94 tests (37 happy-path + 57 stress)
- 22-table SQLAlchemy domain schema with instance-scoped people/codebook and project-scoped sessions/quotes/themes; `assigned_by` tracks pipeline vs researcher authorship; idempotent upsert importer
- Desktop app scaffold — SwiftUI macOS shell with folder picker, pipeline runner, sidecar architecture (self-contained in `desktop/`)
- Renderer overlay (dev-only, press **D**) — colour-codes report regions by origin: blue for Jinja2, green for React, amber for vanilla JS
- Visual diff page (dev-only) — side-by-side, overlay, and toggle comparison of Jinja2 vs React sessions table

**0.9.3** — _13 Feb 2026_

- Interactive dashboard — Project tab stat cards are clickable links to their target tabs (audio→Sessions, quotes→Quotes, sections/themes→Quotes anchors, AI tags→Analysis, user tags→Codebook); featured quote cards open video player or fall back to transcript; session table rows drill into Sessions tab; section/theme names switch to Quotes tab and scroll to the anchor
- New `--bn-colour-hover` design token with `light-dark()` support
- Speaker code lozenge attribution on featured quotes
- Reusable JS helpers (`scrollToAnchor`, `navigateToSession`) and Python helpers (`_timecode_html`, `_session_anchor`)
- Fix: logo dark/light swap on appearance toggle

**0.9.2** — _12 Feb 2026_

- Sessions table redesign — speaker badges with colour-coded IDs, user journey paths below start dates, video thumbnail placeholders (96×54px, 16:9), per-session sentiment sparkline mini-bar charts
- Appearance toggle — system/light/dark mode switcher in settings tab
- User journeys — derived from topic-segmentation screen clusters, shown in sessions table and sortable journeys table
- Time estimates — upfront pipeline duration estimate after ingest (`~8 min (±2 min)`), recalculated remaining time after each stage, Welford's online algorithm for per-metric running stats, hardware+config keyed profiles persisted to `~/.config/bristlenose/timing.json`
- Clickable logo — Bristlenose logo in report header navigates to project tab
- Fix: `llm_max_tokens` truncation causing silent 0-quote extraction — providers now detect truncation via `stop_reason`/`finish_reason` and raise `RuntimeError` with actionable `.env` fix
- Fix: sentiment sparkline bars now align with video thumbnail baseline (removed inline height override that capped sparkline container at 20px instead of the intended 54px)

**0.9.1** — _11 Feb 2026_

- Moderator and observer names shown in Project tab stats row (Oxford comma lists, observer box only when observers exist)
- Fix: clicking [+] to add a tag on a quote now tags that quote, not the previously-focused quote

**0.9.0** — _11 Feb 2026_

- Tab navigation — tabs remember their position across page reloads via URL hash (`#codebook`, `#analysis`, etc.); browser back/forward navigates between tabs; deep-linkable tab URLs
- Analysis tab — inline signal cards and heatmaps in the main report (previously a placeholder); `BRISTLENOSE_ANALYSIS` data injected into the report's script block alongside the standalone `analysis.html`
- Codebook tab — fixed empty grid caused by `_countQuotesPerTag` function name collision between `codebook.js` and `tag-filter.js` in the concatenated JS bundle; codebook panel now renders correctly in the main report
- Removed dead toolbar button handlers from `analysis.js` and `codebook.js` (replaced by navigation tabs)

**0.8.2** — _9 Feb 2026_

- Transcript annotations — per-participant transcript pages now highlight which segments were selected as quotes, with margin labels showing sentiment, colour-coded span bars connecting multi-segment quotes, and a citation toggle to show/hide annotations; playback-synced glow on both transcript segments and report quote cards when video is playing
- Gemini provider — `--llm gemini` for budget-conscious teams (~$0.20/study, 5–7× cheaper than Claude or ChatGPT); `bristlenose configure gemini` stores your key in the system credential store; interactive provider picker now includes Gemini as option [4]
- Jinja2 template extraction — report renderer migrated from f-strings to Jinja2 templates (13 templates extracted across two phases); pure refactor, no output changes
- Platform-specific credential language — doctor and configure now show the actual store name: "Keychain" on macOS, "Secret Service" on Linux, instead of generic "credential store"

**0.8.1** — _7 Feb 2026_

- Hidden quotes — press `h` (or click the eye-slash button) to hide volume quotes you want to keep as evidence but need out of your working view; per-subsection badge shows count with dropdown of truncated previews; click a preview to unhide with highlight animation; bulk hide via multi-select + `h`; hidden state persists in localStorage and survives search, tag filter, and view switching
- Codebook — standalone `codebook.html` page (opens in a new window via toolbar button) with interactive panel for organising tags into groups; drag-and-drop reordering within and between groups; inline editing of group names; add/delete groups with confirmation; toggle AI tag visibility per-tag; colour-coded tag badges with 24-colour palette; shared data model across report and codebook via localStorage
- Toolbar redesign — unified round-rect button styling with 3-state border progression (rest → hover → active); tag filter and view switcher use dual-class pattern for consistent appearance
- Python 3.14 compatibility — `check_pii` in doctor now catches `Exception` (not just `ImportError`) to handle pydantic v1 crash when importing presidio on Python 3.14

**0.8.0** — _7 Feb 2026_

- Azure OpenAI provider — `--llm azure` for enterprise users with Microsoft Azure contracts; uses `AsyncAzureOpenAI` from the existing OpenAI SDK (no new dependencies); configure with `bristlenose configure azure` or `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` env vars
- Install smoke tests — new CI workflow (`install-test.yml`) verifies install instructions work on clean Linux and macOS VMs; runs `bristlenose doctor` and `bristlenose render` from pre-built fixtures with no API key needed; weekly full-pipeline run with real API key catches integration regressions

**0.7.1** — _6 Feb 2026_

- Bar chart alignment — sentiment and user-tag charts use CSS grid so bar left edges align within each chart; labels hug text with variable gap to bars
- Histogram delete — hover × on user tag labels in the histogram to remove that tag from all quotes (with confirmation modal)
- Surprise placement — surprise sentiment bar now renders between positive and negative sentiments
- Quote exclusivity in themes — each quote assigned to exactly one theme (pick strongest fit)

**0.7.0** — _5 Feb 2026_

- Multi-select — Finder-like click selection (click, Shift-click, Cmd/Ctrl-click) with bulk starring (`s` key) and bulk tagging; selection count shown in view-switcher label; CSV export respects selection
- Tag filter — toolbar dropdown between search and view-switcher filters quotes by user tags; checkboxes per tag with "(No tags)" for untagged quotes; per-tag quote counts, search-within-filter for large tag lists, dropdown chevron, ellipsis truncation for long names

**0.6.15** — _4 Feb 2026_

- Unified tag close buttons — AI badges and user tags now use the same floating circle "×" style
- Tab-to-continue tagging — pressing Tab commits the current tag and immediately opens a new input for adding another tag (type, Tab, type, Tab, Enter for fast keyboard-only tagging)
- Render command path fix — `bristlenose render <input-dir>` now auto-detects `bristlenose-output/` inside the input directory

**0.6.14** — _4 Feb 2026_

- Doctor fixes — improved Whisper model detection and PII capability checking

**0.6.13** — _3 Feb 2026_

- Keychain credential storage — `bristlenose configure claude` (or `chatgpt`) validates and stores API keys securely in macOS Keychain or Linux Secret Service; keys are loaded automatically with priority keychain → env var → .env; `bristlenose doctor` now shows "(Keychain)" suffix when key comes from system credential store; `--key` option available for non-interactive use

**0.6.12** — _3 Feb 2026_

- File-level transcription progress — spinner now shows "(2/4 sessions)" during transcription
- Improved Ollama start command detection — uses `brew services start ollama` for Homebrew installs, `open -a Ollama` for macOS app, platform-appropriate commands for snap/systemd
- Doctor displays "(MLX)" accelerator — when mlx-whisper is installed on Apple Silicon, doctor now shows "(MLX)" instead of "(CPU)"
- Whisper model line fits 80 columns — shortened to "~1.5 GB download on first run"
- Provider header fix — pipeline header now shows "Local (Ollama)" instead of "ChatGPT" when using local provider
- Improved fix messages — doctor fix messages now use `pipx inject` for pipx installs, proper Homebrew Python path for brew installs (PEP 668 compliance)
- Retry logic catches ValidationError — local model retries now also handle Pydantic schema validation failures, not just JSON parse errors

**0.6.11** — _3 Feb 2026_

- Local AI support via Ollama — run bristlenose without an API key using local models like Llama 3.2; interactive first-run prompt offers Local/Claude/ChatGPT choice
- Automated Ollama installation — offers to install Ollama automatically (Homebrew on macOS, snap on Linux, curl script fallback); falls back to download page if installation fails
- Auto-start Ollama — if installed but not running, bristlenose will start it for you
- Provider registry — centralised `bristlenose/providers.py` with `ProviderSpec` dataclass, alias resolution (claude→anthropic, chatgpt→openai, ollama→local)
- Ollama integration — `bristlenose/ollama.py` with status checking, model detection, and auto-pull with consent
- Retry logic for local models — 3 retries with exponential backoff for JSON parsing failures (~85% reliability vs ~99% for cloud)
- Smart cloud fallback hints — fix messages for Ollama issues now check which API keys you have and only suggest providers you can actually use
- Doctor integration for local provider — shows "Local (llama3.2:3b via Ollama)" status, helpful fix messages for Ollama not running or model missing

**0.6.10** — _3 Feb 2026_

- Output directory inside input folder — `bristlenose run interviews/` now creates `interviews/bristlenose-output/` to avoid collisions when processing multiple projects
- New directory structure — `assets/` for static files, `sessions/` for transcript pages, `transcripts-raw/`/`transcripts-cooked/` for transcripts, `.bristlenose/` for internal files
- Report filenames include project name — `bristlenose-{slug}-report.html` so multiple reports in Downloads are distinguishable
- Coverage link fix — player.js no longer intercepts non-player timecode links
- Anchor highlight — transcript page segments flash yellow when arriving via anchor link

**0.6.9** — _3 Feb 2026_

- Transcript coverage section — collapsible section at the end of the report showing what % of the transcript made it into quotes (X% in report · Y% moderator · Z% omitted), with expandable omitted content per session
- Transcript page fix — pages now render correctly when PII redaction is off (was failing with assertion error)

**0.6.8** — _3 Feb 2026_

- Multi-participant session support — sessions with multiple interviewees get globally-numbered participant codes (p1–p11 across sessions); report header shows correct participant count
- Sessions table — restructured from per-participant rows to per-session rows with a Speakers column showing all speaker codes (m1, p1, p2, o1) per session
- Transcript page format — heading shows `Session N: m1 Name, p5 Name, o1`; segment labels show raw codes for consistency with the anonymisation boundary
- Session duration — now derived from transcript timestamps for VTT-only sessions (previously showed "—")
- Moderator identification (Phase 1) — per-session speaker codes (`[m1]`/`[p1]`) in transcript files, moderator entries in `people.yaml`, `.segment-moderator` CSS class for muted moderator styling

**0.6.7** — _2 Feb 2026_

- Search enhancements — clear button (×) inside the search input, yellow highlight markers on matching text, match count shown in view-switcher label ("7 matching quotes"), ToC and Participants hidden during search, CSV export respects search filter
- Pipeline warnings — clean dim-yellow warning lines when LLM stages fail (e.g. credit balance too low), with direct billing URL for Claude/ChatGPT; deduplication and 74-char truncation
- CLI polish — "Bristlenose" in regular weight in the header line, "Report:" label in regular weight in the summary

**0.6.6** — _2 Feb 2026_

- Cargo/uv-style CLI output — clean `✓` checkmark lines with per-stage timing, replacing garbled Rich spinner output; dim header (version · sessions · provider · hardware), LLM token usage with cost estimate, OSC 8 terminal hyperlinks for report path; output capped at 80 columns; all tqdm/HuggingFace progress bars suppressed
- Search-as-you-type quote filtering — collapsible magnifying glass icon in the toolbar; filters by quote text, speaker, and tag content; overrides view mode during search; hides empty sections/subsections; 150ms debounce
- Platform-aware session grouping — Teams, Zoom cloud, Zoom local, and Google Meet naming conventions recognised automatically; two-pass grouping (Zoom folders by directory, remaining files by normalised stem); audio extraction skipped when a platform transcript is present
- Man page — full troff man page (`man bristlenose`); bundled in the wheel and self-installs to `~/.local/share/man/man1/` for pip/pipx users on first run; wired into snap, CI version gate, and GitHub Release assets
- Page footer — "Bristlenose version X.Y.Z" colophon linking to the GitHub repo on every generated page

**0.6.5** — _2 Feb 2026_

- Timecode typography — two-tone treatment with blue digits and muted grey brackets; `:visited` colour fix so clicked timecodes stay blue
- Hanging-indent layout — timecodes sit in a left gutter column on both report quotes and transcript pages, making them scannable as a vertical column
- Non-breaking spaces on quote attributions prevent the `— p1` from widowing onto a new line
- Transcript name propagation — name edits made in the report's participant table now appear on transcript page headings and speaker labels via shared localStorage

**0.6.4** — _1 Feb 2026_

- Concurrent LLM calls — per-participant stages (speaker identification, topic segmentation, quote extraction) now run up to 3 API calls in parallel via `llm_concurrency` config; screen clustering and thematic grouping also run concurrently; ~2.7× speedup on the LLM-bound portion for multi-participant studies

**0.6.3** — _1 Feb 2026_

- Report header redesign — logo top-left (flipped horizontally), "Bristlenose" logotype with project name, right-aligned document title and session metadata
- View-switcher dropdown — borderless menu to switch between All quotes, Favourite quotes, and Participant data views; replaces old button-bar pattern
- Copy CSV button with clipboard icon — single adaptive button that exports all or favourites based on the current view
- Quote attributions use raw participant IDs (`— p1`) in the report for anonymisation; transcript pages continue to show display names
- Table of Contents reorganised — Sentiment, Tags, Friction points, and User journeys moved to a dedicated "Analysis" column, separate from Themes

**0.6.2** — _1 Feb 2026_

- Editable participant names — pencil icon on Name and Role cells in the participant table; inline editing with localStorage persistence; YAML clipboard export for writing back to `people.yaml`; reconciliation with baked-in data on re-render
- Auto name and role extraction — Stage 5b LLM prompt now extracts participant names and job titles alongside speaker role identification; speaker label metadata harvested from Teams/DOCX/VTT sources; empty `people.yaml` fields auto-populated (LLM results take priority over metadata, human edits never overwritten)
- Short name suggestion — `short_name` auto-suggested from first token of `full_name` with disambiguation for collisions ("Sarah J." vs "Sarah K."); works both in the pipeline and in-browser
- Editable section and theme headings — inline editing on section titles, descriptions, theme titles, and theme descriptions with bidirectional Table of Contents sync

**0.6.1** — _1 Feb 2026_

- Snap packaging for Linux — `snap/snapcraft.yaml` recipe and CI workflow (`.github/workflows/snap.yml`); builds on every push to main, publishes to edge/stable when Store registration completes
- Pre-release snap testing instructions in README for early feedback on amd64 Linux
- Author identity (Martin Storey) added to copyright headers, metadata, and legal files

**0.6.0** — _1 Feb 2026_

- `bristlenose doctor` command — checks FFmpeg, transcription backend, Whisper model cache, API key validity, network, PII dependencies, and disk space
- Pre-flight gate on `run`, `transcribe-only`, and `analyze` — catches missing dependencies before slow work starts
- First-run auto-doctor — runs automatically on first invocation, guides users through setup
- Install-method-aware fix messages — detects snap, Homebrew, or pip and shows tailored install instructions
- API key validation — cheap API call catches expired or revoked keys upfront

**0.5.0** — _1 Feb 2026_

- Per-participant transcript pages — full transcript for each participant with clickable timecodes and video player; participant IDs in the table link to these pages
- Quote attribution deep-links — clicking `— p1` at the end of a quote jumps to the exact segment in the participant's transcript page
- Segment anchors on transcript pages for deep linking from quotes and external tools

**0.4.1** — _31 Jan 2026_

- People file (`people.yaml`) — participant registry with computed stats (words, % words, % speaking time) and human-editable fields (name, role, persona, notes); preserved across re-runs
- Display names — set `short_name` in `people.yaml`, re-render with `bristlenose render` to update quotes and tables
- Enriched participant table in reports (ID, Name, Role, Start, Duration, Words, Source) with macOS Finder-style relative dates
- PII redaction now off by default; opt in with `--redact-pii` (replaces `--no-pii`)
- Man page updated for new CLI flags and output structure

**0.4.0** — _31 Jan 2026_

- Dark mode — report follows OS/browser preference automatically via CSS `light-dark()` function
- Override with `color_scheme = "dark"` (or `"light"`) in `bristlenose.toml` or `BRISTLENOSE_COLOR_SCHEME` env var
- Dark-mode logo variant (placeholder; proper albino bristlenose pleco coming soon)
- Print always uses light mode
- Replaced hard-coded colours in histogram JS with CSS custom properties

**0.3.8** — _31 Jan 2026_

- Timecode handling audit: verified full pipeline copes with sessions shorter and longer than one hour (mixed `MM:SS` and `HH:MM:SS` in the same file round-trips correctly)
- Edge-case tests for timecode formatting at the 1-hour boundary, sub-minute sessions, long sessions (24h+), and format→parse round-trips

**0.3.7** — _31 Jan 2026_

- Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting constants and formatter functions
- Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- Participant codes in transcript segments (`[p1]` instead of `[PARTICIPANT]`) for better researcher context when copying quotes
- Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes

**0.3.6** — _31 Jan 2026_

- Document full CI/CD pipeline topology, secrets, and cross-repo setup

**0.3.5** — _31 Jan 2026_

- Automated Homebrew tap updates and GitHub Releases on every tagged release

**0.3.4** — _31 Jan 2026_

- Participants table: renamed columns (ID→Session, Session date→Date), added Start time column, date format now dd-mm-yyyy

**0.3.3** — _31 Jan 2026_

- README rewrite: install moved up, new quick start section, changelog with all versions, dev setup leads with git clone
- Links to Anthropic and OpenAI API key pages in install instructions

**0.3.2** — _30 Jan 2026_

- Fix tag auto-suggest offering tags the quote already has
- Project logo in report header

**0.3.1** — _30 Jan 2026_

- Single-source version: `__init__.py` is the only place to bump
- Updated release process in CONTRIBUTING.md

**0.3.0** — _30 Jan 2026_

- CI on every push/PR (ruff, mypy, pytest)
- Automated PyPI publishing on tagged releases (OIDC trusted publishing)

**0.2.0** — _30 Jan 2026_

- Tag system: AI-generated badges (deletable/restorable) + user tags with auto-suggest and keyboard navigation
- Favourite quotes with reorder animation and CSV export (separate AI/User tag columns)
- Inline quote editing with localStorage persistence
- Sentiment histogram (side-by-side AI + user-tag charts)
- `bristlenose render` command for re-rendering without LLM calls
- Report JS extracted into 8 standalone modules under `bristlenose/theme/js/`
- Atomic CSS design system (`bristlenose/theme/`)

**0.1.0** — _30 Jan 2026_

- 12-stage pipeline: ingest, extract audio, parse subtitles/docx, transcribe (Whisper), identify speakers, merge, PII redaction (Presidio), topic segmentation, quote extraction, screen clustering, thematic grouping, render
- HTML report with clickable timecodes and popout video player
- Quote enrichment: intent, emotion, intensity, journey stage
- Friction points and user journey summaries
- Apple Silicon GPU acceleration (MLX), CUDA support, CPU fallback
- PII redaction with Presidio
- Cross-platform (macOS, Linux, Windows)
- Published to PyPI and Homebrew tap
- AGPL-3.0 licence with CLA
