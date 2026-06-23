import AppKit

/// Native activity/copy ring for the sidebar cell's subtitle-right slot — the
/// AppKit equivalent of `ProjectRowActivityIndicator`'s determinate ring +
/// indeterminate spinner, with the Phase-4 hover-× cancel.
///
/// `fraction == nil` → indeterminate spinner (uncalibrated first run, or a copy
/// cancel-rollback). `fraction != nil` → a determinate arc (run progress / copy
/// byte ratio).
///
/// **Hover-× (Phase 4).** When `onStop != nil`, hovering swaps the ring for a
/// grey `xmark.circle.fill` in the SAME 16pt frame (no reflow); clicking it calls
/// `onStop` (cancel the run / cancel the copy). Grey, not red — red reads as
/// "error" (Finder / App Store download-ring idiom). Mouse-only + accessibility-
/// hidden: keyboard / VoiceOver reach Stop via the Project menu (⌘.) and the row
/// context menu. `onStop == nil` → no × (the cancel-rollback spinner: you can't
/// cancel a cancel). Mirrors `ProjectRowActivityIndicator.ring(fraction:)`.
///
/// **The reload-contention trap.** Live progress rebuilds this view ~1×/s
/// (full `reloadData` per tick, the §6 Phase-A cost). A naive hover swap would
/// flicker every tick while the pointer sits on the ring. Fix: `updateTrackingAreas`
/// re-derives the hover state from the *live* pointer position on every rebuild
/// (`reconcileHover`), so a view rebuilt under the cursor paints the × from frame
/// one. A cursor *rect* (not `NSCursor.push/pop`) avoids an unbalanced cursor
/// stack when a hovered view is destroyed mid-hover.
///
/// **QA (not visually verified):** arc fill direction (clockwise-from-12 — flip
/// `clockwise:`/angles in `buildRing` if reversed); the × size/grey vs `ProjectRow`;
/// that the swap is flicker-free across progress ticks; that clicking × cancels
/// without selecting the row.
final class SidebarActivityRing: NSView {

    /// Matches `ProjectRowActivityIndicator`'s 16×16 box.
    static let side: CGFloat = 16
    private let lineWidth: CGFloat = 2

    /// When non-nil, hovering shows the cancel ×; clicking it calls this. nil →
    /// no × (cancel-rollback spinner). Set at build time by `cellRightSlot`.
    var onStop: (() -> Void)? {
        didSet { window?.invalidateCursorRects(for: self) }
    }

    /// The ring's drawn content — hidden while the × shows. Layers for the
    /// determinate arc, or the indeterminate spinner subview.
    private var ringLayers: [CAShapeLayer] = []
    private var spinner: NSProgressIndicator?
    private lazy var stopButton: NSButton = makeStopButton()
    private var hovering = false

    init(fraction: Double?, onStop: (() -> Void)? = nil) {
        self.onStop = onStop
        super.init(frame: NSRect(x: 0, y: 0, width: Self.side, height: Self.side))
        translatesAutoresizingMaskIntoConstraints = false
        wantsLayer = true
        if let fraction {
            buildRing(fraction: fraction)
        } else {
            buildSpinner()
        }
        addSubview(stopButton)
        NSLayoutConstraint.activate([
            stopButton.centerXAnchor.constraint(equalTo: centerXAnchor),
            stopButton.centerYAnchor.constraint(equalTo: centerYAnchor),
            stopButton.widthAnchor.constraint(equalToConstant: Self.side),
            stopButton.heightAnchor.constraint(equalToConstant: Self.side),
        ])
        // Mouse-only, like ProjectRow's `.accessibilityHidden(true)`.
        setAccessibilityElement(false)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) unavailable") }

    override var intrinsicContentSize: NSSize { NSSize(width: Self.side, height: Self.side) }

    // MARK: - Hover swap

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(
            rect: .zero,
            options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
            owner: self, userInfo: nil))
        // Reconcile after a rebuild: if the pointer is already inside (a reload
        // tick rebuilt this view mid-hover), show the × from the first paint.
        reconcileHover()
    }

    private func reconcileHover() {
        guard let window else { return }
        let local = convert(window.mouseLocationOutsideOfEventStream, from: nil)
        setHovering(bounds.contains(local))
    }

    override func mouseEntered(with event: NSEvent) { setHovering(true) }
    override func mouseExited(with event: NSEvent) { setHovering(false) }

    private func setHovering(_ value: Bool) {
        hovering = value
        let showStop = value && onStop != nil
        stopButton.isHidden = !showStop
        ringLayers.forEach { $0.isHidden = showStop }
        spinner?.isHidden = showStop
    }

    /// Pointing-hand whenever the ring is cancellable — the native inline-click
    /// affordance (no underline). A cursor *rect* is balanced across the view's
    /// lifecycle, unlike `NSCursor.push/pop` which leaks if the view dies hovered.
    override func resetCursorRects() {
        if onStop != nil { addCursorRect(bounds, cursor: .pointingHand) }
    }

    private func makeStopButton() -> NSButton {
        // Sized to sit inside the 16pt box like the ring; grey, not red.
        let cfg = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
        let image = NSImage(systemSymbolName: "xmark.circle.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(cfg)
        let button = NSButton(image: image ?? NSImage(), target: self, action: #selector(stopTapped))
        button.isBordered = false
        button.bezelStyle = .regularSquare
        button.imagePosition = .imageOnly
        button.contentTintColor = .secondaryLabelColor
        button.translatesAutoresizingMaskIntoConstraints = false
        button.isHidden = true
        button.setAccessibilityElement(false)
        return button
    }

    @objc private func stopTapped() { onStop?() }

    // MARK: - Build

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
        ringLayers = [track, fill]
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
        self.spinner = spinner
    }
}
