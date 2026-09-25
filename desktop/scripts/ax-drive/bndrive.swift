// bndrive — drive the REAL Bristlenose.app over the Accessibility API.
// Usage: bndrive <cmd> [args]   (needs Accessibility trust for the caller)
import AppKit
import ApplicationServices
import Foundation

let appName = "Bristlenose"
if CommandLine.arguments.dropFirst().first == "trusted" { print("AXIsProcessTrusted:", AXIsProcessTrusted()); exit(0) }
let wantPid = ProcessInfo.processInfo.environment["BNDRIVE_PID"].flatMap { Int32($0) }
let candidates = NSRunningApplication.runningApplications(withBundleIdentifier: "app.bristlenose")
guard let running = wantPid.flatMap({ p in candidates.first(where: { $0.processIdentifier == p }) })
        ?? (candidates.count == 1 ? candidates.first : nil) else {
    print("ERR: need BNDRIVE_PID; running instances:", candidates.map { "\($0.processIdentifier) \($0.bundleURL?.path ?? "?")" }); exit(2)
}
let pid = running.processIdentifier
let app = AXUIElementCreateApplication(pid)
AXUIElementSetMessagingTimeout(app, 5)

func attr(_ el: AXUIElement, _ name: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(el, name as CFString, &v) == .success ? v : nil
}
func str(_ el: AXUIElement, _ name: String) -> String? {
    guard let v = attr(el, name) else { return nil }
    if let s = v as? String { return s }
    if let n = v as? NSNumber { return n.stringValue }
    if let a = v as? [String] { return a.joined(separator: ",") }
    return nil
}
func kids(_ el: AXUIElement) -> [AXUIElement] { (attr(el, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func frame(_ el: AXUIElement) -> CGRect? {
    guard let p = attr(el, kAXPositionAttribute), let s = attr(el, kAXSizeAttribute) else { return nil }
    var pt = CGPoint.zero; var sz = CGSize.zero
    AXValueGetValue(p as! AXValue, .cgPoint, &pt); AXValueGetValue(s as! AXValue, .cgSize, &sz)
    return CGRect(origin: pt, size: sz)
}
func role(_ el: AXUIElement) -> String { str(el, kAXRoleAttribute) ?? "?" }
func mainWindow() -> AXUIElement? {
    if let w = attr(app, kAXMainWindowAttribute) { return (w as! AXUIElement) }
    if let w = attr(app, kAXFocusedWindowAttribute) { return (w as! AXUIElement) }
    return (attr(app, kAXWindowsAttribute) as? [AXUIElement])?.first
}
func fmt(_ r: CGRect?, origin: CGPoint) -> String {
    guard let r else { return "frame=nil" }
    return String(format: "x=%.0f y=%.0f w=%.0f h=%.0f (winX=%.0f)", r.minX, r.minY, r.width, r.height, r.minX - origin.x)
}
func describe(_ el: AXUIElement, origin: CGPoint) -> String {
    var parts: [String] = [role(el)]
    if let s = str(el, kAXSubroleAttribute) { parts.append("sub=\(s)") }
    if let s = str(el, kAXTitleAttribute), !s.isEmpty { parts.append("title=\"\(s.prefix(40))\"") }
    if let s = str(el, kAXDescriptionAttribute), !s.isEmpty { parts.append("desc=\"\(s.prefix(40))\"") }
    if let s = str(el, kAXIdentifierAttribute), !s.isEmpty { parts.append("id=\(s)") }
    if let s = str(el, "AXDOMIdentifier"), !s.isEmpty { parts.append("dom#\(s)") }
    if let s = str(el, "AXDOMClassList"), !s.isEmpty { parts.append("dom.\(s.prefix(80))") }
    if let s = str(el, kAXValueAttribute), !s.isEmpty, s.count < 30 { parts.append("val=\(s)") }
    if let s = str(el, kAXOrientationAttribute) { parts.append("orient=\(s)") }
    if let h = attr(el, kAXHiddenAttribute) as? Bool, h { parts.append("HIDDEN") }
    parts.append(fmt(frame(el), origin: origin))
    return parts.joined(separator: " ")
}
func walk(_ el: AXUIElement, depth: Int, maxDepth: Int, webDepth: Int, origin: CGPoint, inWeb: Bool, webStart: Int = -1, line: (String) -> Void) {
    let r = role(el)
    let nowWeb = inWeb || r == "AXWebArea"
    let ws = (!inWeb && nowWeb) ? depth : webStart
    line(String(repeating: "  ", count: depth) + describe(el, origin: origin))
    if nowWeb { if depth - ws >= webDepth { return } } else if depth >= maxDepth { return }
    for k in kids(el) { walk(k, depth: depth + 1, maxDepth: maxDepth, webDepth: webDepth, origin: origin, inWeb: nowWeb, webStart: ws, line: line) }
}
func collect(_ el: AXUIElement, into out: inout [AXUIElement], maxN: Int = 20000) {
    if out.count > maxN { return }
    out.append(el)
    for k in kids(el) { collect(k, into: &out, maxN: maxN) }
}
func matches(_ el: AXUIElement, _ q: String) -> Bool {
    let hay = [str(el, kAXRoleAttribute), str(el, kAXTitleAttribute), str(el, kAXDescriptionAttribute),
               str(el, kAXIdentifierAttribute), str(el, "AXDOMIdentifier"), str(el, "AXDOMClassList"), str(el, kAXValueAttribute)]
        .compactMap { $0 }.joined(separator: " ").lowercased()
    return hay.contains(q.lowercased())
}
func setFrame(_ win: AXUIElement, pos: CGPoint?, size: CGSize?) {
    if var p = pos { AXUIElementSetAttributeValue(win, kAXPositionAttribute as CFString, AXValueCreate(.cgPoint, &p)!) }
    if var s = size { AXUIElementSetAttributeValue(win, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &s)!) }
}
func activate() {
    running.activate(options: [.activateIgnoringOtherApps])
    usleep(150_000)
}
func postKey(_ code: CGKeyCode, flags: CGEventFlags) {
    activate()
    let src = CGEventSource(stateID: .hidSystemState)
    let d = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true)!; d.flags = flags; d.post(tap: .cghidEventTap)
    usleep(30_000)
    let u = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false)!; u.flags = flags; u.post(tap: .cghidEventTap)
}
func drag(from a: CGPoint, to b: CGPoint, steps: Int, holdMs: UInt32) {
    activate()
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: a, mouseButton: .left)!.post(tap: .cghidEventTap)
    usleep(120_000)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: a, mouseButton: .left)!.post(tap: .cghidEventTap)
    usleep(holdMs * 1000)
    for i in 1...max(steps, 1) {
        let t = CGFloat(i) / CGFloat(max(steps, 1))
        let p = CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t)
        CGEvent(mouseEventSource: src, mouseType: .leftMouseDragged, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
        usleep(16_000)
    }
    usleep(80_000)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: b, mouseButton: .left)!.post(tap: .cghidEventTap)
}
func click(_ p: CGPoint) {
    activate()
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
    usleep(60_000)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
    usleep(50_000)
    CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
}

let args = Array(CommandLine.arguments.dropFirst())
guard let cmd = args.first else {
    print("""
    cmds: trusted | window | tree [depth] [webDepth] | find <substr> [webDepth] | summary
          resize W H | move X Y | frame X Y W H
          press <substr>            (AXPress on first matching button)
          key <char> [cmd] [alt] [shift] [ctrl]
          menu <menuTitleSubstr> <itemSubstr>
          drag x1 y1 x2 y2 [steps] [holdMs] | click x y
          splitters | splitter <n> <value>
    """); exit(0)
}
if cmd == "trusted" { print("AXIsProcessTrusted:", AXIsProcessTrusted()); exit(0) }
guard AXIsProcessTrusted() else { print("ERR: not AX-trusted"); exit(3) }
guard let win = mainWindow() else { print("ERR: no main window"); exit(4) }
let wf = frame(win) ?? .zero
let origin = wf.origin

switch cmd {
case "activate":
    activate(); print("activated; isActive=\(running.isActive)")
case "window":
    print("pid=\(pid) title=\"\(str(win, kAXTitleAttribute) ?? "")\" \(fmt(wf, origin: origin))")
    let scr = NSScreen.main?.frame ?? .zero
    print("screen w=\(Int(scr.width)) h=\(Int(scr.height))")
case "tree":
    let d = args.count > 1 ? Int(args[1]) ?? 8 : 8
    let wd = args.count > 2 ? Int(args[2]) ?? 0 : 0
    walk(win, depth: 0, maxDepth: d, webDepth: wd, origin: origin, inWeb: false) { print($0) }
case "find":
    guard args.count > 1 else { print("need substr"); exit(1) }
    var all: [AXUIElement] = []; collect(win, into: &all)
    for el in all where matches(el, args[1]) { print(describe(el, origin: origin)) }
case "summary":
    print("WINDOW \(fmt(wf, origin: origin))")
    var all: [AXUIElement] = []; collect(win, into: &all)
    for el in all {
        let r = role(el)
        if ["AXSplitGroup", "AXSplitter", "AXWebArea", "AXOutline", "AXTable", "AXList", "AXToolbar", "AXScrollArea"].contains(r) {
            print(describe(el, origin: origin))
        }
        if r == "AXSplitGroup" { for k in kids(el) { print("  child: " + describe(k, origin: origin)) } }
        if r == "AXWebArea" { for k in kids(el) { print("  web child: " + describe(k, origin: origin)) } }
    }
    for cls in ["layout", "sidebar", "bn-sidebar", "toolbar", "minimap", "panel"] {
        for el in all where (str(el, "AXDOMClassList") ?? "").lowercased().split(separator: ",").contains(where: { $0 == cls || $0.hasPrefix(cls + "-") || $0.hasPrefix("bn-" + cls) }) {
            print("  DOM[\(cls)]: " + describe(el, origin: origin))
        }
    }
case "resize":
    setFrame(win, pos: nil, size: CGSize(width: Double(args[1])!, height: Double(args[2])!))
    usleep(400_000); print("now " + fmt(frame(win), origin: origin))
case "move":
    setFrame(win, pos: CGPoint(x: Double(args[1])!, y: Double(args[2])!), size: nil)
    usleep(300_000); print("now " + fmt(frame(win), origin: origin))
case "frame":
    setFrame(win, pos: CGPoint(x: Double(args[1])!, y: Double(args[2])!), size: CGSize(width: Double(args[3])!, height: Double(args[4])!))
    usleep(400_000); print("now " + fmt(frame(win), origin: origin))
case "press":
    var all: [AXUIElement] = []; collect(win, into: &all)
    guard let b = all.first(where: { role($0) == "AXButton" && matches($0, args[1]) }) else { print("no button matching \(args[1])"); exit(1) }
    print("pressing " + describe(b, origin: origin))
    let r = AXUIElementPerformAction(b, kAXPressAction as CFString); print("result=\(r.rawValue)")
case "key":
    let map: [String: CGKeyCode] = ["s": 1, "l": 37, "w": 13, "n": 45, "a": 0, "f": 3, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "left": 123, "right": 124, "esc": 53]
    guard let code = map[args[1].lowercased()] else { print("unknown key"); exit(1) }
    var flags: CGEventFlags = []
    if args.contains("cmd") { flags.insert(.maskCommand) }
    if args.contains("alt") { flags.insert(.maskAlternate) }
    if args.contains("shift") { flags.insert(.maskShift) }
    if args.contains("ctrl") { flags.insert(.maskControl) }
    postKey(code, flags: flags); print("sent")
case "menu":
    guard let bar = attr(app, kAXMenuBarAttribute) else { print("no menubar"); exit(1) }
    let menus = kids(bar as! AXUIElement)
    guard let m = menus.first(where: { (str($0, kAXTitleAttribute) ?? "").lowercased().contains(args[1].lowercased()) }) else {
        print("menus: " + menus.compactMap { str($0, kAXTitleAttribute) }.joined(separator: " | ")); exit(1)
    }
    let items = kids(m).flatMap { kids($0) }
    if args.count < 3 { for it in items { print(describe(it, origin: origin)) }; exit(0) }
    guard let it = items.first(where: { (str($0, kAXTitleAttribute) ?? "").lowercased().contains(args[2].lowercased()) }) else {
        print("items: " + items.compactMap { str($0, kAXTitleAttribute) }.filter { !$0.isEmpty }.joined(separator: " | ")); exit(1)
    }
    print("pressing menu item \"\(str(it, kAXTitleAttribute) ?? "")\" enabled=\(str(it, kAXEnabledAttribute) ?? "?")")
    let r = AXUIElementPerformAction(it, kAXPressAction as CFString); print("result=\(r.rawValue)")
case "drag":
    let steps = args.count > 5 ? Int(args[5]) ?? 20 : 20
    let hold = args.count > 6 ? UInt32(args[6]) ?? 150 : 150
    drag(from: CGPoint(x: Double(args[1])!, y: Double(args[2])!), to: CGPoint(x: Double(args[3])!, y: Double(args[4])!), steps: steps, holdMs: hold)
    print("dragged")
case "click":
    click(CGPoint(x: Double(args[1])!, y: Double(args[2])!)); print("clicked")
case "splitters":
    var all: [AXUIElement] = []; collect(win, into: &all)
    for (i, el) in all.filter({ role($0) == "AXSplitter" }).enumerated() {
        var settable: DarwinBoolean = false
        AXUIElementIsAttributeSettable(el, kAXValueAttribute as CFString, &settable)
        print("[\(i)] " + describe(el, origin: origin) + " valueSettable=\(settable) min=\(str(el, kAXMinValueAttribute) ?? "?") max=\(str(el, kAXMaxValueAttribute) ?? "?")")
    }
case "splitter":
    var all: [AXUIElement] = []; collect(win, into: &all)
    let sp = all.filter { role($0) == "AXSplitter" }
    let el = sp[Int(args[1])!]
    let r = AXUIElementSetAttributeValue(el, kAXValueAttribute as CFString, NSNumber(value: Double(args[2])!))
    usleep(300_000); print("set result=\(r.rawValue) now " + describe(el, origin: origin))
default:
    print("unknown cmd")
}
