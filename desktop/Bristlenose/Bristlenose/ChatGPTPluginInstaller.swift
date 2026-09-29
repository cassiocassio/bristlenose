import AppKit
import Foundation

/// Installs Bristlenose into ChatGPT as a plugin (design-mcp-native-proxy §1.2,
/// §6.9 D7/D8).
///
/// The app bundle carries a one-plugin marketplace, `chatgpt-marketplace/`,
/// built by `desktop/mcp-helper/build-helper.sh` around the signed helper.
/// ChatGPT installs from it through its own link:
///
///     codex://plugins/bristlenose?marketplacePath=<absolute path to marketplace.json>
///
/// ChatGPT then shows its plugin page, the researcher clicks Install plugin,
/// and ChatGPT copies the plugin into its own cache. That consent moment is
/// ChatGPT's, as the `.mcpb` one is Claude's. We register nothing and write
/// nothing into ChatGPT's settings.
///
/// The marketplace must stay INSIDE the bundle (D7): a copy in our container
/// would be a cross-team read that macOS 27 denies. A `.dmg` app run from
/// Downloads is translocated to a random read-only path, which is why that
/// case is refused with "move to Applications" rather than attempted.
enum ChatGPTPluginInstaller {

    static let chatGPTBundleID = "com.openai.codex"

    /// Why the Install Plugin… button can't act, if it can't.
    enum Availability: Equatable {
        case ready
        /// No `chatgpt-marketplace` in this build (an unsigned or ad-hoc build
        /// skips it, because such a helper cannot read the team group).
        case notBundled
        case noChatGPT
        /// ChatGPT is installed but does not handle `codex://` links.
        case chatGPTTooOld
        /// Running translocated (a `.dmg` app opened in place).
        case notInApplications
    }

    /// Pure: the decision, from the four facts that make it.
    static func availability(bundlePath: String, marketplaceExists: Bool,
                             chatGPTInstalled: Bool, handlesCodexLinks: Bool) -> Availability {
        if bundlePath.contains("/AppTranslocation/") { return .notInApplications }
        if !marketplaceExists { return .notBundled }
        if !chatGPTInstalled { return .noChatGPT }
        if !handlesCodexLinks { return .chatGPTTooOld }
        return .ready
    }

    static var marketplaceRoot: URL? {
        Bundle.main.resourceURL?.appendingPathComponent("chatgpt-marketplace", isDirectory: true)
    }

    static var marketplaceFile: URL? {
        marketplaceRoot?.appendingPathComponent(".agents/plugins/marketplace.json")
    }

    /// The plugin's stamped `<release>+<build>`, which ChatGPT also shows as
    /// its version. Nil when the build carries no plugin.
    static var bundledVersion: String? {
        guard let url = marketplaceRoot?.appendingPathComponent("plugins/bristlenose/.codex-plugin/plugin.json"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let version = json["version"] as? String, !version.isEmpty
        else { return nil }
        return version
    }

    static var currentAvailability: Availability {
        let workspace = NSWorkspace.shared
        return availability(
            bundlePath: Bundle.main.bundlePath,
            marketplaceExists: marketplaceFile.map { FileManager.default.fileExists(atPath: $0.path) } ?? false,
            chatGPTInstalled: workspace.urlForApplication(withBundleIdentifier: chatGPTBundleID) != nil,
            handlesCodexLinks: URL(string: "codex://plugins").flatMap(workspace.urlForApplication(toOpen:)) != nil)
    }

    /// Pure: the link, with the path encoded STRICTLY. Only unreserved
    /// characters survive, so `/`, spaces, `&`, `+`, `#` and `%` in a folder
    /// name can never end the query or smuggle a second parameter.
    static func installURL(marketplacePath: String) -> URL? {
        var unreserved = CharacterSet()
        unreserved.insert(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        guard let encoded = marketplacePath.addingPercentEncoding(withAllowedCharacters: unreserved)
        else { return nil }
        return URL(string: "codex://plugins/bristlenose?marketplacePath=\(encoded)")
    }

    /// Hand the link to ChatGPT. Returns whether LaunchServices accepted it.
    @discardableResult
    static func install() -> Bool {
        guard currentAvailability == .ready,
              let file = marketplaceFile,
              let url = installURL(marketplacePath: file.path)
        else { return false }
        return NSWorkspace.shared.open(url)
    }
}
