import Foundation
import Testing
@testable import Bristlenose

/// Coverage for the two pure decision functions that pick which UX the pill
/// shows: `classify` (URL error → which failure popover copy) and
/// `isFinalizing` (daemon stream status → "Finishing" vs "Downloading").
/// Both are the *triggering* logic behind states that are otherwise awkward to
/// reproduce by hand, so they earn unit tests.
@Suite("Ollama download model")
struct OllamaDownloadModelTests {

    private func isGeneric(_ failure: OllamaDownloadModel.Failure) -> Bool {
        if case .generic = failure { return true }
        return false
    }

    // MARK: - classify: URLError → Failure

    @Test func classify_offlineCodes_mapToNoInternet() {
        #expect(OllamaDownloadModel.classify(URLError(.notConnectedToInternet)) == .noInternet)
        #expect(OllamaDownloadModel.classify(URLError(.networkConnectionLost)) == .noInternet)
        #expect(OllamaDownloadModel.classify(URLError(.dataNotAllowed)) == .noInternet)
    }

    @Test func classify_timeout_mapsToTimedOut() {
        #expect(OllamaDownloadModel.classify(URLError(.timedOut)) == .timedOut)
    }

    @Test func classify_hostUnreachable_mapsToCantReach() {
        #expect(OllamaDownloadModel.classify(URLError(.cannotConnectToHost)) == .cantReach)
        #expect(OllamaDownloadModel.classify(URLError(.cannotFindHost)) == .cantReach)
    }

    @Test func classify_otherURLError_isGeneric() {
        #expect(isGeneric(OllamaDownloadModel.classify(URLError(.badServerResponse))))
    }

    @Test func classify_nonURLError_isGeneric() {
        struct Boom: Error {}
        #expect(isGeneric(OllamaDownloadModel.classify(Boom())))
    }

    @Test func classify_genericCarriesTheMessage() {
        let err = NSError(domain: "ollama", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "daemon exploded"])
        #expect(OllamaDownloadModel.classify(err) == .generic("daemon exploded"))
    }

    // MARK: - isFinalizing: stream status → finishing vs downloading

    @Test func isFinalizing_postDownloadStages_areTrue() {
        #expect(OllamaDownloadModel.isFinalizing("verifying sha256 digest"))
        #expect(OllamaDownloadModel.isFinalizing("writing manifest"))
        #expect(OllamaDownloadModel.isFinalizing("removing unused layers"))
        #expect(OllamaDownloadModel.isFinalizing("success"))
    }

    @Test func isFinalizing_isCaseInsensitive() {
        #expect(OllamaDownloadModel.isFinalizing("Verifying SHA256 Digest"))
        #expect(OllamaDownloadModel.isFinalizing("SUCCESS"))
    }

    @Test func isFinalizing_downloadStages_areFalse() {
        // The initial manifest fetch and the byte-moving layer pulls must stay
        // in `.downloading` — otherwise the bar would flip to a spinner early.
        #expect(!OllamaDownloadModel.isFinalizing("pulling manifest"))
        #expect(!OllamaDownloadModel.isFinalizing("pulling 2af3b81862c6"))
        #expect(!OllamaDownloadModel.isFinalizing(""))
    }
}
