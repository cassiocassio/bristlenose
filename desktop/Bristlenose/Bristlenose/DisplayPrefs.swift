import Foundation

/// How the report's quote content looks: Layout, Density, Break long paragraphs
/// (docs/design-display-preferences.md).
///
/// The SPA owns these and saves them (`storePref`, mirrored into UserDefaults by
/// the `report-pref` allowlist). Native only mirrors the live value, the way it
/// mirrors Focus Mode, so the Display popover always shows what the report has
/// and never a second source of truth. The popover sends a choice back through
/// `menuAction` and the SPA validates it.
struct DisplayPrefs: Equatable {
    static let layouts = ["columns", "single"]
    static let breakValues = ["on", "off"]

    /// Density is continuous, 0 (the tightest) to 1 (the roomiest), with Normal,
    /// today's screen, in the middle.
    static let densityNormal = 0.5

    /// A report that has not yet said otherwise: columns, Normal density, and long
    /// quotes broken into paragraphs (on by default, owner 4 Nov 2026; the SPA's
    /// `DEFAULT_BREAKS` is the other half of this).
    static let standard = DisplayPrefs(layout: "columns", density: densityNormal, breaks: "on")

    var layout: String
    var density: Double
    var breaks: String

    var breaksOn: Bool { breaks == "on" }

    init(layout: String, density: Double, breaks: String) {
        self.layout = layout
        self.density = density
        self.breaks = breaks
    }

    /// Parse the SPA's `display-prefs` post. Nil unless all three values are
    /// ones the SPA could have sent, so a malformed message changes nothing.
    init?(message body: [String: Any]) {
        guard let layout = body["layout"] as? String, Self.layouts.contains(layout),
              let number = body["density"] as? NSNumber,
              // JavaScript's true and false arrive as NSNumbers too; they are not densities.
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              case let density = number.doubleValue,
              density.isFinite, (0...1).contains(density),
              let breaks = body["breaks"] as? String, Self.breakValues.contains(breaks)
        else { return nil }
        self.init(layout: layout, density: density, breaks: breaks)
    }
}
