import AppKit
import Foundation

// MARK: - Wire model

/// The payload POSTed to the feedback endpoint — identical shape to the React
/// modal (`FeedbackModal.tsx`) and the status-page form. **Exactly**
/// `{version, rating, message}`: no project id, session, path, timestamp, or any
/// identifier ever rides along. This minimisation is a governance contract, not
/// an accident (docs/methodology/consent-gradient.md) — asserted by
/// `FeedbackSubmissionTests.payloadCarriesNoIdentifiers`.
struct FeedbackPayload: Codable, Equatable {
    let version: String
    let rating: String
    let message: String
}

/// The five affective points. Shared taxonomy with the web surfaces — the
/// `rawValue` is the `rating` on the wire, identical to `FeedbackModal.tsx` and
/// `status_page.py`. Native rendering uses the localised text labels (a
/// segmented control), NOT emoji: emoji-as-chrome is off-grid, VoiceOver-hostile,
/// and version/locale-variant (`feedback_native_primitives_first`).
enum FeedbackRating: String, CaseIterable, Identifiable {
    case hate, dislike, neutral, like, love

    var id: String { rawValue }

    /// `common.feedback.*` label key — already translated in every locale.
    var labelKey: String {
        switch self {
        case .hate: return "sentimentHate"
        case .dislike: return "sentimentDislike"
        case .neutral: return "sentimentNeutral"
        case .like: return "sentimentLike"
        case .love: return "sentimentLove"
        }
    }
}

// MARK: - Endpoint validation

enum FeedbackEndpoint {
    /// The native sheet only ever posts to Bristlenose's own feedback host. The
    /// desktop app never overrides `BRISTLENOSE_FEEDBACK_URL` (that env knob is a
    /// CLI affordance, and the CLI uses the web form, not this sheet), so a
    /// value from `/api/health` that isn't `https://bristlenose.app/…` can only
    /// come from a rogue local process answering the auth-exempt health port —
    /// reject it before handing user-typed text to `URLSession`.
    static let allowedHosts: Set<String> = ["bristlenose.app"]

    /// Accept only `https` on an allow-listed host. Rejects `http:`/`javascript:`/
    /// relative values and off-host redirection. Returns nil ⇒ cannot POST (the
    /// sheet falls back to the clipboard).
    static func validate(_ raw: String) -> URL? {
        guard let url = URL(string: raw),
              url.scheme?.lowercased() == "https",
              let host = url.host?.lowercased(),
              allowedHosts.contains(host)
        else { return nil }
        return url
    }
}

// MARK: - Success predicate

enum FeedbackSuccess {
    /// Strict: HTTP **200** + `Content-Type: application/json` + a body that
    /// decodes to `{ "ok": true }`. Everything else is a failure — a captive-
    /// portal / proxy 200 HTML interstitial, a `{"ok":false}` soft-reject, a
    /// 2xx-that-isn't-200, a decode error, a redirect landing page. Mirrors the
    /// hardened web predicate so "sent" always means the server confirmed
    /// receipt, never "the socket returned something."
    static func isSuccess(status: Int, contentType: String?, body: Data) -> Bool {
        guard status == 200,
              (contentType ?? "").lowercased().contains("application/json")
        else { return false }
        struct Ack: Decodable { let ok: Bool }
        return (try? JSONDecoder().decode(Ack.self, from: body))?.ok == true
    }
}

// MARK: - Submission client

enum SubmissionResult: Equatable { case sent, failed }

/// POSTs a `FeedbackPayload` to the (already validated) endpoint. `session` is
/// injectable so tests exercise the predicate against stubbed responses without
/// touching the network.
struct FeedbackClient {
    var session: URLSession = .shared

    func submit(_ payload: FeedbackPayload, to url: URL) async -> SubmissionResult {
        do {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(payload)
            let (data, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            let ok = FeedbackSuccess.isSuccess(
                status: http?.statusCode ?? 0,
                contentType: http?.value(forHTTPHeaderField: "Content-Type"),
                body: data
            )
            return ok ? .sent : .failed
        } catch {
            return .failed
        }
    }
}

// MARK: - Health-derived config

/// Feedback config resolved from the local sidecar's `/api/health` — the single
/// source of truth shared with the web modal and the status-page form. A nil
/// `url` means "cannot POST" (disabled, unreachable, malformed, or off-host);
/// the sheet then offers a clipboard copy instead of silently sending anywhere.
struct FeedbackConfig: Equatable {
    let url: URL?
    let enabled: Bool
    let version: String

    static let unavailable = FeedbackConfig(url: nil, enabled: false, version: "")
}

enum FeedbackHealth {
    /// GET the auth-exempt `/api/health` on loopback and resolve the feedback
    /// config. Any failure (unreachable, non-200, malformed) resolves to
    /// `.unavailable` — we never fall back to a baked URL, so a network blip
    /// can't re-enable a disabled endpoint or bypass the validation above.
    static func load(port: Int, session: URLSession = .shared) async -> FeedbackConfig {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/health") else {
            return .unavailable
        }
        do {
            let (data, response) = try await session.data(from: url)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return .unavailable }
            return parse(data)
        } catch {
            return .unavailable
        }
    }

    /// Pure decode of a `/api/health` body into a `FeedbackConfig`. Split out so
    /// the resolution logic is unit-tested without a live server.
    static func parse(_ data: Data) -> FeedbackConfig {
        struct Health: Decodable {
            struct Feedback: Decodable {
                let enabled: Bool?
                let url: String?
            }
            let version: String?
            let feedback: Feedback?
        }
        guard let health = try? JSONDecoder().decode(Health.self, from: data) else {
            return .unavailable
        }
        let enabled = health.feedback?.enabled ?? false
        // Only resolve a usable URL when feedback is enabled AND the value passes
        // scheme+host validation — otherwise nil (clipboard path).
        let url = enabled ? FeedbackEndpoint.validate(health.feedback?.url ?? "") : nil
        return FeedbackConfig(url: url, enabled: enabled, version: health.version ?? "")
    }
}
