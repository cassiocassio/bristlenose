import Foundation
import Testing
@testable import Bristlenose

/// A Developer-ID `.dmg` reaches testers who have never hand-set a client ID, so
/// the build itself must carry one for Teams, for Meet and (since Zoom approved the
/// beta share, 9 Nov 2026) for Zoom. Until 18 Oct 2026 the
/// IDs lived only in the dev Mac's sandboxed defaults: every sign-in worked
/// there and could not start anywhere else.
///
/// The test host is the real app, so `Bundle.main` here is the built
/// `Bristlenose.app` and its merged Info.plist, not a fixture.
@Suite("OAuth client IDs ship in the bundle")
struct OAuthBundledClientIDTests {

    private static func emptyDefaults(_ name: String) -> UserDefaults {
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    private static func bundled(_ key: String) -> String? {
        (Bundle.main.object(forInfoDictionaryKey: key) as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    @Test("The host bundle is the app, so the checks below read the shipped plist")
    func hostIsTheApp() {
        #expect(Bundle.main.bundleIdentifier == "app.bristlenose")
    }

    @Test("Microsoft's client ID is baked in, and is a GUID")
    func microsoftClientID() throws {
        let id = try #require(Self.bundled(MicrosoftOAuthConfig.clientIDDefaultsKey))
        #expect(UUID(uuidString: id) != nil, "MicrosoftOAuthClientID is not a GUID: \(id)")
    }

    @Test("Microsoft's redirect is baked in, and is the one the registration lists")
    func microsoftRedirect() {
        #expect(Self.bundled(MicrosoftOAuthConfig.redirectDefaultsKey)
                == "msauth.app.bristlenose://auth")
    }

    @Test("Google's client ID is baked in, and is an installed-app client")
    func googleClientID() throws {
        let id = try #require(Self.bundled(GoogleOAuthConfig.defaultsKey))
        #expect(id.hasSuffix(".apps.googleusercontent.com"), "GoogleOAuthClientID: \(id)")
        #expect(!id.contains("__"), "GoogleOAuthClientID is still a placeholder")
    }

    @Test("Zoom's production public client ID is baked in (beta share approved 9 Nov 2026)")
    func zoomClientID() throws {
        let id = try #require(Self.bundled(ZoomOAuthConfig.clientIDDefaultsKey))
        // The production public client, not the development one or the confidential one
        // (`_K7QaGWRe265MNrSecZDQ`), which would fail at the token exchange without a secret.
        #expect(id == "5p8ZT9wKRrmm7pHrwsvzWw")
    }

    @Test("Zoom's redirect is the HTTPS one in Zoom's allow list, on our associated domain")
    func zoomRedirect() throws {
        let redirect = try #require(Self.bundled(ZoomOAuthConfig.redirectDefaultsKey))
        #expect(redirect == "https://bristlenose.app/auth/zoom")
        let config = ZoomOAuthConfig(publicClientID: "x", redirectURI: redirect)
        #expect(config.callbackHost == "bristlenose.app" && config.callbackPath == "/auth/zoom")
    }

    @Test("With nothing hand-set, all three platforms resolve from the bundle")
    func resolvesWithNoDefaults() {
        let defaults = Self.emptyDefaults("oauth-bundled-empty")
        let microsoft = MicrosoftOAuthConfig.resolve(defaults: defaults, bundle: .main)
        #expect(microsoft?.clientID == Self.bundled(MicrosoftOAuthConfig.clientIDDefaultsKey))
        #expect(microsoft?.redirectURI == "msauth.app.bristlenose://auth")
        #expect(microsoft?.tenant == "common")
        let google = GoogleOAuthConfig.resolve(defaults: defaults, bundle: .main)
        #expect(google?.clientID == Self.bundled(GoogleOAuthConfig.defaultsKey))
        let zoom = ZoomOAuthConfig.resolve(defaults: defaults, bundle: .main)
        #expect(zoom?.publicClientID == "5p8ZT9wKRrmm7pHrwsvzWw")
        #expect(zoom?.redirectURI == "https://bristlenose.app/auth/zoom")
    }

    @Test("A hand-set value still overrides the bundle, for development")
    func defaultsOverride() {
        let defaults = Self.emptyDefaults("oauth-bundled-override")
        defaults.set("11111111-2222-3333-4444-555555555555",
                     forKey: MicrosoftOAuthConfig.clientIDDefaultsKey)
        defaults.set("999-test.apps.googleusercontent.com", forKey: GoogleOAuthConfig.defaultsKey)
        #expect(MicrosoftOAuthConfig.resolve(defaults: defaults, bundle: .main)?.clientID
                == "11111111-2222-3333-4444-555555555555")
        #expect(GoogleOAuthConfig.resolve(defaults: defaults, bundle: .main)?.clientID
                == "999-test.apps.googleusercontent.com")
        defaults.removePersistentDomain(forName: "oauth-bundled-override")
    }
}
