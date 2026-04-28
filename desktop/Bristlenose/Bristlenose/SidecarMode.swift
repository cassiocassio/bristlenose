import Foundation

/// How `ServeManager` should connect to `bristlenose serve`.
///
/// Decided once at `ServeManager.init()` from caller-supplied dev env
/// strings + bundle layout, stored as a property, switched on at every
/// call site. Three cases:
///
/// - `.bundled`: the PyInstaller sidecar inside the `.app`. What TestFlight ships.
/// - `.devSidecar`: a developer-specified binary (usually a venv-installed
///   `bristlenose`). Debug builds only. Exercises the full subprocess flow
///   without rebuilding the PyInstaller bundle.
/// - `.external`: a `bristlenose serve` already running on localhost.
///   Debug builds only. No subprocess — fast CSS/React iteration.
///
/// The two dev cases are gated at the caller via `#if DEBUG`:
/// `ServeManager.init` only reads `BRISTLENOSE_DEV_*` env vars under
/// `#if DEBUG`; in Release it passes `nil` for both raw strings so only
/// `.bundled` can be returned. The env-var string literals therefore live
/// solely inside `#if DEBUG`-guarded code and are stripped from the
/// Release Mach-O. `desktop/scripts/check-release-binary.sh` verifies this
/// at archive time.
enum SidecarMode: Equatable {
    case bundled(path: URL)
    case devSidecar(path: URL)
    case external(port: Int)

    /// Human-readable summary for the startup log line.
    var logDescription: String {
        switch self {
        case .bundled(let path):
            return "bundled, path=\(path.path)"
        case .devSidecar(let path):
            return "dev-sidecar, path=\(path.path)"
        case .external(let port):
            return "external-server, port=\(port)"
        }
    }
}

/// Reasons `SidecarMode.resolve` can fail.
enum SidecarResolveError: Error, Equatable, LocalizedError, CustomStringConvertible {
    /// Both dev env vars were set. Pick one.
    case bothDevEnvVarsSet

    /// External-port raw string was not a valid port (1–65535).
    case invalidExternalPort(String)

    /// Dev-sidecar raw path failed validation (non-existent, relative,
    /// directory, non-executable, etc.).
    case invalidSidecarPath(path: String, reason: String)

    /// No dev env set and the bundled sidecar is missing from the `.app`.
    case bundledSidecarMissing(expectedPath: String)

    var description: String {
        switch self {
        case .bothDevEnvVarsSet:
            return "Both dev env vars are set — pick one."
        case .invalidExternalPort(let value):
            return "Dev external port is not a valid port number: \(value)"
        case .invalidSidecarPath(let path, let reason):
            return "Dev sidecar path is not a usable executable: \(path) — \(reason)"
        case .bundledSidecarMissing(let expectedPath):
            return "Bundled sidecar missing at \(expectedPath)"
        }
    }

    /// SwiftUI error cards read `localizedDescription`, which is backed by
    /// `errorDescription` when the type conforms to `LocalizedError`.
    var errorDescription: String? { description }
}

extension SidecarMode {

    /// Path inside `Bundle.main.resourceURL` of the bundled sidecar executable.
    /// Exposed for tests and for error messages.
    static let bundledRelativePath = "bristlenose-sidecar/bristlenose-sidecar"

    /// Pure resolver. No `ProcessInfo`, no `Bundle` lookup — everything
    /// passed in so the unit tests exercise every branch with synthetic
    /// inputs, and so the caller (not the resolver) owns the policy of
    /// when dev env vars may be read.
    ///
    /// - Parameters:
    ///   - externalPortRaw: Raw value of the dev external-port env var, or
    ///     `nil` if unset. Callers must pass `nil` in Release builds.
    ///   - sidecarPathRaw: Raw value of the dev sidecar-path env var, or
    ///     `nil` if unset. Callers must pass `nil` in Release builds.
    ///   - bundleResourceURL: `Bundle.main.resourceURL` at runtime. `nil`
    ///     if running without a bundle (some unit-test contexts).
    ///   - fileManager: Defaults to `.default`; injected for tests.
    static func resolve(
        externalPortRaw: String?,
        sidecarPathRaw: String?,
        bundleResourceURL: URL?,
        fileManager: FileManager = .default
    ) -> Result<SidecarMode, SidecarResolveError> {
        if externalPortRaw != nil && sidecarPathRaw != nil {
            return .failure(.bothDevEnvVarsSet)
        }

        if let portStr = externalPortRaw {
            guard let port = Int(portStr), (1...65535).contains(port) else {
                return .failure(.invalidExternalPort(portStr))
            }
            return .success(.external(port: port))
        }

        if let rawPath = sidecarPathRaw {
            switch validateSidecarPath(rawPath, fileManager: fileManager) {
            case .success(let url):
                return .success(.devSidecar(path: url))
            case .failure(let error):
                return .failure(error)
            }
        }

        // Bundled mode: default for every Release launch.
        guard let resourceURL = bundleResourceURL else {
            return .failure(
                .bundledSidecarMissing(expectedPath: "Resources/\(bundledRelativePath)")
            )
        }
        let bundled = resourceURL.appendingPathComponent(bundledRelativePath)
        if fileManager.isExecutableFile(atPath: bundled.path) {
            return .success(.bundled(path: bundled))
        }
        return .failure(.bundledSidecarMissing(expectedPath: bundled.path))
    }

    /// Validate a dev-sidecar path. Tilde-expand, reject relative paths,
    /// reject directories, require executable bit.
    private static func validateSidecarPath(
        _ rawPath: String,
        fileManager: FileManager
    ) -> Result<URL, SidecarResolveError> {
        let trimmed = rawPath.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            return .failure(.invalidSidecarPath(path: rawPath, reason: "empty path"))
        }

        let expanded = (trimmed as NSString).expandingTildeInPath
        guard expanded.hasPrefix("/") else {
            return .failure(.invalidSidecarPath(path: rawPath, reason: "not an absolute path"))
        }

        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: expanded, isDirectory: &isDirectory) else {
            return .failure(.invalidSidecarPath(path: expanded, reason: "no such file"))
        }
        if isDirectory.boolValue {
            return .failure(.invalidSidecarPath(path: expanded, reason: "path is a directory"))
        }
        guard fileManager.isExecutableFile(atPath: expanded) else {
            return .failure(.invalidSidecarPath(path: expanded, reason: "not executable"))
        }

        return .success(URL(fileURLWithPath: expanded))
    }
}
