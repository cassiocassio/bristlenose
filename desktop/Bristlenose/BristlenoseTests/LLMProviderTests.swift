import Testing
@testable import Bristlenose

@MainActor
@Suite("LLM provider definitions")
struct LLMProviderTests {

    // MARK: - Raw values match config keys

    @Test func rawValues_matchConfigKeys() {
        #expect(LLMProvider.claude.rawValue == "anthropic")
        #expect(LLMProvider.chatGPT.rawValue == "openai")
        #expect(LLMProvider.gemini.rawValue == "google")
        #expect(LLMProvider.azure.rawValue == "azure")
        #expect(LLMProvider.ollama.rawValue == "local")
    }

    // MARK: - Display names use product names (not company names)

    @Test func displayNames_useProductNames() {
        #expect(LLMProvider.claude.displayName == "Claude")
        #expect(LLMProvider.chatGPT.displayName == "ChatGPT")
        #expect(LLMProvider.gemini.displayName == "Gemini")
        #expect(LLMProvider.azure.displayName == "Azure OpenAI")
        #expect(LLMProvider.ollama.displayName == "Ollama")
    }

    // MARK: - API key requirements

    @Test func needsAPIKey_cloudProviders() {
        #expect(LLMProvider.claude.needsAPIKey == true)
        #expect(LLMProvider.chatGPT.needsAPIKey == true)
        #expect(LLMProvider.gemini.needsAPIKey == true)
        #expect(LLMProvider.azure.needsAPIKey == true)
    }

    @Test func needsAPIKey_ollama_false() {
        #expect(LLMProvider.ollama.needsAPIKey == false)
    }

    @Test func keychainProvider_nil_forOllama() {
        #expect(LLMProvider.ollama.keychainProvider == nil)
    }

    @Test func keychainProvider_matchesRawValue_forCloudProviders() {
        for provider in LLMProvider.allCases where provider.needsAPIKey {
            #expect(provider.keychainProvider == provider.rawValue)
        }
    }

    // MARK: - Default models

    @Test func defaultModels_areNonEmpty() {
        for provider in LLMProvider.allCases {
            #expect(!provider.defaultModel.isEmpty)
        }
    }

    @Test func availableModels_containDefault() {
        for provider in LLMProvider.allCases {
            #expect(provider.availableModels.contains(provider.defaultModel),
                    "\(provider.displayName) default model not in available models")
        }
    }

    // MARK: - Provider status

    @Test func providerStatus_isConfigured_onlyWhenOnline() {
        #expect(ProviderStatus.online.isConfigured == true)
        #expect(ProviderStatus.notSetUp.isConfigured == false)
        #expect(ProviderStatus.invalid.isConfigured == false)
        #expect(ProviderStatus.unavailable.isConfigured == false)
        #expect(ProviderStatus.checking.isConfigured == false)
    }

    @Test func providerStatus_labels_areNonEmpty() {
        let statuses: [ProviderStatus] = [.online, .notSetUp, .invalid, .unavailable, .checking]
        for status in statuses {
            #expect(!status.label.isEmpty)
        }
    }
}
