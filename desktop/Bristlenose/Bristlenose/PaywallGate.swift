import Foundation

/// Where the subscription meets the app: owns the store (App Store channel
/// only), decides whether a run may start, and holds the study that is waiting
/// on the paywall sheet. One per app, like `ServeFleet`.
///
/// The rule itself is `SubscriptionAccess.canStartAnalysis`; this only applies
/// it at the one place every analysis passes, `PipelineRunner.start`.
@MainActor
final class SubscriptionGate: ObservableObject {

    struct Pending: Identifiable, Equatable {
        let id = UUID()
        let project: Project
        let clean: Bool
        static func == (a: Pending, b: Pending) -> Bool { a.id == b.id }
    }

    let channel: DistributionChannel
    /// nil everywhere except the App Store channel.
    let store: SubscriptionStore?
    /// The study waiting on the sheet, if any.
    @Published var pending: Pending?
    /// Starts the run once the researcher is subscribed (the runner's own
    /// `start`, which asks this gate again and now passes).
    var resume: (@MainActor (Project, Bool) -> Void)?

    /// The debug seed: a local Xcode build (`.debug`) is not the App Store
    /// channel, so it has no store and no paywall. To test the purchase with
    /// `Bristlenose.storekit`, switch on `BRISTLENOSE_DEBUG_SUBSCRIPTION` in the
    /// "Bristlenose Store" scheme. Honoured in `.debug` only; the `.dmg` and the
    /// App Store build ignore it. Compiled into Debug only: a Release Mach-O must
    /// not carry the name at all (`desktop/scripts/check-release-binary.sh`
    /// refuses any `BRISTLENOSE_DEBUG_*` literal), and `.debug` never occurs there.
    nonisolated static func effectiveChannel(_ channel: DistributionChannel,
                                 environment: [String: String] = ProcessInfo.processInfo.environment)
        -> DistributionChannel {
        #if DEBUG
        if channel == .debug, environment["BRISTLENOSE_DEBUG_SUBSCRIPTION"] == "1" {
            return .appStoreOrTestFlight
        }
        #endif
        return channel
    }

    init(channel: DistributionChannel = SubscriptionGate.effectiveChannel(.current),
         store: SubscriptionStore? = nil, usesLiveStore: Bool = true) {
        self.channel = channel
        self.store = store ?? (usesLiveStore ? SubscriptionStore.make(channel: channel) : nil)
    }

    /// Whether a run may start now. When it may not and the researcher asked
    /// for it, the paywall is raised for that study; a run the app started by
    /// itself (a restored queue) just does not start, and shows nothing.
    func allowsStart(project: Project, clean: Bool, researcherAsked: Bool) -> Bool {
        let state = store?.state ?? .unknown
        if SubscriptionAccess.canStartAnalysis(state, channel: channel) { return true }
        if researcherAsked { pending = Pending(project: project, clean: clean) }
        return false
    }

    /// The sheet's "Not Now".
    func dismissPaywall() { pending = nil }

    /// Subscribed while the sheet was up: start what was asked for, with no
    /// second click.
    func resumePending() {
        guard let p = pending else { return }
        pending = nil
        resume?(p.project, p.clean)
    }

    /// Back to the foreground: a subscription that lapsed, or was approved by
    /// a family organiser, while the app was open is noticed here.
    func refreshOnActivation() {
        guard let store else { return }
        Task { await store.refresh() }
    }
}
