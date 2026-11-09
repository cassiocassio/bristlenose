import Foundation
import Testing
@testable import Bristlenose

/// N162 (owner go, 9 Nov 2026): the Mac's Azure key check used `GET /openai/deployments`, a data-plane
/// call Microsoft retired in 2023 (the last version reported working was 2023-03-15-preview), so it
/// probably answered 404 on every resource, which the app reads as "wrong endpoint" and blocks Azure for
/// every Mac user. It now posts one token to the deployment, as Python's doctor does, so a 401 is the key
/// and a 404 is the deployment or endpoint. Unproven against a live resource: no Azure resource was
/// available, which is why a 400 is deliberately left as `.unavailable`.
struct AzureKeyCheckRequestTests {
    private func request(
        deployment: String = "prod-eastus",
        endpoint: String = "https://acme.openai.azure.com/",
        apiVersion: String = "2024-10-21"
    ) throws -> URLRequest {
        try LLMValidator.buildRequest(
            provider: .azure, key: "not-a-real-key-123",
            azureConfig: .init(endpoint: endpoint, apiVersion: apiVersion, deployment: deployment))
    }

    @Test("The check posts to the deployment's chat completions, not the retired list call")
    func postsToTheDeployment() throws {
        let req = try request()
        #expect(req.httpMethod == "POST")
        #expect(req.url?.absoluteString
                == "https://acme.openai.azure.com/openai/deployments/prod-eastus/chat/completions?api-version=2024-10-21")
        #expect(req.url?.path.hasSuffix("/chat/completions") == true)
        #expect(req.url?.absoluteString.contains("/openai/deployments?") == false)
    }

    @Test("The key goes in the api-key header, never the URL")
    func keyIsAHeader() throws {
        let req = try request()
        #expect(req.value(forHTTPHeaderField: "api-key") == "not-a-real-key-123")
        #expect(req.url?.absoluteString.contains("not-a-real-key") == false)
        #expect(req.value(forHTTPHeaderField: "Content-Type") == "application/json")
    }

    @Test("It asks for one token and sends the inert prompt")
    func oneTokenBody() throws {
        let req = try request()
        let body = try #require(req.httpBody)
        let json = try #require(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        #expect(json["max_tokens"] as? Int == 1)
        let messages = try #require(json["messages"] as? [[String: String]])
        #expect(messages == [["role": "user", "content": "."]])
    }

    @Test("A deployment name is percent-encoded into the path, and a trailing slash on the endpoint is dropped")
    func encodesTheDeployment() throws {
        let req = try request(deployment: "my deploy/v2", endpoint: " https://acme.openai.azure.com// ")
        let url = try #require(req.url?.absoluteString)
        #expect(url.hasPrefix("https://acme.openai.azure.com/openai/deployments/my%20deploy%2Fv2/chat/completions"))
    }

    @Test("An empty API version falls back to 2024-10-21")
    func defaultAPIVersion() throws {
        #expect(try request(apiVersion: "").url?.absoluteString.hasSuffix("api-version=2024-10-21") == true)
    }

    @Test("No deployment means no request")
    func noDeploymentNoRequest() {
        #expect(throws: URLError.self) { _ = try request(deployment: "   ") }
    }

    @Test("A missing deployment is not set up, not a verdict, and never reaches the network")
    func missingDeploymentIsUnavailable() async {
        let (status, _) = await LLMValidator.validate(
            provider: .azure, key: "not-a-real-key-123",
            azureConfig: .init(endpoint: "https://acme.openai.azure.com", apiVersion: "2024-10-21", deployment: ""))
        #expect(status == .notSetUp)
    }

    @Test("401 is the key, 404 is the deployment or endpoint, and a 400 is not a verdict on either")
    func verdicts() {
        #expect(LLMValidator.classify(provider: .azure, status: 401).0 == .invalid)
        #expect(LLMValidator.classify(provider: .azure, status: 404).0 == .invalid)
        #expect(LLMValidator.classify(provider: .azure, status: 404).1?.key == "desktop.llmSettings.validation.azureNotFound")
        #expect(LLMValidator.classify(provider: .azure, status: 200).0 == .online)
        #expect(LLMValidator.classify(provider: .azure, status: 400).0 == .unavailable)
    }
}
