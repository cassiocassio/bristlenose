// walker — drives a Mac app through the accessibility interface, inside a tart guest.
//
// Proof of concept for the nightly guest walk (20 Oct 2026): click through the
// app by element name, record the menu tree as text, and screenshot every window,
// so two nights can be diffed. Built on the host, pushed to the guest, run with
// `tart exec`. See experiments/guest-walk/README.md.
//
//   walker trusted                         is this process allowed to use accessibility?
//   walker windows  <bundle>               on-screen windows: id, title, frame
//   walker menus    <bundle>               the whole menu bar as JSON lines (path, enabled, shortcut)
//   walker tree     <bundle> [window-sub]  a window's element tree, one element per line
//   walker press    <bundle> <role> <title-sub> [window-sub]   AXPress the first match
//   walker menu     <bundle> <A>B>C>       press a menu item by path
//   walker wait     <bundle> <window-sub> [seconds]            until a window title matches
//   walker shot     <bundle> <out-dir> <name> [window-sub]     every titled window → <name>[-n].png
//   walker type     <bundle> <text>        type text to the frontmost app
//   walker front    <bundle>               name of the frontmost app
//   walker owners                          every on-screen window and its owning process
//   walker diff     <a.png> <b.png> <out.png>  changed fraction + bbox, pink overlay (host-side)
//   walker set      <bundle> <text>        set the focused element's value (no keystrokes)
//   walker has      <bundle> <window-sub> <text> [seconds]  wait until the tree contains <text>
//   walker key      <bundle> <keys>        type keys to the frontmost app (e.g. "cmd+," or "tab")
//
// Exit codes: 0 done, 1 not found / timed out, 2 usage, 3 not trusted.

import AppKit
import ImageIO
import ApplicationServices
import Foundation

func fail(_ msg: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

// Two copies with one bundle id can be running (a guest reopens yesterday's Debug
// build at login), so the walk targets the copy at WALK_APP, never `.first`.
let walkApp = ProcessInfo.processInfo.environment["WALK_APP"] ?? "/Applications/Bristlenose.app"

func app(_ bundle: String) -> NSRunningApplication {
    let all = NSRunningApplication.runningApplications(withBundleIdentifier: bundle)
    guard let a = all.first(where: { $0.bundleURL?.path == walkApp }) else {
        fail("not running from \(walkApp): \(bundle) (running: \(all.compactMap { $0.bundleURL?.path }))")
    }
    return a
}

func attr(_ el: AXUIElement, _ name: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(el, name as CFString, &v) == .success ? v : nil
}

func str(_ el: AXUIElement, _ name: String) -> String {
    (attr(el, name) as? String) ?? ""
}

func children(_ el: AXUIElement) -> [AXUIElement] {
    (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? []
}

func label(_ el: AXUIElement) -> String {
    for a in [kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute, kAXHelpAttribute] {
        if let s = attr(el, a) as? String, !s.isEmpty { return s }
    }
    return ""
}

func frame(_ el: AXUIElement) -> CGRect? {
    guard let p = attr(el, kAXPositionAttribute), let s = attr(el, kAXSizeAttribute) else { return nil }
    var pt = CGPoint.zero, sz = CGSize.zero
    AXValueGetValue(p as! AXValue, .cgPoint, &pt)
    AXValueGetValue(s as! AXValue, .cgSize, &sz)
    return CGRect(origin: pt, size: sz)
}

func axWindows(_ bundle: String) -> [AXUIElement] {
    let el = AXUIElementCreateApplication(app(bundle).processIdentifier)
    return (attr(el, kAXWindowsAttribute) as? [AXUIElement]) ?? []
}

func window(_ bundle: String, _ sub: String?) -> AXUIElement {
    let ws = axWindows(bundle)
    guard let sub, !sub.isEmpty else {
        guard let w = ws.first else { fail("no windows: \(bundle)") }
        return w
    }
    // Exact title first: "Bristlenose" must not match "Welcome to Bristlenose".
    let exact = ws.first(where: { str($0, kAXTitleAttribute).caseInsensitiveCompare(sub) == .orderedSame })
    guard let w = exact ?? ws.first(where: { str($0, kAXTitleAttribute).localizedCaseInsensitiveContains(sub) }) else {
        fail("no window matching '\(sub)'; have: \(ws.map { str($0, kAXTitleAttribute) })")
    }
    return w
}

func walk(_ el: AXUIElement, depth: Int = 0, _ visit: (AXUIElement, Int) -> Bool) {
    if !visit(el, depth) { return }
    if depth > 40 { return }
    for c in children(el) { walk(c, depth: depth + 1, visit) }
}

// MARK: menus

func menuShortcut(_ el: AXUIElement) -> String {
    let ch = str(el, kAXMenuItemCmdCharAttribute)
    guard !ch.isEmpty else { return "" }
    let mods = (attr(el, kAXMenuItemCmdModifiersAttribute) as? Int) ?? 0
    // kAXMenuItemModifier: 1 shift, 2 option, 4 control, 8 = no command
    var s = ""
    if mods & 4 != 0 { s += "⌃" }
    if mods & 2 != 0 { s += "⌥" }
    if mods & 1 != 0 { s += "⇧" }
    if mods & 8 == 0 { s += "⌘" }
    return s + ch
}

func dumpMenu(_ el: AXUIElement, path: [String]) {
    for item in children(el) {
        let role = str(item, kAXRoleAttribute)
        if role == "AXMenu" { dumpMenu(item, path: path); continue }
        let title = str(item, kAXTitleAttribute)
        if role == "AXMenuItem" && title.isEmpty { continue }  // separators
        if path.isEmpty && title == "Apple" { continue }  // the system's menu, not ours
        let p = path + [title]
        let enabled = (attr(item, kAXEnabledAttribute) as? Bool) ?? false
        let marked = !str(item, kAXMenuItemMarkCharAttribute).isEmpty
        let obj: [String: Any] = [
            "path": p.joined(separator: " ▸ "),
            "enabled": enabled,
            "shortcut": menuShortcut(item),
            "checked": marked,
        ]
        let data = try! JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])
        print(String(data: data, encoding: .utf8)!)
        dumpMenu(item, path: p)
    }
}

func menuBar(_ bundle: String) -> AXUIElement {
    let el = AXUIElementCreateApplication(app(bundle).processIdentifier)
    guard let bar = attr(el, kAXMenuBarAttribute) else { fail("no menu bar") }
    return bar as! AXUIElement
}

func pressMenu(_ bundle: String, _ path: [String]) {
    var cur: AXUIElement = menuBar(bundle)
    for (i, name) in path.enumerated() {
        var found: AXUIElement?
        walk(cur) { el, d in
            if found != nil { return false }
            if d > 0, ["AXMenuBarItem", "AXMenuItem"].contains(str(el, kAXRoleAttribute)),
               str(el, kAXTitleAttribute).trimmingCharacters(in: CharacterSet(charactersIn: ".…"))
                   .caseInsensitiveCompare(name.trimmingCharacters(in: CharacterSet(charactersIn: ".…"))) == .orderedSame {
                found = el; return false
            }
            // only descend through menus, never into a sibling item's submenu
            return d == 0 || str(el, kAXRoleAttribute) == "AXMenu"
        }
        guard let f = found else { fail("menu item not found: \(path[0...i].joined(separator: " ▸ "))") }
        if i == path.count - 1 {
            if (attr(f, kAXEnabledAttribute) as? Bool) == false { fail("menu item disabled: \(path.joined(separator: " ▸ "))") }
            let r = AXUIElementPerformAction(f, kAXPressAction as CFString)
            if r != .success { fail("press failed (\(r.rawValue))") }
        } else {
            cur = f
        }
    }
}

// MARK: keys

func ensureFront(_ a: NSRunningApplication) {
    // Activating an app that is already in front still re-keys its main window,
    // which takes focus off an Open panel's Go-to sheet: only activate when needed.
    if NSWorkspace.shared.frontmostApplication?.processIdentifier != a.processIdentifier {
        a.activate()
        usleep(300_000)
    }
}

func sendKeys(_ bundle: String, _ spec: String) {
    let a = app(bundle)
    ensureFront(a)
    let codes: [String: CGKeyCode] = [
        "tab": 48, "return": 36, "escape": 53, "space": 49, "delete": 51,
        "left": 123, "right": 124, "down": 125, "up": 126, ",": 43, "w": 13, "n": 45, "q": 12,
        "g": 5, "a": 0, "o": 31, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22,
    ]
    for chord in spec.split(separator: " ") {
        let parts = chord.split(separator: "+").map(String.init)
        guard let key = parts.last, let code = codes[key] else { fail("unknown key: \(chord)", 2) }
        var flags: CGEventFlags = []
        for m in parts.dropLast() {
            switch m {
            case "cmd": flags.insert(.maskCommand)
            case "shift": flags.insert(.maskShift)
            case "opt": flags.insert(.maskAlternate)
            case "ctrl": flags.insert(.maskControl)
            default: fail("unknown modifier: \(m)", 2)
            }
        }
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down)!
            e.flags = flags
            // The HID tap, not postToPid: a sandboxed app's Open panel is a separate
            // process, and only the frontmost-app route reaches it.
            e.post(tap: .cghidEventTap)
        }
        usleep(150_000)
    }
}

func typeText(_ bundle: String, _ text: String) {
    ensureFront(app(bundle))
    for ch in text.utf16 {
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: down)!
            var c = ch
            e.keyboardSetUnicodeString(stringLength: 1, unicodeString: &c)
            e.post(tap: .cghidEventTap)
        }
        usleep(20_000)
    }
}

// MARK: windows & screenshots

func cgWindows(_ bundle: String) -> [[String: Any]] {
    let pid = app(bundle).processIdentifier
    let all = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        as? [[String: Any]]) ?? []
    return all.filter { ($0[kCGWindowOwnerPID as String] as? pid_t) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
}

// MARK: main

let args = CommandLine.arguments.dropFirst().map { $0 }
guard let cmd = args.first else { fail("usage: walker <command> …", 2) }
if cmd == "diff" {
    // diff <baseline.png> <tonight.png> <overlay.png>: no accessibility needed.
    // Prints: changed-fraction  bbox(x,y,w,h in px, or -)  size-note
    // The overlay is tonight dimmed to 28% over white with changed pixels in pink.
    // An optional 5th argument masks regions, "x,y,w,h;x,y,w,h" in pixels: differences
    // there are ignored on purpose (a blinking caret, a relative time) and drawn hatched.
    guard args.count >= 4 else { fail("usage: walker diff <a.png> <b.png> <out.png> [masks]", 2) }
    let masks: [CGRect] = (args.count > 4 ? args[4] : "").split(separator: ";").compactMap {
        let n = $0.split(separator: ",").compactMap { Double($0) }
        return n.count == 4 ? CGRect(x: n[0], y: n[1], width: n[2], height: n[3]) : nil
    }
    func load(_ p: String) -> CGImage {
        guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: p) as CFURL, nil),
              let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { fail("cannot read \(p)") }
        return img
    }
    func rgba(_ img: CGImage, _ w: Int, _ h: Int) -> [UInt8] {
        var buf = [UInt8](repeating: 255, count: w * h * 4)
        let ctx = CGContext(data: &buf, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                            space: CGColorSpace(name: CGColorSpace.sRGB)!,
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
        ctx.draw(img, in: CGRect(x: 0, y: h - img.height, width: img.width, height: img.height))
        return buf
    }
    let a = load(args[1]), b = load(args[2])
    let w = max(a.width, b.width), h = max(a.height, b.height)
    let pa = rgba(a, w, h), pb = rgba(b, w, h)
    var out = [UInt8](repeating: 255, count: w * h * 4)
    var changed = 0, minX = w, minY = h, maxX = -1, maxY = -1
    let tol = 24  // per-channel: absorbs antialiasing jitter, not a real change
    for y in 0..<h {
        for x in 0..<w {
            let i = (y * w + x) * 4
            if masks.contains(where: { $0.contains(CGPoint(x: Double(x) + 0.5, y: Double(y) + 0.5)) }) {
                let hatch = (x + y) / 6 % 2 == 0
                let g: UInt8 = hatch ? 200 : 232
                out[i] = g; out[i+1] = g; out[i+2] = g; out[i+3] = 255
                continue
            }
            let d = max(abs(Int(pa[i]) - Int(pb[i])), abs(Int(pa[i+1]) - Int(pb[i+1])), abs(Int(pa[i+2]) - Int(pb[i+2])))
            if d > tol {
                changed += 1
                minX = min(minX, x); maxX = max(maxX, x); minY = min(minY, y); maxY = max(maxY, y)
                out[i] = 255; out[i+1] = 45; out[i+2] = 149; out[i+3] = 255
            } else {
                for c in 0..<3 { out[i+c] = UInt8(255 - (255 - Int(pb[i+c])) * 28 / 100) }
                out[i+3] = 255
            }
        }
    }
    let ctx = CGContext(data: &out, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[3]) as CFURL, "public.png" as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
    CGImageDestinationFinalize(dest)
    let frac = Double(changed) / Double(w * h)
    let bbox = maxX < 0 ? "-" : "\(minX),\(minY),\(maxX - minX + 1),\(maxY - minY + 1)"
    let size = (a.width == b.width && a.height == b.height) ? "" : "size \(a.width)x\(a.height)->\(b.width)x\(b.height)"
    print(String(format: "%.6f", frac) + "\t\(bbox)\t\(size)")
    exit(0)
}
if cmd == "owners" {
    // Every on-screen window and its owner, any app: how a walk notices a system
    // prompt (a privacy alert, a crash reporter) that is not the app under test.
    let all = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        as? [[String: Any]]) ?? []
    for w in all where (w[kCGWindowLayer as String] as? Int ?? 0) >= 0 {
        let pid = w[kCGWindowOwnerPID as String] as? pid_t ?? 0
        let a = NSRunningApplication(processIdentifier: pid)
        let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
        print("\(pid)\t\(w[kCGWindowOwnerName as String] ?? "?")\t\(a?.bundleIdentifier ?? "-")\t\(a?.bundleURL?.path ?? "-")\tlayer=\(w[kCGWindowLayer as String] ?? 0)\t\(b["Width"] ?? 0)x\(b["Height"] ?? 0)\t\(w[kCGWindowName as String] ?? "")")
    }
    exit(0)
}
if cmd == "trusted" {
    // `trusted --prompt` raises the system's Accessibility request, which opens the
    // right pane of System Settings for whoever grants it (SIP-on guests).
    if args.count > 1 && args[1] == "--prompt" {
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(opts)
    }
    print(AXIsProcessTrusted() ? "trusted" : "NOT trusted")
    exit(AXIsProcessTrusted() ? 0 : 3)
}
guard AXIsProcessTrusted() else { fail("accessibility not granted to this process", 3) }
guard args.count >= 2 else { fail("usage: walker \(cmd) <bundle> …", 2) }
let bundle = args[1]

switch cmd {
case "windows":
    for w in cgWindows(bundle) {
        let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
        print("\(w[kCGWindowNumber as String] ?? "?")\t\(w[kCGWindowName as String] ?? "")\t\(b["X"] ?? 0),\(b["Y"] ?? 0) \(b["Width"] ?? 0)x\(b["Height"] ?? 0)")
    }
    for w in axWindows(bundle) { print("ax\t\(str(w, kAXTitleAttribute))\t\(frame(w).map { "\($0)" } ?? "")") }
case "menus":
    dumpMenu(menuBar(bundle), path: [])
case "tree":
    let w = window(bundle, args.count > 2 ? args[2] : nil)
    walk(w) { el, d in
        let role = str(el, kAXRoleAttribute)
        let sub = str(el, kAXSubroleAttribute)
        let id = str(el, kAXIdentifierAttribute)
        let en = (attr(el, kAXEnabledAttribute) as? Bool).map { $0 ? "" : " [disabled]" } ?? ""
        var lab = label(el)
        if role == "AXTextField" && sub == "AXSecureTextField" { lab = "•••" }  // never print a secret
        lab = lab.replacingOccurrences(of: "\n", with: " ")
        if lab.count > 80 { lab = String(lab.prefix(80)) + "…" }
        print(String(repeating: "  ", count: d) + role + (sub.isEmpty ? "" : "/\(sub)")
              + (lab.isEmpty ? "" : " \"\(lab)\"") + (id.isEmpty ? "" : " #\(id)") + en)
        return true
    }
case "press":
    guard args.count >= 4 else { fail("usage: walker press <bundle> <role> <title-sub> [window-sub]", 2) }
    let w = window(bundle, args.count > 4 ? args[4] : nil)
    var hit: AXUIElement?
    walk(w) { el, _ in
        if hit != nil { return false }
        // The role argument matches a role or a subrole (AXCloseButton has no title);
        // an empty title matches any.
        let roleOK = str(el, kAXRoleAttribute) == args[2] || str(el, kAXSubroleAttribute) == args[2]
        if roleOK, args[3].isEmpty || label(el).localizedCaseInsensitiveContains(args[3]) { hit = el; return false }
        return true
    }
    guard let h = hit else { fail("no \(args[2]) matching '\(args[3])'") }
    // Accessibility accepts a press on a disabled button and does nothing, so a
    // walk would log "pressed Add" with the panel still open. Refuse instead.
    if (attr(h, kAXEnabledAttribute) as? Bool) == false { fail("\(args[2]) \"\(label(h))\" is disabled") }
    let r = AXUIElementPerformAction(h, kAXPressAction as CFString)
    if r != .success { fail("press failed (\(r.rawValue))") }
    print("pressed \(args[2]) \"\(label(h))\"")
case "action":
    // action <bundle> <role> <title-sub> <AXAction> [window-sub]: e.g. AXIncrement on a slider
    guard args.count >= 5 else { fail("usage: walker action <bundle> <role> <title-sub> <AXAction> [window-sub]", 2) }
    let w = window(bundle, args.count > 5 ? args[5] : nil)
    var hit: AXUIElement?
    walk(w) { el, _ in
        if hit != nil { return false }
        let roleOK = str(el, kAXRoleAttribute) == args[2] || str(el, kAXSubroleAttribute) == args[2]
        if roleOK, args[3].isEmpty || label(el).localizedCaseInsensitiveContains(args[3]) { hit = el; return false }
        return true
    }
    guard let h = hit else { fail("no \(args[2]) matching '\(args[3])'") }
    let r = AXUIElementPerformAction(h, args[4] as CFString)
    if r != .success { fail("\(args[4]) failed (\(r.rawValue))") }
    print("\(args[4]) on \(args[2]) \"\(label(h))\"")
case "select":
    // select <bundle> <text> [window-sub]: select the list/outline row whose subtree
    // contains <text>, through AXSelected (a row has no press action).
    guard args.count >= 3 else { fail("usage: walker select <bundle> <text> [window-sub]", 2) }
    let w = window(bundle, args.count > 3 ? args[3] : nil)
    var row: AXUIElement?
    walk(w) { el, _ in
        if row != nil { return false }
        guard str(el, kAXRoleAttribute) == "AXRow" else { return true }
        var hit = false
        walk(el) { c, _ in
            if hit { return false }
            if label(c).caseInsensitiveCompare(args[2]) == .orderedSame { hit = true; return false }
            return true
        }
        if hit { row = el }
        return false
    }
    guard let r = row else { fail("no row containing '\(args[2])'") }
    let res = AXUIElementSetAttributeValue(r, kAXSelectedAttribute as CFString, kCFBooleanTrue)
    if res != .success { fail("select failed (\(res.rawValue))") }
    print("selected row '\(args[2])'")
case "menu":
    guard args.count >= 3 else { fail("usage: walker menu <bundle> 'A>B'", 2) }
    pressMenu(bundle, args[2].split(separator: ">").map { $0.trimmingCharacters(in: .whitespaces) })
    print("pressed \(args[2])")
case "wait":
    guard args.count >= 3 else { fail("usage: walker wait <bundle> <window-sub> [seconds]", 2) }
    let deadline = Date().addingTimeInterval(Double(args.count > 3 ? args[3] : "20") ?? 20)
    while Date() < deadline {
        if NSRunningApplication.runningApplications(withBundleIdentifier: bundle).contains(where: { $0.bundleURL?.path == walkApp }),
           axWindows(bundle).contains(where: { str($0, kAXTitleAttribute).localizedCaseInsensitiveContains(args[2]) }) {
            print("window '\(args[2])' present"); exit(0)
        }
        usleep(250_000)
    }
    fail("timed out waiting for window '\(args[2])'")
case "shot":
    guard args.count >= 4 else { fail("usage: walker shot <bundle> <out-dir> <name>", 2) }
    try? FileManager.default.createDirectory(atPath: args[2], withIntermediateDirectories: true)
    var ws = cgWindows(bundle)
    if args.count > 4 {
        ws = ws.filter { (($0[kCGWindowName as String] as? String) ?? "").localizedCaseInsensitiveContains(args[4]) }
    } else {
        // A sheet is its own untitled window, but it is drawn into its parent's
        // capture as well; capturing both doubles every sheet in the diff. The
        // accessibility window list tells them apart: a sheet is never in it (it is
        // an AXSheet child), a standalone untitled window (About) always is. Window
        // geometry cannot: About sits inside the main window's frame.
        let axFrames = axWindows(bundle).compactMap { frame($0) }
        ws = ws.filter { w in
            if !(((w[kCGWindowName as String] as? String) ?? "").isEmpty) { return true }
            let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
            let r = CGRect(x: b["X"] as? Double ?? 0, y: b["Y"] as? Double ?? 0,
                           width: b["Width"] as? Double ?? 0, height: b["Height"] as? Double ?? 0)
            return axFrames.contains { abs($0.minX - r.minX) < 2 && abs($0.minY - r.minY) < 2
                && abs($0.width - r.width) < 2 && abs($0.height - r.height) < 2 }
        }
    }
    if ws.isEmpty { fail("no on-screen windows to capture") }
    for (i, w) in ws.enumerated() {
        let id = w[kCGWindowNumber as String] as! Int
        let title = (w[kCGWindowName as String] as? String) ?? ""
        let file = "\(args[2])/\(args[3])\(ws.count > 1 ? "-\(i + 1)" : "").png"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        p.arguments = ["-x", "-o", "-l", "\(id)", file]
        try! p.run(); p.waitUntilExit()
        print("\(file)\t\(title)\trc=\(p.terminationStatus)")
    }
case "set":
    // Set the focused element's value in one accessibility call: no keystrokes, so
    // nothing can land in the wrong field (typing into a panel beeps per character).
    guard args.count >= 3 else { fail("usage: walker set <bundle> <text>", 2) }
    let appEl = AXUIElementCreateApplication(app(bundle).processIdentifier)
    guard let f = attr(appEl, kAXFocusedUIElementAttribute) else { fail("no focused element") }
    let fe = f as! AXUIElement
    let r = AXUIElementSetAttributeValue(fe, kAXValueAttribute as CFString, args[2] as CFString)
    if r != .success { fail("set value failed (\(r.rawValue)) on \(str(fe, kAXRoleAttribute))") }
    print("set \(str(fe, kAXRoleAttribute)) value (\(args[2].count) characters)")
case "has":
    // has <bundle> <window-sub> <text>: does the window's tree contain a line with <text>?
    guard args.count >= 4 else { fail("usage: walker has <bundle> <window-sub> <text> [seconds]", 2) }
    let deadline = Date().addingTimeInterval(Double(args.count > 4 ? args[4] : "0") ?? 0)
    repeat {
        var found = false
        if let w = axWindows(bundle).first(where: { str($0, kAXTitleAttribute).localizedCaseInsensitiveContains(args[2]) }) {
            walk(w) { el, _ in
                if found { return false }
                let line = "\(str(el, kAXRoleAttribute)) \(label(el)) #\(str(el, kAXIdentifierAttribute))"
                if line.localizedCaseInsensitiveContains(args[3]) { found = true; return false }
                return true
            }
        }
        if found { print("found '\(args[3])'"); exit(0) }
        usleep(250_000)
    } while Date() < deadline
    fail("'\(args[3])' not in window '\(args[2])'")
case "type":
    guard args.count >= 3 else { fail("usage: walker type <bundle> <text>", 2) }
    typeText(bundle, args[2])
    print("typed \(args[2].count) characters")
case "front":
    // The frontmost app's name, so a walk can tell when a panel or another app took focus.
    print(NSWorkspace.shared.frontmostApplication?.localizedName ?? "?")
case "key":
    guard args.count >= 3 else { fail("usage: walker key <bundle> <keys>", 2) }
    sendKeys(bundle, args[2])
    print("sent \(args[2])")
default:
    fail("unknown command: \(cmd)", 2)
}
