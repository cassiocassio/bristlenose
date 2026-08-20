// Antenna activity-blink prototype — timing rig, not shippable code.
//
// A/B: the SAME envelope and the SAME traffic drive two treatments side by side.
//   LEFT  — colour ramp. Tint lerps secondary -> system accent. Glyph static.
//   RIGHT — radiating waves. Tint stays at baseline; the arcs sweep outward.
//
// No glyph surgery: `antenna.radiowaves.left.and.right` is a variable-value
// symbol. Measured 20 Aug 2026 by rendering 0...1 in 0.05 steps and diffing the
// PNGs — exactly THREE distinct renderings, with edges at 0.0 / 0.05 / 0.55:
//     0.0  mast only
//     0.3  mast + inner arc pair
//     1.0  mast + both arc pairs
// So the "sweep" is a 3-frame flipbook, not a continuous ramp. That is the
// thing to judge: three frames of ~2pt arcs at caption1 size.
//
// Three row styles in each strip, because the peak colour is contested:
// SidebarPalette.accentOverride's doc-comment records that Default theme
// "preserves the system's backgroundStyle-driven icon tinting (selected row ->
// system accent)", and Edo forces accent on EVERY row's icon.
//
// Metrics from ProjectCellSpec: caption1 subtitle, 16pt identity icon, 20pt
// icon column, 32pt single-line pitch, 4pt trailing inset.
//
//   swiftc -O AntennaBlink.swift -o antenna-blink && ./antenna-blink

import AppKit

// MARK: - Envelope

struct Envelope {
    var attack: Double = 0.18      // ramp to peak on first call of a burst
    var hold: Double = 4.0         // RETRIGGERABLE — any new call resets it
    var release: Double = 0.50     // peak -> baseline
    var gap: Double = 0.90         // silence before the sign-off taps
    var tapUp: Double = 0.15
    var tapHold: Double = 0.20
    var tapDown: Double = 0.30
    var tapGap: Double = 0.45
    var taps: Int = 2
    var signOff: Bool = true

    /// Scripted level for `t` seconds after the hold expired. nil = finished.
    func afterHold(_ t: Double) -> Double? {
        if t < release { return 1 - ease(t / release) }
        var c = release
        guard signOff else { return t < c ? 0 : nil }
        c += gap
        if t < c { return 0 }
        let unit = tapUp + tapHold + tapDown + tapGap
        for _ in 0..<taps {
            if t < c + tapUp { return ease((t - c) / tapUp) }
            if t < c + tapUp + tapHold { return 1 }
            if t < c + tapUp + tapHold + tapDown { return 1 - ease((t - c - tapUp - tapHold) / tapDown) }
            if t < c + unit { return 0 }
            c += unit
        }
        return nil
    }

    private func ease(_ x: Double) -> Double {
        let c = min(max(x, 0), 1)
        return c < 0.5 ? 2 * c * c : 1 - pow(-2 * c + 2, 2) / 2
    }
}

// MARK: - One mock source-list row

final class RowView: NSView {
    enum Style { case plain, selected, edo }
    enum Treatment { case colour, waves }

    private let icon = NSImageView()
    private let title = NSTextField(labelWithString: "")
    private let subtitle = NSTextField(labelWithString: "")
    private let antenna = NSImageView()
    private let style: Style
    private let treatment: Treatment

    /// The three measured variable-value frames, built once.
    private static let waveFrames: [NSImage?] = {
        let cfg = NSImage.SymbolConfiguration(
            pointSize: NSFont.preferredFont(forTextStyle: .caption1).pointSize, weight: .regular)
        return [0.0, 0.3, 1.0].map {
            NSImage(systemSymbolName: "antenna.radiowaves.left.and.right",
                    variableValue: $0, accessibilityDescription: nil)?
                .withSymbolConfiguration(cfg)
        }
    }()

    var baseline: NSColor = .secondaryLabelColor

    init(style: Style, treatment: Treatment, name: String, sub: String) {
        self.style = style
        self.treatment = treatment
        super.init(frame: .zero)
        wantsLayer = true

        let iconCfg = NSImage.SymbolConfiguration(pointSize: 16, weight: .regular)
        icon.image = NSImage(systemSymbolName: "folder", accessibilityDescription: nil)?
            .withSymbolConfiguration(iconCfg)
        // The collision, reproduced.
        switch style {
        case .plain:    icon.contentTintColor = .labelColor
        case .selected: icon.contentTintColor = .controlAccentColor
        case .edo:      icon.contentTintColor = NSColor(srgbRed: 0.11, green: 0.27, blue: 0.47, alpha: 1)
        }

        title.font = .preferredFont(forTextStyle: .body)
        title.stringValue = name
        title.textColor = .labelColor
        subtitle.font = .preferredFont(forTextStyle: .caption1)
        subtitle.stringValue = sub
        subtitle.textColor = .secondaryLabelColor

        antenna.image = Self.waveFrames[2]        // at rest: both arc pairs
        antenna.contentTintColor = baseline

        for v in [icon, title, subtitle, antenna] {
            v.translatesAutoresizingMaskIntoConstraints = false
            addSubview(v)
        }
        NSLayoutConstraint.activate([
            icon.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 10),
            icon.widthAnchor.constraint(equalToConstant: 20),
            icon.centerYAnchor.constraint(equalTo: centerYAnchor),
            title.leadingAnchor.constraint(equalTo: icon.trailingAnchor, constant: 6),
            title.topAnchor.constraint(equalTo: topAnchor, constant: 4),
            subtitle.leadingAnchor.constraint(equalTo: title.leadingAnchor),
            subtitle.topAnchor.constraint(equalTo: title.bottomAnchor, constant: 1),
            antenna.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -4),
            antenna.centerYAnchor.constraint(equalTo: subtitle.centerYAnchor),
        ])
    }
    required init?(coder: NSCoder) { fatalError() }

    override func draw(_ dirty: NSRect) {
        guard style == .selected else { return }
        NSColor.unemphasizedSelectedContentBackgroundColor.setFill()
        NSBezierPath(roundedRect: bounds.insetBy(dx: 6, dy: 2), xRadius: 5, yRadius: 5).fill()
    }

    /// `level` 0 = at rest, 1 = peak. `phase` 0..<1 is the wave sweep position.
    func apply(level: Double, phase: Double) {
        switch treatment {
        case .colour:
            antenna.contentTintColor = Self.lerp(baseline, .controlAccentColor, level)
        case .waves:
            // Tint held at baseline so the A/B isolates ONE variable.
            antenna.contentTintColor = baseline
            if level <= 0.05 {
                antenna.image = Self.waveFrames[2]          // rest = full glyph
            } else {
                let frame = min(2, Int(phase * 3))
                antenna.image = Self.waveFrames[frame]
            }
        }
    }

    private static func lerp(_ a: NSColor, _ b: NSColor, _ t: Double) -> NSColor {
        guard let x = a.usingColorSpace(.sRGB), let y = b.usingColorSpace(.sRGB) else { return a }
        let t = CGFloat(min(max(t, 0), 1))
        return NSColor(srgbRed: x.redComponent + (y.redComponent - x.redComponent) * t,
                       green: x.greenComponent + (y.greenComponent - x.greenComponent) * t,
                       blue: x.blueComponent + (y.blueComponent - x.blueComponent) * t,
                       alpha: 1)
    }
}

// MARK: - Controller

final class Rig: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var rows: [RowView] = []
    private var env = Envelope()
    private var lastCall: Date?
    private var level: Double = 0
    private var wavePhase: Double = 0
    private var sweepPeriod: Double = 0.9
    private var lastTick = Date()
    private var timer: Timer?
    private var quantise = false
    private var pending: [Date] = []
    private let readout = NSTextField(labelWithString: "")

    private let projects: [(RowView.Style, String, String)] = [
        (.plain,    "Onboarding study",   "12 sessions"),
        (.selected, "Q3 diary study",     "8 sessions"),
        (.edo,      "Pricing (Edo)",      "5 sessions"),
    ]

    func applicationDidFinishLaunching(_ n: Notification) {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 880, height: 600),
                          styleMask: [.titled, .closable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Antenna blink — colour ramp vs radiating waves"

        let root = NSStackView()
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 14
        root.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)

        // --- the two strips, side by side ------------------------------------
        let strips = NSStackView(views: [makeStrip(.colour, "Colour ramp"),
                                         makeStrip(.waves, "Radiating waves (3 frames)")])
        strips.orientation = .horizontal
        strips.alignment = .top
        strips.spacing = 24
        root.addArrangedSubview(strips)

        // --- triggers ---------------------------------------------------------
        root.addArrangedSubview(label("Traffic — the two shapes measured in bristlenose.log", bold: true))
        let trig = NSStackView(views: [
            button("1 call", #selector(fireOne)),
            button("burst — 6 in 1s", #selector(fireBurst)),
            button("spread — 3 over 10s", #selector(fireSpread)),
        ])
        trig.spacing = 8
        root.addArrangedSubview(trig)

        let q = NSButton(checkboxWithTitle: "Quantise to a 1.5s poll (what the host actually sees)",
                         target: self, action: #selector(toggleQuantise))
        root.addArrangedSubview(q)
        let s = NSButton(checkboxWithTitle: "Sign-off taps", target: self, action: #selector(toggleSignOff))
        s.state = .on
        root.addArrangedSubview(s)

        // --- sliders ----------------------------------------------------------
        root.addArrangedSubview(label("Envelope (drives BOTH treatments)", bold: true))
        let grid = NSGridView(numberOfColumns: 3, rows: 0)
        addSlider(grid, "attack", 0.02, 0.60, env.attack) { self.env.attack = $0 }
        addSlider(grid, "hold (retriggerable)", 0.5, 10.0, env.hold) { self.env.hold = $0 }
        addSlider(grid, "release", 0.1, 2.0, env.release) { self.env.release = $0 }
        addSlider(grid, "gap before taps", 0.1, 2.0, env.gap) { self.env.gap = $0 }
        addSlider(grid, "tap up", 0.05, 0.5, env.tapUp) { self.env.tapUp = $0 }
        addSlider(grid, "tap hold", 0.05, 0.6, env.tapHold) { self.env.tapHold = $0 }
        addSlider(grid, "tap down", 0.05, 0.8, env.tapDown) { self.env.tapDown = $0 }
        addSlider(grid, "tap gap", 0.1, 1.2, env.tapGap) { self.env.tapGap = $0 }
        addSlider(grid, "wave sweep period", 0.3, 2.5, sweepPeriod) { self.sweepPeriod = $0 }
        root.addArrangedSubview(grid)

        readout.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        readout.textColor = .secondaryLabelColor
        root.addArrangedSubview(readout)

        window.contentView = root
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }

    private func makeStrip(_ treatment: RowView.Treatment, _ caption: String) -> NSView {
        let strip = NSStackView()
        strip.orientation = .vertical
        strip.alignment = .leading
        strip.spacing = 0
        for (style, name, sub) in projects {
            let r = RowView(style: style, treatment: treatment, name: name, sub: sub)
            r.heightAnchor.constraint(equalToConstant: 33).isActive = true
            r.widthAnchor.constraint(equalToConstant: 260).isActive = true
            strip.addArrangedSubview(r)
            rows.append(r)
        }
        let box = NSStackView(views: [label(caption, bold: true), strip])
        box.orientation = .vertical
        box.alignment = .leading
        box.spacing = 6
        return box
    }

    // MARK: traffic

    @objc private func fireOne() { schedule([0]) }
    @objc private func fireBurst() { schedule([0, 0.08, 0.15, 0.31, 0.52, 0.90]) }   // the 17:14:33 shape
    @objc private func fireSpread() { schedule([0, 8, 10]) }                          // the 11:27 shape

    private func schedule(_ offsets: [Double]) {
        let now = Date()
        pending.append(contentsOf: offsets.map { now.addingTimeInterval($0) })
    }

    @objc private func toggleQuantise(_ s: NSButton) { quantise = s.state == .on }
    @objc private func toggleSignOff(_ s: NSButton) { env.signOff = s.state == .on }

    // MARK: loop

    private func tick() {
        let now = Date()
        let dt = now.timeIntervalSince(lastTick)
        lastTick = now

        let due = pending.filter { $0 <= now }
        if !due.isEmpty {
            pending.removeAll { $0 <= now }
            if quantise {
                let grid = 1.5
                let snapped = Date(timeIntervalSinceReferenceDate:
                    (now.timeIntervalSinceReferenceDate / grid).rounded(.up) * grid)
                pending.append(snapped)
            } else {
                if lastCall == nil { wavePhase = 0 }   // sweep starts at the burst
                lastCall = now
            }
        }

        var scripted: Double? = nil
        if let last = lastCall {
            let e = now.timeIntervalSince(last)
            if e < env.hold {
                level += (1 - level) * min(1, dt / max(env.attack, 0.001))
            } else if let v = env.afterHold(e - env.hold) {
                scripted = v
            } else {
                scripted = 0
                lastCall = nil
            }
        } else {
            scripted = 0
        }
        if let v = scripted { level = v }

        wavePhase = level > 0.05 ? (wavePhase + dt / max(sweepPeriod, 0.05)).truncatingRemainder(dividingBy: 1) : 0
        for r in rows { r.apply(level: level, phase: wavePhase) }

        let phase: String
        if let last = lastCall {
            let e = now.timeIntervalSince(last)
            phase = e < env.hold ? String(format: "HOLD  %.1fs left", env.hold - e)
                                 : String(format: "SIGN-OFF  +%.2fs", e - env.hold)
        } else { phase = "idle" }
        readout.stringValue = String(format: "level %.2f   wave %.2f   %@   queued %d",
                                     level, wavePhase, phase, pending.count)
    }

    // MARK: chrome helpers

    private func label(_ s: String, bold: Bool = false) -> NSTextField {
        let t = NSTextField(labelWithString: s)
        t.font = bold ? .boldSystemFont(ofSize: 12) : .systemFont(ofSize: 12)
        if !bold { t.textColor = .secondaryLabelColor }
        return t
    }

    private func button(_ title: String, _ sel: Selector) -> NSButton {
        NSButton(title: title, target: self, action: sel)
    }

    private var sinks: [NSSlider: (Double) -> Void] = [:]
    private var valueLabels: [NSSlider: NSTextField] = [:]

    private func addSlider(_ grid: NSGridView, _ name: String, _ lo: Double, _ hi: Double,
                           _ start: Double, _ sink: @escaping (Double) -> Void) {
        let s = NSSlider(value: start, minValue: lo, maxValue: hi,
                         target: self, action: #selector(sliderMoved(_:)))
        s.widthAnchor.constraint(equalToConstant: 240).isActive = true
        let v = NSTextField(labelWithString: String(format: "%.2fs", start))
        v.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        sinks[s] = sink
        valueLabels[s] = v
        grid.addRow(with: [label(name), s, v])
    }

    @objc private func sliderMoved(_ s: NSSlider) {
        sinks[s]?(s.doubleValue)
        valueLabels[s]?.stringValue = String(format: "%.2fs", s.doubleValue)
    }
}

let app = NSApplication.shared
let rig = Rig()
app.delegate = rig
app.setActivationPolicy(.regular)
app.run()
