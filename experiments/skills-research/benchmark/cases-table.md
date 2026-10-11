| P1 | `8579cf56` | fix: AutoCode progress write no longer discards a batch's proposals | bristlenose/server/autocode.py |
| P2 | `0c9f7f2b` | fix: identify projects and cache inputs by resolved path, not spelling | bristlenose/hashing.py bristlenose/server/importer.py |
| P3 | `3bce61d0` | doctor: a bad model directory was reported as an incompatible Python | bristlenose/doctor.py bristlenose/doctor_fixes.py |
| P4 | `57777276` | people: a moderator lost to a code collision now says so | bristlenose/people.py |
| P5 | `040080c6` | fix: validate anthropic key via /v1/models, not a retired model | bristlenose/doctor.py |
| T1 | `ae522367` | fix sessions sidebar moderator detection (role never == "moderator") | frontend/src/components/SessionsSidebar.tsx |
| T2 | `1eefa14c` | fix tags typed since mount vanishing from the tag sidebar | frontend/src/components/TagSidebar.tsx |
| T3 | `0fc90840` | export: speaker links must be hash-routed, and the guard that missed it | frontend/src/islands/QuoteCard.tsx |
| T4 | `397f23c2` | search: from review — highlights stop at the word, it's is not every it | frontend/src/utils/searchMatch.ts |
| S1 | `891823da` | the dead lenses: reset() was wiping the outbound channel a warm switch had just registered | desktop/Bristlenose/Bristlenose/BridgeHandler.swift desktop/Bristlenose/Bristlenose/WebView.swift |
| S2 | `d794778d` | window roster: five restored windows were becoming five masters | desktop/Bristlenose/Bristlenose/WindowRoster.swift |
| S3 | `1c5bebfa` | watcher: publish the first scan even when it found nothing | desktop/Bristlenose/Bristlenose/ProjectFolderWatcher.swift |
| S4 | `8cb6811b` | mcp handshake: write one payload to both copies, so they agree on updated_at | desktop/Bristlenose/Bristlenose/MCPHandshake.swift |
| S5 | `2a3bcbe4` | fix: the relaunch prompt was dismissed by the window it was attached to | desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift desktop/Bristlenose/Bristlenose/SettingsView.swift |
