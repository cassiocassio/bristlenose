import Foundation
import Testing
@testable import Bristlenose

/// The ChatGPT plugin row's decisions (design-mcp-native-proxy §6.9 P3), tested
/// without ChatGPT: which state the button is in, and the link it opens.
@Suite("ChatGPT plugin installer")
struct ChatGPTPluginInstallerTests {

    // MARK: - Availability

    @Test func ready_whenBundledAndChatGPTHandlesItsLinks() {
        #expect(ChatGPTPluginInstaller.availability(
            bundlePath: "/Applications/Bristlenose.app", marketplaceExists: true,
            chatGPTInstalled: true, handlesCodexLinks: true) == .ready)
    }

    @Test func translocatedAppIsRefused_beforeAnythingElse() {
        // A .dmg app opened in place runs from a random read-only path, and a
        // link pointing into it breaks the moment the app quits (D7).
        #expect(ChatGPTPluginInstaller.availability(
            bundlePath: "/private/var/folders/x/AppTranslocation/ABC/d/Bristlenose.app",
            marketplaceExists: true, chatGPTInstalled: true, handlesCodexLinks: true) == .notInApplications)
    }

    @Test func noPluginInThisBuild() {
        #expect(ChatGPTPluginInstaller.availability(
            bundlePath: "/Applications/Bristlenose.app", marketplaceExists: false,
            chatGPTInstalled: true, handlesCodexLinks: true) == .notBundled)
    }

    @Test func noChatGPT_isNotTheSameAsAnOldOne() {
        #expect(ChatGPTPluginInstaller.availability(
            bundlePath: "/Applications/Bristlenose.app", marketplaceExists: true,
            chatGPTInstalled: false, handlesCodexLinks: false) == .noChatGPT)
        #expect(ChatGPTPluginInstaller.availability(
            bundlePath: "/Applications/Bristlenose.app", marketplaceExists: true,
            chatGPTInstalled: true, handlesCodexLinks: false) == .chatGPTTooOld)
    }

    // MARK: - The link

    @Test func link_carriesTheMarketplaceFile_encodedStrictly() throws {
        let url = try #require(ChatGPTPluginInstaller.installURL(
            marketplacePath: "/Applications/Bristlenose.app/Contents/Resources/chatgpt-marketplace/.agents/plugins/marketplace.json"))
        #expect(url.scheme == "codex")
        #expect(url.absoluteString.hasPrefix("codex://plugins/bristlenose?marketplacePath=%2FApplications%2FBristlenose.app%2F"))
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
        #expect(items?.count == 1)
        #expect(items?.first?.value == "/Applications/Bristlenose.app/Contents/Resources/chatgpt-marketplace/.agents/plugins/marketplace.json")
    }

    @Test func link_survivesAFolderNameThatLooksLikeQuerySyntax() throws {
        let path = "/Users/a b/My & Co + #1 50%/Bristlenose.app/x/marketplace.json"
        let url = try #require(ChatGPTPluginInstaller.installURL(marketplacePath: path))
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems
        // One parameter, decoded back to exactly the path: nothing ended the
        // query early and nothing smuggled in a second one.
        #expect(items?.count == 1)
        #expect(items?.first?.name == "marketplacePath")
        #expect(items?.first?.value == path)
    }

    // MARK: - Per-host proxy builds (D8)

    @Test func proxyVersions_readsEachHost_andDropsUnreadableEntries() {
        let json: [String: Any] = ["proxy_version": "0.26.0+854270a",
                                   "proxy_versions": ["ChatGPT": "0.32.0+3950", "Claude": "", "X": 7]]
        #expect(AgentActivity.proxyVersions(json) == ["ChatGPT": "0.32.0+3950"])
        #expect(AgentActivity.proxyVersion(json) == "0.26.0+854270a")
        #expect(AgentActivity.proxyVersions(["calls": 1]).isEmpty)
    }
}
