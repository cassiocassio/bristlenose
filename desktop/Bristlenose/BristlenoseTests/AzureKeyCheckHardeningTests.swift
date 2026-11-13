import Foundation
import Testing
@testable import Bristlenose

/// The Mac's Azure key check (design-azure-connection §12 and §13, 13 Nov 2026). This file holds
/// the parent suite, and the stub the network-facing children share. R9 (the cache key) is in
/// `LLMValidatorTests`, beside the other cache tests, because they all swap the one global
/// `LLMValidator.verdictStore` and only a suite's own `.serialized` keeps them apart. Later commits
/// add the https-only and the no-redirect children as extensions of this suite.
///
/// `.serialized` on the parent because the stub's request log is process-wide static state, and a
/// nested child is serialised with it (the `CloudTransportTests` precedent, desktop/gotchas.md).
@Suite("Azure key check", .serialized)
struct AzureKeyCheckHardeningTests {

    /// Answers every request with the armed reply and records what it was asked. A 3xx reply
    /// carries a `Location`, and the stub takes the protocol's own redirect path, so the session's
    /// task delegate decides, as it does against a real server.
    final class AzureStub: URLProtocol, @unchecked Sendable {
        nonisolated(unsafe) static var reply: (status: Int, location: String?) = (200, nil)
        nonisolated(unsafe) static var requests: [URLRequest] = []
        private static let lock = NSLock()

        static func arm(status: Int, location: String? = nil) {
            lock.lock(); defer { lock.unlock() }
            reply = (status, location); requests = []
        }
        static var seen: [URLRequest] { lock.lock(); defer { lock.unlock() }; return requests }

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func stopLoading() {}
        override func startLoading() {
            Self.lock.lock()
            Self.requests.append(request)
            let (status, location) = Self.reply
            Self.lock.unlock()
            guard let url = request.url else { return }
            var headers: [String: String] = [:]
            if let location { headers["Location"] = location }
            let response = HTTPURLResponse(
                url: url, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
            if let location, let next = URL(string: location), (300..<400).contains(status) {
                client?.urlProtocol(self, wasRedirectedTo: URLRequest(url: next), redirectResponse: response)
                // A refused redirect leaves the 3xx as the answer, as a real server's would be.
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: Data())
                client?.urlProtocolDidFinishLoading(self)
            } else {
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: Data())
                client?.urlProtocolDidFinishLoading(self)
            }
        }
    }

    static func config(
        _ endpoint: String = "https://acme.openai.azure.com",
        deployment: String = "prod", apiVersion: String = "2024-10-21"
    ) -> LLMValidator.AzureConfig {
        .init(endpoint: endpoint, apiVersion: apiVersion, deployment: deployment)
    }

    /// One check through the production session builder, with the stub answering.
    static func check(_ cfg: LLMValidator.AzureConfig) async -> (ProviderStatus, FailureMessage?) {
        await LLMValidator.validate(
            provider: .azure, key: "not-a-real-key-123", azureConfig: cfg,
            session: LLMValidator.makeSession(protocolClasses: [AzureStub.self]))
    }

    private func config(
        _ endpoint: String = "https://acme.openai.azure.com",
        deployment: String = "prod", apiVersion: String = "2024-10-21"
    ) -> LLMValidator.AzureConfig {
        Self.config(endpoint, deployment: deployment, apiVersion: apiVersion)
    }

    // MARK: (d) the session is injectable

    @Test("An injected session carries the check: the request reaches it, key in the header")
    func injectedSessionIsUsed() async {
        AzureStub.arm(status: 200)
        let (status, _) = await Self.check(config())
        #expect(status == .online)
        #expect(AzureStub.seen.count == 1)
        #expect(AzureStub.seen.first?.url?.host == "acme.openai.azure.com")
        #expect(AzureStub.seen.first?.value(forHTTPHeaderField: "api-key") == "not-a-real-key-123")
    }
}
