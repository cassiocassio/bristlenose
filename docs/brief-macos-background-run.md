# Brief: can a Mac analysis keep running, recoverably, after the app is quit?

For a separate investigation session. Written 6 Nov 2026. This is a question to research and answer, not a feature to build. It is deliberately **not** part of the run-finished banner work (`docs/design-run-banner.md`), which covers the common case: the researcher has hidden Bristlenose, left it under other windows or gone full-screen elsewhere, and is told when the run ends. This brief covers the other case, where the app is not running at all.

## The question

Today, quitting the Mac app stops the analysis. The owner suspects the rule was inherited from the command line and does not fit the Mac:

- On the CLI, the terminal and the process are the same thing, and a browser on top of `bristlenose serve` is a light, detachable viewer. The **process is the driver and the viewer comes and goes.**
- In the Mac app the shape is reversed in the researcher's mind: the app is the product, and quitting it is a normal thing to do. Nobody planned the UX for "I quit, and the Python is still working, recoverably".

**Find out what macOS offers natively for keeping a process alive headlessly, and whether there is an elegant, App Store-compatible way to let a run continue after Quit and be picked up again on relaunch.** Report what exists, what each costs, what the researcher would experience, and whether it is worth doing. A valid answer is "not worth it, and here is why".

## What is already true (read these first)

- **The 20 Oct 2026 decision (R19):** leaving the app stops the run; Analyse resumes from the cache. ⌘Q sends a stop signal; a force-quit or crash makes the run stop itself within about half a second; a run that ends after the app has gone is recorded as cancelled. Source: `docs/design-subprocess-lifecycle.md` (§ "Superseded for hosted runs") and `desktop/CLAUDE.md` (the `stopAllForQuit` paragraph).
- **Why it was made:** a hosted run's standard output is a pipe to the app. When the app went away the run died at its next print, so a relaunch that had attached and showed "Resuming…" ended as a failure, "CLI exited with code 1". The rule ended that. **The cause was the pipe, not a law that runs cannot outlive the app.** A run that wrote only to its own log, with no pipe to the app, would not die this way.
- **Recovery already exists in part:** a run writes `pipeline-events.jsonl` and a manifest atomically to disk; progress is read from the events log; a PID file lets the app find and attach to a run it did not start (the attach logic is described in `docs/design-subprocess-lifecycle.md`, and marked superseded for hosted runs). Resume from cache already works after a stop.
- **Constraints of the shipped app:** App Sandbox and Hardened Runtime, Mac App Store build plus a Developer-ID `.dmg`, deployment floor macOS 15, one app group (`group.app.bristlenose`) on the store build only, a bundled PyInstaller sidecar, provider keys in the Keychain. The ledger's "declined" list records a stance against speculative background spawns.
- **Provider failure is fail-stop** (decided): a run that hits a provider error stops rather than retrying forever, so a long unattended run has a defined end.

## What to investigate

1. **Native ways to keep work running after the app quits**, each described from Apple's own documentation where it exists: a helper registered with `SMAppService` (login item, launch agent, launch daemon); an XPC service; a launch agent started by `launchd` on demand; `NSBackgroundActivityScheduler`; keeping the machine awake for the job (`ProcessInfo` activity assertions, power assertions) and what App Nap does to a headless process; running as a child of `launchd` rather than of the app. For each: does it survive Quit, logout, restart, sleep and lid-close; what does the sandbox allow; does a sandboxed helper inherit the app's Keychain access and container; what the user must approve and how it appears in System Settings (Login Items & Extensions).
2. **App Store compatibility.** What App Review Guidelines say about processes that outlive the app (2.4.5(iii) on consent for auto-launch and outliving processes was quoted by an earlier session; verify the current text, and 2.4.2). Real precedent: Mac App Store apps that run long jobs in the background (video encoders, backup, sync, transcription apps) and how they do it.
3. **The pipe problem.** What a run needs to be detachable: its own log instead of a pipe, a handshake, how it learns the app is gone without dying, how it finds the app again, how it ends if nobody returns. Whether Python under a sandboxed launch agent (the PyInstaller sidecar, with Whisper's native code) has any extra constraint. The existing PID-file and manifest recovery should be reused, not replaced.
4. **The researcher's experience.** What macOS apps that do this look like and whether it surprises people (the Mac convention that closing the last window does not quit, against ⌘Q meaning stop everything; whether "Quit" should ask when a run is going; a menu bar item; the Dock). What the researcher sees on relaunch for a run that finished, failed, or is still going. What an honest "it is still running with the app closed" indicator looks like and where it lives, if anywhere. How this interacts with the banner (a helper that outlives the app could raise the banner itself, since nothing else is alive).
5. **Sleep and power.** A 40-minute run on a laptop: what happens when the lid closes, the Mac sleeps, or the researcher unplugs. What the app does today about keeping the Mac awake during a run, if anything; what a detached run would need.
6. **Failure modes the detachment adds.** A run that finishes with nobody to tell; a run that keeps spending provider credit after the researcher forgot; two copies of the app; the study moved or the drive ejected under it; a crashed helper that leaves a stale status. How each is made visible and recoverable without nagging.
7. **The CLI parity question.** The CLI and the Mac app share one Python pipeline (`docs/design-modularity.md`). Whether detachment changes that, or stays Mac-only packaging.

## What a good answer contains

- A plain statement of the options and which are viable for a sandboxed, App Store build, with Apple sources opened (not remembered). Mark every claim **verified**, **partly** or **unverified**, as the earlier research did; do not present recall as fact.
- A recommendation with the researcher's experience described in a short scenario, including the two cases that matter: they quit while a run is going, and they return later.
- The cost: new entitlements or capabilities, a new process to ship and sign, review risk, tests, and what it reverses (the 20 Oct decision, and any tests that pin it).
- What it would take to **try it cheaply**: the smallest spike that would show whether a detached run survives Quit on a real Mac under the real sandbox, and whether the Python keeps its Keychain and file access. Run the spike only in a disposable setup, never on a researcher's real study; the sandbox answers are empirical and have been wrong before when read from the entitlements files.
- Honest "not worth it" if that is the finding.

## Hard rules

- **Do not edit product code** in this investigation. Write findings to a new file, for example `docs/design-background-run.md`.
- The owner's standing rules apply to any UX it proposes: the UI tells the truth; nothing needy (no retry loops or "are you still there?"); expected outcomes get plain words; native macOS idioms first ("go with the macOS grain"); fit the existing framework and nearest shipped sibling before inventing; no new glyphs or colours when one fits.
- **Beta means almost no new features.** This brief is for deciding, not building. Present the result so the owner can choose to defer it.
- Participant data stays out of examples; use synthetic ones.
- Provider-bound LLM time and the speed of transcription itself are out of scope for performance; this is about where the run lives, not how fast it goes.

## Out of scope

- Alerts to an iPhone or Apple Watch (see `docs/design-perceived-wait.md`).
- The banner for the hidden-or-buried case (`docs/design-run-banner.md`).
- A hosted relay or any server.
- Windows and Linux.

## Related reading

- `docs/design-subprocess-lifecycle.md` (the R19 section, the attach logic, quit propagation)
- `docs/design-analysis-lifecycle.md` (the state machine and failure modes)
- `docs/design-perceived-wait.md` (why this matters to how a wait feels)
- `docs/design-run-banner.md`
- `docs/design-desktop-python-runtime.md` (the sidecar)
- `docs/design-pipeline-resilience.md` (manifest, events, resume)
