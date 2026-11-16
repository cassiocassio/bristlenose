import BackgroundAssets
import StoreKit

// The Background Assets download extension for the Mac App Store build
// (docs/private/background-assets-whisper-plan-2026-11.md §4). It has no code of its own:
// Apple hosts the asset pack, and the system runs this extension to fetch it. The app
// asks for the pack through `AssetPackManager` (`AssetPackManagerAdapter.swift`).
//
// Sources live here, outside the app's synchronised folder, so the app target never
// compiles them and a build of the app alone never signs this target.

@main
struct BAExtension: StoreDownloaderExtension {
}
