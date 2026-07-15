import Foundation
import Testing
@testable import Bristlenose

/// The serve-free path is load-bearing for the expired-alpha `.dmg` flow: with
/// no sidecar there's nothing to answer `/api/health`, so `load()` MUST honour
/// the `preresolved` guard and keep the supplied `FeedbackConfig` rather than
/// probing port 0 (which resolves to `.unavailable` → silent clipboard-only
/// degradation). Pure, no network. Suite is `@MainActor` — the model is.
@MainActor
@Suite struct FeedbackSheetModelTests {

    @Test func serverlessLoadSkipsHealthProbeAndKeepsConfig() async {
        let model = FeedbackSheetModel(config: .serverless, i18n: I18n())
        await model.load()

        // Ready without a probe, and the config is the serverless one we passed
        // — NOT overwritten by a failed port-0 health probe (which would be
        // `.unavailable`, url == nil → clipboard-only).
        #expect(model.phase == .ready)
        #expect(model.config.url == FeedbackEndpoint.defaultURL)
        #expect(model.config.enabled)
    }
}
