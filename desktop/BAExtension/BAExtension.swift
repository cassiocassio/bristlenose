import BackgroundAssets
import ExtensionFoundation
import StoreKit

// The Background Assets download extension for the Mac App Store build
// (the Background Assets plan, design section). It has no code of its own:
// Apple hosts the asset pack, and the system runs this extension to fetch it. The app
// asks for the pack through `AssetPackManager` (`AssetPackManagerAdapter.swift`).
//
// Sources live here, outside the app's synchronised folder, so the app target never
// compiles them and a build of the app alone never signs this target.

@main
struct BAExtension: StoreDownloaderExtension {
}
