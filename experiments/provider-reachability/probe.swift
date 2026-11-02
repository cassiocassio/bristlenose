// Provider-reachability probe. Records what a macOS app can know about its network path
// when an LLM call is refused: path state, DNS answers, system proxy settings, a gateway
// TCP probe, and keyless HTTP requests to the control host and each provider.
//
// KEYLESS BY DESIGN: no request carries a key or user data. The only hosts contacted are
// Apple's captive-portal host, the providers' public endpoints, and anything you pass with
// --url / --azure-host. Output is one JSON document on stdout; progress goes to stderr.
//
//   swiftc -O -swift-version 5 probe.swift -o probe && ./probe --label wifi-off
//
// See README.md for the states to run it in.

import Foundation
import Network
import CFNetwork

// MARK: - arguments

var label = "unlabelled"
var timeout: TimeInterval = 5
var extraTargets: [(String, String)] = []   // name, url
var azureHost: String? = nil
var skipProviders = false
do {
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let a = it.next() {
        switch a {
        case "--label": label = it.next() ?? label
        case "--timeout": timeout = TimeInterval(it.next() ?? "") ?? timeout
        case "--azure-host": azureHost = it.next()
        case "--skip-providers": skipProviders = true
        case "--url":
            // --url name=https://host/path
            if let kv = it.next(), let eq = kv.firstIndex(of: "=") {
                extraTargets.append((String(kv[..<eq]), String(kv[kv.index(after: eq)...])))
            }
        default:
            FileHandle.standardError.write(Data("unknown argument \(a)\n".utf8))
            exit(2)
        }
    }
}

func log(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }
func ms(_ from: Date) -> Int { Int(Date().timeIntervalSince(from) * 1000) }

// MARK: - network path

func samplePath(requiring: NWInterface.InterfaceType? = nil) -> [String: Any] {
    let monitor = requiring.map { NWPathMonitor(requiredInterfaceType: $0) } ?? NWPathMonitor()
    let q = DispatchQueue(label: "path")
    let sem = DispatchSemaphore(value: 0)
    var out: [String: Any] = ["error": "no update within 2 s"]
    var gateways: [String] = []
    monitor.pathUpdateHandler = { p in
        var ifs: [[String: String]] = []
        for i in p.availableInterfaces {
            ifs.append(["name": i.name, "type": "\(i.type)"])
        }
        gateways = p.gateways.map { gw in
            if case let .hostPort(host, _) = gw { return "\(host)" }
            return "\(gw)"
        }
        var reason = "n/a"
        reason = "\(p.unsatisfiedReason)"
        out = [
            "status": "\(p.status)",
            "unsatisfied_reason": reason,
            "supports_dns": p.supportsDNS,
            "supports_ipv4": p.supportsIPv4,
            "supports_ipv6": p.supportsIPv6,
            "is_expensive": p.isExpensive,
            "is_constrained": p.isConstrained,
            "interfaces": ifs,
            "uses_wifi": p.usesInterfaceType(.wifi),
            "uses_wired": p.usesInterfaceType(.wiredEthernet),
            "uses_cellular": p.usesInterfaceType(.cellular),
            "uses_other": p.usesInterfaceType(.other),   // VPN tunnels (utun) show here
            "gateways": gateways,
        ]
        sem.signal()
    }
    monitor.start(queue: q)
    _ = sem.wait(timeout: .now() + 2)
    monitor.cancel()
    return out
}

// MARK: - system proxy

func proxySettings() -> [String: Any] {
    guard let raw = CFNetworkCopySystemProxySettings()?.takeRetainedValue() as? [String: Any]
    else { return ["error": "CFNetworkCopySystemProxySettings returned nil"] }
    // Keep the shape (which proxies are on, their hosts); drop nothing: this file is local.
    return JSONSafe(raw) as? [String: Any] ?? ["raw": "\(raw)"]
}

func JSONSafe(_ v: Any) -> Any {
    switch v {
    case let d as [String: Any]: return d.mapValues(JSONSafe)
    case let a as [Any]: return a.map(JSONSafe)
    case let n as NSNumber: return n
    case let s as String: return s
    default: return "\(v)"
    }
}

// MARK: - DNS

func addrClass(_ s: String) -> String {
    if s == "0.0.0.0" || s == "::" { return "unspecified" }
    if s.hasPrefix("127.") || s == "::1" { return "loopback" }
    if s.hasPrefix("10.") || s.hasPrefix("192.168.") { return "private" }
    if s.hasPrefix("172."), let second = Int(s.split(separator: ".").dropFirst().first ?? ""),
       (16...31).contains(second) { return "private" }
    if s.hasPrefix("169.254.") || s.lowercased().hasPrefix("fe80") { return "link-local" }
    if s.hasPrefix("100."), let second = Int(s.split(separator: ".").dropFirst().first ?? ""),
       (64...127).contains(second) { return "cgnat" }
    if s.lowercased().hasPrefix("fc") || s.lowercased().hasPrefix("fd") { return "unique-local" }
    return "public"
}

func resolve(_ host: String) -> [String: Any] {
    let t0 = Date()
    var result: [String: Any] = ["host": host]
    let sem = DispatchSemaphore(value: 0)
    var done = false
    DispatchQueue.global().async {
        var hints = addrinfo()
        hints.ai_family = AF_UNSPEC
        hints.ai_socktype = SOCK_STREAM
        var res: UnsafeMutablePointer<addrinfo>?
        let rc = getaddrinfo(host, nil, &hints, &res)
        var addrs: [[String: String]] = []
        if rc == 0 {
            var p = res
            while let ai = p {
                var buf = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                if getnameinfo(ai.pointee.ai_addr, ai.pointee.ai_addrlen, &buf, socklen_t(buf.count),
                               nil, 0, NI_NUMERICHOST) == 0 {
                    let s = String(cString: buf)
                    addrs.append(["addr": s, "class": addrClass(s)])
                }
                p = ai.pointee.ai_next
            }
            freeaddrinfo(res)
            result["addresses"] = addrs
        } else {
            result["gai_error"] = Int(rc)
            result["gai_message"] = String(cString: gai_strerror(rc))
        }
        done = true
        sem.signal()
    }
    if sem.wait(timeout: .now() + 8) == .timedOut && !done { result["gai_error"] = "timeout >8 s" }
    result["elapsed_ms"] = ms(t0)
    return result
}

// MARK: - gateway TCP probe

func tcpProbe(host: String, port: UInt16, wait: TimeInterval = 1.5) -> [String: Any] {
    let t0 = Date()
    let conn = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: port)!, using: .tcp)
    let sem = DispatchSemaphore(value: 0)
    var state = "timeout"
    var err = ""
    conn.stateUpdateHandler = { s in
        switch s {
        case .ready: state = "ready"; sem.signal()
        case .failed(let e): state = "failed"; err = "\(e)"; sem.signal()
        case .waiting(let e): state = "waiting"; err = "\(e)"   // ECONNREFUSED / ENETUNREACH land here
        case .cancelled: break
        default: break
        }
    }
    conn.start(queue: DispatchQueue(label: "tcp.\(host).\(port)"))
    _ = sem.wait(timeout: .now() + wait)
    conn.cancel()
    return ["host": host, "port": Int(port), "state": state, "error": err, "elapsed_ms": ms(t0)]
}

// MARK: - HTTP

final class NoRedirect: NSObject, URLSessionTaskDelegate {
    func urlSession(_ s: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection r: HTTPURLResponse, newRequest: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)   // hand back the 3xx itself: that is the portal evidence
    }
}

let urlErrorNames: [Int: String] = [
    -999: "cancelled", -1000: "badURL", -1001: "timedOut", -1002: "unsupportedURL",
    -1003: "cannotFindHost", -1004: "cannotConnectToHost", -1005: "networkConnectionLost",
    -1006: "dnsLookupFailed", -1007: "httpTooManyRedirects", -1008: "resourceUnavailable",
    -1009: "notConnectedToInternet", -1011: "badServerResponse", -1017: "cannotParseResponse",
    -1022: "appTransportSecurityRequiresSecureConnection",
    -1200: "secureConnectionFailed", -1201: "serverCertificateHasBadDate",
    -1202: "serverCertificateUntrusted", -1203: "serverCertificateHasUnknownRoot",
    -1204: "serverCertificateNotYetValid", -1205: "clientCertificateRejected",
    -1206: "clientCertificateRequired",
]

func describe(error e: Error) -> [String: Any] {
    let ns = e as NSError
    var o: [String: Any] = ["domain": ns.domain, "code": ns.code]
    if let n = urlErrorNames[ns.code] { o["name"] = n }
    for k in ["_kCFStreamErrorDomainKey", "_kCFStreamErrorCodeKey"] {
        if let v = ns.userInfo[k] { o[k] = "\(v)" }
    }
    o["has_peer_trust"] = ns.userInfo["NSURLErrorFailingURLPeerTrustErrorKey"] != nil
    var chain: [String] = []
    var cur: NSError? = ns.userInfo[NSUnderlyingErrorKey] as? NSError
    while let u = cur { chain.append("\(u.domain)/\(u.code)"); cur = u.userInfo[NSUnderlyingErrorKey] as? NSError }
    if !chain.isEmpty { o["underlying"] = chain }
    return o
}

func request(name: String, url: String, session: URLSession) async -> [String: Any] {
    var o: [String: Any] = ["name": name, "url": url]
    guard let u = URL(string: url) else { o["error"] = ["name": "badURL"]; return o }
    let t0 = Date()
    var req = URLRequest(url: u)
    req.httpMethod = "GET"
    do {
        let (data, resp) = try await session.data(for: req)
        o["elapsed_ms"] = ms(t0)
        if let h = resp as? HTTPURLResponse {
            o["status"] = h.statusCode
            var headers: [String: String] = [:]
            for (k, v) in h.allHeaderFields { headers["\(k)".lowercased()] = "\(v)" }
            o["headers"] = headers
            // Keyless probes only: bodies are provider error JSON, an HTML page, or "Success".
            o["body_prefix"] = name == "ollama" ? "<omitted: lists local model names>"
                : String(decoding: data.prefix(300), as: UTF8.self)
            o["body_bytes"] = data.count
        } else {
            o["status"] = "non-http-response"
        }
    } catch {
        o["elapsed_ms"] = ms(t0)
        o["error"] = describe(error: error)
    }
    return o
}

// MARK: - run

let t00 = Date()
log("probe: label=\(label) timeout=\(timeout)s")
let info = ProcessInfo.processInfo
var doc: [String: Any] = [
    "label": label,
    "started": ISO8601DateFormatter().string(from: Date()),
    "macos": info.operatingSystemVersionString,
    "sandboxed": info.environment["APP_SANDBOX_CONTAINER_ID"] != nil,
    "sandbox_container_id": info.environment["APP_SANDBOX_CONTAINER_ID"] ?? "",
    "bundle_id": Bundle.main.bundleIdentifier ?? "",
    "ats_dict": (Bundle.main.object(forInfoDictionaryKey: "NSAppTransportSecurity") as Any?).map { "\($0)" } ?? "none",
]

let path = samplePath()
doc["path"] = path
// What the API reports for a path with NO usable route, without touching any setting: ask
// for a cellular-only view (a Mac has no cellular interface). Shows the unsatisfied shape,
// not a real offline state; the real one needs Wi-Fi off (README).
doc["path_cellular_only_demo"] = samplePath(requiring: .cellular)
log("path: \(path["status"] ?? "?")  gateways=\(path["gateways"] ?? [])")

doc["proxy"] = proxySettings()

var hosts = ["captive.apple.com", "api.anthropic.com", "api.openai.com",
             "generativelanguage.googleapis.com"]
if let a = azureHost { hosts.append(a) }
doc["dns"] = hosts.map(resolve)

var gw: [[String: Any]] = []
for g in (path["gateways"] as? [String]) ?? [] where !g.contains(":") || g.contains(".") {
    for port: UInt16 in [53, 80, 443] { gw.append(tcpProbe(host: g, port: port)) }
}
doc["gateway_tcp"] = gw

let cfg = URLSessionConfiguration.ephemeral
cfg.timeoutIntervalForRequest = timeout
cfg.timeoutIntervalForResource = timeout
cfg.waitsForConnectivity = false
let session = URLSession(configuration: cfg, delegate: NoRedirect(), delegateQueue: nil)

var targets: [(String, String)] = [
    ("control-https", "https://captive.apple.com/hotspot-detect.html"),
    ("control-http", "http://captive.apple.com/hotspot-detect.html"),
]
if !skipProviders {
    targets += [
        ("anthropic", "https://api.anthropic.com/v1/models"),
        ("openai", "https://api.openai.com/v1/models"),
        ("gemini", "https://generativelanguage.googleapis.com/v1beta/models"),
        ("ollama", "http://127.0.0.1:11434/api/tags"),
    ]
    if let a = azureHost {
        targets.append(("azure", "https://\(a)/openai/deployments?api-version=2024-10-21"))
    }
}
targets += extraTargets

var results = [[String: Any]](repeating: [:], count: targets.count)
await withTaskGroup(of: (Int, [String: Any]).self) { group in
    for (i, t) in targets.enumerated() {
        group.addTask { (i, await request(name: t.0, url: t.1, session: session)) }
    }
    for await (i, r) in group { results[i] = r }
}
doc["requests"] = results
doc["total_ms"] = ms(t00)

for r in results {
    let n = r["name"] as? String ?? "?"
    if let s = r["status"] { log("  \(n): HTTP \(s) in \(r["elapsed_ms"] ?? "?") ms") }
    else if let e = r["error"] as? [String: Any] { log("  \(n): URLError \(e["code"] ?? "?") \(e["name"] ?? "") in \(r["elapsed_ms"] ?? "?") ms") }
}

let data = try JSONSerialization.data(withJSONObject: JSONSafe(doc), options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
