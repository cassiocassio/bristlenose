import Foundation
import os

/// Native client for `GET /api/projects/1/sessions` — the same endpoint and the
/// same payload the web sessions sidebar consumes.
///
/// ## The (port, token) pair IS the project identity
///
/// This is the **second** native bearer consumer (`MiroAPI` was the first), and
/// the hazard is not the one that bit MiroAPI. That was a *mismatched* pair —
/// fresh sidecar, stale token — which 401s, loudly. The mode that matters here
/// is the **matched-but-stale pair**:
///
/// - `switchProject` **parks** the outgoing sidecar rather than stopping it
///   (`ParkedSidecar.swift`). It stays alive, stays listening on its own port,
///   and keeps accepting its own token.
/// - Project id is always `1` in every sidecar, so the URL carries no
///   disambiguation whatsoever.
///
/// Therefore a stale pair returns **HTTP 200 with the previous project's
/// participant names**, rendered under the current project's title. For a tool
/// whose value proposition is trustworthy attribution of quotes to people, a
/// confidently-wrong list is worse than an empty one.
///
/// Three rules follow, and all three are enforced *inside* `load(identity:)`
/// rather than left to caller discipline:
///
/// 1. **Identity is a `@MainActor` provider, not a value.** `load` reads it at
///    the moment the request is built; there is no `(port, token)` parameter a
///    caller could snapshot early. (`MiroSheet` *does* snapshot, and is safe
///    only because a `.sheet` is window-modal so no switch can occur while it
///    lives. A popover is light-dismiss — that safety does not transfer.)
/// 2. **Key on the port, never `selectedProjectPath`.** The path is set
///    synchronously at `ContentView.swift:701` while `switchProject` runs on a
///    later turn, so a path-keyed fetch fires *inside* the window with the
///    fresh key and the stale credentials. The port and token move together in
///    both write paths, so one provider read is always a coherent pair. This
///    mirrors the WebView's own `.id("\(project.id)-\(port)")` fix.
/// 3. **The post-await re-check happens here.** After the network await, `load`
///    reads the provider AGAIN and compares ports (`SessionsFetchIdentity`).
///    An overtaken fetch returns `nil` — discarded, never rendered — so the
///    caller keeps its previous state rather than publishing another project's
///    data *or* a stale failure.
///
/// A stale-port variant is why this is not merely a correctness nicety: ports
/// are kernel-assigned, so a freed ephemeral port can be reassigned to any
/// other local process — which would then receive an unscoped `/api/*` bearer.
enum SessionsFetchIdentity {

    /// Whether a response may be published. Extracted so the invariant has a
    /// test that fails on a path-keyed implementation and passes on a
    /// port-keyed one — per `feedback_test_the_outcome_not_the_rule`, and
    /// following `RepointDecision` as the in-house precedent for
    /// "decision → testable helper".
    static func shouldPublish(responseFrom requestPort: Int, currentPort: Int?) -> Bool {
        guard let currentPort else { return false }
        return currentPort == requestPort
    }
}

/// What the popover renders. Three states, not eight.
///
/// The eight underlying conditions (never-fetched, in-flight, 200-empty,
/// 401-no-header, 401-stale, connection-refused, 404, decode-failure) collapse
/// to three *user-facing* states, and stay distinct only in the log. The one
/// that must never merge with the others is **`empty`**: a 200 carrying zero
/// sessions is a correct answer and the state a just-imported project is in.
/// Rendering it as the same nothing as a failure teaches the researcher to
/// distrust an accurate screen.
///
/// Deliberately NOT modelled on `MiroAPI.status()`, whose own doc-comment
/// forbids widening its collapse-everything-to-false shape "to a context where
/// 'no token' and 'couldn't tell' must be distinguished". This is exactly that
/// context: the popover is the only session switcher, so "couldn't tell"
/// strands the researcher while "no sessions" is fine.
enum SessionsLoadState: Equatable {
    case loading
    case loaded([SessionsPopoverSpec.Session])
    case empty
    case unreachable
}

struct SessionsAPI {

    private static let log = Logger(subsystem: "app.bristlenose", category: "sessions-popover")

    /// API4: `URLSession.shared`'s cookie jar is port-blind for 127.0.0.1, and
    /// the serve middleware accepts a `bristlenose_auth` cookie fallback on
    /// `/api/*` — so one future native `/report/` fetch through the shared
    /// session would arm a jar that then lets a STALE bearer 200 via the
    /// cookie, masking the exact 401 diagnostic this file exists to preserve.
    /// Ephemeral + cookies off makes that structurally impossible rather than
    /// currently-unexercised. In-house precedent: `LLMValidator.swift:109`,
    /// `OllamaDownloadModel.swift:80`.
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.httpShouldSetCookies = false
        config.httpCookieAcceptPolicy = .never
        config.timeoutIntervalForRequest = 10
        return URLSession(configuration: config)
    }()

    // MARK: - Wire types
    //
    // Narrow by design. Swift's `Decodable` fails the WHOLE payload on one
    // missing required key, and the bundled-sidecar-lag class is live and
    // documented — a bundle predating a Python change serves an older shape
    // under a green freshness gate. Decoding only what we render means schema
    // drift degrades a field rather than blanking the popover. The two
    // required keys — `session_id` (navigation + route memory depend on it)
    // and `session_number` (the row title) — are each a deliberate
    // whole-payload-failure decision; everything else is optional.
    //
    // It also means `source_folder_uri` and `source_files[].path` — absolute
    // paths encoding the username and often the client name — are structurally
    // unable to reach the view, rather than merely unused by it.

    private struct Wire: Decodable {
        let sessions: [WireSession]
    }

    private struct WireSession: Decodable {
        let session_id: String
        let session_number: Int
        let session_date: String?
        let duration_seconds: Double?
        let speakers: [WireSpeaker]?
    }

    private struct WireSpeaker: Decodable {
        let speaker_code: String
        let name: String?
    }

    private struct ErrorBody: Decodable { let detail: String? }

    // MARK: - Fetch

    /// Load the session list for the currently-serving project.
    ///
    /// - Parameter provider: read on the MainActor at request-build time AND
    ///   re-read after the network await for the supersession check — see the
    ///   type doc. Returning nil (no serve, or no token yet) yields
    ///   `.unreachable` **without** sending anything: a request with no
    ///   `Authorization` header 401s with the identical body a wrong-token
    ///   request produces, destroying the one diagnostic signal we have.
    /// - Returns: the state to publish, or **nil when the fetch was overtaken
    ///   by a project switch** — the caller keeps its previous state and never
    ///   renders another project's data (or a stale failure) as current.
    static func load(
        identity provider: @MainActor @Sendable () -> (port: Int, token: String)?
    ) async -> SessionsLoadState? {
        guard let identity = await provider() else {
            log.notice("sessions fetch skipped — no serve identity yet")
            return .unreachable
        }
        let (port, token) = identity

        guard let url = URL(string: "http://127.0.0.1:\(port)/api/projects/1/sessions") else {
            return .unreachable
        }
        var req = URLRequest(url: url)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let outcome: SessionsLoadState
        do {
            let (data, response) = try await session.data(for: req)
            guard let http = response as? HTTPURLResponse else {
                outcome = .unreachable
                return await publish(outcome, requestPort: port, provider: provider)
            }
            if http.statusCode == 200 {
                let wire = try JSONDecoder().decode(Wire.self, from: data)
                let sessions = wire.sessions.map(convert)
                outcome = sessions.isEmpty ? .empty : .loaded(sessions)
            } else {
                // API1: the middleware's detail string is what distinguishes
                // its fixed {"detail":"Unauthorized"} from a route-level 404
                // "Project not found" or a stray foreign process on a reused
                // port — the distinction that identified the MiroAPI bug.
                // Bounded + ASCII-filtered so a foreign process's body cannot
                // spray the log; the port is the only other interpolation.
                log.error("sessions fetch failed — port \(port, privacy: .public), HTTP \(http.statusCode, privacy: .public), detail \(boundedDetail(data), privacy: .public)")
                outcome = .unreachable
            }
        } catch is DecodingError {
            // The coding path would be useful and is also the one error type
            // whose description can quote payload keys — so it stays out.
            log.error("sessions fetch decode failed — port \(port, privacy: .public)")
            outcome = .unreachable
        } catch let urlError as URLError {
            // API3: refused (dead sidecar), timed out (wedged sidecar) and
            // cancelled need different fixes — the code integer keeps them
            // distinct without interpolating anything that could carry PII.
            log.error("sessions fetch transport error — port \(port, privacy: .public), urlError \(urlError.code.rawValue, privacy: .public)")
            outcome = .unreachable
        } catch is CancellationError {
            // A caller-cancelled fetch during a project switch is not a
            // failure; logging it as .error would pollute the log with false
            // alarms on every fast switch.
            log.notice("sessions fetch cancelled — port \(port, privacy: .public)")
            outcome = .unreachable
        } catch {
            log.error("sessions fetch errored — port \(port, privacy: .public)")
            outcome = .unreachable
        }

        return await publish(outcome, requestPort: port, provider: provider)
    }

    /// Rule 3, applied to every network-derived result — including failures: an
    /// overtaken fetch's connection-refused must not mark the NEW project's
    /// popover unreachable any more than its 200 may show the old project's
    /// names.
    private static func publish(
        _ outcome: SessionsLoadState,
        requestPort: Int,
        provider: @MainActor @Sendable () -> (port: Int, token: String)?
    ) async -> SessionsLoadState? {
        let current = await provider()
        guard SessionsFetchIdentity.shouldPublish(responseFrom: requestPort,
                                                  currentPort: current?.port) else {
            log.notice("sessions fetch superseded — port \(requestPort, privacy: .public)")
            return nil
        }
        return outcome
    }

    /// The middleware's `detail` string when the body carries one, else a
    /// bounded printable-ASCII prefix. 120 chars, newlines stripped — enough to
    /// carry every legitimate detail string while a foreign process on a
    /// reused port cannot spray the log.
    private static func boundedDetail(_ data: Data) -> String {
        if let body = try? JSONDecoder().decode(ErrorBody.self, from: data),
           let detail = body.detail, !detail.isEmpty {
            return String(detail.prefix(120))
        }
        let prefix = String(decoding: data.prefix(120), as: UTF8.self)
            .filter { $0.isASCII && !$0.isNewline }
        return prefix.isEmpty ? "<empty body>" : prefix
    }

    /// Participants only. Moderators and observers are deliberately dropped:
    /// this is a switcher keyed on *who was interviewed*, and the moderator is
    /// the same person in nearly every session of a study.
    ///
    /// The filter keys off the **badge code prefix**, not the role string,
    /// matching the server's own convention — `sessions.py:176` (journey
    /// assembly) and `:317` (video map) both select participants with
    /// `startswith("p")`. Verified against all 24 trial-run DBs: zero rows
    /// where a `p`-code and `role == "participant"` disagree in either
    /// direction.
    private static func convert(_ w: WireSession) -> SessionsPopoverSpec.Session {
        let participants = (w.speakers ?? [])
            .filter { $0.speaker_code.hasPrefix("p") }
            .map { SessionsPopoverSpec.Participant(code: $0.speaker_code, name: $0.name) }
        return SessionsPopoverSpec.Session(
            sessionID: w.session_id,
            number: w.session_number,
            isoDate: w.session_date,
            durationSeconds: w.duration_seconds ?? 0,
            participants: participants
        )
    }
}
