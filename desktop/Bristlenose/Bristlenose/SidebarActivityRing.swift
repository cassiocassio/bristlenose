import AppKit

/// Native activity/copy ring for the sidebar cell's subtitle-right slot — the
/// AppKit equivalent of `ProjectRowActivityIndicator`'s determinate ring +
/// indeterminate spinner (Phase 3 of the cell port).
///
/// `fraction == nil` → indeterminate spinner (uncalibrated first run, or a copy
/// cancel-rollback). `fraction != nil` → a determinate arc (run progress / copy
/// byte ratio). The hover-× cancel swap is Phase 4.
///
/// **The one bespoke visual of the cell port.** There is no stock determinate-
/// *circular* `NSProgressIndicator` (it only does bars + indeterminate spin), so
/// the arc is a `CAShapeLayer` (faint track + accent fill, `strokeEnd = fraction`).
/// `ProjectRowActivityIndicator.swift` stays in the tree as the dormant SwiftUI
/// template / spec.
///
/// **QA (not visually verified overnight):** the arc is built to fill **clockwise
/// from 12 o'clock**. If it reads reversed or starts at the wrong clock position,
/// the fix is local — flip the `clockwise:` flag or negate the angles in
/// `buildRing` (the CALayer geometry-flip state depends on the host view and
/// wasn't confirmed against a live render). Size (16pt) + colours (accent fill,
/// tertiary track) are also tune-against-`ProjectRow` carpentry.
final class SidebarActivityRing: NSView {

    /// Matches `ProjectRowActivityIndicator`'s 16×16 box.
    static let side: CGFloat = 16
    private let lineWidth: CGFloat = 2

    init(fraction: Double?) {
        super.init(frame: NSRect(x: 0, y: 0, width: Self.side, height: Self.side))
        translatesAutoresizingMaskIntoConstraints = false
        wantsLayer = true
        if let fraction {
            buildRing(fraction: fraction)
        } else {
            buildSpinner()
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) unavailable") }

    override var intrinsicContentSize: NSSize { NSSize(width: Self.side, height: Self.side) }

    private func buildRing(fraction: Double) {
        let inset = lineWidth / 2 + 0.5
        let rect = bounds.insetBy(dx: inset, dy: inset)
        let center = CGPoint(x: bounds.midX, y: bounds.midY)
        let radius = rect.width / 2
        // Clockwise from 12 o'clock (y-up layer coords: top = +π/2, clockwise = true).
        let path = CGMutablePath()
        path.addArc(center: center, radius: radius,
                    startAngle: .pi / 2, endAngle: .pi / 2 - 2 * .pi, clockwise: true)

        let track = CAShapeLayer()
        track.frame = bounds
        track.path = path
        track.fillColor = NSColor.clear.cgColor
        track.strokeColor = NSColor.tertiaryLabelColor.cgColor
        track.lineWidth = lineWidth

        let fill = CAShapeLayer()
        fill.frame = bounds
        fill.path = path
        fill.fillColor = NSColor.clear.cgColor
        fill.strokeColor = NSColor.controlAccentColor.cgColor
        fill.lineWidth = lineWidth
        fill.lineCap = .round
        fill.strokeEnd = CGFloat(max(0, min(1, fraction)))

        layer?.addSublayer(track)
        layer?.addSublayer(fill)
    }

    private func buildSpinner() {
        let spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isIndeterminate = true
        spinner.translatesAutoresizingMaskIntoConstraints = false
        addSubview(spinner)
        NSLayoutConstraint.activate([
            spinner.centerXAnchor.constraint(equalTo: centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: centerYAnchor),
            spinner.widthAnchor.constraint(equalToConstant: Self.side),
            spinner.heightAnchor.constraint(equalToConstant: Self.side),
        ])
        spinner.startAnimation(nil)
    }
}
