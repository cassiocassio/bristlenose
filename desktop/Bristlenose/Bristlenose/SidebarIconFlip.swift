import AppKit

/// Plays the one-shot split-flap reveal on a layer-backed `NSImageView`: cycles the
/// icon through palette symbols at a decelerating cadence, each flipping in around
/// the horizontal axis (edge-on → face-on), settling on the final symbol.
///
/// Pure motion — the caller owns the overlay view, its placement over the row's icon,
/// and its teardown. Used by `SidebarOutlineController` (AppKit sidebar); the SwiftUI
/// `ProjectRow` has its own `TumblingProjectIcon` equivalent.
enum SidebarIconFlip {

    @MainActor
    static func play(on imageView: NSImageView, settlingOn finalSymbol: String, tint: NSColor?) async {
        let pool = RandomProjectIcon.pool
        let config = ProjectCellSpec.iconSymbolConfig
        let steps = 12

        for i in 0..<steps {
            let isLast = i == steps - 1
            let frac = Double(i) / Double(steps - 1)
            // Floor raised (0.06→0.10) so the opening steps read legibly instead of
            // a burst; ceiling raised (0.26→0.30) for a slightly longer settle.
            let interval = 0.10 + (0.30 - 0.10) * frac * frac
            let glyph = isLast ? finalSymbol : (pool.randomElement() ?? finalSymbol)

            imageView.image = NSImage(systemSymbolName: glyph, accessibilityDescription: nil)
            imageView.symbolConfiguration = config
            imageView.contentTintColor = tint

            // Flip the freshly-swapped glyph in from edge-on. Explicit fromValue, so
            // (unlike SwiftUI's implicit animation) there's no same-tick coalescing to
            // worry about — Core Animation interpolates from 90° regardless of state.
            if let layer = imageView.layer {
                let flip = CABasicAnimation(keyPath: "transform.rotation.x")
                flip.fromValue = CGFloat.pi / 2
                flip.toValue = 0
                flip.duration = isLast ? 0.34 : min(0.20, interval)
                flip.timingFunction = CAMediaTimingFunction(name: .easeOut)
                layer.add(flip, forKey: "bn-icon-flip")
            }

            try? await Task.sleep(for: .seconds(interval))
        }
        // Let the final flap settle before the caller tears the overlay down.
        try? await Task.sleep(for: .milliseconds(300))
    }
}
