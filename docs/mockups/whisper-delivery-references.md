# Whisper delivery: reference screens and sources

Collected 17 Nov 2026. These are links, not copies: nothing here is reproduced in the repo. **No screenshot was viewed by the research agents** (the fetch tool returns text and image URLs only), so "shows" below is from alt text or surrounding prose and is marked. Open the image links yourself before leaning on any of them. Findings and numbering: `docs/private/app-store-launch/ba-ux-research.md`.

## Apple

| Reference | URL | What it teaches |
|---|---|---|
| Downloading Apple-hosted asset packs | https://developer.apple.com/documentation/backgroundassets/downloading-apple-hosted-asset-packs | "When downloading asset packs in the foreground, display a progress indicator"; status cases; cancel via `Progress.cancel()`; no pause API. |
| `DownloadStatusUpdate` | https://developer.apple.com/documentation/backgroundassets/assetpackmanager/downloadstatusupdate | `began` (also "resumed"), `paused`, `downloading`, `finished`, `failed`. |
| WWDC25 session 325 | https://developer.apple.com/videos/play/wwdc2025/325/ | Versions, TestFlight and review states, storage shown under the app. Not watched in full. |
| Forum 815174, review environment | https://developer.apple.com/forums/thread/815174 | Apple staff: pre-launch downloads are off for App Review; show `downloadSize` per 4.2.3(ii). |
| Forum 848686, restart from byte 0 | https://developer.apple.com/forums/thread/848686 | Known bug on iOS and visionOS: backgrounding discards resume data. |
| App Review Guidelines | https://developer.apple.com/app-store/review/guidelines/ | 4.2.3(ii), 2.4.5(iv), 2.5.2, 2.3.1(a). |
| HIG Progress indicators | https://developer.apple.com/design/human-interface-guidelines/progress-indicators | Determinate; stalls; Pause beside Cancel when cancelling loses progress; confirm a lossy cancel. |
| HIG Loading | https://developer.apple.com/design/human-interface-guidelines/loading | Do other things while loading; say how long; Background Assets named. |
| HIG Alerts | https://developer.apple.com/design/human-interface-guidelines/alerts | "Avoid showing an alert when your app starts"; button naming. |
| Xcode components | https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components | Get button per component; app usable while downloading; only run and build gated. |
| Logic Pro Sound Library | https://support.apple.com/en-us/102030 | Space needed stated up front; install in smaller packs on failure. |
| Final Cut Pro content | https://support.apple.com/guide/final-cut-pro/ver927c79852/mac | Hands a large download to Software Update. |
| SpeechAnalyzer assets | https://developer.apple.com/documentation/speech/assetinventory | Models are system assets that may be absent or evicted: check every time. |

## Third-party apps (text sources; image links are unviewed)

| App | Source | Teaches |
|---|---|---|
| MacWhisper | https://docs.macwhisper.com/article/29-switching-to-a-whisperkit-model ; images https://d33v4339jhl8k0.cloudfront.net/docs/assets/659d3a04ca9db27644270725/images/68768d7d52724d3c54de87b0/file-OKuHnw0x1r.png | Manage Models screen; warns of a second wait for first load after the download. |
| Aiko | https://sindresorhus.com/aiko | Bundles the model; 2.8 GB app; store owns progress. |
| Superwhisper | https://superwhisper.com/docs/get-started/choose-your-model.md ; image https://mintcdn.com/superwhisper/SFDRA4G70egO6eAv/images/screens/mac/models-library-voice.png | Size on each row; cloud first run needs no download. |
| VoiceInk | https://tryvoiceink.com/docs/local-models | One default model in onboarding; "reveal in Finder". |
| Ollama | https://ollama.com/blog/new-app ; user reports https://hn.svelte.dev/item/44739632 | Implicit download on first chat confused users: show what is not on disk. |
| LM Studio | https://lmstudio.ai/docs/bionic/models/download-local-models ; https://lmstudio.ai/changelog/lmstudio-v0.4.3 | Pause, resume, cancel, retry; auto-retry with backoff; panel closed by default. |
| Jan | https://docs.jan.ai/desktop/manage-models | Top-bar indicator with name and percent; fit pill (Fits, May be slow, Won't fit). |
| Handy | https://handy.computer/docs/troubleshooting ; https://github.com/cjpais/Handy | Manual install path; partial-file cleanup is the user's job (counter-example). |
| NN/g progress indicators | https://www.nngroup.com/articles/progress-indicators/ | Percent for 10 s or more; general time estimate; let people stop; say why. |

Could not read: SitePoint "UX patterns for large model downloads" (403), Apple's game large-downloads article (body did not load).
