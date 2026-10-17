import AppKit
import Foundation
import Testing

@testable import Bristlenose

/// Pins the sidebar's palette lookups.
///
/// A palette in the picker with no colorsets is not an error anywhere: the
/// asset miss falls back to system colours, so the sidebar silently stays
/// Default while the report beside it changes. And `"rose-pine".capitalized`
/// is `"Rose-Pine"`, an asset name nothing carries.
@Suite("SidebarPalette")
struct SidebarPaletteTests {
    @Test func assetStemDropsTheHyphen() {
        #expect(SidebarPalette.assetStem("rose-pine") == "RosePine")
        #expect(SidebarPalette.assetStem("edo") == "Edo")
        #expect(SidebarPalette.assetName(.accent, palette: "rose-pine") == "PaletteRosePineAccent")
    }

    @Test func anUnknownPaletteIsDefault() {
        #expect(SidebarPalette.normalised("no-such-palette") == "default")
        #expect(SidebarPalette.normalised(nil) == "default")
        #expect(SidebarPalette.normalised("gruvbox") == "gruvbox")
    }

    @Test(arguments: ["default"] + SidebarPalette.tinted.sorted())
    func everyPaletteHasItsFourColorsets(palette: String) {
        for concept: SidebarPalette.Concept in [.paper, .ink, .accent, .lozenge] {
            let name = SidebarPalette.assetName(concept, palette: palette)
            #expect(NSColor(named: name) != nil, "missing colorset \(name)")
        }
    }
}
