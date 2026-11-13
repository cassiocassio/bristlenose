import Foundation
import Testing
@testable import Bristlenose

/// No redirects (design-azure-connection §12): the `api-key` header and a POST body must not follow
/// a redirect to another host, so the session refuses every one and the 3xx reads as an HTTP status.
extension AzureKeyCheckHardeningTests {
    @Suite("Azure key check: no redirects", .serialized)
    struct RedirectTests {

        @Test("A redirect is not followed: the key never reaches the other host, and the 3xx reads as an HTTP status")
        func redirectIsRefused() async {
            AzureStub.arm(status: 307, location: "https://evil.example/collect")
            let (status, message) = await AzureKeyCheckHardeningTests.check(AzureKeyCheckHardeningTests.config())
            #expect(AzureStub.seen.count == 1, "only the Azure host was asked")
            #expect(AzureStub.seen.allSatisfy { $0.url?.host == "acme.openai.azure.com" })
            #expect(status == .unavailable)
            #expect(message?.key == "desktop.llmSettings.validation.httpStatus")
            #expect(message?.vars["status"] == "307")
        }

        @Test("Control: a session without the delegate follows the same redirect, so the test above can fail")
        func plainSessionFollows() async {
            AzureStub.arm(status: 307, location: "https://evil.example/collect")
            let cfg = URLSessionConfiguration.ephemeral
            cfg.protocolClasses = [AzureStub.self]
            _ = try? await URLSession(configuration: cfg)
                .data(for: URLRequest(url: URL(string: "https://acme.openai.azure.com/x")!))
            #expect(AzureStub.seen.contains { $0.url?.host == "evil.example" })
        }
    }
}
