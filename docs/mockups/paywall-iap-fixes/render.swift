// Throwaway renderer for the paywall mockup. Draws the shipped PaywallView
// layout (copied modifier for modifier from PaywallView.swift) and the
// proposed one, with AppKit's real controls, in light and dark, to PNG.
// Usage: probe <desktop.json> <outdir>
import AppKit
import SwiftUI

let args = CommandLine.arguments
let shipped: [String: String] = {
    let d = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[1]))) as! [String: Any]
    return d["subscription"] as! [String: String]
}()
let out = URL(fileURLWithPath: args[2])

// Values StoreKit would hand us (Bristlenose.storekit): displayPrice, displayName,
// and the introductory offer's period, formatted by Foundation, not typed.
let price = "£9.99"
let planName = "Bristlenose Monthly"
let trialLength: String = {
    let f = DateComponentsFormatter(); f.unitsStyle = .full; f.allowedUnits = [.day]
    return f.string(from: DateComponents(day: 7))!
}()

// Proposed new and changed keys (owner to approve).
let proposed: [String: String] = [
    "pricePerMonth": "{{price}} a month",
    "trialLead": "Free for the first {{trial}}.",
    "trialTerms": "Free for {{trial}}, then {{price}} a month until you cancel. Cancel any time in App Store settings, at least a day before the trial ends to avoid being charged. Your AI provider bills you separately for what the analysis uses.",
    "pending": "Waiting for approval. Once it is approved, press Analyse again.",
]

func t(_ key: String, _ vars: [String: String] = [:], new: Bool = false) -> String {
    var s = (new ? proposed[key] : shipped[key]) ?? "<<\(key)>>"
    for (k, v) in vars { s = s.replacingOccurrences(of: "{{\(k)}}", with: v) }
    return s
}

let terms = URL(string: "https://bristlenose.app/terms.html")!

// ---- Shipped layout (PaywallView.offerBody, lines 62-110) ----
struct Shipped: View {
    var trial: Bool
    var message: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(t(trial ? "trialTitle" : "lapsedTitle")).font(.title2.bold())
            if trial {
                Text(t("aiBilling")).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(t(trial ? "trialBody" : "lapsedBody")).fixedSize(horizontal: false, vertical: true)
            if let message {
                Text(message).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button(t("notNow")) {}.keyboardShortcut(.cancelAction)
                Button(t(trial ? "startTrial" : "subscribe")) {}.keyboardShortcut(.defaultAction)
            }
            Text(t(trial ? "trialTerms" : "renewTerms", ["price": price]))
                .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                Link(t("terms"), destination: terms)
                Link(t("privacy"), destination: terms)
                Button(t("restore")) {}.buttonStyle(.link)
                Link(t("manage"), destination: terms)
            }.font(.footnote)
        }
        .padding(24).frame(width: 460)
    }
}

// ---- Proposed layout ----
// The plan name and the billed amount lead; the trial is a plain line under
// them; everything else is the shipped sheet, in the shipped order.
struct Proposed: View {
    var trial: Bool
    var message: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(planName).font(.headline).foregroundStyle(.secondary)
                Text(t("pricePerMonth", ["price": price], new: true)).font(.title2.bold())
                Text(trial ? t("trialLead", ["trial": trialLength], new: true) : t("lapsedTitle"))
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if trial {
                Text(t("aiBilling")).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(t(trial ? "trialBody" : "lapsedBody")).fixedSize(horizontal: false, vertical: true)
            if let message {
                Text(message).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button(t("notNow")) {}.keyboardShortcut(.cancelAction)
                Button(t(trial ? "startTrial" : "subscribe")) {}.keyboardShortcut(.defaultAction)
            }
            Text(trial ? t("trialTerms", ["price": price, "trial": trialLength], new: true)
                       : t("renewTerms", ["price": price]))
                .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                Link(t("terms"), destination: terms)
                Link(t("privacy"), destination: terms)
                Button(t("restore")) {}.buttonStyle(.link)
                Link(t("manage"), destination: terms)
            }.font(.footnote)
        }
        .padding(24).frame(width: 460)
    }
}

// A window that draws as key, so the default button is blue as it is in the
// real sheet, without activating this process or taking focus.
final class KeyWindow: NSWindow {
    override var isKeyWindow: Bool { true }
    override var isMainWindow: Bool { true }
}

@MainActor func render<V: View>(_ view: V, _ name: String, dark: Bool) {
    let host = NSHostingView(rootView: view.environment(\.controlActiveState, .key).background(Color(nsColor: .windowBackgroundColor)))
    host.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
    let size = host.fittingSize
    host.frame = NSRect(origin: .zero, size: size)
    let w = KeyWindow(contentRect: host.frame, styleMask: [.borderless], backing: .buffered, defer: false)
    w.appearance = host.appearance
    w.contentView = host
    w.setFrameOrigin(NSPoint(x: -20000, y: -20000))
    w.orderFrontRegardless()
    host.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.3))
    let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds)!
    host.cacheDisplay(in: host.bounds, to: rep)
    let png = rep.representation(using: .png, properties: [:])!
    let file = out.appendingPathComponent("\(name)-\(dark ? "dark" : "light").png")
    try! png.write(to: file)
    print(file.lastPathComponent, Int(size.width), "x", Int(size.height), "pt;", rep.pixelsWide, "px wide")
    w.orderOut(nil)
}

MainActor.assumeIsolated {
    NSApplication.shared.setActivationPolicy(.prohibited)
    try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    for dark in [false, true] {
        render(Shipped(trial: true), "before-trial", dark: dark)
        render(Proposed(trial: true), "after-trial", dark: dark)
        render(Shipped(trial: false), "before-lapsed", dark: dark)
        render(Proposed(trial: false), "after-lapsed", dark: dark)
        render(Shipped(trial: true, message: t("pending")), "before-pending", dark: dark)
        render(Proposed(trial: true, message: t("pending", new: true)), "after-pending", dark: dark)
    }
}
