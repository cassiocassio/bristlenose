import Foundation
import Testing
@testable import Bristlenose

/// The Debug menu opens whatever address the server names, so the one rule worth pinning is that
/// it is a path under `/admin/` on this machine and nothing else (T21).
struct AdminPanelActionTests {
    @Test("A path under /admin/ becomes a loopback address on the serve's port")
    func adminPathBecomesLoopbackURL() {
        let url = AdminPanelAction.url(port: 8490, path: "/admin/?t=abc_DEF-123")
        #expect(url?.absoluteString == "http://127.0.0.1:8490/admin/?t=abc_DEF-123")
    }

    @Test("Anything that is not a path under /admin/ is refused")
    func otherPathsAreRefused() {
        for bad in [nil, "", "/api/projects", "admin/", "//evil.example/admin/", "/admin//evil.example",
                    "https://evil.example/admin/", "/admin/..\\x", "/administrator/"] as [String?] {
            #expect(AdminPanelAction.url(port: 8490, path: bad) == nil, "\(bad ?? "nil")")
        }
    }
}
