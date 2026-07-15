import Foundation
import Testing

@testable import Bristlenose

// The native feedback sheet's testable core: endpoint validation, the strict
// success predicate, /api/health config resolution, and payload minimisation.
// These are the branches the silent-failure + security reviews flagged — pinned
// here so they can't quietly regress.

@Suite("FeedbackEndpoint.validate")
struct FeedbackEndpointTests {
    @Test("accepts https on the allow-listed host")
    func acceptsHttpsAllowedHost() {
        #expect(FeedbackEndpoint.validate("https://bristlenose.app/feedback.php") != nil)
    }

    @Test(
        "rejects non-https, off-host, and non-absolute values",
        arguments: [
            "http://bristlenose.app/feedback.php",   // scheme downgrade
            "https://evil.example/collect",          // hijacked /api/health host
            "javascript:alert(1)",                   // injection
            "/feedback.php",                         // relative
            "ftp://bristlenose.app/x",               // wrong scheme
            "",
        ]
    )
    func rejectsBadURLs(raw: String) {
        #expect(FeedbackEndpoint.validate(raw) == nil)
    }
}

@Suite("FeedbackSuccess.isSuccess")
struct FeedbackSuccessTests {
    private func data(_ s: String) -> Data { Data(s.utf8) }

    @Test("200 + application/json + {ok:true} is the ONLY success")
    func strictSuccess() {
        #expect(FeedbackSuccess.isSuccess(
            status: 200, contentType: "application/json", body: data(#"{"ok":true}"#)))
    }

    @Test("200 HTML interstitial (captive portal / proxy) is a failure")
    func htmlInterstitialFails() {
        #expect(!FeedbackSuccess.isSuccess(
            status: 200,
            contentType: "text/html",
            body: data("<html>Sign in to WiFi</html>")))
    }

    @Test("200 + {ok:false} soft-reject is a failure")
    func okFalseFails() {
        #expect(!FeedbackSuccess.isSuccess(
            status: 200, contentType: "application/json", body: data(#"{"ok":false}"#)))
    }

    @Test("200 + {} (missing key) is a failure")
    func missingKeyFails() {
        #expect(!FeedbackSuccess.isSuccess(
            status: 200, contentType: "application/json", body: data("{}")))
    }

    @Test("2xx-that-isn't-200 is a failure")
    func non200Fails() {
        #expect(!FeedbackSuccess.isSuccess(
            status: 202, contentType: "application/json", body: data(#"{"ok":true}"#)))
        #expect(!FeedbackSuccess.isSuccess(
            status: 500, contentType: "application/json", body: data(#"{"ok":true}"#)))
    }

    @Test("json content-type with charset param still counts")
    func charsetContentType() {
        #expect(FeedbackSuccess.isSuccess(
            status: 200,
            contentType: "application/json; charset=utf-8",
            body: data(#"{"ok":true}"#)))
    }
}

@Suite("FeedbackHealth.parse")
struct FeedbackHealthParseTests {
    private func data(_ s: String) -> Data { Data(s.utf8) }

    @Test("enabled + valid url resolves a usable config")
    func enabledValid() {
        let cfg = FeedbackHealth.parse(data(#"""
        {"version":"1.2.3","feedback":{"enabled":true,"url":"https://bristlenose.app/feedback.php"}}
        """#))
        #expect(cfg.enabled)
        #expect(cfg.version == "1.2.3")
        #expect(cfg.url?.absoluteString == "https://bristlenose.app/feedback.php")
    }

    @Test("disabled ⇒ no URL even if one is present")
    func disabledNoURL() {
        let cfg = FeedbackHealth.parse(data(#"""
        {"version":"1.2.3","feedback":{"enabled":false,"url":"https://bristlenose.app/feedback.php"}}
        """#))
        #expect(!cfg.enabled)
        #expect(cfg.url == nil)
    }

    @Test("enabled but off-host url ⇒ nil URL (validation still applies)")
    func enabledBadHost() {
        let cfg = FeedbackHealth.parse(data(#"""
        {"version":"9","feedback":{"enabled":true,"url":"https://evil.example/x"}}
        """#))
        #expect(cfg.enabled)
        #expect(cfg.url == nil)
        #expect(cfg.version == "9")
    }

    @Test("malformed / empty body ⇒ unavailable")
    func malformed() {
        #expect(FeedbackHealth.parse(data("not json")) == .unavailable)
        #expect(FeedbackHealth.parse(Data()) == .unavailable)
    }
}

@Suite("FeedbackRedirect.allow")
struct FeedbackRedirectTests {
    private func req(_ s: String) -> URLRequest { URLRequest(url: URL(string: s)!) }

    @Test("follows a same-host https redirect")
    func followsSameHost() {
        #expect(FeedbackRedirect.allow(req("https://bristlenose.app/feedback-2.php")) != nil)
    }

    @Test(
        "cancels off-host, scheme-downgrade, and non-https redirects",
        arguments: [
            "https://evil.example/collect",   // off-host exfil target
            "http://bristlenose.app/x",        // https → http downgrade
            "https://bristlenose.app.evil.co/x", // look-alike host
            "ftp://bristlenose.app/x",         // wrong scheme
        ]
    )
    func cancelsBadRedirects(target: String) {
        #expect(FeedbackRedirect.allow(req(target)) == nil)
    }
}

@Suite("FeedbackPayload")
struct FeedbackPayloadTests {
    @Test("encodes exactly {version, rating, message} — no identifiers")
    func payloadCarriesNoIdentifiers() throws {
        let payload = FeedbackPayload(version: "1.0.0", rating: "like", message: "clear")
        let json = try JSONEncoder().encode(payload)
        let obj = try #require(
            try JSONSerialization.jsonObject(with: json) as? [String: Any])
        #expect(Set(obj.keys) == ["version", "rating", "message"])
        // Guard against a project id / session / path ever creeping in.
        for forbidden in ["project", "project_id", "session", "path", "researcher", "id"] {
            #expect(obj[forbidden] == nil)
        }
    }
}
