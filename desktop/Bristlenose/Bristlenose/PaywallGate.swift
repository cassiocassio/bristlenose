import Combine
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

    /// Called whenever the subscription state changes to one that lets a run
    /// start: the runner retries the automatic starts this gate held
    /// (`PipelineRunner.retryHeldStarts`). Called a turn after the change, so
    /// `allowsStart` already reads the new state.
    var startsAllowed: (@MainActor () -> Void)?
    private var stateWatch: AnyCancellable?

    init(channel: DistributionChannel = SubscriptionGate.effectiveChannel(.current),
         store: SubscriptionStore? = nil, usesLiveStore: Bool = true) {
        self.channel = channel
        self.store = store ?? (usesLiveStore ? SubscriptionStore.make(channel: channel) : nil)
        // `$state` publishes before the property changes; hop a turn.
        stateWatch = self.store?.$state.removeDuplicates().sink { [weak self] new in
            guard let self, SubscriptionAccess.canStartAnalysis(new, channel: self.channel) else { return }
            Task { @MainActor [weak self] in self?.startsAllowed?() }
        }
    }

    /// Whether a run may start now. When it may not and the researcher asked
    /// for it, the paywall is raised for that study; a run the app started by
    /// itself (a restored queue) does not start and shows nothing, and its
    /// caller keeps it for `startsAllowed`.
    func allowsStart(project: Project, clean: Bool, researcherAsked: Bool) -> Bool {
        let state = store?.state ?? .unknown
        if SubscriptionAccess.canStartAnalysis(state, channel: channel) { return true }
        if researcherAsked { pending = Pending(project: project, clean: clean) }
        return false
    }

    /// The window that is showing the sheet. A window claims it while it is key
    /// and keeps it until the sheet goes: presenting a sheet makes the sheet
    /// the key window and the parent reports not-key, so a rule of "show only
    /// while I am key" dismisses the sheet it just showed, and flashes forever.
    private var presentingWindow: UUID?

    /// What `window` should present now. Only the key window starts showing the
    /// sheet, and no second window takes it while one has it, but the window
    /// that has it keeps it whatever its key state does until `pending` clears.
    func paywall(for window: UUID, isKey: Bool) -> Pending? {
        guard let pending else {
            presentingWindow = nil
            return nil
        }
        if presentingWindow == window { return pending }
        if presentingWindow == nil, isKey {
            presentingWindow = window
            return pending
        }
        return nil
    }

    /// The sheet's "Not Now".
    func dismissPaywall() {
        pending = nil
        presentingWindow = nil
    }

    /// Subscribed while the sheet was up: start what was asked for, with no
    /// second click.
    func resumePending() {
        guard let p = pending else { return }
        pending = nil
        presentingWindow = nil
        resume?(p.project, p.clean)
    }

    /// Back to the foreground: a subscription that lapsed, or was approved by
    /// a family organiser, while the app was open is noticed here.
    func refreshOnActivation() {
        guard let store else { return }
        Task { await store.refresh() }
    }
}
