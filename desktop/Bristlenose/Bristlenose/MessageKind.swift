import Foundation
import SwiftUI

/// Swift mirror of `bristlenose/ui_kinds.py::MessageKind`. The Python module
/// is the canonical source of truth — it carries additional metadata
/// (length budgets, markdown glyphs) the Swift mirror does not need.
/// When extending: edit `bristlenose/ui_kinds.py` first; the Swift side
/// only carries the cases + CLI glyphs the popover uses.
///
/// The taxonomy is the entire glyph vocabulary the popover (and the CLI) may
/// use. The design doc forbids minting new glyphs — anything that doesn't fit
/// these five maps to the nearest existing kind.
enum MessageKind: String, Codable, Equatable, CaseIterable {
    case success
    case info
    case warning
    case error
    case skipped

    /// CLI glyph — must match `CLI_GLYPH` in `bristlenose/ui_kinds.py`.
    /// Used inside `formatDiagnosticPlaintext` so copy-pasted diagnostics
    /// look the same as a CLI run. NOT used for inline rendering in the
    /// Mac UI — use `symbolName` + `tint` instead, which are Mac-native.
    var glyph: String {
        switch self {
        case .success: return "✓"
        case .info:    return "ℹ"
        case .warning: return "⚠"
        case .error:   return "✗"
        case .skipped: return "—"
        }
    }

    /// SF Symbol name for inline use in macOS surfaces. Each kind keeps its
    /// own shape *and* fill weight (filled for loud states that demand the
    /// eye; outline for quiet states that ride alongside text). Combined
    /// with `tint`, the pair carries the state signal redundantly via shape
    /// and colour — colour-blind readers get the shape disambiguation for
    /// free.
    var symbolName: String {
        switch self {
        case .success: return "checkmark.circle"           // outline · "fine, no action"
        case .info:    return "info.circle"                // outline · informational
        case .warning: return "exclamationmark.triangle.fill"  // filled · caution earns weight
        case .error:   return "xmark.circle.fill"          // filled · must not be missed
        case .skipped: return "minus.circle.fill"          // filled · deliberate, not empty
        }
    }

    /// Canonical SwiftUI tint paired with `symbolName`. All values are
    /// system semantic colours (dark-mode adaptive, accessibility-tinted)
    /// — Apple does not provide meaning-named colours (no `Color.error`
    /// etc.), so the mapping from kind → palette is *our* convention,
    /// matching macOS HIG colour idioms:
    ///   - red = destructive / failure
    ///   - orange = caution / warning
    ///   - green = success / cooperative action
    ///   - blue = informational / system accent
    ///   - cyan = dormant / "icy" — chosen for `.skipped` because it
    ///     reads as "intentionally untouched / cold" without competing
    ///     with `.info`'s blue.
    /// Apply via `.foregroundStyle(kind.tint)` on the Image.
    var tint: Color {
        switch self {
        case .success: return .green
        case .info:    return .blue
        case .warning: return .orange
        case .error:   return .red
        case .skipped: return .cyan
        }
    }
}
